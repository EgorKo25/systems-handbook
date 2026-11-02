#!/usr/bin/env python3
"""Real HCL/state fixtures with built-in provider; all data belongs to temp roots."""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--terraform',default='terraform')
p.add_argument('--report',type=Path)
a=p.parse_args()
binary=shutil.which(a.terraform)
if not binary:raise SystemExit('Real CLI 1.17.1 required')
binary=str(Path(binary).resolve())
env={k:v for k,v in os.environ.items() if not k.startswith('TF_')}
env.update(CHECKPOINT_DISABLE='1',TF_INPUT='0',TF_IN_AUTOMATION='1')
tests=[]
with tempfile.TemporaryDirectory(prefix='tf-handbook-language-') as tmp:
    base=Path(tmp);rc=base/'terraform.rc';rc.write_text('disable_checkpoint = true\n');env['TF_CLI_CONFIG_FILE']=str(rc)
    def tf(root,*args,expected=0):
        r=subprocess.run([binary,'-chdir='+str(root),*args],capture_output=True,text=True,env=env,timeout=30)
        assert r.returncode==expected,(args,r.returncode,r.stdout,r.stderr)
        return r
    def fixture(name):
        root=base/name;shutil.copytree(Path(__file__).resolve().parent/'fixtures'/name,root)
        tf(root,'init','-input=false');return root
    def passed(name):tests.append(name);print('PASS',name)
    root=fixture('unknown-bad');r=tf(root,'plan',expected=1)
    assert 'Invalid for_each argument' in r.stdout+r.stderr
    passed('unknown for_each key refuses first plan')
    root=fixture('unknown-good');tf(root,'plan','-out=good.tfplan');tf(root,'apply','good.tfplan');tf(root,'plan','-detailed-exitcode')
    passed('known key with unknown value plans and converges')
    root=fixture('cycle');r=tf(root,'validate',expected=1);assert 'Cycle' in r.stdout+r.stderr
    passed('mutual references rejected as dependency cycle')
    root=fixture('validation')
    for value in ['80','8080.5','65536']:
        r=tf(root,'plan','-var=port='+value,expected=1);assert 'port must be' in r.stdout+r.stderr
    passed('semantic validation rejects out-of-range and fractional ports')
    root=fixture('sensitive');r=tf(root,'apply','-auto-approve')
    assert 'dummy-not-a-real-secret' not in r.stdout
    assert 'dummy-not-a-real-secret' in tf(root,'state','pull').stdout
    assert json.loads(tf(root,'output','-json','example').stdout)=='dummy-not-a-real-secret'
    passed('sensitive redacts display but preserves ordinary state and JSON output value')
    root=fixture('address');source=root/'main.tf';original=source.read_text();tf(root,'apply','-auto-approve')
    raw=json.loads(tf(root,'state','pull').stdout);identity=raw['resources'][0]['instances'][0]['attributes']['id']
    source.write_text('terraform { required_version = "= 1.17.1" }\nremoved {\n from = terraform_data.owned\n lifecycle { destroy = false }\n}\n')
    tf(root,'plan','-out=forget.tfplan');tf(root,'apply','forget.tfplan');assert not tf(root,'state','list').stdout.strip()
    passed('removed destroy=false forgets association')
    source.write_text(original);tf(root,'plan','-out=readd.tfplan','-detailed-exitcode',expected=2)
    planned=json.loads(tf(root,'show','-json','readd.tfplan').stdout)
    assert planned['resource_changes'][0]['change']['actions']==['create']
    passed('restoring old HCL after removed proposes create, not implicit association recovery')
    source.write_text(original+'\nimport {\n to = terraform_data.owned\n id = '+json.dumps(identity)+'\n}\n')
    tf(root,'plan','-out=import.tfplan');tf(root,'apply','import.tfplan')
    raw=json.loads(tf(root,'state','pull').stdout);attributes=raw['resources'][0]['instances'][0]['attributes']
    assert attributes['id']==identity and attributes['input']['value']=='desired-input'
    tf(root,'plan','-detailed-exitcode')
    passed('built-in terraform_data import block restores ID association; config restores input')
    root=fixture('ignore');tf(root,'apply','-auto-approve');source=root/'main.tf';source.write_text(source.read_text().replace('port = 8080','port = 8180'))
    tf(root,'plan','-detailed-exitcode');raw=json.loads(tf(root,'state','pull').stdout)
    assert raw['resources'][0]['instances'][0]['attributes']['input']['value']['port']==8080
    passed('ignore_changes input.port suppresses correction and preserves old state field')
    root=fixture('collection');tf(root,'apply','-auto-approve')
    tf(root,'plan','-var=names=["worker","batch"]','-out=collections.tfplan')
    changes=json.loads(tf(root,'show','-json','collections.tfplan').stdout)['resource_changes']
    actions={r['address']:r['change']['actions'] for r in changes}
    assert actions['terraform_data.indexed[0]']==['update'] and actions['terraform_data.indexed[1]']==['update']
    assert actions['terraform_data.indexed[2]']==['delete']
    assert actions['terraform_data.keyed["api"]']==['delete'] and actions['terraform_data.keyed["worker"]']==['no-op']
    passed('count index shift changes remaining positions; for_each stable keys preserve worker')
    result={'cli':'1.17.1','external_providers':False,'count':len(tests),'tests':tests}
    if a.report:a.report.write_text(json.dumps(result,indent=2)+'\n')
print(len(tests),'real language/state fixture checks passed; own temporary roots removed')
