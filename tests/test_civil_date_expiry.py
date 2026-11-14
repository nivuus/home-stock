"""Expiry stages and the expiring window follow the household's civil date.

A batch is good up to and including its best-before day, in the time zone
Home Assistant is configured with — not in UTC. Two frozen clocks: late in
the evening in a zone behind UTC (the UTC date is already tomorrow), and
just after midnight in a zone ahead of it (the UTC date is still yesterday).
"""
from datetime import date
from zoneinfo import ZoneInfo

from freezegun import freeze_time

BEST_BEFORE = "2026-11-14"
# 23:30 on the 14th in Los Angeles; already the 15th in UTC.
EVENING_BEHIND = "2026-11-15T07:30:00+00:00"
# 00:30 on the 15th in Tokyo; still the 14th in UTC.
MIDNIGHT_AHEAD = "2026-11-14T15:30:00+00:00"


async def _announced_stage(hass, setup_entry, zone: str) -> str:
    await hass.config.async_set_time_zone(zone)
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=500.0, location_id=1, best_before=BEST_BEFORE))
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    return hass.states.get("event.home_stock_expiration").attributes["event_type"]


async def test_late_evening_behind_utc_is_still_the_last_good_day(hass, setup_entry):
    with freeze_time(EVENING_BEHIND):
        assert await _announced_stage(
            hass, setup_entry, "America/Los_Angeles") == "approaching"


async def test_just_after_midnight_ahead_of_utc_is_already_expired(hass, setup_entry):
    with freeze_time(MIDNIGHT_AHEAD):
        assert await _announced_stage(hass, setup_entry, "Asia/Tokyo") == "expired"


async def test_the_expiring_window_starts_on_the_local_date(hass, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=500.0, location_id=1, best_before="2026-11-15"))
    with freeze_time(MIDNIGHT_AHEAD):
        summary = await hass.async_add_executor_job(lambda: manager.summary(
            expiration_alert_days=0, tz=ZoneInfo("Asia/Tokyo")))
    assert [b["best_before"] for b in summary["expiring"]] == ["2026-11-15"]


async def test_equipment_days_left_use_the_local_date(hass, setup_entry, hass_ws_client):
    await hass.config.async_set_time_zone("Asia/Tokyo")
    entry = await setup_entry()
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(lambda: manager.create_equipment(
        name="Four", purchased_on="2026-11-01", warranty_months=0))
    client = await hass_ws_client(hass)
    with freeze_time(MIDNIGHT_AHEAD):
        await client.send_json({"id": 1, "type": "home_stock/equipment/list"})
        answer = await client.receive_json()
    rows = answer["result"]["equipment"]
    assert rows[0]["days_left"] == (date(2026, 11, 1) - date(2026, 11, 15)).days
