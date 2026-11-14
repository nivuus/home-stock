"""Script-neutral text folding, shared by matching and search.

Dropping every combining mark after NFD is a Latin-script convention (an
accented letter and its bare form are the same letter to someone
searching), not a universal one: in Devanagari, Thai or Japanese a mark is part of the letter,
and in Cyrillic "й" and "и" are different letters. So marks are dropped only
when they sit on a Latin base letter; every other script keeps its text
whole. Words are runs of letters, marks and digits in ANY script.

Standard library only: `unicodedata` has no script property, but every
Latin letter's character name starts with "LATIN", which is the one fact
needed here. The `regex` module would give `\\p{Script=Latin}`, but Home
Assistant does not guarantee it is installed.
"""
from __future__ import annotations

import unicodedata
from functools import lru_cache
from typing import Final

# NFD leaves the oe/ae ligatures whole (single code points): expand them, or
# a word spelt with a ligature never matches its two-letter spelling.
_LIGATURES: Final = {"œ": "oe", "æ": "ae", "Œ": "OE", "Æ": "AE"}


@lru_cache(maxsize=4096)
def is_latin(char: str) -> bool:
    """Whether `char` is a Latin-script letter."""
    return unicodedata.name(char, "").startswith("LATIN ")


def _is_mark(char: str) -> bool:
    return unicodedata.category(char).startswith("M")


def fold(text: str) -> str:
    """Casefolded, with Latin diacritics removed and every other mark kept."""
    for ligature, expanded in _LIGATURES.items():
        text = text.replace(ligature, expanded)
    decomposed = unicodedata.normalize("NFD", text.casefold())
    kept: list[str] = []
    base = ""
    for char in decomposed:
        if _is_mark(char):
            if is_latin(base):
                continue
        else:
            base = char
        kept.append(char)
    return unicodedata.normalize("NFC", "".join(kept))


def words(text: str) -> list[str]:
    """Runs of letters, marks and digits, in any script."""
    found: list[str] = []
    current: list[str] = []
    for char in text:
        if unicodedata.category(char)[0] in "LMN":
            current.append(char)
        elif current:
            found.append("".join(current))
            current = []
    if current:
        found.append("".join(current))
    return found
