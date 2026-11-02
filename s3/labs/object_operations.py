"""One-key teaching model. No sockets, SDK calls, or filesystem operations."""
from dataclasses import dataclass
from hashlib import sha256

V1 = b"object-lab v1\n"
V2 = b"object-lab v2\n"
OP1 = "00000000000000000000000000000001"
OP2 = "00000000000000000000000000000002"

@dataclass(frozen=True)
class Version:
    id: str
    body: bytes | None
    operation_id: str | None
    etag: str | None

class OneKey:
    def __init__(self, mode):
        assert mode in ("never", "enabled", "suspended")
        self.mode = mode
        self.history = []
        self.serial = 0

    def current(self):
        return self.history[0] if self.history else None

    def _new_id(self, marker=False):
        if self.mode != "enabled":
            return "null"
        self.serial += 1
        return ("m" if marker else "v") + str(self.serial)

    def _install(self, item):
        if self.mode == "never":
            self.history = [item]
        elif self.mode == "suspended":
            self.history = [item] + [
                v for v in self.history if v.id != "null"
            ]
        else:
            self.history.insert(0, item)

    def put(self, body, operation_id, etag, *, create=False, match=None):
        cur = self.current()
        present = cur is not None and cur.body is not None
        if create and present:
            return 412, None
        if match is not None:
            if not present:
                return 404, None
            if cur.etag != match:
                return 412, None
        item = Version(self._new_id(), body, operation_id, etag)
        self._install(item)
        return 200, item.id

    def get(self, version_id=None):
        if version_id is None:
            item = self.current()
        else:
            item = next((v for v in self.history
                         if v.id == version_id), None)
        if item is None:
            return 404, None
        if item.body is None:
            return (404 if version_id is None else 405), item
        return 200, item

    def delete_current(self):
        if self.mode == "never":
            self.history = []
            return None
        marker = Version(self._new_id(marker=True), None, None, None)
        self._install(marker)
        return marker.id

    def remove_known_version(self, version_id):
        # A set operation in the model, not an assertion about HTTP
        # status for DeleteObject with a nonexistent version.
        before = len(self.history)
        self.history = [v for v in self.history if v.id != version_id]
        return len(self.history) < before

def accept_copy(chunks, *, maximum, length, expected_sha256,
                ended=True, late_error=False):
    # Symbolic publication only. Does not test files, hard links, or fsync.
    body = b"".join(chunks)
    if maximum < 0 or len(body) > maximum or not ended or late_error:
        return None
    if length is not None and len(body) != length:
        return None
    if sha256(body).hexdigest() != expected_sha256:
        return None
    return body

expected = sha256(V1).hexdigest()
s = OneKey("enabled")
status, v1 = s.put(V1, OP1, "E1", create=True)
assert status == 200
# The response is lost. A retry sees the saved object.
assert s.put(V1, OP1, "E1", create=True) == (412, None)
logical_outcome = "unknown"
assert logical_outcome == "unknown" and len(s.history) == 1
assert s.get(v1)[1].operation_id == OP1
status, v2 = s.put(V2, OP2, "E2", match="E1")
assert status == 200 and s.get()[1].body == V2
assert s.get(v1)[1].body == V1
assert s.put(V1, OP1, "E1", match="stale")[0] == 412
m1 = s.delete_current()  # response lost
m2 = s.delete_current()  # another simple DELETE
assert len({v1, v2, m1, m2}) == 4
assert s.get()[0] == 404 and s.get(m1)[0] == 405
assert s.remove_known_version(m2)
assert s.get()[0] == 404  # m1 remains
assert s.remove_known_version(m1)
assert s.get()[1].id == v2
assert s.remove_known_version(v1)
assert s.get(v1)[0] == 404  # selected data version is gone
print("enabled: lost PUT response -> retry 412; two DELETE markers")
print("remove newest marker -> still 404; remove selected data -> gone")

# A marker is not a precondition failure for create-only in this model.
s.delete_current()
assert s.put(V1, OP1, "E1", create=True)[0] == 200
print("enabled: create-only can write over a current marker")

suspended = OneKey("suspended")
suspended.history = [Version("saved-v1", V1, OP1, "E1")]
assert suspended.put(V1, OP1, "E1")[1] == "null"
assert suspended.put(V2, OP2, "E2")[1] == "null"
assert len(suspended.history) == 2
assert suspended.get("null")[1].body == V2
assert suspended.get("saved-v1")[1].body == V1
assert suspended.delete_current() == "null"
assert suspended.get()[0] == 404
assert suspended.get("null")[0] == 405
assert suspended.get("saved-v1")[0] == 200
assert suspended.remove_known_version("null")
assert suspended.get()[1].id == "saved-v1"
print("suspended: same null ID, replaced body; null marker preserves non-null")

never = OneKey("never")
never.put(V1, OP1, "E1")
never.delete_current()  # response lost
never.put(V2, OP2, "E2")  # competing writer
never.delete_current()  # blind retry deletes the new body
assert never.get()[0] == 404 and never.history == []
print("never: blind DELETE retry can remove a competing new PUT")

assert accept_copy([V1[:10]], maximum=14, length=14,
                   expected_sha256=expected) is None
assert accept_copy([V1, b"x"], maximum=14, length=None,
                   expected_sha256=expected) is None
assert accept_copy([V1], maximum=14, length=14,
                   expected_sha256=expected, ended=False) is None
assert accept_copy([V1], maximum=14, length=14,
                   expected_sha256=expected, late_error=True) is None
assert accept_copy([V2], maximum=14, length=14,
                   expected_sha256=expected) is None
assert accept_copy([V1[:10], V1[10:]], maximum=14, length=14,
                   expected_sha256=expected) == V1
short = V1[:-1]
assert accept_copy([short], maximum=14, length=13,
                   expected_sha256=sha256(short).hexdigest()) == short
empty_sha = sha256(b"").hexdigest()
assert accept_copy([], maximum=0, length=0,
                   expected_sha256=empty_sha) == b""
assert accept_copy([b"x"], maximum=0, length=1,
                   expected_sha256=empty_sha) is None
print("GET: 10/14, 15>14, missing EOF, late error, wrong hash -> no copy")
print("GET: full 14/14 and complete 13<14 -> accepted; maximum=0 only empty")
