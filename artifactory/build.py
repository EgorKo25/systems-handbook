#!/usr/bin/env python3
"""Managed volume wrapper. Run only after integration, or in an isolated snapshot."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_volume import build, home
from scripts.library_catalog import refresh
if __name__ == '__main__':
    build('artifactory')
    home()
    refresh()
