#!/usr/bin/env python3
"""Read this book's classic Ethernet/IPv4/TCP PCAP without external packages."""
from pathlib import Path
import socket
import struct
import sys


def checksum(data):
    if len(data) & 1:
        data += b"\0"
    value = sum(struct.unpack("!%dH" % (len(data) // 2), data))
    while value >> 16:
        value = (value & 65535) + (value >> 16)
    return (~value) & 65535


def read_capture(path):
    data = Path(path).read_bytes()
    if len(data) < 24:
        raise ValueError("Нет полного общего заголовка PCAP")
    formats = {b"\xd4\xc3\xb2\xa1": "<", b"\xa1\xb2\xc3\xd4": ">"}
    if data[:4] not in formats:
        raise ValueError("Нужен classic PCAP с микросекундами; PCAPNG не поддерживается")
    endian = formats[data[:4]]
    _, major, minor, _, _, snaplen, linktype = struct.unpack(endian+"IHHIIII", data[:24])
    if (major, minor, linktype) != (2, 4, 1):
        raise ValueError("Нужен PCAP 2.4 с Ethernet (linktype 1)")
    offset, result = 24, []
    while offset < len(data):
        if len(data) - offset < 16:
            raise ValueError("Оборван заголовок записи PCAP")
        sec, usec, size, original = struct.unpack(endian+"IIII", data[offset:offset+16])
        offset += 16
        frame = data[offset:offset+size]
        if len(frame) != size or size > snaplen:
            raise ValueError("Оборван кадр или длина больше snaplen")
        offset += size
        if len(frame) < 34 or frame[12:14] != b"\x08\x00":
            raise ValueError("Ожидался Ethernet II с IPv4 без VLAN")
        ihl = (frame[14] & 15) * 4
        total = int.from_bytes(frame[16:18], "big")
        ip = frame[14:14+total]
        if ihl < 20 or total < ihl + 20 or len(ip) != total:
            raise ValueError("Некорректная длина IPv4/TCP")
        if ip[9] != 6 or int.from_bytes(ip[6:8], "big") & 0x3fff:
            raise ValueError("Этот учебный разборщик ожидает TCP без фрагментации")
        tcp = ip[ihl:]
        thl = (tcp[12] >> 4) * 4
        if not 20 <= thl <= len(tcp):
            raise ValueError("Некорректная длина TCP-заголовка")
        pseudo = ip[12:20] + struct.pack("!BBH", 0, 6, len(tcp))
        flags = tcp[13]
        row = dict(number=len(result)+1, frame_length=size,
                   original_length=original, ip_length=total,
                   ip_checksum_ok=checksum(ip[:ihl]) == 0,
                   tcp_checksum_ok=checksum(pseudo+tcp) == 0,
                   source=socket.inet_ntoa(ip[12:16]),
                   destination=socket.inet_ntoa(ip[16:20]),
                   sport=int.from_bytes(tcp[:2], "big"),
                   dport=int.from_bytes(tcp[2:4], "big"),
                   seq=int.from_bytes(tcp[4:8], "big"),
                   ack=int.from_bytes(tcp[8:12], "big"), flags=flags,
                   flag_names=",".join(name for bit, name in
                       [(2,"SYN"),(16,"ACK"),(8,"PSH"),(1,"FIN"),(4,"RST")]
                       if flags & bit), payload=tcp[thl:],
                   padding_length=len(frame)-14-total)
        result.append(row)
    return result


def verify_example(rows):
    expected = [
        (1000, 0, 2, 0), (9000, 1001, 18, 0),
        (1001, 9001, 16, 0), (1001, 9001, 24, 73),
        (9001, 1074, 16, 0), (9001, 1074, 24, 106),
        (9107, 1074, 17, 0), (1074, 9108, 16, 0),
        (1074, 9108, 17, 0), (9108, 1075, 16, 0)]
    if len(rows) != len(expected):
        raise ValueError("Число кадров не совпало с эталонным примером")
    for row, values in zip(rows, expected):
        actual = (row["seq"], row["ack"], row["flags"], len(row["payload"]))
        if actual != values or not row["ip_checksum_ok"] or not row["tcp_checksum_ok"]:
            raise ValueError("Не прошла проверка кадра %d" % row["number"])
        if row["frame_length"] != max(60, row["ip_length"]+14):
            raise ValueError("Не совпала длина Ethernet")
    request = rows[3]["payload"]
    assert request == (b"GET /api/session HTTP/1.1\r\nHost: app.lab.test:7000\r\n"
                       b"Connection: close\r\n\r\n")
    head, body = rows[5]["payload"].split(b"\r\n\r\n", 1)
    assert b"Content-Length: 16" in head and len(body) == 16


def main():
    args = [arg for arg in sys.argv[1:] if arg != "--verify-example"]
    path = args[0] if args else Path(__file__).with_name("document-flow-http.pcap")
    rows = read_capture(path)
    print("№  откуда:порт -> куда:порт              SEQ   ACK    флаги      данные IP TCP доп.")
    for r in rows:
        print(f'{r["number"]:2} {r["source"]}:{r["sport"]} -> '
              f'{r["destination"]}:{r["dport"]} '
              f'{r["seq"]:5} {r["ack"]:5} {r["flag_names"]:10} '
              f'{len(r["payload"]):3} '
              f'{"OK" if r["ip_checksum_ok"] else "BAD"} '
              f'{"OK" if r["tcp_checksum_ok"] else "BAD"} {r["padding_length"]}')
    if "--verify-example" in sys.argv:
        verify_example(rows)
        print("Проверено: 10 кадров, длины, обе контрольные суммы, SEQ/ACK, HTTP.")
    print("\nТело кадра 4 в виде Python bytes:")
    print(repr(rows[3]["payload"]) if len(rows) >= 4 else "кадра нет")


if __name__ == "__main__":
    main()
