"""Reads and writes, one function per operation. No business logic lives here.

Every function takes an open connection: the caller owns the transaction, so a
service can write a batch and its movement atomically.
"""
from __future__ import annotations

import sqlite3
from calendar import monthrange
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, Final

from ..const import (
    CONSUME_REASONS,
    ROUTE_SESSION_WINDOW,
    MACRO_COLUMNS,
    NUTRITION_COLUMNS,
    OBSERVED_PRICE_SOURCES,
    REASON_CONSUMPTION,
)
from ..domain.matching import normalise
from ..domain.route import is_reliable

PRODUCT_FIELDS = (
    "category_id", "aisle_id", "edible", "default_location_id", "min_quantity",
    "days_after_opening", "default_shelf_life_days", "reference_kcal", "active",
    "external_ref",
)
ARTICLE_FIELDS = (
    "brand", "label", "net_quantity", "image", "kcal_per_base_unit", "proteins",
    "carbohydrates", "sugars", "added_sugars", "fat", "saturated_fat", "fiber",
    "salt", "nutriscore", "nova", "ecoscore", "allergens", "traces", "additives",
    "off_labels", "off_source", "off_synced_at", "off_raw", "manual_fields",
    "is_generic", "external_ref", "serving_quantity",
)

# The kcal rate to price a movement with, in the only order that makes sense:
# the BATCH's own rate first (lot 3, amendment A2 — a cooked dish's calories
# belong to that pan of lasagne, not to every future one), then the article's
# own kcal_per_base_unit, then its product's reference_kcal (spec 7.4) —
# generic and fresh-produce articles usually carry no rate of their own.
# Named once here so the SQL call sites (list_batches_for_product, stock_rows)
# and the Python call sites (resolve_kcal_rate, used by
# application.add_stock/consume_batch) cannot drift apart.
#
# Every query using this MUST join `batch` as `b`, `article` as `a` and
# `product` as `p`. All three do today.
KCAL_RATE_SQL = (
    "COALESCE(b.kcal_per_base_unit, a.kcal_per_base_unit, p.reference_kcal)"
)

# The eight macro rates: the batch's own value when it has one, the article's
# otherwise. Unlike the kcal rate above, there is NO product-level fallback:
# `product.reference_kcal` exists because a generic article (loose apples)
# still has a known calorie count, but nobody maintains a reference protein
# content per product. No value on either means no value, and the movement
# freezes NULL.
#
# The cascade is per COLUMN, not per row: a dish whose protein content is
# known and whose fibre content is not must read the known protein off the
# batch and still fall through to the article for the fibre. A row-level
# choice would throw away eight known values to punish one missing one.
# And COALESCE only skips NULL, never 0.0 — a dish measured at zero salt
# says zero, it does not say "ask the article".
MACRO_RATE_SQL = ", ".join(
    f"COALESCE(b.{column}, a.{column}) AS {column}" for column in MACRO_COLUMNS
)

# The batch's OWN columns, spelled out, MINUS the nine nutrition ones.
#
# Lot 3 (amendment A2) gave `batch` its own kcal_per_base_unit and eight macro
# columns, so `batch` and `article` now share those nine names. `SELECT b.*`
# used to be safe next to KCAL_RATE_SQL/MACRO_RATE_SQL because the names never
# collided; now the row would carry each of those names TWICE and
# `dict(sqlite3.Row)` keeps the FIRST — the raw batch column, ahead of the
# resolved cascade. Every calorie in the stock would read NULL, with no
# exception raised and no test the wiser.
#
# So the batch's nutrition never travels under its own name: it reaches
# callers only through the cascade above, which already reads it first. A
# test forbids `SELECT b.*` across the component so this cannot come back.
BATCH_COLUMNS_SQL = (
    "b.id, b.article_id, b.location_id, b.remaining, b.initial, b.best_before,"
    " b.entered_at, b.opened_at, b.price_per_base_unit, b.session_id, b.closed_at"
)


def macro_rates(row: Mapping[str, Any]) -> dict[str, float | None]:
    """The eight macro rates of an already-read row, keyed by column name."""
    return {column: row[column] for column in MACRO_COLUMNS}


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _rows(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(row) for row in cursor.fetchall()]


def _insert(conn: sqlite3.Connection, table: str, values: dict[str, Any]) -> int:
    columns = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    cursor = conn.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(values.values())
    )
    return int(cursor.lastrowid)


# --- locations, aisles, categories -----------------------------------------

def insert_location(conn, *, name: str, kind: str, position: int = 0) -> int:
    return _insert(conn, "location", {"name": name, "kind": kind, "position": position})


def list_locations(conn) -> list[dict[str, Any]]:
    return _rows(conn.execute("SELECT * FROM location ORDER BY position, name"))


def list_aisles(conn) -> list[dict[str, Any]]:
    """Aisles in walking order. Seeded by the m002 migration."""
    return _rows(conn.execute("SELECT * FROM aisle ORDER BY position, name"))


def insert_category(conn, name: str) -> int:
    return _insert(conn, "category", {"name": name})


def insert_aisle(conn, *, name: str, position: int = 0) -> int:
    # Not called by the integration itself: lot 1 seeds the aisle table from
    # the migration (storage/migrations/m002_scan.py), not through here.
    # Kept for tests and for a future by-shop ordering (lot 4).
    return _insert(conn, "aisle", {"name": name, "position": position})


# --- products ---------------------------------------------------------------

def insert_product(conn, *, name: str, base_unit: str, **fields: Any) -> int:
    values: dict[str, Any] = {"name": name, "base_unit": base_unit}
    values.update({k: v for k, v in fields.items() if k in PRODUCT_FIELDS})
    return _insert(conn, "product", values)


def get_product(conn, product_id: int) -> dict[str, Any] | None:
    return _row(conn.execute("SELECT * FROM product WHERE id = ?", (product_id,)).fetchone())


def find_product_by_name(conn, name: str) -> dict[str, Any] | None:
    # Not called by the integration itself: lot 1 matches a scanned article
    # to a product by score (domain/matching.py), not by exact name, and the
    # duplicate-name case is caught by product.name's UNIQUE constraint.
    return _row(conn.execute("SELECT * FROM product WHERE name = ?", (name,)).fetchone())


def list_products(conn, active_only: bool = True) -> list[dict[str, Any]]:
    sql = "SELECT * FROM product"
    if active_only:
        sql += " WHERE active = 1"
    return _rows(conn.execute(sql + " ORDER BY name"))


# --- articles and barcodes --------------------------------------------------

def insert_article(conn, *, product_id: int, **fields: Any) -> int:
    values: dict[str, Any] = {"product_id": product_id}
    values.update({k: v for k, v in fields.items() if k in ARTICLE_FIELDS})
    return _insert(conn, "article", values)


def get_article(conn, article_id: int) -> dict[str, Any] | None:
    return _row(conn.execute("SELECT * FROM article WHERE id = ?", (article_id,)).fetchone())


def resolve_kcal_rate(conn, article: Mapping[str, Any],
                      batch: Mapping[str, Any] | None = None) -> float | None:
    """The kcal rate to price a movement with: the batch's own rate (lot 3),
    then the article's own kcal_per_base_unit, then its product's
    reference_kcal (spec 7.4). Python-side twin of KCAL_RATE_SQL, for call
    sites that already hold their rows in hand instead of joining kcal in SQL
    (application.add_stock/consume_batch). The two must always agree."""
    if batch is not None and batch["kcal_per_base_unit"] is not None:
        return batch["kcal_per_base_unit"]
    rate = article["kcal_per_base_unit"]
    if rate is not None:
        return rate
    product = get_product(conn, article["product_id"])
    return product["reference_kcal"] if product else None


def batch_macro_rates(batch: Mapping[str, Any] | None,
                      article: Mapping[str, Any]) -> dict[str, float | None]:
    """The eight macro rates, batch first then article, column by column.
    Python-side twin of MACRO_RATE_SQL.

    `is not None` and not a truth test: a macro measured at 0.0 is a
    measurement, and falling through to the article on a zero would quietly
    replace "this dish has no salt" with "this ingredient has some".
    """
    return {
        column: (batch[column] if batch is not None
                 and batch[column] is not None else article[column])
        for column in MACRO_COLUMNS
    }


def find_article_by_barcode(conn, code: str) -> dict[str, Any] | None:
    return _row(
        conn.execute(
            "SELECT a.* FROM article a JOIN barcode b ON b.article_id = a.id"
            " WHERE b.code = ?",
            (code,),
        ).fetchone()
    )


def link_barcode(conn, code: str, article_id: int) -> None:
    conn.execute("INSERT INTO barcode (code, article_id) VALUES (?, ?)", (code, article_id))


def barcodes_to_resync(conn, *, article_id: int | None, product_id: int | None,
                       everything: bool) -> list[tuple[str, int]]:
    """One (code, article_id) pair per article that has a barcode, for the
    `home_stock.resync_off` service: the whole catalogue (`everything`), one
    article, or every article of one product.

    An article linked to more than one code contributes only its lowest one
    — Open Food Facts only needs a single code to answer for an article, and
    a barcode-less article (never scanned, hand-entered) has nothing to
    resync from in the first place, so it is silently left out rather than
    reported as an error.
    """
    if everything:
        where, params = "", ()
    elif article_id is not None:
        where, params = "WHERE a.id = ?", (article_id,)
    elif product_id is not None:
        where, params = "WHERE a.product_id = ?", (product_id,)
    else:
        return []
    rows = conn.execute(
        f"""
        SELECT a.id AS article_id, MIN(b.code) AS code
        FROM article a JOIN barcode b ON b.article_id = a.id
        {where}
        GROUP BY a.id
        ORDER BY a.id
        """,
        params,
    ).fetchall()
    return [(row["code"], row["article_id"]) for row in rows]


# --- packagings and prices --------------------------------------------------

def insert_packaging(conn, *, scope: str, target_id: int, name: str,
                     base_quantity: float, is_purchase_default: bool = False) -> int:
    # Used by StockManager.convert_product_unit (Task 10) to record the name
    # of the pack an article used to be sold in, once its product switches to
    # weight/volume. Net weights themselves still come from Open Food Facts'
    # product_quantity, a measurement, never from a guess parsed out of a
    # product name (design §10, amended 2026-08-18).
    return _insert(conn, "packaging", {
        "scope": scope, "target_id": target_id, "name": name,
        "base_quantity": base_quantity,
        "is_purchase_default": 1 if is_purchase_default else 0,
    })


def insert_price(conn, *, article_id: int, observed_on: str,
                 price_per_base_unit: float, source: str, store: str | None = None,
                 store_id: int | None = None) -> int:
    return _insert(conn, "price", {
        "article_id": article_id, "observed_on": observed_on,
        "price_per_base_unit": price_per_base_unit, "source": source, "store": store,
        "store_id": store_id,
    })


def set_batch_price(conn, batch_id: int, price_per_base_unit: float | None) -> None:
    """The current price of one batch in the fridge — an UPDATE, not a journal
    line. What a batch is worth today is state, not history."""
    conn.execute("UPDATE batch SET price_per_base_unit = ? WHERE id = ?",
                 (price_per_base_unit, batch_id))


