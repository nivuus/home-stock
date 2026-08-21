"""The application layer: composes the domain rules with the repositories.

Everything here is synchronous. Home Assistant calls it from the executor.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections.abc import Collection, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4
from typing import Any, Final

import voluptuous as vol
from zoneinfo import ZoneInfo

from .const import (
    BATTERY_EVENT_KINDS,
    BATTERY_KINDS,
    CONSUMABLE_ROLES,
    CONSUMABLE_UNITS,
    DEFAULT_KEEP_PERCENT,
    DEFAULT_LOW_PERCENT,
    MACRO_COLUMNS,
    LEFTOVER_CATEGORY_NAME,
    LEFTOVER_NAME_PREFIX,
    LEFTOVER_SHELF_LIFE_DAYS,
    MATCH_STATES,
    MEAL_HORIZON_DAYS,
    MEAL_SLOT_KEYS,
    MAX_PARTS,
    MAX_RECIPE_INGREDIENTS,
    MAX_RECIPE_STEPS,
    NUTRITION_COLUMNS,
    QUANTITY_EPSILON,
    REASON_CONSUMPTION,
    REASON_CONVERSION,
    REASON_COOKED,
    REASON_INVENTORY,
    REASON_PURCHASE,
    REASON_TRANSFER,
    REASONS,
    RECIPE_SOURCES,
)
from .domain.conversion import ConversionError, plan_conversion
from .domain.correction import (
    CorrectionError,
    check_correctable,
    correction_key,
    reprice,
    reversal,
)
from .domain.matching import Candidate, candidates, normalise, preselect
from .domain.recipes import (
    IngredientLine,
    IngredientNeed,
    Measure,
    display_amount,
    per_part_values,
    plan_decrement,
    scale_factor,
)
from .domain.foodday import bounds_of_food_day, bucket_bounds, food_day_bounds, food_day_of
from .domain.maintenance import battery_plan, merge_plan
from .domain.nutrition import movement_values
from .domain.stock import BatchView, InsufficientStock, allocate, is_empty
from .domain.units import convertible_amount, format_quantity, to_base_quantity
from .recipes.adapt import AdaptedRecipe
from .recipes.mapping import SourceIngredient, SourceRecipe
from .storage import repositories as repo
from .storage.database import Database
from .messages import french_message
from .validators import (
    check_battery_event,
    check_battery_fields,
    finite_float,
    iso_date,
    media_path,
)


# The keys a bucket and a day both carry. One definition, so a series and a
# day can never disagree about what "kcal" means.
_TOTAL_KEYS: Final = ("kcal", *MACRO_COLUMNS, "cost", "waste_cost", "unvalued")

# The two stages of an expiry announcement, in the only order they may occur.
EXPIRY_STAGES: Final = ("approaching", "expired")


_LOGGER = logging.getLogger(__name__)


def _empty_totals() -> dict[str, float]:
    return {key: 0.0 for key in _TOTAL_KEYS}


def _accumulate(totals: dict[str, float], row: dict[str, Any]) -> None:
    """Add one movement to a bucket, splitting it the way repo.totals_between's
    SQL does: personal share on the nutrients, never on the money.

    This function does not itself filter by reason — every row that is not a
    consumption is booked as waste, whatever its reason. It relies on its only
    caller, repo.counted_movements, to have already excluded purchase,
    inventory, transfer and conversion rows; fed anything else, it would
    mislabel it as waste.
    """
    reason = row["reason"]
    if reason == REASON_CONSUMPTION:
        share = ((row["parts_mine"] if row["parts_mine"] is not None else 1)
                 / (row["parts_total"] if row["parts_total"] is not None else 1))
        for key in ("kcal", *MACRO_COLUMNS):
            value = row[key]
            if value is not None:
                totals[key] += value * share
        if row["kcal"] is None:
            totals["unvalued"] += 1
        if row["cost"] is not None:
            totals["cost"] += row["cost"]
    elif row["cost"] is not None:
        totals["waste_cost"] += row["cost"]


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


class PartsError(ValueError):
    """Parts that cannot be true, or parts on a movement that cannot have any."""


def _checked_parts(reason: str, parts_total: int | None,
                   parts_mine: int | None) -> tuple[int | None, int | None]:
    """Validate the pair, or refuse the whole call.

    Both or neither: given one alone, the caller believes it recorded a share
    it did not, and the movement would read as 1/1 forever after.
    """
    if parts_total is None and parts_mine is None:
        return None, None
    if parts_total is None or parts_mine is None:
        raise PartsError("parts_total and parts_mine go together")
    if reason != REASON_CONSUMPTION:
        raise PartsError(f"a {reason} movement cannot be shared")
    if not 1 <= parts_total <= MAX_PARTS:
        raise PartsError(f"parts_total must be between 1 and {MAX_PARTS}")
    if not 0 <= parts_mine <= parts_total:
        raise PartsError("parts_mine must be between 0 and parts_total")
    return parts_total, parts_mine


def as_batch_view(row: dict[str, Any]) -> BatchView:
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
                  record_price_observation: bool = True,
                  reason: str = REASON_PURCHASE,
                  nutrition: Mapping[str, float | None] | None = None) -> int:
        """Create a batch and its entry movement. Returns the batch id.

        `record_price_observation` defaults to True for every existing
        caller. The one caller that must pass False is the shopping session
        (shopping.store_line): a price observed in the aisle is recorded at
        the moment of the scan, with the shop it was seen in — put-away time
        is not a second observation, so add_stock must not write it again.

        `reason` and `nutrition` are lot 3 (amendment A3), and both default to
        exactly what every existing caller already did. A cooked dish enters
        the stock through THIS method, with `reason="cooked"` and the
        nutrition computed from the ingredients it consumed — rather than
        through a second entry path. `add_stock` is the only way into the
        stock, and opening a second one would mean maintaining two entry
        behaviours forever: the same debt lot 0 refused on the way out.

        `nutrition` freezes on the batch. It is a per-column freeze, not a
        per-row one: what the dish knows about itself wins, and what it does
        not know still falls through to the article (see the cascade in
        `repositories`). A dish that knows its calories but not its fibre
        must not lose the article's fibre.
        """
        if reason not in REASONS:
            raise ValueError(f"unknown reason {reason!r}; expected one of {REASONS}")
        moment = occurred_at or _now()
        amount = to_base_quantity(quantity, packaging_base_quantity)
        stored_key = _namespaced_key("add_stock", idempotency_key)
        # A full nine-column row, not the caller's partial dict: the two
        # cascade helpers below index every column rather than probing for it,
        # so an absent key must arrive as an explicit None. Filtering on
        # NUTRITION_COLUMNS also stops an invented key from reaching the
        # INSERT — `nutrition` is computed from a recipe, not typed in a form,
        # but a stray "remaining" would overwrite the quantity.
        frozen = None if nutrition is None else {
            column: nutrition.get(column) for column in NUTRITION_COLUMNS
        }
        with self.db.write() as conn:
            if stored_key and repo.movement_exists(conn, stored_key):
                row = conn.execute(
                    "SELECT batch_id FROM movement WHERE idempotency_key = ?",
                    (stored_key,),
                ).fetchone()
                return int(row["batch_id"])
            return self._add_stock_within(
                conn, article_id=article_id, quantity=amount,
                location_id=location_id, moment=moment, best_before=best_before,
                price_per_base_unit=price_per_base_unit, reason=reason,
                nutrition=frozen, key=stored_key,
                record_price_observation=record_price_observation)

    def _add_stock_within(self, conn, *, article_id: int, quantity: float,
                          location_id: int, moment: str,
                          best_before: str | None = None,
                          price_per_base_unit: float | None = None,
                          reason: str = REASON_PURCHASE,
                          nutrition: Mapping[str, float | None] | None = None,
                          ref_type: str | None = None, ref_id: int | None = None,
                          key: str | None = None,
                          record_price_observation: bool = True) -> int:
        """`add_stock`'s body, on a connection the caller already owns.

        Extracted so `validate_meal` can write the cooked dish INSIDE its own
        transaction. `Database._lock` is a plain `threading.Lock`, not a
        reentrant one: calling `add_stock` from inside another `db.write()`
        blocks the process forever, with no exception and no traceback.

        `quantity` is already in base units here — the public wrapper does the
        packaging conversion, the idempotency check and the validation before
        it ever takes the lock, and none of that may quietly move in here.
        """
        article = repo.get_article(conn, article_id)
        if article is None:
            raise ValueError(f"unknown article {article_id}")
        batch_id = repo.insert_batch(
            conn, article_id=article_id, location_id=location_id, quantity=quantity,
            entered_at=moment, best_before=best_before,
            price_per_base_unit=price_per_base_unit, nutrition=nutrition,
        )
        # The entry movement is valued with the SAME cascade a later
        # consumption will read off this batch, so entering a dish and
        # eating it cannot disagree about what it was worth.
        kcal_rate = repo.resolve_kcal_rate(conn, article, batch=nutrition)
        values = movement_values(quantity, kcal_rate, price_per_base_unit,
                                 macro_rates=repo.batch_macro_rates(nutrition, article))
        base_unit = repo.product_base_unit(conn, article["product_id"])
        repo.insert_movement(
            conn, occurred_at=moment, product_id=article["product_id"],
            article_id=article_id, batch_id=batch_id, quantity=quantity,
            reason=reason, base_unit=base_unit,
            kcal=values.kcal, cost=values.cost, macros=values.macros,
            ref_type=ref_type, ref_id=ref_id, idempotency_key=key,
        )
        if price_per_base_unit is not None and record_price_observation:
            repo.insert_price(
                conn, article_id=article_id, observed_on=moment[:10],
                price_per_base_unit=price_per_base_unit, source="manual",
            )
        return batch_id

    def consume(self, *, product_id: int, quantity: float,
                reason: str = REASON_CONSUMPTION, occurred_at: str | None = None,
                idempotency_key: str | None = None,
                parts_total: int | None = None, parts_mine: int | None = None) -> list[int]:
        """Take a quantity out of stock, across as many batches as needed."""
        moment = occurred_at or _now()
        stored_key = _namespaced_key("consume", idempotency_key)
        # Validated before the write transaction opens: an inconsistent
        # entry must not take the write lock just to be refused inside it.
        parts_total, parts_mine = _checked_parts(reason, parts_total, parts_mine)
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
            return self._consume_within(
                conn, product_id=product_id, quantity=quantity, reason=reason,
                moment=moment, parts_total=parts_total, parts_mine=parts_mine,
                key=stored_key)

    def _consume_within(self, conn, *, product_id: int, quantity: float,
                        reason: str, moment: str, base_unit: str | None = None,
                        parts_total: int | None = None,
                        parts_mine: int | None = None,
                        ref_type: str | None = None, ref_id: int | None = None,
                        key: str | None = None) -> list[int]:
        """`consume`'s body, on a connection the caller already owns.

        Extracted for `validate_meal`, which takes every ingredient out inside
        ONE transaction: `Database._lock` is not reentrant, and calling the
        public `consume` from within another `db.write()` hangs the process
        silently.

        `parts_total`/`parts_mine` arrive ALREADY validated. The public method
        checks them before taking the lock — an inconsistent entry must not
        take the write lock just to be refused inside it — and that check must
        not quietly migrate in here.
        """
        # Every batch of one product necessarily shares that product's unit:
        # read it once here rather than once per batch in the loop below.
        if base_unit is None:
            base_unit = repo.product_base_unit(conn, product_id)
        batches = [as_batch_view(row)
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
            movement_key = None
            if key:
                movement_key = key if index == 0 else f"{key}#{index}"
            movement_ids.append(repo.insert_movement(
                conn, occurred_at=moment, product_id=product_id,
                article_id=article_row["article_id"], batch_id=allocation.batch_id,
                quantity=-allocation.quantity, reason=reason, base_unit=base_unit,
                kcal=values.kcal, cost=values.cost, macros=values.macros,
                parts_total=parts_total, parts_mine=parts_mine,
                ref_type=ref_type, ref_id=ref_id, idempotency_key=movement_key,
            ))
            repo.set_batch_remaining(
                conn, allocation.batch_id, allocation.remaining_after,
                closed_at=moment if allocation.closes_batch else None,
            )
        return movement_ids

    def consume_batch(self, batch_id: int, *, product_id: int | None = None,
                      quantity: float | None = None,
                      reason: str = REASON_CONSUMPTION,
                      occurred_at: str | None = None,
                      idempotency_key: str | None = None,
                      parts_total: int | None = None, parts_mine: int | None = None) -> int:
        """Take from one precise batch. Without a quantity, empties it.

        The expiry list checks off a batch, not a product: FIFO must not apply.

        `product_id`, when given, is checked against the batch's own article:
        the panel's "manger" screen always sends both, and the pair is
        checked rather than one of the two being trusted — a batch of the
        wrong product must be refused, not silently consumed.
        """
        moment = occurred_at or _now()
        stored_key = _namespaced_key("consume_batch", idempotency_key)
        # Validated before the write transaction opens: an inconsistent
        # entry must not take the write lock just to be refused inside it.
        parts_total, parts_mine = _checked_parts(reason, parts_total, parts_mine)
        with self.db.write() as conn:
            if stored_key and repo.movement_exists(conn, stored_key):
                row = conn.execute(
                    "SELECT id FROM movement WHERE idempotency_key = ?",
                    (stored_key,),
                ).fetchone()
                return int(row["id"])
            return self._consume_batch_within(
                conn, batch_id, quantity=quantity, reason=reason, moment=moment,
                product_id=product_id, parts_total=parts_total,
                parts_mine=parts_mine, key=stored_key)

    def _consume_batch_within(self, conn, batch_id: int, *,
                              quantity: float | None = None, reason: str,
                              moment: str, product_id: int | None = None,
                              parts_total: int | None = None,
                              parts_mine: int | None = None,
                              ref_type: str | None = None,
                              ref_id: int | None = None,
                              key: str | None = None) -> int:
        """`consume_batch`'s body, on a connection the caller already owns.

        Extracted for `validate_meal`, which eats its portion out of the very
        batch it created moments earlier, in the SAME transaction — something
        the public method cannot do, `Database._lock` being non-reentrant.
        """
        row = conn.execute(
            # kcal and macro rates: the same cascade as add_stock() and
            # consume() — the batch's own values first (lot 3, amendment
            # A2), then the article's, then the product's reference_kcal
            # (spec 7.4). Eating a portion of last night's lasagne must
            # count the lasagne's calories, not the flour's.
            #
            # `b.*` is deliberately not used: batch and article now share
            # those nine column names, and sqlite3.Row keeps the FIRST
            # match — the raw batch column would shadow the cascade and
            # every value would read NULL in silence. See
            # repo.BATCH_COLUMNS_SQL.
            f"SELECT {repo.BATCH_COLUMNS_SQL}, a.product_id,"
            f" {repo.KCAL_RATE_SQL} AS kcal_per_base_unit,"
            f" {repo.MACRO_RATE_SQL}"
            " FROM batch b"
            " JOIN article a ON a.id = b.article_id"
            " JOIN product p ON p.id = a.product_id"
            " WHERE b.id = ? AND b.closed_at IS NULL",
            (batch_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown or closed batch {batch_id}")
        if product_id is not None and row["product_id"] != product_id:
            raise ValueError(
                f"batch {batch_id} does not belong to product {product_id}")
        taken = row["remaining"] if quantity is None else float(quantity)
        if taken <= 0:
            raise ValueError(f"quantity must be positive, got {taken}")
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
            macros=values.macros, parts_total=parts_total, parts_mine=parts_mine,
            ref_type=ref_type, ref_id=ref_id, idempotency_key=key,
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
                # correction is not a consumption (spec 7.5) — but as_batch_view
                # now always reads all eight macro columns off its row, so they
                # must be present to avoid a KeyError.
                views = [
                    as_batch_view({
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

    def summary(self, *, expiration_alert_days: int, tz: ZoneInfo,
                now: datetime | None = None, today: str | None = None) -> dict[str, Any]:
        """The numbers the entities publish.

        `today` and `now` serve two different clocks: `today` is a civil date
        and only bounds the expiration window, while `now` is an instant and
        only bounds the food day. Neither substitutes for the other.
        """
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
        cumulative = repo.totals_between(conn)
        day_start, day_end = food_day_bounds(now or datetime.now(UTC), tz)
        today_totals = repo.totals_between(conn, day_start, day_end)

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
            # Lot 2, amendment A2: these two counters now total consumption
            # only. Waste has its own, cost_waste_total, so that
            # cost_total + cost_waste_total gives back the former total.
            "kcal_total": round(cumulative["kcal"], 1),
            "cost_total": round(cumulative["cost"], 2),
            "cost_waste_total": round(cumulative["waste_cost"], 2),
            "today": {
                "food_day": food_day_of(now or datetime.now(UTC), tz).isoformat(),
                # Naive UTC ISO, exactly like every other bound this module
                # returns (see domain/foodday.py). Sensors turn it into an
                # aware UTC datetime for `last_reset`; they never resolve a
                # time zone themselves (spec 9, amendment).
                "start": day_start,
                "kcal": round(today_totals["kcal"], 1),
                **{column: round(today_totals[column], 3) for column in MACRO_COLUMNS},
                "cost": round(today_totals["cost"], 2),
                "waste_cost": round(today_totals["waste_cost"], 2),
                "unvalued": int(today_totals["unvalued"]),
            },
            # Rounded to 2 decimals like every other euro sensor
            # (stock_value, cost_total): session_totals() itself keeps 4,
            # for the websocket API's own precision needs.
            "cart_total": round(cart_totals["total"], 2) if cart_totals else 0.0,
            "cart_lines": cart_totals["lines"] if cart_totals else 0,
            "cart_pending": cart_totals["pending"] if cart_totals else 0,
            "cart_store": session["store"] if session else None,
            "cart_to_store": awaiting_storage,
        }

    def claim_expiry_announcements(
        self, *, expiration_alert_days: int, today: str | None = None,
    ) -> list[tuple[str, list[dict[str, Any]]]]:
        """What has just crossed a threshold, marked as announced on the way out.

        Claiming and marking happen in ONE write transaction: an announcement
        read but not marked would be repeated at the next refresh, which is
        the exact failure this method exists to prevent.

        A stage never goes backwards. A batch already announced as `expired`
        stays there even if the clock moves back — a corrected timezone or a
        restored backup must not re-announce the whole fridge.
        """
        reference = date.fromisoformat(today) if today else datetime.now(UTC).date()
        limit = (reference + timedelta(days=expiration_alert_days)).isoformat()
        claimed: dict[str, list[dict[str, Any]]] = {stage: [] for stage in EXPIRY_STAGES}
        with self.db.write() as conn:
            for row in repo.expiry_candidates(conn, limit):
                stage = ("expired" if date.fromisoformat(row["best_before"]) < reference
                         else "approaching")
                already = row["expiry_announced_stage"]
                if already is not None and (
                        already == stage
                        or EXPIRY_STAGES.index(already) > EXPIRY_STAGES.index(stage)):
                    continue
                repo.mark_expiry_announced(conn, row["id"], stage)
                claimed[stage].append({
                    "batch_id": row["id"],
                    "product_name": row["product_name"],
                    "best_before": row["best_before"],
                    "display": format_quantity(row["remaining"], row["base_unit"]),
                })
        return [(stage, batches) for stage, batches in claimed.items() if batches]

    def journal_day(self, day: date | None, *, tz: ZoneInfo,
                    now: datetime | None = None) -> dict[str, Any]:
        """One food day: its bounds, its entries, its totals."""
        reference = day or food_day_of(now or datetime.now(UTC), tz)
        start, end = bounds_of_food_day(reference, tz)
        conn = self.db.read()
        return {
            "food_day": reference.isoformat(),
            "start": start,
            "end": end,
            "entries": repo.journal_entries(conn, start, end),
            "totals": repo.totals_between(conn, start, end),
        }

    def journal_series(self, granularity: str, count: int, *, tz: ZoneInfo,
                       now: datetime | None = None) -> dict[str, Any]:
        """The last `count` buckets, oldest first. Raises ValueError on a
        granularity or a count the domain refuses."""
        buckets = bucket_bounds(granularity, count, now or datetime.now(UTC), tz)
        rows = repo.counted_movements(self.db.read(), buckets[0].start)
        filled = []
        for bucket in buckets:
            totals = _empty_totals()
            for row in rows:
                if bucket.start <= row["occurred_at"] < bucket.end:
                    _accumulate(totals, row)
            filled.append({"label": bucket.label, **totals})
        return {"granularity": granularity, "buckets": filled}

    def export_journal(self) -> list[dict[str, Any]]:
        """The whole append-only journal. It is enough to rebuild everything."""
        return repo.list_movements(self.db.read())

    # --- lot 3 -------------------------------------------------------------

    def match_ingredient(self, ingredient_id: int, *, product_id: int | None,
                         state: str, create_alias: bool = False) -> dict[str, Any]:
        """Record which product a recipe line means. Returns the updated line.

        `state` is checked against MATCH_STATES, and a state other than
        `unmatched` is refused without a product BEFORE the transaction opens.
        The schema's CHECK would refuse it too, but as an IntegrityError with
        no context — this says which line and why, in French, and it does not
        take the write lock just to give up inside it.
        """
        if state not in MATCH_STATES:
            raise ValueError(
                f"unknown match state {state!r}; "
                f"expected one of {', '.join(MATCH_STATES)}")
        if state in ("auto", "confirmed") and product_id is None:
            raise ValueError(
                f"a {state!r} match needs a product; "
                "only 'unmatched' and 'ignored' may have none")
        moment = _now()
        with self.db.write() as conn:
            return _match_ingredient_within(
                conn, ingredient_id, product_id=product_id, state=state,
                create_alias=create_alias, moment=moment)

    def create_recipe(self, *, name: str, servings: int = 1,
                      source: str = "manual", steps: Sequence[Mapping[str, Any]] = (),
                      ingredients: Sequence[Mapping[str, Any]] = (),
                      **fields: Any) -> int:
        """Write one recipe, its pages and its lines, in ONE transaction.

        Everything is validated before the transaction opens, and everything
        is written inside it: there is never half a recipe. A recipe whose
        eighth ingredient is refused must leave no trace at all, or the next
        import would find a shell it cannot tell from a real one.
        """
        if len(steps) > MAX_RECIPE_STEPS:
            raise ValueError(
                f"a recipe cannot have more than {MAX_RECIPE_STEPS} steps, "
                f"got {len(steps)}")
        if len(ingredients) > MAX_RECIPE_INGREDIENTS:
            raise ValueError(
                f"a recipe cannot have more than {MAX_RECIPE_INGREDIENTS} "
                f"ingredients, got {len(ingredients)}")
        if source not in RECIPE_SOURCES:
            raise ValueError(
                f"unknown recipe source {source!r}; "
                f"expected one of {', '.join(RECIPE_SOURCES)}")
        if servings < 1:
            raise ValueError(
                f"a recipe serves at least one, got {servings}")

        moment = _now()
        with self.db.write() as conn:
            recipe_id = repo.insert_recipe(
                conn, name=name, source=source, created_at=moment,
                servings=servings, **fields)
            _write_steps_within(conn, recipe_id, steps)
            for position, line in enumerate(ingredients, start=1):
                payload = dict(line)
                repo.insert_ingredient(
                    conn, recipe_id=recipe_id,
                    position=payload.pop("position", position),
                    raw_text=payload.pop("raw_text", ""), **payload)
            return recipe_id

    def list_recipes(self, *, search: str | None = None,
                     only_reviewable: bool = False) -> list[dict[str, Any]]:
        return repo.list_recipes(self.db.read(), search=search,
                                 only_reviewable=only_reviewable)

    def get_recipe_view(self, recipe_id: int) -> dict[str, Any]:
        """The recipe, its pages, its lines resolved, and the candidates.

        Read-only, on a read connection: the matching screen needs the five
        candidates for every unmatched line, and computing them here means the
        panel never has to re-derive a score the backend already knows.
        """
        conn = self.db.read()
        recipe = repo.get_recipe(conn, recipe_id)
        if recipe is None:
            raise ValueError(f"unknown recipe {recipe_id}")
        products = repo.list_products(conn)
        lines = []
        for row in repo.list_ingredients(conn, recipe_id):
            line = dict(row)
            line["display_amount"] = display_amount(_ingredient_line(row))
            if row["match_state"] == "unmatched":
                _, _, _, found = resolve_ingredient_match(
                    conn, raw_text=row["raw_text"], ingredient_name=None,
                    products=products)
                line["candidates"] = [
                    {"product_id": c.product_id, "name": c.name, "score": c.score}
                    for c in found
                ]
            else:
                line["candidates"] = []
            lines.append(line)
        return {"recipe": recipe, "steps": repo.list_steps(conn, recipe_id),
                "ingredients": lines}

    def update_recipe(self, recipe_id: int, fields: Mapping[str, Any]) -> None:
        with self.db.write() as conn:
            if repo.get_recipe(conn, recipe_id) is None:
                raise ValueError(f"unknown recipe {recipe_id}")
            repo.update_recipe_fields(conn, recipe_id, fields)

    def delete_recipe(self, recipe_id: int) -> None:
        """Remove a recipe — unless a validated meal names it.

        A `done` meal is history. Deleting what it names would leave the
        journal pointing at nothing, and the journal is append-only precisely
        so that cannot happen. Deactivating is the path instead: the recipe
        stops being offered and the past stays readable.
        """
        with self.db.write() as conn:
            if repo.get_recipe(conn, recipe_id) is None:
                raise ValueError(f"unknown recipe {recipe_id}")
            if repo.recipe_is_referenced_by_a_done_meal(conn, recipe_id):
                raise ValueError(
                    f"recipe {recipe_id} has already been cooked")
            repo.delete_recipe(conn, recipe_id)

    def write_source_recipe(self, recipe: SourceRecipe, *,
                            adapted: AdaptedRecipe | None = None) -> tuple[int, bool]:
        """Write an imported card. Replayable: returns `(recipe_id, created)`.

        A second import of the same `source_ref` UPDATES the first rather than
        making a twin — that is what `idx_recipe_source` guarantees, and what
        makes re-importing safe to do on a hunch.

        A rewrite never touches a line a human confirmed, nor a step edited by
        hand. Same rule as `article.manual_fields` protecting a typed value
        from an OFF resync: the machine may refresh what it wrote, never what
        someone corrected.
        """
        moment = _now()
        with self.db.write() as conn:
            existing = repo.find_recipe_by_source(conn, "themealdb", recipe.source_ref)
            created = existing is None
            # Adapted or not, in one shot. There is no half-adapted recipe:
            # `adapt` returns a whole AdaptedRecipe or None, so the fields
            # below either all come from the agent or all come from the source.
            if adapted is None:
                fields = {"name": recipe.name, "language": "en",
                          "needs_review": 1, "adapted_at": None}
            else:
                fields = {
                    "name": adapted.name, "summary": adapted.summary,
                    "total_minutes": adapted.total_minutes,
                    "utensils": adapted.utensils, "servings": adapted.servings,
                    "language": "fr", "needs_review": 0, "adapted_at": moment,
                }
            fields |= {"image_url": recipe.image_url,
                       "source_url": recipe.source_url}

            if created:
                recipe_id = repo.insert_recipe(
                    conn, source="themealdb", created_at=moment,
                    source_ref=recipe.source_ref, **fields)
            else:
                recipe_id = existing["id"]
                repo.update_recipe_fields(conn, recipe_id, fields)
                conn.execute(
                    "DELETE FROM recipe_instruction WHERE step_id IN"
                    " (SELECT id FROM recipe_step WHERE recipe_id = ?)", (recipe_id,))
                conn.execute("DELETE FROM recipe_step WHERE recipe_id = ?", (recipe_id,))

            if adapted is not None:
                _write_steps_within(conn, recipe_id, [
                    {"title": step.title,
                     "instructions": [
                         {"text": text, "timer_label": label,
                          "timer_seconds": seconds}
                         for text, label, seconds in step.bullets]}
                    for step in adapted.steps])
            _write_source_ingredients_within(conn, recipe_id, recipe, moment,
                                             adapted=adapted)
            return recipe_id, created

    # --- meals -------------------------------------------------------------

    def plan_meal(self, *, day: str, slot_key: str, recipe_id: int | None = None,
                  product_id: int | None = None, amount: float | None = None,
                  packaging_id: int | None = None, note: str | None = None,
                  servings: float = 1.0, position: int | None = None,
                  uid: str | None = None,
                  created_at: str | None = None) -> dict[str, Any]:
        """Put one meal on one food day. Returns `{"meal_id", "uid"}`.

        `day` is a FOOD day in extended `YYYY-MM-DD` form and nothing else —
        a date the caller has already decided, not an instant to convert.
        The compact and week forms `date.fromisoformat` has accepted since
        Python 3.11 make SQLite's `julianday()` return NULL, which would drop
        the meal out of the planning without a word.
        """
        _checked_day(day)
        _checked_slot(slot_key)
        natures = sum(value is not None for value in (recipe_id, product_id, note))
        if natures != 1:
            raise ValueError(
                "a meal is exactly one of a recipe, a product or a note, "
                f"got {natures}")
        servings = _checked_servings(servings)

        moment = created_at or _now()
        meal_uid = uid or f"home-stock-meal-{uuid4()}"
        with self.db.write() as conn:
            if recipe_id is not None and repo.get_recipe(conn, recipe_id) is None:
                raise ValueError(f"unknown recipe {recipe_id}")
            meal_id = repo.insert_meal(
                conn, uid=meal_uid, day=day, slot_key=slot_key, created_at=moment,
                recipe_id=recipe_id, product_id=product_id, amount=amount,
                packaging_id=packaging_id, note=note, servings=servings,
                position=(repo.next_meal_position(conn, day, slot_key)
                          if position is None else position))
            return {"meal_id": meal_id, "uid": meal_uid}

    def move_meal(self, meal_id: int, *, day: str, slot_key: str,
                  position: int | None = None) -> None:
        """Move a planned meal to another day or slot.

        A `done` meal never moves. Its movements carry a date nothing can
        change any more, and moving the row would silently decouple the two:
        the journal would say Tuesday, the planning Thursday, and neither
        would be wrong on its own terms.
        """
        _checked_day(day)
        _checked_slot(slot_key)
        with self.db.write() as conn:
            meal = repo.get_meal(conn, meal_id)
            if meal is None:
                raise ValueError(f"unknown meal {meal_id}")
            if meal["state"] == "done":
                raise ValueError(f"meal {meal_id} is already done")
            repo.update_meal_fields(conn, meal_id, {
                "day": day, "slot_key": slot_key,
                "position": (repo.next_meal_position(conn, day, slot_key)
                             if position is None else position)})

    def cancel_meal(self, meal_id: int) -> str:
        """Drop a planned meal, or mark a validated one skipped.

        Returns `"deleted"` or `"skipped"`. Deleting a `done` meal would
        destroy the `movement.ref_type = 'meal'` reference the journal already
        carries — and the journal is append-only precisely so that cannot
        happen. Skipping says the same thing without erasing anything.
        """
        with self.db.write() as conn:
            meal = repo.get_meal(conn, meal_id)
            if meal is None:
                raise ValueError(f"unknown meal {meal_id}")
            if meal["state"] == "done":
                repo.update_meal_fields(conn, meal_id, {"state": "skipped"})
                return "skipped"
            repo.delete_meal(conn, meal_id)
            return "deleted"

    def list_meals(self, start: str, end: str) -> list[dict[str, Any]]:
        _checked_day(start)
        _checked_day(end)
        return repo.list_meals(self.db.read(), start, end)

    def meal_summary(self, *, tz: ZoneInfo, now: datetime | None = None,
                     horizon_days: int = MEAL_HORIZON_DAYS) -> dict[str, Any]:
        """What the coordinator publishes: the next meal, the recipes, the gaps.

        Anchored on the FOOD day, not the calendar day: at one in the morning
        you are still finishing yesterday evening, and yesterday's dinner is
        still "next" rather than already missed.
        """
        today = food_day_of(now or datetime.now(UTC), tz)
        conn = self.db.read()
        recipes = repo.list_recipes(conn)
        return {
            "next": repo.next_meal(conn, today.isoformat()),
            "recipes": {
                "total": len(recipes),
                "to_review": sum(1 for r in recipes if r["needs_review"]),
                "unmatched": sum(r["unmatched_count"] for r in recipes),
            },
            "missing": repo.missing_products_between(
                conn, today.isoformat(),
                (today + timedelta(days=horizon_days)).isoformat()),
        }

    def preview_meal(self, meal_id: int, *, servings: float | None = None,
                     skip_ingredient_ids: Collection[int] = (),
                     portions_eaten: float | None = None,
                     parts_total: int | None = None,
                     parts_mine: int | None = None,
                     today: str | None = None,
                     allow_done: bool = False) -> dict[str, Any]:
        """What validating this meal WOULD do. Writes absolutely nothing.

        Runs on a read connection and goes through `domain.recipes.plan_decrement`,
        which goes through `domain.stock.allocate` — the very function the real
        consumption uses. A simulation that does not share its code with the
        execution is a simulation that lies eventually, so there is no second
        FIFO anywhere in this lot.

        It does not create the leftover product either: the dish summary names
        the FUTURE product without writing it.
        """
        conn = self.db.read()
        meal = repo.get_meal(conn, meal_id)
        if meal is None:
            raise LookupError(f"unknown meal {meal_id}")
        if meal["state"] == "done" and not allow_done:
            raise ValueError(f"meal {meal_id} is already done")

        wanted = _checked_servings(servings if servings is not None else meal["servings"])
        skipped = set(skip_ingredient_ids)
        preview: dict[str, Any] = {
            "meal_id": meal_id, "day": meal["day"], "slot_key": meal["slot_key"],
            "recipe": None, "servings": wanted, "factor": 1.0,
            "lines": [], "by_hand": [], "dish": None, "blocking": [],
        }

        recipe = (repo.get_recipe(conn, meal["recipe_id"])
                  if meal["recipe_id"] is not None else None)
        if recipe is None:
            # A note meal ("restaurant") decrements nothing and produces no
            # dish. A product meal is one line, planned like any other.
            if meal["product_id"] is not None:
                preview["lines"], preview["by_hand"], preview["blocking"] = (
                    _plan_product_meal(conn, meal, wanted))
            return preview

        preview["recipe"] = {"id": recipe["id"], "name": recipe["name"],
                             "servings": recipe["servings"]}
        factor = scale_factor(wanted, recipe["servings"])
        preview["factor"] = factor

        rows = repo.list_ingredients(conn, recipe["id"])
        lines = [_ingredient_line(row) for row in rows]
        batches_by_product = {
            product_id: [as_batch_view(batch)
                         for batch in repo.list_batches_for_product(conn, product_id)]
            for product_id in {line.product_id for line in lines
                               if line.product_id is not None}
        }
        needs = plan_decrement(lines, batches_by_product, factor=factor,
                               skipped_ids=skipped)

        frozen: list[dict[str, float | None]] = []
        for need, row in zip(needs, rows, strict=True):
            entry = _need_entry(need, row)
            if need.status == "ignored":
                # Salt, pepper, water. Ignored means silent: without this
                # state the same judgement call would come back at every
                # recipe, which is the work the alias table exists to shrink.
                continue
            if need.status in ("unmatched", "unquantified"):
                preview["by_hand"].append(entry)
                continue
            preview["lines"].append(entry)
            if need.status == "short":
                preview["blocking"].append("short")
            for allocation in need.allocations:
                values = movement_values(allocation.quantity,
                                         allocation.kcal_per_base_unit,
                                         allocation.price_per_base_unit,
                                         macro_rates=allocation.macros)
                frozen.append({"kcal": values.kcal, "cost": values.cost,
                               **values.macros})

        preview["blocking"] = sorted(set(preview["blocking"]))
        preview["dish"] = _dish_summary(conn, recipe, wanted, frozen, today)
        return preview

    def validate_meal(self, meal_id: int, *, portions_eaten: float,
                      servings: float | None = None,
                      parts_total: int | None = None,
                      parts_mine: int | None = None,
                      skip_ingredient_ids: Collection[int] = (),
                      dry_run: bool = True,
                      occurred_at: str | None = None) -> dict[str, Any]:
        """Cook, then eat, in ONE transaction. `dry_run` is the default.

        Simulating by default follows `import_grocy_catalog`, which has done so
        since lot 0: a service that decrements a stock must not do it on the
        first exploratory call from the developer tools.

        The three writes, in this exact order:

        1. the ingredients leave with reason `cooked`, FIFO, one movement per
           batch crossed, each freezing its own price, kcal and eight macros;
        2. the dish enters with reason `cooked`, one batch on the recipe's
           leftover product, valued from the movements just written;
        3. the evening's portion leaves with reason `consumption`, out of the
           batch created one step earlier.

        Idempotency does NOT rest on the panel's key. It rests on the
        deterministic family `meal:<id>:…`: two different panel keys for the
        same meal must not decrement it twice. A replay reads the movements
        back by key prefix and returns the same ids.

        This is not reversible at lot 3, and the screen says so rather than
        pretending otherwise.
        """
        # Zero portions is a real answer, not a refusal: cooking a big dish on
        # Sunday to eat during the week is exactly the case leftovers exist
        # for. Negative, infinite and NaN are refused — an infinite portion
        # would reach the movement row as `Inf`, which Home Assistant's JSON
        # encoder renders as `null`, so nothing would look wrong on screen.
        eaten = _checked_portions(portions_eaten)
        parts_total, parts_mine = _checked_parts(
            REASON_CONSUMPTION, parts_total, parts_mine)

        moment = occurred_at or _now()
        prefix = f"meal:{meal_id}"
        if not dry_run:
            # Looked up BEFORE the simulation is judged. A replay runs against
            # a stock the first pass already decremented, so every line would
            # now read `short` and the replay would be refused instead of
            # recognised — turning a harmless retry into a hard error exactly
            # when the offline queue needs it to be harmless.
            replayed = _replayed_movements(self.db.read(), prefix)
            if replayed:
                return {**self.preview_meal(
                            meal_id, servings=servings,
                            skip_ingredient_ids=skip_ingredient_ids,
                            today=moment[:10], allow_done=True),
                        "movement_ids": replayed,
                        "batch_id": _replayed_dish_batch(self.db.read(), prefix)}

        preview = self.preview_meal(
            meal_id, servings=servings, skip_ingredient_ids=skip_ingredient_ids,
            today=moment[:10])
        if dry_run:
            return preview
        if preview["blocking"]:
            raise ValueError(
                "meal {} cannot be validated: {}".format(
                    meal_id, ", ".join(preview["blocking"])))
        if preview["dish"] is not None and eaten > preview["dish"]["parts"]:
            raise ValueError(
                f"portions_eaten {eaten} exceeds the {preview['dish']['parts']} "
                "parts this meal produces")

        with self.db.write() as conn:
            movement_ids: list[int] = []
            frozen: list[dict[str, float | None]] = []
            for line in preview["lines"]:
                written = self._consume_within(
                    conn, product_id=line["product_id"], quantity=line["needed"],
                    reason=REASON_COOKED, moment=moment,
                    base_unit=line["base_unit"], ref_type="meal", ref_id=meal_id,
                    key=f"{prefix}:ing:{line['ingredient_id']}")
                movement_ids.extend(written)
                for movement_id in written:
                    row = conn.execute(
                        "SELECT kcal, cost, proteins, carbohydrates, sugars,"
                        " added_sugars, fat, saturated_fat, fiber, salt"
                        " FROM movement WHERE id = ?", (movement_id,)).fetchone()
                    frozen.append(dict(row))

            batch_id = None
            if preview["recipe"] is not None:
                batch_id = self._write_dish_within(
                    conn, preview, frozen, moment=moment, meal_id=meal_id,
                    prefix=prefix)
                # The dish's own ENTRY movement counts too. It is a movement
                # this validation wrote, and a replay reads it back with the
                # others: leaving it out here would make the first answer and
                # the replayed one disagree about what happened.
                entry = conn.execute(
                    "SELECT id FROM movement WHERE idempotency_key = ?",
                    (f"{prefix}:dish",)).fetchone()
                if entry is not None:
                    movement_ids.append(int(entry["id"]))
                if eaten > 0:
                    movement_ids.append(self._consume_batch_within(
                        conn, batch_id, quantity=eaten,
                        reason=REASON_CONSUMPTION, moment=moment,
                        parts_total=parts_total, parts_mine=parts_mine,
                        ref_type="meal", ref_id=meal_id, key=f"{prefix}:eaten"))

            repo.update_meal_fields(conn, meal_id, {
                "state": "done", "validated_at": moment,
                "portions_eaten": eaten, "servings": preview["servings"],
                "parts_total": parts_total, "parts_mine": parts_mine,
                # Provenance only. Nothing reads this back to compute anything:
                # what was actually taken is in the movements, which are the
                # only arithmetic there is.
                "skipped_ingredient_ids": json.dumps(sorted(
                    [line["ingredient_id"] for line in preview["by_hand"]]
                    + sorted(skip_ingredient_ids))),
            })
            return {**preview, "movement_ids": movement_ids, "batch_id": batch_id}

    def _write_dish_within(self, conn, preview: Mapping[str, Any],
                           frozen: Sequence[Mapping[str, float | None]], *,
                           moment: str, meal_id: int, prefix: str) -> int:
        """The cooked dish enters the stock, valued from what actually left it.

        The nutrition and the price live on the BATCH, not on the shared
        article (amendment A2): two cookings of the same recipe have neither
        the same nutrients nor the same cost, and writing them on the article
        would overwrite the previous cooking while its portions are still in
        the fridge.
        """
        recipe = repo.get_recipe(conn, preview["recipe"]["id"])
        _, article_id = self._ensure_leftover_product(conn, recipe)
        location_id = _fridge_location(conn)
        dish = preview["dish"]
        parts = dish["parts"]
        nutrition = {
            "kcal_per_base_unit": dish["kcal"],
            **{column: dish[column] for column in MACRO_COLUMNS},
        }
        return self._add_stock_within(
            conn, article_id=article_id, quantity=parts, location_id=location_id,
            moment=moment, best_before=dish["best_before"],
            price_per_base_unit=dish["cost"], reason=REASON_COOKED,
            nutrition=nutrition, ref_type="meal", ref_id=meal_id,
            key=f"{prefix}:dish",
            # A cooked dish was never bought: recording a price observation
            # for it would poison the price history of a product that has no
            # shop and no receipt.
            record_price_observation=False)

    def _ensure_leftover_product(self, conn, recipe: Mapping[str, Any]) -> tuple[int, int]:
        """The recipe's leftover product and its generic article, made once.

        `recipe.leftover_product_id` remembers the link, so a second cooking
        reuses the same product. A generic article accompanies it — lot 0
        §6.3, no exception: a batch always points at an article, so no special
        case appears in the consumption, kcal or cost code.
        """
        existing = recipe["leftover_product_id"]
        if existing is not None:
            article = conn.execute(
                "SELECT id FROM article WHERE product_id = ? ORDER BY id LIMIT 1",
                (existing,)).fetchone()
            if article is not None:
                return existing, int(article["id"])

        category = conn.execute("SELECT id FROM category WHERE name = ?",
                                (LEFTOVER_CATEGORY_NAME,)).fetchone()
        category_id = (int(category["id"]) if category
                       else repo.insert_category(conn, LEFTOVER_CATEGORY_NAME))
        # `product.name` is UNIQUE since m001: on a collision the recipe id
        # disambiguates rather than the write failing.
        name = f"{LEFTOVER_NAME_PREFIX}{recipe['name']}"
        if conn.execute("SELECT 1 FROM product WHERE name = ?", (name,)).fetchone():
            name = f"{name} ({recipe['id']})"
        product_id = repo.insert_product(
            conn, name=name, base_unit="piece", category_id=category_id,
            default_location_id=_fridge_location(conn), edible=1)
        article_id = repo.insert_article(conn, product_id=product_id, is_generic=1)
        repo.update_recipe_fields(conn, recipe["id"],
                                  {"leftover_product_id": product_id})
        return product_id, article_id


    # --- lot 5 : piles, équipements et consommables -------------------------

    def declare_battery(self, *, label: str, kind: str,
                        entity_registry_id: str | None = None,
                        device_id: str | None = None,
                        equipment_id: int | None = None,
                        product_id: int | None = None,
                        cell_count: int = 1,
                        tracked: bool | None = None,
                        exclusion_reason: str | None = None,
                        low_percent: float = DEFAULT_LOW_PERCENT,
                        keep_percent: float = DEFAULT_KEEP_PERCENT,
                        installed_on: str | None = None,
                        expected_life_days: int | None = None,
                        note: str | None = None,
                        external_ref: str | None = None,
                        idempotency_key: str | None = None) -> int:
        """Declare a place where a battery lives. Returns its id.

        Validates before writing, even though both surfaces already called
        `check_battery_fields`: a third door exists — the import (task 13) —
        and a rule only enforced at the surfaces is a rule an import that
        writes fourteen rows in one go quietly walks around.
        """
        if kind not in BATTERY_KINDS:
            raise vol.Invalid(f"unknown battery kind {kind!r}")
        fields = {
            "entity_registry_id": entity_registry_id, "device_id": device_id,
            "equipment_id": equipment_id, "product_id": product_id,
            "cell_count": cell_count, "tracked": tracked,
            "exclusion_reason": exclusion_reason, "low_percent": low_percent,
            "keep_percent": keep_percent, "installed_on": installed_on,
            "expected_life_days": expected_life_days, "note": note,
            "external_ref": external_ref,
        }
        check_battery_fields(fields, kind=kind)
        # `battery` has no idempotency_key column (the DDL is the spec's, and
        # no column is added to it), so the replay marker rides in
        # `external_ref` — the same column the Grocy import uses for its own
        # id. That is safe only because both sides are NAMESPACED: the queue
        # writes "declare_battery:<uuid>", the import writes "grocy:battery:7"
        # (task 13). Never store a bare id here, or lot 7's join between the
        # two systems starts matching a queue token.
        stored_key = _namespaced_key("declare_battery", idempotency_key)
        # An explicit external_ref always wins: the import owns that column
        # for the rows it creates, and its replayability depends on it.
        marker = external_ref or stored_key
        with self.db.write() as conn:
            if stored_key:
                existing = conn.execute(
                    "SELECT id FROM battery WHERE external_ref = ?",
                    (stored_key,)).fetchone()
                if existing is not None:
                    return int(existing["id"])
            return repo.insert_battery(
                conn, label=label, kind=kind, **{**fields, "external_ref": marker})

    def update_battery(self, battery_id: int, fields: dict[str, Any]) -> None:
        """Correct a declaration. Refuses an unknown column, like
        `update_article_fields` already does: a typo in a column name must be
        a refusal, never a silence."""
        unknown = set(fields) - set(repo.BATTERY_FIELDS)
        if unknown:
            raise ValueError(f"unknown battery fields: {sorted(unknown)}")
        with self.db.write() as conn:
            row = repo.get_battery(conn, battery_id)
            if row is None:
                raise ValueError(f"unknown battery {battery_id}")
            # The invariants bind the SUBMITTED fields to the STORED ones: a
            # `product_id` alone is still refused on a built_in battery whose
            # kind is not in the same request, because the kind is in the row.
            merged = {**dict(row), **fields}
            # SQLite gives `tracked` back as 0/1, and `tracked_flag` refuses
            # an int on purpose (0/1/"oui" must not stand in for the three
            # meanings). Normalise the STORED value before merging, or every
            # update of an already-declared battery is refused for a reason
            # that has nothing to do with what the caller sent.
            if "tracked" not in fields and merged.get("tracked") is not None:
                merged["tracked"] = bool(merged["tracked"])
            check_battery_fields(merged, kind=merged["kind"])
            repo.update_battery_fields(conn, battery_id, fields)

    def record_reading(self, battery_id: int, *, percent: float, at: str) -> None:
        with self.db.write() as conn:
            repo.set_battery_reading(conn, battery_id, percent=percent, at=at)

    def list_batteries(self, *, include_untracked: bool = True) -> list[dict[str, Any]]:
        """Every declared place, in the shape `domain/maintenance` expects —
        minus `state` and `entity_id`, which only the coordinator can resolve.
        """
        conn = self.db.read()
        rows = repo.list_batteries(conn)
        stock = repo.spare_stock(
            conn, {row["product_id"] for row in rows if row["product_id"]})
        batteries = []
        for row in rows:
            if not include_untracked and not row["tracked"]:
                continue
            battery = dict(row)
            battery["tracked"] = (None if row["tracked"] is None
                                  else bool(row["tracked"]))
            battery["spare"] = None if row["product_id"] is None else {
                "label": row["spare_label"],
                "cell_count": int(row["cell_count"]),
                "in_stock": stock.get(row["product_id"], 0.0),
            }
            batteries.append(battery)
        return batteries

    def list_battery_events(self, battery_id: int, limit: int = 20) -> list[dict[str, Any]]:
        return repo.list_battery_events(self.db.read(), battery_id, limit)

    def maintenance_plan(self, *, now: datetime, readings: Mapping[int, Mapping[str, Any]],
                         extra_items: Sequence[Any] | None = None,
                         extra_keep: Sequence[Any] | None = None,
                         spares: Mapping[str, Mapping[str, Any]] | None = None,
                         ) -> dict[str, Any]:
        """The plan `home_stock.maintenance_plan` answers with.

        NEVER raises towards its caller: it catches, logs, and answers
        `complete: False`. That is the whole contract of task 15 — an
        incomplete plan may add and refresh, never close. A plan that raised
        would take the battery items out of `items` AND out of `keep`, and one
        single 5:05 sync would close all fourteen battery tasks of the house.
        """
        try:
            rows = []
            for battery in self.list_batteries():
                reading = readings.get(battery["id"], {})
                rows.append({**battery,
                             "entity_id": reading.get("entity_id"),
                             "state": reading.get("state")})
            own = battery_plan(rows, now=now)
            merged = merge_plan(own, extra_items=extra_items,
                                extra_keep=extra_keep, spares=spares)
            return {**merged, "complete": True}
        except Exception:  # noqa: BLE001 - the refusal is data, not an exception
            _LOGGER.exception(
                "maintenance_plan could not be built; answering complete=False "
                "so the reconciliation adds and refreshes but closes nothing")
            own = battery_plan([], now=now)
            merged = merge_plan(own, extra_items=extra_items, extra_keep=extra_keep)
            return {**merged, "complete": False}

    def record_battery_event(self, battery_id: int, *, kind: str,
                             occurred_at: str | None = None,
                             consume_spare: bool | None = None,
                             note: str | None = None,
                             idempotency_key: str | None = None) -> dict[str, Any]:
        """Record a charge or a replacement, and take the spare out of the
        cupboard when there is one to take.

        ONE transaction, never two. The event and the movement are written on
        the SAME connection: `Database._lock` is not reentrant, so calling
        `self.consume(...)` from inside this `db.write()` block would freeze
        the process forever, with no exception to see it by. That is why this
        goes through `_consume_within`.

        Idempotence crosses both tables: the movement's key is
        `_namespaced_key('battery_event', key)`, so a replay from the offline
        queue can neither write a second event nor decrement the cupboard
        twice, and answers the SAME `event_id`.
        """
        if kind not in BATTERY_EVENT_KINDS:
            raise vol.Invalid(f"unknown battery event kind {kind!r}")
        moment = occurred_at or _now()
        stored_key = _namespaced_key("battery_event", idempotency_key)
        with self.db.write() as conn:
            if stored_key:
                existing = repo.battery_event_by_key(conn, stored_key)
                if existing is not None:
                    return {"event_id": int(existing["id"]),
                            "movement_id": existing["movement_id"],
                            "spare_refused": None}
            battery = repo.get_battery(conn, battery_id)
            if battery is None:
                raise ValueError(f"unknown battery {battery_id}")

            # `consume_spare` defaults by nature, and an explicit value always
            # wins. A rechargeable cell consumes NOTHING by default: the four
            # LADDA rotate between the drawer and three sensors, and counting
            # each rotation would empty the stock in a year while all four
            # cells are still in the house — a lying shortage, and a shopping
            # line for batteries one already owns.
            wants_spare = consume_spare
            if wants_spare is None:
                wants_spare = (battery["kind"] == "primary"
                               and battery["product_id"] is not None)
            check_battery_event(kind, battery_kind=battery["kind"],
                                consume_spare=bool(wants_spare),
                                product_id=battery["product_id"])

            movement_id: int | None = None
            spare_refused: str | None = None
            # The spare comes out of the cupboard BEFORE the event is written,
            # not after: `battery_event` is append-only (two triggers), so
            # there is no second pass to fill `movement_id` in. The event is
            # therefore written once, complete, whichever way this goes.
            if wants_spare and battery["product_id"] is not None:
                try:
                    movement_ids = self._consume_within(
                        conn, product_id=int(battery["product_id"]),
                        quantity=float(battery["cell_count"]),
                        reason=REASON_CONSUMPTION, moment=moment,
                        key=stored_key)
                except InsufficientStock as err:
                    # The event still gets written. We do not lose "the
                    # battery was changed" because the cupboard was out of
                    # date; the refusal travels back as data, all the way to
                    # the panel.
                    spare_refused = french_message(err)
                else:
                    movement_id = movement_ids[0] if movement_ids else None

            event_id = repo.insert_battery_event(
                conn, battery_id=battery_id, occurred_at=moment, kind=kind,
                movement_id=movement_id, note=note, idempotency_key=stored_key)

            if kind in ("install", "replacement"):
                # A new cell: we know nothing about it until the device
                # speaks, so the old reading goes. It is also what stops a
                # "Pile HS ?" from firing the minute after a replacement.
                repo.update_battery_fields(conn, battery_id, {
                    "installed_on": moment[:10],
                    "last_percent": None, "last_reading_at": None,
                })

            return {"event_id": event_id, "movement_id": movement_id,
                    "spare_refused": spare_refused}

    # --- lot 5 : les équipements -------------------------------------------

    _EQUIPMENT_DATE_FIELDS: Final = ("purchased_on",)
    _EQUIPMENT_PATH_FIELDS: Final = ("manual_media_id", "receipt_media_id")

    @staticmethod
    def _checked_equipment_fields(fields: dict[str, Any]) -> dict[str, Any]:
        """Guard the two kinds of field that can poison a later refresh: a
        malformed date (which makes every coordinator pass raise, taking every
        entity unavailable) and a path that escapes `media/`."""
        checked = dict(fields)
        for column in StockManager._EQUIPMENT_DATE_FIELDS:
            if checked.get(column) is not None:
                checked[column] = iso_date(checked[column])
        for column in StockManager._EQUIPMENT_PATH_FIELDS:
            if checked.get(column) is not None:
                checked[column] = media_path(checked[column])
        return checked

    def create_equipment(self, *, name: str, device_id: str | None = None,
                         location_id: int | None = None, brand: str | None = None,
                         model: str | None = None, serial: str | None = None,
                         purchased_on: str | None = None,
                         purchase_price: float | None = None,
                         warranty_months: int | None = None,
                         manual_url: str | None = None,
                         manual_media_id: str | None = None,
                         receipt_media_id: str | None = None,
                         note: str | None = None, external_ref: str | None = None,
                         idempotency_key: str | None = None) -> int:
        """Create an equipment sheet. Returns its id.

        `purchase_price` writes NO movement. It is sheet data: a 900 € TV in a
        journal whose `cost_today` feeds the day's food spending would make
        that sensor useless forever — and the journal is append-only, so the
        mistake would not be correctable.
        """
        fields = self._checked_equipment_fields({
            "device_id": device_id, "location_id": location_id, "brand": brand,
            "model": model, "serial": serial, "purchased_on": purchased_on,
            "purchase_price": purchase_price, "warranty_months": warranty_months,
            "manual_url": manual_url, "manual_media_id": manual_media_id,
            "receipt_media_id": receipt_media_id, "note": note,
        })
        stored_key = _namespaced_key("create_equipment", idempotency_key)
        marker = external_ref or stored_key
        with self.db.write() as conn:
            if stored_key:
                existing = conn.execute(
                    "SELECT id FROM equipment WHERE external_ref = ?",
                    (stored_key,)).fetchone()
                if existing is not None:
                    return int(existing["id"])
            return repo.insert_equipment(conn, name=name,
                                         **{**fields, "external_ref": marker})

    def update_equipment(self, equipment_id: int, fields: dict[str, Any]) -> None:
        unknown = set(fields) - set(repo.EQUIPMENT_FIELDS)
        if unknown:
            raise ValueError(f"unknown equipment fields: {sorted(unknown)}")
        checked = self._checked_equipment_fields(fields)
        with self.db.write() as conn:
            if repo.get_equipment(conn, equipment_id) is None:
                raise ValueError(f"unknown equipment {equipment_id}")
            repo.update_equipment_fields(conn, equipment_id, checked)

    def list_equipment(self, *, today: date | None = None) -> list[dict[str, Any]]:
        """Every sheet, with the warranty end and the days left — signed.

        An EXPIRED warranty keeps its date here, with a negative `days_left`:
        the panel owes three distinct sentences (ahead, over, never recorded)
        and cannot write the second one from a row that hides the date. Only
        `warranties()` narrows to what is still ahead.
        """
        day = today or date.today()
        conn = self.db.read()
        ends = {row["id"]: row["warranty_ends_on"] for row in repo.warranty_rows(conn)}
        rows = []
        for row in repo.list_equipment(conn):
            ends_on = ends.get(row["id"])
            rows.append({
                **row,
                "warranty_ends_on": ends_on,
                "days_left": None if ends_on is None
                else (date.fromisoformat(ends_on) - day).days,
            })
        return rows

    def get_equipment(self, equipment_id: int) -> dict[str, Any]:
        conn = self.db.read()
        row = repo.get_equipment(conn, equipment_id)
        if row is None:
            raise ValueError(f"unknown equipment {equipment_id}")
        consumables = repo.list_consumables(conn, equipment_id)
        stock = repo.spare_stock(conn, {c["product_id"] for c in consumables})
        return {
            **row,
            "consumables": [{**c, "in_stock": stock.get(c["product_id"], 0.0)}
                            for c in consumables],
            "batteries": [b for b in self.list_batteries()
                          if b["equipment_id"] == equipment_id],
        }

    def link_consumable(self, *, equipment_id: int, product_id: int, role: str,
                        label: str | None = None,
                        entity_registry_id: str | None = None,
                        low_value: float | None = None,
                        keep_value: float | None = None,
                        unit: str | None = None,
                        expected_life_days: int | None = None,
                        installed_on: str | None = None) -> int:
        if role not in CONSUMABLE_ROLES:
            raise vol.Invalid(f"unknown consumable role {role!r}")
        if unit is not None and unit not in CONSUMABLE_UNITS:
            raise vol.Invalid(f"unknown consumable unit {unit!r}")
        with self.db.write() as conn:
            return repo.link_consumable(
                conn, equipment_id=equipment_id, product_id=product_id, role=role,
                label=label, entity_registry_id=entity_registry_id,
                low_value=low_value, keep_value=keep_value, unit=unit,
                expected_life_days=expected_life_days,
                installed_on=iso_date(installed_on))

    def unlink_consumable(self, consumable_id: int) -> None:
        with self.db.write() as conn:
            repo.unlink_consumable(conn, consumable_id)

    def warranties(self, *, today: date) -> list[dict[str, Any]]:
        """Only the deadlines still AHEAD, soonest first.

        A warranty that has run out is no longer a deadline: it leaves this
        list, and therefore the sensor. That is the coherent reading of "a
        warranty never produces a task" — what is over is not watched any
        more.
        """
        ahead = []
        for row in repo.warranty_rows(self.db.read()):
            days_left = (date.fromisoformat(row["warranty_ends_on"]) - today).days
            if days_left >= 0:
                ahead.append({**row, "days_left": days_left})
        return ahead

    def record_readings(self, readings) -> None:
        """Write a whole refresh's worth of readings in one transaction."""
        rows = list(readings)
        if not rows:
            return
        with self.db.write() as conn:
            repo.set_battery_readings(conn, rows)

    # --- lot 4 : corriger une ligne déjà écrite ---------------------------

    def preview_correction(self, movement_id: int) -> dict[str, Any]:
        """Ce que la correction fera, AVANT de la faire.

        Une opération irréversible qui ne s'annonce pas est une opération
        qu'on déclenche par erreur (§ 12.6).
        """
        conn = self.db.read()
        movement = repo.get_movement(conn, movement_id)
        if movement is None:
            raise LookupError(f"unknown movement {movement_id}")
        row = conn.execute(
            "SELECT p.name AS product_name, p.base_unit FROM product p WHERE p.id = ?",
            (movement["product_id"],),
        ).fetchone()
        batch = None
        if movement["batch_id"] is not None:
            batch = conn.execute(
                "SELECT entered_at FROM batch WHERE id = ?", (movement["batch_id"],)
            ).fetchone()
        preview: dict[str, Any] = {
            "movement_id": movement_id,
            "product_name": row["product_name"] if row else None,
            "base_unit": movement["base_unit"] or (row["base_unit"] if row else None),
            # Ce que la correction ANNULE, dit positivement : « annule 200 g
            # de Pâtes — 700 kcal, 0,80 € ». Le signe vit dans l'écriture,
            # pas dans la phrase qu'on lit avant d'appuyer.
            "quantity": abs(movement["quantity"]),
            "kcal": movement["kcal"],
            "cost": movement["cost"],
            "reason": movement["reason"],
            "occurred_at": movement["occurred_at"],
            "batch_id": movement["batch_id"],
            "batch_entered_at": batch["entered_at"] if batch else None,
            "correctable": True,
            "refusal": None,
        }
        existing = repo.correction_of(conn, movement_id)
        if existing is not None:
            return {**preview, "correctable": False,
                    "refusal": french_message(
                        CorrectionError(f"movement {movement_id} has already been corrected"))}
        try:
            check_correctable(movement)
        except CorrectionError as err:
            return {**preview, "correctable": False, "refusal": french_message(err)}
        return preview

    def correct_movement(self, movement_id: int, *,
                         occurred_at: str | None = None) -> dict[str, Any]:
        """Contrepasser une ligne du journal : une écriture DE PLUS.

        `movement` est en ajout seul depuis le lot 0 ; la correction n'est
        donc jamais un `UPDATE`. Elle porte le motif de la ligne qu'elle
        annule — `reason` est le compte comptable — et le lien vit dans
        `movement.corrects_id` (amendement A1).
        """
        moment = occurred_at or _now()
        with self.db.write() as conn:
            movement = repo.get_movement(conn, movement_id)
            if movement is None:
                raise LookupError(f"unknown movement {movement_id}")
            batch_id = movement["batch_id"]
            restored = batch_id is not None and conn.execute(
                "SELECT 1 FROM batch WHERE id = ?", (batch_id,)).fetchone() is not None
            existing = repo.correction_of(conn, movement_id)
            if existing is not None:
                # Rejeu de la file hors ligne : la même clé, le même résultat,
                # et surtout AUCUNE seconde remise en stock. La garantie
                # « une seule annulation » est tenue par l'index UNIQUE,
                # cette lecture ne fait qu'éviter de la faire lever.
                return {
                    "movement_id": movement_id,
                    "correction_id": int(existing["id"]),
                    "batch_id": batch_id,
                    "restored": restored,
                }
            correction_id = self._correct_movement_within(
                conn, movement, moment=moment)
            return {
                "movement_id": movement_id,
                "correction_id": correction_id,
                "batch_id": batch_id,
                "restored": restored,
            }

    def _correct_movement_within(self, conn, movement: Mapping[str, Any], *,
                                 moment: str,
                                 allow_cooked: bool = False,
                                 adjust_stock: bool = True) -> int:
        """Le corps d'une contrepassation, sur une connexion déjà tenue.

        Extrait pour `correct_price` et `correct_meal`, qui en écrivent
        plusieurs dans UNE transaction. `Database._lock` n'est pas réentrant :
        appeler `correct_movement` depuis l'intérieur d'un `db.write()` fige le
        processus, sans exception et sans trace.

        `adjust_stock=False` sert à `correct_price`, dont la paire
        contrepassation + réécriture est de solde NUL sur la quantité :
        ajuster le lot entre les deux le ferait passer par un état négatif
        et déclencherait un refus sur une correction pourtant légitime.
        """
        check_correctable(movement, allow_cooked=allow_cooked)
        line = reversal(movement, moment=moment)
        batch_id = line.pop("batch_id")
        if batch_id is not None and adjust_stock:
            batch = conn.execute(
                "SELECT remaining FROM batch WHERE id = ?", (batch_id,)
            ).fetchone()
            if batch is not None:
                after = batch["remaining"] + line["quantity"]
                if after < -QUANTITY_EPSILON:
                    # Le stock a déjà été repris ailleurs : un lot à quantité
                    # négative serait pire que le refus.
                    raise ValueError(
                        f"reversing movement {movement['id']} would leave batch"
                        f" {batch_id} negative; only {batch['remaining']} left")
                # Un lot PEUT dépasser sa quantité initiale : c'est le seul
                # cas où la correction est vraiment utile (§ 12.2).
                closes = is_empty(after)
                repo.set_batch_remaining(
                    conn, batch_id, 0.0 if closes else after,
                    closed_at=moment if closes else None)
        return repo.insert_movement(conn, batch_id=batch_id, **line)

    # --- § 12.4 : corriger un prix ----------------------------------------

    @staticmethod
    def _movements_to_reprice(conn, batch_id: int) -> list[dict[str, Any]]:
        """Les lignes de ce lot qui ne sont ni des annulations ni annulées.

        Une ligne déjà contrepassée ne se contrepasse pas deux fois (index
        UNIQUE), et une contrepassation ne se corrige pas : ce sont les
        réécritures qui portent le coût courant.
        """
        return [
            row for row in repo.movements_of_batch(conn, batch_id)
            if row["corrects_id"] is None
            and repo.correction_of(conn, row["id"]) is None
        ]

    def preview_price_correction(self, batch_id: int, *,
                                 price_per_base_unit: float | None) -> dict[str, Any]:
        """« 3 mouvements déjà écrits seront corrigés », ou zéro. N'écrit rien."""
        conn = self.db.read()
        batch = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
        if batch is None:
            raise LookupError(f"unknown batch {batch_id}")
        affected = self._movements_to_reprice(conn, batch_id)
        return {
            "batch_id": batch_id,
            "price_per_base_unit": price_per_base_unit,
            "previous_price_per_base_unit": batch["price_per_base_unit"],
            "corrected_movements": len(affected),
        }

    def correct_price(self, batch_id: int, *, price_per_base_unit: float | None,
                      observed_on: str | None = None,
                      store_id: int | None = None,
                      source: str = "manual",
                      moment: str | None = None) -> dict[str, Any]:
        """Corriger le prix d'un lot, des deux côtés (§ 12.4), en UNE transaction.

        En avant : le lot porte désormais le bon prix, et une observation
        `price` le dit. Toutes les sorties futures seront chiffrées juste
        sans rien réécrire.

        En arrière : chaque mouvement déjà pris sur ce lot est contrepassé
        PUIS réécrit au coût corrigé. Deux lignes par mouvement, `corrects_id`
        sur la première seulement. Les nutriments sont recopiés à l'identique :
        un prix faux n'a jamais faussé des calories.

        Le cas normal ne produit aucune écriture arrière hors l'achat : un
        ticket lu le soir même corrige des lots dont rien n'est sorti.
        """
        when = moment or _now()
        with self.db.write() as conn:
            batch = conn.execute("SELECT * FROM batch WHERE id = ?",
                                 (batch_id,)).fetchone()
            if batch is None:
                raise LookupError(f"unknown batch {batch_id}")
            affected = self._movements_to_reprice(conn, batch_id)
            repo.set_batch_price(conn, batch_id, price_per_base_unit)
            price_id = None
            if price_per_base_unit is not None:
                price_id = repo.insert_price(
                    conn, article_id=batch["article_id"],
                    observed_on=observed_on or when[:10],
                    price_per_base_unit=price_per_base_unit,
                    source=source, store_id=store_id)
            written: list[int] = []
            for movement in affected:
                self._correct_movement_within(conn, movement, moment=when,
                                              adjust_stock=False)
                line = reprice(movement, price_per_base_unit=price_per_base_unit,
                               moment=when)
                line["idempotency_key"] = f"reprice:{movement['id']}"
                written.append(repo.insert_movement(conn, **line))
            return {
                "batch_id": batch_id,
                "corrected_movements": len(affected),
                "movement_ids": written,
                "price_id": price_id,
            }

    # --- § 12.5 : corriger un repas validé ---------------------------------

    def correct_meal(self, meal_id: int, *,
                     occurred_at: str | None = None) -> dict[str, Any]:
        """Annuler un repas validé : le bloc entier, dans l'ordre INVERSE.

        Une validation écrit N sorties `cooked`, une entrée `cooked` (le plat)
        et une `consumption`. Les contrepasser dans l'ordre où elles ont été
        écrites remettrait le plat en stock avant d'avoir annulé ce qu'on en a
        mangé — d'où l'ordre inverse, et une seule transaction.
        """
        when = occurred_at or _now()
        with self.db.write() as conn:
            meal = repo.get_meal(conn, meal_id)
            if meal is None:
                raise LookupError(f"unknown meal {meal_id}")
            movements = repo.movements_of_meal(conn, meal_id)
            already = [row for row in movements
                       if repo.correction_of(conn, row["id"]) is not None]
            if len(already) == len(movements) and movements:
                # Rejeu : la file hors ligne rejoue, et le résultat ne change pas.
                return {"meal_id": meal_id,
                        "reversed_movements": [row["id"] for row in reversed(movements)],
                        "state": meal["state"]}
            if meal["state"] != "done" or not movements:
                raise ValueError(f"meal {meal_id} was never validated")
            dish_batches = {row["batch_id"] for row in movements
                            if row["reason"] == REASON_COOKED and row["quantity"] > 0}
            for dish_batch_id in dish_batches:
                foreign = [row for row in repo.movements_of_batch(conn, dish_batch_id)
                           if (row["ref_type"], row["ref_id"]) != ("meal", meal_id)]
                if foreign:
                    raise ValueError(
                        f"meal {meal_id} cannot be corrected: its dish has been started")
            reversed_ids: list[int] = []
            for movement in reversed(movements):
                self._correct_movement_within(conn, movement, moment=when,
                                              allow_cooked=True)
                reversed_ids.append(movement["id"])
            repo.update_meal_fields(conn, meal_id, {
                "state": "planned", "validated_at": None, "portions_eaten": None,
            })
            return {"meal_id": meal_id, "reversed_movements": reversed_ids,
                    "state": "planned"}


