"""m010: the folded product name is a column, written once, read by every search."""
import sqlite3

from custom_components.home_stock.storage import migrations
from custom_components.home_stock.storage.migrations import (
    CURRENT_VERSION,
    MIGRATIONS,
    apply_migrations,
)


def _stopped_at(tmp_path, version: int) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "home_stock.db"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    for migration in MIGRATIONS:
        if migration.VERSION > version:
            break
        conn.executescript(migration.SQL)
        hook = getattr(migration, "apply", None)
        if hook is not None:
            hook(conn)
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    conn.commit()
    return conn


def test_m010_folds_the_name_of_every_existing_product(tmp_path):
    conn = _stopped_at(tmp_path, 9)
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Pâtes', 'g')")
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Œufs Frais', 'piece')")
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('lait', 'ml')")
    conn.commit()

    assert apply_migrations(conn) == 10

    rows = conn.execute("SELECT name, name_fold FROM product ORDER BY id").fetchall()
    assert [(r["name"], r["name_fold"]) for r in rows] == [
        ("Pâtes", "pates"), ("Œufs Frais", "oeufs frais"), ("lait", "lait")]


def test_m010_is_the_current_version_and_replayable(tmp_path):
    assert migrations.CURRENT_VERSION == 10
    conn = _stopped_at(tmp_path, 10)
    assert apply_migrations(conn) == 10
    assert apply_migrations(conn) == 10
    assert CURRENT_VERSION == 10
