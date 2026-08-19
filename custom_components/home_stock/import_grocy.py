"""One-way, replayable import of the Grocy catalogue.

Reads a read-only copy of grocy.db. Stock, history and recipes stay in Grocy: they
come over in lot 7. Every product and article keeps its Grocy id in external_ref,
so a second run changes nothing and lot 7 becomes a join instead of a name match —
name matching is what created 35 duplicates in April 2026.

A dry run (apply=False) must be able to prove the same anomalies a real run would
raise — that is the point of running it before writing anything — so the barcode
and price pass below is not gated behind apply the way the actual repo.* writes
are: it always walks the rows and always reports, and only the writes are skipped.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
MAX_KCAL_PER_ML = 8.1     # olive oil, the densest common liquid, tops out there —
                          # this is the household's actual highest value (81
                          # kcal/cl), so it only passes because the comparison
                          # below is strict (">", not ">=")


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


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


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
            # Resolve every already-imported product's generic article and base unit
            # by external_ref, not just its existence: a replay needs both to pick
            # up a barcode added in Grocy after the first import, without
            # re-creating the product itself. A price is only picked up alongside
            # a barcode that is new to this run — once a barcode is already
            # linked, the loop below `continue`s before reaching the price block,
            # so a price added later on an already-imported barcode is missed.
            article_ids: dict[int, int] = {}
            base_units: dict[int, str] = {}
            for row in conn.execute(
                "SELECT p.external_ref AS ref, p.base_unit AS base_unit, a.id AS article_id"
                " FROM product p JOIN article a ON a.product_id = p.id AND a.is_generic = 1"
                " WHERE p.external_ref IS NOT NULL"
            ):
                gid = int(row["ref"])
                article_ids[gid] = row["article_id"]
                base_units[gid] = row["base_unit"]
            known = set(article_ids)
            # Grocy ids that end up with an article — already known, or successfully
            # examined this run — and are therefore eligible for barcodes/prices.
            importable: set[int] = set(known)

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

            for row in grocy.execute("SELECT * FROM products ORDER BY name"):
                if not row["active"]:
                    report.skipped += 1
                    continue
                if row["id"] in known:
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
                if kcal is not None and base_unit == "ml" and kcal > MAX_KCAL_PER_ML:
                    report.anomalies.append(
                        f"{row['name']} : {kcal:.1f} kcal/ml est impossible")
                    continue
                if not row["name"]:
                    report.anomalies.append(f"produit Grocy {row['id']} sans nom")
                    continue
                # A product created by hand in home_stock before the import, or a
                # second Grocy product sharing a name, collides with the UNIQUE
                # constraint — exactly the April 2026 duplicate scenario the whole
                # external_ref scheme exists to prevent. Report it, keep going.
                if conn.execute(
                    "SELECT 1 FROM product WHERE name = ?", (row["name"],)
                ).fetchone():
                    report.anomalies.append(
                        f"{row['name']} : nom déjà utilisé par un produit existant")
                    continue
                # Reported, not skipped: category_id is nullable and the product
                # still imports, but design §10's control gate requires this
                # count to be visible so an uncategorised product does not go
                # unnoticed.
                if row["product_group_id"] is None:
                    report.anomalies.append(f"{row['name']} : sans catégorie")

                report.products += 1
                report.articles += 1
                importable.add(row["id"])
                base_units[row["id"]] = base_unit
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
                nova_value = custom.get("nova")
                article_ids[row["id"]] = repo.insert_article(
                    conn,
                    product_id=product_id,
                    is_generic=1,
                    kcal_per_base_unit=kcal,
                    brand=custom.get("marque"),
                    nutriscore=custom.get("nutriscore"),
                    nova=int(nova_value) if nova_value and nova_value.isdigit() else None,
                    ecoscore=custom.get("ecoscore"),
                    allergens=custom.get("allergenes"),
                    external_ref=str(row["id"]),
                )

            # Barcodes and prices, always inspected — even on a dry run — so the
            # report can be trusted *before* apply=True writes anything. Only the
            # actual repo.* calls below are gated behind apply.
            existing_barcodes = {
                row["code"]: row["article_id"] for row in conn.execute(
                    "SELECT code, article_id FROM barcode")
            }
            claimed_this_run: dict[str, int] = {}   # code -> grocy product id
            for row in grocy.execute("SELECT * FROM product_barcodes"):
                product_gid = row["product_id"]
                if product_gid not in importable:
                    continue
                code = row["barcode"]
                article_id = article_ids.get(product_gid)

                linked_to = existing_barcodes.get(code)
                if linked_to is not None:
                    if article_id is not None and linked_to == article_id:
                        continue   # already imported by an earlier run: a no-op
                    report.anomalies.append(f"code-barres {code} déjà attribué")
                    continue
                claimant = claimed_this_run.get(code)
                if claimant is not None and claimant != product_gid:
                    report.anomalies.append(f"code-barres {code} déjà attribué")
                    continue
                claimed_this_run[code] = product_gid

                report.barcodes += 1
                if apply and article_id is not None:
                    repo.link_barcode(conn, code, article_id)
                    existing_barcodes[code] = article_id

                if not row["last_price"]:
                    continue

                # last_price is per purchase unit, but is written as a price per
                # STOCK unit: convert only when the two resolve to the same base
                # unit. "Houmous bio Pascalou 160g" is bought by Pièce and stocked
                # in g — converting blindly would record a price per gram that is
                # actually a price per whole 160 g pack, wrong by that factor.
                stock_base = base_units.get(product_gid)
                price_unit = _base_unit(units.get(row["qu_id"], "?"))
                if not row["amount"]:
                    report.anomalies.append(
                        f"prix de {code} non convertible (quantité d'achat manquante)")
                elif price_unit is None:
                    report.anomalies.append(
                        f"prix de {code} non convertible (unité d'achat"
                        f" « {units.get(row['qu_id'], '?')} » inconnue)")
                elif stock_base is None or price_unit[0] != stock_base:
                    report.anomalies.append(
                        f"prix de {code} non convertible (unité d'achat incompatible"
                        " avec l'unité de stock)")
                else:
                    per_base = row["last_price"] / (row["amount"] * price_unit[1])
                    report.prices += 1
                    if apply and article_id is not None:
                        repo.insert_price(
                            conn, article_id=article_id, observed_on=_today(),
                            price_per_base_unit=per_base, source="import",
                        )

            if not apply:
                conn.rollback()
    finally:
        grocy.close()
    return report
