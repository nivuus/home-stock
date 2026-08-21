"""Turn one Open Food Facts record into the columns of `article`.

Pure: no network, no hass, no SQLite. That is deliberate — the rules encoded
here (per-100 g versus per-serving, the plausibility guards, the refusal to
invent a net weight) are the ones that produced Grocy's thousand-fold-wrong
spinach, and they must be testable on a fixture without starting anything.

Nutrition leaves this module PER 100 g/ml. Bringing it down to the product's
base unit needs the product, which may not exist yet when a barcode is first
scanned: that is `nutrition_per_base_unit`'s job. Renaming the result onto
`article`'s actual column names is `to_article_columns`'s job.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Final

from ..aisles import resolve_aisle
from ..const import BASE_UNITS, MAX_SERVING
# Re-exported: the table lives in the domain since lot 3 (recipes need it and
# may not import a data provider), but lot 1's callers still import it here.
from ..domain.units import UNIT_TO_BASE

# Our internal nutrition keys, mapped to the OFF nutriment name each one
# reads (e.g. "energy-kcal_100g"). This is NOT the list of `article` columns:
# `kcal` here becomes `article.kcal_per_base_unit`, not `article.kcal`. See
# `to_article_columns` for the translation that actually produces column
# names — repo.insert_article silently drops keys it does not recognise, so
# that translation must never be skipped.
NUTRIMENT_KEYS: Final = {
    "kcal": "energy-kcal",
    "proteins": "proteins",
    "carbohydrates": "carbohydrates",
    "sugars": "sugars",
    "added_sugars": "added-sugars",
    "fat": "fat",
    "saturated_fat": "saturated-fat",
    "fiber": "fiber",
    "salt": "salt",
}

# How each internal nutrition key is actually named on `article`. Only `kcal`
# differs (`kcal_per_base_unit`); the rest keep their name.
_ARTICLE_COLUMN_NAMES: Final = {
    key: ("kcal_per_base_unit" if key == "kcal" else key) for key in NUTRIMENT_KEYS
}

MIN_NET_QUANTITY: Final = 0.5
MAX_NET_QUANTITY: Final = 50_000.0
MAX_KCAL_PER_100: Final = 900.0      # pure fat tops out at 884
MAX_MACRO_PER_100: Final = 100.0
MAX_MACRO_SUM: Final = 105.0         # 100 plus a rounding allowance

# The only four NOVA groups OFF's classification uses, and the only five
# Nutri-Score letter grades. A contributor typo (a Nova group of 99, a
# Nutri-Score of "zzz") is exactly the kind of thing this module already
# refuses for nutrition — the same policy, extended to these two fields.
NOVA_GROUPS: Final = (1, 2, 3, 4)
NUTRISCORE_GRADES: Final = ("a", "b", "c", "d", "e")

# OFF's own way of saying "there is no grade for this product" — not a
# contributor's typo. 14 of 51 real fixture records carry "unknown" here:
# reporting that as a dropped/rejected value would tell the user something
# was ignored on more than a quarter of ordinary scans, when nothing usable
# was ever offered in the first place.
_OFF_NO_VALUE: Final = frozenset({"unknown", "not-applicable"})

# A number, optionally with a decimal part. "1,kg" must NOT parse: a lenient
# comma-to-dot replacement turns it into 1.0 and invents a one-kilogram pack.
_NUMBER = re.compile(r"^\d+(?:[.,]\d+)?$")


@dataclass(frozen=True)
class MappedArticle:
    """What one OFF record has to say about an article."""

    off_source: str
    aisle: str
    label: str | None = None
    generic_name: str | None = None
    brand: str | None = None
    net_quantity: float | None = None
    net_unit: str | None = None
    image: str | None = None
    nutriscore: str | None = None
    nova: int | None = None
    ecoscore: str | None = None
    allergens: str | None = None
    traces: str | None = None
    additives: str | None = None
    off_labels: str | None = None
    nutrition_per_100: dict[str, float] | None = None
    rejections: tuple[str, ...] = field(default_factory=tuple)


def _number(value: Any) -> float | None:
    """Read a number OFF may have stored as a string, refusing what is malformed."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str) and _NUMBER.match(value.strip()):
        return float(value.strip().replace(",", "."))
    return None


def parse_net_quantity(product: dict[str, Any]) -> tuple[float, str] | None:
    """The net weight or volume, in base units. None when OFF is not usable."""
    amount = _number(product.get("product_quantity"))
    unit = str(product.get("product_quantity_unit") or "").strip().lower()
    if amount is None or unit not in UNIT_TO_BASE:
        return None
    base_unit, factor = UNIT_TO_BASE[unit]
    quantity = amount * factor
    if not MIN_NET_QUANTITY <= quantity <= MAX_NET_QUANTITY:
        return None
    return quantity, base_unit


