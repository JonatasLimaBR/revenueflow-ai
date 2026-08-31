ALTER TABLE sim_product ADD COLUMN IF NOT EXISTS unit_cost numeric NOT NULL DEFAULT 0;
ALTER TABLE sim_product ADD COLUMN IF NOT EXISTS min_margin_pct numeric NOT NULL DEFAULT 0.15;

CREATE TABLE IF NOT EXISTS sim_customer_pricing (
    customer_id      text NOT NULL,
    product_id       text NOT NULL REFERENCES sim_product(product_id),
    negotiated_price numeric NOT NULL,
    max_discount_pct numeric NOT NULL,
    PRIMARY KEY (customer_id, product_id)
);

CREATE TABLE IF NOT EXISTS approval (
    approval_id        text PRIMARY KEY,
    conversation_id    text NOT NULL,
    turn_id            text NOT NULL,
    reason             text NOT NULL,
    requested_discount numeric NOT NULL,
    current_margin     numeric NOT NULL,
    resulting_margin   numeric NOT NULL,
    amount             numeric NOT NULL,
    customer_ref       text,
    status             text NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (conversation_id, turn_id)
);
