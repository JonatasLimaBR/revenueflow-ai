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

_CUSTOMER_360_ALL = """
SELECT customer_id, orders_12m, revenue_12m, last_purchase, purchase_interval_days,
       preferred_product, open_quotes
FROM v_customer_360_all
"""

_LEAD_FUNNEL = "SELECT lead_id, status, created_at FROM v_lead_funnel"

_OPPORTUNITY_SUMMARY = """
SELECT opportunity_id, customer_id, opportunity_type, status, estimated_revenue,
       probability, created_at
FROM v_opportunity_summary
"""

_HANDOFF_RATE = "SELECT total_turns, handoff_turns FROM v_handoff_rate"


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


async def customer_360_all(conn: AsyncConnection[Any]) -> list[dict[str, Any]]:
    rows = await fetchall(conn, _CUSTOMER_360_ALL)
    return [_row_to_json(row) for row in rows]


async def lead_funnel(conn: AsyncConnection[Any]) -> list[dict[str, Any]]:
    rows = await fetchall(conn, _LEAD_FUNNEL)
    return [_row_to_json(row) for row in rows]


async def opportunity_summary(conn: AsyncConnection[Any]) -> list[dict[str, Any]]:
    rows = await fetchall(conn, _OPPORTUNITY_SUMMARY)
    return [_row_to_json(row) for row in rows]


async def handoff_rate(conn: AsyncConnection[Any]) -> list[dict[str, Any]]:
    rows = await fetchall(conn, _HANDOFF_RATE)
    return [_row_to_json(row) for row in rows]
