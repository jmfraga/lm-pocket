"""Encrypted storage: SQLCipher + FTS5.

The Store knows nothing about profiles or MCP; access control lives in
service.py. Every write here is a single transaction.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import uuid
from pathlib import Path

import sqlcipher3

from .pocket import now

MEMORY_TYPES = ("fact", "preference", "event", "interpretation", "skill", "decision", "relationship", "goal")
STATUSES = ("candidate", "durable", "archived", "rejected")
SOURCE_TYPES = ("user", "llm", "imported", "derived")
SENSITIVITIES = ("normal", "sensitive", "confidential")
SPACE_RE = re.compile(r"^(personal|portable_professional|shared|public|work:[a-z0-9_-]+)$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS spaces (
    id TEXT PRIMARY KEY, label TEXT NOT NULL, description TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS profiles (name TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    space TEXT NOT NULL REFERENCES spaces(id),
    sensitivity TEXT NOT NULL DEFAULT 'normal',
    portable INTEGER NOT NULL DEFAULT 0,
    source_type TEXT NOT NULL,
    provenance TEXT NOT NULL,
    confidence REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    derived_from TEXT NOT NULL DEFAULT '[]',
    supersedes TEXT NOT NULL DEFAULT '[]',
    tags TEXT NOT NULL DEFAULT '[]',
    declassified_at TEXT,
    extra TEXT NOT NULL DEFAULT '{}',
    CHECK (NOT (source_type = 'derived' AND portable = 1 AND declassified_at IS NULL))
);
CREATE INDEX IF NOT EXISTS memories_space_status ON memories(space, status);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content, tags, content='memories', content_rowid='rowid',
    tokenize="unicode61 remove_diacritics 2");
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags) VALUES ('delete', old.rowid, old.content, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags) VALUES ('delete', old.rowid, old.content, old.tags);
    INSERT INTO memories_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
END;
-- Application append-only: the code only INSERTs here. Not immutable (SPEC § 18).
CREATE TABLE IF NOT EXISTS audit (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    event TEXT NOT NULL,
    profile TEXT,
    client TEXT,
    detail TEXT NOT NULL DEFAULT '{}');
"""

JSON_FIELDS = ("provenance", "derived_from", "supersedes", "tags", "extra")


