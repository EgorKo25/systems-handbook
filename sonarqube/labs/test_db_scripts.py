#!/usr/bin/env python3
"""Execute Bash control flow with a stub Docker CLI; NOT a PostgreSQL restore."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
STUB = r'''
import hashlib, json, os, sys
args = sys.argv[1:]
text = ' '.join(args)
if args[:2] == ['volume', 'ls']:
    stage = 'volumes'
elif 'ps' in args:
    stage = 'containers'
elif 'up' in args:
    stage = 'start' if args[-1] == 'sonar' else 'ready'
elif 'pg_dump' in text:
    stage = 'dump'
elif 'pg_restore' in text:
    stage = 'list' if '--list' in text else 'restore'
elif 'psql' in text:
    stage = 'sql'
else:
    raise SystemExit('Unexpected Docker invocation: '+repr(args))
data = sys.stdin.buffer.read() if stage in ('list', 'restore') else b''
with open(os.environ['STUB_LOG'], 'a') as output:
    output.write(json.dumps(dict(stage=stage, args=args, port=os.getenv('SONAR_BIND_PORT'),
                                 stdin_sha=hashlib.sha256(data).hexdigest()))+'\n')
if os.getenv('FAIL_STAGE') == stage:
    if stage == 'dump':
        sys.stdout.buffer.write(b'PARTIAL-UNACCEPTED')
    print('deliberate stub failure at '+stage, file=sys.stderr)
    raise SystemExit(17)
if stage == 'dump' and not os.getenv('EMPTY_DUMP'):
    sys.stdout.buffer.write(b'PGDMP\0STUB-BYTES-NOT-A-REAL-DATABASE')
elif stage == 'list':
    print('STUB TOC; not a parsed PostgreSQL archive')
elif stage == 'sql':
    print(os.getenv('SQL_IDENTITY', 'sonar|sonar|0'))
elif stage in ('volumes', 'containers') and os.getenv('EXISTING_STAGE') == stage:
    print('existing-resource')
'''


class DatabaseScriptControlFlowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.instance = self.root/'instance'
        self.instance.mkdir()
        for name in ('compose.yaml', 'compose.restore.yaml', 'images.env'):
            (self.instance/name).write_text('# dummy; stub CLI does not parse configuration\n')
        self.backups = self.root/'backups'
        self.bin = self.root/'bin'; self.bin.mkdir()
        docker = self.bin/'docker'
        docker.write_text('#!'+sys.executable+'\n'+STUB)
        docker.chmod(0o700)
        self.log = self.root/'calls.jsonl'
        self.env = {**os.environ, 'PATH': str(self.bin)+os.pathsep+os.defpath,
                    'STUB_LOG': str(self.log)}
        for name in ('FAIL_STAGE', 'EMPTY_DUMP', 'SQL_IDENTITY', 'EXISTING_STAGE'):
            self.env.pop(name, None)

    def run_script(self, name, *args, **extra):
        return subprocess.run(['bash', str(HERE/name), *map(str, args)], env={**self.env, **extra},
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)

    def backup(self, **extra):
        return self.run_script('backup-db.sh', self.instance, self.backups, **extra)

    def accepted_set(self):
        result = self.backup()
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(result.stdout.strip())

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def clear_calls(self):
        self.log.unlink(missing_ok=True)

    def restore(self, backup_set, **extra):
        return self.run_script('restore-db.sh', self.instance, backup_set,
                               'handbook-sonar-restore-test', '19001', **extra)

    def test_accepted_backups_are_unique_and_checksum_the_complete_new_file(self):
        first, second = self.accepted_set(), self.accepted_set()
        self.assertNotEqual(first, second)
        self.assertEqual(first.parent, self.backups)
        for directory in (first, second):
            self.assertEqual((directory/'COMPLETE').read_text().strip(), 'handbook-sonar-db-backup-v1')
            data = (directory/'sonar.dump').read_bytes()
            self.assertEqual((directory/'SHA256SUMS').read_text(),
                             hashlib.sha256(data).hexdigest()+'  sonar.dump\n')
            self.assertFalse(list(directory.glob('*.partial')))
            self.assertTrue((directory/'sonar.dump.list').is_file())

    def test_failed_or_empty_dump_cannot_replace_a_previous_accepted_backup(self):
        previous = self.accepted_set()
        original = {path.name: path.read_bytes() for path in previous.iterdir()}
        for condition in ({'FAIL_STAGE': 'dump'}, {'EMPTY_DUMP': 'yes'}):
            with self.subTest(condition=condition):
                self.clear_calls()
                result = self.backup(**condition)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '', 'no accepted path published')
                self.assertEqual(list(self.backups.iterdir()), [previous])
                self.assertEqual({path.name: path.read_bytes() for path in previous.iterdir()}, original)
                self.assertEqual([entry['stage'] for entry in self.calls()], ['dump'])

    def test_failed_toc_does_not_publish_a_backup_or_damage_previous_set(self):
        previous = self.accepted_set()
        original = (previous/'sonar.dump').read_bytes()
        self.clear_calls()
        result = self.backup(FAIL_STAGE='list')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertEqual(list(self.backups.iterdir()), [previous])
        self.assertEqual((previous/'sonar.dump').read_bytes(), original)
        self.assertEqual([entry['stage'] for entry in self.calls()], ['dump', 'list'])

    def test_restore_waits_for_ready_and_sql_before_transaction_and_start(self):
        backup_set = self.accepted_set(); self.clear_calls()
        result = self.restore(backup_set)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual([entry['stage'] for entry in calls],
                         ['containers', 'volumes', 'ready', 'sql', 'restore', 'start'])
        ready = calls[2]['args']
        self.assertIn('--wait', ready); self.assertIn('--wait-timeout', ready)
        self.assertEqual(ready[ready.index('--wait-timeout')+1], '180')
        sql = ' '.join(calls[3]['args'])
        self.assertIn('-h 127.0.0.1', sql); self.assertIn('ON_ERROR_STOP=1', sql)
        self.assertIn("table_schema='public'", sql)
        restore = ' '.join(calls[4]['args'])
        self.assertIn('--single-transaction', restore); self.assertIn('--exit-on-error', restore)
        self.assertNotIn('--clean', restore); self.assertNotIn('--create', restore)
        self.assertEqual(calls[4]['stdin_sha'], hashlib.sha256((backup_set/'sonar.dump').read_bytes()).hexdigest())
        self.assertTrue(all(entry['port'] == '19001' for entry in calls))
        self.assertIn('Complete application acceptance next', result.stdout)

    def test_any_failed_restore_stage_stops_the_whole_script(self):
        backup_set = self.accepted_set()
        stages = ['containers', 'volumes', 'ready', 'sql', 'restore', 'start']
        for failed in ('ready', 'sql', 'restore', 'start'):
            with self.subTest(stage=failed):
                self.clear_calls()
                result = self.restore(backup_set, FAIL_STAGE=failed)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual([entry['stage'] for entry in self.calls()], stages[:stages.index(failed)+1])
                self.assertNotIn('Database restored;', result.stdout)

    def test_wrong_sql_identity_or_nonempty_target_prevents_restore_and_start(self):
        backup_set = self.accepted_set()
        for identity in ('postgres|sonar|0', 'sonar|other|0', 'sonar|sonar|3'):
            with self.subTest(identity=identity):
                self.clear_calls()
                result = self.restore(backup_set, SQL_IDENTITY=identity)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.calls()[-1]['stage'], 'sql')
                self.assertNotIn('restore', [entry['stage'] for entry in self.calls()])

    def test_existing_resources_and_unaccepted_or_corrupt_backup_are_rejected(self):
        backup_set = self.accepted_set()
        for stage in ('volumes', 'containers'):
            with self.subTest(stage=stage):
                self.clear_calls()
                result = self.restore(backup_set, EXISTING_STAGE=stage)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('ready', [entry['stage'] for entry in self.calls()])
        (backup_set/'sonar.dump').write_bytes(b'TAMPERED')
        self.clear_calls()
        self.assertNotEqual(self.restore(backup_set).returncode, 0)
        self.assertEqual(self.calls(), [], 'checksum failure before Docker')
        (backup_set/'COMPLETE').unlink()
        self.assertNotEqual(self.restore(backup_set).returncode, 0)
        self.assertEqual(self.calls(), [])


if __name__ == '__main__':
    unittest.main()
