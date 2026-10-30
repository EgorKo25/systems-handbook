\set ON_ERROR_STOP on
BEGIN;
DO $$ BEGIN
  IF current_database() <> 'course_db' THEN
    RAISE EXCEPTION 'Only the isolated course_db database is allowed';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='course') THEN
    RAISE EXCEPTION 'course schema already exists; refusing to overwrite it';
  END IF;
END $$;
CREATE ROLE course_owner NOLOGIN;
CREATE ROLE course_reader NOLOGIN;
CREATE ROLE course_writer NOLOGIN;
CREATE SCHEMA course AUTHORIZATION course_owner;
GRANT CONNECT ON DATABASE course_db TO course_reader, course_writer;
SET ROLE course_owner;
GRANT USAGE ON SCHEMA course TO course_reader, course_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA course GRANT SELECT ON TABLES TO course_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA course GRANT SELECT, INSERT, UPDATE ON TABLES TO course_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA course GRANT USAGE ON SEQUENCES TO course_writer;
CREATE TABLE course.documents(id serial PRIMARY KEY, title text NOT NULL);
INSERT INTO course.documents(title) VALUES ('Первый'),('Второй');
CREATE TABLE course.counter(id integer PRIMARY KEY, value integer NOT NULL);
INSERT INTO course.counter VALUES (1,10);
RESET ROLE;
COMMIT;
\echo READY: course schema, three NOLOGIN roles, documents and counter created
