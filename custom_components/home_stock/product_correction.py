"""The `home_stock.update_product` service: correct a product's kcal and unit.

Both corrections existed only in the panel: `reference_kcal` through the
websocket command `home_stock/product/update`, `base_unit` through
`home_stock/product/convert_unit`. Neither could be called from Developer
Tools → Actions, a script or an automation. This service runs the same code,
not a copy of it:

- the kcal is read by `websocket_api.PRODUCT_EDITABLE["reference_kcal"]`, the
  validator `product/update` uses, and written the way `product/update`
  writes it (`repo.update_product_fields`);
- the unit is changed by `conversion_execution`, the body of
  `StockManager.convert_product_unit` that `product/convert_unit` runs, with
  its refusals translated by `websocket_api._translate_conversion_error`.

Both in ONE transaction: a conversion and a kcal written together, or
nothing. A kcal given with a unit is read in the NEW unit (kcal per gram once
`target_unit` is "g") and wins over the one the conversion recomputes.

`unchanged_batches` names the open batches whose quantity is already in the
new unit — "80" typed for 80 g under a product counted in pieces: they keep
their quantity and their price (see `conversion_execution`).

A dry run writes nothing: the corrections are carried out inside the
transaction, read back, and the transaction is rolled back. The plan it
answers is therefore what the real run does, not a second computation of it
that could drift — batch by batch, with the kcal rate each batch really
counts (its own, else its article's, else the product's: `KCAL_RATE_SQL`).

Kept out of `services.py`, already far over this project's line limit.
Registration is called once, from `__init__.py`.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from typing import Any, Final

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .application import StockManager, _now
from .const import DOMAIN
from .conversion_execution import (
    KeptBatchError,
    PreparedConversion,
    conversion_report,
    execute_conversion,
    prepare_conversion,
)
from .domain.conversion import ConversionError
from .messages import french_message
from .services import _entry, _run
from .storage import repositories as repo
from .validators import bounded_int, finite_float, preview
from .websocket_api import PRODUCT_EDITABLE, _translate_conversion_error

SERVICE_UPDATE_PRODUCT: Final = "update_product"
TARGET_UNITS: Final = ("g", "ml")
# The packaging a conversion creates, "1 unité = <reference_quantity>": the
# default of the panel's `product/convert_unit`, so both surfaces name it alike.
PACKAGING_NAME: Final = "unité"

_FIELDS: Final = ("product_id", "reference_kcal", "target_unit", "reference_quantity",
                  "unchanged_batches", "dry_run")
# Every field is read by `parse_request`, which refuses in French; the schema
# only says which keys exist, so that a wrong value never meets an English
# voluptuous message first.
UPDATE_PRODUCT_SCHEMA: Final = vol.Schema(
    {vol.Optional(field): cv.match_all for field in _FIELDS})

NOTHING_TO_CORRECT: Final = (
    "Rien à corriger : donnez reference_kcal, ou target_unit avec reference_quantity, "
    "ou les deux.")


class CorrectionRefused(Exception):
    """A correction refused before anything is written. The message is French.

    Not a `ValueError`: `services._run` translates those generically, and this
    message is already the sentence to show.
    """


@dataclass(frozen=True)
class CorrectionRequest:
    """What to correct, read and checked by `parse_request`."""

    product_id: int
    kcal_given: bool = False
    reference_kcal: float | None = None
    target_unit: str | None = None
    reference_quantity: float | None = None
    unchanged_batches: tuple[int, ...] = ()
    dry_run: bool = False


class _RolledBack(Exception):
    """Carries a dry run's answer out of the transaction it rolls back."""

    def __init__(self, answer: dict[str, Any]) -> None:
        super().__init__("dry run")
        self.answer = answer


# --- reading the request -------------------------------------------------------

def _read(field: str, validator: Callable[[Any], Any], value: Any) -> Any:
    try:
        return validator(value)
    except vol.Invalid as error:
        raise CorrectionRefused(f"{field} : {french_message(error)}") from error


def _read_kcal(value: Any) -> float | None:
    try:
        kcal: float | None = PRODUCT_EDITABLE["reference_kcal"](value)
    except vol.Invalid as error:
        raise CorrectionRefused(
            "reference_kcal doit être un nombre positif ou nul : les kcal d'une unité de "
            "base du produit (d'un gramme avec target_unit « g »), ou null pour "
            f"l'effacer (reçu : {preview(value)}).") from error
    return kcal


