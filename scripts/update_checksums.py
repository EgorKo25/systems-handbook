#!/usr/bin/env python3
"""Refresh the repository's checksum list for tracked public reading files."""
import hashlib
from pathlib import Path
import subprocess
from prepare_site import is_reading_file

root = Path(__file__).resolve().parents[1]
names = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z']).decode('utf-8').split('\0')
lines = []
for name in sorted(n for n in names if n and is_reading_file(n)):
    path = root / name
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        raise SystemExit('Cannot checksum a missing file or symlink: ' + name)
    lines.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + name + '\n')
(root / 'SHA256SUMS').write_text(''.join(lines), encoding='utf-8')
print('Checksums:', len(lines), 'public reading files')
