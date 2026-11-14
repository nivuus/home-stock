"""The pure half of the Grocy stock import: planning batches from Grocy rows.

No database, no file: `plan_batches` turns Grocy's stock rows and what
home_stock already knows into the batches to write, and the anomalies to
look at. `import_grocy_stock` reads both sides and writes the plan; it
re-exports every name defined here, so callers import from it unchanged.
"""
# policy: allow-fr-file - the comments below were moved verbatim from
# import_grocy_stock.py, written before the English rule; not translated here.
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

# Le dernier cran de la cascade d'emplacement, et le seul nom que ce module
# crée s'il manque.
FALLBACK_LOCATION_NAME = "Autre"
# Corrigé PAR NOM EXACT, une seule ligne. Aucun autre nom n'est deviné.
FRIDGE_NAME = "Frigo"


class StockImportError(ValueError):
    """A batch whose Grocy product is not in the catalogue. The only hard stop.

    A `ValueError` on purpose: `services._run` translates that family into a
    French refusal, and `websocket_api` does the same. A bare Exception would
    reach the log as a raw Python traceback on one surface and as nothing at
    all on the other — the weaker-surface asymmetry this lot forbids.

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
