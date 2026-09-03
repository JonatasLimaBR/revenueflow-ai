CREATE TABLE IF NOT EXISTS opportunity (
    opportunity_id     text PRIMARY KEY,
    customer_id        text NOT NULL,
    opportunity_type   text NOT NULL,
    product            text,
    estimated_revenue  numeric,
    probability        numeric,
    reason             text NOT NULL,
    evidence           jsonb NOT NULL,
    recommended_action text NOT NULL,
    status             text NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS opportunity_one_open_per_signal
    ON opportunity (customer_id, opportunity_type, product)
    WHERE status = 'OPEN';
