"""Matching keys and folded names, recomputed with the script-neutral folding.

`matching.normalise` and `search.fold_for_search` used to erase every letter
outside ASCII a-z after dropping all combining marks. An ingredient text in
Cyrillic, Greek, CJK, Arabic or Hebrew normalised to the empty string, and
one alias stored under that empty key made every such line "confirmed" as
that product. The folding now keeps every script (domain/textfold.py).

The text an alias was taught from is not stored with it, so each key is
re-derived from the recipe lines that produced it under the OLD folding
(frozen below as `_legacy_normalise`; `normalise` is not idempotent, because
of its plural trim, so a key cannot simply be normalised again):

- the empty key is deleted: it cannot be told apart from any other
  letterless text, and it is the one that confirmed lines wrongly;
- a key some line produces is replaced by that line's new key(s), for the
  same product; when two keys meet, the most recent decision wins, as
  `upsert_alias` decides;
- a key no line produces is left as it is (for Latin text the two foldings
  agree).

`product.name_fold` is recomputed for every product. Runs inside the
migration runner's transaction: all or nothing.

Numbering: the file name and VERSION move together, in the same commit.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata

from ...domain.matching import normalise
from ...domain.search import fold_for_search

VERSION = 11

SQL = ""

_LEGACY_LIGATURES = {"œ": "oe", "æ": "ae", "Œ": "OE", "Æ": "AE"}
_LEGACY_NON_WORD = re.compile(r"[^a-z0-9]+")


def _legacy_normalise(text: str) -> str:
    """matching.normalise as it was up to schema version 10. Never change it."""
    for ligature, expanded in _LEGACY_LIGATURES.items():
        text = text.replace(ligature, expanded)
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    words = _LEGACY_NON_WORD.sub(" ", stripped.casefold()).split()
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


def _upsert(conn: sqlite3.Connection, key: str, product_id: int,
            created_at: str) -> None:
    conn.execute(
        "INSERT INTO ingredient_alias (normalised, product_id, created_at)"
        " VALUES (?, ?, ?)"
        " ON CONFLICT(normalised) DO UPDATE SET product_id = excluded.product_id,"
        " created_at = excluded.created_at"
        " WHERE excluded.created_at > ingredient_alias.created_at",
        (key, product_id, created_at))


def apply(conn: sqlite3.Connection) -> None:
    """Re-derive alias keys and refold product names."""
    # Tuple access: this must work whatever row_factory the caller set.
    sources: dict[str, set[str]] = {}
    for (raw_text,) in conn.execute("SELECT DISTINCT raw_text FROM recipe_ingredient"):
        sources.setdefault(_legacy_normalise(raw_text), set()).add(normalise(raw_text))

    aliases = conn.execute(
        "SELECT id, normalised, product_id, created_at FROM ingredient_alias"
        " ORDER BY created_at, id").fetchall()
    for alias_id, key, product_id, created_at in aliases:
        if not key:
            conn.execute("DELETE FROM ingredient_alias WHERE id = ?", (alias_id,))
            continue
        new_keys = {new for new in sources.get(key, ()) if new}
        if not new_keys or new_keys == {key}:
            continue
        conn.execute("DELETE FROM ingredient_alias WHERE id = ?", (alias_id,))
        for new_key in sorted(new_keys):
            _upsert(conn, new_key, product_id, created_at)

    rows = conn.execute("SELECT id, name FROM product").fetchall()
    conn.executemany(
        "UPDATE product SET name_fold = ? WHERE id = ?",
        [(fold_for_search(name), row_id) for row_id, name in rows],
    )
