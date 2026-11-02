#!/usr/bin/env python3
"""Pure arithmetic fixtures; no MinIO, network, files, RS or HighwayHash."""
from fractions import Fraction
from math import ceil

def encoded(s, block, n, k, hash_bytes=32):
    if (type(s) is not int or s < 0 or type(block) is not int or block <= 0
            or type(n) is not int or type(k) is not int or not 1 <= k <= n
            or type(hash_bytes) is not int or hash_bytes < 0):
        raise ValueError("Invalid arithmetic profile")
    full, tail = divmod(s, block)
    chunks = full + bool(tail)
    shard_payload = full * ((block + k - 1) // k)
    if tail:
        shard_payload += (tail + k - 1) // k
    shard_stream = shard_payload + chunks * hash_bytes
    return {"chunks": chunks, "shard_payload": shard_payload,
            "shard_stream": shard_stream, "all_streams": n * shard_stream}

def weighted(weights, value):
    if not weights or any(type(w) is not int or w < 0 for w in weights):
        raise ValueError("Invalid weights")
    total = sum(weights)
    if total == 0 or type(value) is not int or not 0 <= value < total:
        raise ValueError("Out of range")
    for index, weight in enumerate(weights):
        if value < weight:
            return index
        value -= weight
    raise AssertionError("Unreachable")

def nearest_rank(values, q):
    if not values or not 0 < q <= 1:
        raise ValueError("Empty distribution or invalid quantile")
    return sorted(values)[ceil(q * len(values)) - 1]

def main():
    mib = 1024 * 1024
    assert encoded(4*mib,mib,4,2) == {
        "chunks":4,"shard_payload":2097152,"shard_stream":2097280,
        "all_streams":8389120}
    a = encoded(mib,mib,8,4)
    z = encoded(mib+1,mib,8,4)
    assert a["all_streams"] == 2097408
    assert z["all_streams"] == 2097672
    assert z["all_streams"]-a["all_streams"] == 264
    assert z["shard_payload"] == 262145
    assert [weighted([20,60],i) for i in range(80)].count(0) == 20
    assert [weighted([20,60],i) for i in range(80)].count(1) == 60
    assert Fraction(20+80,100+100) == Fraction(1,2)
    assert 100*Fraction(1,2)-20 == 30
    x = [1,100]
    y = [2]*98
    assert nearest_rank(x,.99)==100 and nearest_rank(y,.99)==2
    assert nearest_rank(x+y,.99)==2
    assert Fraction(sum(x+y),len(x+y)) == Fraction(297,100)
    for args in [(-1,mib,4,2),(1,0,4,2),(1,mib,4,0),(1,mib,4,5)]:
        try:
            encoded(*args)
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted invalid profile")
    for weights,value in [([0,0],0),([20,60],80),([-1,2],0)]:
        try:
            weighted(weights,value)
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted invalid placement vector")
    print("PASS: arithmetic fixtures only; no native performance result")

if __name__ == "__main__":
    main()
