#!/usr/bin/env python3
"""Create a private MIT Kerberos lab configuration. Python 3.7+."""
import argparse
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument("directory",type=Path)
root=parser.parse_args().directory.expanduser().resolve()
if any(c.isspace() or c in ('"','\\','{','}') for c in str(root)):
    parser.error("Use a path without whitespace or configuration delimiters")
root.mkdir(mode=0o700,parents=False,exist_ok=False)
(root/"krb5.conf").write_text("""[libdefaults]
 default_realm = LAB.TEST
 dns_lookup_kdc = false
 dns_lookup_realm = false
 rdns = false
[realms]
 LAB.TEST = {
  kdc = 127.0.0.1:10088
 }
[domain_realm]
 .lab.test = LAB.TEST
 lab.test = LAB.TEST
""",encoding="utf-8")
(root/"kdc.conf").write_text("""[kdcdefaults]
 kdc_listen = 127.0.0.1:10088
 kdc_tcp_listen = 127.0.0.1:10088
[realms]
 LAB.TEST = {{
  database_name = {root}/principal
  key_stash_file = {root}/stash
  max_life = 1h
  max_renewable_life = 8h
 }}
[logging]
 kdc = FILE:{root}/kdc.log
 admin_server = FILE:{root}/admin.log
""".format(root=root),encoding="utf-8")
print("Created:",root)
print("Set KRB5_CONFIG and KRB5_KDC_PROFILE before creating the lab database")
