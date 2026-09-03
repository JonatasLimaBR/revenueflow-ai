CREATE OR REPLACE VIEW v_ai_cost_per_revenue AS
SELECT
    ae.conversation_id,
    sum(ae.cost_usd)              AS ai_cost_usd,
    coalesce(max(rev.revenue), 0) AS revenue,
    coalesce(max(rev.orders), 0)  AS orders,
    count(*)                      AS turns
FROM audit_event ae
LEFT JOIN (
    SELECT q.conversation_id,
           sum(so.total)              AS revenue,
           count(DISTINCT so.order_id) AS orders
    FROM quote q
    JOIN sales_order so
      ON so.quote_id = q.quote_id AND so.status = 'PAID'
    GROUP BY q.conversation_id
) rev ON rev.conversation_id = ae.conversation_id
GROUP BY ae.conversation_id;
