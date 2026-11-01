#!/usr/bin/env bash
# Official PostgreSQL image runs this only for an initially empty data directory.
(
set -euo pipefail
psql --set=ON_ERROR_STOP=1 --username="$POSTGRES_USER" --dbname=postgres \
  --set=sonar_password="$SONAR_DB_PASSWORD" <<'SQL'
CREATE ROLE sonar LOGIN PASSWORD :'sonar_password';
CREATE DATABASE sonar OWNER sonar ENCODING 'UTF8';
SQL
)
