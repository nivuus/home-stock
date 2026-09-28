"""m009: an article can be hidden, like a product already could."""
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


def test_m009_leaves_every_existing_article_active(tmp_path):
    conn = _stopped_at(tmp_path, 8)
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Riz', 'g')")
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Lait', 'ml')")
    conn.execute("INSERT INTO article (product_id) VALUES (1)")
    conn.execute("INSERT INTO article (product_id) VALUES (2)")
    conn.commit()

    assert apply_migrations(conn) == 9

    rows = conn.execute("SELECT id, active FROM article ORDER BY id").fetchall()
    assert [(r["id"], r["active"]) for r in rows] == [(1, 1), (2, 1)]


def test_m009_a_new_article_defaults_to_active(tmp_path):
    conn = _stopped_at(tmp_path, CURRENT_VERSION)
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Riz', 'g')")
    conn.execute("INSERT INTO article (product_id) VALUES (1)")
    assert conn.execute("SELECT active FROM article").fetchone()["active"] == 1


def test_m009_is_the_current_version_and_replayable(tmp_path):
    assert migrations.CURRENT_VERSION == 9
    conn = _stopped_at(tmp_path, 9)
    assert apply_migrations(conn) == 9
    assert apply_migrations(conn) == 9
