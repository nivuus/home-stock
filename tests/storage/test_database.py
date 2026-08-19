import sqlite3
import threading

import pytest

from custom_components.home_stock.storage.database import Database


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "home_stock.db"))
    database.connect()
    yield database
    database.close()


def test_connect_enables_wal_and_foreign_keys(db):
    conn = db.read()
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_write_commits_on_success(db):
    with db.write() as conn:
        conn.execute("CREATE TABLE t (v INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
    assert db.read().execute("SELECT v FROM t").fetchone()[0] == 1


def test_write_rolls_back_on_error(db):
    with db.write() as conn:
        conn.execute("CREATE TABLE t (v INTEGER)")
    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
        with db.write() as conn:
            conn.execute("INSERT INTO t VALUES (1)")
            conn.execute("INSERT INTO t VALUES (NULL), (2)")
            conn.execute("CREATE TABLE t (v INTEGER)")  # raises
    # Nothing from the failed transaction survived.
    assert db.read().execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0


def test_rows_are_dict_like(db):
    with db.write() as conn:
        conn.execute("CREATE TABLE t (v INTEGER)")
        conn.execute("INSERT INTO t VALUES (7)")
    row = db.read().execute("SELECT v FROM t").fetchone()
    assert row["v"] == 7


def test_read_uses_a_dedicated_connection(db):
    # Not the writer's connection: a coordinator refresh must never share a
    # transaction context with a write in progress (see the next test).
    assert db.read() is not db._conn


def test_read_does_not_block_on_a_write_in_progress_and_sees_no_dirty_data(db):
    """A long write (import_catalog holds the lock across hundreds of
    products) must never make a concurrent read wait, and a read must never
    observe a write's uncommitted rows — exactly what sharing one connection
    across threads without the lock used to allow."""
    with db.write() as conn:
        conn.execute("CREATE TABLE t (v INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")

    write_is_open = threading.Event()
    release_write = threading.Event()

    def _slow_write() -> None:
        with db.write() as conn:
            conn.execute("INSERT INTO t VALUES (2)")
            write_is_open.set()
            release_write.wait(timeout=5)

    writer = threading.Thread(target=_slow_write)
    writer.start()
    assert write_is_open.wait(timeout=5)
    try:
        # Must return promptly (no wait on Database._lock) and must not see
        # row 2: the write holding the lock has not committed it yet.
        count = db.read().execute("SELECT COUNT(*) AS n FROM t").fetchone()["n"]
    finally:
        release_write.set()
        writer.join(timeout=5)
    assert count == 1
