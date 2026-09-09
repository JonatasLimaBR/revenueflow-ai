CREATE INDEX IF NOT EXISTS approval_status_expires_idx
    ON approval (status, expires_at) WHERE status = 'PENDING';

CREATE INDEX IF NOT EXISTS quote_status_expiration_idx
    ON quote (status, expiration) WHERE status = 'SENT';
