SET LOCAL lock_timeout = '2s';
-- Irreversible loss of the old representation. Only v3 writers may remain.
ALTER TABLE app.notes DROP COLUMN body;
