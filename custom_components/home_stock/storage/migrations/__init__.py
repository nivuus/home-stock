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
    m007_portion,
    m008_migration,
    m009_article_active,
    m010_product_name_fold,
    m011_script_neutral_keys,
)

MIGRATIONS = (
    m001_initial,
    m002_scan,
    m003_consumption,
    m004_recipes,
    m005_equipment,
    m006_shopping,
    m007_portion,
    m008_migration,
    m009_article_active,
    m010_product_name_fold,
    m011_script_neutral_keys,
)
CURRENT_VERSION = MIGRATIONS[-1].VERSION


class SchemaTooNewError(RuntimeError):
    """The database was written by a newer release than this code."""


def _current_version(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return row[0] or 0


def _apply_one(conn: sqlite3.Connection, migration) -> None:
    """Run one migration and its version write as ONE transaction.

    `executescript` issues no BEGIN of its own (and, under the legacy
    transaction control this connection uses, commits whatever is pending
    first), so each statement of a bare script would be durable on its own:
    a process dying half-way would leave a schema the next start cannot
    re-run ("duplicate column"). The script therefore opens the transaction
    itself; the hook and the version write join it, because the module only
    begins an implicit transaction when none is open. SQLite DDL is
    transactional, and no migration uses a PRAGMA that cannot run inside a
    transaction. Any failure rolls the whole step back.
    """
    try:
        conn.executescript("BEGIN;\n" + migration.SQL)
        # A migration whose data step needs the referential in Python
        # (aisles.py) exposes apply(); schema-only migrations do not.
        hook = getattr(migration, "apply", None)
        if hook is not None:
            hook(conn)
        conn.execute("DELETE FROM schema_version")
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)", (migration.VERSION,)
        )
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        raise
    conn.commit()


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Bring the database up to CURRENT_VERSION. Returns the version reached.

    Each migration commits whole or not at all. A database whose version is
    newer than this code is refused rather than used with a schema the code
    does not know.
    """
    version = _current_version(conn)
    if version > CURRENT_VERSION:
        raise SchemaTooNewError(
            f"the database is at schema version {version}, newer than the"
            f" {CURRENT_VERSION} this release knows: install a newer release"
            " or restore a backup made by this one"
        )
    for migration in MIGRATIONS:
        if migration.VERSION > version:
            _apply_one(conn, migration)
            version = migration.VERSION
    return version
