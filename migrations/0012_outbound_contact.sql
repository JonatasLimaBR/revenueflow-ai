ALTER TABLE customer ADD COLUMN IF NOT EXISTS consent_opt_in_at  timestamptz;
ALTER TABLE customer ADD COLUMN IF NOT EXISTS consent_opt_out_at timestamptz;

CREATE TABLE IF NOT EXISTS outbound_contact (
    contact_id     text PRIMARY KEY,
    customer_id    text NOT NULL,
    opportunity_id text NOT NULL,
    status         text NOT NULL,
    skip_reason    text,
    contacted_at   timestamptz NOT NULL DEFAULT now()
);
