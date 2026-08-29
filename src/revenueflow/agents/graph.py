"""LangGraph turn graph: classify -> supervisor -> [recommendation] -> respond.

Implements the supervisor / agent split (SPEC-023/024/025) and D2's Postgres
checkpointer wiring: ``build_graph`` takes any LangGraph checkpointer and passes
it straight to ``compile``. In ``LLM_STUB`` mode every node is deterministic and
no real model is called.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from revenueflow.agents.recommendation import recommendation_node
from revenueflow.agents.state import TurnState
from revenueflow.domain.models import Intent
from revenueflow.observability import get_tracer
from revenueflow.services import classify, generate
from revenueflow.tools.registry import RECOMMENDATION_TOOL_NAMES

RECO_INTENTS: frozenset[str] = frozenset({Intent.PRODUCT_SEARCH.value, Intent.RECOMMENDATION.value})


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
    """Send reco-shaped intents to the Recommendation Agent, else straight to reply."""

    return "recommendation" if state["intent"] in RECO_INTENTS else "respond"


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
    graph.add_node("respond", respond_node)
    graph.add_edge(START, "classify_intent")
    graph.add_edge("classify_intent", "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {"recommendation": "recommendation", "respond": "respond"},
    )
    graph.add_edge("recommendation", "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer)


def graph_tool_names(compiled: Any) -> set[str]:
    """Tool ``__name__``s reachable from the recommendation node.

    The recommendation node only ever calls tools from
    ``revenueflow.tools.registry``, so this returns the registry names by
    construction. When the real ToolNode lands this will introspect the tools
    bound to that node on ``compiled``.
    """

    return set(RECOMMENDATION_TOOL_NAMES)
