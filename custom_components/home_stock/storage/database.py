"""SQLite access: one writer, serialised, WAL enabled, plus a dedicated reader.

Home Assistant calls into this module from the executor. All writes go through a
single lock so two services can never interleave a transaction. Reads use a
second, independent connection so a long write (import_catalog holds the lock
across hundreds of products) never blocks — or is blocked by — a read, and a
reader never observes a half-finished transaction the writer has not committed
yet. WAL mode is exactly what makes this safe: a reader can run concurrently
with the one writer without waiting on it. The price of handing the reader
out bare is that close() must not free it under whoever holds it — see
close().
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
        """Let go of both connections — never sqlite3.Connection.close() them.

        read() hands the read-only connection out bare, on purpose: a
        coordinator refresh must not queue behind anything. So when
        async_unload_entry runs this on one executor thread, another executor
        thread is still using that same connection. sqlite3_close_v2 frees the
        handle as soon as no statement is live on it, and the other thread is
        preparing its next one right then, with the GIL released: it reads a
        structure that has just been freed. The interpreter dies of a
        segmentation fault, and when it survives, SQLite is left wedged — the
        next connection's executescript never returns.

        Dropping the reference is enough, and is what closes the file in the
        normal case: CPython disposes of a connection as soon as its last
        owner lets go, so with nobody reading, the sqlite3_close happens right
        here, and with a reader in flight it happens the instant that reader
        is done. Callers arriving after us get the RuntimeError below instead
        of a connection. No lock is taken on either side, so a close can never
        deadlock against the non-reentrant write lock a long import_catalog is
        holding.
        """
        self._conn = None
        self._read_conn = None

    def read(self) -> sqlite3.Connection:
        """Return the dedicated read-only connection."""
        # Read the attribute once: a close landing between the check and the
        # return would otherwise hand the caller a None to call .execute() on.
        conn = self._read_conn
        if conn is None:
            raise RuntimeError("database is not connected")
        return conn

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """Run a transaction. Commits on success, rolls back on any exception."""
        # Same reason as read(): one look at the attribute, then work on the
        # local, so a concurrent close cannot swap it out mid-transaction.
        conn = self._conn
        if conn is None:
            raise RuntimeError("database is not connected")
        with self._lock:
            try:
                yield conn
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
