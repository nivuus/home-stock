"""The WHERE clause of `repositories.list_products`: active products, a name search.

Kept out of `repositories.py` on purpose, as `storage/products.py` is: that
module is already over this project's line limit (nivuus/home-stock#9).

SQLite's own LIKE folds case for ASCII only and never ignores accents, so
"pâte" would miss "PÂTES" and "Pates". The name is therefore folded in SQL by
the integration's own `fold_for_search`, registered on the connection as
FOLD_FUNCTION, and compared with the searched word folded the same way.
"""
from __future__ import annotations

import sqlite3
from typing import Final

from ..domain.search import LIKE_ESCAPE, fold_for_search, like_pattern

FOLD_FUNCTION: Final = "home_stock_fold"


def _fold_or_null(value: object) -> str | None:
    return fold_for_search(value) if isinstance(value, str) else None


def ensure_fold_function(conn: sqlite3.Connection) -> None:
    """Register FOLD_FUNCTION on `conn` unless it already answers there.

    Functions are per connection, and the integration hands out two (writer
    and read-only) plus whatever a caller opens. Registering only when absent
    never redefines a function another thread's statement may be running.
    """
    try:
        conn.execute(f"SELECT {FOLD_FUNCTION}('')").fetchone()
    except sqlite3.OperationalError:
        conn.create_function(FOLD_FUNCTION, 1, _fold_or_null, deterministic=True)


def product_filter(conn: sqlite3.Connection, *, active_only: bool,
                   search: str | None) -> tuple[str, tuple[str, ...]]:
    """(" WHERE ...", params) for `SELECT * FROM product`, or ("", ()) for all."""
    clauses: list[str] = ["active = 1"] if active_only else []
    params: tuple[str, ...] = ()
    pattern = like_pattern(search)
    if pattern is not None:
        ensure_fold_function(conn)
        clauses.append(f"{FOLD_FUNCTION}(name) LIKE ? ESCAPE '{LIKE_ESCAPE}'")
        params = (pattern,)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params
