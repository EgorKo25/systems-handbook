#!/usr/bin/env python3
"""Build the maintained volumes and synchronize their offline dictionaries."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
for book in ('cache', 'git'):
    subprocess.run([sys.executable, str(ROOT / book / 'build.py')], cwd=ROOT, check=True)
from library_catalog import refresh
print(f'Shared dictionary: {refresh()} definitions')
