"""The `home_stock.skip_meal` service: skip a meal from a dashboard.

A Lovelace card can only call services, and the panel's websocket command
`home_stock/meal/cancel` is out of its reach. This service gives the card a
"skip" button:

- a `planned` meal becomes `skipped`. Nothing is written to the movement
  journal and no batch is touched, so the meal counts zero kcal. The meal is
  kept rather than deleted (what `cancel_meal` does to a planned meal), so the
  day still shows that it was skipped.
- a `done` meal goes through `StockManager.cancel_meal` itself, the very code
  behind `home_stock/meal/cancel`: same transition, same journal left intact.
- an already `skipped` meal is left as it is and reported as such, so a
  second tap on the button is harmless.

Without `meal_id`, the meal skipped is the next planned meal of the current
FOOD day, the same one the "next meal" sensor publishes (`repo.next_meal`).

Kept out of `services.py` on purpose: that module is already far over this
project's line limit. Registration is called once, from `__init__.py`.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any, Final
from zoneinfo import ZoneInfo

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .domain.foodday import food_day_of
from .services import _entry, _run
from .storage import repositories as repo
from .validators import bounded_int

SERVICE_SKIP_MEAL: Final = "skip_meal"

SKIP_MEAL_SCHEMA: Final = vol.Schema({
    vol.Optional("meal_id"): bounded_int,
})

# What `skip_meal` answers, in `outcome`.
OUTCOME_SKIPPED: Final = "skipped"
OUTCOME_ALREADY_SKIPPED: Final = "already_skipped"


class NoPlannedMealToday(Exception):
    """No meal is left to skip on the current food day."""

    def __init__(self, day: str) -> None:
        super().__init__(f"no planned meal left on {day}")
        self.day = day


@dataclass(frozen=True)
class SkippedMeal:
    """The meal a call acted on, and what happened to it."""

    meal_id: int
    day: str
    slot_key: str
    outcome: str


def _target(conn: Any, meal_id: int | None, today: str) -> dict[str, Any]:
    """The meal row the call means. Raises `ValueError` for an unknown id,
    worded like `cancel_meal` so both surfaces translate it the same way."""
    if meal_id is None:
        meal = repo.next_meal(conn, today)
        if meal is None or meal["day"] != today:
            raise NoPlannedMealToday(today)
        return meal
    found = repo.get_meal(conn, meal_id)
    if found is None:
        raise ValueError(f"unknown meal {meal_id}")
    return found


def skip_meal(manager: Any, meal_id: int | None, today: str) -> SkippedMeal:
    """Skip one meal; blocking, run in the executor."""
    outcome: str | None = None
    with manager.db.write() as conn:
        meal = _target(conn, meal_id, today)
        if meal["state"] == "planned":
            repo.update_meal_fields(conn, meal["id"], {"state": "skipped"})
            outcome = OUTCOME_SKIPPED
        elif meal["state"] == "skipped":
            outcome = OUTCOME_ALREADY_SKIPPED
    if outcome is None:
        # A `done` meal. Outside the transaction above: cancel_meal opens
        # its own, and must stay the one place that decides this case.
        outcome = manager.cancel_meal(meal["id"])
    return SkippedMeal(meal_id=int(meal["id"]), day=str(meal["day"]),
                       slot_key=str(meal["slot_key"]), outcome=outcome)


def current_food_day(hass: HomeAssistant) -> str:
    """Today's food day, in the time zone this Home Assistant is set to."""
    return food_day_of(dt_util.utcnow(), ZoneInfo(hass.config.time_zone)).isoformat()


async def async_handle_skip_meal(hass: HomeAssistant,
                                 call: ServiceCall) -> ServiceResponse:
    """Skip the meal asked for, or the next planned meal of today."""
    runtime = _entry(hass).runtime_data
    today = current_food_day(hass)
    try:
        skipped: SkippedMeal = await _run(hass, partial(
            skip_meal, runtime.manager, call.data.get("meal_id"), today))
    except NoPlannedMealToday as error:
        raise ServiceValidationError(
            f"Aucun repas planifié à ignorer aujourd'hui ({error.day}).") from error
    await runtime.coordinator.async_request_refresh()
    if not call.return_response:
        return None
    return {"meal_id": skipped.meal_id, "day": skipped.day,
            "slot_key": skipped.slot_key, "outcome": skipped.outcome}


def async_register_skip_meal_service(hass: HomeAssistant) -> None:
    """Register once; a reload of the entry must not register twice."""
    if hass.services.has_service(DOMAIN, SERVICE_SKIP_MEAL):
        return

    hass.services.async_register(
        DOMAIN, SERVICE_SKIP_MEAL,
        partial(async_handle_skip_meal, hass),
        schema=SKIP_MEAL_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
