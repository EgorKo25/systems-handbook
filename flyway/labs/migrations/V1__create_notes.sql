CREATE TABLE app.notes (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    body text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
GRANT SELECT, INSERT, UPDATE ON app.notes TO app_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA app TO app_runtime;
