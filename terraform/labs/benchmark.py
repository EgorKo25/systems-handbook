#!/usr/bin/env python3
"""Local graph/state experiment in own temporary roots; no external providers."""
import argparse
import json
import math
import os
import shutil
import statistics
import subprocess
import tempfile
import time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--terraform',default='terraform')
p.add_argument('--counts',default='10,100')
p.add_argument('--repeats',type=int,default=5)
p.add_argument('--report',type=Path)
a=p.parse_args()
counts=[int(x) for x in a.counts.split(',')]
assert 1<=a.repeats<=20 and all(1<=x<=1000 for x in counts)
binary=shutil.which(a.terraform)
if not binary: raise SystemExit('Real CLI required')
binary=str(Path(binary).resolve())
env={k:v for k,v in os.environ.items() if not k.startswith('TF_')}
env.update(CHECKPOINT_DISABLE='1',TF_INPUT='0',TF_IN_AUTOMATION='1')
rows=[]
with tempfile.TemporaryDirectory(prefix='tf-handbook-benchmark-') as temp:
    base=Path(temp); rc=base/'terraform.rc';rc.write_text('disable_checkpoint = true\n')
    env['TF_CLI_CONFIG_FILE']=str(rc)
    for n in counts:
        root=base/str(n);root.mkdir()
        (root/'main.tf').write_text('terraform { required_version = "= 1.17.1" }\nresource "terraform_data" "item" {\nfor_each = { for i in range('+str(n)+') : tostring(i) => i }\ninput = each.value\n}\n')
        def run(*args):
            start=time.perf_counter()
            r=subprocess.run([binary,'-chdir='+str(root),*args],capture_output=True,text=True,env=env,timeout=90)
            if r.returncode: raise AssertionError(r.stderr)
            return time.perf_counter()-start
        run('init','-input=false')
        apply_s=run('apply','-auto-approve')
        times=[run('plan','-detailed-exitcode') for _ in range(a.repeats)]
        rows.append({'instances':n,'plan_repeats':a.repeats,'plan_wall_s':times,
                     'plan_median_s':statistics.median(times),'plan_min_s':min(times),
                     'plan_max_s':max(times),'first_apply_wall_s':apply_s,
                     'state_bytes':(root/'terraform.tfstate').stat().st_size})
    result={'cli':'1.17.1','provider':'built-in terraform_data','backend':'local',
            'parallelism':'CLI default','cold_init_excluded':True,
            'external_api':False,'p95_estimated':False,'rows':rows}
    if a.report:a.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
