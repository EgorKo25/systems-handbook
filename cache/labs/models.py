"""Deterministic teaching experiments, not Redis/Memcached benchmarks."""
from collections import OrderedDict
from pathlib import Path
import json
import math


def run():
    rate, hit, cache_ms, source_ms, fill_ms = 20000, .95, .6, 8, .4
    mean = cache_ms+(1-hit)*(source_ms+fill_ms)
    assert math.isclose(mean,1.02)
    required = 1-(3000-500)/rate
    assert required == .875
    assert math.isclose(rate*mean/1000,20.4)
    events=[]; source=7; cache=None
    read=source; events.append(dict(action='reader obtains',reader=read,source=source,cache=cache))
    source=8; events.append(dict(action='writer commits',reader=read,source=source,cache=cache))
    cache=None; events.append(dict(action='writer invalidates',reader=read,source=source,cache=cache))
    cache=read; events.append(dict(action='reader fills',reader=read,source=source,cache=cache))
    assert cache==7 and source==8
    trace=['A','B','A','C','A','B']; results=[]
    for capacity in [1,2,3]:
        items=OrderedDict(); hits=0
        for key in trace:
            if key in items: hits+=1; items.move_to_end(key)
            else:
                if len(items)==capacity: items.popitem(last=False)
                items[key]=True
        results.append(dict(capacity=capacity,hits=hits,misses=len(trace)-hits))
    assert [r['hits'] for r in results]==[0,2,3]
    # One prescribed simultaneous batch, rather than a timing-dependent thread race.
    fills_without=200; fills_with=1
    assert fills_without/fills_with==200
    return dict(kind='deterministic model, not live server',status='PASS',
        economics=dict(mean_ms=mean,required_hit=required,source_rps=rate*(1-hit)+500,concurrency=rate*mean/1000),
        invalidation_race=events,lru=dict(trace=trace,results=results),
        single_flight=dict(simultaneous_requests=200,without=fills_without,with_local=fills_with),
        memory=dict(bytes=2000000*(900+48+160),gib=2000000*(900+48+160)/2**30))


if __name__=='__main__':
    result=run()
    out=Path(__file__).with_name('model-results.json')
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