# =============================================================================
# Lot 3 — matching a recipe ingredient onto a catalogue product.
# =============================================================================

# A leading quantity, as recipe text writes it: a number (decimal, fraction or
# vulgar fraction glyph), then optionally a unit word, then an optional "de".
# Stripped so "2 cs d'huile d'olive" can be compared as "huile d'olive".
#
# This is normalisation of SOURCE TEXT, which is why it lives here and not in
# `domain/units`: the domain converts what it is told, it does not parse prose.
_QUANTITY_WORDS: Final = (
    "g", "kg", "mg", "ml", "cl", "dl", "l", "cs", "cc", "cuillère", "cuillères",
    "cuiller", "cuillerée", "cuillerées", "pincée", "pincées", "sachet", "sachets",
    "tranche", "tranches", "verre", "verres", "gousse", "gousses", "brin", "brins",
    "botte", "bottes", "poignée", "poignées", "boîte", "boîtes", "pot", "pots",
    "bouquet", "feuille", "feuilles", "goutte", "gouttes", "filet", "filets",
    "à", "soupe", "café", "de", "d", "du", "des", "la", "le", "les", "un", "une",
)
_LEADING_NUMBER: Final = re.compile(
    r"^\s*[0-9]+(?:[.,][0-9]+)?(?:\s*/\s*[0-9]+)?\s*|^\s*[¼½¾⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞]\s*")
