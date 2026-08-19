"""Which catalogue product does this scanned article belong to?

Pure and deterministic, so it can be run against the real 299-product
catalogue in a test. Getting this wrong writes one article's nutrition onto
another product's recipes, which is why the preselection thresholds are
deliberately timid: when the answer is not obvious, the panel asks.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Final

PRESELECT_SCORE: Final = 0.75
PRESELECT_MARGIN: Final = 0.10

# NFD splits an accented letter into letter plus combining mark, but leaves the
# œ/æ ligatures alone: they are single code points. Expand them by hand or
# "œufs" never matches a product named "Œufs".
_LIGATURES: Final = {"œ": "oe", "æ": "ae", "Œ": "OE", "Æ": "AE"}
_NON_WORD = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class Candidate:
    product_id: int
    name: str
    score: float


def normalise(text: str) -> str:
    """Case-, accent- and punctuation-free form, with simple plurals trimmed."""
    for ligature, expanded in _LIGATURES.items():
        text = text.replace(ligature, expanded)
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    words = _NON_WORD.sub(" ", stripped.casefold()).split()
    # Trim a trailing plural s, but only on words long enough for it to be one:
    # "os" and "gaz" are not plurals.
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


def strip_brand(name: str, brands: str | None) -> str:
    """Drop the brand from a commercial name: it is noise for matching."""
    if not brands:
        return name
    result = name
    for brand in brands.split(","):
        brand = brand.strip()
        if brand:
            result = re.sub(re.escape(brand), " ", result, flags=re.IGNORECASE)
    return " ".join(result.split())


def _score(left: str, right: str) -> float:
    """Half string similarity, half word overlap.

    Similarity alone rates "Yaourt nature" and "Yaourt sucré" far too close;
    overlap alone ignores word order and spelling entirely. Together they
    behave on the real catalogue.
    """
    if not left or not right:
        return 0.0
    left_words, right_words = set(left.split()), set(right.split())
    overlap = len(left_words & right_words) / len(left_words | right_words)
    ratio = SequenceMatcher(None, left, right).ratio()
    return round(0.5 * ratio + 0.5 * overlap, 4)


def candidates(*, names: Sequence[str | None], products: Sequence[dict[str, Any]],
               limit: int = 5) -> list[Candidate]:
    """Rank catalogue products against every name OFF offers for the article."""
    wanted = [normalise(name) for name in names if name]
    wanted = [name for name in wanted if name]
    if not wanted:
        return []

    found = [
        Candidate(
            product_id=product["id"],
            name=product["name"],
            score=max(_score(name, normalise(product["name"])) for name in wanted),
        )
        for product in products
    ]
    # Sort by score, then by id: two identically-named products must not swap
    # places between two runs.
    found.sort(key=lambda c: (-c.score, c.product_id))
    return [c for c in found[:limit] if c.score > 0]


def preselect(found: Sequence[Candidate]) -> Candidate | None:
    """The one candidate the panel may tick on its own — or nothing.

    Requires both a strong best score and a clear gap to the runner-up: a
    hesitation between two products is exactly what a human is for.
    """
    if not found:
        return None
    best = found[0]
    if best.score <= PRESELECT_SCORE:
        return None
    if len(found) > 1 and best.score - found[1].score <= PRESELECT_MARGIN:
        return None
    return best
