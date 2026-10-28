"""What waits to be relayed, on disk: a power cut or an API that is down loses nothing.

Two tables of one file: ``reading`` (sensor readings) and ``event`` (watch-tower events, each with its frame).
"""

# ruff: noqa: S608 (the table name comes from TABLES, never from a caller)

import json
import sqlite3
import threading
from pathlib import Path

Reading = dict[str, str]
TABLES = ("reading", "event")


class Queue:
    def __init__(self, path: Path, limit: int, table: str = "reading") -> None:
        if table not in TABLES:
            raise ValueError(table)
        self._table = table
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            f"CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL)"
        )
        self._lock = threading.Lock()
        self._limit = limit

    def _count(self) -> int:
        return int(self._db.execute(f"SELECT count(*) FROM {self._table}").fetchone()[0])

    def size(self) -> int:
        with self._lock:
            return self._count()

    def push(self, items: list[Reading]) -> bool:
        """Queue the items; False (nothing queued) when the queue is full."""
        with self._lock:
            if self._count() + len(items) > self._limit:
                return False
            self._db.executemany(f"INSERT INTO {self._table} (body) VALUES (?)", [(json.dumps(r),) for r in items])
            return True

    def peek(self, n: int) -> list[tuple[int, Reading]]:
        with self._lock:
            rows = self._db.execute(f"SELECT id, body FROM {self._table} ORDER BY id LIMIT ?", (n,)).fetchall()
        return [(int(i), json.loads(b)) for i, b in rows]

    def drop(self, last_id: int) -> None:
        with self._lock:
            self._db.execute(f"DELETE FROM {self._table} WHERE id <= ?", (last_id,))

    def close(self) -> None:
        with self._lock:
            self._db.close()
