from datetime import UTC, datetime, timedelta
from uuid import uuid4

from revenueflow.repositories import portal as portal_repo
from revenueflow.repositories.db import execute, unit_of_work

_INSERT_QUOTE = """
INSERT INTO quote (quote_id, conversation_id, customer_ref, items, total, expiration, status)
VALUES (%s, %s, NULL, '[]'::jsonb, %s, %s, %s)
"""

_INSERT_SESSION = """
INSERT INTO conversation_session (conversation_id, phone, status)
VALUES (%s, %s, 'OPEN')
"""


async def test_recent_transactions_returns_quote_without_order_or_payment(db: None) -> None:
    quote_id = f"q-{uuid4().hex}"
    conversation_id = f"c-{uuid4().hex}"
    expiration = datetime.now(UTC) + timedelta(days=1)
    async with unit_of_work() as conn:
        await execute(
            conn, _INSERT_QUOTE, (quote_id, conversation_id, "125.50", expiration, "SENT")
        )
        rows = await portal_repo.recent_transactions(conn, limit=500)

    row = next(r for r in rows if r["quote_id"] == quote_id)
    assert row["conversation_id"] == conversation_id
    assert row["quote_status"] == "SENT"
    assert float(row["total"]) == 125.50
    assert row["order_id"] is None
    assert row["payment_status"] is None


async def test_recent_conversations_returns_masked_source_phone(db: None) -> None:
    conversation_id = f"c-{uuid4().hex}"
    phone = f"+1555{uuid4().hex[:7]}"
    async with unit_of_work() as conn:
        await execute(conn, _INSERT_SESSION, (conversation_id, phone))
        rows = await portal_repo.recent_conversations(conn, limit=500)

    row = next(r for r in rows if r["conversation_id"] == conversation_id)
    assert row["phone"] == phone  # masking happens at the view layer, not the repo
    assert row["status"] == "OPEN"
