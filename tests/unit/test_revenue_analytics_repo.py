from decimal import Decimal
from uuid import uuid4

from revenueflow.repositories.db import execute, fetchall, unit_of_work

_PRODUCT = """
INSERT INTO sim_product (product_id, name, category, unit_cost)
VALUES (%s, %s, 'test', %s)
"""

_AUDIT = """
INSERT INTO audit_event (
    audit_id, trace_id, conversation_id, turn_id, agent, model, prompt_version,
    outcome, policy_decision, handoff, tools, token_usage, cost_usd, latency_ms, events
) VALUES (%s, %s, %s, %s, NULL, NULL, NULL, 'replied', 'n/a', false,
    '[]'::jsonb, 0, %s, 40, '[]'::jsonb)
"""

_QUOTE = """
INSERT INTO quote (quote_id, conversation_id, items, total, expiration, status)
VALUES (%s, %s, %s::jsonb, %s, now() + interval '1 day', 'ACCEPTED')
"""

_ORDER = """
INSERT INTO sales_order (order_id, quote_id, items, total, status)
VALUES (%s, %s, %s::jsonb, %s, %s)
"""

_OPPORTUNITY = """
INSERT INTO opportunity (
    opportunity_id, customer_id, opportunity_type, reason, evidence,
    recommended_action, status
) VALUES (%s, %s, 'QUOTE_RECOVERY', 'test', %s::jsonb, 'follow_up_quote', 'OPEN')
"""


def _items(product_id: str, quantity: int, unit_price: str) -> str:
    return (
        f'[{{"product_id": "{product_id}", "name": "x", '
        f'"quantity": {quantity}, "unit_price": "{unit_price}", "discount": "0"}}]'
    )


async def _paid_order(
    conn: object, *, unit_cost: str, quantity: int, unit_price: str
) -> tuple[str, str]:
    product_id = f"P-{uuid4().hex[:8]}"
    conv = f"c-{uuid4().hex}"
    quote_id = f"q-{uuid4().hex}"
    order_id = f"o-{uuid4().hex}"
    items = _items(product_id, quantity, unit_price)
    total = str(Decimal(unit_price) * quantity)

    await execute(conn, _PRODUCT, (product_id, "Test Product", unit_cost))
    audit_id = f"{conv}-0"
    await execute(conn, _AUDIT, (audit_id, f"tr-{audit_id}", conv, audit_id, "0.0010"))
    await execute(conn, _QUOTE, (quote_id, conv, items, total))
    await execute(conn, _ORDER, (order_id, quote_id, items, total, "PAID"))
    return conv, quote_id


async def test_margin_calculated_correctly(db: None) -> None:
    async with unit_of_work() as conn:
        conv, _ = await _paid_order(conn, unit_cost="60.00", quantity=2, unit_price="100.00")
        rows = await fetchall(
            conn,
            "SELECT revenue, margin_usd FROM v_conversation_revenue WHERE conversation_id = %s",
            (conv,),
        )

    assert rows[0]["revenue"] == Decimal("200.00")
    assert rows[0]["margin_usd"] == Decimal("80.00")


async def test_recovered_revenue_flagged_by_quote_id(db: None) -> None:
    async with unit_of_work() as conn:
        conv, quote_id = await _paid_order(conn, unit_cost="60.00", quantity=1, unit_price="100.00")
        await execute(
            conn,
            _OPPORTUNITY,
            (uuid4().hex, f"CUST-{uuid4().hex[:8]}", f'{{"quote_id": "{quote_id}"}}'),
        )
        rows = await fetchall(
            conn,
            "SELECT revenue, recovered_revenue_usd FROM v_conversation_revenue "
            "WHERE conversation_id = %s",
            (conv,),
        )

    assert rows[0]["recovered_revenue_usd"] == rows[0]["revenue"]


async def test_unrelated_recovery_opportunity_does_not_flag_revenue(db: None) -> None:
    async with unit_of_work() as conn:
        conv, _ = await _paid_order(conn, unit_cost="60.00", quantity=1, unit_price="100.00")
        await execute(
            conn,
            _OPPORTUNITY,
            (uuid4().hex, f"CUST-{uuid4().hex[:8]}", f'{{"quote_id": "{uuid4().hex}"}}'),
        )
        rows = await fetchall(
            conn,
            "SELECT recovered_revenue_usd FROM v_conversation_revenue WHERE conversation_id = %s",
            (conv,),
        )

    assert rows[0]["recovered_revenue_usd"] == 0


async def test_conversation_without_orders_has_zero_not_null(db: None) -> None:
    conv = f"c-{uuid4().hex}"
    async with unit_of_work() as conn:
        audit_id = f"{conv}-0"
        await execute(conn, _AUDIT, (audit_id, f"tr-{audit_id}", conv, audit_id, "0.0005"))
        rows = await fetchall(
            conn,
            "SELECT orders, revenue, margin_usd, recovered_revenue_usd "
            "FROM v_conversation_revenue WHERE conversation_id = %s",
            (conv,),
        )

    assert rows[0]["orders"] == 0
    assert rows[0]["revenue"] == 0
    assert rows[0]["margin_usd"] == 0
    assert rows[0]["recovered_revenue_usd"] == 0
