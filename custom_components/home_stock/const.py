"""Constants shared across the integration."""
from typing import Final

DOMAIN: Final = "home_stock"

BASE_UNITS: Final = ("g", "ml", "piece")

# Movement reasons. See spec section 7.5 for the sign and accounting rules.
REASON_PURCHASE: Final = "purchase"
REASON_CONSUMPTION: Final = "consumption"
REASON_WASTE: Final = "waste"
REASON_EXPIRED: Final = "expired"
REASON_INVENTORY: Final = "inventory"
REASON_TRANSFER: Final = "transfer"
REASON_CONVERSION: Final = "conversion"
# Lot 3. Cuisiner n'est pas consommer : `cooked` deplace la valeur des
# ingredients vers le plat, donc il rejoint REASONS mais jamais
# CONSUME_REASONS. Sa place est la DERNIERE du tuple, et un test epingle
# cet ordre (tests/test_harness.py) : les lots 3 et 5 fusionnent en
# parallele, et une insertion au milieu decalerait silencieusement des
# valeurs deja ecrites en base.
REASON_COOKED: Final = "cooked"
REASONS: Final = (
    REASON_PURCHASE,
    REASON_CONSUMPTION,
    REASON_WASTE,
    REASON_EXPIRED,
    REASON_INVENTORY,
    REASON_TRANSFER,
    REASON_CONVERSION,
    REASON_COOKED,
)

# Reasons a "consume" call may legitimately carry — offered by both the
# services.yaml selector and the websocket schema. The other three reasons
# (purchase, inventory, transfer) are written exclusively by
# add_stock/adjust_inventory/transfer_batch; letting them through here would
# tag a negative-quantity movement with a reason that repo.totals_between/
# journal_entries/counted_movements do not track, silently under-counting
# the kcal, cost or cost_waste totals for stock that really did leave the
# pantry. Lives here, not in services.py, so the websocket surface can use
# the exact same tuple without importing from the older module — the newer
# surface must not be at the mercy of the older one.
CONSUME_REASONS: Final = (REASON_CONSUMPTION, REASON_WASTE, REASON_EXPIRED)

DATABASE_FILENAME: Final = "home_stock.db"
DEFAULT_EXPIRATION_ALERT_DAYS: Final = 3
CONF_EXPIRATION_ALERT_DAYS: Final = "expiration_alert_days"

# Below this many base units, a batch is empty: floating point dust (spec 7.2).
QUANTITY_EPSILON: Final = 0.001

# The eight macros of `article`, exactly as the schema names them. `kcal` is
# not among them: it is `kcal_per_base_unit` on `article` and `kcal` on
# `movement`, and it is the only one with a fallback at the product level
# (`product.reference_kcal`).
MACRO_COLUMNS: Final = (
    "proteins", "carbohydrates", "sugars", "added_sugars",
    "fat", "saturated_fat", "fiber", "salt",
)

# The nine nutrition columns, all stored per base unit, all rescaled when a
# product changes unit. Lives here rather than in `application` because the
# repositories need it too since lot 3 (a batch may carry its own nutrition)
# and the storage layer must never import the layer above it.
NUTRITION_COLUMNS: Final = ("kcal_per_base_unit", *MACRO_COLUMNS)

# A serving above this value is not a serving: it is a data entry mistake in
# a collaborative database (a pallet announced in grams).
MAX_SERVING: Final = 5000.0

# A food day runs from 04:00 local to 04:00 local: what you eat at one in the
# morning belongs to the evening you are still finishing, not to the calendar
# day that just started.
FOOD_DAY_START_HOUR: Final = 4

# Twenty-four plates is already a party; past that it is a typo, and the
# number ends up dividing someone's calories by a hundred.
MAX_PARTS: Final = 24

# --- lot 3 : recettes, planning, repas --------------------------------------
MEAL_SLOT_KEYS: Final = ("breakfast", "lunch", "dinner", "snack")
MEAL_STATES: Final = ("planned", "done", "skipped")
MATCH_STATES: Final = ("unmatched", "auto", "confirmed", "ignored")
RECIPE_SOURCES: Final = ("manual", "themealdb", "grocy")
LEFTOVER_SHELF_LIFE_DAYS: Final = 3
LEFTOVER_CATEGORY_NAME: Final = "Plats cuisinés"
LEFTOVER_NAME_PREFIX: Final = "Reste — "
MAX_SERVINGS: Final = 100.0              # au-delà, c'est une saisie, pas un dîner
MAX_RECIPE_STEPS: Final = 40
MAX_RECIPE_INGREDIENTS: Final = 60
MEAL_HORIZON_DAYS: Final = 7             # la fenêtre de sensor.missing_ingredients
CONF_RECIPE_AGENT: Final = "recipe_agent"
CONF_RECIPE_SOURCE_KEY: Final = "recipe_source_key"
DEFAULT_RECIPE_SOURCE_KEY: Final = "1"

