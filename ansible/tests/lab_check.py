#!/usr/bin/env python3
"""Safe real Ansible checks: local connection, temp files, no privileged work."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'labs' / 'local'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ansible-bin', type=Path, help='directory containing an already prepared Ansible CLI')
    parser.add_argument('--keep', action='store_true', help='keep only the newly created private temporary lab')
    args = parser.parse_args()
    executable = (args.ansible_bin / 'ansible-playbook') if args.ansible_bin else Path(shutil.which('ansible-playbook') or '')
    if not executable.is_file():
        parser.error('prepare an isolated ansible-core 2.21.5 environment first; this script installs nothing')
    cli = executable.resolve().parent
    root = Path(tempfile.mkdtemp(prefix='ansible-book-check-'))
    env = os.environ.copy()
    for key in list(env):
        if key.startswith('ANSIBLE_'):
            del env[key]
    env.update(ANSIBLE_CONFIG=str(LOCAL / 'ansible.cfg'),
               ANSIBLE_HOME=str(root / 'ansible-home'),
               ANSIBLE_LOCAL_TEMP=str(root / 'controller-tmp'),
               ANSIBLE_REMOTE_TEMP=str(root / 'remote-tmp'),
               ANSIBLE_COLLECTIONS_PATH=str(root / 'collections'),
               ANSIBLE_ROLES_PATH=str(root / 'roles'),
               ANSIBLE_NOCOLOR='1', ANSIBLE_FORCE_COLOR='0',
               ANSIBLE_DISPLAY_ARGS_TO_STDOUT='false', PYTHONDONTWRITEBYTECODE='1')
    records = []
    vars_base = dict(lab_root=str(root), ansible_python_interpreter=sys.executable,
                     ansible_become=False)

    def run(command, expected=0, extra=None):
        result = subprocess.run([str(x) for x in command], cwd=LOCAL, env=env,
                                capture_output=True, text=True, timeout=120)
        (root / ('run-%02d.log' % len(records))).write_text(result.stdout + result.stderr)
        records.append(dict(command=[Path(str(command[0])).name] + [str(x) for x in command[1:]],
                            rc=result.returncode))
        if (expected == 0 and result.returncode != 0) or (expected != 0 and result.returncode == 0):
            raise AssertionError('unexpected CLI exit: ' + result.stdout[-5000:] + result.stderr[-2000:])
        return result.stdout

    def play(name, extra=None, flags=(), expected=0):
        path = root / 'run-vars.json'
        path.write_text(json.dumps({**vars_base, **(extra or {})}))
        return run([cli / 'ansible-playbook', name, '-e', '@' + str(path), *flags], expected)

    def recap(text):
        rows = {}
        for host, fields in re.findall(r'^(counter_[ab])\s+:\s+(.+)$', text, re.M):
            rows[host] = {key: int(value) for key, value in re.findall(r'(\w+)=(\d+)', fields)}
        assert rows, 'no play recap received'
        return rows

    def snapshots():
        return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                for host in ('counter_a', 'counter_b') for p in (root / host).rglob('*') if p.is_file()}

    try:
        version = run([cli / 'ansible', '--version']).splitlines()[0]
        assert '[core 2.21.5]' in version, 'This fixture edition requires core 2.21.5; got ' + version
        print('PASS runtime: ' + version)
        for filename in ('site.yml', 'precedence.yml', 'reuse.yml', 'failure.yml', 'serial.yml', 'module.yml'):
            play(filename, flags=('--syntax-check',))
        print('PASS six playbook syntax checks')
        inventory = json.loads(run([cli / 'ansible-inventory', '--list']))
        assert set(inventory['counters']['hosts']) == {'counter_a', 'counter_b'}
        assert all(inventory['_meta']['hostvars'][h]['ansible_connection'] == 'local' for h in inventory['counters']['hosts'])
        print('PASS inventory has exactly two local aliases')
        first = recap(play('site.yml', flags=('--diff',)))
        assert set(first) == {'counter_a', 'counter_b'}
        assert all(row['changed'] > 0 and row['failed'] == 0 for row in first.values())
        for host in first:
            assert json.loads((root / host / 'config.json').read_text())['release'] == '0.1.0'
            assert json.loads((root / host / 'applied.json').read_text())['release'] == '0.1.0'
            (root / host / 'data' / 'count.txt').write_text('41\n')
        before = snapshots()
        repeat = recap(play('site.yml'))
        assert all(row['changed'] == 0 for row in repeat.values()), repeat
        assert snapshots() == before
        print('PASS apply then unchanged repeat; persistent data remains 41')
        preview = play('site.yml', extra=dict(counter_release='0.2.0'), flags=('--check', '--diff'))
        assert any(row['changed'] > 0 for row in recap(preview).values())
        assert '0.2.0' in preview and snapshots() == before
        print('PASS check/diff predicts 0.2.0 without changing bytes or mtime')
        play('site.yml', extra=dict(counter_release='0.2.0'))
        for host in first:
            assert json.loads((root / host / 'config.json').read_text())['release'] == '0.2.0'
            assert json.loads((root / host / 'applied.json').read_text())['release'] == '0.2.0'
            assert (root / host / 'data' / 'count.txt').read_text() == '41\n'
        play('site.yml', extra=dict(counter_release='0.1.0'))
        assert all((root / h / 'data' / 'count.txt').read_text() == '41\n' for h in first)
        print('PASS forward and explicit configuration rollback preserve data')
        play('precedence.yml')
        play('precedence.yml', extra=dict(counter_port=8085, counter_expected_port=8085, extra_case=True))
        play('reuse.yml')
        serial = recap(play('serial.yml'))
        assert len(serial) == 2
        handled = recap(play('failure.yml'))
        assert all(row['rescued'] == 1 and row['failed'] == 0 for row in handled.values())
        print('PASS precedence, frozen set_fact, import/include gates, serial run_once and rescue')
        module_path = root / 'counter_a' / 'module.json'
        module_vars = dict(module_test_path=str(module_path), module_test_config={'release': 'test'}, module_expected_changed=True)
        play('module.yml', extra=module_vars)
        module_vars['module_expected_changed'] = False
        play('module.yml', extra=module_vars)
        module_path.chmod(0o644)
        module_vars['module_expected_changed'] = True
        module_before = (module_path.read_bytes(), module_path.stat().st_mode, module_path.stat().st_mtime_ns)
        play('module.yml', extra=module_vars, flags=('--check', '--diff'))
        assert module_before == (module_path.read_bytes(), module_path.stat().st_mode, module_path.stat().st_mtime_ns)
        play('module.yml', extra=module_vars)
        assert module_path.stat().st_mode & 0o777 == 0o640
        module_path.write_text('{broken')
        failure = play('module.yml', extra=module_vars, expected=1)
        assert 'configuration operation failed' in failure and module_path.read_text() == '{broken'
        symlink = root / 'counter_a' / 'module-link.json'
        symlink.symlink_to(module_path)
        module_vars['module_test_path'] = str(symlink)
        failure = play('module.yml', extra=module_vars, expected=1)
        assert 'not a symlink' in failure and symlink.is_symlink() and module_path.read_text() == '{broken'
        print('PASS module mode correction, check non-write, malformed JSON rejection and symlink rejection')
        password = root / 'vault-password'
        password.write_text(os.urandom(32).hex())
        password.chmod(0o600)
        secret = root / 'vault.yml'
        plaintext = 'fixture_secret: local-test-only\n'
        secret.write_text(plaintext)
        run([cli / 'ansible-vault', 'encrypt', '--vault-id', 'lab@' + str(password), secret])
        assert secret.read_text().startswith('$ANSIBLE_VAULT;') and plaintext not in secret.read_text()
        assert run([cli / 'ansible-vault', 'view', '--vault-id', 'lab@' + str(password), secret]) == plaintext
        print('PASS temporary Vault encrypt/view roundtrip without printing plaintext')
        print('PASS all real local checks; no SSH, VM, become, package manager or service operations')
        return 0
    finally:
        if args.keep:
            print('Private newly created lab retained at ' + str(root))
        else:
            shutil.rmtree(root)


if __name__ == '__main__':
    raise SystemExit(main())
