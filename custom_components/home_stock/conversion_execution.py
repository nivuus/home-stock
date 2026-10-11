"""Execute a product's move from pieces to grams or millilitres.

`domain.conversion.plan_conversion` computes the plan and writes nothing;
this module carries it out, inside a transaction its caller holds. It is the
body `StockManager.convert_product_unit` used to hold, moved here unchanged so
that two surfaces run the very same writes:

- the panel's websocket command `home_stock/product/convert_unit`, through
  `StockManager.convert_product_unit`, which opens the transaction;
- the `home_stock.update_product` service (`product_correction.py`), which
  opens one transaction for a conversion and a kcal correction together.
  `Database._lock` is not reentrant, so neither surface can call the other's
  transaction from inside its own: both call this module instead.

One addition, which the panel never uses: `kept_batches`, the open batches
whose quantity is already expressed in the new unit — a batch typed in as
"80" (meaning 80 g) under a product counted in pieces. Such a batch keeps its
`remaining`, its `initial` and its `price_per_base_unit`; it still gets its
two conversion movements (out in pieces, in in the new unit, same quantity),
so the journal stays right unit by unit.
"""
from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, replace
from typing import Any

from .const import NUTRITION_COLUMNS, REASON_CONVERSION
from .domain.conversion import BatchConversion, ConversionError, ConversionPlan, plan_conversion
from .storage import repositories as repo


class KeptBatchError(ConversionError):
    """A batch named to be kept as it is is not an open batch of the product."""

    def __init__(self, product_id: int, batch_ids: Collection[int]) -> None:
        self.product_id = product_id
        self.batch_ids = tuple(sorted(batch_ids))
        super().__init__(
            f"batch(es) {list(self.batch_ids)} are not open batches of product {product_id}")


@dataclass(frozen=True)
class PreparedConversion:
    """A planned conversion and the rows it was planned from."""

    product: dict[str, Any]
    articles: tuple[dict[str, Any], ...]
    batches: tuple[dict[str, Any], ...]
    plan: ConversionPlan
    kept_batches: frozenset[int]


def _kept(batch: BatchConversion) -> BatchConversion:
    return replace(batch, new_remaining=batch.old_remaining, new_initial=batch.old_initial)


def prepare_conversion(conn: Any, product: dict[str, Any], *, to_unit: str,
                       reference_quantity: float,
                       kept_batches: Collection[int] = ()) -> PreparedConversion:
    """Plan the conversion of `product`, or raise `ConversionError`. Writes nothing."""
    product_id = product["id"]
    articles = repo.list_articles_for_product(conn, product_id)
    # Closed batches are deliberately left out and stay in their
    # pre-conversion unit: their `remaining`, `initial` AND
    # `price_per_base_unit` all stay expressed in the old unit. Safe
    # only because every read today filters on open batches and none
    # of those three columns is ever read back off a closed batch —
    # this stops being safe the day something does (e.g. a future
    # "how much of each pack did we finish" or "what did this pack
    # cost us" report), which would then silently average pieces
    # with grams, or euros per piece with euros per gram.
    batches = repo.list_open_batches_for_product(conn, product_id)

    plan = plan_conversion(product=product, articles=articles, batches=batches,
                           to_unit=to_unit, reference_quantity=reference_quantity)

    kept = frozenset(kept_batches)
    unknown = kept - {batch["id"] for batch in batches}
    if unknown:
        raise KeptBatchError(product_id, unknown)
    if kept:
        plan = replace(plan, batches=tuple(
            _kept(batch) if batch.batch_id in kept else batch for batch in plan.batches))

    # A pending shopping_line stores its quantity in the product's
    # base unit as a promise, not yet a batch. Converting under it
    # would silently reinterpret that number in the new unit — two
    # queued packets becoming "2 g" instead of 1000 g the moment they
    # are put away — with no trace in the journal. Refuse instead,
    # even for a dry run: a plan that cannot actually be applied is
    # not a plan worth showing.
    pending = repo.count_pending_lines_for_product(conn, product_id)
    if pending:
        raise ConversionError(
            f"{pending} ligne(s) de courses en attente de rangement pour ce "
            "produit : rangez d'abord les courses avant de convertir son unité"
        )
    return PreparedConversion(product=product, articles=tuple(articles),
                              batches=tuple(batches), plan=plan, kept_batches=kept)


