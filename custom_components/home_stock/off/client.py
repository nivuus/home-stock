"""The Open Food Facts cascade.

Four sister databases share one API and one barcode space, so a scan walks
them until something answers. The transport is injected: this module owns the
cascade rules, not the HTTP library, and every rule below is exercised in
tests without a socket.

Rate limits are measured, not assumed. Capturing the fixtures on 2026-08-19 at
one request every 1.5 s earned an HTTP 429 after about twenty calls. Hence:
an interactive scan fires once and takes what it gets, while a bulk resync
waits BULK_INTERVAL between cards and backs off THROTTLE_BACKOFF on a 429.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final, Protocol

BASES: Final = (
    ("food", "world.openfoodfacts.org"),
    ("products", "world.openproductsfacts.org"),
    ("beauty", "world.openbeautyfacts.org"),
    ("petfood", "world.openpetfoodfacts.org"),
)

FIELDS: Final = (
    "code,product_name,product_name_fr,generic_name,generic_name_fr,brands,quantity,"
    "product_quantity,product_quantity_unit,serving_size,serving_quantity,nutriments,"
    "nutrition_data_per,nutrition_data_prepared_per,nutriscore_grade,nova_group,"
    "ecoscore_grade,categories_tags,labels_tags,allergens_tags,traces_tags,"
    "additives_tags,ingredients_text_fr,ingredients_text,image_front_url,"
    "image_nutrition_url,image_ingredients_url,obsolete,completeness,last_modified_t,"
    # Lot 2bis : le matériau d'emballage. Absent jusqu'ici, donc absent de tous
    # les `off_raw` déjà stockés — la consigne de tri n'apparaîtra que sur les
    # articles scannés ou resynchronisés après cette version (spec § 9.1).
    "packagings,packaging_tags"
)

TIMEOUT_PER_BASE: Final = 10.0
CASCADE_BUDGET: Final = 20.0
BULK_INTERVAL: Final = 8.0
THROTTLE_BACKOFF: Final = 45.0


class OffTransport(Protocol):
    """Whatever can fetch a JSON document. Injected so tests stay offline."""

    async def get_json(self, url: str, headers: dict[str, str],
                       timeout: float) -> tuple[int, dict[str, Any] | None]:
        ...


@dataclass(frozen=True)
class OffRecord:
    code: str
    off_source: str
    product: dict[str, Any]


@dataclass(frozen=True)
class OffLookup:
    """What a cascade found, and why it stopped if it found nothing."""

    record: OffRecord | None = None
    throttled: bool = False
    timed_out: bool = False


class OffClient:
    """Walks the four bases for one barcode."""

    def __init__(self, transport: OffTransport, *, user_agent: str,
                 clock: Callable[[], float] = time.monotonic,
                 sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._transport = transport
        self._user_agent = user_agent
        self._clock = clock
        self._sleep = sleeper

    async def lookup(self, code: str) -> OffLookup:
        """One pass down the cascade. Never raises.

        `timed_out` is reported only when the walk was cut short — at least
        one base never got queried. A walk that reached every base and found
        nothing is a genuine absence, not "we did not look", even if the
        last call slightly overran CASCADE_BUDGET finishing its own request.
        """
        started = self._clock()
        headers = {"User-Agent": self._user_agent}

        for off_source, host in BASES:
            remaining = CASCADE_BUDGET - (self._clock() - started)
            if remaining <= 0:
                return OffLookup(timed_out=True)

            # CASCADE_BUDGET is a promise to the person holding the phone: cap
            # what we ask of this base at what is actually left, so one base
            # queried near the end of the budget cannot add its own full
            # TIMEOUT_PER_BASE on top and push the real wall clock past it.
            timeout = min(TIMEOUT_PER_BASE, remaining)
            url = f"https://{host}/api/v2/product/{code}.json?fields={FIELDS}"
            try:
                status, payload = await self._transport.get_json(url, headers, timeout)
            except Exception:  # noqa: BLE001 - deliberately swallows everything the
                # transport can raise (timeout, connection error, ...): a scan
                # that fails must return nothing, never throw at the user.
                continue

            if status == 429:
                # Walking on to the next base would only deepen the throttle:
                # the limit is per client, not per host.
                return OffLookup(throttled=True)
            if status != 200 or not isinstance(payload, dict):
                # A 404, any other non-200 status, or a 200 body that did not
                # deserialise into a dict (OFF has been seen to answer with a
                # bare list/string/number) — either way this base has nothing
                # usable. Checked explicitly so a malformed body reads as an
                # expected condition, not an accident that raises on us.
                continue
            product = payload.get("product")
            # Same defensive shape as the payload check above: OFF has been
            # seen to answer status 1 with a "product" that is not a dict
            # (a bare list, a string). map_article() raises ValueError on
            # exactly that shape, so letting it through here would turn one
            # base's malformed record into a crash instead of "try the next
            # base" — checked explicitly, not folded into the outer except.
            if payload.get("status") == 1 and isinstance(product, dict) and product:
                return OffLookup(record=OffRecord(code, off_source, product))

        return OffLookup()

    async def lookup_with_retry(self, code: str, *, attempts: int = 5,
                                backoff: float = THROTTLE_BACKOFF) -> OffLookup:
        """The bulk path: waits out a throttle instead of dropping the card."""
        result = OffLookup()
        for attempt in range(attempts):
            result = await self.lookup(code)
            if not result.throttled:
                return result
            if attempt < attempts - 1:
                await self._sleep(backoff)
        return result


class AiohttpTransport:
    """The only thing here that touches the network."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def get_json(self, url: str, headers: dict[str, str],
                       timeout: float) -> tuple[int, dict[str, Any] | None]:
        async with self._session.get(url, headers=headers, timeout=timeout) as response:
            if response.status != 200:
                return response.status, None
            return 200, await response.json(content_type=None)
