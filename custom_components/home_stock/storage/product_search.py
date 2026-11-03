"""The WHERE clause of `repositories.list_products`: active products, a name search.

Kept out of `repositories.py` on purpose, as `storage/products.py` is: that
module is already over this project's line limit (nivuus/home-stock#9).

SQLite's own LIKE folds case for ASCII only and never ignores accents, so
"pâte" would miss "PÂTES" and "Pates". The name is therefore folded ONCE, at
write time, into `product.name_fold` (m010, kept current by `folded_name`
below), and compared with the searched word folded the same way.

Never fold in SQL through a Python function registered on the connection:
the reader connection is shared bare between executor threads, and a Python
callback from inside a SQLite step deadlocks the GIL against the SQLite
mutex — that froze Home Assistant whole on 2026-10-22.
"""
# policy: allow-fr-file -- the docstring quotes French product names ("pâte",
# "PÂTES") as examples of what accent-insensitive search must match.
from __future__ import annotations

from typing import Any

from ..domain.search import LIKE_ESCAPE, fold_for_search, like_pattern


def folded_name(values: dict[str, Any]) -> dict[str, Any]:
    """`values` with `name_fold` set from its `name`, when it carries one.

    Every write of `product.name` goes through this, so the column can never
    drift from the name it folds.
    """
    if "name" not in values:
        return values
    return {**values, "name_fold": fold_for_search(values["name"])}


def product_filter(*, active_only: bool,
                   search: str | None) -> tuple[str, tuple[str, ...]]:
    """(" WHERE ...", params) for `SELECT * FROM product`, or ("", ()) for all."""
    clauses: list[str] = ["active = 1"] if active_only else []
    params: tuple[str, ...] = ()
    pattern = like_pattern(search)
    if pattern is not None:
        clauses.append(f"name_fold LIKE ? ESCAPE '{LIKE_ESCAPE}'")
        params = (pattern,)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params
