SELECT current_database(),current_user;
SELECT count(*),min(id),max(id),md5(string_agg(id::text,',' ORDER BY id)) AS id_fingerprint FROM app.notes;
SELECT md5(string_agg(row_to_json(n)::text,E'\n' ORDER BY id)) AS row_fingerprint FROM app.notes n;
SELECT installed_rank,version,script,checksum,success FROM flyway_meta.flyway_schema_history ORDER BY installed_rank;
SELECT indexrelid::regclass,indisvalid FROM pg_index WHERE indrelid='app.notes'::regclass;