_WORD_SPLIT: Final = re.compile(r"[\s'’]+")


def _without_quantity(raw_text: str) -> str:
    """`raw_text` with any leading quantity and unit words removed.

    "2 cs d'huile d'olive" becomes "huile d'olive"; "½ concombre" becomes
    "concombre". Only the LEADING run is stripped, so "pain burger" keeps
    both words and "filet de poulet" keeps "poulet" — a filet is a unit word
    at the front and part of the name nowhere else.
    """
    text = _LEADING_NUMBER.sub("", raw_text, count=1).strip()
    words = [w for w in _WORD_SPLIT.split(text) if w]
    while words and words[0].casefold().strip(".") in _QUANTITY_WORDS:
        words.pop(0)
        # A second number may follow the unit ("1 boîte 400 g de tomates").
        if words and _LEADING_NUMBER.match(words[0]):
            words.pop(0)
    return " ".join(words) or text


def resolve_ingredient_match(
    conn, *, raw_text: str, ingredient_name: str | None,
    products: Sequence[dict[str, Any]],
) -> tuple[str, int | None, float | None, list[Candidate]]:
    """Decide what product a recipe line means (spec §8).

    Returns `(match_state, product_id, match_score, candidates_to_offer)`.

    The order is normative and it stops at the first answer:

    1. **An alias.** What a human already decided, looked up on the normalised
       text. It wins outright, and it wins even against a higher-scoring
       preselect: that is what makes the work shrink over time instead of
       being re-litigated at every import.
    2. **Scoring**, over three spellings of the same line — the isolated
       ingredient name, the text without its leading quantity, and the raw
       text. The best of the three wins, exactly as lot 1 tries
       `generic_name_fr`, `product_name_fr` and the de-branded name.
    3. **`preselect()`**, with lot 1's thresholds untouched. One clear winner
       becomes `auto`; anything less comes back `unmatched` with the five
       candidates for a human to arbitrate.

    An `auto` match NEVER writes an alias. Only an explicit human confirmation
    does. Without that rule a wrong automatic match would become permanent and
    contaminate every later recipe — which is exactly how re-matching by name
    produced 35 duplicates in Grocy in April 2026.
    """
    alias = repo.find_alias(conn, normalise(raw_text))
    if alias is not None:
        return "confirmed", alias["product_id"], 1.0, []

    found = candidates(
        names=[ingredient_name, _without_quantity(raw_text), raw_text],
        products=products,
    )
    chosen = preselect(found)
    if chosen is not None:
        return "auto", chosen.product_id, chosen.score, []
    return "unmatched", None, None, list(found)


