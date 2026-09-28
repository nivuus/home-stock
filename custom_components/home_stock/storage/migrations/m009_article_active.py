"""Deletion: an article can be hidden, the way a product already can.

Schema-only, no apply(): every existing article stays visible, which is what
the DEFAULT gives. Hiding a PRODUCT never writes this column — the listings
join on product.active — so restoring a product brings its articles back
exactly as they were.

Numbering: the file name and VERSION move together, in the same commit.
"""
from __future__ import annotations

VERSION = 9

SQL = """
ALTER TABLE article ADD COLUMN active INTEGER NOT NULL DEFAULT 1;
"""