# --- lot 5 : équipements, piles et consommables -----------------------------
BATTERY_KINDS: Final = ("primary", "rechargeable_cell", "built_in")
BATTERY_EVENT_KINDS: Final = ("install", "charge", "replacement", "removal")

# Le verbe affiché, par nature. C'est la SEULE source de la grammaire des
# résumés : `«{verbe} — {libellé}»`. Un caractère de plus ici ferme toutes les
# tâches ouvertes de cette nature et en rouvre autant, avec l'annonce vocale
# qui va avec.
BATTERY_VERBS: Final = {
    "primary": "Pile à changer",
    "rechargeable_cell": "Piles à recharger",
    "built_in": "Recharger",
}
MUTE_SUMMARY_PREFIX: Final = "Pile HS ? — "

# Zigbee2MQTT ne publie `offline` pour un appareil sur pile qu'après 25 h de
# silence (passive.timeout par défaut). En dessous, un capteur muet est un
# capteur qui n'a rien eu à dire. Ce seuil n'est plus contraint par l'uptime
# de Home Assistant depuis que `battery.last_reading_at` vit en base : le
# macro devait se contenter d'1 h parce que `last_changed` repartait à chaque
# démarrage — et un seuil de 12 h avait laissé la porte d'entrée muette 9
# jours (2026-08-07 → 08-16) sans jamais créer de tâche.
BATTERY_MUTE_HOURS: Final = 26

# Les seuils d'AUJOURD'HUI, repris tels quels pour que la bascule ne déplace
# aucune tâche. Ils deviennent réglables par pile, ils ne changent pas de
# valeur par défaut.
DEFAULT_LOW_PERCENT: Final = 20.0
DEFAULT_KEEP_PERCENT: Final = 25.0

CONSUMABLE_ROLES: Final = ("filter", "bag", "brush", "cartridge", "other")
CONSUMABLE_UNITS: Final = ("percent", "minutes")

# --- lot 4 : liste de courses, ticket, correction ---------------------------
# `REASONS` et `CONSUME_REASONS` ne bougent PAS (amendement A1) : une
# contrepassation porte le motif de la ligne qu'elle annule, et le lien vit
# dans `movement.corrects_id`. Un motif `correction` serait invisible de
# `totals_between`, `_PERSONAL_SUMS`, `journal_entries`, `counted_movements`
# et de onze capteurs — `reason` est le compte comptable.
CONF_RECEIPT_AGENT: Final = "receipt_agent"
CONF_SHOPPING_LIST_HORIZON_DAYS: Final = "shopping_list_horizon_days"
DEFAULT_SHOPPING_LIST_HORIZON_DAYS: Final = 7

# Les quatre raisons pour lesquelles une ligne peut être sur la liste. Une
# seule est humaine ; les trois autres se réclament et se relâchent seules.
LIST_ORIGINS: Final = ("shortage", "meal_plan", "manual", "recurring")

# D'où vient un prix. Les trois premières sont OBSERVÉES : quelqu'un ou
# quelque chose a vu ce prix à la caisse. Les trois dernières sont des
# suggestions — un prix suggéré n'est pas un prix observé (amendement A3).
PRICE_SOURCES: Final = (
    "manual", "receipt", "import", "open_prices", "last_known", "store",
)
OBSERVED_PRICE_SOURCES: Final = ("manual", "receipt", "import")

# Hystérésis de la rupture : on ajoute à `seuil`, on ne retire qu'au-dessus
# de `seuil * 1.15`. Sans cela une ligne clignote à chaque consommation.
SHORTAGE_KEEP_FACTOR: Final = 1.15

# L'ordre d'un magasin ne s'apprend pas d'une seule visite.
ROUTE_MIN_SESSIONS: Final = 3
ROUTE_SESSION_WINDOW: Final = 10
ROUTE_MIN_AISLE_SESSIONS: Final = 2