def _match_ingredient_within(conn, ingredient_id: int, *, product_id: int | None,
                             state: str, create_alias: bool,
                             moment: str) -> dict[str, Any]:
    """The body of `match_ingredient`, on a connection the caller already owns.

    Extracted so a later caller inside another transaction can reuse it:
    `Database._lock` is a plain, non-reentrant lock, and nesting two
    `db.write()` blocks the process for good, with no error and no traceback.
    """
    line = conn.execute(
        "SELECT * FROM recipe_ingredient WHERE id = ?", (ingredient_id,)).fetchone()
    if line is None:
        raise ValueError(f"unknown ingredient line {ingredient_id}")

    repo.update_ingredient_match(conn, ingredient_id, product_id=product_id,
                                 state=state, score=1.0 if product_id else None)
    # Only an explicit human confirmation teaches an alias. An `auto` match
    # never does: a wrong guess made permanent would contaminate every later
    # recipe (Grocy, April 2026 — 35 duplicates from re-matching by name).
    if create_alias and state == "confirmed" and product_id is not None:
        repo.upsert_alias(conn, normalised=normalise(line["raw_text"]),
                          product_id=product_id, created_at=moment)
    return dict(conn.execute(
        "SELECT * FROM recipe_ingredient WHERE id = ?", (ingredient_id,)).fetchone())


