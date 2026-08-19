"""Reads and writes, one function per operation. No business logic lives here.

Every function takes an open connection: the caller owns the transaction, so a
service can write a batch and its movement atomically.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from ..const import COUNTED_REASONS

PRODUCT_FIELDS = (
    "category_id", "aisle_id", "edible", "default_location_id", "min_quantity",
    "days_after_opening", "reference_kcal", "active", "external_ref",
)
ARTICLE_FIELDS = (
    "brand", "label", "net_quantity", "image", "kcal_per_base_unit", "proteins",
    "carbohydrates", "sugars", "added_sugars", "fat", "saturated_fat", "fiber",
    "salt", "nutriscore", "nova", "ecoscore", "allergens", "traces", "additives",
    "off_labels", "off_source", "off_synced_at", "off_raw", "manual_fields",
    "is_generic", "external_ref",
)

# The kcal rate to price a movement with: the article's own kcal_per_base_unit,
# or lacking that, its product's reference_kcal (spec 7.4) — generic and
# fresh-produce articles usually carry no rate of their own. Named once here so
# the SQL call sites (list_batches_for_product, stock_rows) and the Python call
# sites (resolve_kcal_rate, used by application.add_stock/consume_batch) cannot
# drift apart.
KCAL_RATE_SQL = "COALESCE(a.kcal_per_base_unit, p.reference_kcal)"


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
    """Aisles in walking order. Empty until Open Food Facts seeds them (lot 1)."""
    return _rows(conn.execute("SELECT * FROM aisle ORDER BY position, name"))


def insert_category(conn, name: str) -> int:
    return _insert(conn, "category", {"name": name})


def insert_aisle(conn, *, name: str, position: int = 0) -> int:
    # Unused in lot 0; lot 1 seeds aisles from Open Food Facts categories.
    return _insert(conn, "aisle", {"name": name, "position": position})


# --- products ---------------------------------------------------------------

def insert_product(conn, *, name: str, base_unit: str, **fields: Any) -> int:
    values: dict[str, Any] = {"name": name, "base_unit": base_unit}
    values.update({k: v for k, v in fields.items() if k in PRODUCT_FIELDS})
    return _insert(conn, "product", values)


def get_product(conn, product_id: int) -> dict[str, Any] | None:
    return _row(conn.execute("SELECT * FROM product WHERE id = ?", (product_id,)).fetchone())


def find_product_by_name(conn, name: str) -> dict[str, Any] | None:
    # Unused in lot 0; lot 1 needs it to match a scanned article to an
    # existing product before offering to create a duplicate.
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


def resolve_kcal_rate(conn, article: dict[str, Any]) -> float | None:
    """The kcal rate to price a movement with (spec 7.4): the article's own
    kcal_per_base_unit, or lacking that, its product's reference_kcal. Python-side
    twin of KCAL_RATE_SQL, for call sites that already hold the article row in
    hand instead of joining kcal in SQL (application.add_stock/consume_batch)."""
    rate = article["kcal_per_base_unit"]
    if rate is not None:
        return rate
    product = get_product(conn, article["product_id"])
    return product["reference_kcal"] if product else None


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


# --- packagings and prices --------------------------------------------------

def insert_packaging(conn, *, scope: str, target_id: int, name: str,
                     base_quantity: float, is_purchase_default: bool = False) -> int:
    # Deliberately unused until lot 1 (design §10, amended 2026-08-18): net
    # weights come from Open Food Facts' product_quantity, a measurement, not
    # from a guess parsed out of a product name. Do not delete as dead code.
    return _insert(conn, "packaging", {
        "scope": scope, "target_id": target_id, "name": name,
        "base_quantity": base_quantity,
        "is_purchase_default": 1 if is_purchase_default else 0,
    })


def insert_price(conn, *, article_id: int, observed_on: str,
                 price_per_base_unit: float, source: str, store: str | None = None) -> int:
    return _insert(conn, "price", {
        "article_id": article_id, "observed_on": observed_on,
        "price_per_base_unit": price_per_base_unit, "source": source, "store": store,
    })


def latest_price(conn, article_id: int) -> float | None:
    # Unused in lot 0; lot 1 needs it to pre-fill the price field at scan time.
    row = conn.execute(
        "SELECT price_per_base_unit FROM price WHERE article_id = ?"
        " ORDER BY observed_on DESC, id DESC LIMIT 1",
        (article_id,),
    ).fetchone()
    return None if row is None else float(row["price_per_base_unit"])


# --- batches ----------------------------------------------------------------

def insert_batch(conn, *, article_id: int, location_id: int, quantity: float,
                 entered_at: str, best_before: str | None = None,
                 price_per_base_unit: float | None = None) -> int:
    return _insert(conn, "batch", {
        "article_id": article_id, "location_id": location_id,
        "remaining": quantity, "initial": quantity, "entered_at": entered_at,
        "best_before": best_before, "price_per_base_unit": price_per_base_unit,
    })


def list_batches_for_product(conn, product_id: int) -> list[dict[str, Any]]:
    """Open batches only, with the kcal rate resolved: the article's own rate,
    falling back to the product's reference_kcal when the article has none
    (spec 7.4 — generic/produce articles usually carry no rate of their own).
    """
    return _rows(conn.execute(
        f"SELECT b.*, {KCAL_RATE_SQL} AS kcal_per_base_unit,"
        "       a.product_id FROM batch b"
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


# --- movements --------------------------------------------------------------

def insert_movement(conn, *, occurred_at: str, product_id: int, article_id: int,
                    quantity: float, reason: str, base_unit: str,
                    batch_id: int | None = None,
                    kcal: float | None = None, cost: float | None = None,
                    ref_type: str | None = None, ref_id: int | None = None,
                    idempotency_key: str | None = None) -> int:
    return _insert(conn, "movement", {
        "occurred_at": occurred_at, "product_id": product_id, "article_id": article_id,
        "batch_id": batch_id, "quantity": quantity, "reason": reason,
        "base_unit": base_unit, "kcal": kcal,
        "cost": cost, "ref_type": ref_type, "ref_id": ref_id,
        "idempotency_key": idempotency_key,
    })


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


def counted_totals(conn) -> dict[str, float]:
    """Cumulative kcal and cost of everything that left the stock.

    Purchases, inventory corrections and transfers are excluded: only the reasons
    listed in COUNTED_REASONS feed the daily totals (spec 7.5).
    """
    marks = ", ".join("?" for _ in COUNTED_REASONS)
    row = conn.execute(
        f"SELECT COALESCE(SUM(kcal), 0) AS kcal, COALESCE(SUM(cost), 0) AS cost"
        f" FROM movement WHERE reason IN ({marks})",
        tuple(sorted(COUNTED_REASONS)),
    ).fetchone()
    return {"kcal": float(row["kcal"]), "cost": float(row["cost"])}


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
