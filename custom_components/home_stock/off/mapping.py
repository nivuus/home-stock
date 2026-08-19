"""Turn one Open Food Facts record into the columns of `article`.

Pure: no network, no hass, no SQLite. That is deliberate — the rules encoded
here (per-100 g versus per-serving, the plausibility guards, the refusal to
invent a net weight) are the ones that produced Grocy's thousand-fold-wrong
spinach, and they must be testable on a fixture without starting anything.

Nutrition leaves this module PER 100 g/ml. Bringing it down to the product's
base unit needs the product, which may not exist yet when a barcode is first
scanned: that is `nutrition_per_base_unit`'s job.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Final

from ..aisles import resolve_aisle

# Columns of `article`, and the OFF nutriment key each one reads.
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
NUTRIMENT_COLUMNS: Final = tuple(NUTRIMENT_KEYS)

# Everything OFF may express a mass or a volume in, and what one unit is worth
# in our base unit. Anything else — "unité", "pcs", "portions" — is a count,
# not a weight, and is refused.
UNIT_TO_BASE: Final = {
    "g": ("g", 1.0), "gr": ("g", 1.0), "gram": ("g", 1.0), "grammes": ("g", 1.0),
    "kg": ("g", 1000.0), "mg": ("g", 0.001),
    "ml": ("ml", 1.0), "cl": ("ml", 10.0), "dl": ("ml", 100.0), "l": ("ml", 1000.0),
}

MIN_NET_QUANTITY: Final = 0.5
MAX_NET_QUANTITY: Final = 50_000.0
MAX_KCAL_PER_100: Final = 900.0      # pure fat tops out at 884
MAX_MACRO_PER_100: Final = 100.0
MAX_MACRO_SUM: Final = 105.0         # 100 plus a rounding allowance

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
    values = product.get(key)
    return ", ".join(values) if values else None


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
    # water is added. We stock the dry packet, so those values are never read.
    if not values:
        return None, ["no usable nutrition table"]

    rejections: list[str] = []
    kcal = values.get("kcal")
    if kcal is not None and not 0 <= kcal <= MAX_KCAL_PER_100:
        rejections.append(f"kcal per 100 out of range: {kcal}")
    for column in ("proteins", "carbohydrates", "sugars", "fat", "saturated_fat",
                   "fiber", "salt"):
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


def map_article(product: dict[str, Any], off_source: str) -> MappedArticle:
    """Read one OFF record. Never raises: what is unusable is left out."""
    net = parse_net_quantity(product)
    nutrition, rejections = _nutrition_per_100(product)
    nova = _number(product.get("nova_group"))

    return MappedArticle(
        off_source=off_source,
        aisle=resolve_aisle(product.get("categories_tags"), off_source),
        label=product.get("product_name_fr") or product.get("product_name") or None,
        generic_name=product.get("generic_name_fr") or product.get("generic_name") or None,
        brand=product.get("brands") or None,
        net_quantity=net[0] if net else None,
        net_unit=net[1] if net else None,
        image=product.get("image_front_url") or None,
        nutriscore=(product.get("nutriscore_grade") or None),
        nova=int(nova) if nova is not None else None,
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
    """
    if not nutrition_per_100:
        return None
    if base_unit in ("g", "ml"):
        factor = 1 / 100
    elif net_quantity and net_quantity > 0:
        factor = net_quantity / 100
    else:
        return None
    return {column: value * factor for column, value in nutrition_per_100.items()}
