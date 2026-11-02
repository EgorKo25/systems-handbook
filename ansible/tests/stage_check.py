#!/usr/bin/env python3
"""Execute only extracted read/copy/file/SHA stage tasks locally under own /tmp."""
from pathlib import Path
import argparse
import copy
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import yaml
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ansible-bin',type=Path,required=True)
args=parser.parse_args()
root=Path(tempfile.mkdtemp(prefix='ansible-stage-check-'))
try:
    original=yaml.safe_load((ROOT/'labs/vm/site.yml').read_text())[0]
    source_stat=next(t for t in original['pre_tasks'] if t.get('register')=='counter_source_artifact')
    source_assert=original['pre_tasks'][original['pre_tasks'].index(source_stat)+1]
    block=original['tasks'][0]['block']
    until=next(i for i,t in enumerate(block) if t['name']=='Require the compiled version')
    stage=copy.deepcopy(block[:until])
    # Adapt only ownership to the test runner, so this cannot require privilege.
    # Source task ordering, copy guard, paths, content and SHA assertions stay intact.
    for task in stage:
        for key in ('ansible.builtin.copy','ansible.builtin.file'):
            if key in task:
                task[key]['owner']=str(os.getuid())
                task[key]['group']=str(os.getgid())
    allowed={'name','when','register','delegate_to','become','ansible.builtin.stat','ansible.builtin.assert','ansible.builtin.copy','ansible.builtin.file'}
    assert all(set(t)<=allowed for t in [source_stat,source_assert,*stage])
    env=os.environ.copy()
    for key in list(env):
        if key.startswith('ANSIBLE_'):del env[key]
    cfg=root/'ansible.cfg';cfg.write_text('[defaults]\nretry_files_enabled=False\n')
    env.update(ANSIBLE_CONFIG=str(cfg),ANSIBLE_HOME=str(root/'home'),
               ANSIBLE_LOCAL_TEMP=str(root/'local'),ANSIBLE_REMOTE_TEMP=str(root/'remote'),
               ANSIBLE_COLLECTIONS_PATH=str(root/'collections'),ANSIBLE_ROLES_PATH=str(root/'roles'),
               ANSIBLE_NOCOLOR='1',ANSIBLE_FORCE_COLOR='0',PYTHONDONTWRITEBYTECODE='1')
    version=subprocess.check_output([str(args.ansible_bin/'ansible'),'--version'],env=env,text=True).splitlines()[0]
    assert '[core 2.21.5]' in version,version
    trusted=b'original independently trusted release bytes\n'
    damaged=b'damaged controller source\n'
    digest=hashlib.sha256(trusted).hexdigest()
    source=root/'controller-artifact'

    def case(label,existing,source_bytes,wanted_sha,expected_success,mutate_after_preflight=False):
        target_root=root/label
        directory=target_root/'releases'/'0.1.0';directory.mkdir(parents=True)
        target=directory/'counter'
        if existing:
            target.write_bytes(trusted);target.chmod(0o644)
        source.write_bytes(source_bytes)
        tasks=[source_stat,source_assert]
        if mutate_after_preflight:
            tasks.append(dict(name='Fixture: source changes after observation',**{'ansible.builtin.copy':dict(dest=str(source),content=damaged.decode(),mode='0600')}))
        tasks+=stage
        play=[dict(name='Local stage component only',hosts='localhost',connection='local',gather_facts=False,become=False,
                   vars=dict(ansible_python_interpreter=sys.executable,counter_root=str(target_root),counter_release='0.1.0',counter_artifact=str(source),counter_sha256=wanted_sha),tasks=tasks)]
        path=root/(label+'.yml');path.write_text(yaml.safe_dump(play,sort_keys=False))
        result=subprocess.run([str(args.ansible_bin/'ansible-playbook'),'-i','localhost,',str(path)],env=env,capture_output=True,text=True,timeout=90)
        if (result.returncode==0)!=expected_success:raise AssertionError(label+'\n'+result.stdout+result.stderr)
        if existing:
            assert target.read_bytes()==trusted,label+' overwrote existing release'
        elif expected_success:
            assert target.read_bytes()==trusted,label+' copied wrong new bytes'
        else:
            assert not target.exists(),label+' wrote before rejecting bad source'
        if expected_success:assert target.stat().st_mode&0o777==0o755
        print('PASS '+label+': '+('accepted' if expected_success else 'rejected')+'; existing bytes preserved' if existing else 'PASS '+label+': '+('new bytes verified' if expected_success else 'rejected before target creation'))

    case('existing-valid-damaged-source',True,damaged,digest,False)
    case('existing-valid-source-changes-after-preflight',True,trusted,digest,True,True)
    case('new-release-wrong-sha',False,trusted,'0'*64,False)
    case('new-release-valid-source',False,trusted,digest,True)
    case('existing-valid-metadata-drift',True,trusted,digest,True)
    print('PASS real extracted stage tasks on local connection, temporary files only; no unit, role bootstrap, SSH, become or VM run')
finally:
    shutil.rmtree(root)
