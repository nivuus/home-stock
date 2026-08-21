"""Recipe rules: scaling, resolving a quantity into base units, planning a
decrement, and what one portion is worth.

Pure functions over value objects: no `hass`, no network, no SQLite. Scaling a
recipe and turning "2 tbsp of oil" into "30 ml" are precisely the two
calculations Grocy got wrong, and keeping them here means they can be tested
without starting anything.
"""
from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from ..const import MACRO_COLUMNS
from .stock import Allocation, BatchView, allocate, is_empty
from .units import convertible_amount, format_quantity, to_base_quantity

# What the validation screen may show against a line. Declared here because
# both the websocket payload and the panel branch on it: a status returned but
# not declared would render as an empty cell.
STATUSES: Final = ("ok", "short", "unmatched", "unquantified", "ignored")

# The keys `per_part_values` reports on, in the order the journal uses them.
PER_PART_KEYS: Final = ("kcal", *MACRO_COLUMNS)


@dataclass(frozen=True)
class Measure:
    """A culinary measure ("cuillère à soupe"), normalised once in `m004`."""

    id: int | None
    name: str
    base_unit: str          # 'g' | 'ml' | 'piece'
    base_quantity: float


@dataclass(frozen=True)
class IngredientLine:
    """One recipe line, as the repository hands it over — already joined."""

    id: int
    position: int
    product_id: int | None
    product_base_unit: str | None
    amount: float | None
    packaging_base_quantity: float | None
    packaging_name: str | None
    measure: Measure | None
    raw_text: str
    match_state: str
    optional: bool


@dataclass(frozen=True)
class IngredientNeed:
    """What one line needs, what the stock can give, and how."""

    line: IngredientLine
    status: str                       # one of STATUSES
    needed: float | None              # base units, ALREADY scaled
    available: float
    allocations: tuple[Allocation, ...]


def scale_factor(meal_servings: float, recipe_servings: int) -> float:
    """How much of the recipe to make: the ratio of the two serving counts.

    Both must be positive. A recipe for nobody is a data-entry mistake, and a
    factor of zero would silently plan a meal that consumes nothing — which
    looks, on screen, exactly like a meal with nothing in stock.
    """
    if meal_servings <= 0:
        raise ValueError(
            f"le nombre de parts doit être positif, reçu {meal_servings}")
    if recipe_servings <= 0:
        raise ValueError(
            f"la recette doit être pour au moins une part, reçu {recipe_servings}")
    return float(meal_servings) / float(recipe_servings)


def base_amount(line: IngredientLine, factor: float = 1.0) -> float | None:
    """The line's quantity in the product's base unit, scaled — or None.

    Resolution order (spec §9), and it stops at the first that applies:

    1. `packaging_base_quantity`, the packaging that belongs to THIS product
       ("tranche = 30 g"). It is measured, so it beats everything else.
    2. `measure`, the normalised culinary measure, but only when its dimension
       matches the product's base unit. A spoon of a `piece` product, or a
       volume for a product stocked in grams, resolves to None.
    3. `amount` as written — the number is already in the base unit.

    The factor multiplies the BASE quantity, never `amount`: `1 cs × 1,5` is
    "1,5 cs", which is neither wrong nor useful, whereas `15 ml × 1,5` is
    22,5 ml, which decrements.

    None means "no usable quantity", never an estimate. No divisor is ever
    guessed — an impossible conversion is treated exactly like an absent one.
    """
    if line.amount is None or line.product_base_unit is None:
        return None
    if line.packaging_base_quantity is not None:
        return to_base_quantity(line.amount, line.packaging_base_quantity) * factor
    if line.measure is not None:
        resolved = convertible_amount(
            line.amount * line.measure.base_quantity,
            line.measure.base_unit, line.product_base_unit)
        return None if resolved is None else resolved * factor
    return float(line.amount) * factor


def _pluralise(name: str, quantity: float) -> str:
    """French pluralisation of a measure or packaging name, at two and above.

    The `s` goes on the HEAD noun, not on the end of the phrase: two of them
    are "cuillères à soupe", never "cuillère à soupes". Only the first word is
    touched, which is right for every name m004 seeds and for the packaging
    names the catalogue holds ("tranche", "canette", "sachet").
    """
    if quantity < 2:
        return name
    head, separator, tail = name.partition(" ")
    if not head.endswith("s"):
        head = f"{head}s"
    return head + separator + tail


