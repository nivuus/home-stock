"""Plan a product's move from pieces to grams or millilitres.

Pure: this module computes, it never writes. Task 10 executes the plan inside
one transaction. Separating the two is what lets the panel show an honest
confirmation — how many batches move, and which ones fall back to the
reference weight — before anything is touched.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

MIN_REFERENCE: Final = 0.5
MAX_REFERENCE: Final = 50_000.0
TARGET_UNITS: Final = ("g", "ml")


class ConversionError(ValueError):
    """The conversion cannot be planned, and nothing should be attempted."""


@dataclass(frozen=True)
class ArticleConversion:
    article_id: int
    factor: float
    used_reference: bool


@dataclass(frozen=True)
class BatchConversion:
    batch_id: int
    article_id: int
    old_remaining: float
    new_remaining: float
    old_initial: float
    new_initial: float


@dataclass(frozen=True)
class ConversionPlan:
    product_id: int
    from_unit: str
    to_unit: str
    reference_quantity: float
    articles: tuple[ArticleConversion, ...]
    batches: tuple[BatchConversion, ...]
    movements: int
    articles_using_reference: tuple[int, ...]


def _plausible(quantity: Any) -> bool:
    # bool is an int subclass in Python, so it is excluded explicitly — the
    # same convention off/mapping.py's _number() uses — otherwise True/False
    # would silently pass through the range check as 1.0/0.0.
    return (isinstance(quantity, (int, float)) and not isinstance(quantity, bool)
            and MIN_REFERENCE <= quantity <= MAX_REFERENCE)


def plan_conversion(*, product: dict[str, Any], articles: Sequence[dict[str, Any]],
                    batches: Sequence[dict[str, Any]], to_unit: str,
                    reference_quantity: float) -> ConversionPlan:
    """Work out what converting this product would do. Writes nothing."""
    from_unit = product["base_unit"]
    if from_unit != "piece":
        raise ConversionError(
            f"product {product['id']} is already stocked in {from_unit}"
        )
    if to_unit not in TARGET_UNITS:
        raise ConversionError(f"target unit must be one of {TARGET_UNITS}, got {to_unit!r}")
    if not _plausible(reference_quantity):
        raise ConversionError(
            f"reference weight must be between {MIN_REFERENCE} and {MAX_REFERENCE}, "
            f"got {reference_quantity!r}"
        )

    planned_articles: list[ArticleConversion] = []
    factors: dict[int, float] = {}
    for article in articles:
        net = article.get("net_quantity")
        # An implausible weight is treated exactly like a missing one: the
        # reference the human just confirmed is worth more than an OFF typo.
        uses_reference = not _plausible(net)
        factor = reference_quantity if uses_reference else float(net)
        factors[article["id"]] = factor
        planned_articles.append(ArticleConversion(article["id"], factor, uses_reference))

    planned_batch_list: list[BatchConversion] = []
    for batch in batches:
        article_id = batch["article_id"]
        if article_id not in factors:
            # A plan that cannot be computed must fail through the module's
            # own error type, because the caller catches ConversionError and
            # nothing else — a bare KeyError would escape unhandled and crash
            # instead of showing the confirmation screen an error message.
            raise ConversionError(
                f"batch {batch['id']} refers to article {article_id}, "
                "which is not among this product's articles"
            )
        factor = factors[article_id]
        planned_batch_list.append(
            BatchConversion(
                batch_id=batch["id"],
                article_id=article_id,
                old_remaining=batch["remaining"],
                new_remaining=batch["remaining"] * factor,
                old_initial=batch["initial"],
                new_initial=batch["initial"] * factor,
            )
        )
    planned_batches = tuple(planned_batch_list)

    return ConversionPlan(
        product_id=product["id"],
        from_unit=from_unit,
        to_unit=to_unit,
        reference_quantity=reference_quantity,
        articles=tuple(planned_articles),
        batches=planned_batches,
        # One movement out in the old unit, one in in the new: the journal is
        # append-only, so a conversion is written, never edited.
        movements=2 * len(planned_batches),
        articles_using_reference=tuple(
            a.article_id for a in planned_articles if a.used_reference
        ),
    )
