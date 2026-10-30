#!/usr/bin/env python3
"""Проверка сохранённых образов без PostgreSQL и без интернета.

Только чтение файлов. Формат: PostgreSQL 18.6, x86-64 little-endian,
8192 байта на страницу. WAL-файл здесь содержит одну собранную запись,
а не целый сегмент с заголовками страниц.
Базовые константы алгоритма страницы заимствованы из PostgreSQL;
условия распространения — в соседнем файле POSTGRESQL-LICENSE.txt.
"""
import argparse
import json
from pathlib import Path
import struct
from functools import reduce
from operator import xor

BASE = [
    0x5B1F36E9, 0xB8525960, 0x02AB50AA, 0x1DE66D2A,
    0x79FF467A, 0x9BB9F8A3, 0x217E7CD2, 0x83E13D2C,
    0xF8D4474F, 0xE39EB970, 0x42C6AE16, 0x993216FA,
    0x7B093B5D, 0x98DAFF3C, 0xF718902A, 0x0B1C9CDB,
    0xE58F764B, 0x187636BC, 0x5D7B3BB1, 0xE73DE7DE,
    0x92BEC979, 0xCCA6C0B2, 0x304A0979, 0x85AA43D4,
    0x783125BB, 0x6CA8EAA2, 0xE407EAC6, 0x4B5CFC3E,
    0x9FBF8C76, 0x15CA20BE, 0xF2CA9FD3, 0x959BD756
]

def page_checksum(data, block):
    if len(data) != 8192:
        raise ValueError('В этом опыте страница должна содержать ровно 8192 байта')
    if not 0 <= block <= 0xffffffff:
        raise ValueError('Номер блока должен помещаться в uint32')
    copy = bytearray(data)
    copy[8:10] = b'\0\0'  # Собственное поле суммы исключается.
    words = struct.unpack('<2048I', copy)
    sums = list(BASE)
    # 32 независимые дорожки; каждая получает по одному слову за проход.
    for row in range(64):
        for lane in range(32):
            t = sums[lane] ^ words[row * 32 + lane]
            sums[lane] = ((t * 16777619) ^ (t >> 17)) & 0xffffffff
    # Два заключительных прохода с нулевыми значениями.
    for unused in range(2):
        for lane in range(32):
            t = sums[lane]
            sums[lane] = ((t * 16777619) ^ (t >> 17)) & 0xffffffff
    value = reduce(xor, sums, 0) ^ block
    return value % 65535 + 1

def crc32c(data):
    value = 0xffffffff
    for byte in data:
        value ^= byte
        for unused in range(8):
            value = (value >> 1) ^ (0x82f63b78 if value & 1 else 0)
    return value ^ 0xffffffff

def inspect_page(path, block):
    data = path.read_bytes()
    high, low, stored, flags, lower, upper, special, version, prune = struct.unpack_from('<IIHHHHHHI', data)
    calculated = page_checksum(data, block)
    changed = bytearray(data); changed[128] ^= 1
    return dict(file=path.name, block=block, bytes=len(data), lsn=f'{high:X}/{low:X}',
                lower=lower, upper=upper, special=special,
                checksum_stored=stored, checksum_calculated=calculated,
                matches=stored == calculated,
                one_bit_changed_checksum=page_checksum(changed, block))

def inspect_wal(path):
    data = path.read_bytes()
    length, xid, previous, info, manager, stored = struct.unpack_from('<IIQBB2xI', data)
    if length != len(data):
        raise ValueError('Нужна одна собранная запись без заголовков страниц WAL')
    calculated = crc32c(data[24:] + data[:20])
    changed = bytearray(data); changed[-1] ^= 1
    return dict(file=path.name, bytes=length, xid=xid,
                previous=f'{previous >> 32:X}/{previous & 0xffffffff:X}',
                info=info, resource_manager=manager, crc_stored=hex(stored),
                crc_calculated=hex(calculated), matches=stored == calculated,
                one_bit_changed_crc=hex(crc32c(changed[24:] + changed[:20])))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true', help='прочитать три приложенных образа')
    parser.add_argument('--page', type=Path, help='отдельный образ страницы 8192 байта')
    parser.add_argument('--block', type=int, default=0, help='настоящий номер блока страницы')
    parser.add_argument('--wal', type=Path, action='append', default=[], help='одна собранная запись WAL')
    args = parser.parse_args()
    if not args.demo and args.page is None and not args.wal:
        parser.print_help(); return
    if args.demo:
        folder=Path(__file__).resolve().parent
        args.page=folder/'page-0.bin'
        args.wal=[folder/'wal-insert.bin',folder/'wal-commit.bin']
    results=[]
    if args.page is not None:results.append(inspect_page(args.page,args.block))
    results.extend(inspect_wal(path) for path in args.wal)
    print(json.dumps(results,ensure_ascii=False,indent=2))
    if not all(r['matches'] for r in results):raise SystemExit(1)

if __name__ == '__main__':main()
