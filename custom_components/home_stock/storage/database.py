"""SQLite access: one writer, serialised, WAL enabled.

Home Assistant calls into this module from the executor. All writes go through a
single lock so two services can never interleave a transaction.
"""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager


class Database:
    """A single SQLite file, with serialised writes."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def connect(self) -> None:
        """Open the file and apply the pragmas we depend on."""
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        self._conn = conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def read(self) -> sqlite3.Connection:
        """Return the connection for read-only queries."""
        if self._conn is None:
            raise RuntimeError("database is not connected")
        return self._conn

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """Run a transaction. Commits on success, rolls back on any exception."""
        if self._conn is None:
            raise RuntimeError("database is not connected")
        with self._lock:
            try:
                yield self._conn
            except Exception:
                self._conn.rollback()
                raise
            else:
                self._conn.commit()
