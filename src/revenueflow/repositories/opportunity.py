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
from revenueflow.policies.opportunity_policy import (
    CrossSellSignal,
    InventoryToCashSignal,
    OrderRecoverySignal,
    QuoteRecoverySignal,
    ReplenishmentSignal,
    UpsellSignal,
)
from revenueflow.repositories.db import execute, fetchall, fetchone

_ACCESSORY_CATEGORY = "acessório"

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

_CANDIDATES_ORDER_RECOVERY = """
SELECT
    so.order_id,
    so.customer_ref,
    so.created_at,
    so.total,
    so.items #>> '{0,product_id}' AS product_id
FROM sales_order so
WHERE so.status = 'FAILED'
  AND NOT EXISTS (
      SELECT 1 FROM sales_order retried
      WHERE retried.customer_ref = so.customer_ref
        AND retried.status IN ('CONFIRMED', 'PAID')
        AND retried.created_at > so.created_at
  )
"""

_CANDIDATES_CROSS_SELL = """
WITH accessory AS (
    SELECT product_id, (price_tiers -> 0 ->> 'unit_price')::numeric AS unit_price
    FROM sim_product
    WHERE category = %s
    ORDER BY (price_tiers -> 0 ->> 'unit_price')::numeric ASC
    LIMIT 1
),
purchases AS (
    SELECT s.customer_id, p.category, s.last_order_at AS at
    FROM sim_customer_sales s
    JOIN sim_product p ON p.product_id = s.product_id
    UNION ALL
    SELECT so.customer_ref AS customer_id, p.category, so.created_at AS at
    FROM sales_order so
    CROSS JOIN LATERAL jsonb_array_elements(so.items) AS item
    JOIN sim_product p ON p.product_id = item ->> 'product_id'
    WHERE so.customer_ref IS NOT NULL
),
per_customer AS (
    SELECT
        customer_id,
        bool_or(category = %s) AS has_accessory,
        (array_agg(category ORDER BY at DESC))[1] AS latest_category
    FROM purchases
    GROUP BY customer_id
)
SELECT
    pc.customer_id,
    pc.latest_category AS purchased_category,
    a.product_id AS complement_product_id,
    a.unit_price AS complement_price
FROM per_customer pc
CROSS JOIN accessory a
WHERE NOT pc.has_accessory
"""

_CANDIDATES_UPSELL = """
WITH product_orders AS (
    SELECT o.customer_id, item ->> 'product_id' AS product_id
    FROM sim_customer_order o
    CROSS JOIN LATERAL jsonb_array_elements(o.items) AS item
    UNION ALL
    SELECT so.customer_ref AS customer_id, item ->> 'product_id' AS product_id
    FROM sales_order so
    CROSS JOIN LATERAL jsonb_array_elements(so.items) AS item
    WHERE so.customer_ref IS NOT NULL
),
counts AS (
    SELECT customer_id, product_id, count(*) AS repeat_count
    FROM product_orders
    WHERE product_id IS NOT NULL
    GROUP BY customer_id, product_id
),
already_bought AS (
    SELECT customer_id, array_agg(DISTINCT product_id) AS products
    FROM product_orders
    WHERE product_id IS NOT NULL
    GROUP BY customer_id
),
upgrade AS (
    SELECT
        p.product_id AS current_product_id,
        up.product_id AS upgrade_product_id,
        up.unit_price AS upgrade_price
    FROM sim_product p
    JOIN LATERAL (
        SELECT p2.product_id, (p2.price_tiers -> 0 ->> 'unit_price')::numeric AS unit_price
        FROM sim_product p2
        WHERE p2.category = p.category
          AND (p2.price_tiers -> 0 ->> 'unit_price')::numeric
              > (p.price_tiers -> 0 ->> 'unit_price')::numeric
        ORDER BY (p2.price_tiers -> 0 ->> 'unit_price')::numeric ASC
        LIMIT 1
    ) up ON true
)
SELECT
    c.customer_id,
    c.product_id AS current_product_id,
    c.repeat_count,
    u.upgrade_product_id,
    u.upgrade_price
FROM counts c
JOIN upgrade u ON u.current_product_id = c.product_id
JOIN already_bought ab ON ab.customer_id = c.customer_id
WHERE NOT (u.upgrade_product_id = ANY (ab.products))
"""

