"""Which batch is taken, and how much of it.

Pure functions over value objects: no database, no Home Assistant. The rules here
are the ones Grocy got wrong, so they are tested on their own.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from ..const import QUANTITY_EPSILON


@dataclass(frozen=True)
class BatchView:
    """A batch, as the allocation rules need to see it."""

    id: int
    remaining: float
    best_before: date | None
    entered_at: datetime
    opened_at: datetime | None
    price_per_base_unit: float | None
    kcal_per_base_unit: float | None


@dataclass(frozen=True)
class Allocation:
    """How much is taken from one batch, and what that fraction is worth."""

    batch_id: int
    quantity: float
    price_per_base_unit: float | None
    kcal_per_base_unit: float | None
    remaining_after: float
    closes_batch: bool


class InsufficientStock(Exception):
    """Raised instead of letting the stock go negative."""

    def __init__(self, requested: float, available: float) -> None:
        super().__init__(f"requested {requested}, only {available} available")
        self.requested = requested
        self.available = available


def is_empty(remaining: float) -> bool:
    """Below the epsilon a batch is empty: binary rounding leaves 1e-14 g behind."""
    return remaining < QUANTITY_EPSILON


def sort_batches(batches: Sequence[BatchView]) -> list[BatchView]:
    """Opened first, then closest expiry, then oldest entry (spec 7.1)."""
    return sorted(
        batches,
        key=lambda b: (
            b.opened_at is None,
            b.best_before is None,
            b.best_before or date.max,
            b.entered_at,
        ),
    )


def allocate(batches: Sequence[BatchView], quantity: float) -> list[Allocation]:
    """Spread a consumption over the batches, in order. Never partial, never negative."""
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")
    available = sum(b.remaining for b in batches)
    if quantity > available + QUANTITY_EPSILON:
        raise InsufficientStock(requested=quantity, available=available)

    allocations: list[Allocation] = []
    left = quantity
    for candidate in sort_batches(batches):
        if is_empty(left):
            break
        taken = min(candidate.remaining, left)
        remaining_after = candidate.remaining - taken
        closes = is_empty(remaining_after)
        allocations.append(
            Allocation(
                batch_id=candidate.id,
                quantity=taken,
                price_per_base_unit=candidate.price_per_base_unit,
                kcal_per_base_unit=candidate.kcal_per_base_unit,
                remaining_after=0.0 if closes else remaining_after,
                closes_batch=closes,
            )
        )
        left -= taken
    return allocations
