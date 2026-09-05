from datetime import UTC, datetime
from uuid import uuid4

from revenueflow.domain.models import Customer
from revenueflow.repositories import analytics as analytics_repo
from revenueflow.repositories import customer as customer_repo
from revenueflow.repositories.db import execute, unit_of_work

_LEAD = "INSERT INTO lead (lead_id, phone, status) VALUES (%s, %s, %s)"

_OPPORTUNITY = """
INSERT INTO opportunity (
    opportunity_id, customer_id, opportunity_type, estimated_revenue, probability,
    reason, evidence, recommended_action, status
) VALUES (%s, %s, 'REPLENISHMENT', %s, %s, 'test', '{}'::jsonb, 'follow_up', 'OPEN')
"""

_AUDIT = """
INSERT INTO audit_event (
    audit_id, trace_id, conversation_id, turn_id, agent, model, prompt_version,
    outcome, policy_decision, handoff, tools, token_usage, cost_usd, latency_ms, events
) VALUES (%s, %s, %s, %s, NULL, NULL, NULL, 'replied', 'n/a', %s,
    '[]'::jsonb, 0, 0, 40, '[]'::jsonb)
"""


async def test_customer_360_all_includes_customer_without_orders(db: None) -> None:
    customer_id = f"cust-{uuid4().hex}"
    async with unit_of_work() as conn:
        await customer_repo.create(
            conn,
            Customer(
                customer_id=customer_id,
                phone=f"+1555{uuid4().hex[:7]}",
                name=None,
                segment=None,
                created_at=datetime.now(UTC),
            ),
        )
        rows = await analytics_repo.customer_360_all(conn)

    row = next(r for r in rows if r["customer_id"] == customer_id)
    assert row["orders_12m"] == 0
    assert row["revenue_12m"] == 0
    assert row["last_purchase"] is None
    assert row["preferred_product"] is None
    assert row["open_quotes"] == 0


async def test_lead_funnel_excludes_phone(db: None) -> None:
    lead_id = f"lead-{uuid4().hex}"
    async with unit_of_work() as conn:
        await execute(conn, _LEAD, (lead_id, f"+1555{uuid4().hex[:7]}", "NEW"))
        rows = await analytics_repo.lead_funnel(conn)

    row = next(r for r in rows if r["lead_id"] == lead_id)
    assert row["status"] == "NEW"
    assert "phone" not in row


async def test_opportunity_summary_excludes_reason_and_evidence(db: None) -> None:
    opportunity_id = f"opp-{uuid4().hex}"
    async with unit_of_work() as conn:
        await execute(
            conn, _OPPORTUNITY, (opportunity_id, f"cust-{uuid4().hex[:8]}", "50.00", "0.4")
        )
        rows = await analytics_repo.opportunity_summary(conn)

    row = next(r for r in rows if r["opportunity_id"] == opportunity_id)
    assert row["status"] == "OPEN"
    assert row["estimated_revenue"] == 50.0
    assert "reason" not in row
    assert "evidence" not in row


async def test_handoff_rate_counts_handoff_turns(db: None) -> None:
    async with unit_of_work() as conn:
        before = (await analytics_repo.handoff_rate(conn))[0]

        conv = f"c-{uuid4().hex}"
        handoff_id = f"{conv}-h"
        replied_id = f"{conv}-r"
        await execute(conn, _AUDIT, (handoff_id, f"tr-{handoff_id}", conv, handoff_id, True))
        await execute(conn, _AUDIT, (replied_id, f"tr-{replied_id}", conv, replied_id, False))

        after = (await analytics_repo.handoff_rate(conn))[0]

    assert after["total_turns"] == before["total_turns"] + 2
    assert after["handoff_turns"] == before["handoff_turns"] + 1
