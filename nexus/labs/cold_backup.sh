#!/usr/bin/env bash
# Personal, standalone H2/File VM only. No live DB copy and no automatic rollback.
# Both lab File blob paths must be inside /srv/nexus-data; check in Nexus UI first.
# All Nexus launches must belong to nexus.service; no manual/escaped JVM or other writer.
die() { printf '%s\n' "$*" >&2; exit 1; }
[ "$EUID" -eq 0 ] || die "Run only as administrator of your own VM."
[ "$#" -eq 1 ] || die "Usage: bash cold_backup.sh snap-001"
[[ "$1" =~ ^snap-[0-9][0-9][0-9]$ ]] || die "Expected snap-NNN"
for tool in systemctl mountpoint rsync install; do
    command -v "$tool" >/dev/null || die "Missing tool: $tool"
done
mountpoint -q /mnt/nexus-backup || die "Backup volume is not mounted."
[ -d /srv/nexus-data ] || die "Missing data directory."
[ -d /opt/sonatype/nexus-3.97.3-01 ] || die "Missing selected installation."
[ -f /etc/systemd/system/nexus.service ] || die "Missing selected unit."
[ -f /etc/nginx/conf.d/nexus.conf ] || die "Missing selected NGINX configuration."
[ -d /etc/nexus-tls ] || die "Missing selected TLS directory."
fragment=$(systemctl show nexus --property=FragmentPath --value) || die "Cannot inspect unit."
[ "$fragment" = /etc/systemd/system/nexus.service ] || die "Unexpected unit file."
kill_mode=$(systemctl show nexus --property=KillMode --value) || die "Cannot inspect KillMode."
[ "$kill_mode" = control-group ] || die "This recipe requires KillMode=control-group."
dest=/mnt/nexus-backup/"$1"
[ ! -e "$dest" ] && [ ! -L "$dest" ] || die "Snapshot exists: inspect retained state."
install -d -o root -g root -m 0700 "$dest" || die "Cannot create private snapshot."
printf '%s\n' 'INCOMPLETE' > "$dest/STATE" || die "Cannot record snapshot state."
systemctl stop nexus || die "Stop failed; no data copy performed."
active=$(systemctl show nexus --property=ActiveState --value) || die "Cannot inspect stop."
main_pid=$(systemctl show nexus --property=MainPID --value) || die "Cannot inspect MainPID."
[ "$active" = inactive ] && [ "$main_pid" = 0 ] || die "Service is not confirmed inactive."
copy() { rsync -a --numeric-ids -- "$1" "$2" || die "Copy failed; retain INCOMPLETE snapshot, Nexus remains stopped."; }
copy /srv/nexus-data/ "$dest/data/"
copy /opt/sonatype/nexus-3.97.3-01/ "$dest/install/"
copy /etc/systemd/system/nexus.service "$dest/nexus.service"
copy /etc/nginx/conf.d/nexus.conf "$dest/nginx.conf"
copy /etc/nexus-tls/ "$dest/tls/"
printf '%s\n' 'COPIED; RESTORE ACCEPTANCE REQUIRED' > "$dest/STATE" || die "Cannot complete snapshot record."
systemctl start nexus || die "Copy complete, restart failed; inspect service logs."
printf '%s\n' "Copied to $dest. Check application and perform an isolated restore."
