"""Antidating a movement through the websocket: stock/consume and stock/add.

The case these tests replay is the one that asked for the feature: on
2026-10-03 the household records cookies eaten the day before, at 16:30
Paris time, and a purchase made on 2026-10-02. Every check reads the
movement back through the same websocket the panel uses (journal/day,
movements/list), on a real Home Assistant core started by the test harness.
"""
from __future__ import annotations

import pytest
from freezegun import freeze_time

TODAY = "2026-10-03T14:00:00+02:00"
YESTERDAY_SNACK = "2026-10-02T16:30:00+02:00"
YESTERDAY_SNACK_STORED = "2026-10-02T14:30:00"


@pytest.fixture
async def stocked(hass, setup_entry):
    """Paris time, frozen on 2026-10-03, one product with 500 g in stock.

    The product carries 4 kcal per gram so that a day's kcal total is
    something a test can read, not just a movement count.
    """
    await hass.config.async_set_time_zone("Europe/Paris")
    with freeze_time(TODAY):
        entry = await setup_entry(with_article=True)
        manager = entry.runtime_data.manager

        def _seed() -> int:
            with manager.db.write() as conn:
                conn.execute("UPDATE product SET reference_kcal = 4 WHERE id = 1")
            return manager.add_stock(article_id=1, quantity=500.0, location_id=1,
                                     occurred_at="2026-09-30T10:00:00")

        batch_id = await hass.async_add_executor_job(_seed)
    return entry, batch_id


async def _ask(client, message: dict) -> dict:
    await client.send_json_auto_id(message)
    return await client.receive_json()


async def _journal(client, day: str | None = None) -> dict:
    message = {"type": "home_stock/journal/day"}
    if day is not None:
        message["date"] = day
    answer = await _ask(client, message)
    assert answer["success"], answer
    return answer["result"]


def _consume(**extra) -> dict:
    return {"type": "home_stock/stock/consume", "product_id": 1, "quantity": 100.0,
            **extra}


def _add(**extra) -> dict:
    return {"type": "home_stock/stock/add", "article_id": 1, "quantity": 250.0,
            "location_id": 1, **extra}


async def _count(hass, entry, reason: str) -> int:
    row = await hass.async_add_executor_job(lambda: entry.runtime_data.manager.db.read()
                                            .execute("SELECT COUNT(*) AS n FROM movement"
                                                     " WHERE reason = ?", (reason,))
                                            .fetchone())
    return row["n"]


# --- stock/consume ------------------------------------------------------------

async def test_consume_is_booked_on_the_day_it_happened(hass, hass_ws_client, stocked):
    # Connected before the clock is frozen: the harness's access token is
    # issued on the real clock, and a frozen past would reject it.
    client = await hass_ws_client(hass)
    with freeze_time(TODAY):
        answer = await _ask(client, _consume(occurred_at=YESTERDAY_SNACK))
        assert answer["success"], answer

        yesterday = await _journal(client, "2026-10-02")
        today = await _journal(client)

    assert [e["occurred_at"] for e in yesterday["entries"]] == [YESTERDAY_SNACK_STORED]
    assert yesterday["totals"]["kcal"] == pytest.approx(400.0)
    assert today["food_day"] == "2026-10-03"
    assert today["entries"] == []


async def test_consume_of_a_named_batch_is_booked_on_its_day(hass, hass_ws_client,
                                                             stocked):
    _, batch_id = stocked
    # Connected before the clock is frozen: the harness's access token is
    # issued on the real clock, and a frozen past would reject it.
    client = await hass_ws_client(hass)
    with freeze_time(TODAY):
        answer = await _ask(client, _consume(batch_id=batch_id,
                                             occurred_at=YESTERDAY_SNACK))
        assert answer["success"], answer

        yesterday = await _journal(client, "2026-10-02")
        today = await _journal(client)

    assert [e["occurred_at"] for e in yesterday["entries"]] == [YESTERDAY_SNACK_STORED]
    assert [e["batch_id"] for e in yesterday["entries"]] == [batch_id]
    assert today["entries"] == []


async def test_todays_kcal_counter_ignores_an_antidated_consumption(hass, hass_ws_client,
                                                                    stocked):
    entry, _ = stocked
    coordinator = entry.runtime_data.coordinator
    # Connected before the clock is frozen: the harness's access token is
    # issued on the real clock, and a frozen past would reject it.
    client = await hass_ws_client(hass)
    with freeze_time(TODAY):
        assert (await _ask(client, _consume(occurred_at=YESTERDAY_SNACK)))["success"]
        await coordinator.async_refresh()

    assert coordinator.data["today"]["food_day"] == "2026-10-03"
    assert coordinator.data["today"]["kcal"] == 0.0


