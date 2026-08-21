"""Base units and packaging conversions.

A product has exactly one base unit, forever. Packagings ("Paquet = 500 g",
"cs = 13 ml") are a display layer: we read and enter in packagings, we store and
compute in base units. Grocy stored both and had to keep them in sync; it did not.
"""
from __future__ import annotations

from typing import Final

from ..const import BASE_UNITS


# Everything a source may express a mass or a volume in, and what one unit is
# worth in our base unit. Anything else — "unité", "pcs", "portions" — is a
# count, not a weight, and is refused.
#
# It lives in the domain and not in `off/` because recipes need it too, and
# the domain may not import a data provider: it knows neither the network nor
# who supplies the numbers. Copying the table into a second place would give
# two truths about what a decilitre is worth, and the second one would drift.
UNIT_TO_BASE: Final = {
    "g": ("g", 1.0), "gr": ("g", 1.0), "gram": ("g", 1.0), "grammes": ("g", 1.0),
    "kg": ("g", 1000.0), "mg": ("g", 0.001),
    "ml": ("ml", 1.0), "cl": ("ml", 10.0), "dl": ("ml", 100.0), "l": ("ml", 1000.0),
}


class UnitError(ValueError):
    """Raised when a unit or a quantity cannot be used."""


def validate_base_unit(unit: str) -> str:
    """Return the unit if it is one of the three base units, raise otherwise."""
    if unit not in BASE_UNITS:
        raise UnitError(f"{unit!r} is not a base unit; expected one of {BASE_UNITS}")
    return unit


def to_base_quantity(amount: float, packaging_base_quantity: float | None = None) -> float:
    """Convert an amount, optionally expressed in packagings, into base units."""
    if amount < 0:
        raise UnitError(f"quantity must not be negative, got {amount}")
    if packaging_base_quantity is None:
        return float(amount)
    if packaging_base_quantity <= 0:
        raise UnitError(
            f"packaging quantity must be positive, got {packaging_base_quantity}"
        )
    return float(amount) * float(packaging_base_quantity)


def _french_number(value: float) -> str:
    """Render a number the French way: no trailing zeros, comma as separator."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def format_quantity(quantity: float, base_unit: str) -> str:
    """Render a quantity for display, in French."""
    validate_base_unit(base_unit)
    if base_unit == "piece":
        plural = "s" if quantity >= 2 else ""
        return f"{_french_number(quantity)} pièce{plural}"
    if base_unit == "g":
        if quantity >= 1000:
            return f"{_french_number(quantity / 1000)} kg"
        return f"{_french_number(quantity)} g"
    if quantity >= 1000:
        return f"{_french_number(quantity / 1000)} l"
    return f"{_french_number(quantity)} ml"


def convertible_amount(amount: float, unit: str | None,
                       product_base_unit: str) -> float | None:
    """`amount` expressed in `unit`, converted into `product_base_unit` —
    or None when the two do not measure the same thing.

    None means "no usable quantity", never "roughly this much". A recipe
    asking for 100 g of honey against a product stocked in millilitres does
    not become 100 ml: that would be a density, and nobody gave us one. The
    caller must treat None exactly as it treats a missing quantity — the same
    rule lot 1 already applies to a missing divisor (spec 7.4).

    No `strip()` and no `lower()` on purpose. Normalising the text of a source
    is the job of whoever knows where the string came from
    (`recipes/mapping`, `off/mapping`). A function that guesses twice can no
    longer tell you where the guess happened.
    """
    if not isinstance(unit, str) or unit not in UNIT_TO_BASE:
        return None
    dimension, factor = UNIT_TO_BASE[unit]
    if dimension != product_base_unit:
        return None
    return float(amount) * factor