def _ingredient_line(row: Mapping[str, Any]) -> IngredientLine:
    """One joined repository row as the pure domain wants to see it.

    Built here and not in `repositories`: the storage layer hands over rows,
    the domain owns value objects, and this is the one seam between them. One
    definition, so no screen can read a measure differently from another.
    """
    measure = None
    if row["measure_id"] is not None:
        measure = Measure(id=row["measure_id"], name=row["measure_name"],
                          base_unit=row["measure_base_unit"],
                          base_quantity=row["measure_base_quantity"])
    return IngredientLine(
        id=row["id"], position=row["position"], product_id=row["product_id"],
        product_base_unit=row["product_base_unit"], amount=row["amount"],
        packaging_base_quantity=row["packaging_base_quantity"],
        packaging_name=row["packaging_name"], measure=measure,
        raw_text=row["raw_text"], match_state=row["match_state"],
        optional=bool(row["optional"]),
    )


def _write_steps_within(conn, recipe_id: int,
                        steps: Sequence[Mapping[str, Any]]) -> None:
    """Write the cooking pages and their bullets, on the caller's connection."""
    for position, step in enumerate(steps, start=1):
        step_id = repo.insert_step(
            conn, recipe_id=recipe_id, position=step.get("position", position),
            title=step.get("title"), image_url=step.get("image_url"))
        for bullet_position, bullet in enumerate(step.get("instructions", ()), start=1):
            repo.insert_instruction(
                conn, step_id=step_id,
                position=bullet.get("position", bullet_position),
                text=bullet["text"], timer_label=bullet.get("timer_label"),
                timer_seconds=bullet.get("timer_seconds"))


