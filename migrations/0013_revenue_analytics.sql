CREATE OR REPLACE VIEW v_conversation_revenue AS
WITH order_items AS (
    SELECT so.order_id, so.quote_id,
           item->>'product_id' AS product_id,
           (item->>'quantity')::numeric AS quantity,
           (item->>'unit_price')::numeric AS unit_price
    FROM sales_order so, jsonb_array_elements(so.items) AS item
    WHERE so.status = 'PAID'
),
order_totals AS (
    SELECT oi.order_id, oi.quote_id,
           sum(oi.unit_price * oi.quantity) AS order_revenue,
           sum((oi.unit_price - coalesce(sp.unit_cost, 0)) * oi.quantity) AS order_margin
    FROM order_items oi
    LEFT JOIN sim_product sp ON sp.product_id = oi.product_id
    GROUP BY oi.order_id, oi.quote_id
),
recovered_quotes AS (
    SELECT DISTINCT evidence ->> 'quote_id' AS quote_id
    FROM opportunity
    WHERE opportunity_type = 'QUOTE_RECOVERY'
),
conversation_orders AS (
    SELECT
        q.conversation_id,
        count(DISTINCT ot.order_id)                                  AS orders,
        sum(ot.order_revenue)                                        AS revenue,
        sum(ot.order_margin)                                         AS margin_usd,
        sum(ot.order_revenue) FILTER (WHERE rq.quote_id IS NOT NULL) AS recovered_revenue_usd
    FROM order_totals ot
    JOIN quote q ON q.quote_id = ot.quote_id
    LEFT JOIN recovered_quotes rq ON rq.quote_id = ot.quote_id
    GROUP BY q.conversation_id
),
conversation_cost AS (
    SELECT conversation_id,
           sum(cost_usd)   AS ai_cost_usd,
           count(*)        AS turns,
           max(created_at) AS last_at
    FROM audit_event
    GROUP BY conversation_id
)
SELECT
    cc.conversation_id,
    cc.ai_cost_usd,
    cc.turns,
    cc.last_at,
    coalesce(co.orders, 0)                AS orders,
    coalesce(co.revenue, 0)               AS revenue,
    coalesce(co.margin_usd, 0)            AS margin_usd,
    coalesce(co.recovered_revenue_usd, 0) AS recovered_revenue_usd
FROM conversation_cost cc
LEFT JOIN conversation_orders co ON co.conversation_id = cc.conversation_id;
