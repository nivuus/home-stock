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

from dataclasses import dataclass
from typing import Any, Mapping, NamedTuple

from .const import (
    GROCY_MAX_BATCH_VALUE,
    GROCY_NEVER_EXPIRES,
    GROCY_STOCK_REF_PREFIX,
)
from .grocy.units import base_unit

# Sous ce seuil, en unité de base, la quantité est de la poussière flottante :
# le lot #537 porte 5,55e-17 « Pot » de fromage fouetté. Il entre CLOS, avec
# remaining = 0 — l'ignorer serait un écart de comptage au contrôle C1, ce qui
# n'est pas la même chose qu'un pot vide.
DUST_THRESHOLD = 0.001


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
