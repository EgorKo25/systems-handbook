#!/usr/bin/env python3
"""Конечные опыты к главам 08–18. Только собственные файлы и дочерние процессы.

Python 3.12, GNU Bash 5.2, GNU coreutils/findutils/grep/sed, awk, util-linux flock.
Запуск: python3 remaining_lab.py --work-root СОБСТВЕННЫЙ_КАТАЛОГ > result.json
Каталог должен существовать. Каждый запуск создаёт и убирает свой подкаталог.
Нет HOME/BASH_ENV/ENV, стартовых файлов, TTY, сети, служб и установки программ.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True  # Не записывать __pycache__ рядом с файлами книги.
import argparse
import errno
import gzip
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent
BASH = shutil.which('bash') or '/bin/bash'
RESULTS = []
CHECKS = 0
ENV = {}


def check(condition, message):
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(message)


def run(argv, root, *, data=None, status=0):
    result = subprocess.run(argv, cwd=root, env=ENV, input=data,
                            capture_output=True, timeout=8)
    check(result.returncode == status,
          repr((argv, result.returncode, result.stdout, result.stderr)))
    RESULTS.append({'argv': argv, 'cwd': str(root), 'status': result.returncode,
                    'stdout_hex': result.stdout.hex(), 'stderr_hex': result.stderr.hex()})
    return result


def shell(code, root, *, out=None, status=0):
    result = run([BASH, '--noprofile', '--norc', '-c', code], root, status=status)
    if out is not None:
        check(result.stdout == out, repr((code, result.stdout, out)))
    return result


def conditions(root):
    (root/'service.log').write_bytes(b'BOOT\nREADY\n')
    for pattern, name, expected in [('READY', 'service.log', 0), ('WAIT', 'service.log', 1),
                                    ('READY', 'missing.log', 2)]:
        run(['grep', '-qF', '--', pattern, name], root, status=expected)
    # GNU grep -q: найденное совпадение не доказывает полноту чтения всех файлов.
    run(['grep', '-qF', '--', 'READY', 'missing.log', 'service.log'], root)
    shell("for re in '^a$' '^z$' '['; do [[ a =~ $re ]]; printf '%s\\n' \"$?\"; done",
          root, out=b'0\n1\n2\n')
    shell("n=0; ((n++)); rc=$?; printf '%s:%s\\n' \"$n\" \"$rc\"", root, out=b'1:1\n')
    shell('for a in A B; do for b in 1 2; do printf "%s%s\\n" "$a" "$b"; break 2; done; done',
          root, out=b'A1\n')
    shell('for a in A B; do for b in 1 2; do printf "%s%s\\n" "$a" "$b"; continue 2; done; done',
          root, out=b'A1\nB1\n')
    (root/'input.txt').write_bytes(b' a \\ b\nlast')
    shell("while IFS= read -r line || [[ -n $line ]]; do printf '<%s>\\n' \"$line\"; done <input.txt",
          root, out=b'< a \\ b>\n<last>\n')
    (root/'broken').symlink_to('not-created')
    shell('[ -L broken ]; a=$?; [ -e broken ]; b=$?; [ -f broken ]; c=$?; printf "%s:%s:%s" "$a" "$b" "$c"',
          root, out=b'0:1:1')


def functions(root):
    shell('f() { return 300; }; f; printf "%s:" "$?"; f() { return -1; }; f; printf "%s" "$?"',
          root, out=b'44:255')
    shell('a=(); a[5]=x; a[9]=""; printf "%s:%s:%s\\n" "${#a[@]}" "${!a[*]}" "${a[-1]}"',
          root, out=b'2:5 9:\n')
    shell('inner() { printf "%s:" "$color"; }; outer() { local color=blue; inner; }; color=red; outer; printf "%s" "$color"',
          root, out=b'blue:red')
    shell('''make_list() {
    [[ $# == 1 && $1 == items ]] || return 2
    local -n result_ref=items
    result_ref=('a b' '' '*')
}
items=(old)
make_list result_ref; rc=$?
printf '%s:%s\\n' "$rc" "${items[0]}"
make_list items
printf '<%s>\\n' "${items[@]}"
''', root, out=b'2:old\n<a b>\n<>\n<*>\n')
    (root/'library.sh').write_bytes(b'cd /\nvalue=changed\nreturn 7\n')
    shell('value=parent; before=$PWD; ( source ./library.sh ); rc=$?; printf "%s:%s:" "$rc" "$value"; [[ $PWD == "$before" ]]; printf "%s" "$?"',
          root, out=b'7:parent:0')


def traps(root):
    for code, status in [("trap ':' EXIT; exit 7", 7), ("trap false EXIT; exit 7", 7),
                         ("trap 'exit 0' EXIT; exit 7", 0),
                         ("set -e; trap false EXIT; exit 7", 1)]:
        shell(code, root, out=b'', status=status)
    shell("trap 'printf once; exit 7' EXIT; exit 0", root, out=b'once', status=7)
    shell('set -e; f() { false; printf CONTINUE; }; if f; then printf SUCCESS; fi',
          root, out=b'CONTINUESUCCESS')
    shell('set -e; f() { false; printf BAD; }; f', root, out=b'', status=1)
    shell('set -e; x=$(false; printf OK); printf "%s" "$x"', root, out=b'OK')
    shell('set -e; shopt -s inherit_errexit; x=$(false; printf BAD); printf BAD', root, out=b'', status=1)
    r = shell("set -E; trap 'printf ERR >&2' ERR; f() { false; }; f", root, status=1)
    check(r.stderr == b'ERRERR', 'ERR у false и у неуспешного вызова функции')
    shell("set -E; trap 'printf BAD >&2' ERR; f() { false; }; if f; then :; fi", root, out=b'')
    # Выбранная политика: первичный отказ важнее отказа cleanup; при успехе cleanup даёт 74.
    cleanup = '''cleanup() {
 local rc=$?
 trap - EXIT
 if false; then :; else (( rc != 0 )) || rc=74; fi
 exit "$rc"
}
trap cleanup EXIT
'''
    shell(cleanup+'exit 7', root, status=7)
    shell(cleanup+'exit 0', root, status=74)


def filenames(root):
    data = root/'data'; data.mkdir()
    names = [b'a\nb.txt', b'two words', b'*', b'-leading', b'back\\slash', b'bad-\xff']
    for name in names:
        fd = os.open(os.fsencode(data)+b'/'+name, os.O_CREAT|os.O_WRONLY, 0o600); os.close(fd)
    r = run(['find', './data', '-type', 'f', '-print0'], root)
    check(set(r.stdout.split(b'\0')[:-1]) == {b'./data/'+x for x in names}, 'NUL records')
    check(len(b'./data/a\nb.txt\0') == 15, '7-byte component, 14-byte path, 15-byte record')
    run(['xargs', '-0', '-r', 'printf', 'called\n'], root, data=b'')
    r = run(['xargs', '-0', 'printf', 'called\n'], root, data=b'')
    check(r.stdout == b'called\n', 'без -r есть запуск на пустом вводе')
    for code, expected in [('7', 123), ('255', 124)]:
        run(['xargs', '-0', '-r', BASH, '--noprofile', '--norc', '-c', 'exit '+code, 'worker'],
            root, data=b'a\0', status=expected)
    run(['find', './data', '-type', 'f', '-exec', 'false', '{}', '+'], root, status=1)
    run(['find', './data', '-type', 'f', '-exec', 'false', '{}', ';'], root)
    path = root/'held'; path.write_bytes(b'old')
    with path.open('rb') as stream:
        path.rename(root/'old'); path.write_bytes(b'new')
        check(stream.read() == b'old' and path.read_bytes() == b'new', 'удержанный FD против нового пути')
    decoded = os.fsdecode(b'bad-\xff')
    encoded = json.dumps(decoded, ensure_ascii=True).encode('ascii')
    check(os.fsencode(json.loads(encoded)) == b'bad-\xff', 'Python surrogateescape roundtrip')
    # Проверяем поставленный измеритель argv, включая байт, не являющийся UTF-8.
    argv = [sys.executable, str(HERE/'argv_dump.py'), os.fsdecode(b'bad-\xff'), 'Я']
    result = subprocess.run(argv, cwd=root, env=ENV, capture_output=True, timeout=3)
    check(result.returncode == 0, repr(result.stderr))
    check(result.stdout.isascii(), 'JSON-вывод argv_dump остаётся ASCII/UTF-8')
    values = json.loads(result.stdout.decode('utf-8', errors='strict'))
    check([v['hex'] for v in values] == ['62 61 64 2d ff', 'd0 af'], 'точные байты ff и Я')
    check([v['bytes'] for v in values] == [5, 2], 'точные длины аргументов')
    check(os.fsencode(values[0]['text']) == b'bad-\xff' and values[1]['text'] == 'Я',
          'JSON roundtrip имён через Python filesystem codec')
    RESULTS.append({'argv_hex': [os.fsencode(v).hex() for v in argv], 'cwd': str(root),
                    'status': result.returncode, 'stdout_hex': result.stdout.hex(),
                    'stderr_hex': result.stderr.hex()})


def text_bytes(root):
    run(['wc', '-c'], root, data='Я\n'.encode())
    check(run(['wc', '-m'], root, data='Я\n'.encode()).stdout.strip() == b'2', 'locale characters')
    check(run(['wc', '-l'], root, data=b'last').stdout.strip() == b'0', 'LF count')
    check(run(['sed', 's/cat/A&B/'], root, data=b'cat\n').stdout == b'AcatB\n', 'sed &')
    check(run(['sed', r's/cat/A\&B/'], root, data=b'cat\n').stdout == b'A&B\n', 'sed literal &')
    check(run(['awk', '-v', r'v=a\nb', 'BEGIN {printf "%s",v}'], root).stdout == b'a\nb', 'awk escape processing')
    check(run(['grep', '-F', '--', 'a\nb'], root, data=b'a\nb\nx\n').stdout == b'a\nb\n', 'LF creates patterns')
    check(run(['grep', '-Eo', 'a*'], root, data=b'bbb\n').stdout == b'', 'empty match status0, no output')
    zipped = gzip.compress(b'payload\n')
    r = run(['gzip', '-dc'], root, data=zipped[:-5], status=1)
    check(r.stdout == b'payload\n', 'partial stdout persists on gzip failure')


def processes(root):
    shell('sleep 0.02 & a=$!; wait "$a"; printf "%s" "$?"', root, out=b'0')
    shell('set -u; finished=old; wait -n -p finished; rc=$?; printf "%s:%s" "$rc" "${finished-unset}"',
          root, out=b'127:unset')
    shell('''pids=()
(exit 7) & pids+=("$!")
(exit 3) & pids+=("$!")
first=0
for p in "${pids[@]}"; do
 if wait "$p"; then :; else rc=$?; ((first != 0)) || first=$rc; fi
done
printf '%s' "$first"
''', root, out=b'7')
    # TERM только своему Popen; обработчик во время wait возвращает раньше ребёнка.
    code = "trap 'printf TERM; stopped=1' TERM; stopped=0; sleep 0.2 & child=$!; printf ready >ready; wait \"$child\"; first=$?; if ((stopped)); then wait \"$child\"; fi; printf ':%s:%s' \"$first\" \"$?\""
    p = subprocess.Popen([BASH, '--noprofile', '--norc', '-c', code], cwd=root, env=ENV,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        until = time.monotonic()+3
        while not (root/'ready').exists() and time.monotonic()<until:
            time.sleep(0.005)
        check((root/'ready').exists(), 'own child ready')
        p.terminate()
        out, err = p.communicate(timeout=3)
        check(p.returncode == 0 and out == b'TERM:143:0', repr((p.returncode,out,err)))
    finally:
        if p.poll() is None:
            p.kill(); p.communicate(timeout=3)


def scripts(root):
    task = root/'task'
    task.write_bytes(b'#!/usr/bin/env -S /bin/bash --noprofile --norc\nprintf "<%s>\\n" "$@"\nvalue=changed\n')
    task.chmod(0o700)
    check(run([str(task),'two words','','*'],root).stdout == b'<two words>\n<>\n<*>\n','kernel/env/Bash argv')
    task.chmod(0o600)
    try:
        subprocess.run([str(task)],cwd=root,env=ENV,capture_output=True,timeout=3)
    except PermissionError as e:
        check(e.errno == errno.EACCES,'missing execute bit')
    else:
        check(False,'direct execution must fail')
    run([BASH,'--noprofile','--norc',str(task)],root)
    for name, payload, expected in [('crlf',b'#!/bin/bash\r\nprintf ok\n',errno.ENOENT),
                                    ('bom',b'\xef\xbb\xbf#!/bin/bash\nprintf ok\n',errno.ENOEXEC)]:
        q=root/name; q.write_bytes(payload);q.chmod(0o700)
        try:
            subprocess.run([str(q)],cwd=root,env=ENV,capture_output=True,timeout=3)
        except OSError as e:
            check(e.errno == expected,repr((name,e)))
        else:
            check(False,'execve must reject '+name)


def files_concurrency(root):
    # Повторение в одной Bash освобождает FD, поэтому не ждёт свою прежнюю блокировку.
    shell('for i in 1 2; do exec {fd}>lock || exit; flock -x -w 1 "$fd" || exit; printf "%s" "$i"; exec {fd}>&-; done',root,out=b'12')
    # Две открытые ссылки к разным inode: удаление lock разрушает взаимное исключение.
    import fcntl
    a=os.open(root/'split.lock',os.O_CREAT|os.O_RDWR,0o600)
    try:
        fcntl.flock(a,fcntl.LOCK_EX|fcntl.LOCK_NB)
        (root/'split.lock').unlink()
        b=os.open(root/'split.lock',os.O_CREAT|os.O_RDWR,0o600)
        try:
            fcntl.flock(b,fcntl.LOCK_EX|fcntl.LOCK_NB)
            check(os.fstat(a).st_ino != os.fstat(b).st_ino,'different lock objects')
        finally:os.close(b)
    finally:os.close(a)
    (root/'counter').write_bytes(b'10\n')
    # Два писателя гарантированно читают 10 до разрешения публикации.
    code='IFS= read -r n <counter; printf ready >"ready-$1"; while [[ ! -f go ]]; do sleep 0.005; done; printf "%s\\n" "$((n+1))" >"pending-$1"; mv -fT -- "pending-$1" counter'
    ps=[subprocess.Popen([BASH,'--noprofile','--norc','-c',code,'worker',str(i)],cwd=root,env=ENV) for i in [1,2]]
    try:
        until=time.monotonic()+3
        while not all((root/f'ready-{i}').exists() for i in [1,2]) and time.monotonic()<until:time.sleep(.005)
        check(all((root/f'ready-{i}').exists() for i in [1,2]),'both read10')
        (root/'go').touch()
        for p in ps:check(p.wait(timeout=3)==0,'unlocked worker completed')
        check((root/'counter').read_bytes()==b'11\n','lost update despite atomic mv')
    finally:
        for p in ps:
            if p.poll() is None:p.kill();p.wait(timeout=3)
    (root/'counter').write_bytes(b'10\n')
    shell('update() ( exec {fd}>counter.lock || exit; flock -x -w 2 "$fd" || exit; IFS= read -r n <counter || exit; printf "%s\\n" "$((n+1))" >"pending-$BASHPID" || exit; mv -fT -- "pending-$BASHPID" counter ); update & a=$!; update & b=$!; wait "$a" || exit; wait "$b" || exit; cat counter',root,out=b'12\n')
    spec=importlib.util.spec_from_file_location('own_atomic',HERE/'atomic_publish.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    destination=root/'report';destination.write_bytes(b'old')
    try:m.publish(destination,b'new',fail_before_replace=True)
    except RuntimeError:pass
    else:check(False,'expected before-replace fault')
    check(destination.read_bytes()==b'old','old preserved before replace')
    original=m.os.fsync;calls=0
    def fail_directory(fd):
        nonlocal calls
        calls+=1
        if calls==2:raise OSError(errno.EIO,'simulated directory fsync failure')
        return original(fd)
    m.os.fsync=fail_directory
    try:
        try:m.publish(destination,b'new')
        except OSError:pass
        else:check(False,'expected after-replace fault')
    finally:m.os.fsync=original
    check(destination.read_bytes()==b'new','new visible despite post-replace failure')
    check(not list(root.glob('.pending-*')),'pending cleaned')


def diagnostics(root):
    r=shell('''(
exec {tracefd}>trace.log || exit
BASH_XTRACEFD=$tracefd
PS4='+ ${LINENO}: '
set -x
printf '%s\\n' 'two words'
set +x
unset BASH_XTRACEFD
)
''',root,out=b'two words\n')
    check(b'printf' in (root/'trace.log').read_bytes() and r.stderr==b'','separate trace FD')
    shell("produce() { printf 'partial\\n'; return 7; }; if value=$(produce); then exit 1; else rc=$?; printf '%s:%s' \"$rc\" \"$value\"; fi",root,out=b'7:partial')
    shell("set -o pipefail; TIMEFORMAT='elapsed=%3R user=%3U sys=%3S'; time printf '%s\\n' x | grep -q z; rc=$? stages=(\"${PIPESTATUS[@]}\"); printf '%s:%s:%s' \"$rc\" \"${stages[0]}\" \"${stages[1]}\"",root,out=b'1:0:1')


def languages(root):
    values=['two words','','*',"O'Reilly",'line\nnext','a; printf BAD',r'$(printf BAD)']
    code='printf "%s\\0" "$@"'
    r=run([BASH,'--noprofile','--norc','-c',code,'fixed',*values],root)
    check(r.stdout==b''.join(v.encode()+b'\0' for v in values),'fixed code preserves argv')
    # Только фиксированные учебные данные в повторном разборе.
    shell("text='printf FIRST; printf SECOND'; eval \"$text\"",root,out=b'FIRSTSECOND')
    shell("value=$'a b\\n*'; printf -v quoted '%q' \"$value\"; eval \"again=$quoted\"; [[ $again == \"$value\" ]]",root)
    # Модель SSH объединяет аргументы пробелами; реального ssh/соединения нет.
    joined='printf "<%s>\\n" '+' '.join(['two words',''])
    check(run([BASH,'--noprofile','--norc','-c',joined],root).stdout==b'<two>\n<words>\n','second parser loses boundaries')


def report_project(root):
    data=root/'data';data.mkdir()
    expected=[]
    for index,name in enumerate(['a.log','two words.log','line\nnext.log','-leading.log','star*.log']):
        (data/name).write_bytes(b'x'*index)
        expected.append({'path':name,'bytes':index})
    (data/'skip.txt').write_bytes(b'skip')
    (data/'link.log').symlink_to(data/'a.log')
    expected.sort(key=lambda row:os.fsencode(row['path']))
    destination=root/'report.json'
    command=[BASH,'--noprofile','--norc',str(HERE/'collect-report.sh')]
    run(command+['--dry-run',str(data),str(destination)],root)
    check(not destination.exists() and not Path(str(destination)+'.lock').exists(),'dry-run has no output objects')
    run(command+[str(data),str(destination)],root)
    check(json.loads(destination.read_bytes())['records']==expected,'report exact records')
    before=destination.read_bytes()
    run(command+[str(root/'missing'),str(destination)],root,status=1)
    check(destination.read_bytes()==before,'missing input preserves report')
    ps=[subprocess.Popen(command+[str(data),str(destination)],cwd=root,env=ENV,
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
    try:
        for p in ps:
            out,err=p.communicate(timeout=5)
            check(p.returncode==0,repr((out,err)))
        check(destination.read_bytes()==before,'concurrent same report exact bytes')
    finally:
        for p in ps:
            if p.poll() is None:p.kill();p.communicate(timeout=3)
    empty=root/'empty';empty.mkdir()
    run(command+[str(empty),str(destination)],root)
    check(json.loads(destination.read_bytes())['records']==[],'empty set is successful empty report')


GROUPS=[('08',conditions),('09',functions),('10',traps),('11',filenames),
        ('12',text_bytes),('13',processes),('14',scripts),('15',files_concurrency),
        ('16',diagnostics),('17',languages),('18',report_project)]


def main():
    global ENV
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root',required=True,type=Path)
    args=parser.parse_args()
    parent=args.work_root.resolve()
    if not parent.is_dir():parser.error('--work-root должен существовать')
    summaries=[]
    with tempfile.TemporaryDirectory(prefix='bash-remaining-',dir=parent) as temporary:
        root=Path(temporary)
        ENV={'PATH':'/usr/bin:/bin','LC_ALL':'C.UTF-8','TMPDIR':str(root),
             'PYTHONDONTWRITEBYTECODE':'1'}
        versions={}
        for name,argv in [('bash',[BASH,'--noprofile','--norc','--version']),
                          ('python',['python3','--version']),('grep',['grep','--version']),
                          ('find',['find','--version']),('flock',['flock','--version']),
                          ('awk',['awk','-W','version']),('sed',['sed','--version'])]:
            p=subprocess.run(argv,env=ENV,capture_output=True,timeout=3)
            versions[name]=(p.stdout+p.stderr).decode(errors='replace').splitlines()[0]
        for key,func in GROUPS:
            group=root/key;group.mkdir();before=CHECKS;start=len(RESULTS)
            func(group)
            summaries.append({'chapter':key,'status':'PASS','assertions':CHECKS-before,
                              'runs':RESULTS[start:]})
    print(json.dumps({'status':'PASS','groups':summaries,'assertions':CHECKS,
                      'versions':versions,'cleaned':not root.exists(),
                      'limits':'No TTY/startup/network/SQL; simulated faults are labelled, no power-loss test.'},
                     ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
