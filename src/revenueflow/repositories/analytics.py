from datetime import datetime
from decimal import Decimal
from typing import Any

from psycopg import AsyncConnection

from revenueflow.repositories.db import fetchall

_CONVERSATION_REVENUE = """
SELECT conversation_id, ai_cost_usd, turns, last_at, orders, revenue,
       margin_usd, recovered_revenue_usd
FROM v_conversation_revenue
"""

_COST_PER_OUTCOME = """
SELECT outcome, turns, cost_usd, avg_latency_ms
FROM v_ai_cost_per_outcome
"""


def _row_to_json(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            out[key] = value.isoformat()
        elif isinstance(value, Decimal):
            out[key] = float(value)
        else:
            out[key] = value
    return out


async def conversation_revenue(conn: AsyncConnection[Any]) -> list[dict[str, Any]]:
    rows = await fetchall(conn, _CONVERSATION_REVENUE)
    return [_row_to_json(row) for row in rows]


async def cost_per_outcome(conn: AsyncConnection[Any]) -> list[dict[str, Any]]:
    rows = await fetchall(conn, _COST_PER_OUTCOME)
    return [_row_to_json(row) for row in rows]
