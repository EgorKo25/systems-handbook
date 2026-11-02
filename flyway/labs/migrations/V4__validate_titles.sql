SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';
ALTER TABLE app.notes VALIDATE CONSTRAINT notes_title_present;
