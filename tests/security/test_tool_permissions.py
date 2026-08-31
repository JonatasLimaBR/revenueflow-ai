from langgraph.checkpoint.memory import MemorySaver

from revenueflow.agents.graph import build_graph, graph_tool_names
from revenueflow.tools.registry import NEGOTIATION_TOOL_NAMES, RECOMMENDATION_TOOL_NAMES

ALLOWED = {
    "recommendation": {
        "search_products",
        "get_product_details",
        "get_inventory",
        "get_customer_sales_context",
    },
    "negotiation": {"get_price", "calculate_margin", "propose_allowed_discount"},
    "checkout": {
        "get_quote",
        "get_inventory",
        "get_price",
        "create_quote",
        "create_order",
        "create_payment_sandbox",
    },
    "opportunity": {"get_customer_sales_context", "find_opportunities", "create_opportunity"},
}


def test_recommendation_agent_has_no_write_tools() -> None:
    forbidden = {"create_quote", "create_order", "create_payment_sandbox", "set_discount"}
    assert ALLOWED["recommendation"].isdisjoint(forbidden)


def test_no_agent_has_generic_set_discount() -> None:
    assert all("set_discount" not in tools for tools in ALLOWED.values())


def test_opportunity_agent_cannot_send_whatsapp_directly() -> None:
    assert "send_whatsapp_direct" not in ALLOWED["opportunity"]


def test_recommendation_tool_names_are_exact() -> None:
    assert RECOMMENDATION_TOOL_NAMES == {
        "search_products",
        "get_product_details",
        "get_inventory",
        "get_customer_sales_context",
    }


def test_recommendation_tool_names_disjoint_from_write_tools() -> None:
    write_tools = {
        "create_quote",
        "create_order",
        "create_payment_sandbox",
        "set_discount",
        "send_whatsapp_direct",
    }
    assert RECOMMENDATION_TOOL_NAMES.isdisjoint(write_tools)


def test_graph_reachable_tools_stay_within_registry() -> None:
    compiled = build_graph(MemorySaver())
    assert graph_tool_names(compiled) <= (
        set(RECOMMENDATION_TOOL_NAMES) | set(NEGOTIATION_TOOL_NAMES)
    )


def test_negotiation_tool_names_are_exact() -> None:
    assert NEGOTIATION_TOOL_NAMES == {"get_price", "calculate_margin", "propose_allowed_discount"}


def test_negotiation_tool_names_disjoint_from_write_tools() -> None:
    write_tools = {
        "set_discount",
        "create_quote",
        "create_order",
        "create_payment_sandbox",
        "send_whatsapp_direct",
    }
    assert NEGOTIATION_TOOL_NAMES.isdisjoint(write_tools)


def test_graph_reachable_tools_match_both_registries() -> None:
    compiled = build_graph(MemorySaver())
    assert graph_tool_names(compiled) == RECOMMENDATION_TOOL_NAMES | NEGOTIATION_TOOL_NAMES
