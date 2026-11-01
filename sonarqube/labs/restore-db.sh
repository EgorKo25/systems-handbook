#!/usr/bin/env bash
# Restore only this book's small single-owner PostgreSQL17 example into a NEW
# project. Leaves failed targets for inspection; never deletes existing volumes.
# Usage: bash restore-db.sh INSTANCE_DIRECTORY ACCEPTED_BACKUP_SET NEW_PROJECT PORT
set -euo pipefail
if [[ $# != 4 ]]; then
  printf 'Usage: bash restore-db.sh INSTANCE_DIRECTORY ACCEPTED_BACKUP_SET NEW_PROJECT PORT\n' >&2
  exit 2
fi
instance=$(cd -- "$1" && pwd -P)
backup_set=$(cd -- "$2" && pwd -P)
project=$3
port=$4
[[ $project =~ ^handbook-sonar-restore-[a-z0-9][a-z0-9_-]*$ ]] || {
  printf 'Choose a NEW project named handbook-sonar-restore-NAME\n' >&2
  exit 2
}
[[ $port =~ ^[1-9][0-9]{3,4}$ ]] && (( port <= 65535 && port != 9000 )) || {
  printf 'Choose a separate local port 1000..65535, except source port 9000\n' >&2
  exit 2
}
cd -- "$backup_set"
[[ -f COMPLETE && $(<COMPLETE) == handbook-sonar-db-backup-v1 && -s sonar.dump ]] || {
  printf 'Select an accepted backup set, not a partial file\n' >&2
  exit 2
}
checksum=$(<SHA256SUMS)
[[ $checksum =~ ^[0-9a-f]{64}[[:space:]][[:space:]]sonar[.]dump$ ]] || {
  printf 'Expected one checksum for sonar.dump\n' >&2
  exit 2
}
sha256sum --check --status SHA256SUMS
cd -- "$instance"
[[ -f compose.yaml && -f compose.restore.yaml && -f images.env ]] || {
  printf 'Expected compose files and private images.env in instance directory\n' >&2
  exit 2
}
export SONAR_BIND_PORT=$port
compose=(docker compose -p "$project" --env-file images.env -f compose.yaml -f compose.restore.yaml)
containers=$("${compose[@]}" ps --all --quiet)
volumes=$(docker volume ls --quiet --filter "label=com.docker.compose.project=$project")
[[ -z "$containers" && -z "$volumes" ]] || {
  printf 'Project already has containers/volumes; inspect it and choose another NEW name\n' >&2
  exit 2
}

# Stage 1: wait for final TCP server, then verify real credentials and empty DB.
"${compose[@]}" up --wait --wait-timeout 180 db
identity=$("${compose[@]}" exec -T db sh -c '
  export PGPASSWORD="$SONAR_DB_PASSWORD"
  exec psql -X -h 127.0.0.1 -U sonar -d sonar -v ON_ERROR_STOP=1 -At \
    -c "SELECT current_user, current_database(),
        (SELECT count(*) FROM information_schema.tables WHERE table_schema='\''public'\'');"
')
[[ $identity == 'sonar|sonar|0' ]] || {
  printf 'Expected sonar role, sonar database and empty public schema\n' >&2
  exit 1
}

# Stage 2: this small restore is one transaction; on SQL failure no partial
# restored tables are committed. No --create, --clean, or parallel --jobs here.
"${compose[@]}" exec -T db sh -c '
  export PGPASSWORD="$SONAR_DB_PASSWORD"
  exec pg_restore -h 127.0.0.1 -U sonar -d sonar \
    --exit-on-error --single-transaction --no-owner --no-privileges
' < "$backup_set/sonar.dump"

# Stage 3: reachable only after every command above succeeded.
"${compose[@]}" up -d sonar
printf 'Database restored; Sonar start requested on 127.0.0.1:%s. Complete application acceptance next.\n' "$port"