async def test_consume_without_occurred_at_still_happens_now(hass, hass_ws_client,
                                                             stocked):
    entry, _ = stocked
    coordinator = entry.runtime_data.coordinator
    # Connected before the clock is frozen: the harness's access token is
    # issued on the real clock, and a frozen past would reject it.
    client = await hass_ws_client(hass)
    with freeze_time(TODAY):
        assert (await _ask(client, _consume()))["success"]
        today = await _journal(client)
        await coordinator.async_refresh()

    assert [e["occurred_at"] for e in today["entries"]] == ["2026-10-03T12:00:00"]
    assert coordinator.data["today"]["kcal"] == pytest.approx(400.0)


async def test_the_offset_decides_the_food_day(hass, hass_ws_client, stocked):
    """03:30 in Paris on the 2nd is still the food day of the 1st (it turns
    over at 04:00 local). Read as UTC, the same digits would land on the 2nd."""
    # Connected before the clock is frozen: the harness's access token is
    # issued on the real clock, and a frozen past would reject it.
    client = await hass_ws_client(hass)
    with freeze_time(TODAY):
        assert (await _ask(client, _consume(
            occurred_at="2026-10-02T03:30:00+02:00")))["success"]
        assert (await _ask(client, _consume(
            occurred_at="2026-10-02T08:00:00Z")))["success"]

        first = await _journal(client, "2026-10-01")
        second = await _journal(client, "2026-10-02")

    assert [e["occurred_at"] for e in first["entries"]] == ["2026-10-02T01:30:00"]
    assert [e["occurred_at"] for e in second["entries"]] == ["2026-10-02T08:00:00"]


@pytest.mark.parametrize("occurred_at", [
    "2026-10-02T16:30:00",        # no offset
    "2026-10-02",                 # a bare date
    "2026-02-30T12:00:00+01:00",  # no such day
    "hier au goûter",
    "2026-10-04T12:00:00+02:00",  # tomorrow
])
async def test_consume_refuses_an_unusable_moment_and_writes_nothing(
        hass, hass_ws_client, stocked, occurred_at):
    entry, _ = stocked
    # Connected before the clock is frozen: the harness's access token is
    # issued on the real clock, and a frozen past would reject it.
    client = await hass_ws_client(hass)
    with freeze_time(TODAY):
        answer = await _ask(client, _consume(occurred_at=occurred_at))

    assert not answer["success"]
    assert answer["error"]["code"] == "invalid_format"
    assert await _count(hass, entry, "consumption") == 0


# --- stock/add ----------------------------------------------------------------

async def test_add_is_dated_when_it_happened(hass, hass_ws_client, stocked):
    # Connected before the clock is frozen: the harness's access token is
    # issued on the real clock, and a frozen past would reject it.
    client = await hass_ws_client(hass)
    with freeze_time(TODAY):
        answer = await _ask(client, _add(occurred_at="2026-10-02T18:05:00+02:00"))
        assert answer["success"], answer
        batch_id = answer["result"]["batch_id"]

        movements = await _ask(client, {"type": "home_stock/movements/list",
                                        "since": "2026-10-02T00:00:00"})
        batches = await _ask(client, {"type": "home_stock/batches/list"})

    entries = [m for m in movements["result"]["movements"] if m["batch_id"] == batch_id]
    assert [(m["reason"], m["occurred_at"]) for m in entries] == [
        ("purchase", "2026-10-02T16:05:00")]
    batch = next(b for b in batches["result"]["batches"] if b["id"] == batch_id)
    assert batch["entered_at"] == "2026-10-02T16:05:00"


async def test_add_without_occurred_at_still_happens_now(hass, hass_ws_client, stocked):
    # Connected before the clock is frozen: the harness's access token is
    # issued on the real clock, and a frozen past would reject it.
    client = await hass_ws_client(hass)
    with freeze_time(TODAY):
        answer = await _ask(client, _add())
        assert answer["success"], answer
        batch_id = answer["result"]["batch_id"]
        movements = await _ask(client, {"type": "home_stock/movements/list"})

    entries = [m for m in movements["result"]["movements"] if m["batch_id"] == batch_id]
    assert [m["occurred_at"] for m in entries] == ["2026-10-03T12:00:00"]


@pytest.mark.parametrize("occurred_at", [
    "2026-10-02T18:05:00",
    "2026-10-02",
    "pas une date",
    "2026-10-04T12:00:00+02:00",
])
async def test_add_refuses_an_unusable_moment_and_writes_nothing(
        hass, hass_ws_client, stocked, occurred_at):
    entry, _ = stocked
    # Connected before the clock is frozen: the harness's access token is
    # issued on the real clock, and a frozen past would reject it.
    client = await hass_ws_client(hass)
    with freeze_time(TODAY):
        answer = await _ask(client, _add(occurred_at=occurred_at))

    assert not answer["success"]
    assert answer["error"]["code"] == "invalid_format"
    # Only the batch the fixture seeded: nothing was added.
    assert await _count(hass, entry, "purchase") == 1