# How the source's own unit words name our seeded culinary measures. Only the
# ones m004 actually seeds appear: a unit with no measure behind it must fall
# through to "no usable quantity", never to an invented equivalence.
SOURCE_UNIT_TO_MEASURE: Final = {
    "tbsp": "cuillère à soupe", "tbs": "cuillère à soupe",
    "tablespoon": "cuillère à soupe", "tablespoons": "cuillère à soupe",
    "cs": "cuillère à soupe", "c.s.": "cuillère à soupe",
    "tsp": "cuillère à café", "teaspoon": "cuillère à café",
    "teaspoons": "cuillère à café", "cc": "cuillère à café",
    "c.c.": "cuillère à café",
    "cup": "verre", "cups": "verre", "glass": "verre", "verre": "verre",
    "pinch": "pincée", "pinches": "pincée", "pincée": "pincée",
}


def _resolve_source_quantity(
    ingredient: SourceIngredient, product: Mapping[str, Any] | None,
    measures_by_name: Mapping[str, Mapping[str, Any]],
) -> tuple[float | None, int | None]:
    """`(amount, measure_id)` for an imported line — spec §9's table.

    Three outcomes and no fourth:

    - a convertible mass or volume in the product's own dimension becomes the
      converted number with NO measure (the number is then in base units);
    - a known culinary measure whose dimension matches keeps the number as
      written and records the measure;
    - anything else yields `(None, None)`: the line exists, it shows, and it
      decrements nothing. NULL means unknown, never zero.

    A culinary measure against a `piece` product is refused — a yoghurt is not
    dosed by the spoonful — and so is a mass for a `piece` product, for the
    reason lot 1 already refuses to invent a divisor: a guessed per-piece
    weight writes a false number into an append-only journal.
    """
    if ingredient.amount is None or product is None:
        return None, None
    base_unit = product["base_unit"]

    if ingredient.unit is None:
        # A bare number against a product counted in pieces is "2 eggs", which
        # is exactly what the base unit means. Against grams it would be
        # "2 grams of flour", which the source did not say.
        return (float(ingredient.amount), None) if base_unit == "piece" else (None, None)

    unit = ingredient.unit.strip().casefold()
    converted = convertible_amount(ingredient.amount, unit, base_unit)
    if converted is not None:
        return converted, None

    measure_name = SOURCE_UNIT_TO_MEASURE.get(unit)
    measure = measures_by_name.get(measure_name) if measure_name else None
    if measure is not None and measure["base_unit"] == base_unit:
        return float(ingredient.amount), measure["id"]
    return None, None


