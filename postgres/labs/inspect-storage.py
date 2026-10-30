#!/usr/bin/env python3
"""Read-only decoder of bundled PostgreSQL 18.6 little-endian teaching files.
No connection to PostgreSQL is opened; no database file is modified.
The WAL inputs are complete records already assembled across page boundaries.
"""
import argparse
import json
from pathlib import Path
import struct


def crc32c(data):
    crc=0xffffffff
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc=(crc>>1)^(0x82f63b78 if crc&1 else 0)
    return crc^0xffffffff


def record(data):
    if len(data)<24:raise ValueError('WAL record shorter than 24 bytes')
    total,xid,previous,info,rmid,padding,stored=struct.unpack('<IIQBBHI',data[:24])
    if total!=len(data):raise ValueError('xl_tot_len differs from complete-record file length')
    calculated=crc32c(data[24:]+data[:20])
    if calculated!=stored:raise ValueError('WAL CRC32C mismatch')
    return {'length':total,'xid':xid,'previous_lsn':f'{previous>>32:X}/{previous&0xffffffff:X}',
            'info':info,'resource_manager':rmid,'padding':padding,
            'crc32c':f'0x{stored:08x}','crc_verified':True,'body_hex':data[24:].hex(' ')}


def page(data):
    if len(data)!=8192:raise ValueError('Example requires one 8192-byte page')
    high,low,checksum,flags,lower,upper,special,version,prune=struct.unpack('<IIHHHHHHI',data[:24])
    if not 24<=lower<=upper<=special<=8192 or (lower-24)%4:raise ValueError('Invalid page boundaries')
    items=[]
    for index,offset in enumerate(range(24,lower,4),1):
        raw=struct.unpack_from('<I',data,offset)[0]
        off=raw&0x7fff;state=(raw>>15)&3;length=(raw>>17)&0x7fff
        item={'lp':index,'offset':off,'state':state,'length':length}
        if state==1:
            if off<upper or off+length>special or length<23:raise ValueError('Invalid heap item')
            xmin,xmax,cid=struct.unpack_from('<III',data,off)
            block_hi,block_lo,pos=struct.unpack_from('<HHH',data,off+12)
            mask2,mask,hoff=struct.unpack_from('<HHB',data,off+18)
            item.update(xmin=xmin,xmax=xmax,cid=cid,ctid=[(block_hi<<16)|block_lo,pos],
                        infomask2=mask2,infomask=mask,hoff=hoff,
                        user_data_hex=data[off+hoff:off+length].hex(' '))
        items.append(item)
    return {'lsn':f'{high:X}/{low:X}','checksum_16bit':checksum,'flags':flags,'lower':lower,
            'upper':upper,'special':special,'page_size':version&0xff00,'layout_version':version&0xff,
            'prune_xid':prune,'free_contiguous_bytes':upper-lower,'items':items}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--page',type=Path)
    parser.add_argument('--wal-record',type=Path)
    parser.add_argument('--bundled',action='store_true',help='decode and verify the saved real observations')
    args=parser.parse_args()
    if args.bundled:
        root=Path(__file__).parent/'observed'
        print(json.dumps({'page':page((root/'page-0.bin').read_bytes()),
                          'insert':record((root/'wal-insert.bin').read_bytes()),
                          'commit':record((root/'wal-commit.bin').read_bytes())},indent=2))
        damaged=bytearray((root/'wal-insert.bin').read_bytes());damaged[-1]^=1
        try:record(bytes(damaged))
        except ValueError:pass
        else:raise AssertionError('Damaged WAL record was accepted')
    elif args.page:print(json.dumps(page(args.page.read_bytes()),indent=2))
    elif args.wal_record:print(json.dumps(record(args.wal_record.read_bytes()),indent=2))
    else:parser.print_help()

if __name__=='__main__':main()
