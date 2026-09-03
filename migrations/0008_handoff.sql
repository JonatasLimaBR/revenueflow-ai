CREATE TABLE IF NOT EXISTS handoff (
    handoff_id      text PRIMARY KEY,
    conversation_id text NOT NULL,
    reason          text NOT NULL,
    context         jsonb NOT NULL,
    status          text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS handoff_one_open_per_conversation
    ON handoff (conversation_id) WHERE status = 'PENDING';
