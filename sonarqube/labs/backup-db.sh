#!/usr/bin/env bash
# Small PostgreSQL17 example, not a general backup framework.
# Usage: bash backup-db.sh INSTANCE_DIRECTORY BACKUP_PARENT_DIRECTORY
set -euo pipefail
umask 077
if [[ $# != 2 ]]; then
  printf 'Usage: bash backup-db.sh INSTANCE_DIRECTORY BACKUP_PARENT_DIRECTORY\n' >&2
  exit 2
fi
instance=$(cd -- "$1" && pwd -P)
mkdir -p -- "$2"
destination=$(cd -- "$2" && pwd -P)
cd -- "$instance"
[[ -f compose.yaml && -f images.env ]] || {
  printf 'Expected compose.yaml and private images.env in instance directory\n' >&2
  exit 2
}
compose=(docker compose --env-file images.env -f compose.yaml)
backup_set=$(mktemp -d "$destination/backup-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")
accepted=false
cleanup() {
  local status=$?
  if [[ $accepted != true ]]; then
    rm -rf -- "$backup_set"
    printf 'Backup not accepted; previous sets were not changed\n' >&2
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Redirect only into a new unique directory, never into a previous accepted dump.
"${compose[@]}" exec -T db pg_dump -U sonar -d sonar -Fc > "$backup_set/sonar.dump.partial"
[[ -s "$backup_set/sonar.dump.partial" ]]
"${compose[@]}" exec -T db pg_restore --list \
  < "$backup_set/sonar.dump.partial" > "$backup_set/sonar.dump.list.partial"
[[ -s "$backup_set/sonar.dump.list.partial" ]]
mv -- "$backup_set/sonar.dump.partial" "$backup_set/sonar.dump"
mv -- "$backup_set/sonar.dump.list.partial" "$backup_set/sonar.dump.list"
(
  cd -- "$backup_set"
  sha256sum sonar.dump > SHA256SUMS
)
printf '%s\n' 'handbook-sonar-db-backup-v1' > "$backup_set/COMPLETE"
accepted=true
# Only this path is stdout: a caller may save it after checking exit status.
printf '%s\n' "$backup_set"
