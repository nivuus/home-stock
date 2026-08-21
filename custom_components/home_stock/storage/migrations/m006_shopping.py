"""Lot 4: the shopping list, the receipt, the store and the reversal link.
Mirrors section 6.2 of the lot 4 design.

`apply()` backfills what already exists — stores promoted from the free
strings of `shopping_session.store` and `price.store`, by EXACT equality
only — and marks existing shopping lines `manual`. It creates no list row:
the list is built by the first reconciliation, never by a migration.
"""
from __future__ import annotations

import sqlite3

VERSION = 6

SQL = """
-- Le magasin, promu de chaîne libre à ligne (amendement A4).
CREATE TABLE store (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  position INTEGER NOT NULL DEFAULT 0,  -- ordre d'affichage des pastilles
  active INTEGER NOT NULL DEFAULT 1
);

-- L'ordre du parcours DANS ce magasin. Une ligne par rayon effectivement
-- rencontré : un rayon jamais vu ici garde sa place par défaut (aisle.position).
CREATE TABLE store_aisle (
  store_id INTEGER NOT NULL REFERENCES store(id),
  aisle_id INTEGER NOT NULL REFERENCES aisle(id),
  position INTEGER NOT NULL,
  -- 'learned' : recalculé à chaque clôture de session.
  -- 'manual'  : épinglé par le propriétaire, jamais déplacé par l'apprentissage.
  source TEXT NOT NULL CHECK (source IN ('learned','manual')),
  mean_rank REAL,                 -- le rang moyen observé, pour l'explication
  observed_sessions INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT,
  PRIMARY KEY (store_id, aisle_id)
);

-- La liste. Une ligne par produit à acheter, quelles que soient les raisons.
CREATE TABLE shopping_list_item (
  id INTEGER PRIMARY KEY,
  product_id INTEGER REFERENCES product(id),
  free_text TEXT,                 -- une ligne qui ne nomme aucun produit
  quantity REAL,                  -- unité de base du produit ; NULL = « ce qu'il faut »
  note TEXT,
  added_at TEXT NOT NULL,
  checked_at TEXT,                -- « je l'ai » (§ 7.5), jamais « c'est en stock »
  removed_at TEXT,                -- retiré à la main : la réconciliation le respecte
  session_id INTEGER REFERENCES shopping_session(id),
  line_id INTEGER REFERENCES shopping_line(id),
  CHECK (product_id IS NOT NULL OR free_text IS NOT NULL)
);

-- Au plus UNE ligne ouverte par produit. C'est la règle anti-doublon, tenue par
-- la base et non par la bonne volonté des quatre producteurs de lignes.
CREATE UNIQUE INDEX idx_list_open_product ON shopping_list_item(product_id)
  WHERE product_id IS NOT NULL AND checked_at IS NULL AND removed_at IS NULL;

-- Pourquoi cette ligne est là. Autant de revendications que de raisons.
CREATE TABLE shopping_list_claim (
  item_id INTEGER NOT NULL REFERENCES shopping_list_item(id) ON DELETE CASCADE,
  origin TEXT NOT NULL CHECK (origin IN ('shortage','meal_plan','manual','recurring')),
  quantity REAL,                  -- ce que CETTE raison réclame, unité de base
  detail TEXT,                    -- « Dîner de jeudi », « seuil 500 g », « toutes les 3 sem. »
  claimed_at TEXT NOT NULL,
  PRIMARY KEY (item_id, origin)
);

-- Ce qu'on rachète sans que rien ne le réclame : le café, les sacs poubelle.
CREATE TABLE shopping_recurring (
  id INTEGER PRIMARY KEY,
  product_id INTEGER REFERENCES product(id),
  free_text TEXT,
  quantity REAL,
  every_days INTEGER NOT NULL,
  last_added_on TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  CHECK (product_id IS NOT NULL OR free_text IS NOT NULL)
);

-- Le ticket photographié, et ce que le modèle en a lu.
CREATE TABLE receipt (
  id INTEGER PRIMARY KEY,
  session_id INTEGER REFERENCES shopping_session(id),
  media_content_id TEXT NOT NULL, -- media-source://… rendu par le téléversement HA
  captured_at TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('pending','read','failed','applied','discarded')),
  store_id INTEGER REFERENCES store(id),
  purchased_on TEXT,
  total REAL,                     -- le total lu sur le ticket, tel quel
  agent_entity_id TEXT,           -- QUI a lu : l'entité ai_task, figée sur la ligne
  read_at TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  error TEXT,                     -- en français, affichable tel quel
  raw TEXT                        -- la réponse du modèle, brute, comme article.off_raw
);

CREATE TABLE receipt_line (
  id INTEGER PRIMARY KEY,
  receipt_id INTEGER NOT NULL REFERENCES receipt(id),
  position INTEGER NOT NULL,
  label TEXT NOT NULL,            -- le libellé de caisse, illisible et abrégé
  quantity REAL,
  unit_price REAL,                -- € par unité VENDUE, pas par unité de base
  total_price REAL,
  line_id INTEGER REFERENCES shopping_line(id),
  article_id INTEGER REFERENCES article(id),
  -- Même vocabulaire qu'au lot 3 pour l'appariement d'un ingrédient : quatre
  -- états, les mêmes mots, la même signification.
  match_state TEXT NOT NULL DEFAULT 'unmatched'
    CHECK (match_state IN ('unmatched','auto','confirmed','ignored')),
  applied_at TEXT
);

-- La contrepassation (amendement A1). UNIQUE : un mouvement ne s'annule qu'une
-- fois. Deux corrections d'une même ligne rembourseraient deux fois.
ALTER TABLE movement ADD COLUMN corrects_id INTEGER REFERENCES movement(id);
CREATE UNIQUE INDEX idx_movement_corrects ON movement(corrects_id)
  WHERE corrects_id IS NOT NULL;

ALTER TABLE shopping_session ADD COLUMN store_id INTEGER REFERENCES store(id);
ALTER TABLE shopping_line ADD COLUMN price_source TEXT;   -- amendement A3
ALTER TABLE price ADD COLUMN store_id INTEGER REFERENCES store(id);

CREATE INDEX idx_list_open ON shopping_list_item(checked_at, removed_at);
CREATE INDEX idx_receipt_line_receipt ON receipt_line(receipt_id, position);
CREATE INDEX idx_store_aisle_order ON store_aisle(store_id, position);
"""


def apply(conn: sqlite3.Connection) -> None:
    """Backfill, replayable end to end (§ 6.3)."""
    # 1. Les magasins, par égalité EXACTE du nom. Aucun rapprochement
    #    approximatif : fusionner « Leclerc » et « E.Leclerc » est une
    #    décision du propriétaire, pas une migration.
    for table in ("shopping_session", "price"):
        conn.execute(
            f"INSERT OR IGNORE INTO store (name)"
            f" SELECT DISTINCT store FROM {table}"
            f" WHERE store IS NOT NULL AND TRIM(store) <> ''"
        )
        conn.execute(
            f"UPDATE {table} SET store_id = ("
            f"  SELECT s.id FROM store s WHERE s.name = {table}.store)"
            f" WHERE store_id IS NULL AND store IS NOT NULL AND TRIM(store) <> ''"
        )
    # 2. `manual` conserve le comportement actuel de la cascade (amendement A3).
    conn.execute(
        "UPDATE shopping_line SET price_source = 'manual' WHERE price_source IS NULL"
    )
    # 3. Aucune ligne de liste : elle naît de la première réconciliation.
    conn.commit()
