"""Opportunity persistence and batch-scan candidate queries (SPEC-018/021).

``upsert_open`` enforces "one OPEN opportunity per signal" via the partial unique
index from ``0007`` (``INSERT ... ON CONFLICT DO NOTHING`` + read-back).
``replenishment_candidates`` / ``stale_quote_candidates`` are all-customer scans
that feed the pure rules in :mod:`revenueflow.policies.opportunity_policy`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from revenueflow.domain.models import Opportunity, OpportunityStatus, OpportunityType
from revenueflow.policies.opportunity_policy import QuoteRecoverySignal, ReplenishmentSignal
from revenueflow.repositories.db import execute, fetchall, fetchone

_INSERT = """
INSERT INTO opportunity (
    opportunity_id, customer_id, opportunity_type, product, estimated_revenue,
    probability, reason, evidence, recommended_action, status, created_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (customer_id, opportunity_type, product) WHERE status = 'OPEN' DO NOTHING
"""

_SELECT_OPEN = """
SELECT opportunity_id, customer_id, opportunity_type, product, estimated_revenue,
       probability, reason, evidence, recommended_action, status, created_at
FROM opportunity
WHERE customer_id = %s AND opportunity_type = %s
  AND product IS NOT DISTINCT FROM %s AND status = 'OPEN'
"""

_SELECT_BY_STATUS = """
SELECT opportunity_id, customer_id, opportunity_type, product, estimated_revenue,
       probability, reason, evidence, recommended_action, status, created_at
FROM opportunity
WHERE status = %s
ORDER BY created_at DESC
"""

_SET_STATUS = "UPDATE opportunity SET status = %s WHERE opportunity_id = %s"

_CANDIDATES_REPLENISHMENT = """
WITH orders AS (
    SELECT customer_id, ordered_at AS at, total
    FROM sim_customer_order
    WHERE ordered_at >= now() - interval '365 days'
    UNION ALL
    SELECT customer_ref AS customer_id, created_at AS at, total
    FROM sales_order
    WHERE customer_ref IS NOT NULL AND created_at >= now() - interval '365 days'
),
gapped AS (
    SELECT
        customer_id,
        at,
        total,
        extract(
            epoch FROM (at - lag(at) OVER (PARTITION BY customer_id ORDER BY at))
        ) / 86400.0 AS gap
    FROM orders
),
per_customer AS (
    SELECT
        customer_id,
        count(*) AS n,
        max(at) AS last_at,
        sum(total) / count(*) AS avg_ticket,
        avg(gap) AS avg_gap
    FROM gapped
    GROUP BY customer_id
    HAVING count(*) >= 2
)
SELECT
    pc.customer_id,
    extract(epoch FROM (now() - pc.last_at)) / 86400.0 AS days_since_last,
    pc.avg_gap,
    pc.avg_ticket,
    (
        SELECT s.product_id
        FROM sim_customer_sales s
        WHERE s.customer_id = pc.customer_id
        GROUP BY s.product_id
        ORDER BY sum(s.last_qty) DESC
        LIMIT 1
    ) AS product_id
FROM per_customer pc
WHERE pc.avg_gap IS NOT NULL
"""

_CANDIDATES_STALE_QUOTE = """
SELECT
    q.quote_id,
    q.customer_ref,
    q.created_at,
    q.total,
    q.items #>> '{0,product_id}' AS product_id
FROM quote q
LEFT JOIN sales_order so ON so.quote_id = q.quote_id
WHERE q.status = 'SENT' AND so.order_id IS NULL
"""


def _to_opportunity(row: dict[str, Any]) -> Opportunity:
    return Opportunity(
        opportunity_id=row["opportunity_id"],
        customer_id=row["customer_id"],
        opportunity_type=OpportunityType(row["opportunity_type"]),
        product=row["product"],
        estimated_revenue=row["estimated_revenue"],
        probability=row["probability"],
        reason=row["reason"],
        evidence=row["evidence"],
        recommended_action=row["recommended_action"],
        status=OpportunityStatus(row["status"]),
        created_at=row["created_at"],
    )


async def upsert_open(conn: AsyncConnection[Any], opp: Opportunity) -> Opportunity:
    await execute(
        conn,
        _INSERT,
        (
            opp.opportunity_id,
            opp.customer_id,
            opp.opportunity_type.value,
            opp.product,
            opp.estimated_revenue,
            opp.probability,
            opp.reason,
            Jsonb(opp.evidence),
            opp.recommended_action,
            opp.status.value,
            opp.created_at,
        ),
    )
    row = await fetchone(
        conn, _SELECT_OPEN, (opp.customer_id, opp.opportunity_type.value, opp.product)
    )
    return _to_opportunity(row) if row is not None else opp


async def list_by_status(
    conn: AsyncConnection[Any], status: OpportunityStatus
) -> list[Opportunity]:
    rows = await fetchall(conn, _SELECT_BY_STATUS, (status.value,))
    return [_to_opportunity(row) for row in rows]


async def set_status(
    conn: AsyncConnection[Any], opportunity_id: str, status: OpportunityStatus
) -> None:
    await execute(conn, _SET_STATUS, (status.value, opportunity_id))


async def replenishment_candidates(
    conn: AsyncConnection[Any],
) -> list[ReplenishmentSignal]:
    rows = await fetchall(conn, _CANDIDATES_REPLENISHMENT)
    return [
        ReplenishmentSignal(
            customer_id=str(row["customer_id"]),
            product_id=row["product_id"],
            days_since_last_purchase=float(row["days_since_last"]),
            average_purchase_interval=float(row["avg_gap"]),
            average_ticket=Decimal(str(row["avg_ticket"])),
        )
        for row in rows
    ]


async def stale_quote_candidates(
    conn: AsyncConnection[Any],
) -> list[QuoteRecoverySignal]:
    rows = await fetchall(conn, _CANDIDATES_STALE_QUOTE)
    return [
        QuoteRecoverySignal(
            quote_id=str(row["quote_id"]),
            customer_id=str(row["customer_ref"] or ""),
            product_id=row["product_id"],
            status="SENT",
            created_at=row["created_at"],
            total=Decimal(str(row["total"])),
            has_order=False,
        )
        for row in rows
    ]
