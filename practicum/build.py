#!/usr/bin/env python3
"""Compile original missions, then use the common offline reader."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from practicum.sources.prepare import prepare
from scripts.build_volume import build, home
from scripts.library_catalog import refresh

if __name__ == '__main__':
    prepare()
    build('practicum')
    home()
    refresh()
