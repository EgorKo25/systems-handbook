#!/usr/bin/env python3
"""Публикация собственных данных: файл→fsync→replace→fsync каталога.
Требуется существующий доверенный каталог назначения на обычной локальной ФС.
Не копирует атрибуты прежнего файла. Выбранный режим нового файла: 0600.
"""
import argparse
import os
from pathlib import Path
import tempfile


def publish(destination: Path, data: bytes, fail_before_replace=False):
    directory = destination.parent
    fd, pending = tempfile.mkstemp(prefix=".pending-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if fail_before_replace:
            raise RuntimeError("учебный отказ до публикации")
        os.replace(pending, destination)
        dir_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        try:
            os.unlink(pending)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("text")
    args = parser.parse_args()
    publish(args.destination, args.text.encode("utf-8"))
