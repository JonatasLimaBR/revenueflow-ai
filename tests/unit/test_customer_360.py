import json
from decimal import Decimal
from uuid import uuid4

from revenueflow.repositories import customer as customer_repo
from revenueflow.repositories.db import execute, unit_of_work
from revenueflow.tools.catalog import get_customer_360

_QUOTE_INSERT = """
INSERT INTO quote (quote_id, conversation_id, customer_ref, items, total, expiration, status)
VALUES (%s, %s, %s, '[]'::jsonb, %s, now() + interval '7 days', %s)
"""


async def test_revenue_and_orders_respect_365d_window(db: None) -> None:
    async with unit_of_work() as conn:
        view = await customer_repo.customer_360(conn, "CUST-001")

    assert view["orders_12m"] == 2
    assert view["revenue_12m"] == Decimal("10398.00")
    assert view["average_ticket"] == Decimal("5199.00")


async def test_last_purchase_and_interval_from_multiple_orders(db: None) -> None:
    async with unit_of_work() as conn:
        view = await customer_repo.customer_360(conn, "CUST-001")

    assert view["last_purchase"].date().isoformat() == "2026-07-01"
    assert view["purchase_interval_days"] == 77.0


async def test_single_order_has_no_interval(db: None) -> None:
    async with unit_of_work() as conn:
        view = await customer_repo.customer_360(conn, "CUST-002")

    assert view["orders_12m"] == 1
    assert view["purchase_interval_days"] is None


async def test_customer_without_history_returns_zeroed_view(db: None) -> None:
    async with unit_of_work() as conn:
        view = await customer_repo.customer_360(conn, "CUST-003")

    assert view == {
        "orders_12m": 0,
        "revenue_12m": Decimal("0"),
        "average_ticket": Decimal("0"),
        "last_purchase": None,
        "purchase_interval_days": None,
        "preferred_products": [],
        "open_quotes": {"count": 0, "quote_ids": []},
    }


async def test_preferred_products_ordered_by_quantity(db: None) -> None:
    async with unit_of_work() as conn:
        view = await customer_repo.customer_360(conn, "CUST-001")

    assert view["preferred_products"] == ["PMP-050-PER", "PMP-100-PER", "PMP-100-CEN"]


async def test_open_quotes_counts_only_sent_for_the_customer(db: None) -> None:
    customer_id = f"CUST-OQ-{uuid4().hex[:8]}"
    sent_a, sent_b = uuid4().hex, uuid4().hex
    async with unit_of_work() as conn:
        await execute(conn, _QUOTE_INSERT, (sent_a, uuid4().hex, customer_id, "100.00", "SENT"))
        await execute(conn, _QUOTE_INSERT, (sent_b, uuid4().hex, customer_id, "200.00", "SENT"))
        await execute(
            conn, _QUOTE_INSERT, (uuid4().hex, uuid4().hex, customer_id, "300.00", "ACCEPTED")
        )
        view = await customer_repo.customer_360(conn, customer_id)

    assert view["open_quotes"]["count"] == 2
    assert set(view["open_quotes"]["quote_ids"]) == {sent_a, sent_b}


async def test_tool_return_is_json_safe(db: None) -> None:
    result = await get_customer_360("CUST-001")
    json.dumps(result)
    assert isinstance(result["revenue_12m"], str)
    assert set(result) == {
        "orders_12m",
        "revenue_12m",
        "average_ticket",
        "last_purchase",
        "purchase_interval_days",
        "preferred_products",
        "open_quotes",
    }
