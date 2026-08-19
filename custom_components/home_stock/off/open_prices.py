"""Open Prices: what other people paid for this barcode.

A suggestion, never a dependency. Every failure path here returns None and
says nothing: putting a batch away must not wait on someone else's server.
"""
from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

OPEN_PRICES_URL = "https://prices.openfoodfacts.org/api/v1/prices"
OPEN_PRICES_TIMEOUT = 5.0
CURRENCY = "EUR"


async def latest_price(transport: Any, code: str, *, net_quantity: float | None,
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

    if status != 200 or not payload:
        return None

    for item in payload.get("items") or []:
        if item.get("currency") != CURRENCY:
            continue
        price = item.get("price")
        if not isinstance(price, (int, float)):
            continue
        # Open Prices carries its own idea of the pack size. Prefer it: it
        # comes from the same record the price was observed on.
        quantity = (item.get("product") or {}).get("product_quantity") or net_quantity
        if not quantity or quantity <= 0:
            continue
        return float(price) / float(quantity)
    return None
