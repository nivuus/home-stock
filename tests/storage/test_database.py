import sqlite3

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
