CREATE INDEX IF NOT EXISTS opportunity_status_created_idx
    ON opportunity (status, created_at DESC);

CREATE INDEX IF NOT EXISTS handoff_status_created_idx
    ON handoff (status, created_at DESC);

CREATE INDEX IF NOT EXISTS approval_status_created_idx
    ON approval (status, created_at);

CREATE INDEX IF NOT EXISTS quote_customer_ref_open_idx
    ON quote (customer_ref) WHERE status = 'SENT';
