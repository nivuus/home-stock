"""Case- and accent-insensitive search on names, shared by every read that searches.

Pure: no database here. `fold_for_search` is the one folding both sides of a
comparison go through (the voice path's query_stock, the catalogue's
products/list); `escape_like` makes a value literal inside a LIKE pattern, and
`like_pattern` turns what a user typed into the pattern matching folded names
containing it.
"""
from __future__ import annotations

import unicodedata
from typing import Final

# NFD decomposition splits an accented letter into the base letter plus a
# combining mark, but it does NOT split the œ/æ ligatures — those are single
# code points, not a letter plus an accent. Expand them by hand first, or
# "œufs" never matches a product named "Œufs" (services.yaml promises
# case- and accent-insensitive matching for query_stock, the voice path).
_LIGATURES: Final = {"œ": "oe", "æ": "ae", "Œ": "OE", "Æ": "AE"}

# The character that makes the next %, _ or itself literal in a LIKE pattern;
# the SQL using `like_pattern` must say ESCAPE with this very character.
LIKE_ESCAPE: Final = "\\"


def fold_for_search(text: str) -> str:
    """Case- and accent-insensitive form of `text`."""
    for ligature, expanded in _LIGATURES.items():
        text = text.replace(ligature, expanded)
    decomposed = unicodedata.normalize("NFD", text)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_accents.casefold()


def escape_like(value: str) -> str:
    """Escape SQL LIKE wildcards so `value` is matched literally, not as a pattern.

    A HA service call or a voice-generated idempotency key can legally contain
    '%' or '_', both of which are LIKE wildcards. Without escaping, a key like
    "dinner_1" would also match rows keyed "dinnerX1#1" and a replay would
    return movement ids belonging to a different consumption.
    """
    for special in (LIKE_ESCAPE, "%", "_"):
        value = value.replace(special, LIKE_ESCAPE + special)
    return value


def like_pattern(search: str | None) -> str | None:
    """`%<folded search>%`, wildcards escaped; None when there is nothing to search.

    A user typing "100%" or "thé_vert" means those characters, not LIKE's
    "any run" and "any one character": both are escaped, and so is the escape
    character itself.
    """
    needle = fold_for_search(search or "").strip()
    if not needle:
        return None
    return f"%{escape_like(needle)}%"
