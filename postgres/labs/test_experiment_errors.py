#!/usr/bin/env python3
"""Failed-experiment diagnostics: own TEMP and mocks, never PostgreSQL.

Run beside postgres-lab.py: python3 -I -B test_experiment_errors.py
The real helper is imported, but its constructor/start/SQL are not called.
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
SPEC = importlib.util.spec_from_file_location('pgbook_failed_result_target', HERE/'postgres-lab.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExperimentErrorChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='pgbook-result-model-')
        self.owner = Path(self.temporary.name)
        self.lab = MODULE.Lab.__new__(MODULE.Lab)
        self.lab.root = self.owner/'world'
        self.lab.root.mkdir()
        self.lab.data = self.lab.root/'data'
        self.lab.data.mkdir()
        (self.lab.data/'marker').write_bytes(b'own-not-postgresql\x00\xff')
        self.lab.bin = self.owner/'nonexistent-bin'
        self.lab.started = [self.lab.data]
        self.lab.keep = False
        self.lab.results = []
        self.lab.init = lambda: None
        self.calls = []
        def command(name, *args, **kwargs):
            self.assertEqual(name, 'pg_ctl')
            self.assertEqual(args, ('-D', self.lab.data, '-m', 'fast', '-w', '-t', '20', 'stop'))
            self.assertEqual(kwargs, {'timeout': 25})
            self.calls.append((name, args))
            return subprocess.CompletedProcess([name], 0, '', '')
        self.lab.command = command

    def tearDown(self):
        self.temporary.cleanup()  # Only this test's own model files.

    def raising(self, exception):
        def function():
            raise exception
        return function

    def run_main(self, function):
        output, errors = io.StringIO(), io.StringIO()
        def experiments(lab):
            lab.experiment(1, 'own failure case', function)
        args = ['postgres-lab.py', '--run', '--pg-bin', str(self.lab.bin)]
        with patch.object(MODULE, 'Lab', return_value=self.lab), \
             patch.object(MODULE, 'experiments', side_effect=experiments), \
             patch.object(MODULE.os, 'geteuid', return_value=1000), \
             patch.object(sys, 'argv', args), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                result, raised = MODULE.main(), None
            except BaseException as exc:
                result, raised = None, exc
        return result, raised, output.getvalue(), errors.getvalue()

    def assert_retained_no_success(self, output):
        self.assertTrue(self.lab.keep)
        self.assertEqual(self.lab.started, [])
        self.assertEqual((self.lab.data/'marker').read_bytes(), b'own-not-postgresql\x00\xff')
        self.assertNotIn('OK:', output)
        self.assertNotIn('01 PASS', output)
        self.assertEqual(len(self.calls), 1)

    def test_direct_original_exception_identity_survives_writer_error(self):
        primary, errors = ValueError('PRIMARY CAUSE'), io.StringIO()
        with patch.object(self.lab, 'write_results', side_effect=OSError('REPORT ERROR')) as writer, \
             contextlib.redirect_stderr(errors), self.assertRaises(ValueError) as caught:
            self.lab.experiment(1, 'own failure case', self.raising(primary))
        self.assertIs(caught.exception, primary)
        self.assertEqual(writer.call_count, 1)
        text = errors.getvalue()
        self.assertIn('ValueError: PRIMARY CAUSE', text)
        self.assertIn('Cannot save failed experiment result: OSError: REPORT ERROR', text)
        self.assertLess(text.index('PRIMARY CAUSE'), text.index('REPORT ERROR'))
        self.assertEqual(self.lab.results[0]['error'], 'PRIMARY CAUSE')

    def test_main_valueerror_and_writer_failure(self):
        with patch.object(self.lab, 'write_results', side_effect=OSError('REPORT ERROR')) as writer:
            code, raised, out, err = self.run_main(self.raising(ValueError('PRIMARY CAUSE')))
        self.assertEqual((code, raised), (1, None))
        self.assertIn('ValueError: PRIMARY CAUSE', err)
        self.assertIn('FAIL: PRIMARY CAUSE', err)
        self.assertIn('Cannot save failed experiment result: OSError: REPORT ERROR', err)
        self.assertIn('Cannot save results', err)  # Final cleanup really retries.
        self.assertEqual(writer.call_count, 2)
        self.assert_retained_no_success(out)

    def test_successful_writer_retains_original_failure_and_report(self):
        code, raised, out, err = self.run_main(self.raising(ValueError('PRIMARY CAUSE')))
        self.assertEqual((code, raised), (1, None))
        self.assertIn('ValueError: PRIMARY CAUSE', err)
        self.assertNotIn('Cannot save', err)
        saved = json.loads((self.lab.root/'results.json').read_text())
        self.assertEqual(len(saved), 1)
        self.assertEqual((saved[0]['status'], saved[0]['error']), ('FAIL', 'PRIMARY CAUSE'))
        self.assert_retained_no_success(out)

    def test_first_write_failure_then_cleanup_can_write_primary_report(self):
        real_write = self.lab.write_results
        calls = []
        def write():
            calls.append(True)
            if len(calls) == 1:
                raise OSError('FIRST REPORT ERROR')
            real_write()
        with patch.object(self.lab, 'write_results', side_effect=write):
            code, raised, out, err = self.run_main(self.raising(ValueError('PRIMARY CAUSE')))
        self.assertEqual((code, raised), (1, None))
        self.assertIn('Cannot save failed experiment result: OSError: FIRST REPORT ERROR', err)
        self.assertNotIn('Cannot save results;', err)
        self.assertEqual(json.loads((self.lab.root/'results.json').read_text())[0]['error'], 'PRIMARY CAUSE')
        self.assertEqual(len(calls), 2)
        self.assert_retained_no_success(out)

    def test_interrupt_and_writer_failure_stay_visible_and_propagate(self):
        primary = KeyboardInterrupt('PRIMARY INTERRUPT')
        with patch.object(self.lab, 'write_results', side_effect=OSError('REPORT ERROR')):
            code, raised, out, err = self.run_main(self.raising(primary))
        self.assertIsNone(code)
        self.assertIs(raised, primary)
        self.assertIn('KeyboardInterrupt: PRIMARY INTERRUPT', err)
        self.assertIn('Cannot save failed experiment result: OSError: REPORT ERROR', err)
        self.assert_retained_no_success(out)

    def test_empty_interrupt_is_identifiable_even_without_message(self):
        primary = KeyboardInterrupt()
        with patch.object(self.lab, 'write_results', side_effect=OSError('REPORT ERROR')):
            code, raised, out, err = self.run_main(self.raising(primary))
        self.assertIsNone(code)
        self.assertIs(raised, primary)
        self.assertIn('KeyboardInterrupt:', err)
        self.assertIn('REPORT ERROR', err)
        self.assert_retained_no_success(out)

    def test_interrupt_with_successful_writer_stores_fail_and_propagates(self):
        primary = KeyboardInterrupt('PRIMARY INTERRUPT')
        code, raised, out, err = self.run_main(self.raising(primary))
        self.assertIsNone(code)
        self.assertIs(raised, primary)
        self.assertIn('KeyboardInterrupt: PRIMARY INTERRUPT', err)
        self.assertNotIn('Cannot save', err)
        self.assertEqual(json.loads((self.lab.root/'results.json').read_text())[0]['error'], 'PRIMARY INTERRUPT')
        self.assert_retained_no_success(out)

    def test_interrupted_report_does_not_replace_already_reported_primary(self):
        primary, errors = ValueError('PRIMARY CAUSE'), io.StringIO()
        with patch.object(self.lab, 'write_results', side_effect=KeyboardInterrupt('REPORT INTERRUPT')), \
             contextlib.redirect_stderr(errors), self.assertRaises(ValueError) as caught:
            self.lab.experiment(1, 'own failure case', self.raising(primary))
        self.assertIs(caught.exception, primary)
        self.assertIn('ValueError: PRIMARY CAUSE', errors.getvalue())
        self.assertIn('KeyboardInterrupt: REPORT INTERRUPT', errors.getvalue())

    def test_successful_experiment_still_writes_and_prints_pass(self):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.lab.experiment(1, 'own success case', lambda: {'value': 42})
        self.assertEqual(errors.getvalue(), '')
        self.assertIn('01 PASS own success case', output.getvalue())
        saved = json.loads((self.lab.root/'results.json').read_text())
        self.assertEqual((saved[0]['status'], saved[0]['detail']), ('PASS', {'value': 42}))

    def test_successful_experiment_writer_error_is_not_fabricated_function_failure(self):
        with patch.object(self.lab, 'write_results', side_effect=OSError('REPORT ERROR')):
            code, raised, out, err = self.run_main(lambda: {'value': 42})
        self.assertEqual((code, raised), (1, None))
        self.assertIn('FAIL: REPORT ERROR', err)
        self.assertNotIn('EXPERIMENT FAILED:', err)
        self.assertNotIn('Cannot save failed experiment result:', err)
        self.assertEqual(self.lab.results[0]['status'], 'PASS')
        self.assert_retained_no_success(out)


if __name__ == '__main__':
    unittest.main(verbosity=2)
