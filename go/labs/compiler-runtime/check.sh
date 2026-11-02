#!/usr/bin/env bash
# Preconditions: Linux amd64, Python3, Bash, existing Go1.27.3 on PATH;
# cwd is the repository root containing go/labs/compiler-runtime and go/labs/service.
# RUNNER_TEMP exists and belongs to this CI job. No installs or external modules.
set -eu
: "${RUNNER_TEMP:?CI must provide its owned temporary directory}"
VOLUME="$PWD/go"
GO=$(command -v go) || exit 1
stand_parent=$(mktemp -d "$RUNNER_TEMP/go-runtime.XXXXXX") || exit 1
python3 "$VOLUME/labs/compiler-runtime/prepare.py" --go "$GO" --root "$stand_parent/stand" || exit 1
. "$stand_parent/stand/env.sh" || exit 1
cd "$LABROOT/projects/compilerlab" || exit 1
"$GO" test -count=1 -timeout=30s ./... || exit 1
"$GO" build -trimpath -buildvcs=false -o "$LABROOT/out/compiler" . || exit 1
python3 "$VOLUME/labs/compiler-runtime/observe.py" elf "$LABROOT/out/compiler" || exit 1
cd "$LABROOT/service" || exit 1
if "$GO" test -count=1 -timeout=30s -json -run='^TestHandler$/^(health|name)$' \
  ./internal/httpapp >"$LABROOT/reports/selected.jsonl" 2>"$LABROOT/reports/selected.stderr"; then
  rc=0
else
  rc=$?
fi
printf '%s\n' "$rc" >"$LABROOT/reports/selected.exit"
test "$rc" -eq 0 || exit "$rc"
python3 "$VOLUME/labs/compiler-runtime/observe.py" events "$LABROOT/reports/selected.jsonl" \
  --require 'example.org/handbook-service/internal/httpapp/TestHandler/health' \
  --require 'example.org/handbook-service/internal/httpapp/TestHandler/name' || exit 1
# Finite own loopback processes only; helper stops its children in finally.
python3 "$VOLUME/labs/compiler-runtime/release.py" --root "$LABROOT" || exit 1
python3 - "$LABROOT/releases/report.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1]))
assert r.get('ok') is True and r.get('children_stopped') is True
assert len(r['checks'])==7 and all(x['ok'] for x in r['checks'])
PY
