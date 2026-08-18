"""Base units and packaging conversions.

A product has exactly one base unit, forever. Packagings ("Paquet = 500 g",
"cs = 13 ml") are a display layer: we read and enter in packagings, we store and
compute in base units. Grocy stored both and had to keep them in sync; it did not.
"""
from __future__ import annotations

from ..const import BASE_UNITS


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