def movements_of_meal(conn, meal_id: int) -> list[dict[str, Any]]:
    """Every row one meal validation wrote, in writing order."""
    return _rows(conn.execute(
        "SELECT m.* FROM movement m"
        " WHERE m.ref_type = 'meal' AND m.ref_id = ? ORDER BY m.id", (meal_id,)
    ))


def rescale_prices_for_article(conn, article_id: int, factor: float) -> None:
    """Divide every recorded price of this article by `factor`.

    Used when a product's unit is converted (StockManager.convert_product_unit):
    a price is money PER unit, so it moves opposite to the quantities — 1.20 €
    per packet and 0.0024 €/g are the same fact said twice, not two facts. Left
    unconverted, a stale row here would reseed the wrong price on the
    article's next purchase through the suggestion cascade.
    """
    conn.execute(
        "UPDATE price SET price_per_base_unit = price_per_base_unit / ? WHERE article_id = ?",
        (factor, article_id),
    )


def latest_price(conn, article_id: int) -> float | None:
    # Rank 3 of the price cascade (spec 11): the last price seen anywhere.
    row = conn.execute(
        "SELECT price_per_base_unit FROM price WHERE article_id = ?"
        " ORDER BY observed_on DESC, id DESC LIMIT 1",
        (article_id,),
    ).fetchone()
    return None if row is None else float(row["price_per_base_unit"])


# --- batches ----------------------------------------------------------------

def insert_batch(conn, *, article_id: int, location_id: int, quantity: float,
                 entered_at: str, best_before: str | None = None,
                 price_per_base_unit: float | None = None,
                 nutrition: Mapping[str, float | None] | None = None) -> int:
    """Open a batch. `nutrition` freezes this batch's own values (lot 3): a pan
    of lasagne knows its calories, and the next pan made from the same recipe
    with different tomatoes will know its own.

    Filtered on NUTRITION_COLUMNS on the way in. The mapping is computed from a
    recipe, not typed into a form, but an unknown key here would reach an
    INSERT and could overwrite `remaining` — the filter is what makes the
    parameter safe to hand a computed dict.
    """
    values = {
        "article_id": article_id, "location_id": location_id,
        "remaining": quantity, "initial": quantity, "entered_at": entered_at,
        "best_before": best_before, "price_per_base_unit": price_per_base_unit,
    }
    if nutrition:
        values.update({
            column: nutrition[column]
            for column in NUTRITION_COLUMNS
            if column in nutrition
        })
    return _insert(conn, "batch", values)


def list_articles_for_product(conn, product_id: int) -> list[dict[str, Any]]:
    return _rows(conn.execute(
        "SELECT * FROM article WHERE product_id = ? ORDER BY id", (product_id,)))


def list_open_batches_for_product(conn, product_id: int) -> list[dict[str, Any]]:
    return _rows(conn.execute(
        f"""
        SELECT {BATCH_COLUMNS_SQL} FROM batch b JOIN article a ON a.id = b.article_id
        WHERE a.product_id = ? AND b.closed_at IS NULL ORDER BY b.id
        """,
        (product_id,)))


def list_batches_for_product(conn, product_id: int) -> list[dict[str, Any]]:
    """Open batches only, with the kcal rate resolved: the article's own rate,
    falling back to the product's reference_kcal when the article has none
    (spec 7.4 — generic/produce articles usually carry no rate of their own).
    """
    return _rows(conn.execute(
        f"SELECT {BATCH_COLUMNS_SQL}, {KCAL_RATE_SQL} AS kcal_per_base_unit,"
        f" {MACRO_RATE_SQL},"
        "       a.product_id, a.serving_quantity FROM batch b"
        " JOIN article a ON a.id = b.article_id"
        " JOIN product p ON p.id = a.product_id"
        " WHERE a.product_id = ? AND b.closed_at IS NULL",
        (product_id,),
    ))


def set_batch_remaining(conn, batch_id: int, remaining: float,
                        closed_at: str | None = None) -> None:
    conn.execute(
        "UPDATE batch SET remaining = ?, closed_at = ? WHERE id = ?",
        (remaining, closed_at, batch_id),
    )


def set_batch_opened(conn, batch_id: int, opened_at: str, best_before: str | None) -> None:
    conn.execute(
        "UPDATE batch SET opened_at = ?, best_before = ? WHERE id = ?",
        (opened_at, best_before, batch_id),
    )


def set_batch_location(conn, batch_id: int, location_id: int) -> None:
    conn.execute("UPDATE batch SET location_id = ? WHERE id = ?", (location_id, batch_id))


def _update_fields(conn, table: str, row_id: int, fields: dict[str, Any]) -> None:
    """Write only the columns given. An empty dict is a no-op, not an error.

    Column names are interpolated into the SQL: `fields` keys must never come
    from raw user input. Callers are expected to filter against a whitelist of
    columns before calling (see PRODUCT_FIELDS/ARTICLE_FIELDS above).
    """
    if not fields:
        return
    assignments = ", ".join(f"{column} = ?" for column in fields)
    conn.execute(f"UPDATE {table} SET {assignments} WHERE id = ?",
                 (*fields.values(), row_id))


def update_article_fields(conn, article_id: int, fields: dict[str, Any]) -> None:
    _update_fields(conn, "article", article_id, fields)


def update_product_fields(conn, product_id: int, fields: dict[str, Any]) -> None:
    _update_fields(conn, "product", product_id, fields)


# --- movements --------------------------------------------------------------

def insert_movement(conn, *, occurred_at: str, product_id: int, article_id: int,
                    quantity: float, reason: str, base_unit: str,
                    batch_id: int | None = None,
                    kcal: float | None = None, cost: float | None = None,
                    macros: Mapping[str, float | None] | None = None,
                    parts_total: int | None = None, parts_mine: int | None = None,
                    ref_type: str | None = None, ref_id: int | None = None,
                    corrects_id: int | None = None,
                    idempotency_key: str | None = None) -> int:
    values: dict[str, Any] = {
        "occurred_at": occurred_at, "product_id": product_id, "article_id": article_id,
        "batch_id": batch_id, "quantity": quantity, "reason": reason,
        "base_unit": base_unit, "kcal": kcal,
        "cost": cost, "ref_type": ref_type, "ref_id": ref_id,
        "parts_total": parts_total, "parts_mine": parts_mine,
        "corrects_id": corrects_id,
        "idempotency_key": idempotency_key,
    }
    # Always all eight columns, so an absent rate lands as an explicit NULL
    # rather than as a column this INSERT simply never mentioned.
    given = macros or {}
    values.update({column: given.get(column) for column in MACRO_COLUMNS})
    return _insert(conn, "movement", values)


