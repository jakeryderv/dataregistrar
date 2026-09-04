"""Response cache for adapter search and get. SQLite, per-entry expiry."""

from __future__ import annotations

import hashlib
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path

from pydantic import TypeAdapter

from dataregistrar.adapters import Adapter
from dataregistrar.model import AccessPlan, Kind, Record

_RECORDS = TypeAdapter(list[Record])


def cache_key(source: str, op: str, arg: str) -> str:
    return hashlib.sha256(f"{source}\x00{op}\x00{arg}".encode()).hexdigest()


class ResponseCache:
    """Stores serialized adapter responses with an expiry. `path=None` keeps it in memory."""

    def __init__(self, path: Path | None, *, clock: Callable[[], float] = time.time) -> None:
        self.path = path
        self._clock = clock
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path) if path else ":memory:", check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS responses ("
            " key TEXT PRIMARY KEY, source TEXT NOT NULL, op TEXT NOT NULL, arg TEXT NOT NULL,"
            " value TEXT NOT NULL, stored_at REAL NOT NULL, expires_at REAL NOT NULL)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS responses_source ON responses(source)")
        self._conn.commit()

    def get(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value, expires_at FROM responses WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value, expires_at = row
        return str(value) if self._clock() < float(expires_at) else None

    def put(self, key: str, *, source: str, op: str, arg: str, value: str, ttl: float) -> None:
        now = self._clock()
        self._conn.execute(
            "INSERT OR REPLACE INTO responses VALUES (?, ?, ?, ?, ?, ?, ?)",
            (key, source, op, arg, value, now, now + ttl),
        )
        self._conn.commit()

    def clear(self, source: str | None = None) -> int:
        cursor = (
            self._conn.execute("DELETE FROM responses WHERE source = ?", (source,))
            if source
            else self._conn.execute("DELETE FROM responses")
        )
        self._conn.commit()
        return cursor.rowcount

    def purge_expired(self) -> int:
        cursor = self._conn.execute("DELETE FROM responses WHERE expires_at <= ?", (self._clock(),))
        self._conn.commit()
        return cursor.rowcount

    def count(self, source: str | None = None) -> int:
        row = (
            self._conn.execute("SELECT COUNT(*) FROM responses WHERE source = ?", (source,))
            if source
            else self._conn.execute("SELECT COUNT(*) FROM responses")
        ).fetchone()
        return int(row[0]) if row else 0


class CachingAdapter:
    """Wraps an adapter so search and get are served from the cache while fresh.

    resolve and retrieve pass straight through: retrieval already reuses verified files.
    """

    id: str
    kinds: frozenset[Kind]

    def __init__(self, inner: Adapter, cache: ResponseCache, ttl: float) -> None:
        self.inner = inner
        self.cache = cache
        self.ttl = ttl
        self.id = inner.id
        self.kinds = inner.kinds

    def search(self, query: str) -> list[Record]:
        key = cache_key(self.id, "search", query)
        hit = self.cache.get(key)
        if hit is not None:
            return _RECORDS.validate_json(hit)
        records = self.inner.search(query)
        value = _RECORDS.dump_json(records).decode()
        self.cache.put(key, source=self.id, op="search", arg=query, value=value, ttl=self.ttl)
        return records

    def get(self, source_id: str) -> Record:
        key = cache_key(self.id, "get", source_id)
        hit = self.cache.get(key)
        if hit is not None:
            return Record.model_validate_json(hit)
        record = self.inner.get(source_id)
        value = record.model_dump_json()
        self.cache.put(key, source=self.id, op="get", arg=source_id, value=value, ttl=self.ttl)
        return record

    def resolve(self, record: Record) -> AccessPlan:
        return self.inner.resolve(record)

    def retrieve(self, plan: AccessPlan, destination: Path) -> list[Path]:
        return self.inner.retrieve(plan, destination)
