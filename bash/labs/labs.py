#!/usr/bin/env python3
"""18 автономных опытов Bash. Все создаваемые данные живут в TemporaryDirectory.
Запуск: python3 labs.py [01 ... 18]. Нужны bash, Python 3, GNU coreutils,
findutils, grep, awk и flock (util-linux). Службы и интернет не используются.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CHECKS = 0
RESULTS = []


def verify(condition, message):
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(message)


def shell(code, cwd, *, expected=0, env=None):
    process_env = os.environ.copy()
    for name in ("BASH_ENV", "ENV", "SHELLOPTS", "BASHOPTS", "CDPATH", "GLOBIGNORE"):
        process_env.pop(name, None)
    process_env.update({"LC_ALL": "C.UTF-8", "LAB": str(HERE)})
    if env:
        process_env.update(env)
    result = subprocess.run(["bash", "--noprofile", "--norc", "-c", code], cwd=cwd,
                            env=process_env, capture_output=True, timeout=20)
    verify(result.returncode == expected,
           f"Ожидался статус {expected}, получен {result.returncode}:\n"
           f"{code}\nstdout={result.stdout!r}\nstderr={result.stderr!r}")
    return result


def eq(result, expected, note="точные байты stdout"):
    verify(result.stdout == expected, f"{note}: {result.stdout!r} != {expected!r}")


def lab01(root):
    """Процесс, собственная переменная и окружение"""
    code = r'''unset item
item=parent
bash -c 'printf "%s\n" "${item-absent}"'
export item
bash -c 'item=child; printf "%s\n" "$item"'
printf '%s\n' "$item"
item=once bash -c 'printf "%s\n" "$item"'
printf '%s\n' "$item"
'''
    eq(shell(code, root), b"absent\nchild\nparent\nonce\nparent\n")
    eq(shell("here=$PWD; (cd /; :); [[ $PWD == \"$here\" ]]; printf preserved", root), b"preserved")
    r = shell(r'''printf '%s\n' "$$"; exec bash -c 'printf "%s\n" "$$"' ''', root)
    lines = r.stdout.splitlines()
    verify(len(lines) == 2 and lines[0] == lines[1], "exec сохранил PID")


def lab02(root):
    """Временный HOME и выбор стартовых файлов"""
    home = root / "home"
    home.mkdir()
    (home / ".bashrc").write_text("printf 'RC\\n'\n")
    (home / ".bash_profile").write_text("printf 'PROFILE\\n'\n")
    (home / ".bash_login").write_text("printf 'LOGIN\\n'\n")
    (home / ".profile").write_text("printf 'DOTPROFILE\\n'\n")
    # Дистрибутив может дополнительно читать /etc/bash.bashrc и печатать
    # системную подсказку. Проверяем собственный маркер и его порядок,
    # не объявляя произвольную системную настройку частью ожидаемого вывода.
    result = shell("bash --noprofile -ic 'printf BODY' 2>/dev/null", root,
                   env={"HOME": str(home)})
    verify(result.stdout.endswith(b"RC\nBODY"), "пользовательский .bashrc прочитан до команды")
    verify(result.stdout.count(b"RC\n") == 1, ".bashrc прочитан один раз")
    eq(shell("bash --noprofile --norc -c 'printf BODY'", root,
             env={"HOME": str(home)}), b"BODY")
    hook = root / "startup-hook"
    hook.write_text("printf 'ENVHOOK\\n'\n")
    eq(shell("bash --noprofile --norc -c 'printf BODY'", root,
             env={"BASH_ENV": str(hook), "HOME": str(home)}), b"ENVHOOK\nENVHOOK\nBODY")
    # Два hook: внешний тестовый bash и запущенная им дочерняя Bash.
    eq(shell("shopt -q login_shell; printf '%s' \"$?\"", root), b"1")


def lab03(root):
    """Аргументы как точные отдельные байтовые строки"""
    r = shell(r'''python3 "$LAB/argv_dump.py" 'two words' '' '*' $'line\nnext' 'a\b' ''', root)
    data = json.loads(r.stdout)
    verify([x["text"] for x in data] == ["two words", "", "*", "line\nnext", "a\\b"], "argv без потери границ")
    verify([x["bytes"] for x in data] == [9, 0, 1, 9, 3], "точные длины")
    r = shell(r'''value='a; printf BAD'; python3 "$LAB/argv_dump.py" "$value" ''', root)
    verify(json.loads(r.stdout)[0]["text"] == "a; printf BAD", "точка с запятой осталась данными")


def lab04(root):
    """Разбиение слов и раскрытие имён"""
    for name in ("b1", "b2"):
        (root / name).touch()
    r = shell(r'''v='a b*'; python3 "$LAB/argv_dump.py" $v ''', root)
    verify([x["text"] for x in json.loads(r.stdout)] == ["a", "b1", "b2"], "split затем glob")
    r = shell(r'''v='a b*'; python3 "$LAB/argv_dump.py" "$v" ''', root)
    verify([x["text"] for x in json.loads(r.stdout)] == ["a b*"], "двойные кавычки сохранили значение")
    eq(shell(r'''printf '<%s>\n' missing*.xyz''', root), b"<missing*.xyz>\n")
    r = shell(r'''shopt -s nullglob; a=(missing*.xyz); printf '%s' "${#a[@]}"''', root)
    eq(r, b"0")
    shell(r'''shopt -s failglob; printf '%s' missing*.xyz''', root, expected=1)
    eq(shell(r'''n=3; printf '%s' {1..$n}''', root), b"{1..3}")


def lab05(root):
    """Unset, пустота, позиционные параметры и подстановка команды"""
    eq(shell(r'''unset x; printf '<%s>|<%s>\n' "${x-A}" "${x:-B}"
x=; printf '<%s>|<%s>\n' "${x-A}" "${x:-B}"
x=$(printf 'a\n\n'); printf '<%s>\n' "$x"
''', root), b"<A>|<B>\n<>|<B>\n<a>\n")
    r = shell(r'''set -- 'a b' '' '*'; python3 "$LAB/argv_dump.py" "$@"''', root)
    verify([x["text"] for x in json.loads(r.stdout)] == ["a b", "", "*"], "$@ сохранил элементы")
    r = shell(r'''set -- 'a b' '' '*'; python3 "$LAB/argv_dump.py" "$*"''', root)
    verify([x["text"] for x in json.loads(r.stdout)] == ["a b  *"], "$* объединил значения")
    shell("x=$(false)", root, expected=1)
    eq(shell("f() { local x=$(false); printf '%s' \"$?\"; }; f", root), b"0")


def lab06(root):
    """Порядок дескрипторов и усечение"""
    producer = "printf 'OUT\\n'; printf 'ERR\\n' >&2"
    r = shell("{ " + producer + "; } >all 2>&1", root)
    eq(r, b"")
    verify((root / "all").read_bytes() == b"OUT\nERR\n", "оба потока в all")
    r = shell("{ " + producer + "; } 2>&1 >out", root)
    eq(r, b"ERR\n")
    verify((root / "out").read_bytes() == b"OUT\n", "только stdout в out")
    (root / "data").write_bytes(b"original\n")
    shell("cat data >data", root)
    verify((root / "data").read_bytes() == b"", "усечение до чтения")
    r = shell("exec {fd}>extra; printf 'channel' >&\"$fd\"; exec {fd}>&-", root)
    verify((root / "extra").read_bytes() == b"channel", "выделенный FD")


def lab07(root):
    """PIPESTATUS, pipefail, подоболочка и EOF"""
    eq(shell(r'''bash -c 'exit 7' | bash -c 'exit 0'
rc=$? stages=("${PIPESTATUS[@]}")
printf '%s:%s:%s' "$rc" "${stages[0]}" "${stages[1]}"''', root), b"0:7:0")
    eq(shell(r'''set -o pipefail
bash -c 'exit 7' | bash -c 'exit 0'
rc=$? stages=("${PIPESTATUS[@]}")
printf '%s:%s:%s' "$rc" "${stages[0]}" "${stages[1]}"''', root), b"7:7:0")
    eq(shell(r'''n=0; printf 'a\nb\n' | while IFS= read -r line; do ((n+=1)); done
printf '%s' "$n"''', root), b"0")
    eq(shell(r'''n=0; while IFS= read -r line; do ((n+=1)); done < <(printf 'a\nb\n')
printf '%s' "$n"''', root), b"2")
    eq(shell(r'''set +m; shopt -s lastpipe; n=0
printf 'a\nb\n' | while IFS= read -r line; do ((n+=1)); done
printf '%s' "$n"''', root), b"2")
    # Проверяем EOF без временного ожидания: чтение неблокирующее.
    read_fd, write_fd = os.pipe()
    duplicate = os.dup(write_fd)
    try:
        os.set_blocking(read_fd, False)
        os.close(write_fd)
        try:
            os.read(read_fd, 1)
        except BlockingIOError:
            verify(True, "пока ещё есть writer, EOF отсутствует")
        else:
            verify(False, "EOF пришёл до закрытия последнего writer")
        os.close(duplicate)
        duplicate = None
        verify(os.read(read_fd, 1) == b"", "EOF после последнего закрытия")
    finally:
        os.close(read_fd)
        if duplicate is not None:
            os.close(duplicate)


def lab08(root):
    """Условия, выражения и последняя незавершённая строка"""
    eq(shell(r'''x='two words'
[[ $x == two* ]]; printf '%s:' "$?"
[[ $x == 'two*' ]]; printf '%s:' "$?"
re='^port=([0-9]+)$'; [[ port=5432 =~ $re ]]; printf '%s:' "${BASH_REMATCH[1]}"
n=0; ((n++)); printf '%s:%s' "$?" "$n"''', root), b"0:1:5432:1:1")
    (root / "input").write_bytes(b" a \\ b\nlast")
    r = shell(r'''while IFS= read -r line || [[ -n $line ]]; do
printf '<%s>\n' "$line"
done <input''', root)
    eq(r, b"< a \\ b>\n<last>\n")
    eq(shell(r'''x=; [ -n $x ]; printf '%s:' "$?"; [ -n "$x" ]; printf '%s' "$?"''', root), b"0:1")


def lab09(root):
    """Функции, динамическая область и массивы"""
    eq(shell(r'''inner() { printf '%s:' "$color"; }
outer() { local color=blue; inner; }
color=red; outer; printf '%s' "$color"''', root), b"blue:red")
    eq(shell(r'''a=(); a[5]='x'; printf '%s:%s' "${#a[@]}" "${!a[@]}"''', root), b"1:5")
    r = shell(r'''build() { local -n ref=$1; ref=('a b' '' '*'); }
a=(); build a; python3 "$LAB/argv_dump.py" "${a[@]}"''', root)
    verify([x["text"] for x in json.loads(r.stdout)] == ["a b", "", "*"], "nameref и массив")
    eq(shell(r'''n=0; f() { n=9; printf ok; }; result=$(f); printf '%s:%s' "$n" "$result"''', root), b"0:ok")


def lab10(root):
    """Errexit: контексты и наследование"""
    eq(shell("set -e; false; printf BAD", root, expected=1), b"")
    eq(shell("set -e; if false; then :; fi; printf OK", root), b"OK")
    eq(shell("set -e; f() { false; printf CONTINUE; }; if f; then printf SUCCESS; fi", root), b"CONTINUESUCCESS")
    eq(shell("set -e; x=$(false; printf OK); printf '%s' \"$x\"", root), b"OK")
    eq(shell("set -e; shopt -s inherit_errexit; x=$(false; printf BAD); printf BAD", root, expected=1), b"")
    eq(shell("set -e; n=0; ((n++)); printf BAD", root, expected=1), b"")
    eq(shell("set -e; n=0; n=$((n+1)); printf '%s' \"$n\"", root), b"1")


def lab11(root):
    """Сложные имена и нулевые разделители"""
    data = root / "data"
    data.mkdir()
    names = ["two words", "line\nnext", "*literal", "-leading", "back\\slash"]
    for name in names:
        (data / name).touch()
    r = shell(r'''find ./data -type f -print0 >list
while IFS= read -r -d '' f; do printf '%s\0' "$f"; done <list''', root)
    actual = set(r.stdout.split(b"\0")[:-1])
    verify(actual == {os.fsencode("./data/" + n) for n in names}, "все имена целиком")
    verify(len(actual) == 5, "ровно пять файлов")


def lab12(root):
    """Байты, строки, сортировка и соседние дубликаты"""
    eq(shell("printf 'Я\\n' | wc -c", root), b"3\n")
    eq(shell("printf 'Я\\n' | wc -m", root), b"2\n")
    eq(shell("printf last | wc -l", root), b"0\n")
    eq(shell("printf 'a\\nb\\na\\n' | uniq", root), b"a\nb\na\n")
    eq(shell("printf 'a\\nb\\na\\n' | LC_ALL=C sort | uniq", root), b"a\nb\n")
    eq(shell("printf '2\\n10\\n' | LC_ALL=C sort", root), b"10\n2\n")
    eq(shell("printf '2\\n10\\n' | LC_ALL=C sort -n", root), b"2\n10\n")


def lab13(root):
    """Собственный ребёнок, wait и TERM"""
    eq(shell("bash -c 'exit 7' & p=$!; wait \"$p\"; printf '%s' \"$?\"", root), b"7")
    code = r'''bash -c 'trap '\''printf STOP; exit 0'\'' TERM; printf ready >ready; while :; do sleep 0.02; done' &
p=$!
for ((i=0;i<200;i++)); do [[ -f ready ]] && break; sleep 0.01; done
if [[ ! -f ready ]]; then kill -TERM "$p"; wait "$p"; exit 1; fi
kill -TERM "$p"
wait "$p"
'''
    eq(shell(code, root), b"STOP")


def lab14(root):
    """Интерпретатор, source и CRLF"""
    script = root / "task"
    script.write_text("#!/bin/bash\nprintf 'script\\n'\nvalue=changed\n")
    script.chmod(0o700)
    eq(shell("value=parent; ./task; printf '%s' \"$value\"", root), b"script\nparent")
    eq(shell("value=parent; source ./task; printf '%s' \"$value\"", root), b"script\nchanged")
    crlf = root / "crlf"
    crlf.write_bytes(b"#!/bin/bash\r\nprintf ok\r\n")
    crlf.chmod(0o700)
    r = shell("./crlf", root, expected=127)
    verify(bool(r.stderr), "диагностика невозможного CRLF-интерпретатора")


def lab15(root):
    """Согласованное обновление под flock"""
    verify(shutil.which("flock") is not None, "нужна flock из util-linux")
    (root / "counter").write_text("0\n")
    code = r'''update() {
exec {fd}>counter.lock || return
flock -x "$fd" || return
IFS= read -r n <counter || return
printf '%s\n' "$((n+1))" >counter || return
exec {fd}>&-
}
pids=()
for ((i=0;i<12;i++)); do update & pids+=("$!"); done
failed=0
for p in "${pids[@]}"; do wait "$p" || failed=1; done
((failed==0)) || exit 1
cat counter
'''
    eq(shell(code, root), b"12\n")


def lab16(root):
    """Публикация, искусственный отказ и fsync"""
    spec = importlib.util.spec_from_file_location("atomic_publish", HERE / "atomic_publish.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    destination = root / "report"
    destination.write_bytes(b"old\n")
    try:
        module.publish(destination, b"partial\n", fail_before_replace=True)
    except RuntimeError:
        pass
    else:
        verify(False, "ожидался учебный отказ")
    verify(destination.read_bytes() == b"old\n", "до публикации старый файл цел")
    verify(not list(root.glob(".pending-*")), "временный файл убран")
    module.publish(destination, b"new\n")
    verify(destination.read_bytes() == b"new\n", "новая версия опубликована")


def lab17(root):
    """Частичный вывод, синтаксис и отделённая трассировка"""
    eq(shell(r'''produce() { printf partial; return 7; }
if value=$(produce); then exit 1; else rc=$?; printf '%s:%s' "$rc" "$value"; fi''', root), b"7:partial")
    (root / "bad.sh").write_text("if true; then\nprintf missing-fi\n")
    shell("bash -n bad.sh", root, expected=2)
    code = r'''exec {tracefd}>trace.log
BASH_XTRACEFD=$tracefd
PS4='+ ${LINENO}: '
set -x
printf 'useful\n'
set +x
unset BASH_XTRACEFD
'''
    eq(shell(code, root), b"useful\n")
    verify(b"printf" in (root / "trace.log").read_bytes(), "трассировка в отдельном файле")


def lab18(root):
    """Граница между данными и вторым разбором кода"""
    eq(shell(r'''text='a; printf SECOND'
printf '%s' "$text"''', root), b"a; printf SECOND")
    # Eval ниже получает только неизменяемый учебный литерал, не внешний ввод.
    eq(shell(r'''text='printf FIRST; printf SECOND'; eval "$text"''', root), b"FIRSTSECOND")
    eq(shell(r'''needle='a.b'; printf 'aXb\na.b\n' | grep -F -- "$needle"''', root), b"a.b\n")
    eq(shell(r'''needle='a.b'; printf 'aXb\na.b\n' | grep -- "$needle"''', root), b"aXb\na.b\n")


LABS = [lab01, lab02, lab03, lab04, lab05, lab06, lab07, lab08, lab09,
        lab10, lab11, lab12, lab13, lab14, lab15, lab16, lab17, lab18]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("numbers", nargs="*", type=int)
    parser.add_argument("--json", action="store_true", help="вывести итог как JSON")
    args = parser.parse_args()
    selected = args.numbers or list(range(1, 19))
    if any(n < 1 or n > 18 for n in selected):
        parser.error("Номера опытов: от 1 до 18")
    version = subprocess.run(["bash", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    failures = []
    for number in selected:
        func = LABS[number - 1]
        before = CHECKS
        try:
            with tempfile.TemporaryDirectory(prefix=f"bash-book-{number:02d}-") as tmp:
                func(Path(tmp))
            state = "PASS"
            detail = ""
        except Exception as error:
            state = "FAIL"
            detail = str(error)
            failures.append(number)
        RESULTS.append({"number": number, "title": func.__doc__, "status": state,
                        "checks": CHECKS - before, "detail": detail})
        if not args.json:
            print(f"{state} {number:02d}. {func.__doc__}: {CHECKS - before} проверок")
            if detail:
                print(detail)
    if args.json:
        print(json.dumps({"bash": version, "python": sys.version, "checks": CHECKS,
                          "results": RESULTS}, ensure_ascii=False, indent=2))
    else:
        print(f"\n{version}\nPython {sys.version.split()[0]}\nПроверок: {CHECKS}; отказов: {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
