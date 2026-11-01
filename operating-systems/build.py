#!/usr/bin/env python3
"""Build this volume through the maintained shared reader after registration."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_volume import build
if __name__ == '__main__':
    build('operating-systems')
