"""Run chapter 38's sixteen protocol checks against an owned Memcached process.

Uses only Python's standard library and an installed Memcached binary. No existing
service is contacted, no flush_all is sent, and no system configuration is changed.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid


class Client:
    def __init__(self, port):
        self.port = port

    def __enter__(self):
        self.socket = socket.create_connection(("127.0.0.1", self.port), timeout=3)
        self.file = self.socket.makefile("rb")
        return self

    def __exit__(self, *args):
        self.file.close()
        self.socket.close()

    def line(self):
        line = self.file.readline(8193)
        if len(line) > 8192 or not line.endswith(b"\r\n"):
            raise RuntimeError("Incomplete or oversized response line")
        return line[:-2]

    def simple(self, command):
        self.socket.sendall(command.encode("ascii") + b"\r\n")
        return self.line()

    def store(self, operation, key, value, ttl=60, token=None):
        data = value.encode("utf-8") if isinstance(value, str) else value
        header = f"{operation} {key} 0 {ttl} {len(data)}"
        if token is not None:
            header += " " + str(token)
        self.socket.sendall(header.encode("ascii") + b"\r\n" + data + b"\r\n")
        return self.line()

    def get(self, *keys, cas=False):
        command = ("gets " if cas else "get ") + " ".join(keys)
        self.socket.sendall(command.encode("ascii") + b"\r\n")
        result = {}
        while True:
            line = self.line()
            if line == b"END":
                return result
            parts = line.split()
            if len(parts) not in (4, 5) or parts[0] != b"VALUE":
                raise RuntimeError("Unexpected reply: " + repr(line))
            length = int(parts[3])
            if not 0 <= length <= 16 * 1024 * 1024:
                raise RuntimeError("Unexpected payload length")
            data = self.file.read(length)
            if len(data) != length or self.file.read(2) != b"\r\n":
                raise RuntimeError("Incomplete value")
            token = int(parts[4]) if len(parts) == 5 else None
            result[parts[1].decode("ascii")] = data, token

    def stats(self):
        self.socket.sendall(b"stats\r\n")
        result = {}
        while True:
            line = self.line()
            if line == b"END":
                return result
            parts = line.split(maxsplit=2)
            if len(parts) != 3 or parts[0] != b"STAT":
                raise RuntimeError("Unexpected stats reply")
            result[parts[1].decode()] = parts[2].decode()


def exercise(port, check):
    prefix = "book:mc:" + uuid.uuid4().hex
    with Client(port) as a, Client(port) as b:
        key = prefix + ":value"
        empty = prefix + ":empty"
        counter = prefix + ":counter"
        absent = prefix + ":absent"
        check("missing", a.get(absent), {})

        value = "Привет\r\nEND\r\nworld".encode("utf-8")
        assert a.store("set", key, value) == b"STORED"
        check("UTF-8 and embedded CRLF", a.get(key)[key][0], value)

        assert a.store("set", empty, b"") == b"STORED"
        check("empty differs from missing", a.get(empty)[empty][0], b"")
        check("add does not replace", a.store("add", key, "other"), b"NOT_STORED")

        token = a.get(key, cas=True)[key][1]
        assert b.store("set", key, "newer") == b"STORED"
        check("CAS conflict", a.store("cas", key, "old", token=token), b"EXISTS")
        token = a.get(key, cas=True)[key][1]
        check("CAS current token", a.store("cas", key, "current", token=token), b"STORED")

        assert a.store("set", counter, "10") == b"STORED"
        check("increment", a.simple("incr " + counter + " 3"), b"13")
        check("decrement stops at zero", a.simple("decr " + counter + " 99"), b"0")

        past = prefix + ":past"
        assert a.store("set", past, "gone", ttl=2592001) == b"STORED"
        check("absolute date in the past", a.get(past), {})

        short = prefix + ":short"
        assert a.store("set", short, "temporary", ttl=1) == b"STORED"
        time.sleep(2.2)
        check("relative expiration", a.get(short), {})

        before = a.stats()
        found = a.get(key, absent, empty)
        after = a.stats()
        check("multiget keys", set(found), {key, empty})
        check("multiget hit delta", int(after["get_hits"]) - int(before["get_hits"]), 2)
        check("multiget miss delta", int(after["get_misses"]) - int(before["get_misses"]), 1)
        check("cmd_get counts keys in tested server", int(after["cmd_get"]) - int(before["cmd_get"]), 3)

        check("delete", a.simple("delete " + key), b"DELETED")
        check("deleted missing", a.get(key), {})
        for cleanup_key in (empty, counter):
            a.simple("delete " + cleanup_key)


def json_value(value):
    if isinstance(value, bytes):
        return {"utf8": value.decode("utf-8"), "length_bytes": len(value)}
    if isinstance(value, set):
        return sorted(value)
    return value


def unused_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def ready_owned(process, port):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Owned Memcached exited before readiness")
        try:
            with Client(port) as client:
                stats = client.stats()
            if int(stats["pid"]) != process.pid:
                raise RuntimeError("Port belongs to another process; refusing to test")
            if process.poll() is not None:
                raise RuntimeError("Owned Memcached exited during readiness")
            return stats
        except (ConnectionError, socket.timeout):
            time.sleep(0.05)
    raise TimeoutError("Owned Memcached did not become ready")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memcached", default="memcached")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).with_name("memcached-semantics-results.json"))
    args = parser.parse_args()
    binary = shutil.which(args.memcached)
    if binary is None:
        parser.error("Missing program: " + args.memcached)
    binary = str(Path(binary).resolve())
    report = {
        "status": "RUNNING",
        "kind": "actual owned loopback Memcached process",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "versions": {"python": platform.python_version(), "platform": platform.platform()},
        "binary": str(Path(binary).resolve()),
        "cases": [],
        "limits": [
            "Basic text protocol only; no SASL, TLS, meta or built-in proxy execution",
            "No eviction benchmark, network partition, replication or power-loss test",
            "cmd_get expectation is verified for this server version, not inferred from the field name",
        ],
    }

    def check(name, actual, expected):
        passed = actual == expected
        report["cases"].append({"name": name, "status": "PASS" if passed else "FAIL",
                                "actual": json_value(actual), "expected": json_value(expected)})
        if not passed:
            raise AssertionError(f"{name}: {actual!r} != {expected!r}")
        print("PASS", name)

    process = None
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="cache-book-memcached-semantics-") as tmp:
        log_path = Path(tmp) / "memcached.log"
        with log_path.open("wb") as log:
            try:
                port = unused_port()
                command = [binary, "-l", "127.0.0.1", "-p", str(port), "-U", "0",
                           "-m", "32", "-t", "2"]
                if hasattr(os, "geteuid") and os.geteuid() == 0:
                    command += ["-u", "root"]
                report["command"] = command
                process = subprocess.Popen(command, stdout=log, stderr=log, cwd=tmp)
                stats = ready_owned(process, port)
                report["versions"]["memcached"] = stats["version"]
                report["server_pid"] = int(stats["pid"])
                exercise(port, check)
                report["status"] = "PASS"
            except Exception as error:
                report["status"] = "FAIL"
                report["error"] = f"{type(error).__name__}: {error}"
                print(report["error"], file=sys.stderr)
            finally:
                if process is not None:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                    report["owned_process_stopped"] = process.poll() is not None
                log.flush()
                if report["status"] != "PASS":
                    report["server_log"] = log_path.read_text(errors="replace")
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status']}: {len(report['cases'])} checks; report: {args.output}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
