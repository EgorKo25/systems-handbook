#!/usr/bin/env python3
"""Read-only RAM probes of the teaching module; no Ansible, files, SSH or sockets are created."""
from __future__ import annotations
import ast
import io
import json
import posixpath
import stat
from types import SimpleNamespace
from pathlib import Path

class Result(Exception):
    def __init__(self, ok, fields):
        self.ok, self.fields = ok, fields

def probe(module_source, before, config=None, mode="0640", check=False, diff=False,
          kind="file", old_mode=0o640, error_at=None, path="/lab/config.json"):
    """Execute the actual inspected main AST with every filesystem operation in RAM."""
    nodes = ast.parse(module_source)
    main = next(n for n in nodes.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = []
    state = dict(data=before, mode=old_mode, candidate=None, candidate_mode=None)
    class Module:
        params = dict(path=path, config={"release":"0.1.0"} if config is None else config, mode=mode)
        check_mode = check
        _diff = diff
        def fail_json(self, **kw): raise Result(False, kw)
        def exit_json(self, **kw): raise Result(True, kw)
    def event(name):
        calls.append(name)
        if error_at == name: raise OSError("injected " + name)
    class Output:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def fileno(self): return 1
        def write(self, text):
            event("write")
            state["candidate"] = text.encode("utf-8")
        def flush(self): event("flush")
    def open_read(name, **kwargs):
        event("read")
        assert name == path and kwargs == {"encoding":"utf-8"}
        return io.TextIOWrapper(io.BytesIO(state["data"]), encoding="utf-8", newline=None)
    def temporary(**kw):
        event("mkstemp")
        assert kw == dict(prefix=".counter-", dir="/lab")
        state["candidate"] = b""
        return 1, "/lab/.candidate"
    def chmod(fd, value):
        event("fchmod"); assert fd == 1
        state["candidate_mode"] = value
    def replace(old, new):
        event("replace"); assert (old,new) == ("/lab/.candidate",path)
        state["data"], state["mode"] = state["candidate"], state["candidate_mode"]
        state["candidate"] = None
    def unlink(name):
        event("unlink"); assert name == "/lab/.candidate"
        state["candidate"] = None
    filesystem = SimpleNamespace(
        path=SimpleNamespace(isabs=posixpath.isabs, dirname=posixpath.dirname,
            isdir=lambda p:p=="/lab", lexists=lambda p:state["data"] is not None),
        lstat=lambda p:SimpleNamespace(st_mode=(stat.S_IFREG if kind=="file" else stat.S_IFLNK)|state["mode"]),
        fdopen=lambda fd,*args,**kw:Output(), fchmod=chmod, fsync=lambda fd:event("fsync"),
        replace=replace, unlink=unlink)
    ns = dict(AnsibleModule=lambda **kw:Module(), json=json, os=filesystem, stat=stat,
              tempfile=SimpleNamespace(mkstemp=temporary), open=open_read)
    exec(compile(ast.Module(body=[main], type_ignores=[]),"<actual-module-main>","exec"),ns)
    try:
        ns["main"]()
    except Result as r:
        return dict(ok=r.ok, fields=r.fields, calls=calls, state=state)
    raise AssertionError("module did not return a protocol result")

def check(module_source):
    canonical = b'{\n  "release": "0.1.0"\n}\n'
    checks = []
    def verify(label, result, ok, changed=None, data=canonical):
        assert result["ok"] is ok, (label,result)
        if changed is not None: assert result["fields"]["changed"] is changed, (label,result)
        assert result["state"]["data"] == data, (label,result)
        assert result["state"]["candidate"] is None, (label,result)
        checks.append(label)
    verify("canonical LF unchanged",probe(module_source,canonical),True,False)
    for name,raw in [("CRLF",canonical.replace(b"\n",b"\r\n")),("CR",canonical.replace(b"\n",b"\r"))]:
        r=probe(module_source,raw);verify(name+" normalized comparison",r,True,False,data=raw)
        assert "mkstemp" not in r["calls"]
    verify("formatting converges",probe(module_source,b'{"release":"0.1.0"}'),True,True)
    verify("create missing file",probe(module_source,None),True,True)
    r=probe(module_source,None,check=True,diff=True)
    verify("check missing predicts without write",r,True,True,data=None)
    assert r["fields"]["diff"]["after"].encode()==canonical and not r["calls"]
    r=probe(module_source,canonical,old_mode=0o644,check=True)
    verify("mode drift check",r,True,True);assert r["state"]["mode"]==0o644
    verify("mode drift apply",probe(module_source,canonical,old_mode=0o644),True,True)
    for label,raw in [("malformed JSON",b"{broken"),("invalid UTF8",b"\xff"),("array root",b"[]")]:
        r=probe(module_source,raw);verify(label,r,False,data=raw);assert "mkstemp" not in r["calls"]
    for label,kwargs in [
        ("symlink",dict(kind="symlink")),("special mode",dict(mode="1640")),
        ("non-octal mode",dict(mode="08")),("relative path",dict(path="config.json")),
        ("NaN desired",dict(config={"bad":float("nan")}))]:
        r=probe(module_source,canonical,**kwargs);verify(label,r,False);assert "mkstemp" not in r["calls"]
    for fault in ("write","flush","fsync","replace"):
        r=probe(module_source,b'{"release":"old"}',error_at=fault)
        verify(fault+" failure keeps old destination",r,False,data=b'{"release":"old"}')
        assert "unlink" in r["calls"]
    # A mode repair causes a write; normalization then publishes LF.
    raw=canonical.replace(b"\n",b"\r\n")
    verify("mode repair publishes normalized text",probe(module_source,raw,old_mode=0o644),True,True)
    assert "returned: always" not in module_source and module_source.count("returned: success")==2
    return checks

if __name__ == "__main__":
    root=Path(__file__).resolve().parents[1]
    results=check((root/"labs/local/library/counter_config.py").read_text())
    print("PASS",len(results),"RAM module probes; no native Ansible/filesystem atomicity/SSH proof")
    for label in results: print("PASS",label)
