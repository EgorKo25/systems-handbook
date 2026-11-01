"""Control-plane tests with qemu-img stub. These do NOT boot or validate a VM."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("personal_world", Path(__file__).resolve().parents[1] / "vm/world.py")
world = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(world)


class WorldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="personal-world-control-test-")
        self.base = Path(self.temp.name)
        self.root = self.base / "world with space,comma"
        self.config = self.base / "config.json"
        self.config.write_text(world.DEFAULT.read_text(), encoding="utf-8")
        self.patches = [patch.object(world, "tool", lambda name, required=True: name),
                        patch.object(world, "call", self.stub_qemu_img)]
        for item in self.patches:
            item.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(lambda: [item.stop() for item in reversed(self.patches)])

    def stub_qemu_img(self, argv, capture=False):
        self.assertEqual(argv[0], "qemu-img", "Tests must never execute a VM")
        command = argv[1]
        if command == "create":
            Path(argv[-2]).write_bytes(b"UNIT TEST DISK: not qcow2\n")
        elif command == "convert":
            shutil.copyfile(argv[-2], argv[-1])
        elif command == "info":
            self.assertTrue(Path(argv[-1]).is_file())
            return json.dumps({"format": "qcow2", "virtual-size": 20 * 1024**3})
        else:
            self.fail("Unexpected mocked command: " + repr(argv))
        return 0

    def run_world(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(world.main(["--root", str(self.root), *map(str, args)]), 0)
        return output.getvalue()

    def create(self):
        self.run_world("create", "--config", self.config)
        return self.root / "disks/initial.qcow2"

    def test_create_never_overwrites(self):
        disk = self.create()
        disk.write_bytes(b"important exercise state")
        with self.assertRaises(world.LabError):
            self.run_world("create", "--config", self.config)
        self.assertEqual(disk.read_bytes(), b"important exercise state")

    def test_checkpoint_requires_shutdown_confirmation(self):
        self.create()
        with self.assertRaises(world.LabError):
            self.run_world("checkpoint", "first")
        self.assertFalse((self.root / "checkpoints").exists())

    def test_restore_forks_without_deleting_progress(self):
        disk = self.create()
        initial = disk.read_bytes()
        self.run_world("checkpoint", "first", "--guest-stopped")
        disk.write_bytes(b"later progress")
        self.run_world("restore", "first", "--guest-stopped", "--confirm", "first")
        data = world.state(self.root)
        self.assertEqual((self.root / data["active_disk"]).read_bytes(), initial)
        self.assertEqual(disk.read_bytes(), b"later progress")

    def test_bad_restore_hash_preserves_active_state(self):
        self.create()
        self.run_world("checkpoint", "first", "--guest-stopped")
        before = (self.root / "world.json").read_bytes()
        (self.root / "checkpoints/first/disk.qcow2").write_bytes(b"corrupted")
        with self.assertRaises(world.LabError):
            self.run_world("restore", "first", "--guest-stopped", "--confirm", "first")
        self.assertEqual((self.root / "world.json").read_bytes(), before)

    def test_lock_blocks_second_mutator(self):
        self.create()
        (self.root / "world.lock").write_text("occupied", encoding="utf-8")
        with self.assertRaises(world.LabError):
            self.run_world("checkpoint", "blocked", "--guest-stopped")
        self.assertEqual((self.root / "world.lock").read_text(), "occupied")

    def test_checkpoint_name_and_path_traversal_rejected(self):
        self.create()
        with self.assertRaises(world.LabError):
            self.run_world("checkpoint", "../../outside", "--guest-stopped")
        for value in ("../outside", "/tmp/outside", "."):
            with self.assertRaises(world.LabError):
                world.contained(self.root, value)

    def test_export_and_verify_cold_bundle(self):
        disk = self.create()
        destination = self.base / "trip export"
        self.run_world("export", destination, "--guest-stopped")
        self.assertEqual((destination / "disks/initial.qcow2").read_bytes(), disk.read_bytes())
        with contextlib.redirect_stdout(io.StringIO()):
            world.main(["--root", str(destination), "verify"])
        with self.assertRaises(world.LabError):
            self.run_world("export", destination, "--guest-stopped")
        (destination / "disks/initial.qcow2").write_bytes(b"changed")
        with self.assertRaises(world.LabError):
            world.main(["--root", str(destination), "verify"])

    def test_dry_run_readonly_loopback_and_comma_escaping(self):
        self.create()
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = json.loads(self.run_world("start", "--dry-run", "--accel", "tcg"))
        command = result["argv"]
        net = command[command.index("-netdev") + 1]
        self.assertIn("restrict=on", net)
        self.assertIn("hostfwd=tcp:127.0.0.1:2222-:22", net)
        self.assertNotIn("-snapshot", command)
        self.assertNotIn("-virtfs", command)
        self.assertNotIn("tap", net)
        self.assertIn("space,,comma", command[command.index("-drive") + 1])
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_network_opt_in_changes_only_backend_mode(self):
        self.create()
        result = json.loads(self.run_world("start", "--dry-run", "--accel", "tcg", "--allow-network"))
        self.assertIn("restrict=off", result["argv"][result["argv"].index("-netdev") + 1])
        self.assertEqual(result["network"], "outbound-enabled")

    def test_window_console_is_available_after_install_without_network_change(self):
        self.create()
        serial = json.loads(self.run_world("start", "--dry-run", "--accel", "tcg"))
        window = json.loads(self.run_world("start", "--dry-run", "--accel", "tcg", "--console", "window"))
        self.assertEqual(serial["console"], "serial")
        self.assertEqual(window["console"], "window")
        self.assertIn("-nographic", serial["argv"])
        self.assertNotIn("-nographic", window["argv"])
        self.assertEqual([item for item in serial["argv"] if item != "-nographic"], window["argv"])

    def test_installer_always_uses_window(self):
        self.create()
        iso = self.base / "test-not-a-real.iso"
        iso.write_bytes(b"Unit test placeholder, not bootable")
        result = json.loads(self.run_world("start", "--dry-run", "--accel", "tcg",
                                         "--console", "serial", "--installer", iso))
        self.assertEqual(result["console"], "window")
        self.assertEqual(result["guest_memory_mib"], 2048)
        self.assertNotIn("-nographic", result["argv"])
        self.assertEqual(result["argv"][result["argv"].index("-cdrom") + 1], str(iso))

    def test_relocated_export_has_no_dependency_on_original_disk_path(self):
        self.create()
        destination = self.base / "trip export"
        self.run_world("export", destination, "--guest-stopped")
        moved = self.base / "other computer" / "moved world"
        moved.parent.mkdir()
        shutil.move(destination, moved)
        with contextlib.redirect_stdout(io.StringIO()):
            world.main(["--root", str(moved), "verify"])
        with contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()):
            world.main(["--root", str(moved), "start", "--dry-run", "--accel", "tcg"])
        command = json.loads(output.getvalue())["argv"]
        drive = command[command.index("-drive") + 1]
        self.assertIn(str(moved / "disks/initial.qcow2"), drive)
        self.assertNotIn(str(self.root), drive)
        self.assertFalse(Path(world.state(moved)["active_disk"]).is_absolute())

    def test_checkpoint_refreshes_active_branch_after_lock(self):
        self.create()
        branch = self.root / "disks/other.qcow2"
        branch.write_bytes(b"Latest active branch selected by another completed controller")
        original_lock = world.locked
        @contextlib.contextmanager
        def intervening_lock(root):
            with original_lock(root):
                data = world.state(root)
                data["active_disk"] = "disks/other.qcow2"
                world.write_json(root / "world.json", data)
                yield
        with patch.object(world, "locked", intervening_lock):
            self.run_world("checkpoint", "latest", "--guest-stopped")
        self.assertEqual((self.root / "checkpoints/latest/disk.qcow2").read_bytes(), branch.read_bytes())

    def test_reject_invalid_profile(self):
        config = json.loads(self.config.read_text())
        for key, value in (("machine", "host"), ("cpu", "host"), ("vcpus", True), ("memory_mib", 100000),
                           ("ssh_port", 22), ("network_default", "public")):
            with self.subTest(key=key):
                with self.assertRaises(world.LabError):
                    world.valid_config(dict(config, **{key: value}))

    def test_interrupt_wait_keeps_lock_until_child_exits(self):
        from unittest.mock import Mock
        child = Mock()
        count = [0]
        def wait():
            self.assertTrue((self.root / "world.lock").exists())
            count[0] += 1
            if count[0] == 1:
                raise KeyboardInterrupt
            return 0
        child.wait.side_effect = wait
        with world.locked(self.root):
            with patch.object(world.subprocess, "Popen", return_value=child), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(world.run_vm(["not-a-real-vm"]), 0)
            self.assertTrue((self.root / "world.lock").exists())
        self.assertFalse((self.root / "world.lock").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
