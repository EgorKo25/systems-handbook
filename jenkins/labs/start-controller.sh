#!/usr/bin/env bash
# Start the isolated handbook controller in the foreground. No installation.
set -euo pipefail

JENKINS_LAB_ROOT="${1:?Укажите существующий отдельный каталог лаборатории}"
JENKINS_LAB_PORT="${2:-18080}"
case "$JENKINS_LAB_PORT" in
    ''|*[!0-9]*) printf '%s\n' 'Порт должен быть числом.' >&2; exit 2 ;;
esac
if (( JENKINS_LAB_PORT < 1024 || JENKINS_LAB_PORT > 65535 )); then
    printf '%s\n' 'Выберите непривилегированный порт 1024–65535.' >&2
    exit 2
fi
JENKINS_LAB_ROOT="$(cd -- "$JENKINS_LAB_ROOT" && pwd -P)"
JENKINS_LAB_WAR="$JENKINS_LAB_ROOT/downloads/jenkins-2.580.2.war"
python3 - "$JENKINS_LAB_WAR" <<'PY'
import hashlib
from pathlib import Path
import sys
path = Path(sys.argv[1])
expected = 'd98032d2401c540a35613a82ed358921fcf3166d5e6eaaaf60a7941845be3251'
actual = hashlib.sha256(path.read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit('SHA-256 WAR отличается от зафиксированного учебного выпуска')
PY
mkdir -p -- "$JENKINS_LAB_ROOT/controller-home" "$JENKINS_LAB_ROOT/controller-war"
export JENKINS_HOME="$JENKINS_LAB_ROOT/controller-home"
exec java -Xms128m -Xmx512m -Djava.awt.headless=true \
    -jar "$JENKINS_LAB_WAR" \
    --httpListenAddress=127.0.0.1 --httpPort="$JENKINS_LAB_PORT" \
    --webroot="$JENKINS_LAB_ROOT/controller-war"
