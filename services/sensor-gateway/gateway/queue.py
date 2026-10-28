"""The readings waiting to be relayed, on disk: a power cut or an API that is down loses nothing."""

import json
import sqlite3
import threading
from pathlib import Path

Reading = dict[str, str]


class Queue:
    def __init__(self, path: Path, limit: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS reading (id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL)"
        )
        self._lock = threading.Lock()
        self._limit = limit

    def size(self) -> int:
        with self._lock:
            return int(self._db.execute("SELECT count(*) FROM reading").fetchone()[0])

    def push(self, readings: list[Reading]) -> bool:
        """Queue the readings; False (nothing queued) when the queue is full."""
        with self._lock:
            count = int(self._db.execute("SELECT count(*) FROM reading").fetchone()[0])
            if count + len(readings) > self._limit:
                return False
            self._db.executemany("INSERT INTO reading (body) VALUES (?)", [(json.dumps(r),) for r in readings])
            return True

    def peek(self, n: int) -> list[tuple[int, Reading]]:
        with self._lock:
            rows = self._db.execute("SELECT id, body FROM reading ORDER BY id LIMIT ?", (n,)).fetchall()
        return [(int(i), json.loads(b)) for i, b in rows]

    def drop(self, last_id: int) -> None:
        with self._lock:
            self._db.execute("DELETE FROM reading WHERE id <= ?", (last_id,))

    def close(self) -> None:
        with self._lock:
            self._db.close()
