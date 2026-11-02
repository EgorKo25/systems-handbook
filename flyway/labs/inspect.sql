SELECT current_database(),current_user,inet_server_addr(),inet_server_port();
SELECT installed_rank,version,description,type,script,checksum,installed_by,
       installed_on,execution_time,success FROM flyway_meta.flyway_schema_history ORDER BY installed_rank;
SELECT count(*) AS notes FROM app.notes;
SELECT has_schema_privilege('app_local','app','CREATE') AS app_can_create,
       has_table_privilege('app_local','flyway_meta.flyway_schema_history','SELECT') AS app_reads_history;
