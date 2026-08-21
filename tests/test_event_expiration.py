"""Announcing expirations: once, and only once."""
from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time


async def test_a_batch_entering_the_window_is_announced_once(hass, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    # The entity never passes `today` to claim_expiry_announcements (event.py
    # only forwards expiration_alert_days), so production reads the real
    # clock here. A hardcoded best-before date would only sit inside the
    # default 3-day window for a few calendar days and then start failing on
    # its own with nothing having changed; one day out is inside that window
    # on whatever day this test happens to run.
    soon = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=500.0, location_id=1, best_before=soon))
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("event.home_stock_expiration")
    assert state.attributes["event_type"] == "approaching"
    assert state.attributes["count"] == 1
    first_fired = state.state

    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    # Nothing new: the state does not move, the same batch is not re-announced.
    assert hass.states.get("event.home_stock_expiration").state == first_fired


async def test_the_stage_survives_a_restart(hass, setup_entry):
    """The stage lives in the database, not in memory: otherwise every Home
    Assistant restart would re-announce the whole fridge."""
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=500.0, location_id=1, best_before="2026-08-21"))

    claimed = await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3,
                                                   today="2026-08-20"))
    assert [stage for stage, _ in claimed] == ["approaching"]

    again = await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3,
                                                   today="2026-08-20"))
    assert again == []


async def test_the_second_stage_is_announced_when_the_date_passes(hass, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=500.0, location_id=1, best_before="2026-08-21"))

    await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3,
                                                   today="2026-08-20"))
    claimed = await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3,
                                                   today="2026-08-22"))
    assert [stage for stage, _ in claimed] == ["expired"]


async def test_the_stage_never_goes_backwards(hass, setup_entry):
    """A best-before date does not become approaching again after it has
    passed — and a clock moving backwards (corrected timezone, restored
    backup) must not re-announce it."""
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=500.0, location_id=1, best_before="2026-08-21"))

    await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3,
                                                   today="2026-08-22"))
    claimed = await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3,
                                                   today="2026-08-20"))
    assert claimed == []


async def test_several_batches_are_announced_in_one_event(hass, setup_entry):
    """"Three things are expiring," not three sentences — and above all not
    three states written within the same second."""
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    for _ in range(3):
        await hass.async_add_executor_job(lambda: manager.add_stock(
            article_id=1, quantity=100.0, location_id=1, best_before="2026-08-21"))

    claimed = await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3650,
                                                   today="2026-08-20"))
    assert len(claimed) == 1
    stage, batches = claimed[0]
    assert stage == "approaching" and len(batches) == 3
    assert batches[0]["product_name"]
    assert batches[0]["display"]


async def test_the_entity_fires_one_event_for_several_batches(hass, setup_entry):
    """Grouping is an entity-level guarantee, not just an application-layer
    one: test_several_batches_are_announced_in_one_event above only proves
    claim_expiry_announcements groups, since it calls the manager directly
    and never goes through ExpirationEventEntity. Firing once per batch
    instead of once per stage would put three state writes on the bus for
    what a listener (or a voice assistant) should read as a single event."""
    from pytest_homeassistant_custom_component.common import async_capture_events

    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    soon = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
    for _ in range(3):
        await hass.async_add_executor_job(lambda: manager.add_stock(
            article_id=1, quantity=100.0, location_id=1, best_before=soon))

    state_changes = async_capture_events(hass, "state_changed")
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    fires = [event for event in state_changes
             if event.data["entity_id"] == "event.home_stock_expiration"]
    assert len(fires) == 1
    state = hass.states.get("event.home_stock_expiration")
    assert state.attributes["event_type"] == "approaching"
    assert state.attributes["count"] == 3


