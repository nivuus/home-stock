"""A migration commits whole or not at all, and a newer database is refused."""
import sqlite3
import types

import pytest

from custom_components.home_stock.storage import migrations
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import (
    CURRENT_VERSION,
    apply_migrations,
)


def _fresh(tmp_path):
    database = Database(str(tmp_path / "home_stock.db"))
    database.connect()
    return database


def _columns(db, table):
    return {row["name"] for row in db.read().execute(f"PRAGMA table_info({table})")}


def _version(db):
    return db.read().execute("SELECT MAX(version) AS v FROM schema_version").fetchone()["v"]


def _fake_migration(version, *, fail):
    def apply(conn):
        conn.execute("UPDATE product SET name = name || '!'")
        if fail:
            raise RuntimeError("interrupted")

    return types.SimpleNamespace(
        VERSION=version,
        SQL="ALTER TABLE product ADD COLUMN probe TEXT;\n"
        "CREATE TABLE probe_table (id INTEGER PRIMARY KEY);\n",
        apply=apply,
    )


def test_a_failing_hook_leaves_schema_and_version_untouched(tmp_path, monkeypatch):
    db = _fresh(tmp_path)
    with db.write() as conn:
        apply_migrations(conn)
        conn.execute("INSERT INTO product (name, base_unit) VALUES ('Riz', 'g')")

    failing = _fake_migration(CURRENT_VERSION + 1, fail=True)
    monkeypatch.setattr(migrations, "MIGRATIONS", (*migrations.MIGRATIONS, failing))
    monkeypatch.setattr(migrations, "CURRENT_VERSION", failing.VERSION)
    with pytest.raises(RuntimeError, match="interrupted"):
        with db.write() as conn:
            apply_migrations(conn)

    assert "probe" not in _columns(db, "product")
    tables = {r["name"] for r in db.read().execute("SELECT name FROM sqlite_master")}
    assert "probe_table" not in tables
    assert _version(db) == CURRENT_VERSION
    names = [r["name"] for r in db.read().execute("SELECT name FROM product")]
    assert names == ["Riz"]

    # The next start re-runs the same migration from scratch and succeeds.
    working = _fake_migration(CURRENT_VERSION + 1, fail=False)
    monkeypatch.setattr(migrations, "MIGRATIONS", (*migrations.MIGRATIONS[:-1], working))
    with db.write() as conn:
        assert apply_migrations(conn) == working.VERSION
    assert "probe" in _columns(db, "product")
    assert _version(db) == working.VERSION
    db.close()


def test_every_real_migration_runs_inside_the_runner_transaction(tmp_path):
    """No real migration may commit on its own (that would split it in two)."""
    db = _fresh(tmp_path)
    trace = []
    db._conn.set_trace_callback(lambda sql: trace.append(" ".join(sql.split())))
    with db.write() as conn:
        apply_migrations(conn)
    db._conn.set_trace_callback(None)
    # Every COMMIT must close a migration right after its version write; a
    # COMMIT anywhere else means part of a migration became durable alone.
    statements = [s for s in trace if s]
    for index, sql in enumerate(statements):
        if sql.upper() == "COMMIT" and index > 0:
            assert statements[index - 1].startswith("INSERT INTO schema_version"), (
                f"COMMIT after {statements[index - 1]!r}"
            )
    db.close()


def test_a_database_from_a_newer_version_is_refused(tmp_path):
    db = _fresh(tmp_path)
    with db.write() as conn:
        apply_migrations(conn)
        conn.execute("UPDATE schema_version SET version = ?", (CURRENT_VERSION + 1,))
    with pytest.raises(RuntimeError, match=f"version {CURRENT_VERSION + 1}") as refused:
        with db.write() as conn:
            apply_migrations(conn)
    assert type(refused.value).__name__ == "SchemaTooNewError"
    assert _version(db) == CURRENT_VERSION + 1
    db.close()


def test_sqlite_error_mid_script_rolls_back_the_statements_before_it(tmp_path, monkeypatch):
    db = _fresh(tmp_path)
    with db.write() as conn:
        apply_migrations(conn)
    broken = types.SimpleNamespace(
        VERSION=CURRENT_VERSION + 1,
        SQL="ALTER TABLE product ADD COLUMN probe TEXT;\nTHIS IS NOT SQL;\n",
    )
    monkeypatch.setattr(migrations, "MIGRATIONS", (*migrations.MIGRATIONS, broken))
    with pytest.raises(sqlite3.OperationalError):
        with db.write() as conn:
            apply_migrations(conn)
    assert "probe" not in _columns(db, "product")
    assert _version(db) == CURRENT_VERSION
    db.close()
