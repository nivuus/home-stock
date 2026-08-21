"""The recycling bin of a package, read on the fly from a stored record.

No column, no migration, no aggregate: the material is read once per opening
of the "manger" screen, on a single article. It is a display convenience —
anything unusable yields `None` without raising, exactly like
`mapping.serving_from_raw`.

Nothing known means nothing shown. A guessed bin would send glass into the
yellow one with the confidence of a screen.
"""
from __future__ import annotations

import json
from typing import Any, Final

from ..const import RECYCLING_BINS

# A keyword found inside the normalised material, mapped to its bin. The
# lookup is a containment test, so `pp-polypropylene` resolves through `pp`
# without enumerating every polymer Open Food Facts knows.
_MATERIAL_BINS: Final[dict[str, str]] = {
    "glass": "glass",
    "battery": "dropoff",
    "light-bulb": "dropoff",
    "wood": "household",
    "ceramic": "household",
    "plastic": "yellow",
    "pp": "yellow",
    "pet": "yellow",
    "pe": "yellow",
    "hdpe": "yellow",
    "cardboard": "yellow",
    "paper": "yellow",
    "carton": "yellow",
    "brick": "yellow",
    "metal": "yellow",
    "aluminium": "yellow",
    "steel": "yellow",
    "can": "yellow",
}


def _bin_of(material: Any) -> str | None:
    """The bin a raw material tag belongs to, or `None` when unrecognised."""
    if not isinstance(material, str):
        return None
    normalised = material.split(":", 1)[-1].strip().lower()
    if not normalised:
        return None
    for keyword, bin_key in _MATERIAL_BINS.items():
        if keyword in normalised:
            return bin_key
    return None


def _materials_of(payload: dict[str, Any]) -> list[Any]:
    """The material tags to consider: `packagings` first, tags as a fallback.

    An empty `packagings` list is a half-filled record, not a record that
    says "no packaging" — hence the fallback on emptiness, not on absence.
    """
    packagings = payload.get("packagings")
    if isinstance(packagings, list) and packagings:
        return [component.get("material")
                for component in packagings if isinstance(component, dict)]
    tags = payload.get("packaging_tags")
    if isinstance(tags, list):
        return list(tags)
    return []


def bins_from_raw(raw: str | None) -> dict[str, list[str]] | None:
    """The bins and recognised materials of a stored record, or `None`.

    `bins` follows the order of `RECYCLING_BINS`, never the reading order:
    two records describing the same package must yield the same list, or the
    line of the "manger" screen would change wording from one article to the
    next. `materials` keeps the record's own order, deduplicated, and holds
    only the materials that resolved to a bin.
    """
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None

    found: dict[str, str] = {}
    for material in _materials_of(payload):
        bin_key = _bin_of(material)
        if bin_key is not None and material not in found:
            found[material] = bin_key
    if not found:
        return None
    bins = [bin_key for bin_key in RECYCLING_BINS if bin_key in found.values()]
    return {"bins": bins, "materials": list(found)}
