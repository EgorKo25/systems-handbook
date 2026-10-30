#!/usr/bin/env python3
"""Create an isolated three-process BIND lab. Python 3.7+."""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("directory", type=Path)
root = parser.parse_args().directory.expanduser().resolve()
if any(c in str(root) for c in ('"', '\\', '\n', '\r')):
    parser.error("Use a path without quotes, backslashes or newlines")
root.mkdir(mode=0o700, parents=False, exist_ok=False)
zone = """$ORIGIN lab.test.
$TTL 120
@ 30 IN SOA ns1.lab.test. hostmaster.lab.test. (2026102701 30 10 300 30)
@ IN NS ns1.lab.test.
@ IN NS ns2.lab.test.
ns1 IN A 198.18.0.10
ns2 IN A 198.18.0.11
spo1 IN A 198.18.0.20
www IN CNAME app.lab.test.
_ldap._tcp IN SRV 0 100 389 ns1.lab.test.
_kerberos._udp IN SRV 0 100 88 ns1.lab.test.
_kerberos IN TXT "LAB.TEST"
"""
reverse = """$ORIGIN 0.18.198.in-addr.arpa.
$TTL 120
@ 30 IN SOA ns1.lab.test. hostmaster.lab.test. (2026102701 30 10 300 30)
@ IN NS ns1.lab.test.
10 IN PTR ns1.lab.test.
11 IN PTR ns2.lab.test.
20 IN PTR app.lab.test.
"""
for role, port in (("primary",1053),("secondary",2053),("resolver",3053)):
    directory = root / role
    directory.mkdir(mode=0o700)
    options = '''options {{
 directory "{directory}";
 listen-on port {port} {{ 127.0.0.1; }};
 listen-on-v6 {{ none; }};
 pid-file "{directory}/named.pid";
 session-keyfile "{directory}/session.key";
 managed-keys-directory "{directory}";
 recursion {recursion};
 allow-query {{ 127.0.0.1; }};
 allow-transfer {{ 127.0.0.1; }};
 dnssec-validation no;
 {cache}
}};
controls {{ }};
'''.format(directory=directory, port=port, recursion="yes" if role=="resolver" else "no",
           cache="allow-recursion { 127.0.0.1; }; allow-query-cache { 127.0.0.1; };" if role=="resolver" else "")
    for name, filename in (("lab.test","lab.test.zone"),("0.18.198.in-addr.arpa","reverse.zone")):
        if role == "primary":
            body = 'type primary; file "'+filename+'"; also-notify { 127.0.0.1 port 2053; };'
        elif role == "secondary":
            body = 'type secondary; primaries { 127.0.0.1 port 1053; }; file "'+filename+'";'
        else:
            body = 'type forward; forward only; forwarders { 127.0.0.1 port 1053; };'
        options += 'zone "'+name+'" { '+body+' };\n'
    (root / (role+".conf")).write_text(options,encoding="utf-8")
(root/"primary"/"lab.test.zone").write_text(zone,encoding="utf-8")
(root/"primary"/"reverse.zone").write_text(reverse,encoding="utf-8")
(root/".course-dns").write_text("DNS lab v1\n",encoding="ascii")
print("Created:",root)
print("Ports: primary 1053, secondary 2053, resolver 3053; loopback only")
