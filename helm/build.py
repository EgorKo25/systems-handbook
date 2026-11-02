#!/usr/bin/env python3
"""Integration wrapper. Do not run before the volume is registered centrally."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_volume import build, home
from scripts.library_catalog import refresh
if __name__ == '__main__':
    build('helm')
    home()
    refresh()
