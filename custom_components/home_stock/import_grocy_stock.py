"""One-way, replayable import of what Grocy still holds: the stock itself.

Reads a read-only copy of grocy.db, exactly like the lot 0 catalogue import.
Nothing is written without apply=True, so the report can be read in full
before anything moves.

**The join, not the match.** Of the 108 stock rows, 107 resolve to a
home_stock product by `external_ref` — the Grocy id kept at lot 0 for this
very reason. The 108th is the Sorbet Fraise created on 21 August, which the
catalogue replay (gesture 6 of the shutdown procedure) brings in. Lot 3's
scoring matcher is never called: every batch knows its product by id. The
fallback "by name" that created 35 duplicates in April 2026 does not exist
here, and must not be added.

The Grocy query aliases `s` for stock and `prod` for products: the repository
forbids the literal `SELECT b.*` through a scan that does not tell tables
apart, so no table in this lot is ever aliased `b`.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping, NamedTuple

from .const import (
    GROCY_MAX_BATCH_VALUE,
    GROCY_NEVER_EXPIRES,
    GROCY_STOCK_REF_PREFIX,
    REASON_PURCHASE,
)
from .grocy.units import base_unit
from .storage import repositories as repo

# Sous ce seuil, en unité de base, la quantité est de la poussière flottante :
# le lot #537 porte 5,55e-17 « Pot » de fromage fouetté. Il entre CLOS, avec
# remaining = 0 — l'ignorer serait un écart de comptage au contrôle C1, ce qui
# n'est pas la même chose qu'un pot vide.
DUST_THRESHOLD = 0.001

# Le dernier cran de la cascade d'emplacement, et le seul nom que ce module
# crée s'il manque.
FALLBACK_LOCATION_NAME = "Autre"
# Corrigé PAR NOM EXACT, une seule ligne. Aucun autre nom n'est deviné.
FRIDGE_NAME = "Frigo"


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


class StockImportError(Exception):
    """A batch whose Grocy product is not in the catalogue. The only hard stop.

    After the catalogue replay this cannot happen. If it does, someone wrote
    into Grocy during the switchover — and then nothing that follows is worth
    anything.
    """


class CatalogueEntry(NamedTuple):
    """What home_stock knows about one Grocy product id."""

    product_id: int
    article_id: int
    name: str
    base_unit: str
    default_location_id: int | None


class Locations(NamedTuple):
    """Grocy location ids mapped onto home_stock's, plus the last resort.

    Location id 1 was deleted from Grocy's referential and two batches still
    point at it — the same defect as the unit id 1 that debloquer_unites.py
    had to repair in August. It is simply absent from `by_grocy_id`.
    """

    by_grocy_id: Mapping[int, int]
    fallback_id: int


@dataclass(frozen=True)
class PlannedBatch:
    """One batch, computed, before any write."""

    grocy_stock_id: int
    product_id: int
    article_id: int
    base_unit: str
    quantity: float
    best_before: str | None
    price_per_base_unit: float | None
    location_id: int
    opened_at: str | None
    entered_at: str
    closed: bool
    external_ref: str


def _entered_at(row: Mapping[str, Any]) -> str:
    """The purchase date, or failing that the row's own creation stamp.

    28 rows have no purchased_date. A batch has to have entered somewhere, and
    the moment Grocy wrote the row is the only other thing that is true.
    """
    return (row.get("purchased_date")
            or (row.get("row_created_timestamp") or "").split(" ")[0]
            or "")


def _location(row: Mapping[str, Any], entry: CatalogueEntry,
              locations: Locations, anomalies: list[str]) -> int:
    """The cascade, in its three rungs. A batch is NEVER refused for its
    location: a badly stored packet is still a packet you own."""
    resolved = locations.by_grocy_id.get(row.get("location_id"))
    if resolved is not None:
        return resolved
    if entry.default_location_id is not None:
        return entry.default_location_id
    anomalies.append(
        f"{entry.name} (lot Grocy {row['id']}) : emplacement introuvable,"
        " rangé dans « Autre »")
    return locations.fallback_id


def _price(row: Mapping[str, Any], entry: CatalogueEntry, factor: float,
           anomalies: list[str]) -> float | None:
    """The price per base unit, or None.

    Grocy writes 0.0 as often as NULL for "no price": both mean unknown, and
    neither becomes 0.0 here. Zero would read as "measured at zero", which is
    invisible in sensor.home_stock_stock_value; NULL is counted and shown by
    `unpriced_batches`.

    Above GROCY_MAX_BATCH_VALUE, `amount × price` is not a clumsy price but a
    receipt line hung on the wrong product. The note is the PROOF of the
    defect — four of the seven name a different product than the one the batch
    is attached to — so it is quoted word for word: batch.note does not exist,
    and the report is where it has to be readable.
    """
    price = row.get("price")
    if not price:
        return None
    value = row["amount"] * price
    if value > GROCY_MAX_BATCH_VALUE:
        note = row.get("note") or "sans note"
        anomalies.append(
            f"{entry.name} (lot Grocy {row['id']}) : prix écarté —"
            f" {row['amount']} × {price} = {value:.2f} EUR, au-delà de"
            f" {GROCY_MAX_BATCH_VALUE} EUR. Note Grocy : « {note} »")
        return None
    return price / factor


def plan_batches(grocy_rows, catalogue: Mapping[int, CatalogueEntry],
                 locations: Locations, *,
                 today: str) -> tuple[list[PlannedBatch], list[str]]:
    """Compute the batches, and the anomalies, touching no database at all."""
    planned: list[PlannedBatch] = []
    anomalies: list[str] = []
    for row in grocy_rows:
        entry = catalogue.get(row["product_id"])
        if entry is None:
            raise StockImportError(
                f"lot Grocy {row['id']} : le produit {row['product_id']}"
                " n'est pas au catalogue de home_stock — rejouer"
                " import_grocy_catalog avant de continuer")

        mapped = base_unit(row["unit"])
        if mapped is None:
            anomalies.append(
                f"{entry.name} (lot Grocy {row['id']}) :"
                f" unité « {row['unit']} » inconnue")
            continue
        unit, factor = mapped
        if unit != entry.base_unit:
            # Convertir des kilogrammes dans un produit stocké à la pièce
            # écrirait 1 500 « pièces ». Aucune devinette : le lot n'entre pas.
            anomalies.append(
                f"{entry.name} (lot Grocy {row['id']}) : unité « {row['unit']} »"
                f" donne « {unit} », mais le produit est stocké en"
                f" « {entry.base_unit} »")
            continue

        quantity = row["amount"] * factor
        closed = quantity < DUST_THRESHOLD
        if closed:
            quantity = 0.0
        # Aucun arrondi : 0,08 concombre et 12,875 œufs entrent tels quels.

        best_before = row.get("best_before_date")
        if best_before == GROCY_NEVER_EXPIRES:
            # Recopier la sentinelle donnerait dix lots qui périment dans neuf
            # cent soixante-treize ans, en tête de tous les tris décroissants.
            best_before = None

        # La DLC ne se recalcule PAS à l'ouverture : la règle du lot 0 §7.6
        # vaut pour le GESTE d'ouvrir, pas pour la constatation qu'un paquet
        # est ouvert depuis six mois.
        opened_at = None
        if row.get("open"):
            opened_at = row.get("opened_date") or _entered_at(row)

        planned.append(PlannedBatch(
            grocy_stock_id=row["id"],
            product_id=entry.product_id,
            article_id=entry.article_id,
            base_unit=unit,
            quantity=quantity,
            best_before=best_before,
            price_per_base_unit=_price(row, entry, factor, anomalies),
            location_id=_location(row, entry, locations, anomalies),
            opened_at=opened_at,
            entered_at=_entered_at(row),
            closed=closed,
            external_ref=f"{GROCY_STOCK_REF_PREFIX}{row['id']}",
        ))
    return planned, anomalies


@dataclass
class StockReport:
    """What was written, and what must be looked at by hand."""

    batches: int = 0
    movements: int = 0
    packagings: int = 0
    list_items: int = 0
    skipped: int = 0
    anomalies: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.anomalies

    def as_dict(self) -> dict[str, Any]:
        return {
            "batches": self.batches, "movements": self.movements,
            "packagings": self.packagings, "list_items": self.list_items,
            "skipped": self.skipped, "anomalies": self.anomalies, "ok": self.ok,
        }


def _open_grocy(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _catalogue_within(conn) -> dict[int, CatalogueEntry]:
    """What home_stock already knows, keyed by Grocy product id.

    Resolved by `external_ref`, never by name: the fallback by name is what
    created 35 duplicates in April 2026.
    """
    catalogue: dict[int, CatalogueEntry] = {}
    for row in conn.execute(
        "SELECT prod.external_ref AS ref, prod.id AS product_id,"
        "       prod.name AS name, prod.base_unit AS base_unit,"
        "       prod.default_location_id AS default_location_id,"
        "       art.id AS article_id"
        " FROM product AS prod"
        " JOIN article AS art ON art.product_id = prod.id AND art.is_generic = 1"
        " WHERE prod.external_ref IS NOT NULL"
    ):
        catalogue[int(row["ref"])] = CatalogueEntry(
            product_id=row["product_id"], article_id=row["article_id"],
            name=row["name"], base_unit=row["base_unit"],
            default_location_id=row["default_location_id"])
    return catalogue


def _locations_within(conn, grocy) -> Locations:
    """Grocy location ids mapped onto home_stock's, by NAME — the same pairing
    the lot 0 import made when it created them."""
    par_nom = {row["name"]: row["id"] for row in
               conn.execute("SELECT id, name FROM location")}
    by_grocy_id: dict[int, int] = {}
    for row in grocy.execute("SELECT id, name FROM locations WHERE active = 1"):
        home = par_nom.get(row["name"])
        if home is not None:
            by_grocy_id[row["id"]] = home
    fallback = par_nom.get(FALLBACK_LOCATION_NAME)
    if fallback is None:
        fallback = repo.insert_location(conn, name=FALLBACK_LOCATION_NAME,
                                        kind="pantry")
    return Locations(by_grocy_id=by_grocy_id, fallback_id=fallback)


def _stock_rows(grocy) -> list[dict[str, Any]]:
    """The 108 stock rows, joined to their product.

    `s` for stock, `prod` for products, `qu` for the unit: no table in this
    lot is ever aliased `b`, because the repository forbids the literal
    `SELECT b.*` through a scan that does not tell tables apart.
    """
    return [dict(row) for row in grocy.execute(
        "SELECT s.id AS id, s.product_id AS product_id, s.amount AS amount,"
        "       s.best_before_date AS best_before_date,"
        "       s.purchased_date AS purchased_date, s.price AS price,"
        "       s.open AS open, s.opened_date AS opened_date,"
        "       s.location_id AS location_id, s.note AS note,"
        "       s.row_created_timestamp AS row_created_timestamp,"
        "       qu.name AS unit, prod.name AS product_name"
        " FROM stock AS s"
        " JOIN products AS prod ON prod.id = s.product_id"
        " LEFT JOIN quantity_units AS qu ON qu.id = prod.qu_id_stock"
        " ORDER BY s.id")]


def _existing_refs_within(conn) -> set[str]:
    return {row["external_ref"] for row in conn.execute(
        "SELECT external_ref FROM batch WHERE external_ref IS NOT NULL")}


def _fix_fridge_within(conn, report: StockReport) -> None:
    """"Frigo" is a fridge, not a cupboard.

    Inherited defect from lot 0: the catalogue import maps location.kind onto
    `is_freezer`, and Grocy has no "refrigerator" flag, so "Frigo" landed as
    `pantry`. Corrected here BY EXACT NAME, one row, and reported. No other
    name is guessed — a location called "Cave" is not a cellar because it
    sounds like one.
    """
    row = conn.execute(
        "SELECT id, kind FROM location WHERE name = ?", (FRIDGE_NAME,)).fetchone()
    if row is None or row["kind"] == "fridge":
        return
    conn.execute("UPDATE location SET kind = 'fridge' WHERE id = ?", (row["id"],))
    report.anomalies.append(
        f"emplacement « {FRIDGE_NAME} » : type corrigé de « {row['kind']} » en"
        " « fridge » (Grocy ne distingue que le congélateur)")


def import_stock(db, grocy_path: str, *, apply: bool = False) -> StockReport:
    """Bring the stock over. Without apply=True, nothing is written.

    ONE transaction, and only one. `Database._lock` is NOT reentrant: two
    nested `db.write()` freeze the process without raising — no failure, no
    trace, a test that never hands back control. Every helper below takes
    `conn`, never `db`.

    One entry movement per batch, because lot 0 § 12 states that "the journal
    being append-only, it is enough to rebuild everything". A hundred and
    eight batches appearing without a journal line would break that invariant:
    the database would no longer be able to say where its stock came from.
    It fudges nothing: `repo.totals_between()` — the single source of
    kcal_total, cost_total and cost_waste_total — only sums consumption
    reasons. A purchase never enters it. That is control C6.
    """
    report = StockReport()
    grocy = _open_grocy(grocy_path)
    try:
        with db.write() as conn:                # UNE transaction, et une seule
            catalogue = _catalogue_within(conn)
            locations = _locations_within(conn, grocy)
            planned, anomalies = plan_batches(
                _stock_rows(grocy), catalogue, locations, today=_today())
            report.anomalies.extend(anomalies)

            deja = _existing_refs_within(conn)
            for lot in planned:
                if lot.external_ref in deja:
                    # JAMAIS de réécriture : on a mangé depuis. Remettre
                    # remaining = initial déferait une consommation réelle sans
                    # laisser de trace, et movement est en ajout seul.
                    report.skipped += 1
                    continue
                report.batches += 1
                report.movements += 1
                if not apply:
                    continue
                batch_id = repo.insert_batch(
                    conn, article_id=lot.article_id, location_id=lot.location_id,
                    quantity=lot.quantity, entered_at=lot.entered_at,
                    best_before=lot.best_before,
                    price_per_base_unit=lot.price_per_base_unit)
                # `repo.insert_batch` ne prend pas external_ref, et n'a pas à
                # l'apprendre : élargir un insert_* du dépôt avec un **fields
                # ouvrirait une porte sur `remaining`.
                conn.execute(
                    "UPDATE batch SET external_ref = ?, opened_at = ?,"
                    "       closed_at = ? WHERE id = ?",
                    (lot.external_ref, lot.opened_at,
                     lot.entered_at if lot.closed else None, batch_id))
                repo.insert_movement(
                    conn, occurred_at=lot.entered_at, product_id=lot.product_id,
                    article_id=lot.article_id, batch_id=batch_id,
                    quantity=lot.quantity, reason=REASON_PURCHASE,
                    base_unit=lot.base_unit, kcal=None, cost=None,
                    idempotency_key=lot.external_ref)

            _fix_fridge_within(conn, report)
            if not apply:
                conn.rollback()
    finally:
        grocy.close()
    return report
