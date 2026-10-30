#!/usr/bin/env python3
"""Выборочная проверка исполнимых примеров справочника в своём каталоге."""
import os
from pathlib import Path
import subprocess
import tempfile

cases=[
 ("value='100% ready'; printf '%s\\n' \"$value\"",b'100% ready\n'),
 ("printf -v label 'item-%03d' 7; printf '%s\\n' \"$label\"",b'item-007\n'),
 ("printf '%b' 'a\\nb\\n'",b'a\nb\n'),
 ("printf 'aXb\\na.b\\n' | grep -F -- 'a.b'",b'a.b\n'),
 ("printf 'x123\\n' | sed -E 's/[0-9]+/NUM/'",b'xNUM\n'),
 ("printf 'red blue\\n' | sed -e 's/red/R/' -e 's/blue/B/'",b'R B\n'),
 ("printf 'a a\\n' | sed 's/a/b/g'",b'b b\n'),
 ("printf 'alpha:3\\nbeta:5\\n' | awk -F ':' '{s += $2} END {print s}'",b'8\n'),
 ("printf 'a\\nb\\n' | awk 'END {print NR}'",b'2\n'),
 ("printf '' | xargs -r printf 'called\\n'",b''),
 ("printf 'a\\0b\\0c\\0' | xargs -0 -n 2 printf '[%s]\\n'",b'[a]\n[b]\n[c]\n'),
 ("[ 2 -eq 02 ]; printf '%s' \"$?\"",b'0'),
 ("set +m; shopt -s lastpipe; n=0; printf 'x\\n' | read -r n; printf '%s' \"$n\"",b'x'),
 ("bash -c 'exit 7' & p=$!; wait \"$p\"; printf '%s' \"$?\"",b'7'),
 ("bash -c 'exec -c /usr/bin/env'",b''),
 ("printf '2\\n10\\n' | LC_ALL=C sort -n",b'2\n10\n'),
 ("printf 'b\\na\\na\\n' | LC_ALL=C sort -u",b'a\nb\n'),
 ("printf 'a\\na\\nb\\n' | uniq -d",b'a\n'),
 ("printf 'a\\na\\nb\\n' | uniq -u",b'b\n'),
 ("printf 'alpha:3\\n' | cut -d ':' -f 1",b'alpha\n'),
 ("printf 'a:b:c\\n' | cut -d ':' -f 1,3",b'a:c\n'),
 ("printf 'abcdef\\n' | cut -b 2-4",b'bcd\n'),
 ("printf 'plain\\na:b\\n' | cut -s -d ':' -f 2",b'b\n'),
 ("printf 'a1b2\\n' | tr -d '0-9'",b'ab\n'),
 ("printf 'a   b\\n' | tr -s ' '",b'a b\n'),
 ("printf 'abc\\n' | LC_ALL=C tr 'a-z' 'A-Z'",b'ABC\n'),
 ("bash -c 'printf \"%s\\n\" \"$1\"' bash 'two words'",b'two words\n'),
 ("printf data | tee -- ./-log",b'data'),
]
with tempfile.TemporaryDirectory(prefix='bash-command-check-') as directory:
    env=os.environ.copy();env.pop('BASH_ENV',None);env['LC_ALL']='C.UTF-8'
    for index,(code,expected) in enumerate(cases,1):
        result=subprocess.run(['bash','--noprofile','--norc','-c',code],cwd=directory,env=env,
                              capture_output=True,timeout=5)
        assert result.returncode==0,(index,result.returncode,result.stderr)
        assert result.stdout==expected,(index,code,result.stdout,expected)
    assert (Path(directory)/'-log').read_bytes()==b'data'
print(f'PASS commands: {len(cases)} примеров, точные stdout и статус; 1 проверка файла tee')
