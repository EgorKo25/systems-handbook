#!/usr/bin/env python3
"""Actual controller-only rejection; fake SSH records any attempted transport."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ansible-bin', type=Path, required=True)
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='ansible-preflight-check-') as temporary:
    run_root = Path(temporary)
    source = run_root / 'artifact'
    source.write_bytes(b'not the trusted artifact\n')
    marker = run_root / 'ssh-was-called'
    ssh = run_root / 'ssh'
    ssh.write_text('#!/usr/bin/env python3\nfrom pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\nraise SystemExit(7)\n')
    ssh.chmod(0o700)
    inventory = run_root / 'inventory.yml'
    inventory.write_text('all:\n  children:\n    counters:\n      hosts:\n        audit_target:\n          ansible_host: 192.0.2.1\n          ansible_user: deploy\n')
    variables = run_root / 'vars.json'
    variables.write_text(json.dumps(dict(counter_personal_vm=True, counter_artifact=str(source), counter_sha256='0' * 64)))
    env = {k:v for k,v in os.environ.items() if not k.startswith('ANSIBLE_')}
    env.update(ANSIBLE_CONFIG=str(ROOT/'labs/vm/ansible.cfg'), ANSIBLE_SSH_EXECUTABLE=str(ssh),
               ANSIBLE_HOME=str(run_root/'home'), ANSIBLE_LOCAL_TEMP=str(run_root/'local-tmp'),
               ANSIBLE_REMOTE_TEMP=str(run_root/'remote-tmp'), ANSIBLE_NOCOLOR='1', PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([str(args.ansible_bin/'ansible-playbook'), str(ROOT/'labs/vm/site.yml'),
                             '-i', str(inventory), '-e', '@'+str(variables)],
                            cwd=run_root,env=env,text=True,capture_output=True,timeout=30)
    output = result.stdout + result.stderr
    assert result.returncode == 2, output
    assert 'Require a regular controller artifact matching the trusted manifest' in output, output
    assert 'counter_source_artifact.stat.checksum' in output and 'counter_sha256' in output, output
    assert not marker.exists(), 'SSH attempted before controller rejection: '+output
    assert 'TASK [Gathering Facts]' not in output and 'TASK [Gather target facts' not in output, output
    print('PASS wrong controller SHA rejected before facts/SSH/become; fake SSH never called')
    variables.write_text(json.dumps(dict(counter_personal_vm=True, ansible_connection='local', counter_artifact=str(source), counter_sha256='0' * 64)))
    refused = subprocess.run([str(args.ansible_bin/'ansible-playbook'), str(ROOT/'labs/vm/site.yml'), '-i', str(inventory), '-e', '@'+str(variables)], cwd=run_root, env=env, text=True, capture_output=True, timeout=30)
    output = refused.stdout + refused.stderr
    assert refused.returncode == 2 and 'hostvars[inventory_hostname].ansible_connection' in output, output
    assert 'TASK [Verify controller artifact' not in output and 'TASK [Gather target facts' not in output, output
    assert not marker.exists(), output
    print('PASS local target refused before artifact inspection or setup')
    print('Only temporary controller files were created; no VM or host service operation occurred.')
