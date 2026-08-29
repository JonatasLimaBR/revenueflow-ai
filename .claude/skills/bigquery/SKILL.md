# BigQuery Skill

## Use when
Working on Customer 360, Revenue 360, Opportunity 360, analytics or cost/performance.

## Rules
- Prefer partitioning/clustering where justified.
- Never use `SELECT *` in production analytical paths without explicit reason.
- Estimate query impact/cost before large scans.
- Separate raw/staging/curated layers.
- Never treat BigQuery as OLTP for quote/order/payment workflows.
- PII access must be minimized.

## RevenueFlow domains
- customer_360
- lead_360
- revenue_360
- opportunity_360
- conversation_analytics
