CREATE TABLE IF NOT EXISTS audit_event (
    audit_id        text PRIMARY KEY,
    trace_id        text NOT NULL,
    conversation_id text NOT NULL,
    turn_id         text NOT NULL,
    agent           text,
    model           text,
    prompt_version  text,
    outcome         text NOT NULL,
    policy_decision text,
    handoff         boolean NOT NULL DEFAULT false,
    tools           jsonb NOT NULL DEFAULT '[]'::jsonb,
    token_usage     integer NOT NULL DEFAULT 0,
    cost_usd        numeric NOT NULL DEFAULT 0,
    latency_ms      integer,
    events          jsonb NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_event_conversation_idx ON audit_event (conversation_id);

CREATE OR REPLACE VIEW v_ai_cost_per_conversation AS
SELECT conversation_id,
       sum(cost_usd)    AS cost_usd,
       sum(token_usage) AS tokens,
       count(*)         AS turns,
       max(created_at)  AS last_at
FROM audit_event
GROUP BY conversation_id;

CREATE OR REPLACE VIEW v_ai_cost_per_outcome AS
SELECT outcome,
       count(*)               AS turns,
       sum(cost_usd)          AS cost_usd,
       round(avg(latency_ms)) AS avg_latency_ms
FROM audit_event
GROUP BY outcome;
