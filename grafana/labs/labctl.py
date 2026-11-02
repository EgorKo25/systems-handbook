#!/usr/bin/env python3
"""Initialize a persistent private lab or print its native Grafana argv. No auto-start."""
from pathlib import Path
import argparse,os,secrets,shutil,json
HERE=Path(__file__).resolve().parent

def initialize(root,port=13000):
 root=root.resolve()
 if not 1024<=port<=65535:raise ValueError('choose a non-privileged TCP port')
 if any(ord(c)<32 or ord(c)==127 or c in "$#;'\u007d" for c in str(root)) or any(marker in str(root) for marker in ['@LAB_ROOT@','@PORT@']):raise ValueError("lab root contains unsupported INI/YAML characters or template markers; choose a path without control characters, $, #, ;, apostrophe, or }")
 if root.exists() and (not root.is_dir() or any(root.iterdir())):raise ValueError('existing non-empty root: refusing to reset or resume partial state')
 root.mkdir(parents=True,exist_ok=True)
 try:
  fd=os.open(root/'.handbook-init.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 except FileExistsError:raise ValueError('another or interrupted initialization owns this root')
 with os.fdopen(fd,'w') as f:f.write('Private lab initialization: preserve this marker and all state.\n')
 (root/'private').mkdir(mode=0o700)
 for d in ['config','data','logs','plugins','dashboards','provisioning/datasources','provisioning/dashboards','provisioning/alerting','evidence','backups']: (root/d).mkdir(parents=True,exist_ok=True)
 for name in ['admin-password','secret-key']:
  fd=os.open(root/'private'/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(32))
 def expand(s):return s.replace('@LAB_ROOT@',str(root)).replace('@PORT@',str(port))
 (root/'config/grafana.ini').write_text(expand((HERE/'grafana.ini.in').read_text()))
 shutil.copyfile(HERE/'provisioning/datasources/prometheus.yaml',root/'provisioning/datasources/prometheus.yaml')
 (root/'provisioning/dashboards/handbook.yaml').write_text(expand((HERE/'provisioning/dashboards/handbook.yaml.in').read_text()))
 shutil.copyfile(HERE/'dashboards/go-service.json',root/'dashboards/go-service.json')
 return root
if __name__=='__main__':
 a=argparse.ArgumentParser();s=a.add_subparsers(dest='command',required=True);i=s.add_parser('init');i.add_argument('root',type=Path);i.add_argument('--port',type=int,default=13000);p=s.add_parser('argv');p.add_argument('root',type=Path);p.add_argument('--grafana-home',type=Path,required=True);n=a.parse_args()
 if n.command=='init':print(initialize(n.root,n.port));print('Created private persistent lab; no server started. Password is in private/admin-password; do not publish it.')
 else:
  root=n.root.resolve();home=n.grafana_home.resolve()
  if not (root/'config/grafana.ini').is_file():a.error('initialize this lab first')
  if not (home/'bin/grafana').is_file():a.error('grafana binary is missing from the verified distribution')
  print(json.dumps([str(home/'bin/grafana'),'server','--homepath',str(home),'--config',str(root/'config/grafana.ini')],ensure_ascii=False))
