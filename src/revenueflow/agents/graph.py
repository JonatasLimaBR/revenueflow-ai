"""LangGraph turn graph: classify -> supervisor -> [recommendation] -> respond.

Implements the supervisor / agent split (SPEC-023/024/025) and D2's Postgres
checkpointer wiring: ``build_graph`` takes any LangGraph checkpointer and passes
it straight to ``compile``. In ``LLM_STUB`` mode every node is deterministic and
no real model is called.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from revenueflow.agents.apply_decision import apply_decision_node
from revenueflow.agents.checkout import checkout_node
from revenueflow.agents.handoff import handoff_node, to_handoff
from revenueflow.agents.negotiation import await_approval_node, negotiation_node
from revenueflow.agents.recommendation import recommendation_node
from revenueflow.agents.state import TurnState
from revenueflow.config import get_settings
from revenueflow.domain.errors import LLMError
from revenueflow.domain.models import HandoffReason, Intent
from revenueflow.observability import get_tracer
from revenueflow.policies.handoff_policy import should_handoff
from revenueflow.repositories import checkout as checkout_repo
from revenueflow.repositories.db import unit_of_work
from revenueflow.services import classify, generate
from revenueflow.tools.registry import (
    CHECKOUT_TOOL_NAMES,
    NEGOTIATION_TOOL_NAMES,
    RECOMMENDATION_TOOL_NAMES,
)

RECO_INTENTS: frozenset[str] = frozenset({Intent.PRODUCT_SEARCH.value, Intent.RECOMMENDATION.value})
NEGOTIATION_INTENTS: frozenset[str] = frozenset(
    {Intent.NEGOTIATION.value, Intent.PRICE_REQUEST.value, Intent.QUOTE_REQUEST.value}
)
CHECKOUT_INTENTS: frozenset[str] = frozenset({Intent.ORDER_REQUEST.value})


async def classify_intent_node(state: TurnState) -> dict[str, Any]:
    """Classify the customer text into a controlled intent plus confidence."""

    with get_tracer().span("node.classify_intent"):
        try:
            intent, confidence = await classify(state["customer_text"])
        except LLMError:
            return to_handoff("intent")
    return {"intent": intent.value, "confidence": confidence}


async def supervisor_node(state: TurnState) -> dict[str, Any]:
    """Surface any open quote, then hand off on an explicit request or low confidence.

    The handoff check runs here (not in ``classify_intent``) so an open checkout
    quote always keeps the turn: a terse confirmation like "sim, pode fechar"
    would otherwise classify with low confidence and be transferred instead of
    completing the order.
    """

    async with unit_of_work() as conn:
        open_quote = await checkout_repo.get_open_quote(conn, state["conversation_id"])
    get_tracer().event("supervisor.route", attrs={"intent": state["intent"]})
    patch: dict[str, Any] = {
        "open_quote_id": open_quote.quote_id if open_quote is not None else None
    }
    if state["intent"] == Intent.HUMAN_SUPPORT.value:
        return {**patch, **to_handoff(HandoffReason.EXPLICIT_REQUEST.value)}
    if open_quote is None:
        settings = get_settings()
        reason = should_handoff(
            intent=state["intent"],
            confidence=state.get("confidence", 1.0),
            resolved_total=None,
            min_confidence=settings.handoff_min_confidence,
            high_value_threshold=settings.handoff_high_value_threshold,
        )
        if reason is not None:
            return {**patch, **to_handoff(reason.value)}
    return patch


def route_after_classify(state: TurnState) -> str:
    """Skip straight to the handoff node when intent classification failed."""

    return "handoff" if state.get("handoff") else "supervisor"


def route_from_supervisor(state: TurnState) -> str:
    """Handoff patch -> handoff; open quote -> gate; agent intents -> path."""

    if state.get("handoff"):
        return "handoff"
    if state.get("open_quote_id"):
        return "checkout"
    if (
        state["intent"] in RECO_INTENTS
        or state["intent"] in NEGOTIATION_INTENTS
        or state["intent"] in CHECKOUT_INTENTS
    ):
        return "recommendation"
    return "respond"


def route_after_recommendation(state: TurnState) -> str:
    """Continue into the Negotiation Agent for discount- and order-shaped intents."""

    if state["intent"] in NEGOTIATION_INTENTS or state["intent"] in CHECKOUT_INTENTS:
        return "negotiation"
    return "respond"


def route_after_negotiation(state: TurnState) -> str:
    """Handoff on a high-value order, pause at approval, route to checkout, else end."""

    if state.get("handoff"):
        return "handoff"
    if state.get("pending_approval_id"):
        return "await_approval"
    if state["intent"] in CHECKOUT_INTENTS:
        return "checkout"
    return END


def route_after_apply_decision(state: TurnState) -> str:
    """After an approved discount on an order, continue to checkout; else end."""

    if state["intent"] in CHECKOUT_INTENTS and state.get("final_outcome") in (
        "approved",
        "overridden",
    ):
        return "checkout"
    return END


async def respond_node(state: TurnState) -> dict[str, Any]:
    """Draft the customer reply, grounded only in ``tool_results``."""

    with get_tracer().span("node.respond"):
        try:
            reply = await generate(
                intent=Intent(state["intent"]),
                customer_text=state["customer_text"],
                tool_results=state.get("tool_results", []),
            )
        except LLMError:
            return to_handoff("respond")
    return {"reply": reply}


def route_after_respond(state: TurnState) -> str:
    """Route a failed response draft to the handoff node, otherwise end."""

    return "handoff" if state.get("handoff") else END


def build_graph(checkpointer: Any) -> Any:
    """Build and compile the turn graph with the given LangGraph checkpointer."""

    graph = StateGraph(TurnState)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("recommendation", recommendation_node)
    graph.add_node("negotiation", negotiation_node)
    graph.add_node("await_approval", await_approval_node)
    graph.add_node("apply_decision", apply_decision_node)
    graph.add_node("checkout", checkout_node)
    graph.add_node("respond", respond_node)
    graph.add_node("handoff", handoff_node)
    graph.add_edge(START, "classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {"supervisor": "supervisor", "handoff": "handoff"},
    )
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "recommendation": "recommendation",
            "respond": "respond",
            "checkout": "checkout",
            "handoff": "handoff",
        },
    )
    graph.add_conditional_edges(
        "recommendation",
        route_after_recommendation,
        {"negotiation": "negotiation", "respond": "respond"},
    )
    graph.add_conditional_edges(
        "negotiation",
        route_after_negotiation,
        {
            "await_approval": "await_approval",
            "checkout": "checkout",
            "handoff": "handoff",
            END: END,
        },
    )
    graph.add_edge("await_approval", "apply_decision")
    graph.add_conditional_edges(
        "apply_decision",
        route_after_apply_decision,
        {"checkout": "checkout", END: END},
    )
    graph.add_edge("checkout", END)
    graph.add_conditional_edges(
        "respond",
        route_after_respond,
        {"handoff": "handoff", END: END},
    )
    graph.add_edge("handoff", END)
    return graph.compile(checkpointer=checkpointer)


def graph_tool_names(compiled: Any) -> set[str]:
    """Tool ``__name__``s reachable from the agent nodes.

    The recommendation and negotiation nodes only ever call tools from
    ``revenueflow.tools.registry``, so this returns the registry names by
    construction. When the real ToolNode lands this will introspect the tools
    bound to those nodes on ``compiled``.
    """

    return set(RECOMMENDATION_TOOL_NAMES) | set(NEGOTIATION_TOOL_NAMES) | set(CHECKOUT_TOOL_NAMES)
