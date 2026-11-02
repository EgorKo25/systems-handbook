-- Run as lab_admin on your own handbook DB. Passwords are set separately,
-- interactively or from private 0600 input; never replace placeholders in Git.
CREATE ROLE flyway_owner LOGIN;
CREATE ROLE app_runtime NOLOGIN;
CREATE ROLE vault_bootstrap LOGIN CREATEROLE;
GRANT app_runtime TO vault_bootstrap WITH ADMIN TRUE, INHERIT FALSE, SET FALSE;
CREATE SCHEMA app AUTHORIZATION flyway_owner;
CREATE SCHEMA flyway_meta AUTHORIZATION flyway_owner;
GRANT USAGE ON SCHEMA app TO app_runtime;
-- Apply the following as flyway_owner (SET ROLE here is only lab bootstrap).
SET ROLE flyway_owner;
ALTER DEFAULT PRIVILEGES IN SCHEMA app
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA app
  GRANT USAGE ON SEQUENCES TO app_runtime;
CREATE TABLE app.vault_probe(id bigint PRIMARY KEY, message text NOT NULL);
INSERT INTO app.vault_probe VALUES (1, 'saved application data');
-- The real Flyway history belongs in flyway_meta, not in app.
CREATE TABLE flyway_meta.vault_acl_probe(id integer PRIMARY KEY);
RESET ROLE;
