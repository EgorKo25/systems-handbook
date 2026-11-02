#!/usr/bin/env bash
# UNEXECUTED cold backup recipe for this ONE-NODE personal VM only.
# Default local filestore, one dedicated PostgreSQL DB, no other writers/nodes.
# Intentionally does NOT restart Artifactory automatically after success/failure.
set -euo pipefail
destination=${1:?usage: bash recipes/backup-vm.sh OWN_NEW_BACKUP_DIRECTORY}
destination=$(realpath -m -- "$destination")
case "$destination" in /opt/jfrog|/opt/jfrog/*) printf '%s\n' 'Backup must be outside JFROG_HOME' >&2; exit 1;; esac
test ! -e "$destination" || { printf '%s\n' 'Backup destination must be new' >&2; exit 1; }
umask 077
mkdir -p -- "$destination"
sudo systemctl stop artifactory.service
if sudo systemctl is-active --quiet artifactory.service; then
  printf '%s\n' 'Service still active; stop' >&2; exit 1
fi
if pgrep -u artifactory >/dev/null; then
  printf '%s\n' 'Service identity still owns running processes; inspect before backup' >&2; exit 1
fi
pg_isready -h127.0.0.1 -p5432
pg_dump --version > "$destination/postgresql-client-version.txt"
sudo -u postgres pg_dump --format=custom --dbname=artifactory > "$destination/artifactory.dump"
sudo -u postgres pg_dumpall --globals-only > "$destination/globals.sql"
sudo tar -C /opt/jfrog -czf - artifactory/var > "$destination/artifactory-var.tar.gz"
cp -- "$0" "$destination/backup-recipe.sh"
(
  cd -- "$destination"
  sha256sum artifactory.dump globals.sql artifactory-var.tar.gz postgresql-client-version.txt backup-recipe.sh > SHA256SUMS
  sha256sum --check SHA256SUMS
)
printf '%s\n' 'Backup files created. Keep private. Artifactory is still STOPPED; restore has not been tested.'
