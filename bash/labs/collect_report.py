#!/usr/bin/env python3
"""Отчёт о .log в доверенном дереве, без следования ссылкам.
Результат: JSON с именами относительно входа и размерами, сортировка по байтам.
Принимает собственное неизменяемое дерево: это не согласованный снимок ФС.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import sys
from atomic_publish import publish


def make_report(directory: Path):
    records = []

    def fail(error):
        raise error

    for current, directories, filenames in os.walk(directory, followlinks=False, onerror=fail):
        directories[:] = [name for name in directories
                           if not (Path(current) / name).is_symlink()]
        for name in filenames:
            if not name.endswith(".log"):
                continue
            file = Path(current) / name
            info = file.lstat()
            if not stat.S_ISREG(info.st_mode):
                continue
            records.append({"path": str(file.relative_to(directory)), "bytes": info.st_size})
    records.sort(key=lambda record: os.fsencode(record["path"]))
    # ensure_ascii=True также представляет байты имён, декодированные Python
    # через surrogateescape, без требования их печатной корректности в UTF-8.
    return (json.dumps({"format": 1, "records": records}, ensure_ascii=True, indent=2) + "\n").encode("ascii")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if not args.directory.is_dir():
        parser.error("нет входного каталога")
    try:
        report = make_report(args.directory)
        publish(args.destination, report)
    except OSError as error:
        print(f"Ошибка файловой операции: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
