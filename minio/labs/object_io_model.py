from itertools import combinations

def mul(a, b):
    result = 0
    while b:
        if b & 1:
            result ^= a
        b >>= 1
        a <<= 1
        if a & 0x100:
            a ^= 0x11d
    return result

def inv(a):
    if a == 0:
        raise ValueError("zero has no inverse")
    result, base, exponent = 1, a, 254
    while exponent:
        if exponent & 1:
            result = mul(result, base)
        base = mul(base, base)
        exponent >>= 1
    return result

G = ((1, 0), (0, 1), (1, 1), (1, 2))
body, B = b"MinIO!\n", 5
stripes = []
for offset in range(0, len(body), B):
    block = body[offset:offset+B]
    width = (len(block) + 1) // 2
    padded = block + bytes(2*width - len(block))
    x, y = padded[:width], padded[width:]
    shards = [
        bytes(mul(a, u) ^ mul(b, v) for u, v in zip(x, y))
        for a, b in G
    ]
    stripes.append((len(block), shards))
    print([part.hex() for part in shards])

def restore(pair, shards):
    a, b = G[pair[0]]
    c, d = G[pair[1]]
    scale = inv(mul(a, d) ^ mul(b, c))
    left, right = shards[pair[0]], shards[pair[1]]
    x = bytes(mul(scale, mul(d, u) ^ mul(b, v))
              for u, v in zip(left, right))
    y = bytes(mul(scale, mul(c, u) ^ mul(a, v))
              for u, v in zip(left, right))
    return x + y

for pair in combinations(range(4), 2):
    recovered = b"".join(restore(pair, shards)[:length]
                         for length, shards in stripes)
    assert recovered == body
assert mul(3, inv(3)) == 1 and inv(3) == 0xf4
assert all(mul(a, inv(a)) == 1 for a in range(1, 256))
assert sum(len(s) for _, stripe in stripes for s in stripe) == 16
print("6 surviving pairs recover the original 7 bytes")

