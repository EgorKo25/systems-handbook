#!/usr/bin/env python3
"""Offline deterministic DHCP/DNS teaching frames; never opens a network socket.

python3 control-packets.py --self-test
python3 control-packets.py --out ./control-samples
python3 control-packets.py --decode ./control-samples/dns-answer.bin --kind dns

Generated pcap timestamps are synthetic, not evidence of a running DHCP server.
Only standard-library modules are used. All offsets in DNS refer to DNS payload.
"""
import argparse
import ipaddress
import json
from pathlib import Path
import struct

CLIENT_MAC = bytes.fromhex('020000771064')
GATEWAY_MAC = bytes.fromhex('020000771001')
BROADCAST_MAC = b'\xff' * 6
CLIENT = '10.77.10.100'
GATEWAY = '10.77.10.1'
APP = '10.77.10.20'
XID = 0x77100001
BOOTP = struct.Struct('!BBBBIHH4s4s4s4s16s64s128s')
COOKIE = bytes.fromhex('63825363')
DHCP_NAMES = {1:'DISCOVER', 2:'OFFER', 3:'REQUEST', 4:'DECLINE', 5:'ACK', 6:'NAK', 7:'RELEASE', 8:'INFORM'}


def ipv4(value):
    return ipaddress.IPv4Address(value).packed


