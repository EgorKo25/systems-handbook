#!/usr/bin/env python3
"""Check every literal native CLI flag against the prepared core2.21.5 parser."""
from pathlib import Path
import argparse
import importlib.util
import re
import subprocess
import sys
sys.dont_write_bytecode = True
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ansible-bin', type=Path, required=True)
args = parser.parse_args()
source = Path(__file__).resolve().parents[1]/'sources/reference.py'
spec = importlib.util.spec_from_file_location('ansible_command_reference',source)
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
version=subprocess.check_output([str(args.ansible_bin/'ansible'),'--version'],text=True).splitlines()[0]
assert '[core 2.21.5]' in version, version
for command in reference.COMMANDS:
    invocation=command['name'].split();invocation[0]=str(args.ansible_bin/invocation[0])
    result=subprocess.run(invocation+['--help'],capture_output=True,text=True,check=True,timeout=30)
    for flag in command['flags']:
        token=flag['flag'].split()[0]
        assert re.search(r'(?<![\w-])'+re.escape(token)+r'(?![\w-])',result.stdout),(command['name'],token)
print('PASS',len(reference.COMMANDS),'native commands;',sum(len(c['flags']) for c in reference.COMMANDS),'literal flags in matching subcommand --help')
