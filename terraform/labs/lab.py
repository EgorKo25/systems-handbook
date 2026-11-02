#!/usr/bin/env python3
"""Explicit lab lifecycle. No operation uses an existing unmarked directory."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKER = '.terraform-handbook-lab'


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


def snapshot(root, target):
    root = owned(root)
    target = Path(target).resolve()
    if root == target or root in target.parents or target in root.parents:
        raise SystemExit('Snapshot must be separate from the working directory')
    if target.exists():
        raise SystemExit('Snapshot already exists; choose a new name')
    if (root / '.terraform.tfstate.lock.info').exists():
        raise SystemExit('Stop Terraform operations before snapshot')
    shutil.copytree(root, target, ignore=shutil.ignore_patterns('.terraform', '*.tfplan'))
    manifest = {str(p.relative_to(target)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(target.rglob('*')) if p.is_file()}
    (target / 'snapshot-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Snapshot saved: source, local state, lab files; dependency cache excluded')


def restore(root, source):
    root = owned(root)
    source = owned(source)
    if root == source or root in source.parents or source in root.parents:
        raise SystemExit('Snapshot and work directory must be separate')
    if (root / '.terraform.tfstate.lock.info').exists():
        raise SystemExit('Stop Terraform operations before restore')
    manifest = json.loads((source / 'snapshot-manifest.json').read_text())
    for name, digest in manifest.items():
        p = (source / name).resolve()
        if source not in p.parents or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            raise SystemExit('Snapshot verification failed')
    # Preserve current data as a sibling: restoration is never a silent reset.
    previous = root.with_name(root.name + '.before-restore')
    if previous.exists():
        raise SystemExit('Previous restore backup exists; inspect it before another restore')
    root.rename(previous)
    shutil.copytree(source, root, ignore=shutil.ignore_patterns('snapshot-manifest.json'))
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
