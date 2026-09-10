"""The `home_stock.link_shopping_item` service.

`docs/inventory.md`'s `SHOPPING_LINK` rubric found no existing way to attach
a free-text shopping list line to a product after the fact (R11): the only
write path, `add_to_shopping_list`, only ever creates a line, and
`reconcile` is a bulk import matcher, not a per-line service. This module
adds the minimal service the spec asks for in that case.

Kept out of `services.py` on purpose, exactly like `create_product.py`: that
module is already far over this project's line limit, and this lot must not
make it longer.
"""
from __future__ import annotations

from functools import partial
from typing import Final

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .services import _entry
from .storage import products as store
from .storage import repositories as repo

SERVICE_LINK_SHOPPING_ITEM: Final = "link_shopping_item"

LINK_SHOPPING_ITEM_SCHEMA: Final = vol.Schema({
    vol.Required("item"): cv.string,
    vol.Required("product_id"): cv.string,
})


def _find_item(conn, item: str) -> dict | None:
    """`item` is either a numeric line id or the exact free text of a still
    open, unremoved line -- whichever the caller has at hand."""
    if item.isdigit():
        row = repo.get_list_item(conn, int(item))
        if row is not None:
            return row
    for row in repo.list_items(conn, include_checked=True, include_removed=False):
        if row.get("free_text") == item:
            return row
    return None


def _link(conn, call: ServiceCall) -> None:
    item_text = call.data["item"]
    item = _find_item(conn, item_text)
    if item is None:
        raise ServiceValidationError(f"Ligne de courses introuvable : {item_text}")

    product_id = call.data["product_id"]
    row_id = store.parse_product_id(product_id)
    product = repo.get_product(conn, row_id) if row_id is not None else None
    if product is None:
        raise ServiceValidationError(f"Produit introuvable : {product_id}")

    repo.update_list_item(conn, int(item["id"]),
                          {"product_id": row_id, "free_text": None})


async def async_handle_link_shopping_item(hass: HomeAssistant, call: ServiceCall) -> None:
    """Attach an existing shopping list line to a product, so it carries
    the product's aisle from then on (R11)."""
    entry = _entry(hass)
    manager = entry.runtime_data.manager

    def _run() -> None:
        with manager.db.write() as conn:
            _link(conn, call)

    await hass.async_add_executor_job(_run)
    await entry.runtime_data.coordinator.async_request_refresh()


def async_register_link_shopping_item_service(hass: HomeAssistant) -> None:
    """Register once; a reload of the entry must not register twice."""
    if hass.services.has_service(DOMAIN, SERVICE_LINK_SHOPPING_ITEM):
        return

    hass.services.async_register(
        DOMAIN, SERVICE_LINK_SHOPPING_ITEM,
        partial(async_handle_link_shopping_item, hass),
        schema=LINK_SHOPPING_ITEM_SCHEMA,
    )