def uuid7() -> str:
    """UUIDv7 (time-ordered). Python < 3.14 has no uuid.uuid7."""
    ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")
    value = (ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= ((rand >> 62) & 0xFFF) << 64
    value |= 0b10 << 62
    value |= rand & ((1 << 62) - 1)
    return str(uuid.UUID(int=value))


class Store:
    def __init__(self, db_path: Path, dek: bytes):
        self._lock = threading.RLock()
        self.conn = sqlcipher3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlcipher3.Row
        # Raw key: SQLCipher skips its own PBKDF2 (we already ran Argon2id).
        self.conn.execute(f"PRAGMA key = \"x'{dek.hex()}'\"")
        # Wipes freed memory and locks pages. Crashes sqlcipher3-wheels on Windows
        # (stack overflow, 0xC00000FD, verified in CI 2026-10-01), so it is off there.
        if sys.platform != "win32":
            self.conn.execute("PRAGMA cipher_memory_security = ON")
        self.conn.execute("PRAGMA temp_store = MEMORY")
        self.conn.execute("PRAGMA foreign_keys = ON")
        # Fails here with "file is not a database" if the key is wrong.
        self.conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        with self.conn:
            self.conn.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            try:
                self.conn.close()
            except Exception:  # the volume may already be gone
                pass

    # --- helpers --------------------------------------------------------

    @staticmethod
    def _row(row) -> dict:
        d = dict(row)
        for f in JSON_FIELDS:
            d[f] = json.loads(d[f])
        d["portable"] = bool(d["portable"])
        extra = d.pop("extra")
        d.update({k: v for k, v in extra.items() if k not in d})
        if d.get("declassified_at") is None:
            d.pop("declassified_at", None)
        return d

    def is_empty(self) -> bool:
        with self._lock:
            return self.conn.execute("SELECT count(*) FROM spaces").fetchone()[0] == 0

    # --- spaces & profiles ---------------------------------------------

    def add_space(self, space_id: str, label: str, description: str = "") -> None:
        if not SPACE_RE.match(space_id):
            raise ValueError(f"invalid space id: {space_id}")
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO spaces(id, label, description, created_at) VALUES (?,?,?,?)",
                (space_id, label, description, now()),
            )

    def spaces(self) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.conn.execute("SELECT * FROM spaces ORDER BY id")]

    def set_profile(self, name: str, body: dict) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT INTO profiles(name, body) VALUES (?,?) ON CONFLICT(name) DO UPDATE SET body=excluded.body",
                (name, json.dumps(body)),
            )

    def profiles(self) -> dict[str, dict]:
        with self._lock:
            return {r["name"]: json.loads(r["body"]) for r in self.conn.execute("SELECT * FROM profiles ORDER BY name")}

    # --- memories -------------------------------------------------------

    def add_memory(self, m: dict) -> dict:
        m = dict(m)
        m.setdefault("id", uuid7())
        ts = now()
        m.setdefault("created_at", ts)
        m.setdefault("updated_at", m["created_at"])
        if m["type"] not in MEMORY_TYPES:
            raise ValueError(f"invalid type: {m['type']}")
        if m["status"] not in STATUSES:
            raise ValueError(f"invalid status: {m['status']}")
        if m["source_type"] not in SOURCE_TYPES:
            raise ValueError(f"invalid source_type: {m['source_type']}")
        if m.get("sensitivity", "normal") not in SENSITIVITIES:
            raise ValueError(f"invalid sensitivity: {m['sensitivity']}")
        if not str(m.get("content", "")).strip():
            raise ValueError("content is empty")
        known = {
            "id", "content", "type", "status", "space", "sensitivity", "portable", "source_type", "provenance",
            "confidence", "created_at", "updated_at", "derived_from", "supersedes", "tags", "declassified_at",
        }
        extra = {k: v for k, v in m.items() if k not in known}  # preserve unknown fields (format rule)
        with self._lock, self.conn:
            self.conn.execute(
                """INSERT INTO memories(id, content, type, status, space, sensitivity, portable, source_type,
                       provenance, confidence, created_at, updated_at, derived_from, supersedes, tags,
                       declassified_at, extra)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    m["id"], m["content"].strip(), m["type"], m["status"], m["space"], m.get("sensitivity", "normal"),
                    int(bool(m.get("portable", False))), m["source_type"], json.dumps(m["provenance"]),
                    m.get("confidence"), m["created_at"], m["updated_at"], json.dumps(m.get("derived_from", [])),
                    json.dumps(m.get("supersedes", [])), json.dumps(m.get("tags", [])), m.get("declassified_at"),
                    json.dumps(extra),
                ),
            )
        return self.get(m["id"])

    def get(self, memory_id: str) -> dict | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return self._row(row) if row else None

    def update(self, memory_id: str, **fields) -> dict:
        allowed = {"content", "status", "space", "type", "tags", "portable", "declassified_at", "sensitivity", "extra"}
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"cannot update: {bad}")
        current = self.get(memory_id)
        if current is None:
            raise KeyError(memory_id)
        sets, vals = [], []
        for k, v in fields.items():
            if k in ("tags", "extra"):
                v = json.dumps(v)
            if k == "portable":
                v = int(bool(v))
            sets.append(f"{k} = ?")
            vals.append(v)
        sets.append("updated_at = ?")
        vals.append(now())
        with self._lock, self.conn:
            self.conn.execute(f"UPDATE memories SET {', '.join(sets)} WHERE id = ?", (*vals, memory_id))
        return self.get(memory_id)

    def list(self, *, spaces=None, status="durable", limit=200, order="updated_at DESC") -> list[dict]:
        where, args = ["status = ?"], [status]
        if spaces is not None:
            if not spaces:
                return []
            where.append(f"space IN ({','.join('?' * len(spaces))})")
            args += list(spaces)
        sql = f"SELECT * FROM memories WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ?"
        with self._lock:
            return [self._row(r) for r in self.conn.execute(sql, (*args, limit))]

    def search(self, query: str, *, spaces, status="durable", limit=20) -> list[dict]:
        if not spaces:
            return []
        terms = re.findall(r"\w+", query, flags=re.UNICODE)
        if not terms:
            return self.list(spaces=spaces, status=status, limit=limit)
        match = " OR ".join(f'"{t}"*' for t in terms)
        sql = f"""SELECT m.* FROM memories_fts f JOIN memories m ON m.rowid = f.rowid
                  WHERE memories_fts MATCH ? AND m.status = ?
                    AND m.space IN ({','.join('?' * len(spaces))})
                  ORDER BY bm25(memories_fts) LIMIT ?"""
        with self._lock:
            return [self._row(r) for r in self.conn.execute(sql, (match, status, *spaces, limit))]

    def find_same_content(self, content: str, space: str) -> dict | None:
        norm = " ".join(content.lower().split())
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM memories WHERE space = ? AND status IN ('candidate','durable')", (space,)
            ).fetchall()
        for r in rows:
            if " ".join(r["content"].lower().split()) == norm:
                return self._row(r)
        return None

    def counts(self) -> dict:
        with self._lock:
            rows = self.conn.execute("SELECT status, count(*) FROM memories GROUP BY status").fetchall()
        return {r[0]: r[1] for r in rows}

    # --- audit ----------------------------------------------------------

    def audit(self, event: str, profile: str | None = None, client: str | None = None, **detail) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT INTO audit(at, event, profile, client, detail) VALUES (?,?,?,?,?)",
                (now(), event, profile, client, json.dumps(detail, ensure_ascii=False)),
            )

    def audit_events(self, limit=200, event: str | None = None, since_seq: int = 0) -> list[dict]:
        sql, args = "SELECT * FROM audit WHERE seq > ?", [since_seq]
        if event:
            sql += " AND event = ?"
            args.append(event)
        sql += " ORDER BY seq DESC LIMIT ?"
        with self._lock:
            rows = self.conn.execute(sql, (*args, limit)).fetchall()
        return [{**dict(r), "detail": json.loads(r["detail"])} for r in rows]

    def count_events_since(self, event: str, profile: str, since_iso: str) -> int:
        with self._lock:
            return self.conn.execute(
                "SELECT count(*) FROM audit WHERE event = ? AND profile = ? AND at >= ?", (event, profile, since_iso)
            ).fetchone()[0]
