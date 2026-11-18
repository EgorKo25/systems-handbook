#!/usr/bin/env python3
"""Explicit lab lifecycle. No operation uses an existing unmarked directory."""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKER = '.terraform-handbook-lab'
MANIFEST = 'snapshot-manifest.json'


def owned(path):
    path = Path(path).resolve()
    if not (path / MARKER).is_file():
        raise SystemExit('Refusing unmarked directory; prepare a new lab first')
    return path


def prepare(path):
    path = Path(path).resolve()
    if path.exists():
        raise SystemExit('Destination already exists; continuing labs must reuse it without prepare')
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(HERE / 'foundation', path)
    (path / MARKER).write_text('Original Terraform handbook persistent lab v1\n')
    print('Prepared new isolated lab; continue in the same directory')


def file_checksums(directory):
    checksums = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise SystemExit('Lab snapshots do not support symbolic links')
        if path.is_file() and path != directory / MANIFEST:
            checksums[str(path.relative_to(directory))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return checksums


def snapshot(root, target):
    root = owned(root)
    target = Path(target).resolve()
    if root == target or root in target.parents or target in root.parents:
        raise SystemExit('Snapshot must be separate from the working directory')
    if target.exists():
        raise SystemExit('Snapshot already exists; choose a new name')
    if (root / '.terraform.tfstate.lock.info').exists():
        raise SystemExit('Stop Terraform operations before snapshot')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.lab-snapshot-', dir=target.parent) as tmp:
        staged = Path(tmp) / 'snapshot'
        shutil.copytree(
            root, staged, symlinks=True,
            ignore=shutil.ignore_patterns('.terraform', '*.tfplan'),
        )
        (staged / MANIFEST).write_text(json.dumps(file_checksums(staged), indent=2) + '\n')
        if target.exists():
            raise SystemExit('Snapshot already exists; choose a new name')
        staged.rename(target)
    print('Snapshot saved: source, local state, lab files; dependency cache excluded')


def restore(root, source):
    root = owned(root)
    source = owned(source)
    if root == source or root in source.parents or source in root.parents:
        raise SystemExit('Snapshot and work directory must be separate')
    if (root / '.terraform.tfstate.lock.info').exists():
        raise SystemExit('Stop Terraform operations before restore')
    previous = root.with_name(root.name + '.before-restore')
    if previous.exists():
        raise SystemExit('Previous restore backup exists; inspect it before another restore')
    with tempfile.TemporaryDirectory(prefix='.lab-restore-', dir=root.parent) as tmp:
        staged = Path(tmp) / 'restored'
        shutil.copytree(source, staged, symlinks=True)
        actual = file_checksums(staged)
        manifest_file = staged / MANIFEST
        try:
            expected = json.loads(manifest_file.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise SystemExit('Snapshot verification failed: unreadable manifest') from exc
        if actual != expected:
            raise SystemExit('Snapshot verification failed: file list or checksums differ')
        manifest_file.unlink()
        root.rename(previous)
        try:
            staged.rename(root)
        except OSError:
            previous.rename(root)
            raise
    print('Restored stopped local-only lab. Previous directory preserved as *.before-restore')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    for name in ['prepare', 'snapshot', 'restore']:
        a = sub.add_parser(name)
        a.add_argument('root')
        if name != 'prepare':
            a.add_argument('copy')
    args = p.parse_args()
    if args.action == 'prepare': prepare(args.root)
    elif args.action == 'snapshot': snapshot(args.root, args.copy)
    else: restore(args.root, args.copy)

if __name__ == '__main__': main()
