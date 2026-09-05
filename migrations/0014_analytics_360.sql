CREATE OR REPLACE VIEW v_customer_360_all AS
WITH orders AS (
    SELECT customer_id, total, ordered_at AS at
    FROM sim_customer_order
    WHERE ordered_at >= now() - interval '365 days'
    UNION ALL
    SELECT customer_ref AS customer_id, total, created_at AS at
    FROM sales_order
    WHERE customer_ref IS NOT NULL AND created_at >= now() - interval '365 days'
),
gapped AS (
    SELECT customer_id, at, total,
           extract(epoch FROM (at - lag(at) OVER (PARTITION BY customer_id ORDER BY at))) / 86400.0 AS gap
    FROM orders
),
agg AS (
    SELECT customer_id,
           count(*)  AS orders_12m,
           sum(total) AS revenue_12m,
           max(at)    AS last_purchase,
           avg(gap)   AS purchase_interval_days
    FROM gapped
    GROUP BY customer_id
),
preferred_agg AS (
    SELECT customer_id, product_id, sum(last_qty) AS qty
    FROM sim_customer_sales
    GROUP BY customer_id, product_id
),
preferred AS (
    SELECT customer_id, product_id,
           row_number() OVER (PARTITION BY customer_id ORDER BY qty DESC) AS rn
    FROM preferred_agg
),
open_quotes AS (
    SELECT customer_ref AS customer_id, count(*) AS open_quotes
    FROM quote
    WHERE status = 'SENT' AND customer_ref IS NOT NULL
    GROUP BY customer_ref
)
SELECT
    c.customer_id,
    coalesce(a.orders_12m, 0)  AS orders_12m,
    coalesce(a.revenue_12m, 0) AS revenue_12m,
    a.last_purchase,
    a.purchase_interval_days,
    p.product_id                AS preferred_product,
    coalesce(oq.open_quotes, 0) AS open_quotes
FROM customer c
LEFT JOIN agg a ON a.customer_id = c.customer_id
LEFT JOIN preferred p ON p.customer_id = c.customer_id AND p.rn = 1
LEFT JOIN open_quotes oq ON oq.customer_id = c.customer_id;

CREATE OR REPLACE VIEW v_lead_funnel AS
SELECT lead_id, status, created_at FROM lead;

CREATE OR REPLACE VIEW v_opportunity_summary AS
SELECT opportunity_id, customer_id, opportunity_type, status, estimated_revenue, probability, created_at
FROM opportunity;

CREATE OR REPLACE VIEW v_handoff_rate AS
SELECT
    count(*)                        AS total_turns,
    count(*) FILTER (WHERE handoff) AS handoff_turns
FROM audit_event;