RECEIPT_STATES: Final = ("pending", "read", "failed", "applied", "discarded")
MAX_RECEIPT_LINES: Final = 200
MAX_RECEIPT_LINE_PRICE: Final = 1000.0
MAX_RECEIPT_TOTAL: Final = 3000.0
MAX_RECEIPT_LINE_QUANTITY: Final = 500.0
RECEIPT_TOTAL_TOLERANCE: Final = 0.02
RECEIPT_BACKDATE_DAYS: Final = 2

MAX_LIST_QUANTITY: Final = 100_000.0
MAX_EVERY_DAYS: Final = 365

# Jamais sous `www/` : `/local/` est servi SANS authentification, et un
# ticket porte un magasin, une heure et des habitudes.
RECEIPT_MEDIA_FOLDER: Final = "home_stock/receipts"

# Les quatre destinations d'un emballage en France depuis l'extension des
# consignes de tri (2023). Le serveur rend ces clés ; les phrases françaises
# sont l'affaire du panneau (frontend/src/tri.ts).
RECYCLING_BINS: Final = ("yellow", "glass", "household", "dropoff")

# --- lot 2bis : objectifs nutritionnels --------------------------------------
# La clé des options de l'entrée où vivent les plafonds journaliers.
CONF_GOALS: Final = "nutrition_goals"

# Les neuf nutriments qu'un objectif peut viser : ceux, exactement, que le
# journal fige sur chaque mouvement depuis le lot 2. DÉRIVÉ de MACRO_COLUMNS,
# jamais recopié — un objectif sur un nutriment que le journal ne chiffre pas
# ne pourrait être comparé à rien.
GOAL_NUTRIENTS: Final = ("kcal", *MACRO_COLUMNS)

# Au-delà, ce n'est plus un objectif : c'est une faute de frappe (2000 kcal
# tapé « 20000 » se remarque, « 200000 » ne se remarquerait jamais).
MAX_GOAL: Final = 20_000.0

# Sept journées CLOSES, J-7 … J-1 : la journée courante est exclue, sinon la
# moyenne chuterait chaque matin puis remonterait au dîner.
GOAL_WINDOW_DAYS: Final = 7

# --- lot 7 : la bascule ------------------------------------------------------
GROCY_STOCK_REF_PREFIX: Final = "grocy:stock:"
GROCY_RECIPE_REF_PREFIX: Final = "grocy:recipe:"
GROCY_MEAL_UID_TEMPLATE: Final = "grocy-meal-{id}@home_stock"
# La sentinelle « ne périme jamais » de Grocy. La recopier donnerait dix lots
# qui périment dans neuf cent soixante-treize ans, en tête de tous les tris
# décroissants. NULL est la façon dont home_stock dit « pas de DLC ».
GROCY_NEVER_EXPIRES: Final = "2999-12-31"
# Au-delà, `amount x price` n'est pas un prix maladroit mais une ligne de
# ticket accrochée au mauvais produit (spec §8.4). Le lot le plus cher retenu
# vaut 13,80 EUR, le premier écarté en vaut 47 : la frontière est un fossé.
GROCY_MAX_BATCH_VALUE: Final = 20.0

# Les douze contrôles de la bascule, C0 à C11. Un contrôle sans plancher ne
# doit pas pouvoir exister : `migration_check.FLOORS` doit porter chacun de
# ces codes, et un test structurel le vérifie.
MIGRATION_CHECKS: Final = (
    "C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11",
)
# Grocy écrit des horodatages LOCAUX naïfs, et l'heure de la copie se lit dans
# le fuseau du vérificateur. Deux heures absorbent l'écart sans masquer une
# écriture réelle : le geste 2 de la procédure demande de ne plus rien saisir
# du tout, donc toute écriture postérieure est une infraction, pas un retard.
GROCY_FREEZE_TOLERANCE_HOURS: Final = 2
# Au-delà, la copie n'est plus une photo de l'instant : on la refait.
GROCY_COPY_MAX_AGE_HOURS: Final = 2
# Assez serré pour attraper une conversion ratée, assez lâche pour ne pas se
# battre avec les flottants.
MIGRATION_QUANTITY_TOLERANCE: Final = 1e-6
# Un rapport de 500 lignes n'est pas lu. Le reste part dans l'archive.
MIGRATION_DETAIL_CAP: Final = 50
