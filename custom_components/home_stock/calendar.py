"""The meal plan, as a native Home Assistant calendar.

One event per meal, creatable, movable and deletable from any calendar card —
so a meal posted from Lovelace is a real, decrementable meal and not a string
with no follow-up.

No `RRULE`, ever. A week's menu is not a recurring event, and announcing it as
one would promise a behaviour nobody intends to write: editing "every Tuesday"
would then have to mean something, and it does not.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import partial
from typing import Any

from homeassistant.components.calendar import (
    ENTITY_ID_FORMAT,
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HomeStockConfigEntry
from .coordinator import HomeStockCoordinator
from .domain.foodday import food_day_of
from .domain.matching import candidates, preselect
from .entity import HomeStockEntity
from .storage import repositories as repo


async def async_setup_entry(hass: HomeAssistant, entry: HomeStockConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([MealCalendarEntity(entry.runtime_data.coordinator)])


def _slot_start(day: str, slot: dict[str, Any]) -> datetime:
    """The local instant a meal begins: its food day at the slot's own time."""
    hour, _, minute = slot["default_time"].partition(":")
    return datetime.fromisoformat(day).replace(
        hour=int(hour), minute=int(minute),
        tzinfo=dt_util.get_default_time_zone())


def _describe(meal: dict[str, Any], lines: list[dict[str, Any]]) -> str:
    """What the event body says: the ingredients, and what is missing."""
    if not lines:
        return meal["note"] or ""
    shown = [line["raw_text"] for line in lines]
    missing = [line["raw_text"] for line in lines
               if line["match_state"] == "unmatched"]
    text = "Ingrédients : " + ", ".join(shown)
    if missing:
        text += "\nÀ sortir à la main : " + ", ".join(missing)
    return text


class MealCalendarEntity(HomeStockEntity, CalendarEntity):
    """`calendar.home_stock_meals`."""

    _attr_supported_features = (
        CalendarEntityFeature.CREATE_EVENT
        | CalendarEntityFeature.DELETE_EVENT
        | CalendarEntityFeature.UPDATE_EVENT
    )

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "meals", ENTITY_ID_FORMAT)

    @property
    def _manager(self):
        return self.coordinator.config_entry.runtime_data.manager

    # --- reading ------------------------------------------------------------

    def _event_of(self, conn, meal: dict[str, Any]) -> CalendarEvent:
        slot = {"default_time": meal["slot_default_time"],
                "duration_minutes": meal["slot_duration_minutes"]}
        start = _slot_start(meal["day"], slot)
        lines = (repo.list_ingredients(conn, meal["recipe_id"])
                 if meal["recipe_id"] is not None else [])
        return CalendarEvent(
            summary=(meal["recipe_name"] or meal["product_name"]
                     or meal["note"] or "Repas"),
            start=start,
            end=start + timedelta(minutes=meal["slot_duration_minutes"]),
            uid=meal["uid"],
            description=_describe(meal, lines),
        )

    def _events_between(self, start_day: str, end_day: str) -> list[CalendarEvent]:
        conn = self._manager.db.read()
        return [self._event_of(conn, meal)
                for meal in repo.list_meals(conn, start_day, end_day)]

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime,
                               end_date: datetime) -> list[CalendarEvent]:
        return await hass.async_add_executor_job(
            self._events_between,
            start_date.date().isoformat(), end_date.date().isoformat())

    @property
    def event(self) -> CalendarEvent | None:
        """The next meal still to come. A validated one is behind us."""
        conn = self._manager.db.read()
        today = food_day_of(dt_util.utcnow(), dt_util.get_default_time_zone())
        meal = repo.next_meal(conn, today.isoformat())
        return self._event_of(conn, meal) if meal else None

    # --- writing ------------------------------------------------------------

    def _nearest_slot(self, conn, start: datetime) -> str:
        """The slot whose own time is closest to this instant.

        Posting "Lasagne" at 20:30 from a calendar card means dinner. Asking
        the person to pick a slot they cannot see would be asking them to know
        our schema.
        """
        minutes = start.hour * 60 + start.minute
        def distance(slot):
            hour, _, minute = slot["default_time"].partition(":")
            return abs(int(hour) * 60 + int(minute) - minutes)
        return min(repo.list_slots(conn), key=distance)["key"]

    def _create(self, summary: str, start: datetime) -> None:
        conn = self._manager.db.read()
        slot_key = self._nearest_slot(conn, start)
        # The food day, not the calendar day: an event created at one in the
        # morning belongs to the evening still being finished.
        day = food_day_of(start, dt_util.get_default_time_zone()).isoformat()

        # Match the summary against the RECIPES, with lot 1's thresholds. A
        # meal posted from Lovelace is then a real, decrementable meal.
        recipes = repo.list_recipes(conn)
        chosen = preselect(candidates(names=[summary], products=[
            {"id": r["id"], "name": r["name"]} for r in recipes]))
        if chosen is not None:
            self._manager.plan_meal(day=day, slot_key=slot_key,
                                    recipe_id=chosen.product_id)
        else:
            # Not a failure: "Restaurant" is a perfectly legitimate meal.
            self._manager.plan_meal(day=day, slot_key=slot_key, note=summary)

    async def async_create_event(self, **kwargs: Any) -> None:
        summary = kwargs.get("summary") or "Repas"
        start = kwargs.get("dtstart") or kwargs.get("start")
        if isinstance(start, datetime) and start.tzinfo is None:
            start = start.replace(tzinfo=dt_util.get_default_time_zone())
        if not isinstance(start, datetime):
            start = dt_util.now()
        await self.hass.async_add_executor_job(self._create, summary, start)
        await self.coordinator.async_request_refresh()

    def _meal_by_uid(self, uid: str) -> dict[str, Any]:
        meal = repo.get_meal_by_uid(self._manager.db.read(), uid)
        if meal is None:
            raise HomeAssistantError(f"Repas inconnu : {uid}")
        return meal

    def _update(self, uid: str, start: datetime) -> None:
        meal = self._meal_by_uid(uid)
        conn = self._manager.db.read()
        try:
            self._manager.move_meal(
                meal["id"],
                day=food_day_of(start, dt_util.get_default_time_zone()).isoformat(),
                slot_key=self._nearest_slot(conn, start))
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_update_event(self, uid: str, event: dict[str, Any],
                                 recurrence_id: str | None = None,
                                 recurrence_range: str | None = None) -> None:
        start = event.get("dtstart") or event.get("start")
        if isinstance(start, datetime) and start.tzinfo is None:
            start = start.replace(tzinfo=dt_util.get_default_time_zone())
        if not isinstance(start, datetime):
            raise HomeAssistantError("Un repas déplacé a besoin d'une date.")
        await self.hass.async_add_executor_job(self._update, uid, start)
        await self.coordinator.async_request_refresh()

    def _delete(self, uid: str) -> None:
        # `cancel_meal` deletes a planned meal and marks a validated one
        # skipped. Deleting a validated one would destroy the
        # `movement.ref_type = 'meal'` reference the journal already carries.
        self._manager.cancel_meal(self._meal_by_uid(uid)["id"])

    async def async_delete_event(self, uid: str,
                                 recurrence_id: str | None = None,
                                 recurrence_range: str | None = None) -> None:
        await self.hass.async_add_executor_job(self._delete, uid)
        await self.coordinator.async_request_refresh()
