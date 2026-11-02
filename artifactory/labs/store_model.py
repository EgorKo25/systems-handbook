#!/usr/bin/env python3
"""Deliberately small SQLite model of references and bytes. NOT Artifactory code.

No HTTP, permissions, trash, staging, locks between writers, HA or transactions
across DB and filesystem. SHA1 layout models the documented default; SHA256 is
also checked. Never use this as a production artifact store.
"""
from pathlib import Path, PurePosixPath
import hashlib, sqlite3

class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.blobs = self.root / 'filestore'
        self.blobs.mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.root / 'metadata.sqlite')
        self.db.execute('CREATE TABLE IF NOT EXISTS refs(path TEXT PRIMARY KEY, sha1 TEXT, sha256 TEXT, size INTEGER)')
        self.db.commit()

    @staticmethod
    def name(path):
        p = PurePosixPath(path)
        if not path or p.is_absolute() or '..' in p.parts or '\\' in path or len(p.parts) < 2:
            raise ValueError('expected repository/path inside model')
        return str(p)

    def put(self, path, data):
        path = self.name(path)
        if self.db.execute('SELECT 1 FROM refs WHERE path=?', (path,)).fetchone():
            raise ValueError('immutable model path already exists')
        sha1, sha256 = hashlib.sha1(data).hexdigest(), hashlib.sha256(data).hexdigest()
        target = self.blobs / sha1[:2] / sha1
        if target.exists() and target.read_bytes() != data:
            raise ValueError('SHA1 collision: this model refuses different bytes')
        target.parent.mkdir(exist_ok=True)
        if not target.exists():
            target.write_bytes(data)
        with self.db:
            self.db.execute('INSERT INTO refs VALUES(?,?,?,?)', (path, sha1, sha256, len(data)))
        return sha1, sha256

    def copy(self, source, target):
        self.put(target, self.read(source))

    def read(self, path):
        row = self.db.execute('SELECT sha1,sha256,size FROM refs WHERE path=?', (self.name(path),)).fetchone()
        if row is None:
            raise KeyError(path)
        data = (self.blobs / row[0][:2] / row[0]).read_bytes()
        if len(data) != row[2] or hashlib.sha256(data).hexdigest() != row[1]:
            raise ValueError('bytes do not match model metadata')
        return data

    def delete(self, path):
        with self.db:
            self.db.execute('DELETE FROM refs WHERE path=?', (self.name(path),))

    def collect(self):
        live = {r[0] for r in self.db.execute('SELECT sha1 FROM refs')}
        dead = [p for p in self.blobs.glob('*/*') if p.name not in live]
        for p in dead:
            p.unlink()
        return len(dead)

    def stats(self):
        files = list(self.blobs.glob('*/*'))
        row = self.db.execute('SELECT COUNT(*),COALESCE(SUM(size),0) FROM refs').fetchone()
        return {'references': row[0], 'logical_bytes': row[1], 'blob_files': len(files), 'physical_bytes': sum(p.stat().st_size for p in files)}

    def close(self):
        self.db.close()
