SELECT count(*) FROM app.notes;
-- Resolve by catalog OID: name lookup inside the denied schema must itself fail.
SELECT has_table_privilege(current_user,c.oid,'SELECT') AS history_read_allowed,
       has_schema_privilege(current_user,'app','CREATE') AS app_ddl_allowed
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='flyway_meta' AND c.relname='flyway_schema_history';
BEGIN;
UPDATE app.notes SET title=title WHERE false;
ROLLBACK;
