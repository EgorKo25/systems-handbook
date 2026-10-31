"""Build an explicitly bounded, byte-reproducible ZIP without third-party tools."""
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MEMBERS = ("README.txt", "app.py")
DATE = (2000, 1, 1, 0, 0, 0)


def linklike(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def git(*args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    return subprocess.run(["git", "--no-pager", "-c", "core.fsmonitor=false",
                           *args], cwd=ROOT, env=env, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True).stdout.strip()


def build():
    output = ROOT / "dist"
    if linklike(output):
        raise ValueError("dist must not be a symbolic link")
    payload = io.BytesIO()
    records = []
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in MEMBERS:
            path = ROOT / name
            if linklike(path) or not path.is_file():
                raise ValueError(f"input must be a regular file: {name}")
            body = path.read_bytes()
            info = zipfile.ZipInfo(name, DATE)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, body)
            records.append({"name": name, "bytes": len(body),
                            "sha256": hashlib.sha256(body).hexdigest()})
    data = payload.getvalue()
    head = git("rev-parse", "--verify", "HEAD")
    dirty = bool(git("status", "--porcelain", "--untracked-files=normal"))
    manifest = {"format": 1, "archive": "handbook-demo.zip",
                "sha256": hashlib.sha256(data).hexdigest(),
                "members": records,
                "provenance": {"head": head, "tracked_and_untracked_dirty": dirty,
                               "input_source": "working-tree files listed in members"}}
    output.mkdir(exist_ok=True)
    for name in ("handbook-demo.zip", "manifest.json", "source-commit.txt"):
        if linklike(output / name):
            raise ValueError(f"output must not be a symbolic link: {name}")
    (output / "handbook-demo.zip").write_bytes(data)
    with (output / "manifest.json").open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    with (output / "source-commit.txt").open("w", encoding="ascii", newline="\n") as stream:
        stream.write(head + "\n")
    print("dist/handbook-demo.zip", manifest["sha256"])
    return manifest


if __name__ == "__main__":
    build()
