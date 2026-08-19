"""Open Prices: what other people paid for this barcode.

A suggestion, never a dependency. Every failure path here returns None and
says nothing: putting a batch away must not wait on someone else's server.

Open Prices is a collaborative database in active development, so every shape
assumption below is checked with an explicit `isinstance` rather than folded
into the outer `try`: a malformed record — a payload that is not a dict, an
`items` that is not a list, an item that is not a dict, a price or quantity
that is not a real number — is an expected condition to skip, not an
accident worth crashing a scan over.
"""
from __future__ import annotations

import logging
from typing import Any

from .client import OffTransport

_LOGGER = logging.getLogger(__name__)

OPEN_PRICES_URL = "https://prices.openfoodfacts.org/api/v1/prices"
OPEN_PRICES_TIMEOUT = 5.0
CURRENCY = "EUR"


async def latest_price(transport: OffTransport, code: str, *, net_quantity: float | None,
                       user_agent: str, timeout: float = OPEN_PRICES_TIMEOUT) -> float | None:
    """The most recent euro price for this barcode, per base unit."""
    url = f"{OPEN_PRICES_URL}?product_code={code}&order_by=-date&size=5"
    try:
        status, payload = await transport.get_json(
            url, {"User-Agent": user_agent}, timeout
        )
    except Exception as err:  # noqa: BLE001 - a suggestion never fails a scan
        _LOGGER.debug("Open Prices unreachable for %s: %s", code, err)
        return None

    if status != 200 or not isinstance(payload, dict):
        return None

    items = payload.get("items")
    if not isinstance(items, list):
        return None

    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("currency") != CURRENCY:
            continue
        price = _price(item)
        if price is None:
            continue
        quantity = _pack_quantity(item, net_quantity)
        if quantity is None:
            continue
        return price / quantity
    return None


def _price(item: dict[str, Any]) -> float | None:
    """The euro figure to anchor on, preferring the undiscounted price.

    `price_is_discounted` marks a promotion: this field pre-fills "what this
    normally costs" so the shopper only has to correct it, not type the whole
    figure from scratch. A one-off discount is exactly the wrong number to
    anchor that on, so the undiscounted price wins when it was recorded.
    Falling back to `price` when it was not still beats offering nothing: a
    discounted suggestion is closer than a blank field.

    A negative price is a data-entry error upstream and is rejected; zero
    stays valid, since a free item is a real observation.
    """
    price = item.get("price")
    if item.get("price_is_discounted") and _is_number(item.get("price_without_discount")):
        price = item["price_without_discount"]
    if not _is_number(price) or price < 0:
        return None
    return float(price)


def _pack_quantity(item: dict[str, Any], net_quantity: float | None) -> float | None:
    """The pack size to divide by, preferring Open Prices' own record.

    Open Prices carries its own idea of the pack size on the same record the
    price was observed on, so it is preferred over the caller's guess. A
    `product_quantity` that is missing, not a real number, or explicitly 0 is
    just as unusable as an absent one — 0 g/mL divides nothing meaningfully —
    so it falls back to `net_quantity` the same way a missing field would.
    """
    product = item.get("product")
    reported = product.get("product_quantity") if isinstance(product, dict) else None
    quantity = reported if _is_number(reported) and reported > 0 else net_quantity
    if not _is_number(quantity) or quantity <= 0:
        return None
    return float(quantity)


def _is_number(value: Any) -> bool:
    """True for a real int/float, excluding bool (`bool` subclasses `int`)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)
