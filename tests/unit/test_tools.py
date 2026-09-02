import json

from langgraph.checkpoint.memory import MemorySaver

from revenueflow.agents.graph import build_graph, graph_tool_names
from revenueflow.tools import (
    CHECKOUT_TOOL_NAMES,
    NEGOTIATION_TOOL_NAMES,
    RECOMMENDATION_TOOL_NAMES,
    get_customer_sales_context,
    get_inventory,
    get_product_details,
    search_products,
)


def test_checkout_tool_names_are_isolated() -> None:
    assert CHECKOUT_TOOL_NAMES.isdisjoint(RECOMMENDATION_TOOL_NAMES | NEGOTIATION_TOOL_NAMES)
    assert CHECKOUT_TOOL_NAMES == {"create_quote", "create_order", "create_payment_sandbox"}


def test_graph_tool_names_include_checkout() -> None:
    names = graph_tool_names(build_graph(MemorySaver()))
    assert CHECKOUT_TOOL_NAMES <= names


async def test_search_products_returns_serializable_rows(db: None) -> None:
    rows = await search_products("1cv")
    assert len(rows) >= 1
    for row in rows:
        assert isinstance(row, dict)
        assert row["product_id"]
        assert row["name"]
        json.dumps(row)


async def test_get_product_details_hit_and_miss(db: None) -> None:
    rows = await search_products("1cv")
    product_id = rows[0]["product_id"]

    detail = await get_product_details(product_id)
    assert isinstance(detail, dict)
    assert detail["product_id"] == product_id

    assert await get_product_details("NOPE") is None


async def test_get_inventory_hit_and_fallback(db: None) -> None:
    rows = await search_products("1cv")
    product_id = rows[0]["product_id"]

    view = await get_inventory(product_id, 1)
    assert isinstance(view, dict)
    assert isinstance(view["fulfillable"], bool)

    missing = await get_inventory("NOPE", 1)
    assert missing == {
        "product_id": "NOPE",
        "available": 0,
        "fulfillable": False,
        "lead_time_days": None,
    }


async def test_get_customer_sales_context_returns_rows(db: None) -> None:
    rows = await get_customer_sales_context("CUST-001")
    assert len(rows) >= 1
    assert {"product_id", "last_qty", "last_order_at"} <= rows[0].keys()
