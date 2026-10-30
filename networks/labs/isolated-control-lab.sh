#!/usr/bin/env bash
# Optional real DHCP/DNS test. Host interfaces and services are untouched.
set -euo pipefail
if [[ ${1:-} != --run ]]; then
  cat <<'HELP'
Необязательная проверка реального DHCP и DNS в изолированных пространствах Linux.
Запуск: bash isolated-control-lab.sh --run
Нужны unshare, ip, mount, sysctl, dnsmasq, python3 и разрешённые пользовательские пространства.
Скрипт создаёт собственные user/mount/network namespaces, два внутренних сетевых
пространства, пару veth и один процесс dnsmasq. Файлы результатов сохраняются
в новом временном каталоге. Адреса и службы основного компьютера не меняются.
HELP
  exit 0
fi
if [[ $# != 1 ]]; then
  printf '%s\n' 'Допустим только аргумент --run.' >&2
  exit 2
fi
for tool in unshare ip mount sysctl dnsmasq python3 mktemp cp; do
  command -v "$tool" >/dev/null || { printf 'Нет команды: %s\n' "$tool" >&2; exit 1; }
done
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
[[ -r "$script_dir/control-packets.py" ]] || { printf '%s\n' 'Рядом со скриптом отсутствует читаемый control-packets.py.' >&2; exit 1; }
# /run will be hidden in the private mount namespace. Keep both the results
# and the imported module outside it, even when the book is on /run/media
# or the caller has TMPDIR=/run/user/....
result_dir="$(mktemp -d /tmp/book-control.XXXXXX)"
cp -- "$script_dir/control-packets.py" "$result_dir/control-packets.py"
printf 'Файлы опыта: %s\n' "$result_dir"
unshare -Urnm bash -s -- "$result_dir/control-packets.py" "$result_dir" <<'ISOLATED'
set -euo pipefail
# The caller supplies fresh user, mount and network namespaces.
# /run is overmounted only after mount propagation becomes private.
mount --make-rprivate /
mount -t tmpfs -o mode=755 tmpfs /run
mkdir -p /run/netns /run/book-dhcp
server_ns=book-dhcp-server
client_ns=book-dhcp-client
result_dir="$2"
server_pid=''
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  ip netns del "$client_ns" 2>/dev/null || true
  ip netns del "$server_ns" 2>/dev/null || true
}
trap cleanup EXIT
ip netns add "$server_ns"
ip netns add "$client_ns"
ip netns exec "$server_ns" ip link set lo up
ip netns exec "$client_ns" ip link set lo up
ip netns exec "$server_ns" ip link add lan0 type veth peer name c0 netns "$client_ns"
ip -n "$server_ns" link set lan0 address 02:00:00:77:10:01
ip -n "$client_ns" link set c0 address 02:00:00:77:10:64
ip -n "$server_ns" addr add 10.77.10.1/24 dev lan0
ip -n "$server_ns" link set lan0 up
ip -n "$client_ns" link set c0 up
ip netns exec "$client_ns" sysctl -q -w net.ipv4.conf.all.rp_filter=0
ip netns exec "$client_ns" sysctl -q -w net.ipv4.conf.c0.rp_filter=0
ip netns exec "$server_ns" dnsmasq --no-daemon --conf-file=/dev/null --user=root --group=root --interface=lan0 --bind-interfaces --no-hosts --no-resolv --local=/lab.test/ --domain=lab.test --host-record=app.lab.test,10.77.10.20 --local-ttl=300 --dhcp-range=10.77.10.100,10.77.10.150,255.255.255.0,1h --dhcp-option=option:router,10.77.10.1 --dhcp-option=option:dns-server,10.77.10.1 --dhcp-option=option:domain-name,lab.test --dhcp-leasefile=/run/book-dhcp/leases --pid-file= --log-dhcp --log-facility=- --no-ping >"$result_dir/dnsmasq.log" 2>&1 &
server_pid=$!
ip netns exec "$client_ns" python3 - "$1" "$result_dir" <<'PY'
import importlib.util,json,socket,struct,subprocess,sys,time
from pathlib import Path
result_dir=Path(sys.argv[2])
spec=importlib.util.spec_from_file_location('control_packets',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
 sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
 sock.setsockopt(socket.SOL_SOCKET,socket.SO_BINDTODEVICE,b'c0\x00')
 sock.bind(('0.0.0.0',68));sock.settimeout(.5)
 for attempt in range(8):
  sock.sendto(m.dhcp_payload(1),('255.255.255.255',67))
  try:
   offer,source=sock.recvfrom(4096)
   parsed=m.decode_dhcp(offer)
   if parsed['message_type']=='OFFER':break
  except TimeoutError:pass
 else:raise AssertionError('no real offer from dnsmasq')
 assert source==('10.77.10.1',67),source
 assert parsed['xid']==m.XID and parsed['yiaddr'].startswith('10.77.10.'),parsed
 offered=parsed['yiaddr']
 print('Реальное предложение dnsmasq:', source, 'адрес', offered, 'длина', len(offer))
 (result_dir/'real-dhcp-offer.bin').write_bytes(offer)
 request=m.dhcp_payload(3)
 # Substitute actually offered address; allocation is implementation-specific.
 needle=m.tlv(50,m.ipv4(m.CLIENT))
 assert needle in request
 request=request.replace(needle,m.tlv(50,m.ipv4(offered)),1)
 for attempt in range(8):
  sock.sendto(request,('255.255.255.255',67))
  try:
   ack,source=sock.recvfrom(4096);parsed=m.decode_dhcp(ack)
   if parsed['message_type']=='ACK':break
  except TimeoutError:pass
 else:raise AssertionError('no real ACK from dnsmasq')
 assert parsed['yiaddr']==offered and parsed['xid']==m.XID
 opts={o['code']:bytes.fromhex(o['hex']) for o in parsed['options']}
 assert opts[1]==m.ipv4('255.255.255.0') and opts[3]==m.ipv4(m.GATEWAY) and opts[6]==m.ipv4(m.GATEWAY)
 assert struct.unpack('!I',opts[51])[0]==3600 and opts[15]==b'lab.test'
 print('Реальное подтверждение:', offered, '/24; шлюз и DNS', m.GATEWAY, '; аренда 3600 с')
 (result_dir/'real-dhcp-ack.bin').write_bytes(ack)
 (result_dir/'real-dhcp-ack.json').write_text(json.dumps(parsed,ensure_ascii=False,indent=2)+'\n')
 print('Получение аренды прошло через UDP 0.0.0.0:68 без назначенного IPv4; rp_filter отключён только в свежем пространстве клиента.')

# Explicitly apply the observed address only inside the fresh client namespace.
subprocess.run(['ip','addr','add',offered+'/24','dev','c0'],check=True)
subprocess.run(['ip','route','add','default','via',m.GATEWAY],check=True)
print('В изолированном клиенте применены адрес и маршрут; далее проверяется DNS.')

def ask(name,kind=1,tcp=False):
 msg=struct.pack('!6H',0x7710,0x100,1,0,0,0)+m.name_bytes(name)+struct.pack('!HH',kind,1)
 if tcp:
  with socket.create_connection((m.GATEWAY,53),timeout=2) as dns:
   dns.sendall(struct.pack('!H',len(msg))+msg)
   prefix=b''
   while len(prefix)<2:
    part=dns.recv(2-len(prefix))
    if not part:raise EOFError('TCP ended before length prefix')
    prefix+=part
   length=struct.unpack('!H',prefix)[0];reply=b''
   while len(reply)<length:
    part=dns.recv(length-len(reply))
    if not part:raise EOFError('TCP ended before DNS message')
    reply+=part
 else:
  with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as dns:
   dns.settimeout(2);dns.sendto(msg,(m.GATEWAY,53));reply=dns.recv(4096)
 return m.decode_dns(reply),reply

results=[]
for name,kind,tcp,rcode,count in [('app.lab.test',1,False,0,1),('app.lab.test',1,True,0,1),('app.lab.test',28,False,0,0),('missing.lab.test',1,False,3,0),('example.com',1,False,5,0)]:
 decoded,reply=ask(name,kind,tcp)
 assert decoded['rcode']==rcode and decoded['counts']['answer']==count,decoded
 if kind==1 and count==1:assert decoded['answers'][0]['address']==m.APP
 label=name+'-'+str(kind)+('-tcp' if tcp else '-udp')
 (result_dir/(label+'.bin')).write_bytes(reply)
 results.append({'query':name,'type':kind,'transport':'TCP' if tcp else 'UDP','decoded':decoded})
 print('DNS',label,': RCODE',rcode,'записей ответа',count)
(result_dir/'real-dns-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print('OK: реальная выдача DHCP и пять реальных DNS-проверок завершены.')
PY
ISOLATED
printf 'Результаты и журнал: %s\n' "$result_dir"
