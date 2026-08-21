#!/usr/bin/env python3
"""Extract the Grocy tables the lot 7 tests measure, and freeze them as JSON.

NEVER RUN BY THE TEST SUITE. This tool documents where the JSON files next to
it come from, and lets them be regenerated when the spec is amended.

It reads a **copy** of grocy.db, opened `file:…?mode=ro`, and refuses to start
on the production file. Grocy is read-only, and only a copy of it is read —
decision taken in lot 0, never relaxed.

The 102 descriptions weigh 3.80 MB, of which 3.65 MB is base64 inside 62
data-URIs. Versioning 3.6 MB of binary blobs to test an HTML splitter is a bad
trade, so each payload is replaced by the smallest valid 1×1 JPEG, and
inline_images.json keeps each original's length and SHA-256.

One recipe keeps its real data-URIs — the exception that proves the decoder
writes a real JPEG and not the stub. Everything else in the HTML is untouched,
byte for byte: the 323 page divs, the 234 styled h3, the 229 img, the 116
timers and the 443 `#` of which 327 are CSS colours.

Usage:
    python3 tests/fixtures/grocy/extraire.py <copie-de-grocy.db> <dossier>
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

# Le plus petit JPEG 1×1 valide : 160 octets qui commencent par ffd8 et
# finissent par ffd9. Un stub plus court ne serait pas un JPEG, et les tests
# d'écriture d'image vérifient la signature.
STUB_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAAB"
    "AAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
)

# La recette qui garde ses data-URI intacts. La spec disait 41 ; la 41 n'en
# porte aucun (elle pointe une image hébergée). 69 est la première qui en
# porte, et elle en porte deux — cf. § 22 de la spec, amendement A1.
RECIPE_KEEPING_ITS_DATA_URIS = 69

# Les colonnes retenues, table par table. `None` = toutes. Projeter n'est pas
# de l'économie de bout de chandelle : le nom des colonnes pèse plus que les
# valeurs dans un JSON par ligne, et une colonne qu'aucun import ne lit n'a
# rien à faire dans une fixture — sa présence laisserait croire qu'elle
# compte. `grocy_reel_db` reconstruit exactement ces colonnes-là.
TABLES: dict[str, tuple[str, ...] | None] = {
    "recipes": None,
    "recipes_pos": (
        "id", "recipe_id", "product_id", "amount", "note", "qu_id",
        "ingredient_group", "not_check_stock_fulfillment", "variable_amount",
    ),
    "stock": None,
    "products": (
        "id", "name", "active", "location_id", "qu_id_stock", "qu_id_purchase",
        "calories", "product_group_id", "picture_file_name", "min_stock_amount",
        "not_check_stock_fulfillment_for_recipes",
        "default_best_before_days_after_open", "row_created_timestamp",
    ),
    "meal_plan": None,
    "meal_plan_sections": ("id", "name", "sort_number"),
    "shopping_list": (
        "id", "product_id", "note", "amount", "shopping_list_id", "done",
        "qu_id",
    ),
    "quantity_unit_conversions": (
        "id", "from_qu_id", "to_qu_id", "factor", "product_id",
    ),
    "quantity_units": ("id", "name", "name_plural", "active"),
    "locations": ("id", "name", "is_freezer", "active"),
    # L'archive du §9 : un nom de produit, une quantité, une unité, une date,
    # un type et le drapeau d'annulation. Rien d'autre — les 1 123 lignes ne
    # sont PAS réinjectées dans le journal, elles sont conservées lisibles.
    "stock_log": (
        "id", "product_id", "amount", "used_date", "spoiled",
        "transaction_type", "price", "undone", "row_created_timestamp",
    ),
    "chores_log": (
        "id", "chore_id", "tracked_time", "undone", "skipped",
        "row_created_timestamp",
    ),
    "chores": ("id", "name", "period_type"),
    # Ce que l'import du CATALOGUE (lot 0) lit. Les fixtures servent aussi à
    # rejouer la chaîne complète — catalogue puis stock — parce que c'est
    # exactement l'ordre de la bascule, et qu'un import de stock testé contre
    # un catalogue fabriqué à la main ne prouverait rien de cet ordre.
    "product_groups": ("id", "name", "active"),
    "product_barcodes": (
        "id", "product_id", "barcode", "qu_id", "amount", "last_price",
    ),
    "userfields": ("id", "entity", "name"),
    "userfield_values": ("id", "field_id", "object_id", "value"),
    # Vide chez Grocy : rien pour amorcer l'ordre des rayons du lot 4, et on
    # n'en fabrique pas. Extraite quand même pour que le test puisse le
    # PROUVER au lieu de le supposer.
    "shopping_locations": None,
}

DATA_URI = re.compile(r"(data:image/[a-zA-Z0-9.+-]+;base64,)([A-Za-z0-9+/=]+)")


def _refuse_production(path: Path) -> None:
    resolved = path.resolve()
    if str(resolved).startswith("/opt/nivuus/Grocy/"):
        print(f"REFUS : {resolved} est la base de production de Grocy.\n"
              "Copier le fichier ailleurs et relancer sur la copie.",
              file=sys.stderr)
        sys.exit(2)


def _stub_descriptions(recipes: list[dict]) -> list[dict]:
    """Replace every base64 payload by the stub, and record what it replaced."""
    inline: list[dict] = []
    for recipe in recipes:
        description = recipe.get("description") or ""
        if recipe["id"] == RECIPE_KEEPING_ITS_DATA_URIS:
            for rank, (_, payload) in enumerate(DATA_URI.findall(description)):
                inline.append(_note(recipe["id"], rank, payload, stubbed=False))
            continue
        rank = 0

        def _replace(match: re.Match[str]) -> str:
            nonlocal rank
            inline.append(_note(recipe["id"], rank, match.group(2), stubbed=True))
            rank += 1
            return match.group(1) + STUB_JPEG_B64

        recipe["description"] = DATA_URI.sub(_replace, description)
    return inline


def _note(recipe_id: int, rank: int, payload: str, *, stubbed: bool) -> dict:
    return {
        "recipe_id": recipe_id,
        "rank": rank,
        "original_base64_length": len(payload),
        "original_sha256": hashlib.sha256(payload.encode("ascii")).hexdigest(),
        "stubbed": stubbed,
    }


def main(source: str, destination: str) -> int:
    origin = Path(source)
    _refuse_production(origin)
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(f"file:{origin}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for table, columns in TABLES.items():
            selection = "*" if columns is None else ", ".join(columns)
            rows = [dict(row) for row in
                    conn.execute(f"SELECT {selection} FROM {table} ORDER BY id")]
            if table == "recipes":
                rows = [row for row in rows if str(row["type"]) in ("normal", "1")]
                inline = _stub_descriptions(rows)
                _dump(target / "inline_images.json", inline)
            _dump(target / f"{table}.json", rows)
    finally:
        conn.close()
    return 0


# Les colonnes d'une table vide : SELECT * ne les donne pas, et une table
# absente du schéma reconstruit ferait échouer une lecture légitime.
EMPTY_TABLE_COLUMNS = {
    "shopping_locations": ("id", "name"),
}


def _dump(path: Path, payload: list[dict]) -> None:
    """One row per line: a `git diff` shows the row that moved, and only it.

    A pretty-printed `indent=1` would be readable too — and would weigh eight
    times more, most of it whitespace and repeated key names. 1.7 MB of that
    is not a fixture, it is a liability.
    """
    lines = ",\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True)
                       for row in payload)
    path.write_text(f"[\n{lines}\n]\n" if payload else "[]\n", "utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    sys.exit(main(sys.argv[1], sys.argv[2]))
