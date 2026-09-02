CREATE TABLE IF NOT EXISTS quote (
    quote_id        text PRIMARY KEY,
    conversation_id text NOT NULL,
    customer_ref    text,
    items           jsonb NOT NULL,
    total           numeric NOT NULL,
    expiration      timestamptz NOT NULL,
    status          text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS quote_one_open_per_conversation
    ON quote (conversation_id) WHERE status = 'SENT';

CREATE TABLE IF NOT EXISTS sales_order (
    order_id     text PRIMARY KEY,
    quote_id     text NOT NULL UNIQUE,
    customer_ref text,
    items        jsonb NOT NULL,
    total        numeric NOT NULL,
    status       text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS payment (
    payment_id text PRIMARY KEY,
    order_id   text NOT NULL,
    amount     numeric NOT NULL,
    status     text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
