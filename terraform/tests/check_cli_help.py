#!/usr/bin/env python3
"""Read CLI1.17.1 help only; validate documented card flag names."""
import argparse
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--terraform',default='terraform')
p.add_argument('--report',type=Path)
a=p.parse_args()
binary=shutil.which(a.terraform)
if not binary:raise SystemExit('Real Terraform CLI required')
version=json.loads(subprocess.check_output([binary,'version','-json'],text=True))
assert version['terraform_version']=='1.17.1',version
spec=importlib.util.spec_from_file_location('terraform_reference',Path(__file__).resolve().parents[1]/'sources/reference.py')
ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
rows=[]
for card in ref.COMMANDS:
    r=subprocess.run([binary,*card['name'].split()[1:],'-help'],capture_output=True,text=True,timeout=15)
    helptext=r.stdout+r.stderr
    for flag in card['flags']:
        name=flag['flag'].split('=')[0]
        assert name in helptext,(card['name'],name)
    rows.append({'name':card['name'],'flags':len(card['flags']),'help_returncode':r.returncode})
result={'cli':'1.17.1','commands':rows,'flags_checked':sum(r['flags'] for r in rows)}
if a.report:a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(len(rows),'command help pages;',result['flags_checked'],'flag names match')
