"""Initial schema. Mirrors section 6.2 of the design document."""

VERSION = 1

SQL = """
CREATE TABLE location (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE aisle (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE category (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE product (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  base_unit TEXT NOT NULL CHECK (base_unit IN ('g','ml','piece')),
  category_id INTEGER REFERENCES category(id),
  aisle_id INTEGER REFERENCES aisle(id),
  edible INTEGER NOT NULL DEFAULT 1,
  default_location_id INTEGER REFERENCES location(id),
  min_quantity REAL,
  days_after_opening INTEGER,
  reference_kcal REAL,
  active INTEGER NOT NULL DEFAULT 1,
  external_ref TEXT
);

-- All nutrition values are PER BASE UNIT (kcal per g, g of protein per g...).
-- Display divides by 100. One convention everywhere: the "per 100 g or per stock
-- unit?" ambiguity is what produced the 1000x wrong spinach values in Grocy.
CREATE TABLE article (
  id INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL REFERENCES product(id),
  brand TEXT,
  label TEXT,
  net_quantity REAL,
  image TEXT,
  kcal_per_base_unit REAL,
  proteins REAL, carbohydrates REAL, sugars REAL, added_sugars REAL,
  fat REAL, saturated_fat REAL, fiber REAL, salt REAL,
  nutriscore TEXT, nova INTEGER, ecoscore TEXT,
  allergens TEXT, traces TEXT, additives TEXT, off_labels TEXT,
  off_source TEXT,
  off_synced_at TEXT,
  off_raw TEXT,
  manual_fields TEXT,
  is_generic INTEGER NOT NULL DEFAULT 0,
  external_ref TEXT
);

CREATE TABLE barcode (
  code TEXT PRIMARY KEY,
  article_id INTEGER NOT NULL REFERENCES article(id)
);

CREATE TABLE packaging (
  id INTEGER PRIMARY KEY,
  scope TEXT NOT NULL CHECK (scope IN ('product','article')),
  target_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  base_quantity REAL NOT NULL,
  is_purchase_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE price (
  id INTEGER PRIMARY KEY,
  article_id INTEGER NOT NULL REFERENCES article(id),
  observed_on TEXT NOT NULL,
  price_per_base_unit REAL NOT NULL,
  store TEXT,
  source TEXT NOT NULL
);

CREATE TABLE batch (
  id INTEGER PRIMARY KEY,
  article_id INTEGER NOT NULL REFERENCES article(id),
  location_id INTEGER NOT NULL REFERENCES location(id),
  remaining REAL NOT NULL,
  initial REAL NOT NULL,
  best_before TEXT,
  entered_at TEXT NOT NULL,
  opened_at TEXT,
  price_per_base_unit REAL,
  session_id INTEGER,
  closed_at TEXT
);

-- APPEND ONLY. Never UPDATE, never DELETE. A correction is a new movement.
CREATE TABLE movement (
  id INTEGER PRIMARY KEY,
  occurred_at TEXT NOT NULL,
  product_id INTEGER NOT NULL REFERENCES product(id),
  article_id INTEGER NOT NULL REFERENCES article(id),
  batch_id INTEGER REFERENCES batch(id),
  quantity REAL NOT NULL,
  reason TEXT NOT NULL,
  kcal REAL, cost REAL,
  ref_type TEXT, ref_id INTEGER,
  idempotency_key TEXT UNIQUE
);

CREATE INDEX idx_batch_pick ON batch(article_id, closed_at, best_before, entered_at);
CREATE INDEX idx_movement_day ON movement(occurred_at);

-- The append-only comment above is not enough on its own: enforce it in the
-- schema so a stray UPDATE or DELETE fails loudly instead of quietly
-- rewriting history.
CREATE TRIGGER movement_no_update
BEFORE UPDATE ON movement
BEGIN
  SELECT RAISE(ABORT, 'movement is append-only: insert a new row instead of UPDATE');
END;

CREATE TRIGGER movement_no_delete
BEFORE DELETE ON movement
BEGIN
  SELECT RAISE(ABORT, 'movement is append-only: insert a new row instead of DELETE');
END;
"""
