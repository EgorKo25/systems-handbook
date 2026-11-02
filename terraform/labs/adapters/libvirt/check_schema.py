#!/usr/bin/env python3
"""Schema/validate only: no plan, apply, libvirt URI connection or guest start."""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--terraform',default='terraform')
p.add_argument('--mirror',type=Path)
p.add_argument('--report',type=Path)
a=p.parse_args()
binary=shutil.which(a.terraform)
if not binary:raise SystemExit('Real CLI required')
binary=str(Path(binary).resolve())
env={k:v for k,v in os.environ.items() if not k.startswith('TF_')}
env.update(CHECKPOINT_DISABLE='1',TF_IN_AUTOMATION='1',TF_INPUT='0')
with tempfile.TemporaryDirectory(prefix='tf-handbook-libvirt-validate-') as tmp:
    base=Path(tmp);root=base/'adapter'
    shutil.copytree(Path(__file__).resolve().parent,root,
                    ignore=shutil.ignore_patterns('.terraform','*.tfstate','*.tfstate.*','*.tfplan','__pycache__'))
    rc=base/'terraform.rc'; config='disable_checkpoint = true\n'
    if a.mirror:
        mirror=a.mirror.resolve()
        if not mirror.is_dir():raise SystemExit('Mirror not found')
        config+='provider_installation {\n filesystem_mirror {\n  path = '+json.dumps(str(mirror))+'\n  include = ["registry.terraform.io/dmacvicar/libvirt"]\n }\n}\n'
    rc.write_text(config);env['TF_CLI_CONFIG_FILE']=str(rc)
    report={'cli':'1.17.1','provider':'dmacvicar/libvirt 0.9.9','API_operations_executed':False,
            'offline_mirror':bool(a.mirror),
            'docs_example_correction':'boot_devices is list(object({dev=string})), not list(string); verified against schema'}
    for cmd in [['init','-backend=false','-input=false','-lockfile=readonly'],['validate'],['providers','schema','-json']]:
        r=subprocess.run([binary,'-chdir='+str(root),*cmd],capture_output=True,text=True,env=env,timeout=120)
        report[' '.join(cmd)]=r.returncode
        if r.returncode:
            print(r.stdout,r.stderr)
            raise SystemExit(r.returncode)
        if cmd[0]=='providers':
            schemas=json.loads(r.stdout)['provider_schemas']
            domain=schemas['registry.terraform.io/dmacvicar/libvirt']['resource_schemas']['libvirt_domain']
            assert domain['block']['attributes']['os']['nested_type']['attributes']['boot_devices']['nested_type']['attributes']['dev']['type']=='string'
            report['schema_version']=domain['version']
        print('PASS',' '.join(cmd))
    if a.report:a.report.write_text(json.dumps(report,indent=2)+'\n')
print('Only init/schema/validate completed; no libvirt API operation executed')
