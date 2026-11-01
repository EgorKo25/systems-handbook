#!/usr/bin/env python3
"""Local Go + report + artifact checks. No claim of live GitLab validation."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
GO = os.environ.get('HANDBOOK_GO') or shutil.which('go')
if not GO:
    raise SystemExit('Needs prepared Go in PATH or HANDBOOK_GO. Nothing was installed.')


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


CI = module(HERE/'service/tools/ci.py', 'gitlab_lab_ci')
POLICY = module(HERE/'policy.py', 'gitlab_lab_policy')


class GitLabTeachingChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='handbook-gitlab-check-')
        cls.root = Path(cls.temp.name)
        cls.env = dict(os.environ, HANDBOOK_GO=GO, GOENV='off', GOTOOLCHAIN='local',
                       GOWORK='off', GOPROXY='off', GOTELEMETRY='off', GOMAXPROCS='2',
                       GOCACHE=str(cls.root/'cache'), GOPATH=str(cls.root/'gopath'),
                       GOMODCACHE=str(cls.root/'modules'), CI_COMMIT_SHA='a'*40)
        cls.project = cls.root/'service'
        shutil.copytree(HERE/'service', cls.project,
                        ignore=shutil.ignore_patterns('__pycache__', 'dist', 'reports', '.cache'))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def step(self, action, check=True, *args):
        result = subprocess.run(['python3', 'tools/ci.py', action, *args], cwd=self.project,
                                env=self.env, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout)
        return result

    def test_01_real_go_tests_and_reports(self):
        self.step('test')
        report = ET.parse(self.project/'reports/junit.xml')
        self.assertGreaterEqual(len(report.findall('.//testcase')), 6)
        self.assertEqual(report.findall('.//failure'), [])
        self.assertEqual(report.findall('.//error'), [])

    def test_02_real_go_failure_preserves_nonzero_and_report(self):
        path = self.project/'cmd/echo/main_test.go'
        original = path.read_text()
        try:
            path.write_text(original.replace('"ready\\n"', '"intentionally wrong\\n"'))
            result = self.step('test', False)
            self.assertNotEqual(result.returncode, 0)
            self.assertGreaterEqual(len(ET.parse(self.project/'reports/junit.xml').findall('.//failure')), 1)
        finally:
            path.write_text(original)

    def test_03_binary_manifest_and_same_file_verification(self):
        self.step('build')
        manifest = json.loads((self.project/'dist/manifest.json').read_text())
        binary = self.project/'dist'/manifest['file']
        self.assertEqual(manifest['source_revision'], 'a'*40)
        self.assertEqual(manifest['bytes'], binary.stat().st_size)
        self.assertEqual(manifest['sha256'], hashlib.sha256(binary.read_bytes()).hexdigest())
        self.step('verify')

    def test_04_tamper_rejected_before_execution(self):
        self.step('build')
        manifest = json.loads((self.project/'dist/manifest.json').read_text())
        binary = self.project/'dist'/manifest['file']
        original = binary.read_bytes()
        try:
            binary.write_bytes(original+b'changed')
            result = self.step('verify', False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('not executed', result.stdout)
        finally:
            binary.write_bytes(original)

    def test_05_version_is_linked_and_recorded(self):
        self.step('build', True, '--version', '2.3.4-lab')
        manifest = json.loads((self.project/'dist/manifest.json').read_text())
        self.assertEqual(manifest['version'], '2.3.4-lab')
        self.step('verify')

    def test_06_invalid_version_does_not_enter_tool_arguments(self):
        result = self.step('build', False, '--version', 'bad version; command')
        self.assertNotEqual(result.returncode, 0)

    def test_07_non_json_and_incomplete_stream_have_errors(self):
        for output, code in [('compiler failed\n', 1),
                             ('', 0),
                             (json.dumps(dict(Action='run', Package='p', Test='T'))+'\n', 1),
                             (json.dumps(dict(Action='start', Package='p'))+'\n', 0)]:
            with self.subTest(output=output):
                report = ET.fromstring(CI.junit_from_go(output, code))
                self.assertGreaterEqual(len(report.findall('.//error')), 1)

    def test_08_package_failure_without_named_test(self):
        report = ET.fromstring(CI.junit_from_go(json.dumps(dict(Action='fail', Package='p')), 1))
        self.assertIsNotNone(report.find('.//error'))

    def test_09_skip_and_xml_escaping(self):
        events = [dict(Action='run', Package='p&x', Test='T<1>'),
                  dict(Action='skip', Package='p&x', Test='T<1>', Elapsed=0.1)]
        report = ET.fromstring(CI.junit_from_go('\n'.join(map(json.dumps, events)), 0))
        self.assertEqual(report.find('.//testcase').get('name'), 'T<1>')
        self.assertIsNotNone(report.find('.//skipped'))

    def test_10_workflow_truth_table(self):
        for source, branch, opened, tag, expected in [
            ('push', 'topic', False, None, True),
            ('push', 'topic', True, None, False),
            ('merge_request_event', None, True, None, True),
            ('push', None, False, 'v1.0.0', True),
            ('web', 'main', False, None, True),
            ('schedule', 'main', False, None, False),
            ('pipeline', 'topic', True, None, False),
        ]:
            with self.subTest(source=source, branch=branch):
                self.assertEqual(POLICY.pipeline_allowed(source, branch, opened, tag), expected)

    def test_11_release_case(self):
        self.assertEqual(POLICY.release_job('push', 'v1.0.0'), 'automatic')
        self.assertEqual(POLICY.release_job('web'), 'manual-blocking')
        self.assertEqual(POLICY.release_job('merge_request_event'), 'absent')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GitLabTeachingChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
