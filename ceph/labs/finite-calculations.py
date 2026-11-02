# Finite calculations only; no Ceph process, filesystem writes or benchmarks.
from fractions import Fraction
from math import ceil

if not __debug__:
    raise SystemExit("Finite checks require assertions enabled")

def chunks(offset, length, object_size):
    if offset < 0 or length < 0 or object_size <= 0:
        raise ValueError("range")
    result = []
    while length:
        index, within = divmod(offset, object_size)
        count = min(length, object_size - within)
        result.append((index, within, count))
        offset += count
        length -= count
    return result

def percentile(values, p):
    if not values or not 0 < p <= 1:
        raise ValueError("population")
    return sorted(values)[ceil(p*len(values))-1]

def check():
    MiB = 2**20
    GiB = 2**30
    assert chunks(3984588, MiB, 4*MiB) == [(0,3984588,209716),(1,0,838860)]
    assert chunks(4*MiB-4096,8192,4*MiB) == [(0,4*MiB-4096,4096),(1,0,4096)]
    assert chunks(0,0,4096) == []
    for args in [(-1,1,4096),(0,-1,4096),(0,1,0)]:
        try:
            chunks(*args)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid range accepted")
    assert Fraction(80*3,4*128) == Fraction(15,32)
    assert Fraction(80*3,3*128) == Fraction(5,8)
    assert Fraction(3*128*7,10*3) == Fraction(448,5)
    assert Fraction(60*GiB,100*MiB) == Fraction(3072,5)
    assert Fraction(4096+80+160+240,4096) == Fraction(143,128)
    assert 1048576+(4096+(10240-8192)) == 1054720
    assert 1048576 <= 1054720 < 1048576+16384
    samples = [10]*90+[30]*9+[1000]
    assert Fraction(sum(samples),len(samples)) == Fraction(217,10)
    assert percentile(samples,.95) == percentile(samples,.99) == 30
    assert percentile(samples,1) == 1000
    assert (10-8)*60 == 120 and Fraction(120,8) == 15
    print("finite arithmetic passed; no cluster/IO benchmark")

if __name__ == "__main__":
    check()
