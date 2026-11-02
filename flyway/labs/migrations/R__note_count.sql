CREATE OR REPLACE VIEW app.note_count AS
SELECT count(*) AS notes FROM app.notes;
GRANT SELECT ON app.note_count TO app_runtime;
