#!/usr/bin/env python3
"""Optional Linux/Python3 experiments in trusted, private ordinary files.

The files created by init must not be replaced or hard-linked elsewhere.
Symlink checks do not make this helper a security sandbox and do not defend
against hostile concurrent filesystem changes.

Browser models need no Python. This helper is a sequential teaching experiment,
not an atomic multi-client counter or a transactional service.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

MARKER = 'execution-lab.json'
IDENTITY = {'format': 1, 'lab': 'operating-systems-execution', 'counter': 'counter.bin'}


def chosen(path, new=False):
    raw = Path(path).expanduser()
    if not raw.is_absolute():
        raise ValueError('--directory requires an absolute path')
    if any(p.is_symlink() for p in [raw, *raw.parents]):
        raise ValueError('The chosen teaching path must not traverse symlinks')
    if new:
        if raw.exists() and (not raw.is_dir() or any(raw.iterdir())):
            raise ValueError('init needs a new or empty directory; previous data are never reset')
        raw.mkdir(parents=True, exist_ok=True, mode=0o700)
    elif not raw.is_dir():
        raise ValueError('Initialize the own teaching directory explicitly first')
    return raw


def verify(directory):
    marker = directory / MARKER
    counter = directory / 'counter.bin'
    for path in [marker, counter]:
        if path.is_symlink() or not path.is_file():
            raise ValueError('The own lab needs ordinary marker and counter files')
    if json.loads(marker.read_text()) != IDENTITY:
        raise ValueError('Unexpected lab identity')
    if counter.stat().st_size != 4:
        raise ValueError('counter.bin must contain exactly four bytes; state was left unchanged')
    return counter


def write_all(fd, data):
    total = 0
    while total < len(data):
        n = os.write(fd, data[total:])
        if n <= 0:
            raise OSError('Write made no progress')
        total += n
    return total


def sync_directory(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def initialize(path):
    directory = chosen(path, new=True)
    counter = directory / 'counter.bin'
    fd = os.open(counter, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        write_all(fd, bytes([42, 0, 0, 0]))
        os.fsync(fd)
    finally:
        os.close(fd)
    with (directory / MARKER).open('x') as stream:
        json.dump(IDENTITY, stream)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(directory)
    return {'action': 'init', 'directory': str(directory), 'value': 42, 'hex': '2a000000',
            'sync': 'file+directory returned successfully; no power-loss experiment'}


def show(path):
    directory = chosen(path)
    counter = verify(directory)
    data = counter.read_bytes()
    return {'action': 'show', 'directory': str(directory), 'bytes': len(data),
            'hex': data.hex(), 'value': int.from_bytes(data, 'little')}


def increment(path):
    directory = chosen(path)
    counter = verify(directory)
    fd = os.open(counter, os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0))
    try:
        before = os.read(fd, 4)
        if len(before) != 4 or os.fstat(fd).st_size != 4:
            raise ValueError('Changed or incomplete counter; no write started')
        old = int.from_bytes(before, 'little')
        if old == 0xffffffff:
            raise ValueError('This exercise rejects uint32 overflow instead of wrapping')
        after_read = os.lseek(fd, 0, os.SEEK_CUR)
        offset = os.lseek(fd, 0, os.SEEK_SET)
        data = (old + 1).to_bytes(4, 'little')
        n = write_all(fd, data)
        after_write = os.lseek(fd, 0, os.SEEK_CUR)
        os.fsync(fd)
    finally:
        os.close(fd)
    verified = show(path)
    if verified['hex'] != data.hex():
        raise RuntimeError('Post-write read differs; do not run concurrent increments in this sequential exercise')
    return {'action': 'increment', 'before': old, 'after': old + 1,
            'before_hex': before.hex(), 'after_hex': data.hex(),
            'position_after_read': after_read, 'explicit_rewrite_offset': offset,
            'accepted_bytes': n, 'position_after_write': after_write,
            'file_size_after': counter.stat().st_size,
            'sync': 'fsync returned successfully; visibility is not a tested power-loss guarantee',
            'scope': 'one sequential writer; no transaction or concurrent increment guarantee'}


def child(path):
    directory = chosen(path)
    verify(directory)
    # A fresh own child only; no PID lookup, global environment dump or shell.
    code = "import os,json,sys; print(json.dumps({'pid':os.getpid(),'ppid':os.getppid(),'cwd':os.getcwd(),'marker':os.environ['OS_EXECUTION_MARKER']}));sys.exit(7)"
    result = subprocess.run([sys.executable, '-I', '-c', code], cwd=directory,
                            env={'OS_EXECUTION_MARKER': 'child', 'LC_ALL': 'C'},
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=10, check=False)
    if result.returncode != 7:
        raise RuntimeError('Own child returned unexpected result: ' + result.stderr)
    observed = json.loads(result.stdout)
    return {'action': 'child', 'parent_pid': os.getpid(), 'child': observed,
            'waited_exit_status': result.returncode,
            'limits': 'real subprocess creation and waiting; not a measurement of internal fork/exec implementation'}


def clocks(path):
    directory = chosen(path)
    verify(directory)
    wall0, cpu0 = time.perf_counter(), time.process_time()
    time.sleep(0.04)
    sleep = {'wall_seconds': time.perf_counter()-wall0,
             'cpu_seconds': time.process_time()-cpu0}
    wall0, cpu0 = time.perf_counter(), time.process_time()
    checksum = sum(i*i for i in range(100000))
    compute = {'wall_seconds': time.perf_counter()-wall0,
               'cpu_seconds': time.process_time()-cpu0, 'checksum': checksum}
    return {'action': 'clocks', 'sleep': sleep, 'compute': compute,
            'limits': 'own process only; short functional clock contrast, not benchmark or scheduler tracing'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, help='explicit absolute own teaching directory')
    parser.add_argument('action', choices=['init', 'show', 'increment', 'child', 'clocks'])
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        parser.error('This optional native recipe is tested for Linux; browser models remain portable')
    try:
        output = globals()[{'init':'initialize'}.get(args.action, args.action)](args.directory)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({'status':'ERROR','reason':str(error)},ensure_ascii=False),file=sys.stderr)
        return 2
    print(json.dumps(output,ensure_ascii=False,indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
