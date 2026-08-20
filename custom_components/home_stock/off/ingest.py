"""Turn one Open Food Facts record into `article` column writes.

The single place that answers "given this OFF record, what should `article`
hold?" — used both when a fresh scan creates an article
(`websocket_api.article_create`) and when a background pass refreshes an
existing one (`services._write_resync`). The two used to carry their own
copy of the twelve-column map, and only one of them applied the defensive
value-dropping and the `off_raw` size ceiling — exactly the asymmetry
`validators.py`'s own docstring warns about: neither surface is allowed to
be the weaker one. One function now, called from both.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Final

import voluptuous as vol

from ..validators import bounded_int, bounded_text, finite_float
from .mapping import (
    MAX_NET_QUANTITY,
    MIN_NET_QUANTITY,
    map_article,
    nutrition_per_base_unit,
    plausible_serving,
    to_article_columns,
)

# A real Open Food Facts record is a few kilobytes; 256 kB is generous
# headroom without letting one scan (or one resync card) grow the database
# without bound. There is no meaningful way to store "most of" a JSON
# document, so a record over this size loses off_raw rather than being
# truncated.
MAX_OFF_RAW_BYTES: Final = 256 * 1024

_GRADE: Final = vol.In(("a", "b", "c", "d", "e"))
_NOVA: Final = vol.Any(vol.All(bounded_int, vol.In((1, 2, 3, 4))), None)
_TEXT: Final = bounded_text
_NON_NEGATIVE_FLOAT: Final = vol.Any(vol.All(finite_float, vol.Range(min=0)), None)
# Same plausibility window off/mapping.py's own net-weight parsing uses.
_NET_QUANTITY: Final = vol.Any(
    vol.All(finite_float, vol.Range(min=MIN_NET_QUANTITY, max=MAX_NET_QUANTITY)), None)

# Columns an Open Food Facts record may write onto `article`. Also the
# columns a human may hand-correct through the panel — websocket_api's
# ARTICLE_EDITABLE is this same dict, imported under its own name: an OFF
# answer and a person's correction land on the same set of columns,
# validated the same way, by design.
ARTICLE_OFF_SCHEMA: Final[dict[str, Callable[[Any], Any]]] = {
    "label": _TEXT,
    "brand": _TEXT,
    "net_quantity": _NET_QUANTITY,
    "image": _TEXT,
    "kcal_per_base_unit": _NON_NEGATIVE_FLOAT,
    "proteins": _NON_NEGATIVE_FLOAT,
    "carbohydrates": _NON_NEGATIVE_FLOAT,
    "sugars": _NON_NEGATIVE_FLOAT,
    "added_sugars": _NON_NEGATIVE_FLOAT,
    "fat": _NON_NEGATIVE_FLOAT,
    "saturated_fat": _NON_NEGATIVE_FLOAT,
    "fiber": _NON_NEGATIVE_FLOAT,
    "salt": _NON_NEGATIVE_FLOAT,
    "serving_quantity": _NON_NEGATIVE_FLOAT,
    "nutriscore": vol.Any(_GRADE, None),
    "nova": _NOVA,
    "ecoscore": _TEXT,
    # Free text from a collaborative database, exactly like label/brand: a
    # long tag list (many allergens, many additives) belongs under the same
    # cap, not an unbounded one just because it happens to be a join of tags
    # rather than a single name — drop_invalid_off_values reports whichever
    # one it drops the same way it already does for label.
    "allergens": _TEXT,
    "traces": _TEXT,
    "additives": _TEXT,
    "off_labels": _TEXT,
}


def drop_invalid_off_values(values: dict[str, Any]) -> list[str]:
    """Validate the OFF-derived entries of `values` against
    ARTICLE_OFF_SCHEMA, IN PLACE, dropping whichever fail instead of
    refusing the whole write.

    Deliberately not the same policy a person's own typed correction gets
    (refused outright, so they can fix what they typed): an Open Food Facts
    contributor's typo is not something the person scanning a barcode, or
    the background resync, can fix, and refusing the whole write over one
    bad field (a Nova group of 99, a Nutri-Score of "zzz") would make both
    paths useless exactly when they matter most. off/mapping.py already
    guards the two fields most likely to be implausible (nova, nutriscore)
    at the source; this is the general backstop for whatever it does not —
    chiefly free text with no length bound of its own (label, brand, image,
    ecoscore, allergens, traces, additives, off_labels).

    Returns the column names dropped, so a caller can tell its client what
    happened instead of leaving a silently missing value to explain itself.
    """
    dropped: list[str] = []
    for column in list(values):
        if column not in ARTICLE_OFF_SCHEMA:
            continue
        try:
            values[column] = ARTICLE_OFF_SCHEMA[column](values[column])
        except vol.Invalid:
            del values[column]
            dropped.append(column)
    return dropped


@dataclass(frozen=True)
class OffIngest:
    """What one OFF record contributes to `article`, ready to write.

    `values` never contains a `None` for a mapped column and never contains
    `off_raw` when the record was too large — see `build_article_values`'s
    own docstring for why. `dropped_fields` names every OFF-derived column
    that arrived with a value but did not survive validation (the general
    backstop above), a classification map_article already rejected on its
    own (nova/nutriscore), or an oversized `off_raw`.
    """

    values: dict[str, Any]
    dropped_fields: list[str]


def build_article_values(product: dict[str, Any], off_source: str, base_unit: str, *,
                         synced_at: str) -> OffIngest:
    """Map one OFF record to the columns `article` should hold, validated
    and bounded.

    Never writes a `None` for a mapped column: `map_article` already
    returns `None` for anything it could not read, and writing that through
    unconditionally would erase a column a fuller answer (or a person) had
    already filled in — exactly what a resync against a contributor's later,
    thinner edit of the same OFF page would otherwise do. Filling a gap and
    correcting a value are both what a resync is for; erasing one silently
    is not. A value that genuinely needs clearing is a deliberate, recorded
    human act (`article/update`, which lands in `manual_fields`), never a
    side effect of someone else editing an OFF page months later. Nutrition
    already had this property by construction (`to_article_columns({})` is
    `{}`, adding nothing) — the twelve directly-mapped columns below did
    not, until now.
    """
    mapped = map_article(product, off_source)
    values: dict[str, Any] = {
        "label": mapped.label, "brand": mapped.brand,
        "net_quantity": mapped.net_quantity, "image": mapped.image,
        "nutriscore": mapped.nutriscore, "nova": mapped.nova,
        "ecoscore": mapped.ecoscore, "allergens": mapped.allergens,
        "traces": mapped.traces, "additives": mapped.additives,
        "off_labels": mapped.off_labels, "off_source": mapped.off_source,
    }
    per_base = nutrition_per_base_unit(mapped.nutrition_per_100, base_unit, mapped.net_quantity)
    # to_article_columns renames `kcal` to the article's own
    # `kcal_per_base_unit` — see off/mapping.py's own docstring for why
    # skipping this renaming would silently drop the calories.
    values.update(to_article_columns(per_base))

    # La portion vient de la MEME fonction que le remplissage retroactif de
    # m003 : deux copies de ces bornes divergeraient, et la divergence ne se
    # verrait nulle part.
    values["serving_quantity"] = plausible_serving(
        product.get("serving_quantity"), base_unit=base_unit,
        net_quantity=mapped.net_quantity)

    # See this function's own docstring: a gap OFF did not fill this time
    # must not erase a value a fuller answer already put there.
    values = {column: value for column, value in values.items() if value is not None}

    dropped_fields = drop_invalid_off_values(values)
    # off/mapping.py neutralises an implausible nova/nutriscore before this
    # function ever sees it, so the drop above never has a bad value left to
    # catch for those two columns — merge in what map_article already
    # recorded in its own `rejections`, so a caller finds out about those
    # too, not just the ones drop_invalid_off_values catches.
    for name in mapped.rejections:
        if name in ARTICLE_OFF_SCHEMA and name not in dropped_fields:
            dropped_fields.append(name)

    raw_json = json.dumps(product, ensure_ascii=False)
    if len(raw_json.encode("utf-8")) <= MAX_OFF_RAW_BYTES:
        values["off_raw"] = raw_json
    else:
        dropped_fields.append("off_raw")

    values["off_synced_at"] = synced_at
    return OffIngest(values=values, dropped_fields=dropped_fields)
