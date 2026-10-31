#!/usr/bin/env python3
"""Build this independent volume; the shared implementation lives in scripts/."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_volume import build, home
if __name__ == '__main__':
    build('go')
    if all((Path(__file__).resolve().parents[1]/s/'index.html').exists() for s in ('git','go','jenkins')): home()

    from scripts.library_catalog import refresh
    refresh()
