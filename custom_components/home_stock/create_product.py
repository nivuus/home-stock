"""The `home_stock.create_product` service: a product with no barcode.

Kept out of `services.py` on purpose: that module is already far over this
project's line limit, and this lot must not make it longer. Registration is
called once, separately, from `__init__.py`.
"""
from __future__ import annotations

from functools import partial
from typing import Final

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .aisles import AISLES
from .const import BASE_UNITS, DOMAIN
from .services import _entry
from .storage import products as store

SERVICE_CREATE_PRODUCT: Final = "create_product"

CREATE_PRODUCT_SCHEMA: Final = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Required("rayon"): vol.In(AISLES),
    vol.Optional("unit"): vol.In(BASE_UNITS),
    vol.Optional("barcode"): cv.string,
})


def _create(conn, call: ServiceCall) -> dict:
    return store.create_product(
        conn,
        name=call.data["name"],
        rayon=call.data["rayon"],
        unit=call.data.get("unit"),
        barcode=call.data.get("barcode"),
    )


async def async_handle_create_product(hass: HomeAssistant,
                                      call: ServiceCall) -> ServiceResponse:
    """Create a product; translate `store.ProductError` into a French,
    schema-visible error instead of a bare Python exception (R9)."""
    entry = _entry(hass)
    manager = entry.runtime_data.manager

    def _run() -> dict:
        with manager.db.write() as conn:
            return _create(conn, call)

    try:
        product = await hass.async_add_executor_job(_run)
    except store.EmptyName as exc:
        raise ServiceValidationError("Le nom du produit est vide") from exc
    except store.DuplicateBarcode as exc:
        raise ServiceValidationError(
            f"Le code-barres {exc.barcode} est déjà utilisé") from exc
    # InvalidRayon/InvalidUnit are unreachable through THIS service: the
    # schema's `vol.In(AISLES)`/`vol.In(BASE_UNITS)` already refuse any value
    # outside the closed lists before the handler ever runs, so no test
    # exercises these two branches directly. Kept as defence in depth for
    # `store.create_product`'s other, less strictly schema-guarded caller
    # (the existing barcode-scan path), which shares this same store module.
    except store.InvalidRayon as exc:
        raise ServiceValidationError(
            f"Rayon inconnu « {exc.value} » ; rayons acceptés : "
            f"{', '.join(exc.allowed)}") from exc
    except store.InvalidUnit as exc:
        raise ServiceValidationError(
            f"Unité inconnue « {exc.value} » ; unités acceptées : "
            f"{', '.join(exc.allowed)}") from exc
    except store.DuplicateName as exc:
        raise ServiceValidationError(
            f"Un produit s'appelle déjà « {exc.name} »") from exc

    await entry.runtime_data.coordinator.async_request_refresh()
    return {
        "product_id": product["product_id"],
        "name": product["name"],
        "rayon": product["rayon"],
        "unit": product["unit"],
        "barcode": product["barcode"],
    }


def async_register_create_product_service(hass: HomeAssistant) -> None:
    """Register once; a reload of the entry must not register twice."""
    if hass.services.has_service(DOMAIN, SERVICE_CREATE_PRODUCT):
        return

    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_PRODUCT,
        partial(async_handle_create_product, hass),
        schema=CREATE_PRODUCT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
