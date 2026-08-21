"""Versioned migrations. Each module exposes VERSION and SQL."""
from __future__ import annotations

import sqlite3

from . import (
    m001_initial,
    m002_scan,
    m003_consumption,
    m004_recipes,
    m005_equipment,
    m006_shopping,
)

MIGRATIONS = (
    m001_initial,
    m002_scan,
    m003_consumption,
    m004_recipes,
    m005_equipment,
    m006_shopping,
)
CURRENT_VERSION = MIGRATIONS[-1].VERSION


def _current_version(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return row["v"] or 0


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Bring the database up to CURRENT_VERSION. Returns the version reached."""
    version = _current_version(conn)
    for migration in MIGRATIONS:
        if migration.VERSION > version:
            conn.executescript(migration.SQL)
            # A migration whose data step needs the referential in Python
            # (aisles.py) exposes apply(); schema-only migrations do not.
            hook = getattr(migration, "apply", None)
            if hook is not None:
                hook(conn)
            conn.execute("DELETE FROM schema_version")
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (migration.VERSION,)
            )
            version = migration.VERSION
    return version
