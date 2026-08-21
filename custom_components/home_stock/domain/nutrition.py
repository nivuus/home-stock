"""What a movement is worth, in kilocalories and in euros.

Both are frozen into the movement row when it happens: changing an article's price
or its Open Food Facts record later must never rewrite the past.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from ..const import MACRO_COLUMNS


@dataclass(frozen=True)
class MovementValues:
    """Values frozen on a movement. None means unknown, 0.0 means measured at zero."""

    kcal: float | None
    cost: float | None
    macros: Mapping[str, float | None] = field(default_factory=dict)


def movement_values(
    quantity: float,
    kcal_per_base_unit: float | None,
    price_per_base_unit: float | None,
    macro_rates: Mapping[str, float | None] | None = None,
) -> MovementValues:
    """Compute the kcal, cost and macros of a movement. Never rounds.

    `macros` always carries all eight keys, even when the rates given are
    partial or absent: the caller writes this mapping straight into the
    movement row, and a missing key there would leave a column unwritten
    instead of an explicit NULL — the two look identical in SQLite until you
    try to tell "no data" from "never asked".
    """
    magnitude = abs(float(quantity))
    rates = macro_rates or {}
    return MovementValues(
        kcal=None if kcal_per_base_unit is None else magnitude * kcal_per_base_unit,
        cost=None if price_per_base_unit is None else magnitude * price_per_base_unit,
        macros={
            column: (None if rates.get(column) is None else magnitude * rates[column])
            for column in MACRO_COLUMNS
        },
    )
