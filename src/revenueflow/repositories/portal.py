"""Portal-only read queries against the existing quote/sales_order/payment
tables — no new migration, no write path (ADR-073/ADR-037: the portal never
writes state directly)."""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

from revenueflow.repositories.db import fetchall

_RECENT_TRANSACTIONS = """
SELECT q.quote_id, q.conversation_id, q.status AS quote_status, q.total,
       o.order_id, o.status AS order_status, p.status AS payment_status, q.created_at
FROM quote q
LEFT JOIN sales_order o ON o.quote_id = q.quote_id
LEFT JOIN payment p ON p.order_id = o.order_id
ORDER BY q.created_at DESC
LIMIT %s
"""

_RECENT_CONVERSATIONS = """
SELECT conversation_id, phone, status, current_intent, current_agent,
       last_interaction, customer_id
FROM conversation_session
ORDER BY last_interaction DESC
LIMIT %s
"""


async def recent_transactions(
    conn: AsyncConnection[Any], *, limit: int = 50
) -> list[dict[str, Any]]:
    return await fetchall(conn, _RECENT_TRANSACTIONS, (limit,))


async def recent_conversations(
    conn: AsyncConnection[Any], *, limit: int = 50
) -> list[dict[str, Any]]:
    return await fetchall(conn, _RECENT_CONVERSATIONS, (limit,))
