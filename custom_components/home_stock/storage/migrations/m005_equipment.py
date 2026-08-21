"""Lot 5: equipment, batteries and consumables. Mirrors section 6.2 of the
lot 5 design.

Schema-only, on purpose: no `apply()`. Seeding the 14 rows this migration's
tables are meant to hold needs the entity registry, so `hass` — and a
migration running in the executor on a bare SQLite connection has neither,
and must not grow one. The import service (task 13) fills these tables
after this migration has run.
"""
from __future__ import annotations

VERSION = 5

SQL = """
-- Une place où une pile vit : la CR2032 du dimmer de la salle de bain, la
-- batterie intégrée de la serrure, les deux AAA de la télécommande cuisine.
-- Ce n'est PAS une cellule physique : c'est un emplacement, et il survit au
-- remplacement de ce qu'on y met.
CREATE TABLE battery (
  id INTEGER PRIMARY KEY,
  label TEXT NOT NULL,             -- le texte affiché dans la tâche (§ 10)
  -- L'ancre : l'`id` (UUID) de l'entrée du registre d'entités, pas l'entity_id.
  entity_registry_id TEXT,
  device_id TEXT,                  -- ancre de secours et source du nom vivant
  equipment_id INTEGER REFERENCES equipment(id),  -- informatif, jamais résolutif
  kind TEXT NOT NULL CHECK (kind IN ('primary','rechargeable_cell','built_in')),
  product_id INTEGER REFERENCES product(id),      -- la rechange, dans le catalogue
  cell_count INTEGER NOT NULL DEFAULT 1 CHECK (cell_count >= 1),
  tracked INTEGER CHECK (tracked IN (0, 1)),      -- NULL = découvert, pas décidé
  exclusion_reason TEXT,           -- obligatoire quand tracked = 0
  low_percent REAL NOT NULL DEFAULT 20,           -- seuil d'apparition
  keep_percent REAL NOT NULL DEFAULT 25,          -- seuil de maintien
  -- Dernier relevé NUMÉRIQUE vu, écrit par le coordinateur. En base, et pas
  -- déduit de `last_changed`, qui repart au démarrage de HA (§ 8.4).
  last_percent REAL,
  last_reading_at TEXT,
  installed_on TEXT,
  expected_life_days INTEGER,
  note TEXT,
  external_ref TEXT,               -- id Grocy, pour un import rejouable
  active INTEGER NOT NULL DEFAULT 1
);

-- AJOUT SEUL, comme `movement`.
CREATE TABLE battery_event (
  id INTEGER PRIMARY KEY,
  battery_id INTEGER NOT NULL REFERENCES battery(id),
  occurred_at TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('install','charge','replacement','removal')),
  movement_id INTEGER REFERENCES movement(id),    -- la rechange consommée, s'il y en a
  note TEXT,
  idempotency_key TEXT UNIQUE
);

CREATE TABLE equipment (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  device_id TEXT,                  -- l'appareil HA, quand il en a un
  location_id INTEGER REFERENCES location(id),
  brand TEXT, model TEXT, serial TEXT,
  purchased_on TEXT,               -- AAAA-MM-JJ, validé par validators.iso_date
  purchase_price REAL,             -- € TTC. N'écrit AUCUN mouvement (§ 11.2)
  warranty_months INTEGER,
  receipt_media_id TEXT,           -- chemin sous media/, jamais sous www/
  manual_url TEXT,
  manual_media_id TEXT,
  note TEXT,
  external_ref TEXT,
  active INTEGER NOT NULL DEFAULT 1
);

-- Le filtre du purificateur, le sac de l'aspirateur, la brosse latérale :
-- des produits du catalogue, rattachés à l'équipement qui les use.
CREATE TABLE equipment_consumable (
  id INTEGER PRIMARY KEY,
  equipment_id INTEGER NOT NULL REFERENCES equipment(id),
  product_id INTEGER NOT NULL REFERENCES product(id),
  role TEXT NOT NULL CHECK (role IN ('filter','bag','brush','cartridge','other')),
  label TEXT,                      -- « brosse principale », « filtre HEPA »
  entity_registry_id TEXT,         -- le capteur d'usure, même ancre qu'une pile
  low_value REAL, keep_value REAL, -- seuils, dans l'unité du capteur
  unit TEXT,                       -- 'percent' | 'minutes'
  expected_life_days INTEGER,
  installed_on TEXT,
  UNIQUE (equipment_id, product_id, role)
);

CREATE INDEX idx_battery_tracked ON battery(tracked, active);
CREATE UNIQUE INDEX idx_battery_anchor ON battery(entity_registry_id)
  WHERE entity_registry_id IS NOT NULL;
CREATE INDEX idx_battery_event_battery ON battery_event(battery_id, occurred_at);
CREATE INDEX idx_equipment_consumable ON equipment_consumable(equipment_id);

CREATE TRIGGER battery_event_no_update BEFORE UPDATE ON battery_event
BEGIN SELECT RAISE(ABORT, 'battery_event is append-only'); END;
CREATE TRIGGER battery_event_no_delete BEFORE DELETE ON battery_event
BEGIN SELECT RAISE(ABORT, 'battery_event is append-only'); END;
"""