def _tags(product: dict[str, Any], key: str) -> str | None:
    """Read a tag list, without corrupting the rare record where OFF stored one
    tag as a bare string instead of a one-element list.

    `", ".join("en:milk")` silently yields `"e, n, :, m, i, l, k"` — a string
    is iterable character by character, and `join` does not know it was
    handed the wrong shape. Only join when we actually have a list.
    """
    values = product.get(key)
    if not values:
        return None
    if isinstance(values, str):
        return values
    return ", ".join(values)


def _nutrition_per_100(product: dict[str, Any]) -> tuple[dict[str, float] | None, list[str]]:
    """Read the nutrition table, per 100 g/ml, or refuse it entirely."""
    nutriments = product.get("nutriments") or {}
    values: dict[str, float] = {}

    for column, off_key in NUTRIMENT_KEYS.items():
        value = _number(nutriments.get(f"{off_key}_100g"))
        if value is not None:
            values[column] = value

    if not values:
        # No per-100 table. OFF sometimes only fills the per-serving one.
        serving = _number(product.get("serving_quantity"))
        if serving and serving > 0 and product.get("nutrition_data_per") == "serving":
            for column, off_key in NUTRIMENT_KEYS.items():
                value = _number(nutriments.get(f"{off_key}_serving"))
                if value is not None:
                    values[column] = value * 100.0 / serving

    # `*_prepared_100g` describes the reconstituted product — a soup once
    # water is added, canned chickpeas before draining. We stock what is on
    # the shelf, so those values are never read. Real household records hit
    # this exactly like the fabricated ones: canned chickpeas and a bouillon
    # cube both carry only `*_prepared_100g` keys in the fixtures.
    if not values:
        return None, ["no usable nutrition table"]

    # Calories per day are the whole point of this accounting: a table that
    # has some nutriments but no energy value is not a usable nutrition
    # table, and must not be handed out half-built (a caller indexing
    # ["kcal"] would raise, not fail safely).
    if "kcal" not in values:
        return None, ["no energy value"]

    rejections: list[str] = []
    kcal = values["kcal"]
    if not 0 <= kcal <= MAX_KCAL_PER_100:
        rejections.append(f"kcal per 100 out of range: {kcal}")
    for column in ("proteins", "carbohydrates", "sugars", "added_sugars", "fat",
                   "saturated_fat", "fiber", "salt"):
        value = values.get(column)
        if value is not None and not 0 <= value <= MAX_MACRO_PER_100:
            rejections.append(f"{column} per 100 out of range: {value}")
    macro_sum = sum(values.get(c, 0.0) for c in ("proteins", "carbohydrates", "fat"))
    if macro_sum > MAX_MACRO_SUM:
        rejections.append(f"proteins + carbohydrates + fat exceed 100 g: {macro_sum}")

    # One bad number condemns the whole table: a record wrong about its fat is
    # not a record to be trusted about its salt.
    if rejections:
        return None, rejections
    return values, []


def _off_offered(value: Any) -> bool:
    """True when OFF actually offered something for this field, as opposed
    to nothing at all (`None`) or one of its own "no grade" sentinels
    ("unknown", "not-applicable") — both mean "OFF has no answer", not "OFF
    answered something implausible", so neither counts as a rejection."""
    if value is None:
        return False
    if isinstance(value, str) and value.strip().lower() in _OFF_NO_VALUE:
        return False
    return True


def _plausible_nova(value: Any) -> int | None:
    """OFF's nova_group, kept only if it is a whole number among the four
    real groups. A value like 1e30 would otherwise reach `int()` here and
    only fail later, uncaught, when it is eventually bound as a SQLite
    parameter — refused at the source instead."""
    number = _number(value)
    if number is None:
        return None
    whole = int(number)
    if whole != number or whole not in NOVA_GROUPS:
        return None
    return whole


def _plausible_nutriscore(value: Any) -> str | None:
    """OFF's nutriscore_grade, kept only if it is one of the five real
    grades (case-folded: real records are lowercase, but nothing guarantees
    it)."""
    if not isinstance(value, str):
        return None
    grade = value.strip().lower()
    return grade if grade in NUTRISCORE_GRADES else None


