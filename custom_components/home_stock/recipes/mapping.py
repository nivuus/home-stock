"""A TheMealDB card, turned into recipe rows.

Pure: no network, no `hass`, no SQLite. The card arrives as a plain mapping
and leaves as value objects, so every reading rule below is testable without
a socket and without a database.

The one rule that governs the whole module: **nothing is guessed**. A measure
that cannot be read leaves `(None, None)` and the text travels on untouched in
`raw_text`. "a handful" has no number and no unit, and pretending otherwise
would write a false decrement into an append-only journal.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

# TheMealDB always ships exactly twenty ingredient/measure pairs, most of them
# empty. The count is the source's, not ours: reading further would invent
# slots, reading fewer would silently truncate a long recipe.
SLOT_COUNT: Final = 20

# Vulgar fractions as the source actually writes them.
_VULGAR: Final = {
    "¼": 0.25, "½": 0.5, "¾": 0.75, "⅐": 1 / 7, "⅑": 1 / 9, "⅒": 0.1,
    "⅓": 1 / 3, "⅔": 2 / 3, "⅕": 0.2, "⅖": 0.4, "⅗": 0.6, "⅘": 0.8,
    "⅙": 1 / 6, "⅚": 5 / 6, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875,
}

# A leading quantity: an optional whole part, then either a vulgar fraction, an
# ASCII fraction, or a decimal. A range ("1-2 cloves") keeps its LOW bound —
# planning for the smaller amount can be topped up by hand, planning for the
# larger silently takes stock that was never needed.
_QUANTITY: Final = re.compile(
    r"""^\s*
    (?:
        # The ratio and the bare fraction come FIRST: "3/4" must not be read
        # as the whole number 3 with a leftover "/4" — which is exactly what
        # happens if the whole-number branch is allowed to try first.
        (?P<ratio>\d+\s*/\s*\d+)
      | (?P<fraction>[¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞])
      | (?P<whole>\d+(?:[.,]\d+)?)      # 1, 1.5, 1,5
        (?:\s*[-–—]\s*\d+(?:[.,]\d+)?)? # ignored high bound of a range
        (?:\s*(?P<mixed>[¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞]|\d+\s*/\s*\d+))?
    )
    \s*""",
    re.VERBOSE,
)


def _as_number(text: str) -> float:
    text = text.strip()
    if text in _VULGAR:
        return _VULGAR[text]
    if "/" in text:
        numerator, _, denominator = text.partition("/")
        return float(numerator.strip()) / float(denominator.strip())
    return float(text.replace(",", "."))


def parse_measure(text: str | None) -> tuple[float | None, str | None]:
    """Split "2 tbsp" into `(2.0, "tbsp")`. Never guesses.

    Returns `(None, None)` whenever the text does not START with a number:
    "a handful" and "to taste" are prose, not quantities, and the caller keeps
    the whole string as provenance instead. A bare number keeps its `None`
    unit — "2" of something is a count, and which unit that is depends on the
    product, which this module does not know.

    The unit is returned exactly as the source spells it, NOT converted:
    converting here would hide where a conversion happened, and the same text
    resolves differently depending on the product it ends up matched to.
    """
    if not isinstance(text, str) or not text.strip():
        return None, None
    match = _QUANTITY.match(text)
    if match is None:
        return None, None
    amount = _as_number(match["whole"] or match["fraction"] or match["ratio"])
    if match["whole"] and match["mixed"]:
        amount += _as_number(match["mixed"])
    unit = text[match.end():].strip()
    return amount, unit or None


@dataclass(frozen=True)
class SourceIngredient:
    position: int
    name: str
    raw_text: str          # "2 tbsp olive oil", measure and name reassembled
    amount: float | None
    unit: str | None       # as the source writes it, NOT converted


@dataclass(frozen=True)
class SourceRecipe:
    name: str
    source_ref: str
    image_url: str | None
    source_url: str | None
    instructions: str      # the block, undivided — adaptation cuts it up
    ingredients: tuple[SourceIngredient, ...]


def _text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def map_meal(payload: Mapping[str, Any]) -> SourceRecipe | None:
    """One card into one `SourceRecipe`, or None if it is not usable.

    A card with no name or no id is not a recipe we could ever find again, so
    it is refused outright rather than stored as an orphan.

    Empty slots in the middle are normal — TheMealDB leaves `strIngredient7`
    blank between two filled ones. Positions are RENUMBERED over what was
    actually found, never left with the holes in them: a gap in `position`
    would show up as a missing line in the cooking view.
    """
    if not isinstance(payload, Mapping):
        return None
    name = _text(payload, "strMeal")
    source_ref = _text(payload, "idMeal")
    if not name or not source_ref:
        return None

    ingredients: list[SourceIngredient] = []
    for slot in range(1, SLOT_COUNT + 1):
        ingredient_name = _text(payload, f"strIngredient{slot}")
        if not ingredient_name:
            continue
        measure = _text(payload, f"strMeasure{slot}")
        amount, unit = parse_measure(measure)
        ingredients.append(SourceIngredient(
            position=len(ingredients) + 1,
            name=ingredient_name,
            # Provenance, verbatim: `raw_text` has the same status as
            # `article.off_raw`. It is what the source said, never a
            # computation, and no decrement code is allowed to read it.
            raw_text=f"{measure} {ingredient_name}".strip(),
            amount=amount,
            unit=unit,
        ))

    return SourceRecipe(
        name=name,
        source_ref=source_ref,
        image_url=_text(payload, "strMealThumb") or None,
        source_url=_text(payload, "strSource") or None,
        instructions=_text(payload, "strInstructions"),
        ingredients=tuple(ingredients),
    )
