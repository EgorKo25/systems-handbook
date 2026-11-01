#!/usr/bin/env python3
"""Build the maintained volumes and synchronize their offline dictionaries."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.publication import PUBLISHED, refresh_publication_metadata
from scripts.legacy_reading import refresh_legacy


def main():
    refresh_publication_metadata(ROOT)
    print('Legacy reading metadata:', refresh_legacy(ROOT))
    subprocess.run([sys.executable, str(ROOT / 'scripts/build_networks.py')], cwd=ROOT, check=True)
    for book in (row['slug'] for row in PUBLISHED if row['build'] in {'cache', 'managed'}):
        subprocess.run([sys.executable, str(ROOT / book / 'build.py')], cwd=ROOT, check=True)
    # A new reader may not exist when an earlier per-volume wrapper builds the
    # home page. Resolve the final shelf only after every reader and its stats.
    from scripts.build_volume import home
    home()
    from scripts.library_catalog import refresh
    print(f'Shared dictionary: {refresh()} definitions')


if __name__ == '__main__':
    main()
