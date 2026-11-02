-- Read-only observation from lab_admin in the owned cluster.
SELECT clock_timestamp(), pg_current_wal_lsn();
SELECT pg_size_pretty(pg_total_relation_size('app.notes')) AS table_and_indexes,
       pg_relation_size('app.notes') AS heap_bytes;
SELECT pid, application_name, state, wait_event_type, wait_event,
       clock_timestamp()-query_start AS query_age,
       pg_blocking_pids(pid) AS blockers
FROM pg_stat_activity WHERE datname=current_database() ORDER BY pid;
SELECT pid,locktype,mode,granted,relation::regclass
FROM pg_locks WHERE database=(SELECT oid FROM pg_database WHERE datname=current_database())
   OR locktype='advisory' ORDER BY pid,locktype;
SELECT indexrelid::regclass,indisready,indisvalid
FROM pg_index WHERE indrelid='app.notes'::regclass;
SELECT temp_files,temp_bytes,deadlocks FROM pg_stat_database WHERE datname=current_database();
SELECT n_live_tup,n_dead_tup,last_autovacuum FROM pg_stat_user_tables
WHERE schemaname='app' AND relname='notes';
