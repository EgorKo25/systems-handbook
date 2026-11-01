#!/usr/bin/env python3
"""Small bounded closed-loop HTTP experiment for one's own study service."""
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPException, IncompleteRead
import argparse
import json
import math
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


def percentile(samples, percent):
    if not samples:
        return None
    ordered=sorted(samples)
    return ordered[max(0, math.ceil(percent/100*len(ordered))-1)]


def request(url, timeout, expected):
    started=time.perf_counter()
    status=None
    body_bytes_read=0
    error=None
    try:
        try:
            reply=build_opener(NoRedirect()).open(Request(url,headers={'User-Agent':'handbook-study-probe/1'}),timeout=timeout)
        except HTTPError as exc:
            # urllib represents 3xx/4xx/5xx responses as exceptions. They still
            # have a body: use the same measurement boundary as ordinary 2xx.
            reply=exc
        with reply:
            status=reply.status
            body=reply.read(65536)
            body_bytes_read=len(body)
            response=reply.fp if isinstance(reply,HTTPError) else reply
            remaining=getattr(response,'length',None)
            # read(amt) does not itself reject an EOF before Content-Length.
            # Deliberate stopping at the 64 KiB boundary remains valid, but an
            # earlier EOF with advertised bytes outstanding is a protocol error.
            if len(body)<65536 and remaining is not None and remaining>0:
                raise IncompleteRead(body,remaining)
    except HTTPException as exc:
        partial=getattr(exc,'partial',b'')
        if isinstance(partial,(bytes,bytearray)):
            body_bytes_read=max(body_bytes_read,len(partial))
        error='protocol-error'
    except (URLError, TimeoutError, OSError):
        error='transport-error'
    elapsed=(time.perf_counter()-started)*1000
    ok=error is None and status==expected
    return dict(ms=elapsed,status=status,ok=ok,error=None if ok else error or 'unexpected-http-status',
                body_bytes_read=body_bytes_read)


def observe(url, count=20, concurrency=1, timeout=3, expected=200):
    address=urlsplit(url)
    if address.scheme not in {'http','https'} or not address.hostname or address.username or address.password:
        raise ValueError('Use an explicit http(s) URL of your study service, without embedded credentials')
    if not 1<=count<=10000 or not 1<=concurrency<=32 or not 0<timeout<=60:
        raise ValueError('count 1..10000, concurrency 1..32, timeout above0 and at most60s')
    if not isinstance(expected,int) or not 100<=expected<=599:
        raise ValueError('expected HTTP status must be an integer in 100..599')
    started=time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        samples=list(pool.map(lambda _:request(url,timeout,expected), range(count)))
    seconds=time.perf_counter()-started
    successful=[row['ms'] for row in samples if row['ok']]
    statuses={}
    failure_kinds={}
    for row in samples:
        code=str(row['status']) if row['status'] is not None else row['error'] or 'no-http-status'
        statuses[code]=statuses.get(code,0)+1
        if not row['ok']:
            failure_kinds[row['error']]=failure_kinds.get(row['error'],0)+1
    return dict(mode='closed-loop-fixed-concurrency',requests=count,concurrency=concurrency,
                seconds=seconds,completed_per_second=count/seconds,
                successful_per_second=len(successful)/seconds,
                errors=count-len(successful),statuses=statuses,failure_kinds=failure_kinds,
                status_count_scope='received header status, including attempts whose body later failed',
                success_latency_ms={str(p):percentile(successful,p) for p in (50,95,99)},
                percentile_method='nearest-rank; successful requests only',
                response_body_limit_bytes=65536,
                latency_boundary='headers plus up to 65536 response-body bytes; not a complete download for larger responses')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url',help='URL of the explicitly selected personal study service')
    parser.add_argument('--count',type=int,default=20,help='total completed attempts, 1..10000')
    parser.add_argument('--concurrency',type=int,default=1,help='simultaneous workers, 1..32')
    parser.add_argument('--timeout',type=float,default=3,help='per socket operation timeout in seconds, above0..60')
    parser.add_argument('--expected-status',type=int,default=200,help='HTTP status accepted as success')
    args=parser.parse_args()
    try: result=observe(args.url,args.count,args.concurrency,args.timeout,args.expected_status)
    except ValueError as exc:parser.error(str(exc))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
