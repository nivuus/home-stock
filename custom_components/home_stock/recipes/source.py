"""TheMealDB, the discovery source.

The network contract is lot 1's, word for word: the transport is injected,
the timeout is ten seconds, there is ONE attempt and no retry, and **no
method here ever raises**. A source of ideas that throws would take the
evening's dinner down with it; one that retries three times just makes
someone wait longer for the same silence. Callers get an empty list or None,
and say so on screen.

No `hass`, no `homeassistant` import: this module owns the route shapes and
the defensive reading, not the HTTP library.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final
from urllib.parse import quote

from ..off.client import OffTransport

# Deux routes, et c'est la CLÉ qui choisit — jamais un réglage de plus.
#
# « 1 » est la clé de test publique de TheMealDB ; v2 la refuse. Toute autre
# clé est une clé d'abonné, et le catalogue élargi comme les routes exclusives
# (`latest.php`, `randomselection.php`, les multi-filtres) ne vivent que sur
# v2. Mesuré le 2026-08-22 avec une même clé d'abonné : `filter.php?i=chicken`
# rend 20 fiches sur v1 contre 21 sur v2. Rester sur v1 avec une clé payante,
# c'est payer sans rien recevoir ; forcer v2 sans clé, c'est casser toute
# installation qui n'en a pas — d'où le choix par la clé, fait UNE fois à la
# construction plutôt qu'essayé puis repris à chaque appel : le contrat du
# lot 1 est une tentative et pas de reprise, et il ne bouge pas ici.
BASE_URL: Final = "https://www.themealdb.com/api/json/v1/{key}/"
PREMIUM_BASE_URL: Final = "https://www.themealdb.com/api/json/v2/{key}/"
TEST_KEY: Final = "1"


def base_url_for(key: str) -> str:
    """La racine qui répondra à cette clé."""
    return (BASE_URL if key.strip() == TEST_KEY else PREMIUM_BASE_URL).format(
        key=key.strip())
TIMEOUT: Final = 10.0
BULK_INTERVAL: Final = 8.0          # same interval as the OFF ingestion


@dataclass(frozen=True)
class SourceHit:
    """One card as a listing shows it, before anything is imported."""

    source_ref: str                 # idMeal
    name: str
    image_url: str | None
    category: str | None
    area: str | None


def _hit(meal: Any) -> SourceHit | None:
    """One search row, read defensively.

    `filter.php` answers with a REDUCED shape — no `strCategory` at all —
    while `search.php` returns the full card. Reading with `.get` rather than
    indexing is what lets one dataclass serve both routes instead of two
    near-identical ones drifting apart.
    """
    if not isinstance(meal, dict):
        return None
    source_ref = meal.get("idMeal")
    name = meal.get("strMeal")
    if not source_ref or not name:
        return None
    return SourceHit(
        source_ref=str(source_ref),
        name=str(name),
        image_url=meal.get("strMealThumb") or None,
        category=meal.get("strCategory") or None,
        area=meal.get("strArea") or None,
    )


class MealDbClient:
    """Reads TheMealDB. Never raises, never retries."""

    def __init__(self, transport: OffTransport, *, key: str = "1",
                 user_agent: str,
                 clock: Callable[[], float] = time.monotonic,
                 sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._transport = transport
        self._key = key
        self._user_agent = user_agent
        self._clock = clock
        self._sleep = sleeper
        self._last_call: float | None = None

    def _url(self, route: str, parameter: str, value: str) -> str:
        return base_url_for(self._key) + f"{route}?{parameter}={quote(value)}"

    async def _get(self, url: str) -> dict[str, Any] | None:
        """One attempt. Any failure whatsoever reads as "nothing found".

        The bare `except Exception` is deliberate and is lot 1's rule: a
        timeout, a reset connection, a truncated body and a JSON decode error
        are the same fact to a caller — the source did not answer. Letting any
        of them escape would turn a browsing screen into a stack trace.
        """
        try:
            status, payload = await self._transport.get_json(
                url, {"User-Agent": self._user_agent}, TIMEOUT)
        except Exception:       # noqa: BLE001 — see docstring
            return None
        if status != 200 or not isinstance(payload, dict):
            return None
        return payload

    @staticmethod
    def _meals(payload: dict[str, Any] | None) -> list[Any]:
        """The `meals` list, or nothing.

        TheMealDB answers `{"meals": null}` when it finds nothing. That is an
        empty search, not a breakdown, and it must not be told apart from one
        by the caller.
        """
        if payload is None:
            return []
        meals = payload.get("meals")
        return meals if isinstance(meals, list) else []

    def _hits(self, payload: dict[str, Any] | None) -> list[SourceHit]:
        return [hit for hit in (_hit(meal) for meal in self._meals(payload))
                if hit is not None]

    async def search(self, query: str) -> list[SourceHit]:
        """Cards whose name matches. Empty list when nothing answers."""
        return self._hits(await self._get(self._url("search.php", "s", query)))

    async def by_ingredient(self, ingredient: str) -> list[SourceHit]:
        """Cards using this ingredient.

        `filter.php?i=` answers the only question a pantry lets you ask:
        what can I make with this.
        """
        return self._hits(await self._get(self._url("filter.php", "i", ingredient)))

    async def lookup(self, source_ref: str) -> dict[str, Any] | None:
        """One full card, or None. Never raises."""
        meals = self._meals(await self._get(self._url("lookup.php", "i", source_ref)))
        first = meals[0] if meals else None
        return first if isinstance(first, dict) else None

    async def wait_for_bulk(self) -> None:
        """Hold BULK_INTERVAL between two calls of a batch import.

        Same device as the Open Food Facts ingestion, and for the same reason:
        the interval was measured, not assumed. The clock and the sleeper are
        injected so tests spend no real time proving it.
        """
        now = self._clock()
        if self._last_call is not None:
            waited = now - self._last_call
            if waited < BULK_INTERVAL:
                await self._sleep(BULK_INTERVAL - waited)
        self._last_call = self._clock()