_CANDIDATES_INVENTORY_TO_CASH = """
WITH last_sale AS (
    SELECT product_id, max(at) AS last_sale_at
    FROM (
        SELECT product_id, last_order_at AS at FROM sim_customer_sales
        UNION ALL
        SELECT item ->> 'product_id' AS product_id, so.created_at AS at
        FROM sales_order so
        CROSS JOIN LATERAL jsonb_array_elements(so.items) AS item
    ) activity
    GROUP BY product_id
),
stale_products AS (
    SELECT
        i.product_id,
        i.available,
        p.category,
        (p.price_tiers -> 0 ->> 'unit_price')::numeric AS unit_price,
        extract(epoch FROM (now() - coalesce(ls.last_sale_at, TIMESTAMPTZ '1970-01-01')))
            / 86400.0 AS stale_days
    FROM sim_inventory i
    JOIN sim_product p ON p.product_id = i.product_id
    LEFT JOIN last_sale ls ON ls.product_id = i.product_id
),
category_customers AS (
    SELECT DISTINCT s.customer_id, p.category
    FROM sim_customer_sales s
    JOIN sim_product p ON p.product_id = s.product_id
    UNION
    SELECT DISTINCT so.customer_ref AS customer_id, p.category
    FROM sales_order so
    CROSS JOIN LATERAL jsonb_array_elements(so.items) AS item
    JOIN sim_product p ON p.product_id = item ->> 'product_id'
    WHERE so.customer_ref IS NOT NULL
)
SELECT
    cc.customer_id,
    sp.product_id,
    sp.available,
    sp.stale_days::int AS stale_days,
    sp.unit_price
FROM stale_products sp
JOIN category_customers cc ON cc.category = sp.category
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


async def order_recovery_candidates(
    conn: AsyncConnection[Any],
) -> list[OrderRecoverySignal]:
    rows = await fetchall(conn, _CANDIDATES_ORDER_RECOVERY)
    return [
        OrderRecoverySignal(
            order_id=str(row["order_id"]),
            customer_id=str(row["customer_ref"] or ""),
            product_id=row["product_id"],
            total=Decimal(str(row["total"])),
            failed_at=row["created_at"],
        )
        for row in rows
    ]


async def cross_sell_candidates(conn: AsyncConnection[Any]) -> list[CrossSellSignal]:
    rows = await fetchall(conn, _CANDIDATES_CROSS_SELL, (_ACCESSORY_CATEGORY, _ACCESSORY_CATEGORY))
    return [
        CrossSellSignal(
            customer_id=str(row["customer_id"]),
            complement_product_id=str(row["complement_product_id"]),
            complement_price=Decimal(str(row["complement_price"])),
            purchased_category=str(row["purchased_category"]),
        )
        for row in rows
    ]


async def upsell_candidates(conn: AsyncConnection[Any]) -> list[UpsellSignal]:
    rows = await fetchall(conn, _CANDIDATES_UPSELL)
    return [
        UpsellSignal(
            customer_id=str(row["customer_id"]),
            current_product_id=str(row["current_product_id"]),
            repeat_count=int(row["repeat_count"]),
            upgrade_product_id=str(row["upgrade_product_id"]),
            upgrade_price=Decimal(str(row["upgrade_price"])),
        )
        for row in rows
    ]


async def inventory_to_cash_candidates(
    conn: AsyncConnection[Any],
) -> list[InventoryToCashSignal]:
    rows = await fetchall(conn, _CANDIDATES_INVENTORY_TO_CASH)
    return [
        InventoryToCashSignal(
            customer_id=str(row["customer_id"]),
            product_id=str(row["product_id"]),
            available=int(row["available"]),
            stale_days=int(row["stale_days"]),
            unit_price=Decimal(str(row["unit_price"])),
        )
        for row in rows
    ]


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