def _number(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def display_amount(line: IngredientLine) -> str:
    """What the panel shows for this line, in French. Computed, never stored.

    The label follows the single written number (`amount` plus at most one
    measure), so it can never drift from what will actually be decremented.
    `raw_text` is provenance and is used only when there is no number at all:
    showing "2 tbsp" next to a 30 ml decrement is how an import starts lying.
    """
    if line.amount is None:
        return line.raw_text
    if line.packaging_name is not None:
        return f"{_number(line.amount)} {_pluralise(line.packaging_name, line.amount)}"
    if line.measure is not None:
        return f"{_number(line.amount)} {_pluralise(line.measure.name, line.amount)}"
    if line.product_base_unit is None:
        return _number(line.amount)
    return format_quantity(float(line.amount), line.product_base_unit)


def _status_of(line: IngredientLine, needed: float | None,
               skipped: bool) -> str | None:
    """The status a line settles on before any stock is looked at, or None
    when the stock is what decides."""
    if skipped or line.match_state == "ignored":
        return "ignored"
    if line.product_id is None or line.match_state == "unmatched":
        return "unmatched"
    if needed is None or is_empty(needed):
        return "unquantified"
    return None


def plan_decrement(lines: Sequence[IngredientLine],
                   batches_by_product: Mapping[int, Sequence[BatchView]],
                   *, factor: float,
                   skipped_ids: Collection[int] = ()) -> tuple[IngredientNeed, ...]:
    """What validating this meal would take out of the stock, line by line.

    Never raises `InsufficientStock`. It sees it coming: when the need exceeds
    what is there, the line comes back `status="short"` with its allocations
    reduced to what exists, and the caller arbitrates. This is the simulation,
    and a simulation that raises shows nothing.

    Allocation runs in SEQUENCE over a mutable copy of each product's
    remaining quantities, so two onion lines in one recipe cannot each claim
    the same batch in full.
    """
    remaining: dict[int, list[BatchView]] = {
        product_id: [
            BatchView(id=b.id, remaining=b.remaining, best_before=b.best_before,
                      entered_at=b.entered_at, opened_at=b.opened_at,
                      price_per_base_unit=b.price_per_base_unit,
                      kcal_per_base_unit=b.kcal_per_base_unit, macros=b.macros)
            for b in views
        ]
        for product_id, views in batches_by_product.items()
    }
    needs: list[IngredientNeed] = []
    for line in lines:
        needed = base_amount(line, factor)
        settled = _status_of(line, needed, line.id in skipped_ids)
        if settled is not None:
            needs.append(IngredientNeed(line=line, status=settled, needed=needed,
                                        available=0.0, allocations=()))
            continue

        views = remaining.get(line.product_id, [])
        available = sum(view.remaining for view in views)
        taken = min(needed, available)
        allocations: tuple[Allocation, ...] = ()
        if not is_empty(taken):
            allocations = tuple(allocate(views, taken))
            after = {a.batch_id: a.remaining_after for a in allocations}
            remaining[line.product_id] = [
                BatchView(id=v.id, remaining=after.get(v.id, v.remaining),
                          best_before=v.best_before, entered_at=v.entered_at,
                          opened_at=v.opened_at,
                          price_per_base_unit=v.price_per_base_unit,
                          kcal_per_base_unit=v.kcal_per_base_unit, macros=v.macros)
                for v in views
                if not is_empty(after.get(v.id, v.remaining))
            ]
        needs.append(IngredientNeed(
            line=line,
            status="ok" if taken >= needed - 1e-9 else "short",
            needed=needed, available=available, allocations=allocations))
    return tuple(needs)


def per_part_values(frozen: Sequence[Mapping[str, float | None]],
                    parts: float) -> dict[str, float | None]:
    """What one portion of the dish is worth, key by key.

    Each key is treated INDEPENDENTLY: a single ingredient movement carrying
    None on one nutrient makes THAT nutrient None on the dish, and leaves the
    other eight alone. Throwing away eight known values to punish one missing
    one would be worse than useless — it would be wrong.

    No rounding: rounding here would make the dish's total disagree with the
    sum of its portions.
    """
    if parts <= 0:
        raise ValueError(f"le nombre de parts doit être positif, reçu {parts}")
    result: dict[str, float | None] = {}
    for key in PER_PART_KEYS:
        values = [row.get(key) for row in frozen]
        if not values or any(value is None for value in values):
            result[key] = None
        else:
            result[key] = sum(values) / parts
    return result
