"""Lot 3 : recettes, étapes, ingrédients, mesures, alias, créneaux, repas.

Aucune manipulation de trigger : rien ici ne fait d'UPDATE sur `movement`.
Toutes les colonnes ajoutées sont nullables, toutes les tables sont neuves,
et `apply` ne sème que dans une table vide — donc rejouable, comme les rayons
de m002 et les portions de m003.
"""
from __future__ import annotations

import sqlite3

VERSION = 4

SQL = """
-- Pas d'unicité sur le nom : deux « Salade de pâtes » sont légitimes. L'unicité
-- qui compte est celle de la SOURCE, et c'est elle qui rend l'import rejouable
-- (même raison que product.external_ref au lot 0).
CREATE TABLE recipe (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  servings INTEGER NOT NULL DEFAULT 1 CHECK (servings >= 1),
  total_minutes INTEGER,
  utensils TEXT,
  summary TEXT,                    -- l'accroche de couverture
  image_url TEXT,
  source TEXT NOT NULL CHECK (source IN ('manual','themealdb','grocy')),
  source_ref TEXT,                 -- idMeal, id Grocy
  source_url TEXT,
  language TEXT NOT NULL DEFAULT 'fr',
  adapted_at TEXT,                 -- quand l'agent a traduit/adapté, NULL sinon
  needs_review INTEGER NOT NULL DEFAULT 0,
  leftover_product_id INTEGER REFERENCES product(id),
  leftover_shelf_life_days INTEGER,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  external_ref TEXT
);
CREATE UNIQUE INDEX idx_recipe_source
  ON recipe(source, source_ref) WHERE source_ref IS NOT NULL;

-- Une page de la vue cuisine : un titre, une image, et ses puces.
CREATE TABLE recipe_step (
  id INTEGER PRIMARY KEY,
  recipe_id INTEGER NOT NULL REFERENCES recipe(id),
  position INTEGER NOT NULL,
  title TEXT,
  image_url TEXT,
  UNIQUE (recipe_id, position)
);

-- Une puce. Au plus UN minuteur, et son libellé et sa durée vont ensemble ou
-- pas du tout — un bouton « Cuisson » sans durée n'est pas un bouton.
CREATE TABLE recipe_instruction (
  id INTEGER PRIMARY KEY,
  step_id INTEGER NOT NULL REFERENCES recipe_step(id),
  position INTEGER NOT NULL,
  text TEXT NOT NULL,
  timer_label TEXT,
  timer_seconds INTEGER CHECK (timer_seconds IS NULL OR timer_seconds > 0),
  UNIQUE (step_id, position),
  CHECK ((timer_label IS NULL) = (timer_seconds IS NULL))
);

-- Une ligne d'ingrédient. `amount` est le SEUL nombre écrit ; voir § 9.
CREATE TABLE recipe_ingredient (
  id INTEGER PRIMARY KEY,
  recipe_id INTEGER NOT NULL REFERENCES recipe(id),
  position INTEGER NOT NULL,
  product_id INTEGER REFERENCES product(id),
  amount REAL,
  packaging_id INTEGER REFERENCES packaging(id),      -- « 1 tranche », propre au produit
  measure_id INTEGER REFERENCES culinary_measure(id), -- « 1 cs », universelle
  raw_text TEXT NOT NULL,          -- ce que la source disait. PROVENANCE, jamais un calcul
  group_name TEXT,                 -- ingredient_group de Grocy (« Pour la sauce »)
  optional INTEGER NOT NULL DEFAULT 0,
  match_state TEXT NOT NULL DEFAULT 'unmatched'
    CHECK (match_state IN ('unmatched','auto','confirmed','ignored')),
  match_score REAL,
  external_ref TEXT,
  UNIQUE (recipe_id, position),
  -- Une quantité se dit dans UNE mesure, jamais deux.
  CHECK (packaging_id IS NULL OR measure_id IS NULL),
  -- 'auto' et 'confirmed' supposent un produit : ils DÉSIGNENT un produit.
  -- 'unmatched' et 'ignored' n'en supposent aucun — on ignore justement une
  -- ligne qu'on ne veut pas suivre (« sel », « eau du robinet »), et exiger
  -- d'apparier un produit pour pouvoir l'ignorer serait se mordre la queue.
  CHECK (match_state IN ('unmatched', 'ignored') OR product_id IS NOT NULL)
);

-- Les mesures de cuisine, valables pour tous les produits. Un `packaging`
-- propre au produit l'emporte toujours (§ 9).
CREATE TABLE culinary_measure (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  base_unit TEXT NOT NULL CHECK (base_unit IN ('g','ml','piece')),
  base_quantity REAL NOT NULL CHECK (base_quantity > 0),
  UNIQUE (name, base_unit)
);

-- Ce qu'un humain a tranché une fois pour toutes : « coriandre fraîche »,
-- c'est le produit « Coriandre ». Jamais écrit par l'appariement automatique.
CREATE TABLE ingredient_alias (
  id INTEGER PRIMARY KEY,
  normalised TEXT NOT NULL UNIQUE, -- forme rendue par matching.normalise()
  product_id INTEGER NOT NULL REFERENCES product(id),
  created_at TEXT NOT NULL
);

-- Les créneaux du planning. Repris tels quels des meal_plan_sections de Grocy,
-- horaires compris : c'est ce que le calendrier utilise pour poser un début.
CREATE TABLE meal_slot (
  id INTEGER PRIMARY KEY,
  key TEXT NOT NULL UNIQUE CHECK (key IN ('breakfast','lunch','dinner','snack')),
  position INTEGER NOT NULL,
  default_time TEXT NOT NULL,      -- 'HH:MM' local
  duration_minutes INTEGER NOT NULL DEFAULT 45,
  external_ref TEXT
);

-- Un repas posé sur un jour. La table est MUTABLE — ce n'est pas le journal.
CREATE TABLE meal (
  id INTEGER PRIMARY KEY,
  uid TEXT NOT NULL UNIQUE,        -- l'uid de l'événement de calendrier
  day TEXT NOT NULL,               -- journée ALIMENTAIRE (AAAA-MM-JJ), § 12
  slot_key TEXT NOT NULL REFERENCES meal_slot(key),
  position INTEGER NOT NULL DEFAULT 0,
  recipe_id INTEGER REFERENCES recipe(id),
  product_id INTEGER REFERENCES product(id),
  amount REAL,
  packaging_id INTEGER REFERENCES packaging(id),
  note TEXT,
  servings REAL NOT NULL DEFAULT 1 CHECK (servings > 0),
  portions_eaten REAL,             -- combien de parts mangées à la validation
  parts_total INTEGER, parts_mine INTEGER,
  state TEXT NOT NULL DEFAULT 'planned'
    CHECK (state IN ('planned','done','skipped')),
  validated_at TEXT,
  skipped_ingredient_ids TEXT,     -- JSON. Provenance, jamais de la comptabilité
  created_at TEXT NOT NULL,
  external_ref TEXT,
  -- Un repas est une recette, OU un produit, OU une note. Jamais deux.
  CHECK ((recipe_id IS NOT NULL) + (product_id IS NOT NULL) + (note IS NOT NULL) = 1)
);
CREATE INDEX idx_meal_day ON meal(day, slot_key, position);
CREATE INDEX idx_ingredient_recipe ON recipe_ingredient(recipe_id, position);

-- Amendement A2 : un lot peut porter sa propre nutrition.
ALTER TABLE batch ADD COLUMN kcal_per_base_unit REAL;
ALTER TABLE batch ADD COLUMN proteins REAL;
ALTER TABLE batch ADD COLUMN carbohydrates REAL;
ALTER TABLE batch ADD COLUMN sugars REAL;
ALTER TABLE batch ADD COLUMN added_sugars REAL;
ALTER TABLE batch ADD COLUMN fat REAL;
ALTER TABLE batch ADD COLUMN saturated_fat REAL;
ALTER TABLE batch ADD COLUMN fiber REAL;
ALTER TABLE batch ADD COLUMN salt REAL;
"""

