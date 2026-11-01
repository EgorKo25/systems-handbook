#!/usr/bin/env python3
"""Build through the managed library; publication remains an explicit allowlist."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_volume import build
if __name__ == '__main__':
    build('computer-architecture')
