"""LangGraph turn graph: classify -> supervisor -> [recommendation] -> respond.

Implements the supervisor / agent split (SPEC-023/024/025) and D2's Postgres
checkpointer wiring: ``build_graph`` takes any LangGraph checkpointer and passes
it straight to ``compile``. In ``LLM_STUB`` mode every node is deterministic and
no real model is called.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from revenueflow.agents.negotiation import await_approval_node, negotiation_node
from revenueflow.agents.recommendation import recommendation_node
from revenueflow.agents.state import TurnState
from revenueflow.domain.models import Intent
from revenueflow.observability import get_tracer
from revenueflow.services import classify, generate
from revenueflow.tools.registry import NEGOTIATION_TOOL_NAMES, RECOMMENDATION_TOOL_NAMES

RECO_INTENTS: frozenset[str] = frozenset({Intent.PRODUCT_SEARCH.value, Intent.RECOMMENDATION.value})
NEGOTIATION_INTENTS: frozenset[str] = frozenset(
    {Intent.NEGOTIATION.value, Intent.PRICE_REQUEST.value, Intent.QUOTE_REQUEST.value}
)


async def classify_intent_node(state: TurnState) -> dict[str, Any]:
    """Classify the customer text into a controlled intent plus confidence."""

    with get_tracer().span("node.classify_intent"):
        intent, confidence = await classify(state["customer_text"])
    return {"intent": intent.value, "confidence": confidence}


async def supervisor_node(state: TurnState) -> dict[str, Any]:
    """Pass-through supervisor; only records the routing decision for now."""

    get_tracer().event("supervisor.route", attrs={"intent": state["intent"]})
    return {}


def route_from_supervisor(state: TurnState) -> str:
    """Send reco- and negotiation-shaped intents through the agent path, else reply."""

    if state["intent"] in RECO_INTENTS or state["intent"] in NEGOTIATION_INTENTS:
        return "recommendation"
    return "respond"


def route_after_recommendation(state: TurnState) -> str:
    """Continue into the Negotiation Agent for discount-shaped intents, else reply."""

    return "negotiation" if state["intent"] in NEGOTIATION_INTENTS else "respond"


def route_after_negotiation(state: TurnState) -> str:
    """Pause at the approval gate when an approval is pending, else end the turn."""

    return "await_approval" if state.get("pending_approval_id") else END


async def respond_node(state: TurnState) -> dict[str, Any]:
    """Draft the customer reply, grounded only in ``tool_results``."""

    with get_tracer().span("node.respond"):
        reply = await generate(
            intent=Intent(state["intent"]),
            customer_text=state["customer_text"],
            tool_results=state.get("tool_results", []),
        )
    return {"reply": reply}


def build_graph(checkpointer: Any) -> Any:
    """Build and compile the turn graph with the given LangGraph checkpointer."""

    graph = StateGraph(TurnState)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("recommendation", recommendation_node)
    graph.add_node("negotiation", negotiation_node)
    graph.add_node("await_approval", await_approval_node)
    graph.add_node("respond", respond_node)
    graph.add_edge(START, "classify_intent")
    graph.add_edge("classify_intent", "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {"recommendation": "recommendation", "respond": "respond"},
    )
    graph.add_conditional_edges(
        "recommendation",
        route_after_recommendation,
        {"negotiation": "negotiation", "respond": "respond"},
    )
    graph.add_conditional_edges(
        "negotiation",
        route_after_negotiation,
        {"await_approval": "await_approval", END: END},
    )
    graph.add_edge("await_approval", END)
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer)


def graph_tool_names(compiled: Any) -> set[str]:
    """Tool ``__name__``s reachable from the agent nodes.

    The recommendation and negotiation nodes only ever call tools from
    ``revenueflow.tools.registry``, so this returns the registry names by
    construction. When the real ToolNode lands this will introspect the tools
    bound to those nodes on ``compiled``.
    """

    return set(RECOMMENDATION_TOOL_NAMES) | set(NEGOTIATION_TOOL_NAMES)
