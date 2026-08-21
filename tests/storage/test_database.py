import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

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


def test_a_connection_handed_out_before_close_stays_usable(db):
    """`read()` hands the connection out bare, so an executor thread can still
    be holding — and using — it when unload_entry closes the database on
    another thread. Closing it there would free a structure that thread is
    walking; the guarantee `close()` owes is therefore that a connection
    already handed out is never invalidated under its user."""
    with db.write() as conn:
        conn.execute("CREATE TABLE t (v INTEGER)")
        conn.execute("INSERT INTO t VALUES (7)")
    in_flight = db.read()  # what a coordinator refresh is holding

    db.close()

    assert in_flight.execute("SELECT v FROM t").fetchone()["v"] == 7
    # A caller arriving after the close gets a refusal, not a connection.
    with pytest.raises(RuntimeError):
        db.read()


# The child program below provokes the race for real. It needs its own
# interpreter because what it guards against is a segmentation fault, which
# the parent can only observe as an exit status.
_CLOSE_UNDER_READERS = '''
import sys, threading, time

sys.path.insert(0, sys.argv[1])
from custom_components.home_stock.storage.database import Database

for attempt in range(int(sys.argv[3])):
    db = Database(f"{sys.argv[2]}/{attempt}.db")
    db.connect()
    with db.write() as conn:
        conn.execute("CREATE TABLE t (v INTEGER)")
        conn.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(200)])

    reading = threading.Event()
    stop = threading.Event()

    def _read():
        reading.set()
        while not stop.is_set():
            try:
                db.read().execute("SELECT COUNT(*) AS n FROM t").fetchall()
            except Exception:
                return  # the database closed under us: expected, not a crash

    threads = [threading.Thread(target=_read) for _ in range(4)]
    for thread in threads:
        thread.start()
    assert reading.wait(timeout=30), "no reader ever started"
    time.sleep(0.002)  # let them settle into the loop
    db.close()
    stop.set()
    for thread in threads:
        thread.join(timeout=30)
print("ok")
'''


def test_closing_under_live_readers_never_crashes_the_interpreter(tmp_path):
    """Sixty rounds of `close()` landing on four threads reading flat out.

    This is the shape the suite died of: unload_entry closes on one executor
    thread while a coordinator refresh reads on another. The window is the
    handful of microseconds SQLite spends preparing a statement with the GIL
    released — freeing the connection there is a use-after-free, and CPython
    dies of a segmentation fault, which is why the whole thing runs in a
    child and the assertion is on its exit status. Sixty rounds is not a
    proof, it is a net: measured on this image, the unfixed code crashed on
    every run of twenty rounds, three times out of three.
    """
    source = Path(__file__).resolve().parents[2]
    done = subprocess.run(
        [sys.executable, "-c", _CLOSE_UNDER_READERS,
         str(source), str(tmp_path), "60"],
        capture_output=True, text=True, timeout=300, cwd=str(source))
    assert done.returncode == 0, (
        f"exit {done.returncode} (-11 is a segmentation fault)\n"
        f"stdout: {done.stdout}\nstderr: {done.stderr}")
    assert done.stdout.strip().endswith("ok")
