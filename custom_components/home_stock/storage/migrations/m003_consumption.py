"""Lot 2: the journal freezes nine nutrients and who ate, articles learn their
serving, batches remember what has already been announced. Mirrors section 6 of
the lot 2 design.

No trigger dance here, unlike m002: nothing in this migration UPDATEs the
movement table. Every column it adds is nullable, so the rows already written
keep their meaning without being rewritten — NULL parts read as 1/1, NULL
nutrients read as unknown, which is exactly what the history of lots 0 and 1
(and of the Grocy import) actually is.
"""
from __future__ import annotations

import sqlite3

from ...off.mapping import serving_from_raw

VERSION = 3

SQL = """
ALTER TABLE movement ADD COLUMN parts_total INTEGER;
ALTER TABLE movement ADD COLUMN parts_mine INTEGER;

ALTER TABLE movement ADD COLUMN proteins REAL;
ALTER TABLE movement ADD COLUMN carbohydrates REAL;
ALTER TABLE movement ADD COLUMN sugars REAL;
ALTER TABLE movement ADD COLUMN added_sugars REAL;
ALTER TABLE movement ADD COLUMN fat REAL;
ALTER TABLE movement ADD COLUMN saturated_fat REAL;
ALTER TABLE movement ADD COLUMN fiber REAL;
ALTER TABLE movement ADD COLUMN salt REAL;

ALTER TABLE article ADD COLUMN serving_quantity REAL;
ALTER TABLE batch ADD COLUMN expiry_announced_stage TEXT;

-- The daily aggregates all filter on a reason and a date range; the lot 0
-- index (occurred_at alone) leaves the reason to a scan.
CREATE INDEX IF NOT EXISTS idx_movement_reason_day ON movement(reason, occurred_at);
"""


def apply(conn: sqlite3.Connection) -> None:
    """Fill `article.serving_quantity` from the OFF records already stored.

    The record is already in `article.off_raw` (lot 1 stores it): asking the
    network again for something sitting in our own database would be absurd.

    Replayable by construction: only an article whose serving is still NULL is
    touched, so a hand-corrected serving is never overwritten — same discipline
    as m002's aisle backfill.
    """
    rows = conn.execute(
        "SELECT a.id, a.off_raw, a.net_quantity, p.base_unit"
        " FROM article a JOIN product p ON p.id = a.product_id"
        " WHERE a.off_raw IS NOT NULL AND a.serving_quantity IS NULL"
    ).fetchall()
    for row in rows:
        serving = serving_from_raw(row["off_raw"], base_unit=row["base_unit"],
                                   net_quantity=row["net_quantity"])
        if serving is not None:
            conn.execute("UPDATE article SET serving_quantity = ? WHERE id = ?",
                         (serving, row["id"]))
