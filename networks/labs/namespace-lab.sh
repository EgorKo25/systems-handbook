#!/usr/bin/env bash
# Optional Linux-only experiment. All routes, sysctl and tc settings are in NEW namespaces.
# Never run automatically. Read this file first. Requires root, ip, python3, sysctl; tc optional.
set -euo pipefail
if [[ ${1:-} != --run ]]; then
  cat <<'HELP'
Необязательная изолированная лаборатория Linux.
Сначала прочитайте сценарий. Запуск: sudo bash namespace-lab.sh --run
С потерей SYN внутри нового пространства: sudo bash namespace-lab.sh --run --loss
Скрипт создаёт три новых сетевых пространства и удаляет только их.
HELP
  exit 0
fi
if (( EUID != 0 )); then
  printf '%s\n' 'Нужны права root: sudo bash namespace-lab.sh --run'
  exit 1
fi
for tool in ip python3 sysctl; do
  command -v "$tool" >/dev/null || { printf 'Нет команды: %s\n' "$tool"; exit 1; }
done
loss=0
if [[ ${2:-} == --loss ]]; then
  command -v tc >/dev/null || { printf '%s\n' 'Нет tc; используйте обычный режим.'; exit 1; }
  loss=1
elif [[ -n ${2:-} ]]; then
  printf '%s\n' 'Неизвестный аргумент; допустим только --loss'; exit 1
fi
prefix="dfbook-$$-${RANDOM}"
c="${prefix}-c"; r="${prefix}-r"; s="${prefix}-s"
created=()
server_pid=""
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  for ns in "${created[@]}"; do
    ip netns del "$ns" 2>/dev/null || true
  done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for ns in "$c" "$r" "$s"; do
  ip netns add "$ns"
  created+=("$ns")
  ip -n "$ns" link set lo up
done
# Both ends are created directly in namespaces: no host interface is reconfigured.
ip -n "$c" link add c0 type veth peer name rc netns "$r"
ip -n "$s" link add s0 type veth peer name rs netns "$r"
ip -n "$c" link set c0 address 02:00:00:00:00:10
ip -n "$r" link set rc address 02:00:00:00:00:01
ip -n "$r" link set rs address 02:00:00:01:00:01
ip -n "$s" link set s0 address 02:00:00:01:00:20
ip -n "$c" addr add 192.0.2.10/24 dev c0
ip -n "$r" addr add 192.0.2.1/24 dev rc
ip -n "$r" addr add 198.51.100.1/24 dev rs
ip -n "$s" addr add 198.51.100.20/24 dev s0
ip -n "$c" link set c0 up
ip -n "$r" link set rc up
ip -n "$r" link set rs up
ip -n "$s" link set s0 up
ip -n "$c" route add 198.51.100.0/24 via 192.0.2.1
ip -n "$s" route add 192.0.2.0/24 via 198.51.100.1
ip netns exec "$r" sysctl -q -w net.ipv4.ip_forward=1
printf 'Созданы %s, %s, %s\n' "$c" "$r" "$s"
printf '%s\n' 'Маршрут клиента:'
ip -n "$c" route get 198.51.100.20
printf '%s\n' 'Маршрут сервера обратно:'
ip -n "$s" route get 192.0.2.10
ip netns exec "$s" python3 -u -c '
import socket
with socket.socket() as listener:
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("198.51.100.20", 7000)); listener.listen(4); listener.settimeout(20)
    for _ in range(2):
        conn, address = listener.accept()
        with conn:
            conn.settimeout(5); request = bytearray()
            while b"\r\n\r\n" not in request:
                part = conn.recv(1024)
                if not part: raise EOFError("Оборван HTTP-запрос")
                request.extend(part)
                if len(request) > 4096: raise ValueError("Слишком длинный запрос")
            body = b"OK\n"
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\nConnection: close\r\n\r\n" + body)
            print("Сервер получил:", bytes(request).split(b"\r\n", 1)[0].decode())
' &
server_pid=$!
client() {
  ip netns exec "$c" python3 -c '
import socket, time, sys
want_failure = sys.argv[1] == "loss"
deadline = time.monotonic() + 4
while True:
    try:
        sock = socket.create_connection(("198.51.100.20", 7000), timeout=2)
        break
    except ConnectionRefusedError:
        if time.monotonic() >= deadline: raise
        time.sleep(0.02)
    except TimeoutError:
        if want_failure:
            print("Ожидаемо: SYN потерян, соединение не установлено за 2 секунды")
            sys.exit(0)
        raise
if want_failure:
    sock.close(); raise RuntimeError("Ожидалась потеря, но соединение установилось")
with sock:
    sock.sendall(b"GET /api/session HTTP/1.1\r\nHost: app.lab.test:7000\r\nConnection: close\r\n\r\n")
    reply = bytearray()
    while True:
        part = sock.recv(4096)
        if not part: break
        reply.extend(part)
    assert reply.endswith(b"\r\n\r\nOK\n")
    print("Клиент получил:", bytes(reply).split(b"\r\n", 1)[0].decode())
' "${1:-ok}"
}
client ok
printf '%s\n' 'Сосед клиента (MAC маршрутизатора):'
ip -n "$c" neigh show
if (( loss )); then
  # The queue being changed belongs only to c0 inside the new client namespace.
  ip netns exec "$c" tc qdisc add dev c0 root netem loss 100%
  client loss
  ip netns exec "$c" tc -s qdisc show dev c0
  ip netns exec "$c" tc qdisc del dev c0 root
fi
client ok
wait "$server_pid"
server_pid=""
printf '%s\n' 'Опыты завершены; временные пространства удаляются.'
