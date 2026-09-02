CREATE TABLE IF NOT EXISTS customer (
    customer_id text PRIMARY KEY,
    phone       text UNIQUE NOT NULL,
    name        text,
    segment     text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sim_customer_order (
    customer_id text NOT NULL,
    order_id    text NOT NULL,
    total       numeric NOT NULL,
    ordered_at  timestamptz NOT NULL,
    items       jsonb NOT NULL DEFAULT '[]'::jsonb,
    PRIMARY KEY (customer_id, order_id)
);