SLOTS = (("breakfast", 1, "07:30", 45, "1"), ("lunch", 2, "12:30", 45, "2"),
         ("dinner", 3, "20:00", 45, "3"), ("snack", 4, "16:00", 20, None))

# 15 ml est la valeur normalisée française. Le chiffre exact importe peu :
# un `packaging` propre au produit l'emporte dès qu'il existe (spec § 9).
MEASURES = (("cuillère à soupe", "ml", 15.0), ("cuillère à café", "ml", 5.0),
            ("verre", "ml", 200.0), ("pincée", "g", 1.0))


def apply(conn: sqlite3.Connection) -> None:
    if not conn.execute("SELECT 1 FROM meal_slot LIMIT 1").fetchone():
        conn.executemany(
            "INSERT INTO meal_slot (key, position, default_time, duration_minutes,"
            " external_ref) VALUES (?, ?, ?, ?, ?)", SLOTS)
    if not conn.execute("SELECT 1 FROM culinary_measure LIMIT 1").fetchone():
        conn.executemany(
            "INSERT INTO culinary_measure (name, base_unit, base_quantity)"
            " VALUES (?, ?, ?)", MEASURES)
    conn.execute("INSERT OR IGNORE INTO category (name) VALUES (?)",
                 ("Plats cuisinés",))
