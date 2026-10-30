#!/usr/bin/env python3
"""Read the supplied Ethernet/ARP example; no network access or dependencies."""
import argparse
from pathlib import Path
import socket
import struct

CLIENT = bytes.fromhex('020000000010')
GATEWAY = bytes.fromhex('020000000001')
CLIENT_IP = socket.inet_aton('192.0.2.10')
GATEWAY_IP = socket.inet_aton('192.0.2.1')

def frames():
    request = b'\xff' * 6 + CLIENT + struct.pack('!H', 0x0806)
    request += struct.pack('!HHBBH', 1, 0x0800, 6, 4, 1)
    request += CLIENT + CLIENT_IP + b'\0' * 6 + GATEWAY_IP
    reply = CLIENT + GATEWAY + struct.pack('!H', 0x0806)
    reply += struct.pack('!HHBBH', 1, 0x0800, 6, 4, 2)
    reply += GATEWAY + GATEWAY_IP + CLIENT + CLIENT_IP
    return [f.ljust(60, b'\0') for f in (request, reply)]

def capture():
    data = struct.pack('<IHHIIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1)
    for n, frame in enumerate(frames()):
        data += struct.pack('<IIII', 1, n * 1000, len(frame), len(frame)) + frame
    return data

def mac(value):
    return ':'.join(f'{n:02x}' for n in value)

def inspect(path):
    data = path.read_bytes()
    if len(data) < 24 or struct.unpack_from('<IHHIIII', data) != (0xa1b2c3d4, 2, 4, 0, 0, 65535, 1):
        raise ValueError('Expected supplied little-endian Ethernet PCAP')
    pos = 24
    count = 0
    while pos < len(data):
        if len(data) - pos < 16:
            raise ValueError('Incomplete record header')
        seconds, micros, included, original = struct.unpack_from('<IIII', data, pos)
        pos += 16
        frame = data[pos:pos+included]
        pos += included
        if len(frame) != included or included != original or len(frame) < 42:
            raise ValueError('Incomplete or unsupported frame')
        if frame[12:14] != b'\x08\x06':
            raise ValueError('Expected ARP EtherType')
        hardware, protocol, hlen, plen, operation = struct.unpack_from('!HHBBH', frame, 14)
        if (hardware, protocol, hlen, plen) != (1, 0x0800, 6, 4) or operation not in (1, 2):
            raise ValueError('Expected Ethernet/IPv4 ARP request/reply')
        count += 1
        print(f'Кадр {count}: {included} байт; операция {operation} ({"запрос" if operation == 1 else "ответ"})')
        print(f'  Ethernet: {mac(frame[6:12])} → {mac(frame[0:6])}; тип 0x0806')
        print(f'  Отправитель ARP: {socket.inet_ntoa(frame[28:32])} / {mac(frame[22:28])}')
        print(f'  Цель ARP: {socket.inet_ntoa(frame[38:42])} / {mac(frame[32:38])}')
        print(f'  ARP: 28 байт; дополнение Ethernet: {len(frame)-42} байт; FCS в записи отсутствует')
        for start in range(0, len(frame), 16):
            print(f'  {start:04x}  {frame[start:start+16].hex(" ")}')
    return count

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Автономный разбор учебного ARP; сеть не используется')
    parser.add_argument('pcap', nargs='?', type=Path, default=Path(__file__).with_name('arp-request-reply.pcap'))
    parser.add_argument('--write-example', type=Path, help='Записать пример в новый файл, не перезаписывая существующий')
    args = parser.parse_args()
    if args.write_example:
        with args.write_example.open('xb') as f:
            f.write(capture())
        print(args.write_example)
    else:
        inspect(args.pcap)
