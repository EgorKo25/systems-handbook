#!/usr/bin/env bash
# Self-contained NAT lab. Default: help. No interface is attached to the host.
# nft/sysctl/routes are changed only in newly created, registered namespaces.
set -Eeuo pipefail

help() {
  cat <<'HELP'
Изолированная лаборатория NAT, Linux, без доступа к интернету.
  bash nat-lab.sh --help       прочитать эту памятку
  bash nat-lab.sh --run        создать стенд, проверить, удалить стенд

Нужны: bash, ip, nft, python3, sysctl, mktemp; для запуска без root —
unshare и mount, а также разрешённые пользовательские пространства Linux.
Сценарий попробует unshare -Urnm: права администратора будут действовать
только в новом пользовательском и сетевом пространстве. Если эта возможность
запрещена, сценарий завершится до создания стенда. Можно явно запустить его
с правами root в своей учебной виртуальной машине.

Пять узлов C/I/G/U/S соединены только друг с другом. Проверяются: отсутствие
обратного маршрута, SNAT, DNAT, возврат к внутренней службе через внешний
адрес (hairpin), запрет нового входящего соединения и счётчики первого пакета.
Сценарий не устанавливает программы. При выходе удаляет только созданные им
пространства и завершает только запущенные им серверы. SIGKILL/отключение
питания не позволяют оболочке выполнить обработчик завершения.
HELP
}
if [[ $# == 0 || ${1:-} == --help ]]; then help; exit 0; fi
if [[ $# != 1 || $1 != --run ]]; then help >&2; exit 2; fi
for tool in ip nft python3 sysctl mktemp; do
  command -v "$tool" >/dev/null || { printf 'Нет команды %s; ничего не изменено.\n' "$tool" >&2; exit 1; }
done

if (( EUID != 0 )); then
  for tool in unshare mount; do
    command -v "$tool" >/dev/null || { printf 'Нет %s для запуска без root.\n' "$tool" >&2; exit 1; }
  done
  if ! unshare -Urnm true 2>/dev/null; then
    printf '%s\n' 'Пользовательские пространства запрещены: стенд не создан.' \
      'Используйте учебную виртуальную машину с разрешённым unshare либо правами root.' >&2
    exit 1
  fi
  script_path=$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$0")
  # Keep the already opened script available if it lives under /run/media
  # (a USB mount). The private /run below deliberately hides that pathname.
  exec 3< "$script_path"
  exec unshare -Urnm bash -c '
    set -e
    mount --make-rprivate /
    cd /tmp
    mount -t tmpfs -o mode=0755 tmpfs /run
    mkdir -p /run/netns
    exec bash /proc/self/fd/3 --run
  ' nat-lab-wrapper
fi

# TMPDIR may point into /run/user, which the private /run hides as well.
# Use an explicit owned directory on /tmp, independent of the input pathname.
tmpdir=$(mktemp -d /tmp/natlab.XXXXXXXX)
prefix="nl-$$-${RANDOM}"
C="$prefix-c"; I="$prefix-i"; G="$prefix-g"; U="$prefix-u"; S="$prefix-s"
created=()
server_pids=()
server_starts=()
cleanup() {
  local rc=$? idx pid start
  trap - EXIT INT TERM
  set +e
  for idx in "${!server_pids[@]}"; do
    pid=${server_pids[$idx]}
    start=$(python3 -c 'import pathlib,sys
try: print(pathlib.Path("/proc/"+sys.argv[1]+"/stat").read_text().rsplit(") ",1)[1].split()[19])
except (OSError,IndexError): pass' "$pid" 2>/dev/null)
    if [[ -n $start && $start == "${server_starts[$idx]}" ]]; then
      kill "$pid" 2>/dev/null
    fi
    wait "$pid" 2>/dev/null
  done
  for ((idx=${#created[@]}-1; idx>=0; idx--)); do
    ip netns del "${created[$idx]}" 2>/dev/null
  done
  rm -rf -- "$tmpdir"
  printf '%s\n' 'Очистка: собственные серверы остановлены, собственные пространства удалены.'
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for ns in "$C" "$I" "$G" "$U" "$S"; do
  if ! ip netns add "$ns"; then
    printf '%s\n' 'Не удалось создать сетевое пространство; настройка остановлена.' >&2
    exit 1
  fi
  created+=("$ns")
  ip -n "$ns" link set dev lo up
done

# Each end is born inside a new namespace, never inside the host namespace.
ip -n "$C" link add eth0 type veth peer name lc netns "$G"
ip -n "$I" link add eth0 type veth peer name li netns "$G"
ip -n "$G" link add wan0 type veth peer name down0 netns "$U"
ip -n "$U" link add up0 type veth peer name eth0 netns "$S"
ip -n "$G" link add lan0 type bridge
ip -n "$G" link set dev lc master lan0
ip -n "$G" link set dev li master lan0
ip -n "$C" address add 10.77.10.10/24 dev eth0
ip -n "$I" address add 10.77.10.20/24 dev eth0
ip -n "$G" address add 10.77.10.1/24 dev lan0
ip -n "$G" address add 198.18.0.2/24 dev wan0
ip -n "$U" address add 198.18.0.1/24 dev down0
ip -n "$U" address add 198.18.1.1/24 dev up0
ip -n "$S" address add 198.18.1.20/24 dev eth0
for ns in "$C" "$I" "$S"; do ip -n "$ns" link set dev eth0 up; done
for dev in lc li lan0 wan0; do ip -n "$G" link set dev "$dev" up; done
for dev in down0 up0; do ip -n "$U" link set dev "$dev" up; done
ip -n "$C" route add default via 10.77.10.1
ip -n "$I" route add default via 10.77.10.1
ip -n "$G" route add default via 198.18.0.1
ip -n "$S" route add default via 198.18.1.1
for ns in "$G" "$U"; do
  ip netns exec "$ns" sysctl -q -w net.ipv4.ip_forward=1
done
# Remove inherited source-validation policy for a deterministic route-failure test.
# All writes below are namespace-local. Set after ip_forward, which resets defaults.
for ns in "$C" "$I" "$G" "$U" "$S"; do
  ip netns exec "$ns" sh -c '
    for f in /proc/sys/net/ipv4/conf/*/rp_filter; do printf 0 > "$f"; done
  '
done
# Make the LAN a plain Ethernet switch; routed packets still traverse inet hooks.
ip netns exec "$G" sh -c '
  for name in bridge-nf-call-iptables bridge-nf-call-ip6tables; do
    f=/proc/sys/net/bridge/$name
    if [ -f "$f" ]; then printf 0 > "$f"; fi
  done
'

cat > "$tmpdir/server.py" <<'PY'
import http.server, json, pathlib, sys
address, port, ready = sys.argv[1], int(sys.argv[2]), pathlib.Path(sys.argv[3])
class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def do_GET(self):
        body = (json.dumps({"peer": self.client_address[0], "peer_port": self.client_address[1],
                            "local": self.server.server_address[0], "path": self.path}) + "\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, fmt, *args):
        print(self.client_address, fmt % args, flush=True)
server = http.server.HTTPServer((address, port), Handler)
ready.write_text("ready\n")
server.serve_forever()
PY
cat > "$tmpdir/client.py" <<'PY'
import http.client, json, socket, sys
src, sport, dst, dport, expected = sys.argv[1:]
sock = socket.socket()
sock.settimeout(1.5)
sock.bind((src, int(sport)))
try:
    sock.connect((dst, int(dport)))
    sock.sendall(b"GET /nat-lab HTTP/1.1\r\nHost: lab.invalid\r\nConnection: close\r\n\r\n")
    response = http.client.HTTPResponse(sock)
    response.begin()
    data = json.loads(response.read())
except (OSError, http.client.HTTPException) as error:
    if expected == "FAIL":
        print("Ожидаемый отказ:", type(error).__name__, str(error))
        sys.exit(0)
    raise
finally:
    sock.close()
if expected == "FAIL":
    raise SystemExit("ОШИБКА: ожидался отказ, но получен ответ " + repr(data))
if data.get("peer") != expected:
    raise SystemExit("ОШИБКА адреса отправителя: " + repr(data))
print("HTTP 200; сервер наблюдает:", json.dumps(data, ensure_ascii=False))
PY
start_server() {
  local ns=$1 address=$2 port=$3 name=$4 pid start
  ip netns exec "$ns" python3 -u "$tmpdir/server.py" "$address" "$port" "$tmpdir/$name.ready" > "$tmpdir/$name.log" 2>&1 &
  pid=$!
  start=$(python3 -c 'import pathlib,sys; print(pathlib.Path("/proc/"+sys.argv[1]+"/stat").read_text().rsplit(") ",1)[1].split()[19])' "$pid")
  server_pids+=("$pid"); server_starts+=("$start")
  python3 - "$tmpdir/$name.ready" "$pid" <<'PY'
import os, pathlib, sys, time
ready, pid = pathlib.Path(sys.argv[1]), int(sys.argv[2])
deadline = time.monotonic() + 4
while not ready.exists():
    os.kill(pid, 0)
    if time.monotonic() > deadline:
        raise SystemExit("Сервер не начал слушать за 4 секунды")
    time.sleep(0.03)
PY
}
start_server "$S" 198.18.1.20 8080 external
start_server "$I" 10.77.10.20 7000 internal
# This listener makes an incoming-filter test distinguishable from a closed port.
start_server "$C" 10.77.10.10 9090 client-test

rules() {
  local outbound_snat=$1 hairpin_snat=$2
  cat > "$tmpdir/rules.nft" <<'NFT'
flush ruleset
table inet lab_filter {
  counter routed_packets { }
  counter blocked_new_wan { }
  chain input {
    type filter hook input priority filter; policy drop;
    iifname "lo" accept
    ct state invalid drop
    ct state established,related accept
    ip protocol icmp icmp type { echo-request, destination-unreachable, time-exceeded, parameter-problem } accept
  }
  chain forward {
    type filter hook forward priority filter; policy drop;
    counter name routed_packets
    ct state invalid drop
    ct state established,related accept
    iifname "lan0" oifname "wan0" ip saddr 10.77.10.0/24 ip daddr 198.18.1.20 tcp dport 8080 ct state new accept
    iifname "wan0" oifname "lan0" ip saddr 198.18.1.20 ip daddr 10.77.10.20 tcp dport 7000 ct status dnat ct state new accept
    iifname "lan0" oifname "lan0" ip saddr 10.77.10.0/24 ip daddr 10.77.10.20 tcp dport 7000 ct status dnat ct state new accept
    iifname "wan0" ct state new counter name blocked_new_wan drop
  }
}
table ip lab_nat {
  counter outbound_bindings { }
  counter published_bindings { }
  counter hairpin_bindings { }
  chain prerouting {
    type nat hook prerouting priority dstnat; policy accept;
    iifname "wan0" ip saddr 198.18.1.20 ip daddr 198.18.0.2 tcp dport 8080 counter name published_bindings dnat to 10.77.10.20:7000
    iifname "lan0" ip saddr 10.77.10.0/24 ip daddr 198.18.0.2 tcp dport 8080 counter name published_bindings dnat to 10.77.10.20:7000
  }
  chain postrouting {
    type nat hook postrouting priority srcnat; policy accept;
NFT
  if (( outbound_snat )); then
    cat >> "$tmpdir/rules.nft" <<'NFT'
    oifname "wan0" ip saddr 10.77.10.0/24 ip daddr 198.18.1.20 tcp dport 8080 counter name outbound_bindings snat to 198.18.0.2
NFT
  fi
  if (( hairpin_snat )); then
    cat >> "$tmpdir/rules.nft" <<'NFT'
    iifname "lan0" oifname "lan0" ip saddr 10.77.10.0/24 ip daddr 10.77.10.20 tcp dport 7000 ct status dnat counter name hairpin_bindings snat to 10.77.10.1
NFT
  fi
  printf '  }\n}\n' >> "$tmpdir/rules.nft"
  ip netns exec "$G" nft --check --file "$tmpdir/rules.nft"
  ip netns exec "$G" nft --file "$tmpdir/rules.nft"
}
request() {
  local ns=$1 src=$2 sport=$3 dst=$4 dport=$5 expected=$6
  ip netns exec "$ns" python3 "$tmpdir/client.py" "$src" "$sport" "$dst" "$dport" "$expected"
}

printf 'Стенд: C=%s I=%s G=%s U=%s S=%s\n' "$C" "$I" "$G" "$U" "$S"
printf '%s\n' '1. Проверка обратного маршрута U к 10.77.10.10 (должен отсутствовать).'
if ip -n "$U" route get 10.77.10.10; then
  printf '%s\n' 'ОШИБКА: неожиданный маршрут' >&2; exit 1
fi
rules 0 0
printf '%s\n' '2. Без SNAT клиент C не получает ответ.'
request "$C" 10.77.10.10 41001 198.18.1.20 8080 FAIL
rules 1 0
printf '%s\n' '3. Со SNAT внешняя служба видит 198.18.0.2.'
request "$C" 10.77.10.10 41002 198.18.1.20 8080 198.18.0.2
printf '%s\n' 'Счётчик NAT считает создание привязки, forward — все прошедшие здесь пакеты:'
ip netns exec "$G" nft list counter ip lab_nat outbound_bindings
ip netns exec "$G" nft list counter inet lab_filter routed_packets
ip netns exec "$G" nft -j list ruleset > "$tmpdir/counters.json"
python3 - "$tmpdir/counters.json" <<'PY'
import json, sys
entries = json.load(open(sys.argv[1]))["nftables"]
counts = {x["counter"]["name"]: x["counter"]["packets"] for x in entries if "counter" in x}
assert counts["outbound_bindings"] == 1, counts
assert counts["routed_packets"] > counts["outbound_bindings"], counts
print("Проверено: NAT=1, forward>1 для одного нового TCP-соединения")
PY
printf '%s\n' '4. DNAT: внешний S входит к I через 198.18.0.2:8080.'
request "$S" 198.18.1.20 42001 198.18.0.2 8080 198.18.1.20
printf '%s\n' '5. Возврат из LAN через внешний адрес без дополнительного SNAT не работает.'
request "$C" 10.77.10.10 41003 198.18.0.2 8080 FAIL
rules 1 1
printf '%s\n' '6. После SNAT возврат через внешний адрес работает; I видит 10.77.10.1.'
request "$C" 10.77.10.10 41004 198.18.0.2 8080 10.77.10.1
printf '%s\n' '7. Новый вход с WAN прямо к C: маршрут добавлен в U, служба C слушает, фильтр G запрещает.'
ip -n "$U" route add 10.77.10.0/24 via 198.18.0.2
request "$S" 198.18.1.20 42002 10.77.10.10 9090 FAIL
ip netns exec "$G" nft list counter inet lab_filter blocked_new_wan
ip netns exec "$G" nft -j list counter inet lab_filter blocked_new_wan > "$tmpdir/blocked.json"
python3 - "$tmpdir/blocked.json" <<'PY'
import json, sys
entries = json.load(open(sys.argv[1]))["nftables"]
assert any(x.get("counter", {}).get("packets", 0) > 0 for x in entries), entries
print("Проверено: пакет достиг запрещающего правила G")
PY
ip -n "$U" route del 10.77.10.0/24 via 198.18.0.2
printf '%s\n' 'Итоговый набор правил только шлюза G:'
ip netns exec "$G" nft list ruleset
printf '%s\n' 'Все семь этапов завершены успешно. Доступа к интернету не было.'