def _write_source_ingredients_within(conn, recipe_id: int, recipe: SourceRecipe,
                                     moment: str,
                                     adapted: AdaptedRecipe | None = None) -> None:
    """Rewrite the imported lines, sparing everything a human touched."""
    products = repo.list_products(conn)
    measures_by_name = {m["name"]: m for m in repo.list_measures(conn)}
    protected = {
        row["position"]: row for row in repo.list_ingredients(conn, recipe_id)
        if row["match_state"] == "confirmed"
    }
    conn.execute(
        "DELETE FROM recipe_ingredient WHERE recipe_id = ? AND match_state != ?",
        (recipe_id, "confirmed"))

    for ingredient in recipe.ingredients:
        if ingredient.position in protected:
            continue
        # The agent's isolated name, when it gave one for this position: it
        # is a better needle than the raw text, which still carries its
        # quantity. Positions are 1-based, the tuple is 0-based.
        isolated = ingredient.name
        if adapted is not None and ingredient.position <= len(adapted.ingredient_names):
            isolated = adapted.ingredient_names[ingredient.position - 1]
        state, product_id, score, _ = resolve_ingredient_match(
            conn, raw_text=ingredient.raw_text, ingredient_name=isolated,
            products=products)
        product = next((p for p in products if p["id"] == product_id), None)
        amount, measure_id = _resolve_source_quantity(
            ingredient, product, measures_by_name)
        repo.insert_ingredient(
            conn, recipe_id=recipe_id, position=ingredient.position,
            raw_text=ingredient.raw_text, product_id=product_id,
            amount=amount, measure_id=measure_id, match_state=state,
            match_score=score)


