"""Only own TEMP files/child processes. No services or production data."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('os_execution_native', BASE/'labs/execution/native.py')
N = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(N)


class NativeExecution(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='os-execution-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)/'practice'

    def test_retained_counter_42_43_44_and_explicit_zero_offset(self):
        N.initialize(str(self.directory))
        first = N.increment(str(self.directory))
        self.assertEqual((first['before'],first['after']), (42,43))
        self.assertEqual(first['before_hex'],'2a000000')
        self.assertEqual(first['after_hex'],'2b000000')
        self.assertEqual(first['position_after_read'],4)
        self.assertEqual(first['explicit_rewrite_offset'],0)
        self.assertEqual(first['position_after_write'],4)
        self.assertEqual(first['file_size_after'],4)
        second = N.increment(str(self.directory))
        self.assertEqual((second['before'],second['after']),(43,44))
        self.assertEqual(N.show(str(self.directory))['value'],44)

    def test_init_does_not_reset_previous_counter_or_foreign_directory(self):
        N.initialize(str(self.directory));N.increment(str(self.directory))
        with self.assertRaises(ValueError):N.initialize(str(self.directory))
        self.assertEqual(N.show(str(self.directory))['value'],43)
        foreign = Path(self.temp.name)/'other';foreign.mkdir();(foreign/'keep').write_text('kept')
        with self.assertRaises(ValueError):N.initialize(str(foreign))
        self.assertEqual((foreign/'keep').read_text(),'kept')

    def test_invalid_size_marker_and_overflow_have_no_write(self):
        N.initialize(str(self.directory));p=self.directory/'counter.bin'
        for data in [b'',b'\x2a',b'12345678',b'\xff'*4]:
            p.write_bytes(data)
            with self.assertRaises(ValueError):N.increment(str(self.directory))
            self.assertEqual(p.read_bytes(),data)

    def test_invalid_marker_rejects_before_counter_write(self):
        N.initialize(str(self.directory));counter=self.directory/'counter.bin';marker=self.directory/N.MARKER
        for text in ['not JSON', json.dumps({'format':1,'lab':'different'})]:
            marker.write_text(text)
            with self.assertRaises(ValueError):N.increment(str(self.directory))
            self.assertEqual(counter.read_bytes(),bytes([42,0,0,0]))

    def test_short_write_control_flow_and_error_do_not_claim_rollback(self):
        calls=[]
        def short_write(fd,data):
            calls.append(bytes(data));return 1 if len(calls)==1 else len(data)
        with patch.object(N.os,'write',side_effect=short_write):
            self.assertEqual(N.write_all(999,b'abcd'),4)
        self.assertEqual(calls,[b'abcd',b'bcd'])
        with patch.object(N.os,'write',return_value=0):
            with self.assertRaises(OSError):N.write_all(999,b'abcd')
        # These two branches are syscall stubs, not claims about a real short device write.

    def test_error_after_real_write_can_leave_new_visible_bytes(self):
        N.initialize(str(self.directory))
        with patch.object(N.os,'fsync',side_effect=OSError('injected sync failure')):
            with self.assertRaises(OSError):N.increment(str(self.directory))
        self.assertEqual(N.show(str(self.directory))['value'],43)
        # Actual file write/read, injected fsync error; no power-loss or durability claim.

    def test_symlinks_and_relative_directory_are_rejected(self):
        with self.assertRaises(ValueError):N.initialize('relative')
        target=Path(self.temp.name)/'target';target.mkdir();link=Path(self.temp.name)/'link';link.symlink_to(target)
        with self.assertRaises(ValueError):N.initialize(str(link/'child'))
        N.initialize(str(self.directory));counter=self.directory/'counter.bin';counter.unlink();counter.symlink_to(target/'file')
        with self.assertRaises(ValueError):N.increment(str(self.directory))
        self.assertFalse((target/'file').exists())

    def test_own_child_gets_explicit_environment_and_parent_waits(self):
        N.initialize(str(self.directory));r=N.child(str(self.directory))
        self.assertEqual(r['child']['ppid'],r['parent_pid'])
        self.assertNotEqual(r['child']['pid'],r['parent_pid'])
        self.assertEqual(Path(r['child']['cwd']),self.directory)
        self.assertEqual(r['child']['marker'],'child')
        self.assertEqual(r['waited_exit_status'],7)

    def test_clock_interfaces_have_defined_nonnegative_units(self):
        N.initialize(str(self.directory));r=N.clocks(str(self.directory))
        for section in ['sleep','compute']:
            self.assertGreaterEqual(r[section]['wall_seconds'],0)
            self.assertGreaterEqual(r[section]['cpu_seconds'],0)
        self.assertGreater(r['sleep']['wall_seconds'],0)
        self.assertEqual(r['compute']['checksum'],333328333350000)
        # No fixed performance/latency upper bound: CI and scheduling vary.

    def test_shown_cli_control_flow_and_repeat_rejection(self):
        command=[sys.executable,str(BASE/'labs/execution/native.py'),'--directory',str(self.directory)]
        def invoke(action):return subprocess.run(command+[action],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
        init=invoke('init');self.assertEqual(init.returncode,0,init.stderr)
        first=invoke('increment');self.assertEqual(first.returncode,0,first.stderr)
        self.assertEqual(json.loads(first.stdout)['after'],43)
        again=invoke('init');self.assertEqual(again.returncode,2)
        shown=invoke('show');self.assertEqual(json.loads(shown.stdout)['value'],43)


if __name__ == '__main__':unittest.main()
