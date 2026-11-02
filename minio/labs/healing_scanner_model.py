"""Teaching model: selection, per-target publication and byte accounting.
No MinIO calls, sockets, files, HighwayHash or xxhash implementation.
"""
from math import ceil

MiB = 1 << 20
S, B, K, N, H = 4 * MiB, MiB, 2, 4, 32
blocks = [min(B, S - offset) for offset in range(0, S, B)]
widths = [ceil(length / K) for length in blocks]
payload = sum(widths)
hash_bytes = len(blocks) * H
stream = payload + hash_bytes
assert blocks == [MiB] * 4
assert widths == [MiB // 2] * 4
assert payload == 2 * MiB and hash_bytes == 128
assert N * stream == 8389120

# E4 is available but has no V. E3's last chunk has a bad hash.
deep_reads = 3 * stream
source_reads = K * stream
target_writes = 2 * stream
network = source_reads + stream  # healer D; E1/E2 remote; E3 remote; E4 local
assert deep_reads == 6291840
assert source_reads == target_writes == 4194560
assert deep_reads + source_reads + target_writes == 14680960
assert network == 6291840
assert 2 * source_reads == 8389120  # repair sources plus one foreground GET
assert source_reads + stream == 6291840  # another pass, only E3 is target
assert 3*4 + 2*4 + 2*4 == 28  # chunk hashes computed

def cycle_mode(config, cycle, start_cycle, elapsed):
    if config == -1:
        return "normal"
    if config == 0:
        return "deep"
    return "deep" if cycle - start_cycle < 1024 or elapsed > config else "normal"

assert cycle_mode(-1, 0, 0, 0) == "normal"
assert cycle_mode(0, 5000, 0, 0) == "deep"
assert cycle_mode(100, 1023, 0, 0) == "deep"
assert cycle_mode(100, 1024, 0, 100) == "normal"
assert cycle_mode(100, 1024, 0, 101) == "deep"

def selected(hash64, cycle, compact=False, skip=False):
    # hash64 is a supplied synthetic xxhash result, not calculated from a key.
    low = hash64 & 0xffffffff
    high = (hash64 >> 32) & 0xffffffff
    divisor = 16 if compact else 1
    if skip or (compact and low % 16 != cycle % 16):
        return False
    return high % (1024 // divisor) == (cycle // divisor) % (1024 // divisor)

fake_hash = (93 << 32) | 37
ordinary = [c for c in range(1024) if selected(fake_hash, c)]
compacted = [c for c in range(1024) if selected(fake_hash, c, compact=True)]
assert ordinary == [93] and compacted == [469]
assert not selected(fake_hash, 93, skip=True)

def publish(before, close_results, rename_results, decode_error=False):
    # Only observable return values are modeled. No claim that Close carries
    # every late error from a storage goroutine.
    after = dict(before)
    if decode_error:
        return after, "decode error"
    candidates = [name for name in before if close_results[name] is None]
    if not candidates:
        return after, "all targets failed"
    for name in candidates:
        if rename_results[name] is not None:
            return after, "rename error"
        after[name] = "ok"
    return after, None

before = {"E3": "corrupt", "E4": "missing"}
after, error = publish(before, {"E3": "returned close error", "E4": None},
                       {"E4": None})
assert after == {"E3": "corrupt", "E4": "ok"} and error is None
again, error = publish({"E3": after["E3"]}, {"E3": None}, {"E3": None})
assert again == {"E3": "ok"} and error is None
partial, error = publish(before, {"E3": None, "E4": None},
                         {"E3": None, "E4": "error"})
assert partial == {"E3": "ok", "E4": "missing"} and error == "rename error"
early, error = publish(before, {"E3": None, "E4": None}, {},
                       decode_error=True)
assert early == before and error == "decode error"

print("streams:", stream, "four streams:", N * stream)
print("deep/source/target:", deep_reads, source_reads, target_writes)
print("total:", deep_reads + source_reads + target_writes, "network:", network)
print("synthetic selection cycles:", ordinary, compacted)
print("partial:", after, "retry:", again, "rename failure:", partial)
