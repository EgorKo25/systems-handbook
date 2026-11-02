# Source reenter.bash first; source this file, which runs a subshell.
(
  declare -F c >/dev/null
  : "${fsid:?source reenter.bash first}"
  : "${image:?source reenter.bash first}"
set -euo pipefail
umask 077
set -o noclobber

test "$(c config get mon osd_pool_default_size)" = 3
test "$(c config get mon osd_pool_default_min_size)" = 0
test "$(c config get mon mon_allow_pool_size_one)" = false

c osd pool ls --format=json | python3 -B -c '
import json, sys
if "cephstudy" in json.load(sys.stdin):
    raise SystemExit("existing pool: inspect, do not recreate")
'
c osd crush rule ls --format=json | python3 -B -c '
import json, sys
if "cephstudy-host" in json.load(sys.stdin):
    raise SystemExit("existing rule: inspect, do not recreate")
'

c osd crush rule create-replicated cephstudy-host default host
c osd pool create cephstudy 8 8 replicated \
  --rule=cephstudy-host --autoscale-mode=off
c osd pool application enable cephstudy cephstudy

c osd pool get cephstudy all --format=json | python3 -B -c '
import json, sys
p = json.load(sys.stdin)
if (p.get("size"), p.get("min_size")) != (3,2):
    raise SystemExit("expected fresh pool 3/2")
'

restore_guard() {
  status=$?
  trap - EXIT
  if ! c config set mon mon_allow_pool_size_one false; then
    printf '%s\n' 'Failed to restore size-one guard; inspect MON config.' >&2
    exit 1
  fi
  exit "$status"
}
trap restore_guard EXIT

c config set mon mon_allow_pool_size_one true
c osd pool set cephstudy size 1 --yes-i-really-mean-it
c osd pool set cephstudy min_size 1
c config set mon mon_allow_pool_size_one false
trap - EXIT

c osd pool get cephstudy all --format=json | python3 -B -c '
import json, sys
p = json.load(sys.stdin)
if (p.get("size"), p.get("min_size")) != (1,1):
    raise SystemExit("expected teaching pool 1/1")
'

ready=0
for attempt in $(seq 1 120); do
  if c pg ls-by-pool cephstudy --format=json | python3 -B -c '
import json, sys
stats = json.load(sys.stdin).get("pg_stats", [])
if len(stats) != 8 or any(p.get("state") != "active+clean" for p in stats):
    raise SystemExit(1)
'; then
    ready=1
    break
  fi
  sleep 2
done
test "$ready" = 1

c pg ls-by-pool cephstudy
c health detail
)
