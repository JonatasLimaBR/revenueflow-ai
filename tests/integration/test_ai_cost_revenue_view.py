from uuid import uuid4

from revenueflow.repositories.db import execute, fetchall, unit_of_work

_AUDIT = """
INSERT INTO audit_event (
    audit_id, trace_id, conversation_id, turn_id, agent, model, prompt_version,
    outcome, policy_decision, handoff, tools, token_usage, cost_usd, latency_ms, events
) VALUES (%s, %s, %s, %s, NULL, NULL, NULL, 'replied', 'n/a', false,
    '[]'::jsonb, 0, %s, 40, '[]'::jsonb)
"""

_QUOTE = """
INSERT INTO quote (quote_id, conversation_id, items, total, expiration, status)
VALUES (%s, %s, '[]'::jsonb, %s, now() + interval '1 day', 'ACCEPTED')
"""

_ORDER = """
INSERT INTO sales_order (order_id, quote_id, items, total, status)
VALUES (%s, %s, '[]'::jsonb, %s, %s)
"""


async def test_view_pairs_ai_cost_with_paid_revenue(db: None) -> None:
    conv_a = f"c-{uuid4().hex}"
    conv_b = f"c-{uuid4().hex}"
    quote_id = f"q-{uuid4().hex}"

    async with unit_of_work() as conn:
        for i in range(3):
            aid = f"{conv_a}-{i}"
            await execute(conn, _AUDIT, (aid, f"tr-{aid}", conv_a, aid, "0.0020"))
        for i in range(2):
            aid = f"{conv_b}-{i}"
            await execute(conn, _AUDIT, (aid, f"tr-{aid}", conv_b, aid, "0.0010"))

        await execute(conn, _QUOTE, (quote_id, conv_a, "1500"))
        await execute(conn, _ORDER, (f"o-{uuid4().hex}", quote_id, "1500", "PAID"))

        rows = await fetchall(
            conn,
            "SELECT conversation_id, ai_cost_usd, revenue, orders, turns "
            "FROM v_ai_cost_per_revenue WHERE conversation_id IN (%s, %s) "
            "ORDER BY conversation_id",
            (conv_a, conv_b),
        )

    by_id = {r["conversation_id"]: r for r in rows}
    assert by_id[conv_a]["ai_cost_usd"] == 0.006
    assert by_id[conv_a]["revenue"] == 1500
    assert by_id[conv_a]["orders"] == 1
    assert by_id[conv_a]["turns"] == 3

    assert by_id[conv_b]["ai_cost_usd"] == 0.002
    assert by_id[conv_b]["revenue"] == 0
    assert by_id[conv_b]["orders"] == 0
    assert by_id[conv_b]["turns"] == 2


async def test_view_ignores_unpaid_orders(db: None) -> None:
    conv = f"c-{uuid4().hex}"
    quote_id = f"q-{uuid4().hex}"

    async with unit_of_work() as conn:
        aid = f"{conv}-0"
        await execute(conn, _AUDIT, (aid, f"tr-{aid}", conv, aid, "0.0010"))
        await execute(conn, _QUOTE, (quote_id, conv, "900"))
        await execute(conn, _ORDER, (f"o-{uuid4().hex}", quote_id, "900", "PENDING"))

        rows = await fetchall(
            conn,
            "SELECT revenue, orders FROM v_ai_cost_per_revenue WHERE conversation_id = %s",
            (conv,),
        )

    assert rows[0]["revenue"] == 0
    assert rows[0]["orders"] == 0
