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
    # "os" and "gaz" are not plurals. This is symmetric folding, not a
    # linguistically correct French pluraliser: an invariant singular like
    # "ananas" or "couscous" gets trimmed too ("anana", "couscou"), but since
    # both sides of every comparison go through the same trim, an invariant
    # singular still folds to itself and still matches itself consistently.
    # A real pluraliser would fix that at the cost of a permanent dependency,
    # for a collision nobody has demonstrated in the real catalogue.
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


def strip_brand(name: str, brands: str | None) -> str:
    """Drop the brand from a commercial name: it is noise for matching."""
    if not brands:
        return name
    result = name
    for brand in brands.split(","):
        brand = brand.strip()
        if brand:
            # Anchor with lookarounds rather than substring replace or `\b`:
            # a bare substring match would corrupt "Porc fumé Or Label" into
            # "P c fumé Label" when stripping brand "Or", and `\b` misbehaves
            # when the brand itself ends in punctuation, as "Bjorg (bio)" does.
            pattern = rf"(?<!\w){re.escape(brand)}(?!\w)"
            result = re.sub(pattern, " ", result, flags=re.IGNORECASE)
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
    hesitation between two products is exactly what a human is for. Both
    boundaries are exclusive on purpose: a score of exactly PRESELECT_SCORE,
    or a margin of exactly PRESELECT_MARGIN, is not "clearly above" — it is
    the threshold itself, and does not preselect.
    """
    if not found:
        return None
    best = found[0]
    if best.score <= PRESELECT_SCORE:
        return None
    if len(found) > 1 and best.score - found[1].score <= PRESELECT_MARGIN:
        return None
    return best


# --- lot 4 : rapprocher une ligne de caisse d'une ligne de panier -----------
#
# Les seuils du lot 1 sont INCHANGÉS : `preselect` reste le seul arbitre, et
# un ajustement fait ici déplacerait aussi l'appariement d'ingrédients du
# lot 3, qui lit les mêmes constantes.

# Deux prix qui coïncident à 1 % près décrivent probablement le même article.
# Au-delà, ils ne disent plus rien : les rayons sont pleins d'articles au
# même prix.
PRICE_BONUS_TOLERANCE: Final = 0.01
# La prime AIDE, elle ne décide pas. 0,10 est le tiers de l'écart qui sépare
# une similarité passable d'un `auto` : assez pour départager deux candidats
# proches, jamais assez pour porter seul un libellé qui ne ressemble à rien.
PRICE_BONUS: Final = 0.10


@dataclass(frozen=True)
class LineMatch:
    """Une ligne de panier candidate au rapprochement d'une ligne de caisse.

    Un type distinct de `Candidate`, et pas le même avec `product_id` détourné
    en `line_id` : un champ qui ment sur ce qu'il porte est exactement le
    genre de piège que ce dépôt passe son temps à désamorcer. `preselect` ne
    lit que `.score`, donc il arbitre les deux sans rien savoir de plus.
    """

    line_id: int
    label: str
    score: float


def receipt_candidates(*, label: str, lines: Sequence[dict[str, Any]],
                       unit_price: float | None) -> list[LineMatch]:
    """Classer les lignes du panier face à un libellé de caisse.

    Similarité de chaîne, marque comprise puis marque retirée — un libellé de
    caisse nomme parfois la marque et pas le produit (« PANZANI COQ »), et
    parfois l'inverse. Plus une prime de proximité de prix : deux lignes dont
    les prix unitaires coïncident à 1 % près se rapprochent même quand les
    libellés divergent, cas normal des abréviations de caisse.
    """
    wanted = normalise(label)
    if not wanted or not lines:
        return []
    found: list[LineMatch] = []
    for line in lines:
        raw_label = line.get("article_label") or ""
        names = [raw_label, strip_brand(raw_label, line.get("brand")),
                 line.get("brand") or ""]
        score = max(
            (_score(wanted, normalise(name)) for name in names if name),
            default=0.0)
        score += _price_bonus(unit_price, line.get("unit_price"))
        found.append(LineMatch(line_id=int(line["id"]), label=raw_label,
                               score=round(min(score, 1.0), 4)))
    found.sort(key=lambda match: (-match.score, match.line_id))
    return [match for match in found if match.score > 0]


def _price_bonus(observed: float | None, expected: float | None) -> float:
    if observed is None or expected is None or expected <= 0:
        return 0.0
    if abs(observed - expected) <= expected * PRICE_BONUS_TOLERANCE:
        return PRICE_BONUS
    return 0.0
