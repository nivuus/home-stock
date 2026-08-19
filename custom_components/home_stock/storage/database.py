"""SQLite access: one writer, serialised, WAL enabled, plus a dedicated reader.

Home Assistant calls into this module from the executor. All writes go through a
single lock so two services can never interleave a transaction. Reads use a
second, independent connection so a long write (import_catalog holds the lock
across hundreds of products) never blocks — or is blocked by — a read, and a
reader never observes a half-finished transaction the writer has not committed
yet. WAL mode is exactly what makes this safe: a reader can run concurrently
with the one writer without waiting on it.
"""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager


class Database:
    """A single SQLite file, with serialised writes and a read-only reader."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: sqlite3.Connection | None = None
        self._read_conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def connect(self) -> None:
        """Open the file and apply the pragmas we depend on."""
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        self._conn = conn

        # A second connection, opened read-only on the same file, once WAL is
        # active on the writer above. sqlite3.Row so callers cannot tell reads
        # and writes apart.
        read_conn = sqlite3.connect(
            f"file:{self.path}?mode=ro", uri=True, check_same_thread=False
        )
        read_conn.row_factory = sqlite3.Row
        read_conn.execute("PRAGMA foreign_keys=ON")
        read_conn.execute("PRAGMA busy_timeout=5000")
        self._read_conn = read_conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        if self._read_conn is not None:
            self._read_conn.close()
            self._read_conn = None

    def read(self) -> sqlite3.Connection:
        """Return the dedicated read-only connection."""
        if self._read_conn is None:
            raise RuntimeError("database is not connected")
        return self._read_conn

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
