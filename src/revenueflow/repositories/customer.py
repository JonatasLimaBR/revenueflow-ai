"""Customer identity and the bounded Customer 360 view.

``get_by_phone`` / ``create`` mirror :mod:`revenueflow.repositories.lead`: exactly
one customer per phone, exact-match lookup, idempotent insert.

``customer_360`` is a deterministic, read-only aggregate (SPEC-017, ADR-009): a
single windowed CTE over the seeded order history (``sim_customer_order``) unioned
with real orders (``sales_order`` by ``customer_ref``), plus product affinity from
``sim_customer_sales`` and open quotes from ``quote``. No LLM, no business rule
beyond the 365-day window and the average-ticket guard.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from psycopg import AsyncConnection

from revenueflow.domain.models import Customer
from revenueflow.repositories.db import execute, fetchall, fetchone

_SELECT_BY_PHONE = (
    "SELECT customer_id, phone, name, segment, created_at, "
    "consent_opt_in_at, consent_opt_out_at FROM customer WHERE phone = %s"
)

_SELECT_BY_ID = (
    "SELECT customer_id, phone, name, segment, created_at, "
    "consent_opt_in_at, consent_opt_out_at FROM customer WHERE customer_id = %s"
)

_INSERT = """
INSERT INTO customer (customer_id, phone, name, segment)
VALUES (%s, %s, %s, %s)
ON CONFLICT (phone) DO NOTHING
"""

_SET_OPT_IN = "UPDATE customer SET consent_opt_in_at = %s WHERE customer_id = %s"
_SET_OPT_OUT = "UPDATE customer SET consent_opt_out_at = %s WHERE customer_id = %s"

_AGG = """
WITH orders AS (
    SELECT total, ordered_at AS at
    FROM sim_customer_order
    WHERE customer_id = %s AND ordered_at >= now() - interval '365 days'
    UNION ALL
    SELECT total, created_at AS at
    FROM sales_order
    WHERE customer_ref = %s AND created_at >= now() - interval '365 days'
)
SELECT
    count(*) AS orders_12m,
    coalesce(sum(total), 0) AS revenue_12m,
    max(at) AS last_purchase,
    (
        SELECT avg(delta)
        FROM (
            SELECT extract(epoch FROM (at - lag(at) OVER (ORDER BY at))) / 86400.0 AS delta
            FROM orders
        ) s
        WHERE delta IS NOT NULL
    ) AS purchase_interval_days
FROM orders
"""

_PREFERRED = """
SELECT product_id
FROM sim_customer_sales
WHERE customer_id = %s
GROUP BY product_id
ORDER BY sum(last_qty) DESC
LIMIT 3
"""

_OPEN_QUOTES = "SELECT quote_id FROM quote WHERE customer_ref = %s AND status = 'SENT'"


def _to_customer(row: dict[str, Any]) -> Customer:
    return Customer(
        customer_id=row["customer_id"],
        phone=row["phone"],
        name=row["name"],
        segment=row["segment"],
        created_at=row["created_at"],
        consent_opt_in_at=row["consent_opt_in_at"],
        consent_opt_out_at=row["consent_opt_out_at"],
    )


async def get_by_phone(conn: AsyncConnection[Any], phone: str) -> Customer | None:
    row = await fetchone(conn, _SELECT_BY_PHONE, (phone,))
    return _to_customer(row) if row is not None else None


async def get_by_id(conn: AsyncConnection[Any], customer_id: str) -> Customer | None:
    row = await fetchone(conn, _SELECT_BY_ID, (customer_id,))
    return _to_customer(row) if row is not None else None


async def create(conn: AsyncConnection[Any], customer: Customer) -> None:
    await execute(
        conn,
        _INSERT,
        (customer.customer_id, customer.phone, customer.name, customer.segment),
    )


async def set_consent_opt_in(conn: AsyncConnection[Any], customer_id: str, at: datetime) -> None:
    await execute(conn, _SET_OPT_IN, (at, customer_id))


async def set_consent_opt_out(conn: AsyncConnection[Any], customer_id: str, at: datetime) -> None:
    await execute(conn, _SET_OPT_OUT, (at, customer_id))


async def customer_360(conn: AsyncConnection[Any], customer_id: str) -> dict[str, Any]:
    agg = await fetchone(conn, _AGG, (customer_id, customer_id))
    preferred_rows = await fetchall(conn, _PREFERRED, (customer_id,))
    quote_rows = await fetchall(conn, _OPEN_QUOTES, (customer_id,))

    row = agg or {}
    orders_12m = int(row.get("orders_12m") or 0)
    revenue_12m = Decimal(str(row.get("revenue_12m") or 0))
    average_ticket = revenue_12m / orders_12m if orders_12m else Decimal("0")
    interval = row.get("purchase_interval_days")
    quote_ids = [str(r["quote_id"]) for r in quote_rows]

    return {
        "orders_12m": orders_12m,
        "revenue_12m": revenue_12m,
        "average_ticket": average_ticket,
        "last_purchase": row.get("last_purchase"),
        "purchase_interval_days": float(interval) if interval is not None else None,
        "preferred_products": [str(r["product_id"]) for r in preferred_rows],
        "open_quotes": {"count": len(quote_ids), "quote_ids": quote_ids},
    }
