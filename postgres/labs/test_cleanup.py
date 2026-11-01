#!/usr/bin/env python3
"""Cleanup control-flow regressions. Only fake pg_ctl and own temporary files.

Run beside postgres-lab.py: python3 -B test_cleanup.py
These tests do not start PostgreSQL or prove real server shutdown.
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('pgbook_cleanup_target', HERE/'postgres-lab.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CleanupChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='pgbook-cleanup-model-')
        self.owner = Path(self.temporary.name)
        self.bin = self.owner/'fake-bin'
        self.bin.mkdir()
        self.log = self.owner/'calls.txt'
        stub = self.bin/'pg_ctl'
        stub.write_text('''#!/bin/bash
set -eu
target=
while (( $# )); do
    case "$1" in
        -D) target=$2; shift 2 ;;
        *) shift ;;
    esac
done
printf '%s\\n' "$target" >>"$STUB_LOG"
case "$target" in
    */fail-data) printf 'fake shutdown refused\\n' >&2; exit 7 ;;
esac
exit 0
''')
        stub.chmod(0o700)

    def tearDown(self):
        self.temporary.cleanup()  # Only this test's own model files.

    def lab(self, names=('data',), keep=False):
        lab = MODULE.Lab.__new__(MODULE.Lab)
        lab.bin = self.bin
        lab.root = self.owner/('world-'+str(len(list(self.owner.glob('world-*')))))
        lab.root.mkdir(mode=0o700)
        lab.data = lab.root/names[0]
        lab.started = []
        for name in names:
            target = lab.root/name
            target.mkdir()
            (target/'keep.bin').write_bytes(b'42\x00\xff')
            lab.started.append(target)
        lab.results = [{'kind': 'model', 'not_a_live_server': True}]
        lab.keep = keep
        lab.env = {'PATH': '/usr/bin:/bin', 'STUB_LOG': str(self.log)}
        return lab

    def cleanup(self, lab):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            result = lab.cleanup()
        return result, output.getvalue()

    def run_main(self, lab, *, failure=None, keep=False):
        output, errors = io.StringIO(), io.StringIO()
        lab.init = lambda: None
        def experiments(unused):
            if failure:
                raise failure
        args = ['postgres-lab.py', '--run', '--pg-bin', str(self.bin)]
        if keep:
            args.append('--keep')
        with patch.object(MODULE, 'Lab', return_value=lab), \
             patch.object(MODULE, 'experiments', side_effect=experiments), \
             patch.object(MODULE.os, 'geteuid', return_value=1000), \
             patch.object(sys, 'argv', args), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = MODULE.main()
        return code, output.getvalue(), errors.getvalue()

    def test_failed_stop_never_deletes_root(self):
        lab = self.lab(('fail-data',))
        result, error = self.cleanup(lab)
        self.assertEqual((lab.data/'keep.bin').read_bytes(), b'42\x00\xff')
        self.assertFalse(result)
        self.assertTrue(lab.keep)
        self.assertEqual(lab.started, [lab.data])
        self.assertTrue((lab.root/'results.json').is_file())
        saved = json.loads((lab.root/'results.json').read_text())[-1]['cleanup']
        self.assertEqual(saved['unconfirmed_datadirs'], [str(lab.data)])
        self.assertIn('fake shutdown refused', saved['stop_errors'][0]['error'])
        self.assertIn('fake shutdown refused', error)
        self.assertIn(str(lab.root), error)
        self.assertEqual(self.log.read_text().splitlines(), [str(lab.data)])

    def test_other_owned_instances_still_get_stop_attempt(self):
        lab = self.lab(('fail-data', 'restore-data'))
        paths = list(lab.started)
        result, error = self.cleanup(lab)
        self.assertFalse(result)
        self.assertEqual(self.log.read_text().splitlines(), list(map(str, reversed(paths))))
        self.assertEqual(lab.started, [paths[0]])
        self.assertTrue(all((p/'keep.bin').exists() for p in paths))
        self.assertIn('Shutdown not confirmed', error)

    def test_all_success_delete_only_own_world(self):
        lab = self.lab()
        sentinel = self.owner/'outside-keep.txt'
        sentinel.write_text('untouched')
        result, error = self.cleanup(lab)
        self.assertTrue(result)
        self.assertFalse(lab.root.exists())
        self.assertEqual(lab.started, [])
        self.assertEqual(sentinel.read_text(), 'untouched')
        self.assertEqual(error, '')

    def test_keep_preserves_stopped_world_and_second_cleanup_does_not_stop_again(self):
        lab = self.lab(keep=True)
        self.assertTrue(self.cleanup(lab)[0])
        self.assertTrue(lab.root.exists())
        self.assertEqual(lab.started, [])
        first_log = self.log.read_bytes()
        self.assertTrue(self.cleanup(lab)[0])
        self.assertEqual(first_log, self.log.read_bytes())
        self.assertEqual(json.loads((lab.root/'results.json').read_text()), lab.results)

    def test_stop_timeout_retains_world(self):
        lab = self.lab()
        with patch.object(lab, 'command', side_effect=subprocess.TimeoutExpired('fake pg_ctl', 25)):
            result, error = self.cleanup(lab)
        self.assertFalse(result)
        self.assertEqual(lab.started, [lab.data])
        self.assertTrue((lab.data/'keep.bin').exists())
        self.assertIn('timed out', error)

    def test_missing_cli_retains_world(self):
        lab = self.lab()
        (self.bin/'pg_ctl').unlink()  # Only our fake file.
        result, error = self.cleanup(lab)
        self.assertFalse(result)
        self.assertTrue((lab.data/'keep.bin').exists())
        self.assertIn('STOP FAILED', error)

    def test_results_write_failure_retains_world_after_successful_stop(self):
        lab = self.lab()
        with patch.object(lab, 'write_results', side_effect=OSError('fake results failure')):
            result, error = self.cleanup(lab)
        self.assertFalse(result)
        self.assertEqual(lab.started, [])
        self.assertTrue((lab.data/'keep.bin').exists())
        self.assertIn('Cannot save results', error)

    def test_delete_failure_reports_failure(self):
        lab = self.lab()
        with patch.object(MODULE.shutil, 'rmtree', side_effect=OSError('fake deletion failure')):
            result, error = self.cleanup(lab)
        self.assertFalse(result)
        self.assertTrue(lab.keep)
        self.assertTrue(lab.root.exists())
        self.assertIn('Cannot finish cleanup', error)

    def test_main_failed_stop_returns_one_without_stopped_success_claim(self):
        lab = self.lab(('fail-data',))
        code, output, error = self.run_main(lab)
        self.assertEqual(code, 1)
        self.assertNotIn('OK:', output)
        self.assertNotIn('Stopped lab', output)
        self.assertIn('STOP FAILED', error)
        self.assertTrue((lab.data/'keep.bin').exists())

    def test_main_preserves_original_experiment_error_when_stop_also_fails(self):
        lab = self.lab(('fail-data',))
        code, output, error = self.run_main(lab, failure=ValueError('original experiment failure'))
        self.assertEqual(code, 1)
        self.assertIn('FAIL: original experiment failure', error)
        self.assertIn('STOP FAILED', error)
        self.assertTrue((lab.data/'keep.bin').exists())
        self.assertNotIn('OK:', output)

    def test_main_failed_experiment_preserves_stopped_world_without_keep_argument(self):
        lab = self.lab()
        code, output, error = self.run_main(lab, failure=ValueError('original experiment failure'))
        self.assertEqual(code, 1)
        self.assertEqual(lab.started, [])
        self.assertTrue((lab.data/'keep.bin').exists())
        self.assertIn('Evidence directory retained', error)
        self.assertNotIn('OK:', output)

    def test_main_success_reports_after_confirmed_shutdown(self):
        lab = self.lab(keep=True)
        code, output, error = self.run_main(lab, keep=True)
        self.assertEqual(code, 0)
        self.assertEqual(error, '')
        self.assertEqual(lab.started, [])
        self.assertTrue(lab.root.exists())
        self.assertIn('lab servers stopped', output)
        self.assertIn('Stopped lab and evidence retained', output)

    def test_keyboard_interrupt_is_not_converted_to_success_or_deletion(self):
        lab = self.lab()
        with self.assertRaises(KeyboardInterrupt):
            self.run_main(lab, failure=KeyboardInterrupt())
        self.assertTrue(lab.keep)
        self.assertEqual(lab.started, [])
        self.assertTrue((lab.data/'keep.bin').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
