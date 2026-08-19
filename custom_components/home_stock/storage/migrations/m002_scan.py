"""Lot 1: the journal freezes its unit, products carry a shelf life, and the
shopping session gets its two tables. Mirrors section 6 of the lot 1 design.
"""
from __future__ import annotations

import sqlite3

from ...aisles import AISLES, CATEGORY_TO_AISLE

VERSION = 2

# The movement table is append-only, enforced by a BEFORE UPDATE trigger. The
# backfill below IS an UPDATE, so the trigger has to come off and go straight
# back on — inside the same script, so no window exists where history is
# rewritable.
SQL = """
DROP TRIGGER movement_no_update;

ALTER TABLE product ADD COLUMN default_shelf_life_days INTEGER;
ALTER TABLE movement ADD COLUMN base_unit TEXT;

-- A movement whose product_id no longer resolves to a product keeps
-- base_unit = NULL. This is deliberate: when the product is gone we
-- genuinely do not know the unit, and inventing one would be worse than
-- admitting ignorance. In production this case is unreachable: movement
-- carries a foreign key on product_id, and PRAGMA foreign_keys=ON forbids
-- inserting a movement whose product does not exist in the first place.
UPDATE movement SET base_unit = (
  SELECT p.base_unit FROM product p WHERE p.id = movement.product_id
) WHERE base_unit IS NULL;

CREATE TRIGGER movement_no_update
BEFORE UPDATE ON movement
BEGIN
  SELECT RAISE(ABORT, 'movement is append-only: insert a new row instead of UPDATE');
END;

CREATE TABLE shopping_session (
  id INTEGER PRIMARY KEY,
  started_at TEXT NOT NULL,
  closed_at TEXT,
  store TEXT,
  state TEXT NOT NULL CHECK (state IN ('shopping','to_store','done'))
);

CREATE TABLE shopping_line (
  id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES shopping_session(id),
  article_id INTEGER NOT NULL REFERENCES article(id),
  quantity REAL NOT NULL,
  unit_price REAL,
  scanned_at TEXT NOT NULL,
  stored_at TEXT,
  batch_id INTEGER REFERENCES batch(id),
  idempotency_key TEXT UNIQUE
);

CREATE INDEX idx_line_session ON shopping_line(session_id, stored_at);
CREATE UNIQUE INDEX idx_one_open_session
  ON shopping_session(state) WHERE state = 'shopping';
"""


def apply(conn: sqlite3.Connection) -> None:
    """Seed the aisles and give every product the aisle of its category.

    Written in Python rather than SQL because the referential lives in
    aisles.py, where the OFF classification reads it too. Both statements are
    replayable: INSERT OR IGNORE on the names, and a backfill that only ever
    fills an aisle that is still NULL — a hand-chosen aisle is never
    overwritten.
    """
    for position, name in enumerate(AISLES):
        conn.execute(
            "INSERT OR IGNORE INTO aisle (name, position) VALUES (?, ?)", (name, position)
        )

    for category, aisle in CATEGORY_TO_AISLE.items():
        conn.execute(
            """
            UPDATE product SET aisle_id = (SELECT id FROM aisle WHERE name = ?)
            WHERE aisle_id IS NULL
              AND category_id = (SELECT id FROM category WHERE name = ?)
            """,
            (aisle, category),
        )
