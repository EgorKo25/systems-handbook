SET LOCAL lock_timeout = '2s';
ALTER TABLE app.notes ADD COLUMN title text;
-- Release v3 must be able to stop writing body before that column is dropped.
ALTER TABLE app.notes ALTER COLUMN body DROP NOT NULL;
