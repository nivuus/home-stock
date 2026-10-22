"""Search: the folded product name is a column, not a function.

`products/list` with `search` used to fold `product.name` in SQL through a
Python function registered on the connection. The reader connection is
shared bare between executor threads, and a Python function called back
from inside a SQLite step is exactly what deadlocks such a connection: one
thread holds the SQLite mutex and waits for the GIL, another holds the GIL
and waits for the mutex, and the whole interpreter — Home Assistant's event
loop included — stops (2026-10-22). So the folding moves to write time:
`name_fold` is filled by apply() for every existing product and kept by
`repositories.insert_product` / `update_product_fields` from then on.

Numbering: the file name and VERSION move together, in the same commit.
"""
from __future__ import annotations

import sqlite3

from ...domain.search import fold_for_search

VERSION = 10

SQL = """
ALTER TABLE product ADD COLUMN name_fold TEXT NOT NULL DEFAULT '';
"""


def apply(conn: sqlite3.Connection) -> None:
    """Fold the name of every product already in the table."""
    # Tuple access: this must work whatever row_factory the caller set.
    rows = conn.execute("SELECT id, name FROM product").fetchall()
    conn.executemany(
        "UPDATE product SET name_fold = ? WHERE id = ?",
        [(fold_for_search(name), row_id) for row_id, name in rows],
    )
