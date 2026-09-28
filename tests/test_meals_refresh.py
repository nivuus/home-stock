"""Editing the planning from a screen updates the next-meal sensor at once.

Measured 2026-09-28: `meal/cancel` answered `deleted`, yet
sensor.home_stock_next_meal kept announcing the cancelled lunch until the
15-minute coordinator interval. Only `meal/validate` refreshed. The tablet
reads that sensor to say what comes next, so plan, move and cancel must
refresh too.

Each test establishes the "before" state with one refresh while seeding —
otherwise a fresh sensor would prove a first fill, not a change — and then
leaves the refresh after the command entirely to the command.
"""
from datetime import date, timedelta

import pytest

NEXT = "sensor.home_stock_next_meal"


@pytest.fixture(autouse=True)
async def _paris(hass):
    await hass.config.async_set_time_zone("Europe/Paris")


def _future_day(offset: int) -> str:
    # Far enough ahead that the food-day boundary never matters.
    return (date.today() + timedelta(days=offset)).isoformat()


@pytest.fixture
async def two_meals(hass, setup_entry):
    """A lunch and a dinner planned on the same day, sensor showing the lunch."""
    entry = await setup_entry()
    manager = entry.runtime_data.manager
    day = _future_day(10)

    def _seed():
        lunch = manager.plan_meal(day=day, slot_key="lunch", note="Déjeuner")
        dinner = manager.plan_meal(day=day, slot_key="dinner", note="Dîner")
        return lunch["meal_id"], dinner["meal_id"]

    lunch_id, dinner_id = await hass.async_add_executor_job(_seed)
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(NEXT).attributes["meal_id"] == lunch_id
    return {"day": day, "lunch": lunch_id, "dinner": dinner_id}


async def _tablet(hass, hass_ws_client, hass_read_only_access_token):
    # The tablet is a standard user, not an administrator.
    return await hass_ws_client(hass, hass_read_only_access_token)


async def _ask(client, payload):
    await client.send_json_auto_id(payload)
    answer = await client.receive_json()
    assert answer["success"] is True, answer
    return answer["result"]


async def test_cancel_moves_the_sensor_to_the_following_meal(
        hass, two_meals, hass_ws_client, hass_read_only_access_token):
    client = await _tablet(hass, hass_ws_client, hass_read_only_access_token)
    await _ask(client, {"type": "home_stock/meal/cancel", "meal_id": two_meals["lunch"]})
    await hass.async_block_till_done()
    assert hass.states.get(NEXT).attributes["meal_id"] == two_meals["dinner"]


async def test_plan_of_an_earlier_meal_becomes_the_next_one(
        hass, two_meals, hass_ws_client, hass_read_only_access_token):
    client = await _tablet(hass, hass_ws_client, hass_read_only_access_token)
    posted = await _ask(client, {"type": "home_stock/meal/plan",
                                 "day": _future_day(5), "slot_key": "dinner",
                                 "note": "Plus tôt"})
    await hass.async_block_till_done()
    assert hass.states.get(NEXT).attributes["meal_id"] == posted["meal_id"]


async def test_move_of_the_next_meal_to_a_later_day_promotes_the_other(
        hass, two_meals, hass_ws_client, hass_read_only_access_token):
    client = await _tablet(hass, hass_ws_client, hass_read_only_access_token)
    await _ask(client, {"type": "home_stock/meal/move", "meal_id": two_meals["lunch"],
                        "day": _future_day(12), "slot_key": "lunch"})
    await hass.async_block_till_done()
    assert hass.states.get(NEXT).attributes["meal_id"] == two_meals["dinner"]
