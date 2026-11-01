"""Real own-file POSIX observations; never an existing reader directory."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('os_native', Path(__file__).resolve().parents[1] / 'labs/memory-io/native.py')
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='os-memory-io-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'owned'
        lab.prepare(self.root)

    def test_repeated_prepare_refuses_without_reset(self):
        lab.advance(self.root)
        before = (self.root / 'counter.bin').read_bytes()
        with self.assertRaises(ValueError):
            lab.prepare(self.root)
        self.assertEqual((self.root / 'counter.bin').read_bytes(), before)

    def test_continue_and_preserve_previous_versions(self):
        self.assertEqual(lab.status(self.root)['value'], 42)
        self.assertEqual(lab.advance(self.root)['value'], 43)
        self.assertEqual(lab.advance(self.root)['value'], 44)
        self.assertEqual((self.root / 'history/before-42.bin').read_bytes(), b'\x2a\0\0\0')
        self.assertEqual((self.root / 'history/before-43.bin').read_bytes(), b'\x2b\0\0\0')

    def test_duplicate_offsets_and_unlinked_open_file(self):
        observed = lab.descriptors(self.root)
        self.assertEqual(observed['read_first'], '2a 00')
        self.assertEqual(observed['read_duplicate'], '00 00')
        self.assertEqual(observed['read_independent'], '2a 00')
        self.assertEqual(observed['shared_offset'], 4)
        self.assertEqual(observed['offset_after_pwrite'], 4)
        self.assertEqual(observed['read_after_unlink'], '2b 00 00 00')
        self.assertEqual(lab.status(self.root)['value'], 42)

    def test_zero_length_positioned_write_keeps_file_size_and_position(self):
        fd = os.open(self.root / 'counter.bin', os.O_RDWR)
        try:
            os.lseek(fd, 4, os.SEEK_SET)
            self.assertEqual(os.pwrite(fd, b'', 10), 0)
            self.assertEqual(os.fstat(fd).st_size, 4)
            self.assertEqual(os.lseek(fd, 0, os.SEEK_CUR), 4)
            self.assertEqual(os.pread(fd, 4, 0), b'\x2a\0\0\0')
        finally:
            os.close(fd)

    def test_bad_format_and_unowned_root_refuse(self):
        (self.root / 'counter.bin').write_bytes(b'bad')
        with self.assertRaises(ValueError):
            lab.advance(self.root)
        with self.assertRaises(ValueError):
            lab.status(Path(self.temp.name))

    def test_symlink_counter_is_never_followed(self):
        target = Path(self.temp.name) / 'unrelated.bin'
        target.write_bytes(b'untouched')
        (self.root / 'counter.bin').unlink()
        (self.root / 'counter.bin').symlink_to(target)
        with self.assertRaises(ValueError):
            lab.advance(self.root)
        self.assertEqual(target.read_bytes(), b'untouched')

    def test_real_cli_continues_same_directory_and_prepare_is_not_reset(self):
        script = Path(lab.__file__)
        def command(action):
            return subprocess.run([sys.executable, str(script), action, '--root', str(self.root)], capture_output=True, text=True)
        first = command('advance')
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)['value'], 43)
        again = command('prepare')
        self.assertNotEqual(again.returncode, 0)
        self.assertIn('No reset attempted', again.stderr)
        self.assertEqual(json.loads(command('status').stdout)['value'], 43)

    def test_competing_writer_lock_refuses_before_mutation(self):
        lock = os.open(self.root / 'writer.lock', os.O_CREAT | os.O_RDWR, 0o600)
        try:
            lab.fcntl.flock(lock, lab.fcntl.LOCK_EX | lab.fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                lab.advance(self.root)
            self.assertEqual(lab.status(self.root)['value'], 42)
            self.assertEqual(lab.status(self.root)['history_files'], 0)
        finally:
            os.close(lock)

    def test_late_diagnostic_failure_keeps_already_replaced_counter(self):
        target = Path(self.temp.name) / 'unrelated-journal'
        target.write_bytes(b'untouched')
        (self.root / 'observations.jsonl').symlink_to(target)
        with self.assertRaises(ValueError):
            lab.advance(self.root)
        self.assertEqual(lab.status(self.root)['value'], 43)
        self.assertEqual((self.root / 'history/before-42.bin').read_bytes(), b'\x2a\0\0\0')
        self.assertEqual(target.read_bytes(), b'untouched')


if __name__ == '__main__':
    unittest.main()
