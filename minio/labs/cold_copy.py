#!/usr/bin/env python3
"""Original offline cold-copy exercise. Stop the sole lab server before use.
Copies private state only when explicitly invoked by the learner; no MinIO API.
Rejects links/special files and pre-existing destinations. No automatic deletion.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

MANIFEST = "_snapshot_manifest.json"
COMPLETE = "_snapshot_COMPLETE"
RESERVED = {MANIFEST, COMPLETE}

def safe_name(name):
    return (isinstance(name, str) and bool(name)
            and not name.startswith("/") and "\\" not in name
            and all(p not in ("", ".", "..") for p in name.split("/"))
            and name.split("/")[0] not in RESERVED)

def check_manifest(value):
    if not isinstance(value, dict) or value.get("schema") != 1:
        raise ValueError("Unknown snapshot schema")
    rows = value.get("files")
    if not isinstance(rows, dict):
        raise ValueError("Missing file inventory")
    for name, row in rows.items():
        if (not safe_name(name) or not isinstance(row, dict)
                or type(row.get("bytes")) is not int or row["bytes"] < 0
                or not isinstance(row.get("sha256"), str)
                or len(row["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in row["sha256"])):
            raise ValueError("Invalid snapshot entry")
    return rows

def identity(path):
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while True:
            data = stream.read(1024 * 1024)
            if not data:
                break
            size += len(data)
            h.update(data)
    return {"bytes": size, "sha256": h.hexdigest()}

def inspect_tree(root, snapshot=False):
    rows = {}
    directories = []
    def fail_scan(error):
        raise error

    paths = []
    for parent, subdirs, names in os.walk(
            root, onerror=fail_scan, followlinks=False):
        paths.extend(Path(parent) / name for name in subdirs + names)
    for path in sorted(paths):
        rel = path.relative_to(root).as_posix()
        if snapshot and rel in RESERVED:
            continue
        if not safe_name(rel):
            raise ValueError("Reserved or unsafe path")
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            directories.append(rel)
        elif stat.S_ISREG(mode):
            rows[rel] = identity(path)
        else:
            raise ValueError("Links/special files require separate review")
    return rows, directories

def separate(source, destination):
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Source and destination must be separate trees")

def new_target(source, destination):
    separate(source, destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("Destination already exists")
    if not destination.parent.is_dir():
        raise ValueError("Create the private destination parent explicitly")
    destination.mkdir(mode=0o700)

def copy_entries(source, destination, rows, directories):
    for name in directories:
        (destination / name).mkdir(mode=0o700, parents=True, exist_ok=True)
    for name in rows:
        out = destination / name
        out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (source / name).open("rb") as src, out.open("xb") as dst:
            shutil.copyfileobj(src, dst, 1024 * 1024)
            dst.flush()
            os.fsync(dst.fileno())
        shutil.copystat(source / name, out, follow_symlinks=False)

def read_snapshot(source):
    if (source / COMPLETE).read_text() != "complete\n":
        raise ValueError("Snapshot incomplete")
    value = json.loads((source / MANIFEST).read_text())
    rows = check_manifest(value)
    actual, directories = inspect_tree(source, snapshot=True)
    if actual != rows:
        raise ValueError("Snapshot content does not match inventory")
    return rows, directories

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("snapshot", "verify", "restore"))
    parser.add_argument("source")
    parser.add_argument("destination", nargs="?")
    args = parser.parse_args()
    raw = Path(args.source).expanduser()
    if raw.is_symlink():
        raise ValueError("Source root must not be a link")
    source = raw.resolve(strict=True)
    if not source.is_dir():
        raise ValueError("Source is not a directory")
    if args.action == "verify":
        if args.destination is not None:
            parser.error("verify takes only SOURCE")
        rows, _ = read_snapshot(source)
        print(json.dumps({"status": "verified", "files": len(rows)}))
        return
    if args.destination is None:
        parser.error("destination is required")
    destination = Path(args.destination).expanduser().absolute()
    if destination.parent.is_symlink():
        raise ValueError("Destination parent must not be a link")
    destination = destination.parent.resolve(strict=True) / destination.name
    if args.action == "snapshot":
        if not (source / ".setup/root-layout/COMPLETE").is_file():
            raise ValueError("Not a prepared lab root")
        rows, directories = inspect_tree(source)
    else:
        rows, directories = read_snapshot(source)
    new_target(source, destination)
    copy_entries(source, destination, rows, directories)
    actual, _ = inspect_tree(destination)
    if actual != rows:
        raise ValueError("Copy verification failed; preserve partial target")
    if args.action == "snapshot":
        with (destination / MANIFEST).open("x") as stream:
            json.dump({"schema": 1, "files": rows}, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        with (destination / COMPLETE).open("x") as stream:
            stream.write("complete\n")
            stream.flush()
            os.fsync(stream.fileno())
    print(json.dumps({"status": args.action + "-copied", "files": len(rows)}))

if __name__ == "__main__":
    main()