def product_base_unit(conn, product_id: int) -> str:
    """The base unit a movement on this product must be recorded in."""
    row = conn.execute(
        "SELECT base_unit FROM product WHERE id = ?", (product_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"no product {product_id}")
    return row["base_unit"]


def movement_exists(conn, idempotency_key: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM movement WHERE idempotency_key = ? LIMIT 1", (idempotency_key,)
    ).fetchone()
    return row is not None


def get_movement(conn, movement_id: int) -> dict[str, Any] | None:
    """One journal row, whole.

    `m` as the alias, never `b`: the test that forbids selecting a whole
    batch row scans this package literally, and does not look at which
    table is behind the alias.
    """
    return _row(conn.execute(
        "SELECT m.* FROM movement m WHERE m.id = ?", (movement_id,)
    ).fetchone())


def movements_of_batch(conn, batch_id: int) -> list[dict[str, Any]]:
    """Every row written against one batch, in writing order.

    Ordered by `id` and not by `occurred_at`: a correction is booked on the
    day it is made, so it sorts BEFORE its target on the date but after it
    in the story.
    """
    return _rows(conn.execute(
        "SELECT m.* FROM movement m WHERE m.batch_id = ? ORDER BY m.id", (batch_id,)
    ))


def correction_of(conn, movement_id: int) -> dict[str, Any] | None:
    """The reversal that cancels this row, if one was written."""
    return _row(conn.execute(
        "SELECT m.* FROM movement m WHERE m.corrects_id = ?", (movement_id,)
    ).fetchone())


def list_movements(conn, since: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM movement"
    params: tuple[Any, ...] = ()
    if since is not None:
        sql += " WHERE occurred_at >= ?"
        params = (since,)
    return _rows(conn.execute(sql + " ORDER BY occurred_at, id", params))


# --- read models ------------------------------------------------------------

def stock_rows(conn) -> list[dict[str, Any]]:
    """One row per open batch, with the names needed for display.

    kcal_per_base_unit is resolved with the same fallback as
    list_batches_for_product (spec 7.4): this is what home_stock/batches/list
    hands the future panel, and without the fallback it would show no calories
    for exactly the generic and fresh-produce articles the fallback exists for.
    """
    return _rows(conn.execute(
        "SELECT b.id, b.remaining, b.best_before, b.entered_at, b.opened_at,"
        "       b.price_per_base_unit, p.id AS product_id, p.name AS product_name,"
        "       p.base_unit, p.min_quantity, a.id AS article_id, a.label AS article_label,"
        f"       {KCAL_RATE_SQL} AS kcal_per_base_unit,"
        "       l.id AS location_id, l.name AS location_name"
        " FROM batch b"
        " JOIN article a ON a.id = b.article_id"
        " JOIN product p ON p.id = a.product_id"
        " JOIN location l ON l.id = b.location_id"
        " WHERE b.closed_at IS NULL"
        " ORDER BY p.name, b.best_before"
    ))


# The personal share of a movement. The CAST is not decoration: parts_mine and
# parts_total are INTEGER columns, and SQLite's `1 / 4` on two integers is 0 —
# without it, one plate out of four would silently zero the whole day and the
# sensor would read 0 kcal with no error anywhere.
SHARE_SQL = "(CAST(COALESCE(parts_mine, 1) AS REAL) / COALESCE(parts_total, 1))"

# Only a consumption feeds the personal diary. Waste and expiry leave the
# stock and cost money, but nobody ate them (spec 7).
_PERSONAL_SUMS = ", ".join(
    [f"COALESCE(SUM(CASE WHEN reason = '{REASON_CONSUMPTION}'"
     f" THEN kcal * {SHARE_SQL} END), 0) AS kcal"]
    + [f"COALESCE(SUM(CASE WHEN reason = '{REASON_CONSUMPTION}'"
       f" THEN {column} * {SHARE_SQL} END), 0) AS {column}"
       for column in MACRO_COLUMNS]
)


def _reasons_sql(reasons) -> str:
    """An `IN (...)` literal for a handful of reason strings, quoted.

    A function, not a constant computed once at import: journal_entries,
    counted_movements and totals_between all call this AT QUERY TIME on
    const.CONSUME_REASONS (or a filtered view of it), so a reason added to
    that one tuple reaches all three queries by construction — there is no
    second, independently-typed copy of the set anywhere in this file left
    to forget. Baking the string once at import time would defeat the
    point: a test (or a future caller) patching CONSUME_REASONS would then
    silently keep seeing the stale set."""
    return "(" + ", ".join(f"'{r}'" for r in reasons) + ")"


def totals_between(conn, start: str | None = None,
                   end: str | None = None) -> dict[str, Any]:
    """Nutrients, money and coverage over a half-open range, or over everything.

    Money is NEVER divided by the parts: the pack cost what it cost, whether
    it was eaten alone or shared four ways (spec 7). Only the nine nutrients
    carry the personal share.
    """
    where, params = "", []
    if start is not None and end is not None:
        where = " WHERE occurred_at >= ? AND occurred_at < ?"
        params = [start, end]
    row = conn.execute(
        f"SELECT {_PERSONAL_SUMS},"
        f" COALESCE(SUM(CASE WHEN reason = '{REASON_CONSUMPTION}' THEN cost END), 0)"
        "   AS cost,"
        f" COALESCE(SUM(CASE WHEN reason IN "
        f'{_reasons_sql(r for r in CONSUME_REASONS if r != REASON_CONSUMPTION)}'
        " THEN cost END), 0)"
        "   AS waste_cost,"
        f" COALESCE(SUM(CASE WHEN reason = '{REASON_CONSUMPTION}' AND kcal IS NULL"
        "   THEN 1 END), 0) AS unvalued"
        f" FROM movement{where}",
        tuple(params),
    ).fetchone()
    return dict(row)


def journal_entries(conn, start: str, end: str) -> list[dict[str, Any]]:
    """What left the stock during a food day, oldest first."""
    return _rows(conn.execute(
        "SELECT m.id, m.occurred_at, m.quantity, m.reason, m.base_unit, m.kcal,"
        "       m.cost, m.parts_total, m.parts_mine, m.batch_id, m.corrects_id,"
        "       p.name AS product_name,"
        # La contrepassation d'une ligne, si elle existe. Le journal ne cache
        # JAMAIS une erreur : la ligne fautive reste visible, barrée, avec son
        # annulation juste en dessous — c'est ce qui permet de comprendre, six
        # mois plus tard, pourquoi une journée porte une valeur négative.
        "       (SELECT c.id FROM movement c WHERE c.corrects_id = m.id)"
        "         AS corrected_by"
        " FROM movement m JOIN product p ON p.id = m.product_id"
        f" WHERE m.reason IN {_reasons_sql(CONSUME_REASONS)}"
        "   AND m.occurred_at >= ? AND m.occurred_at < ?"
        " ORDER BY m.occurred_at, m.id",
        (start, end),
    ))


def counted_movements(conn, since: str) -> list[dict[str, Any]]:
    """The raw rows a series is bucketed from, in Python.

    Bucketing here rather than in SQL is not laziness: SQLite ships no
    timezone database, so a GROUP BY on a locally-shifted date would be wrong
    twice a year — precisely on the two days the food-day boundary is
    interesting. The volume makes this free: a household writes some fifteen
    movements a day, so twelve months is on the order of 5 000 rows.
    """
    return _rows(conn.execute(
        "SELECT occurred_at, reason, kcal, cost, parts_total, parts_mine,"
        f"       {', '.join(MACRO_COLUMNS)}"
        " FROM movement"
        f" WHERE reason IN {_reasons_sql(CONSUME_REASONS)}"
        "   AND occurred_at >= ? ORDER BY occurred_at, id",
        (since,),
    ))


def learned_portion(conn, product_id: int) -> float | None:
    """The median of the last three consumptions of this product, or nothing.

    Under three, there is no habit yet — and proposing a number drawn from a
    single meal would train the button to be wrong. Same discipline as lot 1's
    learned shelf life.
    """
    rows = conn.execute(
        "SELECT ABS(quantity) AS quantity FROM movement"
        f" WHERE product_id = ? AND reason = '{REASON_CONSUMPTION}'"
        " ORDER BY id DESC LIMIT 3",
        (product_id,),
    ).fetchall()
    if len(rows) < 3:
        return None
    return float(sorted(row["quantity"] for row in rows)[1])


def shortage_rows(conn) -> list[dict[str, Any]]:
    """Products below their minimum quantity, product table first.

    A left join from `product` (not `stock_rows`, which only sees open
    batches) so a product whose stock reached exactly zero — no batch row
    left at all — still appears when it has a threshold to compare against.
    """
    return _rows(conn.execute(
        "SELECT p.id AS product_id, p.name AS product_name, p.base_unit,"
        "       p.min_quantity, COALESCE(SUM(b.remaining), 0) AS quantity"
        " FROM product p"
        " LEFT JOIN article a ON a.product_id = p.id"
        " LEFT JOIN batch b ON b.article_id = a.id AND b.closed_at IS NULL"
        " WHERE p.min_quantity IS NOT NULL AND p.active = 1"
        " GROUP BY p.id"
        " HAVING quantity < p.min_quantity"
        " ORDER BY p.name"
    ))


def expiry_candidates(conn, limit: str) -> list[dict[str, Any]]:
    """Open batches with a date on or before `limit`, and what has already
    been announced about each one."""
    return _rows(conn.execute(
        "SELECT b.id, b.best_before, b.remaining, b.expiry_announced_stage,"
        "       p.name AS product_name, p.base_unit"
        " FROM batch b"
        " JOIN article a ON a.id = b.article_id"
        " JOIN product p ON p.id = a.product_id"
        " WHERE b.closed_at IS NULL AND b.best_before IS NOT NULL"
        "   AND b.best_before <= ?"
        " ORDER BY b.best_before, b.id",
        (limit,),
    ))


def mark_expiry_announced(conn, batch_id: int, stage: str) -> None:
    conn.execute("UPDATE batch SET expiry_announced_stage = ? WHERE id = ?",
                 (stage, batch_id))


# --- shopping sessions ------------------------------------------------------

def open_session(conn, *, started_at: str, store: str | None,
                 store_id: int | None = None) -> int:
    """Start a shopping session. The partial unique index refuses a second one.

    Both `store` (the free text, as the lot 1 sessions hold it) and
    `store_id` are written: the text is what was typed that day, the id is
    the shop it turned out to be.
    """
    return _insert(conn, "shopping_session",
                   {"started_at": started_at, "store": store, "state": "shopping",
                    "store_id": store_id})


def last_closed_session_at(conn) -> str | None:
    """L'instant où le dernier voyage a été clos, ou `None` s'il n'y en a
    jamais eu. C'est ce qui rend la règle 4 de la réconciliation décidable
    ligne par ligne plutôt que globalement."""
    row = conn.execute(
        "SELECT MAX(COALESCE(closed_at, started_at)) AS at FROM shopping_session"
        " WHERE state = 'done'").fetchone()
    return row["at"] if row else None


def current_session(conn) -> dict[str, Any] | None:
    """The session the panel should show: the open one, else the oldest one
    still waiting to be put away.

    Among several `to_store` sessions, the earliest started (not the most
    recently started, and not the most recently closed) is the one to surface:
    when two shops are queued unstored, the older one is the one whose
    chilled items have been sitting out of a fridge the longest, so it is the
    backlog to clear first.
    """
    return _row(conn.execute(
        """
        SELECT * FROM shopping_session
        WHERE state IN ('shopping', 'to_store')
        ORDER BY CASE state WHEN 'shopping' THEN 0 ELSE 1 END, started_at ASC
        LIMIT 1
        """
    ).fetchone())


def get_session(conn, session_id: int) -> dict[str, Any] | None:
    return _row(conn.execute(
        "SELECT * FROM shopping_session WHERE id = ?", (session_id,)).fetchone())


def set_session_state(conn, session_id: int, state: str, *,
                      closed_at: str | None = None) -> None:
    """Move the session to a new state.

    `closed_at` is written only when actually passed: it records when the
    session was checked out, and a timestamp like that must never be cleared
    as a side effect of an unrelated later state change (there is no way to
    recover it once gone — the journal keeps no other copy).
    """
    if closed_at is not None:
        conn.execute("UPDATE shopping_session SET state = ?, closed_at = ? WHERE id = ?",
                     (state, closed_at, session_id))
    else:
        conn.execute("UPDATE shopping_session SET state = ? WHERE id = ?",
                     (state, session_id))


def add_line(conn, *, session_id: int, article_id: int, quantity: float,
             unit_price: float | None, scanned_at: str,
             idempotency_key: str | None,
             price_source: str | None = None) -> int:
    return _insert(conn, "shopping_line", {
        "session_id": session_id, "article_id": article_id, "quantity": quantity,
        "unit_price": unit_price, "scanned_at": scanned_at,
        "idempotency_key": idempotency_key, "price_source": price_source,
    })


def update_line(conn, line_id: int, *, quantity: float | None = None,
                unit_price: float | None = None,
                price_source: str | None = None) -> None:
    """Only the fields actually passed are written: None means "leave it", which
    is not the same as "clear it"."""
    if quantity is not None:
        conn.execute("UPDATE shopping_line SET quantity = ? WHERE id = ?",
                     (quantity, line_id))
    if unit_price is not None:
        conn.execute("UPDATE shopping_line SET unit_price = ? WHERE id = ?",
                     (unit_price, line_id))
    if price_source is not None:
        conn.execute("UPDATE shopping_line SET price_source = ? WHERE id = ?",
                     (price_source, line_id))


def remove_line(conn, line_id: int) -> None:
    """Drop a line. Safe because nothing entered the stock yet — a stored line
    is refused by the caller, not here."""
    conn.execute("DELETE FROM shopping_line WHERE id = ?", (line_id,))


def line_by_key(conn, idempotency_key: str) -> dict[str, Any] | None:
    return _row(conn.execute(
        "SELECT * FROM shopping_line WHERE idempotency_key = ?",
        (idempotency_key,)).fetchone())


def get_line(conn, line_id: int) -> dict[str, Any] | None:
    """The raw shopping_line row, as the database holds it — no join.

    Used to hand a caller back exactly what it just wrote, whether or not it
    supplied an idempotency key (line_by_key only works with one).
    """
    return _row(conn.execute(
        "SELECT * FROM shopping_line WHERE id = ?", (line_id,)).fetchone())


def count_pending_lines_for_product(conn, product_id: int) -> int:
    """Shopping lines not yet turned into a batch (`stored_at IS NULL`), for
    any article of this product.

    Used by StockManager.convert_product_unit to refuse converting while one
    is queued: `shopping_line.quantity` is stored in the product's base unit
    as a promise about a quantity, not yet a batch — changing what the number
    means underneath it would lose stock with no trace the moment the line is
    put away.

    Lines of a CLOSED session (`state = 'done'`) do not count. Closing a
    session is how an abandoned trip is given up: whatever was never put
    away then never will be. Counted, such a line blocked every future
    conversion of its product forever — and no screen reaches it any more to
    clear it by hand, since the panel only ever shows the current session.
    """
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM shopping_line l
        JOIN article a ON a.id = l.article_id
        JOIN shopping_session s ON s.id = l.session_id
        WHERE a.product_id = ? AND l.stored_at IS NULL AND s.state <> 'done'
        """,
        (product_id,),
    ).fetchone()
    return int(row["n"])


# `sa.position` d'abord : l'ordre appris DE CE MAGASIN. `ai.position`
# ensuite — on sait où est le rayon en général, on ne sait juste pas où il
# est ici. 999 enfin, pour un produit sans rayon du tout.
_LINE_SELECT_SQL = """
SELECT l.*, p.id AS product_id, p.name AS product_name, p.base_unit,
       p.default_location_id, p.default_shelf_life_days, p.days_after_opening,
       a.label AS article_label, a.brand, a.image, a.net_quantity,
       ai.name AS aisle_name,
       COALESCE(sa.position, ai.position, 999) AS aisle_position
FROM shopping_line l
JOIN article a ON a.id = l.article_id
JOIN product p ON p.id = a.product_id
LEFT JOIN aisle ai ON ai.id = p.aisle_id
LEFT JOIN store_aisle sa ON sa.aisle_id = ai.id AND sa.store_id = ?
WHERE l.session_id = ?
"""


def list_lines(conn, session_id: int, *, pending_only: bool = False) -> list[dict[str, Any]]:
    """The cart, in walking order. Scan order is never what a shopper wants.

    The learned order of THIS shop only applies once the shop is reliable
    (three closed sessions, § 11.3). Below that, `store_aisle` is filled and
    visible in the settings, but the display keeps `aisle.position`: one
    observation would turn an exceptional detour into the law.
    """
    store_id = _reliable_store_of(conn, session_id)
    sql = _LINE_SELECT_SQL
    if pending_only:
        sql += " AND l.stored_at IS NULL"
    sql += " ORDER BY aisle_position, p.name, l.id"
    return _rows(conn.execute(sql, (store_id, session_id)))


def _reliable_store_of(conn, session_id: int) -> int | None:
    """The session's shop, but only once it has taught us enough."""
    row = conn.execute(
        "SELECT store_id FROM shopping_session WHERE id = ?", (session_id,)
    ).fetchone()
    store_id = row["store_id"] if row else None
    if store_id is None:
        return None
    closed = conn.execute(
        "SELECT COUNT(*) AS n FROM shopping_session"
        " WHERE store_id = ? AND state = 'done'", (store_id,)).fetchone()["n"]
    return store_id if is_reliable(int(closed)) else None


def mark_line_stored(conn, line_id: int, *, batch_id: int, stored_at: str) -> None:
    conn.execute("UPDATE shopping_line SET batch_id = ?, stored_at = ? WHERE id = ?",
                 (batch_id, stored_at, line_id))


def session_totals(conn, session_id: int) -> dict[str, Any]:
    """Ce que le chariot vaut, et quelle part de ce chiffre est une supposition.

    Trois catégories, jamais une moyenne (§ 9) : CONSTATÉ (un humain a tapé
    ou corrigé le prix devant l'étiquette, ou le ticket l'a dit), ESTIMÉ (une
    suggestion acceptée sans y toucher) et INCONNU (aucun prix — compté zéro
    dans le total, et SIGNALÉ). `COALESCE` comptait déjà l'inconnu à zéro en
    silence ; l'écart inexpliqué avec le ticket détruit la confiance dans
    tout le reste.
    """
    observed = _reasons_sql(OBSERVED_PRICE_SOURCES)
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS lines,
               SUM(CASE WHEN stored_at IS NULL THEN 1 ELSE 0 END) AS pending,
               COALESCE(SUM(quantity * COALESCE(unit_price, 0)), 0) AS total,
               COALESCE(SUM(CASE WHEN unit_price IS NOT NULL
                                  AND price_source IN {observed}
                            THEN quantity * unit_price END), 0) AS observed,
               COALESCE(SUM(CASE WHEN unit_price IS NOT NULL
                                  AND (price_source IS NULL
                                       OR price_source NOT IN {observed})
                            THEN quantity * unit_price END), 0) AS estimated,
               COALESCE(SUM(CASE WHEN unit_price IS NULL THEN 1 END), 0)
                 AS unpriced_lines,
               COALESCE(SUM(CASE WHEN NOT EXISTS (
                   SELECT 1 FROM shopping_list_item sl WHERE sl.line_id = l.id
               ) THEN 1 END), 0) AS off_list_lines
        FROM shopping_line l WHERE l.session_id = ?
        """,
        (session_id,),
    ).fetchone()
    progress = conn.execute(
        "SELECT COUNT(*) AS total,"
        "       COALESCE(SUM(CASE WHEN sl.checked_at IS NOT NULL THEN 1 END), 0)"
        "         AS checked"
        " FROM shopping_list_item sl WHERE sl.removed_at IS NULL"
    ).fetchone()
    return {"lines": row["lines"], "pending": row["pending"] or 0,
            "total": round(row["total"], 4),
            "observed": round(row["observed"], 4),
            "estimated": round(row["estimated"], 4),
            "unpriced_lines": int(row["unpriced_lines"]),
            "off_list_lines": int(row["off_list_lines"]),
            "checked_items": int(progress["checked"]),
            "list_items": int(progress["total"])}


def latest_price_in_store(conn, article_id: int, store: str) -> float | None:
    """The last price OBSERVED in this shop — amendment A3.

    A suggestion accepted without being touched (`open_prices`, `last_known`,
    `store`) is not evidence of anything: counting it here would put rank 1
    of the cascade at the mercy of its own guesses, and by the second trip
    the guess would have overwritten the shelf label.
    """
    row = conn.execute(
        f"""
        SELECT price_per_base_unit FROM price
        WHERE article_id = ? AND store = ?
          AND source IN {_reasons_sql(OBSERVED_PRICE_SOURCES)}
        ORDER BY observed_on DESC, id DESC LIMIT 1
        """,
        (article_id, store),
    ).fetchone()
    return row["price_per_base_unit"] if row else None


def recent_shelf_lives(conn, product_id: int, limit: int = 3) -> list[int]:
    """Days between entry and best-before on this product's latest batches.

    Feeds the default the panel offers as a one-tap button. Batches with no
    best-before say nothing about shelf life and are left out.
    """
    rows = conn.execute(
        """
        SELECT CAST(julianday(b.best_before) - julianday(date(b.entered_at)) AS INTEGER) AS days
        FROM batch b JOIN article a ON a.id = b.article_id
        WHERE a.product_id = ? AND b.best_before IS NOT NULL
        ORDER BY b.entered_at DESC, b.id DESC LIMIT ?
        """,
        (product_id, limit),
    ).fetchall()
    return [row["days"] for row in rows if row["days"] is not None and row["days"] >= 0]


# --- lot 4 : le magasin, promu de chaîne libre à ligne (amendement A4) -----
#
# Alias `st`, jamais `b` : un test scanne littéralement ce paquet à la
# recherche d'une ligne de batch entière, sans regarder quelle table est
# derrière l'alias.

def list_stores(conn, *, active_only: bool = True) -> list[dict[str, Any]]:
    """Shops the panel shows as chips, with what is known about each.

    `observed_sessions` counts only `done` trips: a trip still under way
    has not taught anything about this shop yet, and counting it would make
    a brand-new shop look experienced for the length of one visit.
    """
    where = " WHERE st.active = 1" if active_only else ""
    return _rows(conn.execute(
        "SELECT st.id, st.name, st.position, st.active,"
        "       COUNT(s.id) AS observed_sessions,"
        "       MAX(s.started_at) AS last_seen"
        " FROM store st"
        " LEFT JOIN shopping_session s"
        "   ON s.store_id = st.id AND s.state = 'done'"
        f"{where}"
        " GROUP BY st.id"
        " ORDER BY st.position, last_seen DESC, st.name"
    ))


def get_store(conn, store_id: int) -> dict[str, Any] | None:
    return _row(conn.execute(
        "SELECT st.* FROM store st WHERE st.id = ?", (store_id,)).fetchone())


def find_store_by_name(conn, name: str) -> dict[str, Any] | None:
    """Exact equality, case included.

    Deciding that « Leclerc » and « leclerc » are the same shop is a guess,
    and a guess made here would one day merge two shops that really are
    different, with no trace. The panel merges by hand instead (§ 11.1).
    """
    return _row(conn.execute(
        "SELECT st.* FROM store st WHERE st.name = ?", (name,)).fetchone())


def upsert_store(conn, *, name: str, store_id: int | None = None,
                 position: int | None = None, active: int | None = None) -> int:
    """Create the shop or update the one named — returns its id."""
    if store_id is None:
        existing = find_store_by_name(conn, name)
        store_id = existing["id"] if existing else None
    if store_id is None:
        return _insert(conn, "store", {
            "name": name,
            "position": 0 if position is None else position,
            "active": 1 if active is None else active,
        })
    fields: dict[str, Any] = {"name": name}
    if position is not None:
        fields["position"] = position
    if active is not None:
        fields["active"] = active
    _update_fields(conn, "store", store_id, fields)
    return int(store_id)


def merge_stores(conn, *, keep_id: int, merge_id: int) -> dict[str, Any]:
    """Fold one shop into another. `price.store` is NEVER rewritten.

    `price` is a log of observations: each row says what was seen the day it
    was seen. Rewriting the text to make it tidy is exactly what lot 0
    refuses to the movement journal.
    """
    conn.execute("UPDATE shopping_session SET store_id = ? WHERE store_id = ?",
                 (keep_id, merge_id))
    conn.execute("UPDATE price SET store_id = ? WHERE store_id = ?",
                 (keep_id, merge_id))
    # The surviving shop's own order wins: (store_id, aisle_id) is the primary
    # key, so only one may remain, and the one the owner has been walking is
    # the one that is right.
    conn.execute(
        "DELETE FROM store_aisle WHERE store_id = ? AND aisle_id IN"
        " (SELECT aisle_id FROM store_aisle WHERE store_id = ?)",
        (merge_id, keep_id))
    conn.execute("UPDATE store_aisle SET store_id = ? WHERE store_id = ?",
                 (keep_id, merge_id))
    conn.execute("DELETE FROM store WHERE id = ?", (merge_id,))
    return {"keep_id": keep_id, "merged_id": merge_id}


def set_store_aisle(conn, *, store_id: int, aisle_id: int, position: int,
                    source: str, mean_rank: float | None = None,
                    observed_sessions: int = 0,
                    updated_at: str | None = None) -> None:
    """One aisle's place in one shop's walking order."""
    conn.execute(
        "INSERT INTO store_aisle (store_id, aisle_id, position, source,"
        " mean_rank, observed_sessions, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT (store_id, aisle_id) DO UPDATE SET"
        "   position = excluded.position, source = excluded.source,"
        "   mean_rank = excluded.mean_rank,"
        "   observed_sessions = excluded.observed_sessions,"
        "   updated_at = excluded.updated_at",
        (store_id, aisle_id, position, source, mean_rank, observed_sessions,
         updated_at))


def store_aisles(conn, store_id: int) -> list[dict[str, Any]]:
    """This shop's walking order, in it."""
    return _rows(conn.execute(
        "SELECT sa.* FROM store_aisle sa WHERE sa.store_id = ? ORDER BY sa.position",
        (store_id,)))


def store_route(conn, store_id: int) -> list[dict[str, Any]]:
    """The walking order with the aisle names, for the settings screen."""
    return _rows(conn.execute(
        "SELECT sa.*, ai.name AS aisle_name, ai.position AS default_position"
        " FROM store_aisle sa JOIN aisle ai ON ai.id = sa.aisle_id"
        " WHERE sa.store_id = ? ORDER BY sa.position", (store_id,)))


def recent_session_aisle_sequences(conn, store_id: int,
                                   limit: int = ROUTE_SESSION_WINDOW
                                   ) -> list[list[int]]:
    """Les rayons parcourus lors des dernières sessions CLOSES de ce magasin.

    Triées par `scanned_at`, jamais par `id` : c'est l'ordre du PARCOURS
    qu'on apprend, et deux lignes peuvent être écrites dans un ordre que le
    chariot n'a pas suivi (rejeu de la file hors ligne).

    Seules les sessions closes : on n'apprend pas d'un parcours en cours.
    """
    sessions = _rows(conn.execute(
        "SELECT s.id FROM shopping_session s"
        " WHERE s.store_id = ? AND s.state = 'done'"
        " ORDER BY COALESCE(s.closed_at, s.started_at) DESC, s.id DESC"
        " LIMIT ?", (store_id, limit)))
    sequences: list[list[int]] = []
    for session in sessions:
        rows = _rows(conn.execute(
            "SELECT p.aisle_id FROM shopping_line l"
            " JOIN article a ON a.id = l.article_id"
            " JOIN product p ON p.id = a.product_id"
            " WHERE l.session_id = ? AND p.aisle_id IS NOT NULL"
            " ORDER BY l.scanned_at, l.id", (session["id"],)))
        if rows:
            sequences.append([int(row["aisle_id"]) for row in rows])
    return sequences


def save_store_route(conn, store_id: int, entries, *, updated_at: str) -> None:
    """Écrit l'ordre appris, et n'écrase JAMAIS une ligne `manual`.

    Le rang moyen et le nombre de sessions sont écrits même sur une ligne
    épinglée : on doit VOIR que l'apprentissage la contredit. Seule
    `position` reste celle qu'on a choisie.
    """
    pinned = {row["aisle_id"] for row in store_aisles(conn, store_id)
              if row["source"] == "manual"}
    for entry in entries:
        if entry.aisle_id in pinned:
            conn.execute(
                "UPDATE store_aisle SET mean_rank = ?, observed_sessions = ?,"
                " updated_at = ? WHERE store_id = ? AND aisle_id = ?",
                (entry.mean_rank, entry.observed_sessions, updated_at,
                 store_id, entry.aisle_id))
            continue
        set_store_aisle(conn, store_id=store_id, aisle_id=entry.aisle_id,
                        position=entry.position, source=entry.source,
                        mean_rank=entry.mean_rank,
                        observed_sessions=entry.observed_sessions,
                        updated_at=updated_at)


def pin_store_aisles(conn, store_id: int, aisle_ids: Sequence[int]) -> None:
    """Le propriétaire a rangé ces rayons dans cet ordre : ils y restent."""
    for position, aisle_id in enumerate(aisle_ids, start=1):
        conn.execute(
            "INSERT INTO store_aisle (store_id, aisle_id, position, source)"
            " VALUES (?, ?, ?, 'manual')"
            " ON CONFLICT (store_id, aisle_id) DO UPDATE SET"
            "   position = excluded.position, source = 'manual'",
            (store_id, aisle_id, position))


def unpin_store_aisle(conn, store_id: int, aisle_id: int) -> None:
    """« Reprendre l'apprentissage » : la ligne redevient automatique."""
    conn.execute(
        "UPDATE store_aisle SET source = 'learned'"
        " WHERE store_id = ? AND aisle_id = ?", (store_id, aisle_id))


# =============================================================================
# Lot 3 — recipes, steps, ingredients, measures, aliases, slots and meals.
#
# `conn` is positional everywhere and no transaction is opened here: the caller
# owns it. That is what lets `application` compose several of these into ONE
# `db.write()` — `Database._lock` is not reentrant, so a repository that opened
# its own transaction would deadlock the process the day it was called from
# inside another one.
# =============================================================================

# Column whitelists, same pattern as PRODUCT_FIELDS/ARTICLE_FIELDS above: a
# column name interpolated into SQL is never taken from a raw payload.
RECIPE_FIELDS: Final = (
    "name", "servings", "total_minutes", "utensils", "summary", "image_url",
    "source", "source_ref", "source_url", "language", "adapted_at",
    "needs_review", "leftover_product_id", "leftover_shelf_life_days", "active",
    "external_ref",
)
INGREDIENT_FIELDS: Final = (
    "product_id", "amount", "packaging_id", "measure_id", "raw_text",
    "group_name", "optional", "match_state", "match_score", "external_ref",
)
MEAL_FIELDS: Final = (
    "day", "slot_key", "position", "recipe_id", "product_id", "amount",
    "packaging_id", "note", "servings", "portions_eaten", "parts_total",
    "parts_mine", "state", "validated_at", "skipped_ingredient_ids",
    "external_ref",
)


def _filtered(fields: Mapping[str, Any], allowed: Sequence[str]) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if key in allowed}


# --- recipes ----------------------------------------------------------------

def insert_recipe(conn, *, name: str, source: str, created_at: str, **fields) -> int:
    values = {"name": name, "source": source, "created_at": created_at}
    values.update(_filtered(fields, RECIPE_FIELDS))
    return _insert(conn, "recipe", values)


def get_recipe(conn, recipe_id: int) -> dict[str, Any] | None:
    return _row(conn.execute(
        "SELECT * FROM recipe WHERE id = ?", (recipe_id,)).fetchone())


def find_recipe_by_source(conn, source: str, source_ref: str) -> dict[str, Any] | None:
    """The lookup that makes an import replayable: importing the same source
    reference twice must find the first one rather than make a second."""
    return _row(conn.execute(
        "SELECT * FROM recipe WHERE source = ? AND source_ref = ?",
        (source, source_ref)).fetchone())


def list_recipes(conn, *, search: str | None = None,
                 only_reviewable: bool = False) -> list[dict[str, Any]]:
    """Active recipes, each with the number of ingredients still unmatched.

    The count is computed here rather than in the panel: the "n unmatched"
    badge and the screen that fixes them must agree, and they only can if one
    query is the source of both.

    `search` is matched on the NORMALISED name (accent-, case- and
    punctuation-free), using the same `normalise` the ingredient matching
    uses. SQLite's LIKE only folds ASCII case, so "bœuf" would not find
    "Boeuf" and "à l'ancienne" would not find "ancienne". Recipes number in
    the dozens, so folding in Python costs nothing and keeps one definition
    of "the same word".
    """
    rows = _rows(conn.execute(
        """
        SELECT r.*, (
            SELECT COUNT(*) FROM recipe_ingredient ri
            WHERE ri.recipe_id = r.id AND ri.match_state = 'unmatched'
        ) AS unmatched_count
        FROM recipe r
        WHERE r.active = 1
        ORDER BY r.name
        """
    ))
    if only_reviewable:
        rows = [row for row in rows if row["needs_review"]]
    if search:
        needle = normalise(search)
        rows = [row for row in rows if needle in normalise(row["name"])]
    return rows


def update_recipe_fields(conn, recipe_id: int, fields: Mapping[str, Any]) -> None:
    _update_fields(conn, "recipe", recipe_id, _filtered(fields, RECIPE_FIELDS))


def delete_recipe(conn, recipe_id: int) -> None:
    """Remove the recipe and everything that only exists to describe it.

    Bullets before steps before the recipe: SQLite does not enforce the
    foreign keys here by default, but deleting in dependency order means the
    same call is correct whether or not `PRAGMA foreign_keys` is on.
    """
    conn.execute(
        "DELETE FROM recipe_instruction WHERE step_id IN"
        " (SELECT id FROM recipe_step WHERE recipe_id = ?)", (recipe_id,))
    conn.execute("DELETE FROM recipe_step WHERE recipe_id = ?", (recipe_id,))
    conn.execute("DELETE FROM recipe_ingredient WHERE recipe_id = ?", (recipe_id,))
    # Meals that merely PLANNED this recipe go with it. They are intentions,
    # not history: nothing was ever written to the journal for them, and a
    # planned meal pointing at a deleted recipe would be an orphan the
    # calendar could not render. A `done` meal is another matter entirely and
    # is refused a layer above, before we ever get here.
    conn.execute("DELETE FROM meal WHERE recipe_id = ? AND state != 'done'",
                 (recipe_id,))
    conn.execute("DELETE FROM recipe WHERE id = ?", (recipe_id,))


def recipe_is_referenced_by_a_done_meal(conn, recipe_id: int) -> bool:
    """Whether a validated meal points at this recipe.

    The refusal to delete lives above (spec §17); the repository only tells
    the truth. A `done` meal is history — deleting what it names would leave
    the journal pointing at nothing.
    """
    return conn.execute(
        "SELECT 1 FROM meal WHERE recipe_id = ? AND state = 'done' LIMIT 1",
        (recipe_id,)).fetchone() is not None


# --- steps and bullets ------------------------------------------------------

def insert_step(conn, *, recipe_id: int, position: int, title: str | None = None,
                image_url: str | None = None) -> int:
    return _insert(conn, "recipe_step", {
        "recipe_id": recipe_id, "position": position,
        "title": title, "image_url": image_url,
    })


def insert_instruction(conn, *, step_id: int, position: int, text: str,
                       timer_label: str | None = None,
                       timer_seconds: int | None = None) -> int:
    return _insert(conn, "recipe_instruction", {
        "step_id": step_id, "position": position, "text": text,
        "timer_label": timer_label, "timer_seconds": timer_seconds,
    })


def list_steps(conn, recipe_id: int) -> list[dict[str, Any]]:
    """The cooking view's pages, each with its bullets already nested.

    One query per level rather than a join flattened back out in Python: a
    step with no bullet must still appear as a page, which an inner join
    would drop and an outer join would make the caller re-group.
    """
    steps = _rows(conn.execute(
        "SELECT * FROM recipe_step WHERE recipe_id = ? ORDER BY position",
        (recipe_id,)))
    if not steps:
        return []
    bullets = _rows(conn.execute(
        "SELECT * FROM recipe_instruction WHERE step_id IN"
        f" ({', '.join('?' for _ in steps)}) ORDER BY step_id, position",
        tuple(step["id"] for step in steps)))
    by_step: dict[int, list[dict[str, Any]]] = {step["id"]: [] for step in steps}
    for bullet in bullets:
        by_step[bullet["step_id"]].append(bullet)
    for step in steps:
        step["instructions"] = by_step[step["id"]]
    return steps


# --- ingredients, measures, aliases -----------------------------------------

def insert_ingredient(conn, *, recipe_id: int, position: int, raw_text: str,
                      **fields) -> int:
    values = {"recipe_id": recipe_id, "position": position, "raw_text": raw_text}
    values.update(_filtered(fields, INGREDIENT_FIELDS))
    return _insert(conn, "recipe_ingredient", values)


def list_ingredients(conn, recipe_id: int) -> list[dict[str, Any]]:
    """Every column `domain.recipes.IngredientLine` needs, joined once.

    LEFT JOIN throughout: an unmatched line has no product, and it is exactly
    the line the matching screen exists to fix — an inner join would hide the
    work from the person meant to do it.

    Building the IngredientLine stays in `application`, but the query is
    written once here so no two screens can read a measure differently.
    """
    return _rows(conn.execute(
        """
        SELECT ri.*,
               p.name AS product_name, p.base_unit AS product_base_unit,
               pk.name AS packaging_name, pk.base_quantity AS packaging_base_quantity,
               cm.id AS measure_id_joined, cm.name AS measure_name,
               cm.base_unit AS measure_base_unit,
               cm.base_quantity AS measure_base_quantity
        FROM recipe_ingredient ri
        LEFT JOIN product p ON p.id = ri.product_id
        LEFT JOIN packaging pk ON pk.id = ri.packaging_id
        LEFT JOIN culinary_measure cm ON cm.id = ri.measure_id
        WHERE ri.recipe_id = ?
        ORDER BY ri.position
        """,
        (recipe_id,)))


def update_ingredient_match(conn, ingredient_id: int, *, product_id: int | None,
                            state: str, score: float | None) -> None:
    conn.execute(
        "UPDATE recipe_ingredient SET product_id = ?, match_state = ?,"
        " match_score = ? WHERE id = ?",
        (product_id, state, score, ingredient_id))


def list_measures(conn) -> list[dict[str, Any]]:
    return _rows(conn.execute("SELECT * FROM culinary_measure ORDER BY id"))


def find_alias(conn, normalised: str) -> dict[str, Any] | None:
    return _row(conn.execute(
        "SELECT * FROM ingredient_alias WHERE normalised = ?",
        (normalised,)).fetchone())


def upsert_alias(conn, *, normalised: str, product_id: int, created_at: str) -> None:
    """Record what a human decided once and for all.

    Re-teaching the same alias must not pile up rows, and re-teaching it
    towards a DIFFERENT product must move it: the last human decision is the
    one that counts, otherwise a correction would be silently ignored.
    """
    conn.execute(
        "INSERT INTO ingredient_alias (normalised, product_id, created_at)"
        " VALUES (?, ?, ?)"
        " ON CONFLICT(normalised) DO UPDATE SET product_id = excluded.product_id,"
        " created_at = excluded.created_at",
        (normalised, product_id, created_at))


# --- slots and meals --------------------------------------------------------

def list_slots(conn) -> list[dict[str, Any]]:
    return _rows(conn.execute("SELECT * FROM meal_slot ORDER BY position"))


def get_slot(conn, key: str) -> dict[str, Any] | None:
    return _row(conn.execute(
        "SELECT * FROM meal_slot WHERE key = ?", (key,)).fetchone())


def insert_meal(conn, *, uid: str, day: str, slot_key: str, created_at: str,
                **fields) -> int:
    values = {"uid": uid, "day": day, "slot_key": slot_key, "created_at": created_at}
    values.update(_filtered(fields, MEAL_FIELDS))
    return _insert(conn, "meal", values)


def get_meal(conn, meal_id: int) -> dict[str, Any] | None:
    return _row(conn.execute("SELECT * FROM meal WHERE id = ?", (meal_id,)).fetchone())


def get_meal_by_uid(conn, uid: str) -> dict[str, Any] | None:
    return _row(conn.execute("SELECT * FROM meal WHERE uid = ?", (uid,)).fetchone())


# What a meal row carries once joined with what names it. Written once so the
# calendar, the planning screen and the sensors cannot disagree about a meal.
_MEAL_SELECT: Final = """
    SELECT m.*, s.position AS slot_position, s.default_time AS slot_default_time,
           s.duration_minutes AS slot_duration_minutes,
           r.name AS recipe_name, r.servings AS recipe_servings,
           r.image_url AS recipe_image_url, r.total_minutes AS recipe_total_minutes,
           p.name AS product_name, p.base_unit AS product_base_unit
    FROM meal m
    JOIN meal_slot s ON s.key = m.slot_key
    LEFT JOIN recipe r ON r.id = m.recipe_id
    LEFT JOIN product p ON p.id = m.product_id
"""


def list_meals(conn, start: str, end: str) -> list[dict[str, Any]]:
    """Meals over a range of FOOD days, both bounds included.

    Ordered by day, then by the slot's own position, then by the meal's
    position within the slot — so the planning always reads breakfast, lunch,
    dinner, snack, and a meal added to a slot after the fact lands after the
    ones already there rather than ahead of them.
    """
    return _rows(conn.execute(
        _MEAL_SELECT + " WHERE m.day BETWEEN ? AND ?"
        " ORDER BY m.day, s.position, m.position, m.id",
        (start, end)))


def next_meal(conn, day: str) -> dict[str, Any] | None:
    """The first meal still to come on or after `day`.

    `done` and `skipped` are behind us: a meal already eaten is not the next
    one, and one deliberately skipped never will be.
    """
    return _row(conn.execute(
        _MEAL_SELECT + " WHERE m.day >= ? AND m.state = 'planned'"
        " ORDER BY m.day, s.position, m.position, m.id LIMIT 1",
        (day,)).fetchone())


def update_meal_fields(conn, meal_id: int, fields: Mapping[str, Any]) -> None:
    _update_fields(conn, "meal", meal_id, _filtered(fields, MEAL_FIELDS))


def delete_meal(conn, meal_id: int) -> None:
    conn.execute("DELETE FROM meal WHERE id = ?", (meal_id,))


def next_meal_position(conn, day: str, slot_key: str) -> int:
    """The position a meal added to this slot should take: after the last one."""
    row = conn.execute(
        "SELECT MAX(position) AS last FROM meal WHERE day = ? AND slot_key = ?",
        (day, slot_key)).fetchone()
    return 0 if row["last"] is None else int(row["last"]) + 1


# The base-unit factor of an ingredient line, resolved in the same order as
# `domain.recipes.base_amount`: the product's own packaging first, then the
# culinary measure but ONLY when its dimension matches the product's base
# unit, then the number as written. A measure whose dimension does not match
# resolves to NULL and the line drops out below — never to 1.0, which would
# turn "2 tbsp of yoghurt" into "2 yoghurts". No divisor is ever guessed.
_INGREDIENT_FACTOR_SQL: Final = """
    CASE
        WHEN ri.packaging_id IS NOT NULL THEN pk.base_quantity
        WHEN ri.measure_id IS NOT NULL THEN
            CASE WHEN cm.base_unit = p.base_unit THEN cm.base_quantity END
        ELSE 1.0
    END
"""


def missing_products_between(conn, start: str, end: str) -> list[dict[str, Any]]:
    """Products the planned meals need more of than the stock holds.

    Only lines that name a product and are actually going to be decremented
    count: `unmatched` lines are not claimed, because asking someone to buy
    what we failed to identify would be a false shopping list — and the real
    list is lot 4's job. `ignored` lines are the ones a human already ruled
    out. `done` and `skipped` meals are behind us.

    Needs are scaled by each meal's own servings against its recipe's, so
    cooking a two-person recipe for four asks for twice as much.
    """
    return _rows(conn.execute(
        f"""
        SELECT product_id, product_name, base_unit, needed, available
        FROM (
            SELECT p.id AS product_id, p.name AS product_name, p.base_unit AS base_unit,
                   SUM(ri.amount * {_INGREDIENT_FACTOR_SQL}
                       * (m.servings / r.servings)) AS needed,
                   COALESCE((
                       SELECT SUM(b.remaining) FROM batch b
                       JOIN article a ON a.id = b.article_id
                       WHERE a.product_id = p.id AND b.closed_at IS NULL
                   ), 0.0) AS available
            FROM meal m
            JOIN recipe r ON r.id = m.recipe_id
            JOIN recipe_ingredient ri ON ri.recipe_id = r.id
            JOIN product p ON p.id = ri.product_id
            LEFT JOIN packaging pk ON pk.id = ri.packaging_id
            LEFT JOIN culinary_measure cm ON cm.id = ri.measure_id
            WHERE m.day BETWEEN ? AND ?
              AND m.state = 'planned'
              AND ri.match_state IN ('auto', 'confirmed')
              AND ri.amount IS NOT NULL
              AND {_INGREDIENT_FACTOR_SQL} IS NOT NULL
            GROUP BY p.id
        )
        WHERE needed > available
        ORDER BY product_name
        """,
        (start, end)))
# --- lot 5 : piles, équipements, consommables --------------------------------

BATTERY_FIELDS = (
    "label", "entity_registry_id", "device_id", "equipment_id", "kind",
    "product_id", "cell_count", "tracked", "exclusion_reason", "low_percent",
    "keep_percent", "last_percent", "last_reading_at", "installed_on",
    "expected_life_days", "note", "external_ref", "active",
)
EQUIPMENT_FIELDS = (
    "name", "device_id", "location_id", "brand", "model", "serial",
    "purchased_on", "purchase_price", "warranty_months", "receipt_media_id",
    "manual_url", "manual_media_id", "note", "external_ref", "active",
)
CONSUMABLE_FIELDS = (
    "label", "entity_registry_id", "low_value", "keep_value", "unit",
    "expected_life_days", "installed_on",
)


def insert_battery(conn, *, label: str, kind: str, **fields: Any) -> int:
    values: dict[str, Any] = {"label": label, "kind": kind}
    values.update({k: v for k, v in fields.items()
                   if k in BATTERY_FIELDS and k not in ("label", "kind")})
    return _insert(conn, "battery", values)


def update_battery_fields(conn, battery_id: int, fields: dict[str, Any]) -> None:
    _update_fields(conn, "battery", battery_id, fields)


def get_battery(conn, battery_id: int) -> dict[str, Any] | None:
    return _row(conn.execute(
        "SELECT * FROM battery WHERE id = ?", (battery_id,)).fetchone())


def battery_by_anchor(conn, entity_registry_id: str) -> dict[str, Any] | None:
    return _row(conn.execute(
        "SELECT * FROM battery WHERE entity_registry_id = ?",
        (entity_registry_id,)).fetchone())


def list_batteries(conn, *, active_only: bool = True) -> list[dict[str, Any]]:
    """Every declared place, with the spare's name and the equipment's.

    The joins are LEFT: a battery with no spare product and no equipment is
    the ordinary case (a remote nobody has documented yet), not an anomaly.
    """
    # `bat`, jamais `b` : depuis m004 (lot 3), `SELECT b.*` est interdit dans
    # tout le composant parce que `b` y alias `batch`, dont les colonnes de
    # nutriments écraseraient silencieusement les taux résolus. La table
    # `battery` n'a rien à voir, mais un garde-fou textuel ne fait pas la
    # différence — et c'est ce qui le rend fiable.
    where = " WHERE bat.active = 1" if active_only else ""
    return _rows(conn.execute(
        "SELECT bat.*, p.name AS spare_label, e.name AS equipment_name"
        " FROM battery bat"
        " LEFT JOIN product p ON p.id = bat.product_id"
        " LEFT JOIN equipment e ON e.id = bat.equipment_id"
        f"{where}"
        " ORDER BY bat.label, bat.id"
    ))


def set_battery_reading(conn, battery_id: int, *, percent: float, at: str) -> None:
    """The last NUMERIC reading, and when the device said it.

    Both columns move together on purpose: `last_reading_at` must mean "the
    device spoke", never "we looked" (spec § 8.4). The coordinator therefore
    only calls this on a numeric state.
    """
    conn.execute(
        "UPDATE battery SET last_percent = ?, last_reading_at = ? WHERE id = ?",
        (percent, at, battery_id))


def insert_battery_event(conn, *, battery_id: int, occurred_at: str, kind: str,
                         movement_id: int | None = None, note: str | None = None,
                         idempotency_key: str | None = None) -> int:
    return _insert(conn, "battery_event", {
        "battery_id": battery_id, "occurred_at": occurred_at, "kind": kind,
        "movement_id": movement_id, "note": note,
        "idempotency_key": idempotency_key,
    })


def battery_event_by_key(conn, idempotency_key: str) -> dict[str, Any] | None:
    return _row(conn.execute(
        "SELECT * FROM battery_event WHERE idempotency_key = ?",
        (idempotency_key,)).fetchone())


def list_battery_events(conn, battery_id: int, limit: int = 20) -> list[dict[str, Any]]:
    return _rows(conn.execute(
        "SELECT * FROM battery_event WHERE battery_id = ?"
        " ORDER BY occurred_at DESC, id DESC LIMIT ?", (battery_id, limit)))


def spare_stock(conn, product_ids) -> dict[int, float]:
    """How many spares are left, per product id.

    A filter over `stock_rows`, never a second formula: the remaining stock of
    a product is already expressed there, and two formulas for one number
    start to diverge the day one of them gets a correction — this being the
    number that decides whether the task says « aucune en stock ».

    A product with no open batch answers 0.0, not "missing": « aucune en
    stock » and « on ne sait pas » are not the same sentence, and the first is
    the one the task must say.
    """
    wanted = {int(product_id) for product_id in product_ids}
    if not wanted:
        return {}
    totals = {product_id: 0.0 for product_id in wanted}
    for row in stock_rows(conn):
        if row["product_id"] in totals:
            totals[row["product_id"]] += float(row["remaining"] or 0.0)
    return totals


def insert_equipment(conn, *, name: str, **fields: Any) -> int:
    values: dict[str, Any] = {"name": name}
    values.update({k: v for k, v in fields.items()
                   if k in EQUIPMENT_FIELDS and k != "name"})
    return _insert(conn, "equipment", values)


def update_equipment_fields(conn, equipment_id: int, fields: dict[str, Any]) -> None:
    _update_fields(conn, "equipment", equipment_id, fields)


def get_equipment(conn, equipment_id: int) -> dict[str, Any] | None:
    return _row(conn.execute(
        "SELECT e.*, l.name AS location_name FROM equipment e"
        " LEFT JOIN location l ON l.id = e.location_id"
        " WHERE e.id = ?", (equipment_id,)).fetchone())


def list_equipment(conn, *, active_only: bool = True) -> list[dict[str, Any]]:
    where = " WHERE e.active = 1" if active_only else ""
    return _rows(conn.execute(
        "SELECT e.*, l.name AS location_name,"
        "       (SELECT COUNT(*) FROM equipment_consumable c"
        "         WHERE c.equipment_id = e.id) AS consumable_count"
        " FROM equipment e"
        " LEFT JOIN location l ON l.id = e.location_id"
        f"{where}"
        " ORDER BY l.name IS NULL, l.name, e.name"
    ))


def link_consumable(conn, *, equipment_id: int, product_id: int, role: str,
                    **fields: Any) -> int:
    values: dict[str, Any] = {
        "equipment_id": equipment_id, "product_id": product_id, "role": role}
    values.update({k: v for k, v in fields.items() if k in CONSUMABLE_FIELDS})
    return _insert(conn, "equipment_consumable", values)


def unlink_consumable(conn, consumable_id: int) -> None:
    """Unlinking deletes the link, never the product: the filter stays in the
    catalogue with its stock and its price history."""
    conn.execute("DELETE FROM equipment_consumable WHERE id = ?", (consumable_id,))


def list_consumables(conn, equipment_id: int | None = None) -> list[dict[str, Any]]:
    where = " WHERE c.equipment_id = ?" if equipment_id is not None else ""
    params = (equipment_id,) if equipment_id is not None else ()
    return _rows(conn.execute(
        "SELECT c.*, p.name AS product_name, e.name AS equipment_name"
        " FROM equipment_consumable c"
        " JOIN product p ON p.id = c.product_id"
        " JOIN equipment e ON e.id = c.equipment_id"
        f"{where}"
        " ORDER BY c.equipment_id, c.role, c.id", params))


def add_months(start: date, months: int) -> date:
    """`start` plus `months`, clamped to the last day of the arrival month.

    The only arithmetic in this file that is not SQL, and it is here rather
    than in a column because a derived date that is STORED ends up diverging
    from the two values it derives from — someone edits the purchase date and
    the warranty silently keeps the old end. 31 January + 1 month does not
    exist; the answer kept is 28/29 February, never a spill into March.
    """
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    last_day = monthrange(year, month)[1]
    return date(year, month, min(start.day, last_day))


def warranty_rows(conn) -> list[dict[str, Any]]:
    """Every equipment whose warranty end can be COMPUTED, soonest first.

    A duration without a purchase date is not computable, so the line is
    simply absent rather than returned with a `None` somebody will eventually
    render as an empty cell. Expired warranties are still here: filtering to
    what is still ahead is `application.warranties()`'s job, which is the one
    that knows today's date.
    """
    computed: list[dict[str, Any]] = []
    for row in _rows(conn.execute(
            "SELECT id, name, purchased_on, warranty_months FROM equipment"
            " WHERE active = 1 AND purchased_on IS NOT NULL"
            "   AND warranty_months IS NOT NULL")):
        try:
            ends_on = add_months(date.fromisoformat(row["purchased_on"]),
                                 int(row["warranty_months"]))
        except (TypeError, ValueError):
            # A malformed date stored before `iso_date` guarded this column:
            # skipped, never raised — this function runs on every coordinator
            # refresh, and raising here would take every entity unavailable.
            continue
        computed.append({**row, "warranty_ends_on": ends_on.isoformat()})
    computed.sort(key=lambda row: (row["warranty_ends_on"], row["name"]))
    return computed


def set_battery_readings(conn, readings) -> None:
    """Every reading of this refresh, in ONE statement and ONE transaction.

    Fourteen separate UPDATEs every fifteen minutes on a single-writer
    database is 1 344 transactions a day for nothing. `executemany` inside the
    caller's transaction keeps it to one.
    """
    rows = [(percent, at, battery_id) for battery_id, percent, at in readings]
    if not rows:
        return
    conn.executemany(
        "UPDATE battery SET last_percent = ?, last_reading_at = ? WHERE id = ?", rows)


# =============================================================================
# Lot 4 — la liste de courses, ses revendications et ses récurrences.
#
# Alias `sl` (shopping_list_item), `sa` (store_aisle), `ai` (aisle), `st`
# (store), `sc` (shopping_list_claim) — jamais `b` : le test qui interdit de
# sélectionner une ligne de lot entière scanne ce paquet LITTÉRALEMENT et ne
# regarde pas quelle table est derrière l'alias.
# =============================================================================

LIST_ITEM_FIELDS: Final = ("product_id", "free_text", "quantity", "note")

# 999 : un produit sans rayon marche en dernier. Un rayon inconnu DANS ce
# magasin garde sa place par défaut (`aisle.position`) plutôt que de tomber
# à la fin — on sait où il est en général, on ne sait juste pas où il est ici.
_LIST_ORDER_SQL: Final = "COALESCE(sa.position, ai.position, 999)"


def insert_list_item(conn, *, added_at: str, product_id: int | None = None,
                     free_text: str | None = None, quantity: float | None = None,
                     note: str | None = None) -> int:
    return _insert(conn, "shopping_list_item", {
        "product_id": product_id, "free_text": free_text, "quantity": quantity,
        "note": note, "added_at": added_at,
    })


def update_list_item(conn, item_id: int, fields: Mapping[str, Any]) -> None:
    _update_fields(conn, "shopping_list_item", item_id,
                   _filtered(fields, LIST_ITEM_FIELDS))


def check_list_item(conn, item_id: int, *, at: str, session_id: int | None,
                    line_id: int | None) -> None:
    """« Je l'ai », jamais « c'est en stock » (§ 7.5).

    `session_id` et `line_id` sont écrits ensemble : c'est le SCAN qui coche,
    et la ligne de panier doit rester retrouvable pour pouvoir décocher quand
    on repose l'article dans le rayon.
    """
    conn.execute(
        "UPDATE shopping_list_item SET checked_at = ?, session_id = ?, line_id = ?"
        " WHERE id = ?", (at, session_id, line_id, item_id))


def uncheck_list_item(conn, item_id: int) -> None:
    """Les trois colonnes ensemble : un item décoché qui garderait un
    `line_id` mort ferait viser au décochage suivant une ligne disparue."""
    conn.execute(
        "UPDATE shopping_list_item SET checked_at = NULL, session_id = NULL,"
        " line_id = NULL WHERE id = ?", (item_id,))


def remove_list_item(conn, item_id: int, *, at: str) -> None:
    """Un horodatage, jamais un DELETE : la réconciliation doit se SOUVENIR
    qu'on n'en veut pas, sinon elle remet la ligne un quart d'heure plus tard."""
    conn.execute("UPDATE shopping_list_item SET removed_at = ? WHERE id = ?",
                 (at, item_id))


def purge_list_item(conn, item_id: int) -> None:
    """Le seul DELETE de la liste, et il emporte les revendications."""
    conn.execute("DELETE FROM shopping_list_claim WHERE item_id = ?", (item_id,))
    conn.execute("DELETE FROM shopping_list_item WHERE id = ?", (item_id,))


def open_item_for_product(conn, product_id: int) -> dict[str, Any] | None:
    return _row(conn.execute(
        "SELECT sl.* FROM shopping_list_item sl"
        " WHERE sl.product_id = ? AND sl.checked_at IS NULL AND sl.removed_at IS NULL",
        (product_id,)).fetchone())


def get_list_item(conn, item_id: int) -> dict[str, Any] | None:
    return _row(conn.execute(
        "SELECT sl.* FROM shopping_list_item sl WHERE sl.id = ?",
        (item_id,)).fetchone())


def list_items(conn, *, store_id: int | None = None,
               include_checked: bool = True,
               include_removed: bool = False) -> list[dict[str, Any]]:
    """La liste ouverte, dans l'ordre du magasin où l'on est.

    L'ordre appris de CE magasin d'abord, l'ordre par défaut du rayon en
    repli, 999 pour un produit sans rayon. Sans `store_id`, c'est l'ordre du
    lot 1, inchangé.
    """
    where = ["sl.removed_at IS NULL"] if not include_removed else []
    if not include_checked:
        where.append("sl.checked_at IS NULL")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    rows = _rows(conn.execute(
        "SELECT sl.*, p.name AS product_name, p.base_unit, p.aisle_id,"
        "       ai.name AS aisle_name,"
        f"      {_LIST_ORDER_SQL} AS aisle_position"
        " FROM shopping_list_item sl"
        " LEFT JOIN product p ON p.id = sl.product_id"
        " LEFT JOIN aisle ai ON ai.id = p.aisle_id"
        " LEFT JOIN store_aisle sa ON sa.aisle_id = ai.id AND sa.store_id = ?"
        f"{clause}"
        f" ORDER BY {_LIST_ORDER_SQL}, p.name, sl.id",
        (store_id,)))
    claims = _claims_by_item(conn)
    for row in rows:
        row["claims"] = claims.get(row["id"], [])
    return rows


def _claims_by_item(conn) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in _rows(conn.execute(
            "SELECT sc.* FROM shopping_list_claim sc ORDER BY sc.item_id, sc.origin")):
        grouped.setdefault(row["item_id"], []).append(row)
    return grouped


def set_claim(conn, *, item_id: int, origin: str, quantity: float | None,
              detail: str | None, claimed_at: str) -> None:
    """Au plus une revendication par origine : deux passages de la même
    origine mettent à jour, ils n'empilent pas."""
    conn.execute(
        "INSERT INTO shopping_list_claim (item_id, origin, quantity, detail, claimed_at)"
        " VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT (item_id, origin) DO UPDATE SET"
        "   quantity = excluded.quantity, detail = excluded.detail,"
        "   claimed_at = excluded.claimed_at",
        (item_id, origin, quantity, detail, claimed_at))


def drop_claim(conn, *, item_id: int, origin: str) -> None:
    conn.execute("DELETE FROM shopping_list_claim WHERE item_id = ? AND origin = ?",
                 (item_id, origin))


def claims_of(conn, item_id: int) -> list[dict[str, Any]]:
    return _rows(conn.execute(
        "SELECT sc.* FROM shopping_list_claim sc WHERE sc.item_id = ? ORDER BY sc.origin",
        (item_id,)))


# --- les récurrences --------------------------------------------------------

RECURRING_FIELDS: Final = ("product_id", "free_text", "quantity", "every_days",
                           "last_added_on", "active")


def upsert_recurring(conn, *, recurring_id: int | None = None,
                     product_id: int | None = None, free_text: str | None = None,
                     quantity: float | None = None, every_days: int,
                     last_added_on: str | None = None,
                     active: int = 1) -> int:
    values = {
        "product_id": product_id, "free_text": free_text, "quantity": quantity,
        "every_days": every_days, "last_added_on": last_added_on, "active": active,
    }
    if recurring_id is None:
        return _insert(conn, "shopping_recurring", values)
    _update_fields(conn, "shopping_recurring", recurring_id, values)
    return int(recurring_id)


def delete_recurring(conn, recurring_id: int) -> None:
    conn.execute("DELETE FROM shopping_recurring WHERE id = ?", (recurring_id,))


def list_recurring(conn, *, active_only: bool = True) -> list[dict[str, Any]]:
    where = " WHERE sr.active = 1" if active_only else ""
    return _rows(conn.execute(
        "SELECT sr.*, p.name AS product_name, p.base_unit"
        " FROM shopping_recurring sr"
        " LEFT JOIN product p ON p.id = sr.product_id"
        f"{where}"
        " ORDER BY COALESCE(p.name, sr.free_text), sr.id"))


def due_recurring(conn, today: str) -> list[dict[str, Any]]:
    """Ce qu'on rachète sans que rien ne le réclame, arrivé à échéance.

    Jamais ajoutée = due tout de suite : déclarer « le café, toutes les trois
    semaines » et attendre trois semaines avant de le voir apparaître est le
    genre de silence qui fait croire que la fonction ne marche pas.
    """
    return _rows(conn.execute(
        "SELECT sr.*, p.name AS product_name, p.base_unit"
        " FROM shopping_recurring sr"
        " LEFT JOIN product p ON p.id = sr.product_id"
        " WHERE sr.active = 1"
        "   AND (sr.last_added_on IS NULL"
        "        OR DATE(sr.last_added_on, '+' || sr.every_days || ' days') <= DATE(?))"
        " ORDER BY sr.id", (today,)))


def mark_recurring_added(conn, recurring_id: int, on: str) -> None:
    conn.execute("UPDATE shopping_recurring SET last_added_on = ? WHERE id = ?",
                 (on, recurring_id))


# --- l'estimation du panier -------------------------------------------------

def levels_for_products(conn, product_ids: Sequence[int]) -> list[dict[str, Any]]:
    """Le seuil et le stock de ces produits, seuil franchi ou non.

    `shortage_rows` ne rend que ce qui est SOUS le seuil : appliquer une
    hystérésis demande de revoir aussi ce qui vient de repasser au-dessus.
    Un produit disparu ou désactivé n'est simplement pas dans la réponse —
    et une revendication sans mesure se MAINTIENT (§ 7.3).
    """
    if not product_ids:
        return []
    marks = ", ".join("?" for _ in product_ids)
    return _rows(conn.execute(
        "SELECT p.id AS product_id, p.name AS product_name, p.base_unit,"
        "       p.min_quantity, COALESCE(SUM(bt.remaining), 0) AS quantity"
        " FROM product p"
        " LEFT JOIN article a ON a.product_id = p.id"
        " LEFT JOIN batch bt ON bt.article_id = a.id AND bt.closed_at IS NULL"
        f" WHERE p.id IN ({marks}) AND p.active = 1"
        " GROUP BY p.id", tuple(product_ids)))


def _estimate_articles(conn, product_id: int) -> list[dict[str, Any]]:
    """Les articles de ce produit, du plus habituel au moins habituel.

    Le dernier acheté d'abord, l'article générique ensuite, le reste après.
    """
    return _rows(conn.execute(
        "SELECT a.id, a.net_quantity,"
        "       (SELECT MAX(bt.entered_at) FROM batch bt WHERE bt.article_id = a.id)"
        "         AS last_bought"
        " FROM article a WHERE a.product_id = ?"
        " ORDER BY last_bought IS NULL, last_bought DESC, a.is_generic DESC, a.id",
        (product_id,)))


def list_estimate_rows(conn) -> list[dict[str, Any]]:
    """Pour chaque ligne ouverte, l'article qu'on achète d'habitude et son prix.

    « L'article qu'on achète d'habitude » = le dernier entré en stock pour ce
    produit, à défaut son article générique. Répondre « ça va faire combien ? »
    avec le moins cher du catalogue donnerait un total que la caisse
    démentirait à chaque voyage.

    Un article sans prix connu ne fait pas taire la ligne : on descend la
    liste des candidats jusqu'au premier qui en a un. Une estimation muette
    alors qu'un prix existe sur le même produit n'aide personne.

    Sans quantité (« ce qu'il faut »), on estime UN conditionnement : zéro
    afficherait moins que la réalité, et personne ne s'en méfierait.
    """
    rows = _rows(conn.execute(
        "SELECT sl.id AS item_id, sl.product_id, sl.free_text, sl.quantity,"
        "       sl.checked_at, p.name AS product_name, p.base_unit"
        " FROM shopping_list_item sl"
        " LEFT JOIN product p ON p.id = sl.product_id"
        " WHERE sl.removed_at IS NULL"
        " ORDER BY sl.id"))
    for row in rows:
        row["article_id"] = None
        row["price_per_base_unit"] = None
        row["estimate"] = None
        if row["product_id"] is None:
            continue
        candidates = _estimate_articles(conn, row["product_id"])
        if candidates:
            row["article_id"] = candidates[0]["id"]
        for article in candidates:
            price = latest_price(conn, article["id"])
            if price is None:
                continue
            quantity = row["quantity"]
            if quantity is None:
                quantity = article["net_quantity"]
            row["article_id"] = article["id"]
            row["price_per_base_unit"] = price
            if quantity is not None:
                row["estimate"] = round(quantity * price, 4)
            break
    return rows


# =============================================================================
# Lot 4 — le ticket de caisse.
#
# Alias `br` (receipt) et `rl` (receipt_line) — jamais `b` : le test qui
# interdit de sélectionner une ligne de lot entière scanne ce paquet
# littéralement et ne distingue pas les tables.
# =============================================================================

def insert_receipt(conn, *, media_content_id: str, captured_at: str,
                   session_id: int | None = None,
                   store_id: int | None = None,
                   agent_entity_id: str | None = None,
                   state: str = "pending") -> int:
    return _insert(conn, "receipt", {
        "session_id": session_id, "media_content_id": media_content_id,
        "captured_at": captured_at, "state": state, "store_id": store_id,
        "agent_entity_id": agent_entity_id, "attempts": 0,
    })


def get_receipt(conn, receipt_id: int) -> dict[str, Any] | None:
    row = _row(conn.execute(
        "SELECT br.* FROM receipt br WHERE br.id = ?", (receipt_id,)).fetchone())
    if row is None:
        return None
    row["lines"] = receipt_lines(conn, receipt_id)
    return row


def receipt_lines(conn, receipt_id: int) -> list[dict[str, Any]]:
    return _rows(conn.execute(
        "SELECT rl.* FROM receipt_line rl WHERE rl.receipt_id = ?"
        " ORDER BY rl.position, rl.id", (receipt_id,)))


def list_receipts(conn, *, states: Sequence[str] | None = None,
                  limit: int = 50) -> list[dict[str, Any]]:
    where, params = "", []
    if states:
        where = f" WHERE br.state IN {_reasons_sql(states)}"
    return _rows(conn.execute(
        "SELECT br.*, st.name AS store_name FROM receipt br"
        " LEFT JOIN store st ON st.id = br.store_id"
        f"{where}"
        " ORDER BY br.captured_at DESC, br.id DESC LIMIT ?",
        (*params, limit)))


def pending_receipts(conn) -> list[dict[str, Any]]:
    """Ceux qui doivent encore une réponse : à lire, ou dont la lecture a
    échoué. La photo reste, `home_stock.read_receipt` réessaie."""
    return list_receipts(conn, states=("pending", "failed"))


def set_receipt_state(conn, receipt_id: int, state: str, *,
                      error: str | None = None, attempts: int | None = None,
                      read_at: str | None = None, store_id: int | None = None,
                      purchased_on: str | None = None,
                      total: float | None = None,
                      agent_entity_id: str | None = None,
                      raw: str | None = None) -> None:
    fields: dict[str, Any] = {"state": state, "error": error}
    for name, value in (("attempts", attempts), ("read_at", read_at),
                        ("store_id", store_id), ("purchased_on", purchased_on),
                        ("total", total), ("agent_entity_id", agent_entity_id),
                        ("raw", raw)):
        if value is not None:
            fields[name] = value
    _update_fields(conn, "receipt", receipt_id, fields)


def replace_receipt_lines(conn, receipt_id: int,
                          lines: Sequence[Mapping[str, Any]]) -> None:
    """Une relecture REMPLACE ce qu'on avait lu.

    Garder les deux ferait une liste où la moitié des lignes vient d'une
    lecture ratée, et rien à l'écran ne dirait laquelle.
    """
    conn.execute("DELETE FROM receipt_line WHERE receipt_id = ?", (receipt_id,))
    for line in lines:
        _insert(conn, "receipt_line", {
            "receipt_id": receipt_id,
            "position": line["position"],
            "label": line["label"],
            "quantity": line.get("quantity"),
            "unit_price": line.get("unit_price"),
            "total_price": line.get("total_price"),
            "line_id": line.get("line_id"),
            "article_id": line.get("article_id"),
            "match_state": line.get("match_state", "unmatched"),
        })


def set_receipt_line_match(conn, receipt_line_id: int, *, line_id: int | None,
                           state: str) -> None:
    conn.execute(
        "UPDATE receipt_line SET line_id = ?, match_state = ? WHERE id = ?",
        (line_id, state, receipt_line_id))


def mark_receipt_line_applied(conn, receipt_line_id: int, *, at: str) -> None:
    """Ce qui rend une seconde application sans effet."""
    conn.execute("UPDATE receipt_line SET applied_at = ? WHERE id = ?",
                 (at, receipt_line_id))
