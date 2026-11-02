SET LOCAL lock_timeout = '2s';
-- Run only after all v1 writers have been drained and backfill has completed.
ALTER TABLE app.notes ADD CONSTRAINT notes_title_present
    CHECK (title IS NOT NULL) NOT VALID;