def _checked_day(day: Any) -> str:
    """A food day in extended `YYYY-MM-DD` form, or a refusal.

    Shares `iso_date` with both surfaces so the websocket and the service
    cannot disagree about what a date is — neither is allowed to be the
    weaker one. The `vol.Invalid` it raises is re-raised as `ValueError`:
    the application layer speaks one exception type, which is what lets
    `messages.py` translate every refusal at a single seam.
    """
    try:
        checked = iso_date(day)
    except vol.Invalid as err:
        raise ValueError(f"invalid day {day!r}; expected YYYY-MM-DD") from err
    if checked is None:
        raise ValueError(f"invalid day {day!r}; expected YYYY-MM-DD")
    return checked


def _checked_portions(portions: Any) -> float:
    """A real, finite, non-negative number of portions eaten."""
    try:
        value = finite_float(portions)
    except vol.Invalid as err:
        raise ValueError(
            f"portions_eaten must be a real number, got {portions!r}") from err
    if value < 0:
        raise ValueError(f"portions_eaten must not be negative, got {value}")
    return value


def _checked_servings(servings: Any) -> float:
    """A real, finite, strictly positive serving count."""
    try:
        value = finite_float(servings)
    except vol.Invalid as err:
        raise ValueError(f"servings must be a real number, got {servings!r}") from err
    if value <= 0:
        raise ValueError(f"servings must be positive, got {value}")
    return value


def _checked_slot(slot_key: Any) -> str:
    if slot_key not in MEAL_SLOT_KEYS:
        raise ValueError(
            f"unknown slot {slot_key!r}; expected one of {', '.join(MEAL_SLOT_KEYS)}")
    return slot_key


def _need_entry(need: IngredientNeed, row: Mapping[str, Any]) -> dict[str, Any]:
    """One planned line as the validation screen shows it."""
    return {
        "ingredient_id": need.line.id,
        "label": display_amount(need.line),
        "product_id": need.line.product_id,
        "product_name": row["product_name"],
        "base_unit": need.line.product_base_unit,
        "status": need.status,
        "needed": need.needed,
        "available": need.available,
        "raw_text": row["raw_text"],
        "batches": [
            {"batch_id": allocation.batch_id, "quantity": allocation.quantity}
            for allocation in need.allocations
        ],
    }


def _plan_product_meal(conn, meal: Mapping[str, Any],
                       servings: float) -> tuple[list, list, list]:
    """A meal that is just a product ("a yoghurt"): one line, no dish."""
    product = repo.get_product(conn, meal["product_id"])
    if product is None:
        return [], [], []
    line = IngredientLine(
        id=0, position=1, product_id=product["id"],
        product_base_unit=product["base_unit"], amount=meal["amount"],
        packaging_base_quantity=None, packaging_name=None, measure=None,
        raw_text=product["name"], match_state="confirmed", optional=False)
    batches = [as_batch_view(batch)
               for batch in repo.list_batches_for_product(conn, product["id"])]
    [need] = plan_decrement([line], {product["id"]: batches}, factor=servings)
    entry = _need_entry(need, {"product_name": product["name"],
                               "raw_text": product["name"]})
    if need.status in ("unmatched", "unquantified"):
        return [], [entry], []
    return [entry], [], ["short"] if need.status == "short" else []


def _dish_summary(conn, recipe: Mapping[str, Any], parts: float,
                  frozen: Sequence[Mapping[str, float | None]],
                  today: str | None) -> dict[str, Any]:
    """What the cooked dish will be worth, per part.

    The rates are the ones the batches the FIFO is aiming at actually carry —
    the same frozen values the write will record. A number shown before the
    write must be the number that gets written, or showing it is worse than
    showing nothing.
    """
    shelf_life = recipe["leftover_shelf_life_days"] or LEFTOVER_SHELF_LIFE_DAYS
    day = date.fromisoformat(today) if today else datetime.now(UTC).date()
    per_part = per_part_values(frozen, parts)
    costs = [row["cost"] for row in frozen]
    return {
        "product_name": f"{LEFTOVER_NAME_PREFIX}{recipe['name']}",
        "parts": parts,
        "best_before": (day + timedelta(days=shelf_life)).isoformat(),
        "cost": None if not costs or any(c is None for c in costs)
                else sum(costs) / parts,
        # How many decrements carried no value at all. `kcal_today` already
        # counts these in its `unvalued_movements` attribute; the dish says
        # the same thing at the moment the choice is still reversible.
        "unvalued": sum(1 for row in frozen if row["kcal"] is None),
        **per_part,
    }


def _fridge_location(conn) -> int:
    """The first fridge, or failing that the first location at all.

    A dish with nowhere to go would be a dish that cannot be written, so an
    installation with no fridge declared still gets its leftovers stored
    rather than losing the whole validation over a missing setting.
    """
    row = conn.execute(
        "SELECT id FROM location WHERE kind = 'fridge' ORDER BY position, id"
        " LIMIT 1").fetchone()
    if row is not None:
        return int(row["id"])
    row = conn.execute("SELECT id FROM location ORDER BY position, id LIMIT 1").fetchone()
    if row is None:
        raise ValueError("no location to put the dish in")
    return int(row["id"])


def _replayed_movements(conn, prefix: str) -> list[int]:
    """The movements a previous validation of this meal already wrote.

    Matched on the deterministic `meal:<id>:` family, not on the panel's own
    idempotency key: two different panel keys for the same meal must not cook
    it twice. The prefix is escaped so a '%' or '_' inside it stays literal.
    """
    rows = conn.execute(
        "SELECT id FROM movement WHERE idempotency_key LIKE ? ESCAPE '\\'"
        " ORDER BY id", (f"{_escape_like(prefix)}:%",)).fetchall()
    return [int(row["id"]) for row in rows]


def _replayed_dish_batch(conn, prefix: str) -> int | None:
    row = conn.execute(
        "SELECT batch_id FROM movement WHERE idempotency_key = ?",
        (f"{prefix}:dish",)).fetchone()
    return int(row["batch_id"]) if row and row["batch_id"] is not None else None
