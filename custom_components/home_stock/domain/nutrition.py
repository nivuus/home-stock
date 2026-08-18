"""What a movement is worth, in kilocalories and in euros.

Both are frozen into the movement row when it happens: changing an article's price
or its Open Food Facts record later must never rewrite the past.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..const import COUNTED_REASONS


@dataclass(frozen=True)
class MovementValues:
    """Values frozen on a movement. None means unknown, 0.0 means measured at zero."""

    kcal: float | None
    cost: float | None


def movement_values(
    quantity: float,
    kcal_per_base_unit: float | None,
    price_per_base_unit: float | None,
) -> MovementValues:
    """Compute the kcal and cost of a movement. Never rounds."""
    magnitude = abs(float(quantity))
    return MovementValues(
        kcal=None if kcal_per_base_unit is None else magnitude * kcal_per_base_unit,
        cost=None if price_per_base_unit is None else magnitude * price_per_base_unit,
    )


def counts_in_daily_totals(reason: str) -> bool:
    """Whether a movement counts towards the daily kcal and cost (spec 7.5)."""
    return reason in COUNTED_REASONS
