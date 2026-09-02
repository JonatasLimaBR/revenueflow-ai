ALTER TABLE approval ADD COLUMN IF NOT EXISTS expires_at        timestamptz;
ALTER TABLE approval ADD COLUMN IF NOT EXISTS approved_discount numeric;
ALTER TABLE approval ADD COLUMN IF NOT EXISTS decided_at        timestamptz;