def map_article(product: dict[str, Any], off_source: str) -> MappedArticle:
    """Read one OFF record.

    Raises `ValueError` if `product` is not a dict — including OFF's own
    "not found" response, which comes back as `None`: a caller must never be
    able to map a not-found response by accident. For any actual dict, this
    never raises: whatever is unusable inside it (a malformed number, an
    out-of-range macro, a missing net weight) is left out of the result
    instead.
    """
    if not isinstance(product, dict):
        raise ValueError("map_article requires an OFF product dict")

    net = parse_net_quantity(product)
    nutrition, rejections = _nutrition_per_100(product)
    rejections = list(rejections)

    # A value was sent but did not survive the plausibility check: recorded
    # by column name (not a sentence, unlike the nutrition rejections above)
    # so a caller — article_create's off_dropped_fields — can merge these
    # straight in without having to parse free-form English out of them.
    # Only counted when OFF actually sent something: a field that was never
    # present is an absence, not a rejection.
    nutriscore_raw = product.get("nutriscore_grade")
    nutriscore = _plausible_nutriscore(nutriscore_raw)
    if _off_offered(nutriscore_raw) and nutriscore is None:
        rejections.append("nutriscore")

    nova_raw = product.get("nova_group")
    nova = _plausible_nova(nova_raw)
    if _off_offered(nova_raw) and nova is None:
        rejections.append("nova")

    return MappedArticle(
        off_source=off_source,
        aisle=resolve_aisle(product.get("categories_tags"), off_source),
        label=product.get("product_name_fr") or product.get("product_name") or None,
        generic_name=product.get("generic_name_fr") or product.get("generic_name") or None,
        brand=product.get("brands") or None,
        net_quantity=net[0] if net else None,
        net_unit=net[1] if net else None,
        image=product.get("image_front_url") or None,
        nutriscore=nutriscore,
        nova=nova,
        ecoscore=(product.get("ecoscore_grade") or None),
        allergens=_tags(product, "allergens_tags"),
        traces=_tags(product, "traces_tags"),
        additives=_tags(product, "additives_tags"),
        off_labels=_tags(product, "labels_tags"),
        nutrition_per_100=nutrition,
        rejections=tuple(rejections),
    )


def nutrition_per_base_unit(
    nutrition_per_100: dict[str, float] | None,
    base_unit: str,
    net_quantity: float | None,
) -> dict[str, float] | None:
    """Bring a per-100 table down to one base unit of the product.

    A product stocked in pieces needs its net weight to say what one piece
    contains. Without it we return None: a NULL is visible in the panel and
    fixable by hand, an invented factor is neither.

    Raises `ValueError` for any `base_unit` other than `g`, `ml` or `piece` —
    a caller must never be able to pass OFF's own unit (`kg`, `cl`, ...) here
    by mistake and get a silently wrong factor back.
    """
    if not nutrition_per_100:
        return None
    if base_unit not in BASE_UNITS:
        raise ValueError(f"unknown base unit: {base_unit!r}")
    if base_unit in ("g", "ml"):
        factor = 1 / 100
    elif net_quantity and net_quantity > 0:
        factor = net_quantity / 100
    else:
        return None
    return {column: value * factor for column, value in nutrition_per_100.items()}


def to_article_columns(per_base_unit: dict[str, float] | None) -> dict[str, float]:
    """Rename our internal nutrition keys to the article's column names.

    `kcal` is stored in `article.kcal_per_base_unit`; the other eight keep
    their name. `repo.insert_article` silently drops keys it does not know,
    so a caller passing the raw dict would lose the calories and nothing
    would say so — this function is the seam meant to prevent exactly that.
    A silent filter would BE that same failure mode one level up, so an
    unrecognised key raises instead of vanishing.
    """
    if not per_base_unit:
        return {}
    unexpected = sorted(set(per_base_unit) - set(_ARTICLE_COLUMN_NAMES))
    if unexpected:
        raise ValueError(f"unexpected nutrition keys: {unexpected}")
    return {_ARTICLE_COLUMN_NAMES[key]: value for key, value in per_base_unit.items()}


def plausible_serving(value: Any, *, base_unit: str,
                      net_quantity: float | None) -> float | None:
    """Open Food Facts' serving size, or nothing.

    Three refusals, in this order: a product tracked by the piece (a serving
    there is worth one piece, a number of grams means nothing), a value that
    is unreadable or outside `]0 ; MAX_SERVING]`, and a serving bigger than
    the pack itself — Open Food Facts is collaborative, and "300 g" on a
    250 g jar is a typo, not a serving.
    """
    if base_unit not in ("g", "ml"):
        return None
    number = _number(value)
    if number is None or not 0 < number <= MAX_SERVING:
        return None
    if net_quantity is not None and number > net_quantity:
        return None
    return number


def serving_from_raw(raw: str | None, *, base_unit: str,
                     net_quantity: float | None) -> float | None:
    """The serving read from the raw record already stored (`article.off_raw`).

    Anything that is not a usable JSON object yields `None` without raising:
    this reading serves a display convenience, never a value the stock
    depends on, and it runs inside a migration that a truncated `off_raw`
    must not be able to fail.
    """
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return plausible_serving(payload.get("serving_quantity"),
                             base_unit=base_unit, net_quantity=net_quantity)
