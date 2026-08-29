CREATE TABLE IF NOT EXISTS processed_event (
    kind text,
    key text,
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (kind, key)
);

CREATE TABLE IF NOT EXISTS dispatch (
    dispatch_key text PRIMARY KEY,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lead (
    lead_id text PRIMARY KEY,
    phone text NOT NULL,
    status text NOT NULL,
    created_at timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS lead_phone_key ON lead (phone);

CREATE TABLE IF NOT EXISTS conversation_session (
    conversation_id text PRIMARY KEY,
    phone text NOT NULL,
    status text NOT NULL,
    current_intent text,
    current_agent text,
    last_interaction timestamptz NOT NULL DEFAULT now(),
    customer_id text,
    lead_id text REFERENCES lead (lead_id)
);

CREATE INDEX IF NOT EXISTS conversation_session_phone_open
    ON conversation_session (phone)
    WHERE status <> 'CLOSED';
