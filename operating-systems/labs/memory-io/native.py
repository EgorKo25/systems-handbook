#!/usr/bin/env python3
"""Own POSIX learning directory only. No reset, mounts, host tuning or foreign PID."""
from pathlib import Path
import argparse
import fcntl
import json
import os
import struct
import time

MARKER = '.os-memory-io-owned-v1'


def write_all(fd, data):
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        if n <= 0:
            raise OSError('write made no progress')
        view = view[n:]


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected an owned ordinary file: ' + path.name)
    return path


def owned(root):
    if root.is_symlink():
        raise ValueError('Root must not be a symlink')
    root = root.absolute()
    regular(root / MARKER)
    if (root / MARKER).read_text() != 'OS memory/io lab v1\n':
        raise ValueError('Unknown ownership marker')
    regular(root / 'counter.bin')
    if (root / 'history').is_symlink() or not (root / 'history').is_dir():
        raise ValueError('History must be the owned directory')
    return root


def prepare(root):
    if root.exists() or root.is_symlink():
        raise ValueError('Destination exists: continue with status/advance; never prepare over it')
    root.mkdir(parents=True, mode=0o700)
    (root / MARKER).write_text('OS memory/io lab v1\n')
    (root / 'history').mkdir(mode=0o700)
    fd = os.open(root / 'counter.bin', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        write_all(fd, struct.pack('<I', 42))
        os.fsync(fd)
    finally:
        os.close(fd)
    sync_directory(root)
    return status(root)


def status(root):
    root = owned(root)
    data = (root / 'counter.bin').read_bytes()
    if len(data) != 4:
        raise ValueError('Counter format is exactly four bytes; preserve evidence and investigate')
    return {'value': struct.unpack('<I', data)[0], 'bytes': data.hex(' '),
            'history_files': len(list((root / 'history').iterdir())),
            'pending_files': sorted(p.name for p in root.glob('counter.next.*')),
            'scope': 'ordinary reread; not a physical power-loss experiment'}


def advance(root):
    root = owned(root)
    lock_path = root / 'writer.lock'
    if lock_path.is_symlink():
        raise ValueError('Lock must not be a symlink')
    lock = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        old = status(root)['value']
        if old == 0xffffffff:
            raise ValueError('uint32 overflow refused')
        backup = root / 'history' / ('before-' + str(old) + '.bin')
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            write_all(fd, struct.pack('<I', old))
            os.fsync(fd)
        finally:
            os.close(fd)
        sync_directory(root / 'history')
        temporary = root / ('counter.next.' + str(old + 1))
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            write_all(fd, struct.pack('<I', old + 1))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temporary, root / 'counter.bin')
        sync_directory(root)
        # Diagnostic journal is deliberately not one transaction with counter.
        journal = root / 'observations.jsonl'
        if journal.is_symlink():
            raise ValueError('Journal must not be a symlink')
        fd = os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            write_all(fd, (json.dumps({'before': old, 'after': old + 1, 'method': 'file fsync; replace; directory fsync'}) + '\n').encode())
            os.fsync(fd)
        finally:
            os.close(fd)
        return status(root)
    finally:
        os.close(lock)


def descriptors(root):
    root = owned(root)
    path = root / ('fd-observation-' + str(time.time_ns()) + '.bin')
    first = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    duplicate = independent = None
    try:
        write_all(first, struct.pack('<I', 42))
        os.lseek(first, 0, os.SEEK_SET)
        duplicate = os.dup(first)
        independent = os.open(path, os.O_RDONLY)
        a, b, c = os.read(first, 2), os.read(duplicate, 2), os.read(independent, 2)
        position = os.lseek(first, 0, os.SEEK_CUR)
        written = os.pwrite(first, struct.pack('<I', 43), 0)
        if written != 4:
            raise OSError('Unexpected short pwrite in this tiny fixture; preserve file')
        after_position = os.lseek(first, 0, os.SEEK_CUR)
        os.unlink(path)  # Only the uniquely created fixture, never counter.bin.
        after_unlink = os.pread(first, 4, 0)
        return {'read_first': a.hex(' '), 'read_duplicate': b.hex(' '), 'read_independent': c.hex(' '),
                'shared_offset': position, 'offset_after_pwrite': after_position,
                'read_after_unlink': after_unlink.hex(' '), 'original_counter': status(root)['value']}
    finally:
        for fd in (independent, duplicate, first):
            if fd is not None:
                os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'status', 'advance', 'descriptors'])
    parser.add_argument('--root', required=True, type=Path, help='explicit persistent OWN lab directory')
    args = parser.parse_args()
    try:
        result = globals()[args.action](args.root)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\nNo reset attempted; inspect the existing directory.\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
