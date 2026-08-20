"""The application layer: composes the domain rules with the repositories.

Everything here is synchronous. Home Assistant calls it from the executor.
"""
from __future__ import annotations

import unicodedata
from datetime import UTC, date, datetime, timedelta
from typing import Any, Final

from .const import (
    QUANTITY_EPSILON,
    REASON_CONSUMPTION,
    REASON_CONVERSION,
    REASON_INVENTORY,
    REASON_PURCHASE,
    REASON_TRANSFER,
)
from .domain.conversion import ConversionError, plan_conversion
from .domain.nutrition import movement_values
from .domain.stock import BatchView, InsufficientStock, allocate, is_empty
from .domain.units import format_quantity, to_base_quantity
from .storage import repositories as repo
from .storage.database import Database

# Nutrition columns of `article`, all stored per base unit, all rescaled when a
# product changes unit.
NUTRITION_COLUMNS: Final = (
    "kcal_per_base_unit", "proteins", "carbohydrates", "sugars", "added_sugars",
    "fat", "saturated_fat", "fiber", "salt",
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()


def _escape_like(value: str) -> str:
    """Escape SQL LIKE wildcards so a key is matched literally, not as a pattern.

    A HA service call or a voice-generated idempotency key can legally contain
    '%' or '_', both of which are LIKE wildcards. Without escaping, a key like
    "dinner_1" would also match rows keyed "dinnerX1#1" and a replay would
    return movement ids belonging to a different consumption.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# NFD decomposition splits an accented letter into the base letter plus a
# combining mark, but it does NOT split the œ/æ ligatures — those are single
# code points, not a letter plus an accent. Expand them by hand first, or
# "œufs" never matches a product named "Œufs" (services.yaml promises
# case- and accent-insensitive matching for query_stock, the voice path).
_LIGATURES = {"œ": "oe", "æ": "ae", "Œ": "OE", "Æ": "AE"}


def _fold_for_search(text: str) -> str:
    """Case- and accent-insensitive form of `text`, for query_stock matching."""
    for ligature, expanded in _LIGATURES.items():
        text = text.replace(ligature, expanded)
    decomposed = unicodedata.normalize("NFD", text)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_accents.casefold()


def _namespaced_key(operation: str, key: str | None) -> str | None:
    """Prefix a caller-supplied idempotency key with the operation that owns it.

    idempotency_key is a single UNIQUE column shared by every service: without
    a namespace, an add_stock call replaying a key first used by consume()
    would find that unrelated movement and return ITS batch_id instead of
    doing its own work.
    """
    return f"{operation}:{key}" if key else None


def _as_batch_view(row: dict[str, Any]) -> BatchView:
    return BatchView(
        id=row["id"],
        remaining=row["remaining"],
        best_before=date.fromisoformat(row["best_before"]) if row["best_before"] else None,
        entered_at=datetime.fromisoformat(row["entered_at"]),
        opened_at=datetime.fromisoformat(row["opened_at"]) if row["opened_at"] else None,
        price_per_base_unit=row["price_per_base_unit"],
        kcal_per_base_unit=row["kcal_per_base_unit"],
        macros=repo.macro_rates(row),
    )


class StockManager:
    """Every write to the stock goes through here."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # --- writes -------------------------------------------------------------

    def add_stock(self, *, article_id: int, quantity: float, location_id: int,
                  best_before: str | None = None,
                  price_per_base_unit: float | None = None,
                  packaging_base_quantity: float | None = None,
                  occurred_at: str | None = None,
                  idempotency_key: str | None = None,
                  record_price_observation: bool = True) -> int:
        """Create a batch and its purchase movement. Returns the batch id.

        `record_price_observation` defaults to True for every existing
        caller. The one caller that must pass False is the shopping session
        (shopping.store_line): a price observed in the aisle is recorded at
        the moment of the scan, with the shop it was seen in — put-away time
        is not a second observation, so add_stock must not write it again.
        """
        moment = occurred_at or _now()
        amount = to_base_quantity(quantity, packaging_base_quantity)
        stored_key = _namespaced_key("add_stock", idempotency_key)
        with self.db.write() as conn:
            if stored_key and repo.movement_exists(conn, stored_key):
                row = conn.execute(
                    "SELECT batch_id FROM movement WHERE idempotency_key = ?",
                    (stored_key,),
                ).fetchone()
                return int(row["batch_id"])
            article = repo.get_article(conn, article_id)
            if article is None:
                raise ValueError(f"unknown article {article_id}")
            batch_id = repo.insert_batch(
                conn, article_id=article_id, location_id=location_id, quantity=amount,
                entered_at=moment, best_before=best_before,
                price_per_base_unit=price_per_base_unit,
            )
            kcal_rate = repo.resolve_kcal_rate(conn, article)
            values = movement_values(amount, kcal_rate, price_per_base_unit,
                                     macro_rates=repo.macro_rates(article))
            base_unit = repo.product_base_unit(conn, article["product_id"])
            repo.insert_movement(
                conn, occurred_at=moment, product_id=article["product_id"],
                article_id=article_id, batch_id=batch_id, quantity=amount,
                reason=REASON_PURCHASE, base_unit=base_unit,
                kcal=values.kcal, cost=values.cost, macros=values.macros,
                idempotency_key=stored_key,
            )
            if price_per_base_unit is not None and record_price_observation:
                repo.insert_price(
                    conn, article_id=article_id, observed_on=moment[:10],
                    price_per_base_unit=price_per_base_unit, source="manual",
                )
            return batch_id

    def consume(self, *, product_id: int, quantity: float,
                reason: str = REASON_CONSUMPTION, occurred_at: str | None = None,
                idempotency_key: str | None = None) -> list[int]:
        """Take a quantity out of stock, across as many batches as needed."""
        moment = occurred_at or _now()
        stored_key = _namespaced_key("consume", idempotency_key)
        with self.db.write() as conn:
            if stored_key and repo.movement_exists(conn, stored_key):
                # Replayed call: return the movements the first call wrote.
                # The key itself is escaped so '%'/'_' inside it are matched
                # literally; only the trailing '%' we append is a real wildcard.
                rows = conn.execute(
                    "SELECT id FROM movement WHERE idempotency_key = ?"
                    " OR idempotency_key LIKE ? ESCAPE '\\' ORDER BY id",
                    (stored_key, f"{_escape_like(stored_key)}#%"),
                ).fetchall()
                return [int(row["id"]) for row in rows]
            # Every batch of one product necessarily shares that product's unit:
            # read it once here rather than once per batch in the loop below.
            base_unit = repo.product_base_unit(conn, product_id)
            batches = [_as_batch_view(row)
                       for row in repo.list_batches_for_product(conn, product_id)]
            allocations = allocate(batches, quantity)   # raises InsufficientStock
            movement_ids: list[int] = []
            for index, allocation in enumerate(allocations):
                article_row = conn.execute(
                    "SELECT article_id FROM batch WHERE id = ?", (allocation.batch_id,)
                ).fetchone()
                values = movement_values(allocation.quantity,
                                         allocation.kcal_per_base_unit,
                                         allocation.price_per_base_unit,
                                         macro_rates=allocation.macros)
                # One consumption can span several batches, but the key is UNIQUE:
                # the first movement carries it, the next ones carry "key#1", "key#2".
                key = None
                if stored_key:
                    key = stored_key if index == 0 else f"{stored_key}#{index}"
                movement_ids.append(repo.insert_movement(
                    conn, occurred_at=moment, product_id=product_id,
                    article_id=article_row["article_id"], batch_id=allocation.batch_id,
                    quantity=-allocation.quantity, reason=reason, base_unit=base_unit,
                    kcal=values.kcal, cost=values.cost, macros=values.macros,
                    idempotency_key=key,
                ))
                repo.set_batch_remaining(
                    conn, allocation.batch_id, allocation.remaining_after,
                    closed_at=moment if allocation.closes_batch else None,
                )
            return movement_ids

    def consume_batch(self, batch_id: int, *, quantity: float | None = None,
                      reason: str = REASON_CONSUMPTION,
                      occurred_at: str | None = None) -> int:
        """Take from one precise batch. Without a quantity, empties it.

        The expiry list checks off a batch, not a product: FIFO must not apply.
        """
        moment = occurred_at or _now()
        with self.db.write() as conn:
            row = conn.execute(
                # kcal rate: same fallback as add_stock() and consume() (spec 7.4).
                f"SELECT b.*, a.product_id, {repo.KCAL_RATE_SQL} AS kcal_per_base_unit,"
                f" {repo.MACRO_RATE_SQL}"
                " FROM batch b"
                " JOIN article a ON a.id = b.article_id"
                " JOIN product p ON p.id = a.product_id"
                " WHERE b.id = ? AND b.closed_at IS NULL",
                (batch_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown or closed batch {batch_id}")
            taken = row["remaining"] if quantity is None else float(quantity)
            if taken > row["remaining"] + QUANTITY_EPSILON:
                raise InsufficientStock(requested=taken, available=row["remaining"])
            remaining_after = row["remaining"] - taken
            closes = is_empty(remaining_after)
            values = movement_values(taken, row["kcal_per_base_unit"],
                                     row["price_per_base_unit"],
                                     macro_rates=repo.macro_rates(row))
            base_unit = repo.product_base_unit(conn, row["product_id"])
            movement_id = repo.insert_movement(
                conn, occurred_at=moment, product_id=row["product_id"],
                article_id=row["article_id"], batch_id=batch_id, quantity=-taken,
                reason=reason, base_unit=base_unit, kcal=values.kcal, cost=values.cost,
                macros=values.macros,
            )
            repo.set_batch_remaining(conn, batch_id, 0.0 if closes else remaining_after,
                                     closed_at=moment if closes else None)
            return movement_id

    def open_batch(self, batch_id: int, *, occurred_at: str | None = None) -> None:
        """Mark a batch open and, if the product says so, bring its date closer."""
        moment = occurred_at or _now()
        with self.db.write() as conn:
            row = conn.execute(
                "SELECT b.best_before, p.days_after_opening FROM batch b"
                " JOIN article a ON a.id = b.article_id"
                " JOIN product p ON p.id = a.product_id WHERE b.id = ?",
                (batch_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown batch {batch_id}")
            best_before = row["best_before"]
            if row["days_after_opening"]:
                shortened = (
                    datetime.fromisoformat(moment).date()
                    + timedelta(days=int(row["days_after_opening"]))
                ).isoformat()
                if best_before is None or shortened < best_before:
                    best_before = shortened
            repo.set_batch_opened(conn, batch_id, moment, best_before)

    def transfer_batch(self, batch_id: int, location_id: int, *,
                       occurred_at: str | None = None) -> int:
        """Move a batch to another location. Nothing is consumed."""
        moment = occurred_at or _now()
        with self.db.write() as conn:
            row = conn.execute(
                "SELECT b.article_id, a.product_id FROM batch b"
                " JOIN article a ON a.id = b.article_id WHERE b.id = ?",
                (batch_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown batch {batch_id}")
            repo.set_batch_location(conn, batch_id, location_id)
            base_unit = repo.product_base_unit(conn, row["product_id"])
            return repo.insert_movement(
                conn, occurred_at=moment, product_id=row["product_id"],
                article_id=row["article_id"], batch_id=batch_id, quantity=0,
                reason=REASON_TRANSFER, base_unit=base_unit,
                ref_type="location", ref_id=location_id,
            )

    def adjust_inventory(self, *, article_id: int, location_id: int,
                         counted_quantity: float,
                         occurred_at: str | None = None) -> int | None:
        """Record what was actually counted. Returns the movement id, or None."""
        moment = occurred_at or _now()
        with self.db.write() as conn:
            article = repo.get_article(conn, article_id)
            if article is None:
                raise ValueError(f"unknown article {article_id}")
            rows = conn.execute(
                "SELECT * FROM batch WHERE article_id = ? AND location_id = ?"
                " AND closed_at IS NULL", (article_id, location_id),
            ).fetchall()
            current = sum(row["remaining"] for row in rows)
            delta = counted_quantity - current
            if abs(delta) < QUANTITY_EPSILON:
                return None
            if delta < 0:
                # Reuse the same BatchView construction as consume(): the rows
                # from `SELECT * FROM batch` do not carry kcal_per_base_unit or
                # the eight macro columns (those live on `article`, not
                # `batch`), so inject the article's own values before handing
                # them to the helper. Unused here in practice — the movement
                # below is written with kcal and cost pinned to None because a
                # correction is not a consumption (spec 7.5) — but _as_batch_view
                # now always reads all eight macro columns off its row, so they
                # must be present to avoid a KeyError.
                views = [
                    _as_batch_view({
                        **dict(row),
                        "kcal_per_base_unit": article["kcal_per_base_unit"],
                        **repo.macro_rates(article),
                    })
                    for row in rows
                ]
                for allocation in allocate(views, -delta):
                    repo.set_batch_remaining(
                        conn, allocation.batch_id, allocation.remaining_after,
                        closed_at=moment if allocation.closes_batch else None,
                    )
                batch_id = None
            else:
                batch_id = repo.insert_batch(
                    conn, article_id=article_id, location_id=location_id,
                    quantity=delta, entered_at=moment,
                )
            # kcal and cost stay NULL: a correction is not a consumption (spec 7.5).
            base_unit = repo.product_base_unit(conn, article["product_id"])
            return repo.insert_movement(
                conn, occurred_at=moment, product_id=article["product_id"],
                article_id=article_id, batch_id=batch_id, quantity=delta,
                reason=REASON_INVENTORY, base_unit=base_unit,
            )

    def convert_product_unit(self, *, product_id: int, to_unit: str,
                             reference_quantity: float, packaging_name: str = "unité",
                             dry_run: bool = False) -> dict[str, Any]:
        """Move a product from pieces to grams or millilitres.

        Everything happens in one transaction: a product half-converted would
        report a stock that is partly packets and partly grams, and no reading
        of the journal could tell them apart afterwards.
        """
        with self.db.write() as conn:
            product = repo.get_product(conn, product_id)
            if product is None:
                raise LookupError(f"no product {product_id}")
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

            report = {
                "product_id": plan.product_id,
                "product_name": product["name"],
                "from_unit": plan.from_unit,
                "to_unit": plan.to_unit,
                "reference_quantity": plan.reference_quantity,
                "articles": len(plan.articles),
                "batches": len(plan.batches),
                "movements": plan.movements,
                "articles_using_reference": list(plan.articles_using_reference),
                "applied": False,
            }
            if dry_run:
                return report

            occurred_at = _now()
            articles_by_id = {a["id"]: a for a in articles}
            batches_by_id = {b["id"]: b for b in batches}
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
                # is nothing to convert.
                old_price = batches_by_id[batch.batch_id]["price_per_base_unit"]
                new_price = (None if old_price is None
                            else old_price / factors[batch.article_id])
                repo.set_batch_remaining(conn, batch.batch_id, batch.new_remaining)
                conn.execute(
                    "UPDATE batch SET initial = ?, price_per_base_unit = ? WHERE id = ?",
                    (batch.new_initial, new_price, batch.batch_id),
                )

            product_fields: dict[str, Any] = {"base_unit": plan.to_unit}
            if product["min_quantity"] is not None:
                product_fields["min_quantity"] = (
                    product["min_quantity"] * plan.reference_quantity
                )
            if product["reference_kcal"] is not None:
                product_fields["reference_kcal"] = (
                    product["reference_kcal"] / plan.reference_quantity
                )
            repo.update_product_fields(conn, product_id, product_fields)

            report["applied"] = True
            return report

    # --- reads --------------------------------------------------------------

    def query_stock(self, *, name: str | None = None) -> list[dict[str, Any]]:
        """What is in stock, aggregated per product. Feeds the voice answer."""
        rows = repo.stock_rows(self.db.read())
        grouped: dict[int, dict[str, Any]] = {}
        for row in rows:
            entry = grouped.setdefault(row["product_id"], {
                "product_id": row["product_id"], "product_name": row["product_name"],
                "base_unit": row["base_unit"], "quantity": 0.0, "batches": 0,
            })
            entry["quantity"] += row["remaining"]
            entry["batches"] += 1
        result = list(grouped.values())
        if name:
            needle = _fold_for_search(name)
            result = [e for e in result if needle in _fold_for_search(e["product_name"])]
        for entry in result:
            entry["display"] = format_quantity(entry["quantity"], entry["base_unit"])
        return sorted(result, key=lambda e: e["product_name"])

    def summary(self, *, expiration_alert_days: int,
                today: str | None = None) -> dict[str, Any]:
        """The numbers the entities publish."""
        reference = date.fromisoformat(today) if today else datetime.now(UTC).date()
        limit = reference + timedelta(days=expiration_alert_days)
        conn = self.db.read()
        rows = repo.stock_rows(conn)

        value = 0.0
        value_by_location: dict[str, float] = {}
        unpriced = 0
        expiring: list[dict[str, Any]] = []
        for row in rows:
            if row["price_per_base_unit"] is None:
                unpriced += 1
            else:
                line_value = row["remaining"] * row["price_per_base_unit"]
                value += line_value
                value_by_location[row["location_name"]] = (
                    value_by_location.get(row["location_name"], 0.0) + line_value
                )
            if row["best_before"] and date.fromisoformat(row["best_before"]) <= limit:
                expiring.append({
                    "batch_id": row["id"], "product_name": row["product_name"],
                    "best_before": row["best_before"],
                    "display": format_quantity(row["remaining"], row["base_unit"]),
                })

        # Shortages come from the product table, not from stock_rows: a product
        # whose stock reached zero has no open batch left, hence no row in
        # stock_rows, and must still be reported as a shortage (spec: "at
        # least one product under its threshold").
        shortages = [
            {"product_name": row["product_name"],
             "display": format_quantity(row["quantity"], row["base_unit"])}
            for row in repo.shortage_rows(conn)
        ]
        totals = repo.counted_totals(conn)

        # The cart: read on this same connection, like the rest of the
        # summary — a second, separate read here could race a concurrent
        # write and show a session that no longer matches its own totals.
        session = repo.current_session(conn)
        cart_totals = repo.session_totals(conn, session["id"]) if session else None
        # "Awaiting put-away" only starts once the trolley has left the
        # shop: a line scanned in the aisle is not yet "to store" just
        # because it has no batch, or sensor.home_stock_to_store would read
        # 1 while the shopper is still walking the aisles, which is not
        # what that name promises.
        awaiting_storage = (
            cart_totals["pending"] if session and session["state"] != "shopping" else 0
        )

        return {
            "stock_value": round(value, 2),
            "stock_value_by_location": {
                location: round(amount, 2) for location, amount in value_by_location.items()
            },
            "unpriced_batches": unpriced,
            "batch_count": len(rows),
            "open_batch_count": sum(1 for row in rows if row["opened_at"]),
            "expiring": sorted(expiring, key=lambda e: e["best_before"]),
            "shortages": shortages,
            "kcal_total": round(totals["kcal"], 1),
            "cost_total": round(totals["cost"], 2),
            # Rounded to 2 decimals like every other euro sensor
            # (stock_value, cost_total): session_totals() itself keeps 4,
            # for the websocket API's own precision needs.
            "cart_total": round(cart_totals["total"], 2) if cart_totals else 0.0,
            "cart_lines": cart_totals["lines"] if cart_totals else 0,
            "cart_pending": cart_totals["pending"] if cart_totals else 0,
            "cart_store": session["store"] if session else None,
            "cart_to_store": awaiting_storage,
        }

    def export_journal(self) -> list[dict[str, Any]]:
        """The whole append-only journal. It is enough to rebuild everything."""
        return repo.list_movements(self.db.read())
