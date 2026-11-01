#!/usr/bin/env python3
"""Real Go report regressions; this does not run a SonarQube server."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = importlib.util.spec_from_file_location('sonar_reports', HERE/'prepare_reports.py')
REPORTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORTS)
GO = shutil.which(os.environ.get('HANDBOOK_GO', 'go'))


@unittest.skipUnless(GO, 'Set HANDBOOK_GO or prepare a local Go toolchain first')
class ReportsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)/'service'
        shutil.copytree(ROOT/'go/labs/service', self.project,
                        ignore=shutil.ignore_patterns('__pycache__', 'reports', '.git', 'bin', 'dist'))

    def test_real_native_reports_cover_current_application(self):
        self.assertEqual(REPORTS.prepare(self.project, GO), 0)
        reports = self.project/'reports'
        events = [json.loads(line) for line in (reports/'test.jsonl').read_text().splitlines()]
        self.assertTrue(any(e.get('Action') == 'pass' and e.get('Test') == 'TestHandler/long' for e in events))
        self.assertTrue(any(e.get('Action') == 'pass' and e.get('Test') == 'TestHandler/unicode' for e in events))
        profile = (reports/'coverage.out').read_text()
        self.assertTrue(profile.startswith('mode: atomic\n'))
        self.assertIn('/internal/httpapp/handler.go:', profile)
        self.assertNotIn('_test.go:', profile)
        manifest = json.loads((reports/'reports-manifest.json').read_text())
        self.assertEqual((manifest['test_exit'], manifest['vet_exit']), (0, 0))
        for name, entry in manifest['files'].items():
            data = (reports/name).read_bytes()
            self.assertEqual(entry, {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})

    def test_test_failure_is_not_hidden_by_a_successful_vet_or_old_report(self):
        reports = self.project/'reports'; reports.mkdir()
        (reports/'coverage.out').write_text('old coverage from a different source')
        (reports/'reports-manifest.json').write_text('{"test_exit":0}')
        source = self.project/'internal/httpapp/handler_test.go'
        with source.open('a') as output:
            output.write('\nfunc TestDeliberateFailure(t *testing.T) { t.Fatal("original negative fixture") }\n')
        self.assertEqual(REPORTS.prepare(self.project, GO), 1)
        manifest = json.loads((reports/'reports-manifest.json').read_text())
        self.assertNotEqual(manifest['test_exit'], 0)
        self.assertEqual(manifest['vet_exit'], 0)
        events = [json.loads(line) for line in (reports/'test.jsonl').read_text().splitlines()]
        self.assertTrue(any(e.get('Action') == 'fail' and e.get('Test') == 'TestDeliberateFailure' for e in events))
        self.assertNotIn('old coverage', (reports/'coverage.out').read_text())

    def test_inherited_goflags_cannot_silently_change_the_report_contract(self):
        with patch.dict(os.environ, {'GOFLAGS': '-an-option-that-does-not-exist', 'GOWORK': '/does/not/exist'}):
            self.assertEqual(REPORTS.prepare(self.project, GO), 0)
        manifest = json.loads((self.project/'reports/reports-manifest.json').read_text())
        self.assertIn('-covermode=atomic', manifest['argv'])
        self.assertIn('-count=1', manifest['argv'])

    def test_report_symlink_cannot_overwrite_a_different_file(self):
        external = Path(self.temp.name)/'must-stay'; external.write_text('keep')
        reports = self.project/'reports'; reports.mkdir()
        (reports/'test.jsonl').symlink_to(external)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            REPORTS.prepare(self.project, GO)
        self.assertEqual(external.read_text(), 'keep')

    def test_missing_module_is_rejected_before_running_go(self):
        with self.assertRaisesRegex(ValueError, 'go.mod'):
            REPORTS.prepare(Path(self.temp.name)/'missing', GO)


if __name__ == '__main__':
    unittest.main()