def conversion_report(prepared: PreparedConversion) -> dict[str, Any]:
    """What the panel shows before and after a conversion, `applied` still False."""
    plan = prepared.plan
    return {
        "product_id": plan.product_id,
        "product_name": prepared.product["name"],
        "from_unit": plan.from_unit,
        "to_unit": plan.to_unit,
        "reference_quantity": plan.reference_quantity,
        "articles": len(plan.articles),
        "batches": len(plan.batches),
        "movements": plan.movements,
        "articles_using_reference": list(plan.articles_using_reference),
        "applied": False,
    }


def execute_conversion(conn: Any, prepared: PreparedConversion, *, packaging_name: str,
                       occurred_at: str) -> None:
    """Carry the plan out, in the caller's transaction."""
    plan, product = prepared.plan, prepared.product
    product_id, to_unit = plan.product_id, plan.to_unit
    articles_by_id = {a["id"]: a for a in prepared.articles}
    batches_by_id = {b["id"]: b for b in prepared.batches}
    factors = {a.article_id: a.factor for a in plan.articles}

    for article in plan.articles:
        # Nutrition is stored per base unit: per packet becomes per gram.
        # net_quantity is a mass or a volume already, so it does not move.
        current = articles_by_id[article.article_id]
        rescaled = {
            column: current[column] / article.factor
            for column in NUTRITION_COLUMNS
            if current[column] is not None
        }
        repo.update_article_fields(conn, article.article_id, rescaled)
        repo.insert_packaging(conn, scope="article", target_id=article.article_id,
                              name=packaging_name, base_quantity=article.factor,
                              is_purchase_default=True)
        # A price is euros PER unit, so a change of denomination moves
        # it opposite to the quantities: 1.20 €/packet and 0.0024 €/g
        # are the same fact said twice, not history being rewritten.
        repo.rescale_prices_for_article(conn, article.article_id, article.factor)

    for batch in plan.batches:
        # The plan already carries the pre-conversion quantity
        # (batch.old_remaining), so the journal stays correct no
        # matter which of these two writes runs first. Only reading
        # `remaining` back from the batch row instead of from the
        # plan would make this order load-bearing.
        repo.insert_movement(
            conn, occurred_at=occurred_at, product_id=product_id,
            article_id=batch.article_id, batch_id=batch.batch_id,
            quantity=-batch.old_remaining, reason=REASON_CONVERSION,
            base_unit=plan.from_unit, kcal=None, cost=None,
            ref_type=None, ref_id=None,
            idempotency_key=f"conversion:{product_id}:{batch.batch_id}:{to_unit}:out",
        )
        repo.insert_movement(
            conn, occurred_at=occurred_at, product_id=product_id,
            article_id=batch.article_id, batch_id=batch.batch_id,
            quantity=batch.new_remaining, reason=REASON_CONVERSION,
            base_unit=plan.to_unit, kcal=None, cost=None,
            ref_type=None, ref_id=None,
            idempotency_key=f"conversion:{product_id}:{batch.batch_id}:{to_unit}:in",
        )
        # Same denomination change as the article's own price above,
        # applied to the batch's own recorded price — divided by the
        # same factor that multiplies its quantity, so the batch's
        # value in euros (remaining * price_per_base_unit) is
        # unchanged by the conversion. A NULL price stays NULL: there
        # is nothing to convert. A kept batch's quantity does not move,
        # so neither does its price.
        old_price = batches_by_id[batch.batch_id]["price_per_base_unit"]
        divisor = 1.0 if batch.batch_id in prepared.kept_batches else factors[batch.article_id]
        new_price = None if old_price is None else old_price / divisor
        repo.set_batch_remaining(conn, batch.batch_id, batch.new_remaining)
        conn.execute(
            "UPDATE batch SET initial = ?, price_per_base_unit = ? WHERE id = ?",
            (batch.new_initial, new_price, batch.batch_id),
        )

    product_fields: dict[str, Any] = {"base_unit": plan.to_unit}
    if product["min_quantity"] is not None:
        product_fields["min_quantity"] = product["min_quantity"] * plan.reference_quantity
    if product["reference_kcal"] is not None:
        product_fields["reference_kcal"] = product["reference_kcal"] / plan.reference_quantity
    repo.update_product_fields(conn, product_id, product_fields)