def checksum(data):
    """Internet one's-complement checksum, result 0 for valid received data."""
    if len(data) % 2:
        data += b'\x00'
    total = sum(struct.unpack('!' + 'H' * (len(data) // 2), data))
    while total >> 16:
        total = (total & 0xffff) + (total >> 16)
    return (~total) & 0xffff


def tlv(code, value):
    if not 1 <= code <= 254 or len(value) > 255:
        raise ValueError('bad DHCP option')
    return bytes([code, len(value)]) + value


def dhcp_payload(kind):
    server = kind in (2, 5)
    options = [tlv(53, bytes([kind]))]
    if server:
        options += [tlv(61, b'\x01' + CLIENT_MAC), tlv(54, ipv4(GATEWAY)), tlv(51, struct.pack('!I', 3600)),
                    tlv(58, struct.pack('!I', 1800)), tlv(59, struct.pack('!I', 3150)),
                    tlv(1, ipv4('255.255.255.0')), tlv(3, ipv4(GATEWAY)),
                    tlv(6, ipv4(GATEWAY)), tlv(15, b'lab.test')]
    else:
        options += [tlv(61, b'\x01' + CLIENT_MAC), tlv(55, bytes([1,3,6,15,51,58,59]))]
        if kind == 3:
            options += [tlv(50, ipv4(CLIENT)), tlv(54, ipv4(GATEWAY))]
    fixed = BOOTP.pack(2 if server else 1, 1, 6, 0, XID, 0, 0x8000,
                       ipv4('0.0.0.0'), ipv4(CLIENT if server else '0.0.0.0'),
                       ipv4('0.0.0.0'), ipv4('0.0.0.0'), CLIENT_MAC.ljust(16,b'\x00'),
                       b'\x00'*64, b'\x00'*128)
    return (fixed + COOKIE + b''.join(options) + b'\xff').ljust(300, b'\x00')


def decode_dhcp(data):
    if len(data) < 240:
        raise ValueError('DHCP shorter than fixed header and cookie')
    if data[236:240] != COOKIE:
        raise ValueError('DHCP cookie mismatch')
    values = BOOTP.unpack(data[:236])
    result = dict(zip(('op','htype','hlen','hops','xid','secs','flags','ciaddr','yiaddr','siaddr','giaddr','chaddr','sname','file'), values))
    for field in ('ciaddr','yiaddr','siaddr','giaddr'):
        result[field] = str(ipaddress.IPv4Address(result[field]))
    result['chaddr'] = result['chaddr'].hex(':')
    result['sname'] = result['sname'].rstrip(b'\x00').decode('ascii', errors='backslashreplace')
    result['file'] = result['file'].rstrip(b'\x00').decode('ascii', errors='backslashreplace')
    if not 1 <= result['hlen'] <= 16:
        raise ValueError('DHCP hardware address length outside chaddr')
    items, concatenated = [], {}
    offset, ended = 240, False
    while offset < len(data):
        start = offset
        code = data[offset]
        offset += 1
        if code == 0:
            continue
        if code == 255:
            ended = True
            break
        if offset == len(data):
            raise ValueError('DHCP option has no length')
        length = data[offset]
        offset += 1
        if offset + length > len(data):
            raise ValueError('DHCP option exceeds packet')
        value = data[offset:offset+length]
        offset += length
        items.append({'offset':start, 'code':code, 'length':length, 'hex':value.hex()})
        concatenated[code] = concatenated.get(code,b'') + value
    if not ended:
        raise ValueError('DHCP missing end marker')
    if 53 not in concatenated or len(concatenated[53]) != 1:
        raise ValueError('DHCP needs one-byte message type')
    result['message_type'] = DHCP_NAMES.get(concatenated[53][0], 'UNKNOWN')
    result['options'] = items
    result['length'] = len(data)
    return result


def name_bytes(name):
    labels = name.rstrip('.').split('.') if name.rstrip('.') else []
    out = bytearray()
    for label in labels:
        encoded = label.encode('ascii')
        if not 1 <= len(encoded) <= 63:
            raise ValueError('DNS label must have 1..63 octets')
        out.extend(bytes([len(encoded)]) + encoded)
    out.append(0)
    if len(out) > 255:
        raise ValueError('DNS encoded name exceeds 255 octets')
    return bytes(out)


def read_name(packet, start):
    """Return (expanded name, offset after original encoded name).

    Compression jumps are bounded and visited offsets are tracked. The cursor
    consumed by the enclosing RR does not move to the pointer's target.
    """
    labels, visited = [], set()
    pos, after = start, None
    expanded = 1
    for _ in range(128):
        if pos >= len(packet):
            raise ValueError('DNS name crosses packet boundary')
        if pos in visited:
            raise ValueError('DNS compression loop')
        visited.add(pos)
        length = packet[pos]
        if length & 0xc0 == 0xc0:
            if pos + 1 >= len(packet):
                raise ValueError('DNS truncated compression pointer')
            target = ((length & 0x3f) << 8) | packet[pos+1]
            if target >= len(packet):
                raise ValueError('DNS compression target outside packet')
            if after is None:
                after = pos + 2
            pos = target
            continue
        if length & 0xc0:
            raise ValueError('DNS reserved label encoding')
        pos += 1
        if length == 0:
            return '.'.join(labels) + '.', after if after is not None else pos
        if pos + length > len(packet):
            raise ValueError('DNS label crosses packet boundary')
        expanded += length + 1
        if expanded > 255:
            raise ValueError('DNS expanded name exceeds 255 octets')
        labels.append(packet[pos:pos+length].decode('ascii', errors='backslashreplace'))
        pos += length
    raise ValueError('DNS too many compression hops')


def dns_payloads():
    question = name_bytes('app.lab.test') + struct.pack('!HH', 1, 1)
    query = struct.pack('!6H', 0x7710, 0x0100, 1, 0, 0, 0) + question
    # AA=1, RD copied, RA=0. Synthetic authoritative responder; no upstream.
    answer = struct.pack('!6H', 0x7710, 0x8500, 1, 1, 0, 0) + question
    answer += b'\xc0\x0c' + struct.pack('!HHIH', 1, 1, 300, 4) + ipv4(APP)
    return query, answer


def decode_dns(data):
    if len(data) < 12:
        raise ValueError('DNS shorter than 12-byte header')
    ident, flags, qd, an, ns, ar = struct.unpack('!6H', data[:12])
    if qd + an + ns + ar > 2048:
        raise ValueError('DNS excessive item count for teaching decoder')
    result = {'id':ident, 'flags':f'0x{flags:04x}', 'QR':(flags>>15)&1,
              'opcode':(flags>>11)&15, 'AA':(flags>>10)&1, 'TC':(flags>>9)&1,
              'RD':(flags>>8)&1, 'RA':(flags>>7)&1, 'Z':(flags>>6)&1,
              'AD':(flags>>5)&1, 'CD':(flags>>4)&1, 'rcode':flags&15,
              'counts':{'question':qd,'answer':an,'authority':ns,'additional':ar},
              'questions':[], 'answers':[], 'authority':[], 'additional':[]}
    offset = 12
    for _ in range(qd):
        name, offset = read_name(data,offset)
        if offset + 4 > len(data):
            raise ValueError('DNS truncated question')
        qtype, qclass = struct.unpack('!HH', data[offset:offset+4])
        offset += 4
        result['questions'].append({'name':name,'type':qtype,'class':qclass})
    for section, count in (('answers',an),('authority',ns),('additional',ar)):
        for _ in range(count):
            name, offset = read_name(data,offset)
            if offset + 10 > len(data):
                raise ValueError('DNS truncated RR header')
            kind, klass, ttl, length = struct.unpack('!HHIH', data[offset:offset+10])
            offset += 10
            end = offset + length
            if end > len(data):
                raise ValueError('DNS RDATA exceeds packet')
            value = data[offset:end]
            record = {'name':name, 'type':kind, 'class':klass, 'ttl':ttl,
                      'rdlength':length,'rdata_hex':value.hex()}
            if kind == 1:
                if length != 4:
                    raise ValueError('DNS A record length must equal 4')
                record['address'] = str(ipaddress.IPv4Address(value))
            if kind == 28:
                if length != 16:
                    raise ValueError('DNS AAAA record length must equal 16')
                record['address'] = str(ipaddress.IPv6Address(value))
            result[section].append(record)
            offset = end
    if offset != len(data):
        raise ValueError('DNS trailing bytes beyond counted sections')
    result['length'] = len(data)
    return result


def udp_frame(payload, source, target, sport, dport, smac, dmac, ident):
    udp_length = 8 + len(payload)
    udp = struct.pack('!HHHH', sport,dport,udp_length,0) + payload
    pseudo = ipv4(source) + ipv4(target) + struct.pack('!BBH',0,17,udp_length)
    udp_sum = checksum(pseudo+udp) or 0xffff
    udp = udp[:6] + struct.pack('!H',udp_sum) + udp[8:]
    ip = struct.pack('!BBHHHBBH4s4s',0x45,0,20+udp_length,ident,0,64,17,0,ipv4(source),ipv4(target))
    ip = ip[:10] + struct.pack('!H',checksum(ip)) + ip[12:]
    return dmac + smac + b'\x08\x00' + ip + udp


def decode_frame(frame):
    if len(frame) < 42 or frame[12:14] != b'\x08\x00':
        raise ValueError('expected Ethernet IPv4 UDP frame')
    packet = frame[14:]
    ihl = (packet[0]&15)*4
    if packet[0]>>4 != 4 or ihl < 20 or ihl > len(packet):
        raise ValueError('invalid IPv4 header length')
    total = struct.unpack('!H',packet[2:4])[0]
    if total != len(packet) or total < ihl+8:
        raise ValueError('IPv4 total length mismatch')
    if checksum(packet[:ihl]) != 0:
        raise ValueError('IPv4 checksum mismatch')
    if packet[9] != 17 or struct.unpack('!H',packet[6:8])[0]&0x3fff:
        raise ValueError('expected unfragmented UDP')
    udp = packet[ihl:]
    sport, dport, length, received_sum = struct.unpack('!4H',udp[:8])
    if length != len(udp):
        raise ValueError('UDP length mismatch')
    pseudo = packet[12:20] + struct.pack('!BBH',0,17,length)
    if received_sum and checksum(pseudo+udp) != 0:
        raise ValueError('UDP checksum mismatch')
    payload = udp[8:]
    result = {'source_mac':frame[6:12].hex(':'),'target_mac':frame[:6].hex(':'),
              'source_ip':str(ipaddress.IPv4Address(packet[12:16])),
              'target_ip':str(ipaddress.IPv4Address(packet[16:20])),
              'source_port':sport, 'target_port':dport, 'frame_length':len(frame),
              'ip_length':total, 'udp_length':length, 'ip_checksum':'valid',
              'udp_checksum':'valid' if received_sum else 'not supplied'}
    result['payload'] = decode_dhcp(payload) if {sport,dport} == {67,68} else decode_dns(payload)
    return result


def samples():
    result = []
    for index, (name, kind) in enumerate((('dhcp-discover',1),('dhcp-offer',2),('dhcp-request',3),('dhcp-ack',5))):
        server = kind in (2,5)
        payload = dhcp_payload(kind)
        frame = udp_frame(payload,GATEWAY if server else '0.0.0.0','255.255.255.255',
                          67 if server else 68,68 if server else 67,
                          GATEWAY_MAC if server else CLIENT_MAC,BROADCAST_MAC,index+1)
        result.append((name,'dhcp',payload,frame))
    query, answer = dns_payloads()
    result += [('dns-query','dns',query,udp_frame(query,CLIENT,GATEWAY,53000,53,CLIENT_MAC,GATEWAY_MAC,5)),
               ('dns-answer','dns',answer,udp_frame(answer,GATEWAY,CLIENT,53,53000,GATEWAY_MAC,CLIENT_MAC,6))]
    return result


def hexdump(data):
    return '\n'.join(f'{offset:04x}  ' + data[offset:offset+16].hex(' ') for offset in range(0,len(data),16))


def expect_error(function, *args):
    try:
        function(*args)
    except ValueError:
        return
    raise AssertionError(f'{function.__name__} accepted malformed input')


def self_test():
    assert BOOTP.size == 236
    query, answer = dns_payloads()
    # Independent, literal wire representation rather than re-encoding fields.
    assert query.hex() == '77100100000100000000000003617070036c616204746573740000010001'
    assert answer.hex() == '77108500000100010000000003617070036c616204746573740000010001c00c000100010000012c00040a4d0a14'
    assert (len(query),len(answer)) == (30,46)
    decoded = decode_dns(answer)
    assert decoded['answers'][0] == {'name':'app.lab.test.','type':1,'class':1,'ttl':300,'rdlength':4,'rdata_hex':'0a4d0a14','address':APP}
    assert read_name(answer,30) == ('app.lab.test.',32)
    for name, kind, payload, frame in samples():
        result = decode_frame(frame)
        assert result['payload']['length'] == len(payload)
        assert len(frame) == len(payload)+42
        if kind == 'dhcp':
            assert len(payload) == (305 if name in ('dhcp-offer','dhcp-ack') else 300)
            assert result['payload']['xid'] == XID
            opts = {item['code']:bytes.fromhex(item['hex']) for item in result['payload']['options']}
            assert opts[61] == b'\x01' + CLIENT_MAC
            assert payload[28:34] == CLIENT_MAC
        damaged = bytearray(frame)
        damaged[-1] ^= 1
        expect_error(decode_frame,bytes(damaged))
    expect_error(read_name,b'\xc0\x00',0)  # self loop
    expect_error(read_name,b'\xc0\x02\xc0\x00',0)  # two-pointer loop
    expect_error(read_name,b'\xc0',0)
    expect_error(read_name,b'\xc0\xff',0)
    expect_error(read_name,b'\x03ab',0)
    expect_error(read_name,b'\x40',0)
    expect_error(read_name,b'\x3f'+b'a'*63+b'\x3f'+b'b'*63+b'\x3f'+b'c'*63+b'\x3f'+b'd'*63+b'\x00',0)
    expect_error(decode_dns,answer[:-1])
    expect_error(decode_dns,answer+b'\x00')
    expect_error(decode_dhcp,dhcp_payload(1)[:241])
    expect_error(decode_dhcp,b'\x00'*300)
    print('OK: 6 frames; DHCP 236-byte header; literal DNS 30/46 bytes; IP/UDP checksums; 17 damaged or malformed inputs rejected.')


def main():
    parser = argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--out',type=Path)
    parser.add_argument('--decode',type=Path)
    parser.add_argument('--kind',choices=('dhcp','dns','frame'),default='frame')
    args = parser.parse_args()
    if args.self_test:
        self_test()
    if args.out:
        args.out.mkdir(parents=True,exist_ok=True)
        records = []
        pcap = bytearray(struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,1))
        for index, (name,kind,payload,frame) in enumerate(samples()):
            (args.out/(name+'.bin')).write_bytes(payload)
            (args.out/(name+'.frame')).write_bytes(frame)
            (args.out/(name+'.hex.txt')).write_text(hexdump(payload)+'\n',encoding='utf-8')
            record = {'name':name, 'synthetic':True, 'decoded':decode_frame(frame)}
            records.append(record)
            pcap.extend(struct.pack('<IIII',1700000000+index,0,len(frame),len(frame)))
            pcap.extend(frame)
        (args.out/'control-packets.pcap').write_bytes(pcap)
        (args.out/'control-packets.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (args.out/'README.txt').write_text('Синтетические учебные пакеты, не захват живого сервера.\n.bin — полезная нагрузка DHCP/DNS; .frame — кадр Ethernet без FCS; .hex.txt — дамп полезной нагрузки.\nPCAP содержит все 6 кадров, отметки времени условны.\nDNS query 30 bytes; answer 46 bytes; flags answer 0x8500 (QR AA RD, RA=0).\nDHCP client messages 300 bytes including padding; server replies 305 bytes (option 61 echoed per RFC 6842).\n',encoding='utf-8')
        print(f'Wrote 6 synthetic frames to {args.out}')
    if args.decode:
        data = args.decode.read_bytes()
        fn = {'dhcp':decode_dhcp,'dns':decode_dns,'frame':decode_frame}[args.kind]
        print(json.dumps(fn(data),ensure_ascii=False,indent=2))
    if not (args.self_test or args.out or args.decode):
        parser.print_help()


if __name__ == '__main__':
    main()
