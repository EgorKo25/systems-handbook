#!/usr/bin/env python3
"""Cold, persistent personal QEMU world. Standard library only; no downloads.

This is a preparation prototype. QEMU and the guest are separately supplied.
Own world files stay under --root (default labs-personal/runtime); export uses
an explicitly chosen new destination. Child apps and the OS may keep their own
cache/logs. No host mounts, TAP, installed daemons or global configuration edits.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
DEFAULT = HERE / "world.example.json"
NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}\Z")


class LabError(Exception):
    pass


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    temp = path.with_name(path.name + ".new")
    with temp.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tool(name, required=True):
    suffix = ".exe" if os.name == "nt" else ""
    local = LAB / "tools" / ("windows" if os.name == "nt" else "linux") / (name + suffix)
    found = str(local) if local.is_file() else shutil.which(name + suffix)
    if required and not found:
        raise LabError(f"Не найден {name}; ничего не скачано. См. vm/README.txt.")
    return found


def call(argv, capture=False):
    result = subprocess.run([str(x) for x in argv], check=False,
                            text=True, capture_output=capture)
    if result.returncode:
        raise LabError(f"Команда завершилась с кодом {result.returncode}: {argv[0]}\n"
                       + ((result.stderr or "") if capture else ""))
    return result.stdout if capture else result.returncode


def run_vm(argv):
    process = subprocess.Popen([str(value) for value in argv])
    while True:
        try:
            code = process.wait()
            break
        except KeyboardInterrupt:
            # Never release the world lock while its child may still write the disk.
            print("Ожидаю выхода QEMU; не извлекайте носитель. "
                  "Штатное выключение — sudo poweroff внутри гостя.", file=sys.stderr)
    if code:
        raise LabError(f"QEMU завершился с кодом {code}; корректность выключения не подтверждена.")
    return code


def valid_config(config):
    if type(config.get("schema")) is not int or config.get("schema") != 1 or config.get("architecture") != "x86_64":
        raise LabError("Ожидается manifest schema=1, architecture=x86_64.")
    for key, low, high in (("memory_mib", 512, 8192), ("vcpus", 1, 4),
                           ("disk_gib", 4, 128), ("ssh_port", 1024, 65535)):
        if type(config.get(key)) is not int or not low <= config[key] <= high:
            raise LabError(f"Неверное {key}: диапазон {low}..{high}.")
    if not re.fullmatch(r"pc-i440fx-\d+\.\d+", config.get("machine", "")):
        raise LabError("Нужен versioned machine, например pc-i440fx-8.2.")
    if config.get("cpu") != "qemu64" or config.get("network_default") != "isolated":
        raise LabError("Для первого переносимого профиля нужны qemu64 и isolated.")
    if not re.fullmatch(r"52:54:00:(?:[0-9a-fA-F]{2}:){2}[0-9a-fA-F]{2}", config.get("mac", "")):
        raise LabError("Неверный локальный MAC формата 52:54:00:xx:xx:xx.")
    if not NAME.fullmatch(config.get("name", "")):
        raise LabError("Имя мира: буквы/цифры, _ и -, до 48 символов.")
    return config


def contained(root, relative):
    target = (root / relative).resolve()
    if target == root or root not in target.parents:
        raise LabError("Путь должен оставаться внутри каталога мира.")
    return target


def state(root):
    path = root / "world.json"
    if not path.is_file():
        raise LabError("Мир ещё не создан: create или adopt-base; см. vm/README.txt.")
    data = load(path)
    valid_config(data["config"])
    contained(root, data["active_disk"])
    return data


@contextlib.contextmanager
def locked(root):
    root.mkdir(parents=True, exist_ok=True)
    path = root / "world.lock"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise LabError("Мир занят или осталась блокировка после сбоя. См. status; "
                       "не удаляйте lock, пока QEMU ещё работает.") from None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "host": platform.node(), "time": time.time()}, stream)
        yield
    finally:
        path.unlink(missing_ok=True)


def clean_assertion(args):
    if not args.guest_stopped:
        raise LabError("Сначала sudo poweroff внутри гостя, дождитесь выхода QEMU, "
                       "затем повторите с --guest-stopped. Это подтверждение "
                       "корректного выключения, а не способ выключить машину.")


def independent_info(image):
    info = json.loads(call([tool("qemu-img"), "info", "--output=json", image], capture=True))
    if info.get("format") != "qcow2" or info.get("backing-filename"):
        raise LabError("Нужен самостоятельный qcow2 без backing chain. "
                       "Сначала qemu-img convert -O qcow2 исходник новый.qcow2.")
    return info


def clone(source, dest):
    if dest.exists():
        raise LabError(f"Уже существует: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_name(dest.name + ".partial")
    if temp.exists():
        raise LabError(f"Остался частичный файл {temp}; проверьте его вручную.")
    # Explicit formats; qemu-img acquires its own image locks. Never use -U.
    call([tool("qemu-img"), "convert", "-f", "qcow2", "-O", "qcow2", source, temp])
    independent_info(temp)
    os.replace(temp, dest)


def available_mib():
    if sys.platform.startswith("linux"):
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    elif os.name == "nt":
        import ctypes
        class Memory(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (key, ctypes.c_ulonglong) for key in (
                    "totalPhys", "availPhys", "totalPage", "availPage",
                    "totalVirtual", "availVirtual", "availExtended")]
        report = Memory()
        report.length = ctypes.sizeof(Memory)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(report)):
            return report.availPhys // (1024 * 1024)
    return None


def qemu_args(root, data, args):
    config = data["config"]
    disk = contained(root, data["active_disk"])
    # QEMU comma syntax is separate from shell syntax; double embedded commas.
    escaped_disk = str(disk).replace(",", ",,")
    accel = args.accel
    if accel == "auto":
        accel = "kvm" if sys.platform.startswith("linux") and os.access("/dev/kvm", os.R_OK | os.W_OK) else "tcg"
    if os.name == "nt" and accel == "kvm":
        raise LabError("KVM доступен в Linux. На Windows этот профиль использует TCG.")
    memory = 2048 if args.installer else config["memory_mib"]
    network = ("user,id=management,restrict=" + ("off" if args.allow_network else "on")
               + f",ipv6=off,hostfwd=tcp:127.0.0.1:{config['ssh_port']}-:22")
    command = [tool("qemu-system-x86_64", required=not args.dry_run) or "qemu-system-x86_64",
               "-name", config["name"], "-machine", config["machine"] + ",dump-guest-core=off",
               "-accel", accel, "-cpu", config["cpu"], "-m", str(memory),
               "-smp", str(config["vcpus"]), "-drive",
               f"file={escaped_disk},format=qcow2,if=virtio,cache=writethrough",
               "-netdev", network, "-device", "virtio-net-pci,netdev=management,mac=" + config["mac"],
               "-no-reboot"]
    if args.installer:
        iso = Path(args.installer).expanduser().resolve()
        if not iso.is_file():
            raise LabError("Не найден установочный ISO.")
        command += ["-cdrom", str(iso), "-boot", "d"]
    elif args.console == "serial":
        command += ["-nographic"]
    return command, memory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=LAB / "runtime")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    sub.add_parser("status")
    sub.add_parser("verify")
    for verb in ("create", "adopt-base"):
        command = sub.add_parser(verb)
        command.add_argument("--config", type=Path, default=DEFAULT)
        if verb == "adopt-base":
            command.add_argument("image", type=Path)
    command = sub.add_parser("start")
    command.add_argument("--dry-run", action="store_true")
    command.add_argument("--accel", choices=("auto", "kvm", "tcg"), default="auto")
    command.add_argument("--allow-network", action="store_true")
    command.add_argument("--installer", type=Path)
    command.add_argument("--console", choices=("serial", "window"), default="serial",
                         help="serial: console in this terminal; window: VM display window (installer always uses window)")
    for verb in ("checkpoint", "restore", "export"):
        command = sub.add_parser(verb)
        command.add_argument("target", type=Path if verb == "export" else str)
        command.add_argument("--guest-stopped", action="store_true")
        if verb == "restore":
            command.add_argument("--confirm", required=True)
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()

    if args.command == "doctor":
        report = {"platform": platform.system(), "architecture": platform.machine(),
                  "available_memory_mib": available_mib(),
                  "qemu_system": tool("qemu-system-x86_64", False),
                  "qemu_img": tool("qemu-img", False),
                  "kvm_accessible": os.access("/dev/kvm", os.R_OK | os.W_OK),
                  "runtime_exists": root.exists(), "runtime": str(root),
                  "guest_boot_tested": False}
        for key in ("qemu_system", "qemu_img"):
            if report[key]:
                report[key + "_version"] = call([report[key], "--version"], capture=True).splitlines()[0]
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "status":
        print(json.dumps(state(root), ensure_ascii=False, indent=2))
        if (root / "world.lock").exists():
            print("LOCK:", (root / "world.lock").read_text())
        return 0
    if args.command == "verify":
        report = load(root / "SHA256.json")
        if not report:
            raise LabError("Пустой список контрольных сумм.")
        for relative, expected in report.items():
            target = contained(root, relative)
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise LabError("Неверный формат SHA256.")
            if sha(target) != expected:
                raise LabError(f"Контрольная сумма не совпала: {relative}")
        print("Суммы совпали; проверено файлов:", len(report))
        print("После первого изменения рабочего диска эта транспортная сумма закономерно устареет.")
        return 0

    if args.command in ("create", "adopt-base"):
        config = valid_config(load(args.config))
        tool("qemu-img")  # No directory is created if the prerequisite is absent.
        if (root / "world.json").exists():
            raise LabError("Мир уже существует; исходные данные не перезаписаны.")
        with locked(root):
            disk = root / "disks" / "initial.qcow2"
            if disk.exists():
                raise LabError("Диск уже существует без manifest; требуется ручная проверка.")
            if args.command == "adopt-base":
                image = args.image.expanduser().resolve()
                independent_info(image)
                clone(image, disk)
            else:
                disk.parent.mkdir(parents=True, exist_ok=True)
                call([tool("qemu-img"), "create", "-f", "qcow2", disk, f"{config['disk_gib']}G"])
            data = {"schema": 1, "world_id": str(uuid.uuid4()), "config": config,
                    "active_disk": "disks/initial.qcow2", "created": time.time(),
                    "state": "supplied-image" if args.command == "adopt-base" else "empty-disk"}
            write_json(root / "world.json", data)
        print("Мир создан; диск сохраняется между запусками:", disk)
        return 0

    data = state(root)
    if args.command == "start":
        if not args.installer and data["state"] == "empty-disk":
            # Installation may have completed on a previous launch. Do not guess.
            print("Первый диск создан пустым. Если ОС ещё не установлена, нужен --installer ISO.", file=sys.stderr)
        command, memory = qemu_args(root, data, args)
        if args.dry_run:
            print(json.dumps({"argv": command, "guest_memory_mib": memory,
                              "network": "outbound-enabled" if args.allow_network else "isolated-with-local-ssh",
                              "console": "window" if args.installer else args.console,
                              "writes": "none; QEMU was not started"}, ensure_ascii=False, indent=2))
            return 0
        with locked(root):
            # Another short-lived controller may have changed the active branch
            # after our initial read. Read again only after acquiring the lock.
            data = state(root)
            command, memory = qemu_args(root, data, args)
            if not contained(root, data["active_disk"]).is_file():
                raise LabError("Активный диск не найден.")
            available = available_mib()
            if available is not None and available < memory + 768:
                raise LabError(f"Доступно {available} MiB; профилю нужно {memory} MiB + запас 768 MiB. "
                               "Закройте лишние приложения самостоятельно.")
            with socket.socket() as probe:
                try:
                    probe.bind(("127.0.0.1", data["config"]["ssh_port"]))
                except OSError:
                    raise LabError("Порт управления занят; другая VM не остановлена или порт использует иная программа.") from None
            independent_info(contained(root, data["active_disk"]))
            print("SSH (known_hosts храните в каталоге мира): ssh -o UserKnownHostsFile="
                  + str(root / "known_hosts") + " -p", data["config"]["ssh_port"],
                  data["config"]["guest_ssh_user"] + "@127.0.0.1")
            print("Выключение: sudo poweroff внутри гостя. Не извлекайте USB до выхода QEMU.")
            if args.installer:
                print("Установщик: закройте окно только после штатного выключения установленной ОС.")
            elif args.console == "window":
                print("Оконная консоль: вход через виртуальный экран VM. Это не удалённый SSH-сеанс.")
            else:
                print("Консоль: Ctrl+A, затем C — монитор; Ctrl+A, затем H — помощь QEMU.")
            exitcode = run_vm(command)
            data["last_qemu_exit"] = {"time": time.time(), "code": exitcode,
                                      "clean_shutdown_not_automatically_verified": True}
            if args.installer:
                data["state"] = "installation-attempted"
            write_json(root / "world.json", data)
        return 0

    clean_assertion(args)
    with locked(root):
        # A second launcher cannot run; qemu-img additionally refuses incompatible image locks.
        data = state(root)
        disk = contained(root, data["active_disk"])
        independent_info(disk)
        if args.command == "checkpoint":
            if not NAME.fullmatch(args.target):
                raise LabError("Имя точки: буквы/цифры, _ и -, до 48 символов.")
            folder = root / "checkpoints" / args.target
            if folder.exists():
                raise LabError("Такая точка уже существует; она не перезаписана.")
            clone(disk, folder / "disk.qcow2")
            write_json(folder / "checkpoint.json", {"schema": 1, "name": args.target,
                       "world_id": data["world_id"], "config": data["config"], "time": time.time(),
                       "disk_sha256": sha(folder / "disk.qcow2"), "guest_shutdown_confirmed_by_user": True})
            print("Сохранена выключенная точка:", args.target)
        elif args.command == "restore":
            if not NAME.fullmatch(args.target) or args.confirm != args.target:
                raise LabError("--confirm должен совпадать с именем точки.")
            folder = root / "checkpoints" / args.target
            saved = load(folder / "checkpoint.json")
            if saved["world_id"] != data["world_id"] or saved["config"] != data["config"]:
                raise LabError("Контрольная точка принадлежит другому миру/оборудованию.")
            if sha(folder / "disk.qcow2") != saved["disk_sha256"]:
                raise LabError("Контрольная сумма точки не совпала; активный мир не изменён.")
            branch = root / "disks" / ("restore-" + uuid.uuid4().hex[:12] + ".qcow2")
            clone(folder / "disk.qcow2", branch)
            previous = data["active_disk"]
            data["active_disk"] = branch.relative_to(root).as_posix()
            data["restored_from"] = args.target
            data["state"] = "restored-image"
            write_json(root / "world.json", data)
            print("Активна новая ветка:", data["active_disk"], "; прежняя сохранена:", previous)
        else:
            destination = args.target.expanduser().resolve()
            if destination.exists() or destination == root or root in destination.parents:
                raise LabError("Экспорт: нужен новый каталог вне текущего мира; существующие не перезаписываются.")
            destination.mkdir(parents=True)
            clone(disk, destination / "disks" / "initial.qcow2")
            exported = dict(data, active_disk="disks/initial.qcow2", exported_at=time.time())
            write_json(destination / "world.json", exported)
            write_json(destination / "SHA256.json", {"disks/initial.qcow2": sha(destination / "disks" / "initial.qcow2"),
                       "world.json": sha(destination / "world.json")})
            print("Экспортирована независимая выключенная копия:", destination)
            print("У копий одинаковый world_id. Продолжайте только одну ветку; автоматического слияния дисков нет.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LabError, OSError, ValueError, KeyError) as error:
        print("СТЕНД:", error, file=sys.stderr)
        raise SystemExit(2)
