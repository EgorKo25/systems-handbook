#!/usr/bin/env python3
"""Generate a synthetic Ethernet/IPv4/UDP/DNS capture, without sending traffic.
Python 3.7+, standard library only. Refuses to overwrite existing files.
"""
import argparse
import ipaddress
import struct
from pathlib import Path

def checksum(data):
    if len(data)%2:
        data+=b'\0'
    total=sum(struct.unpack('!'+str(len(data)//2)+'H',data))
    while total>>16:
        total=(total&0xffff)+(total>>16)
    return (~total)&0xffff

parser=argparse.ArgumentParser()
parser.add_argument('output',type=Path)
args=parser.parse_args()
source=ipaddress.IPv4Address('198.18.1.2').packed
destination=ipaddress.IPv4Address('198.18.1.53').packed
dns=struct.pack('!6H',0x1234,0x0100,1,0,0,0)+b'\x04spo1\x03lab\x04test\0'+struct.pack('!2H',1,1)
udp_length=8+len(dns)
udp_zero=struct.pack('!4H',53000,53,udp_length,0)
pseudo=source+destination+struct.pack('!BBH',0,17,udp_length)
udp_sum=checksum(pseudo+udp_zero+dns) or 0xffff
udp=struct.pack('!4H',53000,53,udp_length,udp_sum)
ip_zero=struct.pack('!BBHHHBBH4s4s',0x45,0,20+udp_length,0x4242,0x4000,64,17,0,source,destination)
ip_sum=checksum(ip_zero)
ip=ip_zero[:10]+struct.pack('!H',ip_sum)+ip_zero[12:]
ethernet=bytes.fromhex('0200000000350200000000020800')
frame=ethernet+ip+udp+dns
assert len(dns)==31 and len(ip)==20 and len(frame)==73
assert checksum(ip)==0 and checksum(pseudo+udp+dns)==0
pcap_header=struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,1)
record_header=struct.pack('<IIII',0,0,len(frame),len(frame))
with args.output.open('xb') as output:
    output.write(pcap_header+record_header+frame)
print('Synthetic packet; no traffic sent. Capture timestamp is deliberately zero.')
print('Ethernet 0..13; IPv4 14..33; UDP 34..41; DNS 42..72')
print('IP checksum={:04x}; UDP checksum={:04x}'.format(ip_sum,udp_sum))
for offset in range(0,len(frame),16):
    print('{:04x}  {}'.format(offset,' '.join('{:02x}'.format(b) for b in frame[offset:offset+16])))
