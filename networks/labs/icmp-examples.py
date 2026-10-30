#!/usr/bin/env python3
"""Create and inspect synthetic ICMP examples, entirely offline, no privileges.

No traffic is sent. Binary files contain IP packets, not Ethernet frames.
The PCAP uses DLT_RAW=101. --output-dir must name a directory not yet present.
"""
import argparse
import ipaddress
import json
from pathlib import Path
import struct


def checksum(data):
    """Internet checksum, network-order 16-bit words, odd last byte padded."""
    if len(data) % 2:
        data += b"\0"
    total = sum(struct.unpack("!%dH" % (len(data) // 2), data))
    while total >> 16:
        total = (total & 0xffff) + (total >> 16)
    return (~total) & 0xffff


def ip4(src, dst, proto, payload, ident=0x1234, ttl=64, df=False):
    header = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(payload), ident,
                         0x4000 if df else 0, ttl, proto, 0,
                         ipaddress.ip_address(src).packed,
                         ipaddress.ip_address(dst).packed)
    return header[:10] + struct.pack("!H", checksum(header)) + header[12:] + payload


def icmp4(kind, code, rest, body):
    msg = struct.pack("!BBH", kind, code, 0) + rest + body
    return msg[:2] + struct.pack("!H", checksum(msg)) + msg[4:]


def udp4(src, dst, sport, dport, data=b""):
    segment = struct.pack("!HHHH", sport, dport, 8 + len(data), 0) + data
    pseudo = (ipaddress.ip_address(src).packed + ipaddress.ip_address(dst).packed
              + struct.pack("!BBH", 0, 17, len(segment)))
    value = checksum(pseudo + segment) or 0xffff
    return segment[:6] + struct.pack("!H", value) + segment[8:]


def ip6(src, dst, next_header, payload, hop_limit=255):
    return (struct.pack("!IHBB", 6 << 28, len(payload), next_header, hop_limit)
            + ipaddress.ip_address(src).packed
            + ipaddress.ip_address(dst).packed + payload)


def icmp6(src, dst, kind, code, rest):
    msg = struct.pack("!BBH", kind, code, 0) + rest
    pseudo = (ipaddress.ip_address(src).packed + ipaddress.ip_address(dst).packed
              + struct.pack("!I3xB", len(msg), 58))
    return msg[:2] + struct.pack("!H", checksum(pseudo + msg)) + msg[4:]


def examples():
    result = {}
    echo = struct.pack("!HH", 0x1234, 1)
    for name, kind, src, dst in (
            ("echo-request", 8, "192.0.2.10", "198.51.100.20"),
            ("echo-reply", 0, "198.51.100.20", "192.0.2.10")):
        result[name] = ip4(src, dst, 1, icmp4(kind, 0, echo, b"NET!"))
    orig = ip4("192.0.2.10", "198.51.100.20", 17,
               udp4("192.0.2.10", "198.51.100.20", 53000, 33434),
               ident=0x4000, ttl=1, df=True)
    result["quoted-original-udp"] = orig
    for name, kind, code, rest, src in (
            ("port-unreachable", 3, 3, b"\0" * 4, "198.51.100.20"),
            ("ttl-exceeded", 11, 0, b"\0" * 4, "192.0.2.1")):
        result[name] = ip4(src, "192.0.2.10", 1,
                            icmp4(kind, code, rest, orig))
    # A separate large original: quote carries its IP header + first 8 bytes.
    large = ip4("192.0.2.10", "198.51.100.20", 17,
                udp4("192.0.2.10", "198.51.100.20", 53000, 33434,
                     b"X" * 1472), ident=0x4001, ttl=63, df=True)
    result["large-original-udp"] = large
    result["fragmentation-needed"] = ip4("192.0.2.1", "192.0.2.10", 1,
        icmp4(3, 4, struct.pack("!HH", 0, 1400), large[:28]))
    # Error quoting the translated tuple, then the reversed translation.
    external = ip4("198.51.100.2", "203.0.113.9", 17,
        udp4("198.51.100.2", "203.0.113.9", 61000, 33434), ttl=1)
    internal = ip4("10.77.0.10", "203.0.113.9", 17,
        udp4("10.77.0.10", "203.0.113.9", 53000, 33434), ttl=1)
    result["nat-error-before"] = ip4("203.0.113.1", "198.51.100.2", 1,
        icmp4(11, 0, b"\0" * 4, external))
    result["nat-error-after"] = ip4("203.0.113.1", "10.77.0.10", 1,
        icmp4(11, 0, b"\0" * 4, internal))
    src, target, group = "2001:db8:77::10", "2001:db8:77::1", "ff02::1:ff00:1"
    ns_rest = (b"\0" * 4 + ipaddress.ip_address(target).packed
               + bytes.fromhex("01 01 02 00 00 00 00 10"))
    result["ipv6-neighbor-solicitation"] = ip6(src, group, 58,
        icmp6(src, group, 135, 0, ns_rest))
    na_rest = (struct.pack("!I", 0x60000000)
               + ipaddress.ip_address(target).packed
               + bytes.fromhex("02 01 02 00 00 00 00 01"))
    result["ipv6-neighbor-advertisement"] = ip6(target, src, 58,
        icmp6(target, src, 136, 0, na_rest))
    dad_rest = b"\0" * 4 + ipaddress.ip_address(target).packed
    result["ipv6-duplicate-address-probe"] = ip6("::", group, 58,
        icmp6("::", group, 135, 0, dad_rest))
    return result


def hexdump(data):
    return "\n".join(f"{i:04x}  " + data[i:i+16].hex(" ")
                     for i in range(0, len(data), 16))


def inspect(data, quoted=False):
    version = data[0] >> 4
    if version == 4:
        if len(data) < 20:
            raise ValueError("Truncated IPv4 header")
        ihl, total = (data[0] & 15) * 4, struct.unpack("!H", data[2:4])[0]
        assert ihl >= 20 and len(data) >= ihl and checksum(data[:ihl]) == 0
        assert quoted or total == len(data)
        src, dst = str(ipaddress.ip_address(data[12:16])), str(ipaddress.ip_address(data[16:20]))
        proto = data[9]
        info = dict(version=4, src=src, dst=dst, protocol=proto,
                    total_length=total, stored_bytes=len(data), ip_checksum="valid")
        payload = data[ihl:]
        if proto == 1:
            assert len(payload) >= 8 and checksum(payload) == 0
            info.update(type=payload[0], code=payload[1], icmp_checksum="valid")
            if payload[0] in (0, 8):
                info.update(identifier=struct.unpack("!H", payload[4:6])[0],
                            sequence=struct.unpack("!H", payload[6:8])[0],
                            data_hex=payload[8:].hex())
            elif payload[0] in (3, 11):
                info["quoted"] = inspect(payload[8:], quoted=True)
                if payload[:2] == b"\3\4":
                    info["next_hop_mtu"] = struct.unpack("!H", payload[6:8])[0]
        elif proto == 17 and len(payload) >= 8:
            sport, dport, length, value = struct.unpack("!HHHH", payload[:8])
            info.update(source_port=sport, destination_port=dport, udp_length=length)
            if len(payload) >= length:
                pseudo = data[12:20] + struct.pack("!BBH", 0, 17, length)
                assert value and checksum(pseudo + payload[:length]) == 0
                info["udp_checksum"] = "valid"
            else:
                info["udp_checksum"] = "not verifiable: quotation incomplete"
        return info
    if version == 6:
        assert len(data) >= 40
        length = struct.unpack("!H", data[4:6])[0]
        assert len(data) == 40 + length and data[6] == 58
        src, dst = data[8:24], data[24:40]
        payload = data[40:]
        pseudo = src + dst + struct.pack("!I3xB", length, 58)
        assert checksum(pseudo + payload) == 0
        info = dict(version=6, src=str(ipaddress.ip_address(src)),
                    dst=str(ipaddress.ip_address(dst)), payload_length=length,
                    hop_limit=data[7], type=payload[0], code=payload[1],
                    icmp_checksum="valid", target=str(ipaddress.ip_address(payload[8:24])))
        options, pos = [], 24
        while pos < len(payload):
            kind, units = payload[pos:pos+2]
            assert units and pos + units * 8 <= len(payload)
            options.append(dict(type=kind, length_units=units,
                                value_hex=payload[pos+2:pos+units*8].hex()))
            pos += units * 8
        info["options"] = options
        return info
    raise ValueError("Only IPv4/IPv6 examples supported")


def self_test(packets):
    # Internet-checksum example from RFC 1071: the sum is independent of grouping.
    assert checksum(bytes.fromhex("00 01 f2 03 f4 f5 f6 f7")) == 0x220d
    for name, packet in packets.items():
        inspect(packet)
        damaged = bytearray(packet)
        damaged[-1] ^= 1
        try:
            inspect(bytes(damaged))
        except AssertionError:
            pass
        else:
            raise AssertionError("Corruption was not detected: " + name)
    req = packets["echo-request"][20:]
    reply = packets["echo-reply"][20:]
    assert req[4:] == reply[4:] and req[0] == 8 and reply[0] == 0
    assert inspect(packets["fragmentation-needed"])["next_hop_mtu"] == 1400
    before = inspect(packets["nat-error-before"])
    after = inspect(packets["nat-error-after"])
    assert before["quoted"]["source_port"] == 61000
    assert after["quoted"]["source_port"] == 53000
    ns = inspect(packets["ipv6-neighbor-solicitation"])
    assert ns["dst"] == "ff02::1:ff00:1" and ns["options"][0]["type"] == 1
    dad = inspect(packets["ipv6-duplicate-address-probe"])
    assert dad["src"] == "::" and dad["options"] == []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--inspect", type=Path, help="Inspect a .bin generated by this script")
    args = parser.parse_args()
    if args.inspect:
        print(json.dumps(inspect(args.inspect.read_bytes()), ensure_ascii=False, indent=2))
        return
    packets = examples()
    self_test(packets)
    print("PASS: field relationships, checksums, mutations, NAT quotations, IPv6 NS/NA/DAD")
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=False)
        report = {}
        pcap = bytearray(struct.pack("<IHHIIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 101))
        for index, (name, packet) in enumerate(packets.items()):
            (args.output_dir / (name + ".bin")).write_bytes(packet)
            (args.output_dir / (name + ".hex.txt")).write_text(hexdump(packet) + "\n")
            report[name] = inspect(packet)
            pcap += struct.pack("<IIII", 1700000000 + index, 0, len(packet), len(packet)) + packet
        (args.output_dir / "synthetic-icmp.pcap").write_bytes(pcap)
        (args.output_dir / "inspection.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print("Wrote synthetic examples to", args.output_dir)
    else:
        for name in ("echo-request", "echo-reply", "fragmentation-needed", "ipv6-neighbor-solicitation"):
            print("\n" + name + "\n" + hexdump(packets[name]))


if __name__ == "__main__":
    main()
