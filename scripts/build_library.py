#!/usr/bin/env python3
"""Build the maintained volumes and synchronize their offline dictionaries."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.publication import PUBLISHED
from scripts.legacy_reading import refresh_legacy
print('Legacy reading metadata:', refresh_legacy(ROOT))
subprocess.run([sys.executable, str(ROOT / 'scripts/build_networks.py')], cwd=ROOT, check=True)
for book in (row['slug'] for row in PUBLISHED if row['build'] in {'cache', 'managed'}):
    subprocess.run([sys.executable, str(ROOT / book / 'build.py')], cwd=ROOT, check=True)
from library_catalog import refresh
print(f'Shared dictionary: {refresh()} definitions')
