"""One-way, replayable import of the Grocy catalogue.

Reads a read-only copy of grocy.db. Stock, history and recipes stay in Grocy: they
come over in lot 7. Every product and article keeps its Grocy id in external_ref,
so a second run changes nothing and lot 7 becomes a join instead of a name match —
name matching is what created 35 duplicates in April 2026.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from .storage import repositories as repo
from .storage.database import Database

MASS_UNITS = {"g": 1.0, "kg": 1000.0}
VOLUME_UNITS = {"ml": 1.0, "cl": 10.0, "l": 1000.0}
CONTAINER_UNITS = {
    "Pièce", "Paquet", "Pot", "Bouteille", "Barquette", "Brique", "Boîte",
    "Sachet", "Lot",
}
DOSAGE_UNITS = {"cs", "cc"}
MAX_KCAL_PER_GRAM = 9.5   # pure fat is 9; above that the value is wrong


@dataclass
class ImportReport:
    """What was written, and what must be looked at by hand."""

    products: int = 0
    articles: int = 0
    barcodes: int = 0
    prices: int = 0
    categories: int = 0
    locations: int = 0
    skipped: int = 0
    anomalies: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.anomalies

    def as_dict(self) -> dict[str, Any]:
        return {
            "products": self.products, "articles": self.articles,
            "barcodes": self.barcodes, "prices": self.prices,
            "categories": self.categories, "locations": self.locations,
            "skipped": self.skipped, "anomalies": self.anomalies, "ok": self.ok,
        }


def _base_unit(unit_name: str) -> tuple[str, float] | None:
    if unit_name in MASS_UNITS:
        return "g", MASS_UNITS[unit_name]
    if unit_name in VOLUME_UNITS:
        return "ml", VOLUME_UNITS[unit_name]
    if unit_name in CONTAINER_UNITS:
        return "piece", 1.0
    return None


def _open_grocy(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def import_catalog(db: Database, grocy_path: str, *, apply: bool = False) -> ImportReport:
    """Copy the Grocy catalogue over. Without apply=True, nothing is written."""
    report = ImportReport()
    grocy = _open_grocy(grocy_path)
    try:
        units = {row["id"]: row["name"] for row in grocy.execute("SELECT * FROM quantity_units")}
        fields = {
            row["id"]: row["name"]
            for row in grocy.execute("SELECT * FROM userfields WHERE entity = 'products'")
        }
        values: dict[int, dict[str, str]] = {}
        for row in grocy.execute("SELECT * FROM userfield_values"):
            name = fields.get(row["field_id"])
            if name:
                values.setdefault(row["object_id"], {})[name] = row["value"]

        with db.write() as conn:
            known = {
                row["external_ref"]
                for row in conn.execute(
                    "SELECT external_ref FROM product WHERE external_ref IS NOT NULL")
            }

            location_ids: dict[int, int] = {}
            for row in grocy.execute("SELECT * FROM locations"):
                existing = conn.execute(
                    "SELECT id FROM location WHERE name = ?", (row["name"],)).fetchone()
                if existing:
                    location_ids[row["id"]] = existing["id"]
                    continue
                report.locations += 1
                if apply:
                    location_ids[row["id"]] = repo.insert_location(
                        conn, name=row["name"],
                        kind="freezer" if row["is_freezer"] else "pantry",
                    )

            category_ids: dict[int, int] = {}
            for row in grocy.execute("SELECT * FROM product_groups"):
                existing = conn.execute(
                    "SELECT id FROM category WHERE name = ?", (row["name"],)).fetchone()
                if existing:
                    category_ids[row["id"]] = existing["id"]
                    continue
                report.categories += 1
                if apply:
                    category_ids[row["id"]] = repo.insert_category(conn, row["name"])

            article_ids: dict[int, int] = {}
            for row in grocy.execute("SELECT * FROM products ORDER BY name"):
                if not row["active"]:
                    report.skipped += 1
                    continue
                if str(row["id"]) in known:
                    continue
                unit_name = units.get(row["qu_id_stock"], "?")
                if unit_name in DOSAGE_UNITS:
                    report.anomalies.append(
                        f"{row['name']} : unité de stock « {unit_name} » est une unité"
                        " de dosage, pas une unité de stock"
                    )
                    continue
                mapped = _base_unit(unit_name)
                if mapped is None:
                    report.anomalies.append(
                        f"{row['name']} : unité de stock « {unit_name} » inconnue")
                    continue
                base_unit, factor = mapped

                kcal = None if row["calories"] is None else row["calories"] / factor
                if kcal is not None and base_unit == "g" and kcal > MAX_KCAL_PER_GRAM:
                    report.anomalies.append(
                        f"{row['name']} : {kcal:.1f} kcal/g est impossible")
                    continue
                if not row["name"]:
                    report.anomalies.append(f"produit Grocy {row['id']} sans nom")
                    continue

                report.products += 1
                report.articles += 1
                if not apply:
                    continue

                product_id = repo.insert_product(
                    conn,
                    name=row["name"],
                    base_unit=base_unit,
                    category_id=category_ids.get(row["product_group_id"]),
                    default_location_id=location_ids.get(row["location_id"]),
                    min_quantity=None if row["min_stock_amount"] is None
                    else row["min_stock_amount"] * factor,
                    days_after_opening=row["default_best_before_days_after_open"] or None,
                    reference_kcal=kcal,
                    external_ref=str(row["id"]),
                )
                custom = values.get(row["id"], {})
                article_ids[row["id"]] = repo.insert_article(
                    conn,
                    product_id=product_id,
                    is_generic=1,
                    kcal_per_base_unit=kcal,
                    brand=custom.get("marque"),
                    nutriscore=custom.get("nutriscore"),
                    nova=int(custom["nova"]) if custom.get("nova", "").isdigit() else None,
                    ecoscore=custom.get("ecoscore"),
                    allergens=custom.get("allergenes"),
                    external_ref=str(row["id"]),
                )

            for row in grocy.execute("SELECT * FROM product_barcodes"):
                article_id = article_ids.get(row["product_id"])
                if article_id is None:
                    continue
                report.barcodes += 1
                if not apply:
                    continue
                existing = conn.execute(
                    "SELECT 1 FROM barcode WHERE code = ?", (row["barcode"],)).fetchone()
                if existing:
                    report.anomalies.append(
                        f"code-barres {row['barcode']} déjà attribué")
                    continue
                repo.link_barcode(conn, row["barcode"], article_id)

                # last_price is per purchase unit: convert only when it is unambiguous.
                price_unit = _base_unit(units.get(row["qu_id"], "?"))
                if row["last_price"] and row["amount"] and price_unit:
                    per_base = row["last_price"] / (row["amount"] * price_unit[1])
                    repo.insert_price(
                        conn, article_id=article_id, observed_on="2026-08-18",
                        price_per_base_unit=per_base, source="import",
                    )
                    report.prices += 1
                elif row["last_price"]:
                    report.anomalies.append(
                        f"prix de {row['barcode']} non convertible (unité ou quantité"
                        " d'achat manquante)"
                    )

            if not apply:
                conn.rollback()
    finally:
        grocy.close()
    return report