async def test_two_stages_in_one_refresh_fire_two_distinct_events(hass, setup_entry):
    """A stock with mixed dates — something approaching, something already
    overdue and never announced — is the ordinary case, and exactly what a
    Home Assistant restart after a few days off produces: the entity catches
    up on the whole backlog in a single refresh. claim_expiry_announcements
    returns both stages together whenever that happens, so the entity's
    per-stage loop runs twice in the same _announce() call, writing state
    twice. This is exactly the situation grouping exists to protect against:
    two state writes that could land in the same wall-clock second.

    The refresh is wrapped in a frozen instant on purpose: without it, two
    executor round-trips are almost certainly microseconds apart on their
    own, which would prove nothing about a genuine collision. Freezing time
    forces both _trigger_event calls to read the exact same raw clock value,
    the one scenario where a naive implementation (or a regression that
    dropped Home Assistant's own monotonic-timestamp floor) would produce two
    identical states — one silently overwriting the other before anything
    ever observed it.
    """
    from pytest_homeassistant_custom_component.common import async_capture_events

    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    today = datetime.now(UTC).date()
    approaching_date = (today + timedelta(days=1)).isoformat()
    overdue_date = (today - timedelta(days=1)).isoformat()
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=100.0, location_id=1, best_before=approaching_date))
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=200.0, location_id=1, best_before=overdue_date))

    state_changes = async_capture_events(hass, "state_changed")
    frozen_instant = datetime.now(UTC)
    with freeze_time(frozen_instant):
        await entry.runtime_data.coordinator.async_refresh()
        await hass.async_block_till_done()

    fires = [event for event in state_changes
             if event.data["entity_id"] == "event.home_stock_expiration"]
    assert len(fires) == 2

    first, second = (event.data["new_state"] for event in fires)
    assert first.attributes["event_type"] == "approaching"
    assert first.attributes["count"] == 1
    assert [b["display"] for b in first.attributes["batches"]] == ["100 g"]
    assert second.attributes["event_type"] == "expired"
    assert second.attributes["count"] == 1
    assert [b["display"] for b in second.attributes["batches"]] == ["200 g"]

    # The two writes landed on the exact same frozen instant: only a strictly
    # increasing state proves the second did not silently overwrite the
    # first before anyone could observe it.
    assert first.state != second.state
    assert first.state < second.state


async def test_a_batch_with_no_date_is_never_announced(hass, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=500.0, location_id=1))
    claimed = await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3650,
                                                   today="2026-08-20"))
    assert claimed == []


async def test_the_blueprint_is_valid_yaml_and_declares_its_inputs(hass):
    # Plain yaml.safe_load chokes on the `!input` tag blueprints rely on
    # throughout (it has no constructor for it). Home Assistant's own loader
    # is what actually parses blueprint files in production
    # (homeassistant.components.blueprint.models._load_blueprint), so this
    # test uses the same one: it both accepts `!input` and proves the file
    # parses the way Home Assistant itself would parse it, not just the way
    # a generic YAML reader would.
    #
    # Reading the raw keys back (as a previous version of this test did) is
    # not enough: a step can carry every key it is "supposed" to and still
    # be an invalid automation, the way `action:` next to `variables:` on
    # the same step was (Home Assistant's step-type table looks at
    # `variables` first and classifies the whole step as a variables step,
    # then refuses `action` as an unknown extra key). Only Home Assistant's
    # own automation config schema — `cv.SCRIPT_SCHEMA` for actions,
    # `cv.CONDITION_SCHEMA` for a condition — can catch that, so this test
    # feeds the parsed (and `!input`-substituted, the way a real import
    # would) document straight through them.
    from pathlib import Path

    from homeassistant.helpers import config_validation as cv
    from homeassistant.util import yaml as yaml_util

    path = Path(__file__).resolve().parent.parent / "blueprints" / "automation" \
        / "home_stock" / "dlc_bleuenn.yaml"
    document = yaml_util.load_yaml_dict(path)
    assert document["blueprint"]["domain"] == "automation"
    assert set(document["blueprint"]["input"]) == {"heure", "agent", "capteur"}
    assert document["triggers"][0]["trigger"] == "time"

    # Inputs substituted with their defaults, the same step
    # `BlueprintInputs.async_substitute` performs before an automation built
    # from the blueprint is validated — the product's validators reject a
    # bare `Input` placeholder, so they must never see one.
    defaults = {name: spec["default"]
                for name, spec in document["blueprint"]["input"].items()}
    substituted = yaml_util.substitute(document, defaults)

    validated_conditions = cv.CONDITION_SCHEMA(substituted["conditions"][0])
    assert validated_conditions["condition"] == "state"

    validated_actions = cv.SCRIPT_SCHEMA(substituted["actions"])
    action = validated_actions[0]
    assert action["action"] == "conversation.process"

    # `!input capteur` cannot be interpolated straight into the Jinja
    # template below it: it must be handed in as a plain variable first
    # (`nom_capteur`), and the template must actually use that name, or the
    # text Bleuenn reads out would silently see no batches at all.
    assert substituted["variables"] == {"nom_capteur": defaults["capteur"]}
    assert "nom_capteur" in document["actions"][0]["data"]["text"]
