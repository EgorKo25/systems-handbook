#!/usr/bin/env python3
"""Finite byte decoder and deterministic index arithmetic; no DB, files or network writes."""
import argparse,datetime,json,struct

REQUEST_HEX='330000001100000000000000dd07000000000000001e0000001070696e67000100000002246462000600000061646d696e0000'
REPLY_HEX='260000005a00000011000000dd070000000000000011000000016f6b00000000000000f03f00'

def decode_message(data):
    if len(data)<26:raise ValueError('short selected OP_MSG profile')
    length,request_id,response_to,opcode=struct.unpack_from('<4i',data)
    if length!=len(data) or opcode!=2013:raise ValueError('header length/opcode')
    if struct.unpack_from('<I',data,16)[0]!=0 or data[20]!=0:raise ValueError('example supports flags0 and kind0 only')
    doc_length=struct.unpack_from('<i',data,21)[0]
    end=21+doc_length
    if doc_length<5 or end!=len(data) or data[end-1]!=0:raise ValueError('BSON size/end')
    fields=[];cursor=25
    while cursor<end-1:
        start=cursor;kind=data[cursor];cursor+=1
        zero=data.find(b'\0',cursor,end-1)
        if zero<0:raise ValueError('field name not terminated')
        name=data[cursor:zero].decode('utf8');cursor=zero+1
        if kind==16:
            if cursor+4>end-1:raise ValueError('short int32')
            value=struct.unpack_from('<i',data,cursor)[0];cursor+=4
        elif kind==1:
            if cursor+8>end-1:raise ValueError('short double')
            value=struct.unpack_from('<d',data,cursor)[0];cursor+=8
        elif kind==2:
            if cursor+4>end-1:raise ValueError('short string length')
            n=struct.unpack_from('<i',data,cursor)[0];cursor+=4
            if n<1 or cursor+n>end-1 or data[cursor+n-1]!=0:raise ValueError('string bounds/end')
            value=data[cursor:cursor+n-1].decode('utf8');cursor+=n
        else:raise ValueError('unsupported example BSON type')
        fields.append({'name':name,'type_byte':kind,'value':value,'start':start,'end_inclusive':cursor-1})
    if cursor!=end-1:raise ValueError('BSON element overrun')
    return {'length':length,'requestID':request_id,'responseTo':response_to,'opCode':opcode,'flags':0,'kind':0,'bsonLength':doc_length,'fields':fields}

def seed_index(limit):
    # Independent arithmetic of the published seed; not a query planner or physical B-tree.
    records=[{'i':i,'id':f'seed-{i:06d}','tenant':f'tenant-{i%100:02d}','state':'open','epochSeconds':1700000000+i} for i in range(20000)]
    ordered=sorted(records,key=lambda d:(d['tenant'],d['state'],-d['epochSeconds'],d['id']))
    selected=[d for d in ordered if d['tenant']=='tenant-01' and d['state']=='open']
    for d in selected:d['date']=datetime.datetime.fromtimestamp(d['epochSeconds'],datetime.timezone.utc).isoformat().replace('+00:00','Z')
    assert len(selected)==200
    assert [d['i'] for d in selected[:20]]==list(range(19901,17901,-100))
    assert selected[20]['i']==17901
    splits={boundary:[sum(d['id']<boundary for d in selected),sum(d['id']>=boundary for d in selected)] for boundary in ['seed-010000','seed-015000']}
    assert splits=={'seed-010000':[100,100],'seed-015000':[150,50]}
    # One changed date tests the _id ASC tie break independently of the real dataset.
    tied=[dict(selected[0],epochSeconds=1),dict(selected[1],epochSeconds=1)]
    assert sorted(tied,key=lambda d:(-d['epochSeconds'],d['id']))[0]['id']=='seed-019801'
    return {'totalDocuments':20000,'tenantMatches':len(selected),'modelLimit':limit,'first':selected[0],'lastReturned':selected[limit-1],'nextUnreturned':selected[limit] if limit<len(selected) else None,'selectedIds':[d['id'] for d in selected[:limit]],'modelShardRangeCounts':splits,'logicalWorkInRetainedNativeLimit20':{'nReturned':20,'keysExamined':20,'docsExamined':20},'limits':'Arithmetic only. No B-tree page/IO or live sharding simulation; limit5 prediction is not a new server explain.'}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--limit',type=int,default=20);a=ap.parse_args()
    if not 1<=a.limit<=200:ap.error('limit must be 1..200 in this model')
    request=decode_message(bytes.fromhex(REQUEST_HEX));reply=decode_message(bytes.fromhex(REPLY_HEX))
    assert request['fields']==[{'name':'ping','type_byte':16,'value':1,'start':25,'end_inclusive':34},{'name':'$db','type_byte':2,'value':'admin','start':35,'end_inclusive':49}]
    assert request['length']==51 and request['requestID']==17 and request['bsonLength']==30
    assert reply['length']==38 and reply['responseTo']==request['requestID'] and reply['fields'][0]['value']==1.0
    rejected=0
    for offset,value in [(0,52),(21,31),(50,1),(16,4),(20,1)]:
        bad=bytearray.fromhex(REQUEST_HEX);bad[offset]=value
        try:decode_message(bad)
        except ValueError:rejected+=1
        else:raise AssertionError('corrupt sample accepted')
    assert rejected==5
    print(json.dumps({'kind':'pure educational decoder and seed-index arithmetic, not captured packets/server/latency','request':request,'reply':reply,'rejectedCorruptSamples':rejected,'index':seed_index(a.limit),'passed':True},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