def _read_batch_ids(value: Any) -> tuple[int, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        raise CorrectionRefused(
            "unchanged_batches doit être un identifiant de lot ou une liste "
            f"d'identifiants de lots (reçu : {preview(value)}).")
    items = value if isinstance(value, (list, tuple)) else (value,)
    return tuple(sorted({_read("unchanged_batches", bounded_int, item) for item in items}))


def parse_request(data: Mapping[str, Any]) -> CorrectionRequest:
    """Read a call's data, or raise `CorrectionRefused` in French."""
    if data.get("product_id") is None:
        raise CorrectionRefused(
            "product_id est obligatoire : l'identifiant du produit à corriger.")
    product_id: int = _read("product_id", bounded_int, data["product_id"])
    kcal_given = "reference_kcal" in data
    reference_kcal = _read_kcal(data["reference_kcal"]) if kcal_given else None
    dry_run = data.get("dry_run", False)
    if not isinstance(dry_run, bool):
        raise CorrectionRefused(f"dry_run doit valoir true ou false (reçu : {preview(dry_run)}).")

    target_unit = data.get("target_unit")
    raw_quantity = data.get("reference_quantity")
    if target_unit is None:
        for field in ("reference_quantity", "unchanged_batches"):
            if data.get(field) is not None:
                raise CorrectionRefused(
                    f"{field} ne sert qu'avec target_unit, l'unité vers laquelle "
                    "convertir le produit (« g » ou « ml »).")
        if not kcal_given:
            raise CorrectionRefused(NOTHING_TO_CORRECT)
        return CorrectionRequest(product_id=product_id, kcal_given=True,
                                 reference_kcal=reference_kcal, dry_run=dry_run)

    if target_unit not in TARGET_UNITS:
        raise CorrectionRefused(
            f"L'unité cible doit être « g » ou « ml » (reçu : {preview(target_unit)}).")
    if raw_quantity is None:
        raise CorrectionRefused(
            f"target_unit demande reference_quantity : combien de {target_unit} fait une "
            "pièce de ce produit aujourd'hui, par exemple le poids net du paquet.")
    reference_quantity: float = _read("reference_quantity", finite_float, raw_quantity)
    return CorrectionRequest(
        product_id=product_id, kcal_given=kcal_given, reference_kcal=reference_kcal,
        target_unit=str(target_unit), reference_quantity=reference_quantity,
        unchanged_batches=_read_batch_ids(data.get("unchanged_batches")), dry_run=dry_run)


# --- carrying it out -------------------------------------------------------------

def _kept_batch_message(error: KeptBatchError) -> str:
    ids = ", ".join(str(batch_id) for batch_id in error.batch_ids)
    if len(error.batch_ids) == 1:
        said = f"Le lot {ids} n'est pas un lot ouvert du produit {error.product_id}"
    else:
        said = f"Les lots {ids} ne sont pas des lots ouverts du produit {error.product_id}"
    return f"{said} : unchanged_batches ne nomme que des lots encore ouverts de ce produit."


def _prepare(conn: Any, product: dict[str, Any],
             request: CorrectionRequest) -> PreparedConversion:
    assert request.target_unit is not None and request.reference_quantity is not None
    try:
        return prepare_conversion(conn, product, to_unit=request.target_unit,
                                  reference_quantity=request.reference_quantity,
                                  kept_batches=request.unchanged_batches)
    except KeptBatchError as error:
        raise CorrectionRefused(_kept_batch_message(error)) from error
    except ConversionError as error:
        raise CorrectionRefused(_translate_conversion_error(error, product)) from error


def _already_converted(product: dict[str, Any], request: CorrectionRequest) -> dict[str, Any]:
    """What `product/convert_unit` answers for a unit the product already has."""
    return {
        "product_id": product["id"], "product_name": product["name"],
        "from_unit": product["base_unit"], "to_unit": request.target_unit,
        "reference_quantity": request.reference_quantity, "articles": 0,
        "batches": 0, "movements": 0, "articles_using_reference": [],
        "applied": False, "already_converted": True,
    }


def _open_batches(conn: Any, product_id: int) -> dict[int, dict[str, Any]]:
    return {row["id"]: row for row in repo.list_batches_for_product(conn, product_id)}


def _articles(conn: Any, product_id: int) -> dict[int, dict[str, Any]]:
    return {row["id"]: row for row in repo.list_articles_for_product(conn, product_id)}


def _batches_plan(before: dict[int, dict[str, Any]],
                  after: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    lines = []
    for batch_id in sorted(before):
        old, new = before[batch_id], after.get(batch_id, before[batch_id])
        lines.append({
            "batch_id": batch_id,
            "remaining_before": old["remaining"], "remaining_after": new["remaining"],
            "initial_before": old["initial"], "initial_after": new["initial"],
            "unchanged": (old["remaining"], old["initial"]) == (new["remaining"],
                                                                new["initial"]),
            "kcal_per_base_unit_before": old["kcal_per_base_unit"],
            "kcal_per_base_unit_after": new["kcal_per_base_unit"],
        })
    return lines


def _articles_plan(before: dict[int, dict[str, Any]], after: dict[int, dict[str, Any]],
                   factors: Mapping[int, float]) -> list[dict[str, Any]]:
    return [{
        "article_id": article_id, "label": before[article_id]["label"],
        "factor": factors.get(article_id),
        "kcal_per_base_unit_before": before[article_id]["kcal_per_base_unit"],
        "kcal_per_base_unit_after": after[article_id]["kcal_per_base_unit"],
    } for article_id in sorted(before)]


def _correct_within(conn: Any, request: CorrectionRequest, *,
                    occurred_at: str) -> dict[str, Any]:
    product = repo.get_product(conn, request.product_id)
    if product is None:
        raise CorrectionRefused(f"Produit {request.product_id} inconnu.")
    product_id = int(product["id"])
    batches_before = _open_batches(conn, product_id)
    articles_before = _articles(conn, product_id)

    conversion: dict[str, Any] | None = None
    factors: dict[int, float] = {}
    if request.target_unit is not None and product["base_unit"] == request.target_unit:
        conversion = _already_converted(product, request)
    elif request.target_unit is not None:
        prepared = _prepare(conn, product, request)
        execute_conversion(conn, prepared, packaging_name=PACKAGING_NAME,
                           occurred_at=occurred_at)
        conversion = {**conversion_report(prepared), "applied": not request.dry_run,
                      "already_converted": False}
        factors = {article.article_id: article.factor for article in prepared.plan.articles}
    if request.kcal_given:
        # After the conversion, so the kcal given is the one left standing:
        # it is read in the new unit, the recomputed one is only a fallback.
        repo.update_product_fields(conn, product_id,
                                   {"reference_kcal": request.reference_kcal})

    after = repo.get_product(conn, product_id)
    assert after is not None
    wrote = request.kcal_given or bool(conversion and not conversion["already_converted"])
    return {
        "product_id": product_id, "product_name": product["name"],
        "dry_run": request.dry_run, "applied": wrote and not request.dry_run,
        "conversion": conversion,
        "base_unit": {"before": product["base_unit"], "after": after["base_unit"]},
        "reference_kcal": {"before": product["reference_kcal"],
                           "after": after["reference_kcal"]},
        "batches_plan": _batches_plan(batches_before, _open_batches(conn, product_id)),
        "articles_plan": _articles_plan(articles_before, _articles(conn, product_id),
                                        factors),
    }


def correct_product(manager: StockManager, request: CorrectionRequest, *,
                    occurred_at: str) -> dict[str, Any]:
    """Correct the product in one transaction, or roll it back for a dry run.

    Raises `CorrectionRefused` (French) before anything is committed.
    """
    try:
        with manager.db.write() as conn:
            answer = _correct_within(conn, request, occurred_at=occurred_at)
            if request.dry_run:
                raise _RolledBack(answer)
    except _RolledBack as dry_run:
        return dry_run.answer
    return answer


# --- the Home Assistant service ----------------------------------------------------

async def async_handle_update_product(hass: HomeAssistant,
                                      call: ServiceCall) -> ServiceResponse:
    """Correct the product asked for; answer the plan when asked to."""
    try:
        request = parse_request(call.data)
    except CorrectionRefused as error:
        raise ServiceValidationError(str(error)) from error
    runtime = _entry(hass).runtime_data
    try:
        answer: dict[str, Any] = await _run(hass, partial(
            correct_product, runtime.manager, request, occurred_at=_now()))
    except CorrectionRefused as error:
        raise ServiceValidationError(str(error)) from error
    if answer["applied"]:
        await runtime.coordinator.async_request_refresh()
    if not call.return_response:
        return None
    return answer


def async_register_update_product_service(hass: HomeAssistant) -> None:
    """Register once; a reload of the entry must not register twice."""
    if hass.services.has_service(DOMAIN, SERVICE_UPDATE_PRODUCT):
        return

    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_PRODUCT,
        partial(async_handle_update_product, hass),
        schema=UPDATE_PRODUCT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
