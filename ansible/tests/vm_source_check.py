#!/usr/bin/env python3
"""Static regression guards for the unexecuted VM recipe; requires PyYAML."""
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
play=yaml.safe_load((ROOT/'labs/vm/site.yml').read_text())[0]
pre=play['pre_tasks'];block=play['tasks'][0]['block'];rescue=play['tasks'][0]['rescue']
source=next(t for t in pre if t.get('register')=='counter_source_artifact')
assert source['delegate_to']=='localhost' and source['become'] is False
assert source['ansible.builtin.stat']['checksum_algorithm']=='sha256'
assert source['ansible.builtin.stat']['follow'] is False
assert play['gather_facts'] is False
assert pre[0]['delegate_to']=='localhost' and pre[0]['become'] is False
setup=next(t for t in pre if 'ansible.builtin.setup' in t)
assert pre.index(setup)>pre.index(source)+1
assert all(t.get('delegate_to')=='localhost' and t.get('become') is False for t in pre[:pre.index(setup)])
source_assert=pre[pre.index(source)+1]['ansible.builtin.assert']['that']
assert any('counter_source_artifact.stat.checksum' in str(x) and 'counter_sha256' in str(x) for x in source_assert)
assert not any(any(k in t for k in ('ansible.builtin.copy','ansible.builtin.template','ansible.builtin.file','ansible.builtin.user')) for t in pre)
copy=next(t for t in block if 'ansible.builtin.copy' in t)
assert copy['when']=='not counter_existing_release.stat.exists', 'Never rewrite an existing release, even from a new controller source'
metadata=block[block.index(copy)+1]
assert 'ansible.builtin.file' in metadata and metadata['ansible.builtin.file']['state']=='file'
assert 'src' not in metadata['ansible.builtin.file'] and 'content' not in metadata['ansible.builtin.file']
existing=next(t for t in block if t.get('register')=='counter_existing_release')
assert block.index(existing)<block.index(copy)
existing_assert=block[block.index(existing)+1]['ansible.builtin.assert']['that']
assert any('counter_existing_release.stat.checksum == counter_sha256' in str(x) for x in existing_assert)
unit=next(t for t in rescue if t.get('register')=='counter_rescue_unit')
service=next(t for t in rescue if 'ansible.builtin.systemd_service' in t)
assert rescue.index(unit)<rescue.index(service) and service['when']=='counter_rescue_unit.stat.exists'
assert any(t.get('register')=='counter_restored_version' for t in rescue)
assert any(t.get('register')=='counter_restored_data' for t in rescue)
assert 'ansible.builtin.fail' in rescue[-1]
print('PASS static VM regression guards: controller SHA preflight; copy only absent; metadata-only correction; guarded first-install cleanup; version/data rollback probes')
print('No SSH, become, systemd or VM operation was executed.')
