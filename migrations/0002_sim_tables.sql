CREATE TABLE IF NOT EXISTS sim_product (
    product_id text PRIMARY KEY,
    name text NOT NULL,
    category text NOT NULL,
    attrs jsonb NOT NULL DEFAULT '{}'::jsonb,
    price_tiers jsonb NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS sim_inventory (
    product_id text PRIMARY KEY REFERENCES sim_product (product_id),
    available integer NOT NULL DEFAULT 0,
    reserved integer NOT NULL DEFAULT 0,
    lead_time_days integer
);

CREATE TABLE IF NOT EXISTS sim_customer_sales (
    customer_id text NOT NULL,
    product_id text NOT NULL REFERENCES sim_product (product_id),
    last_qty integer NOT NULL,
    last_order_at timestamptz NOT NULL,
    PRIMARY KEY (customer_id, product_id)
);
