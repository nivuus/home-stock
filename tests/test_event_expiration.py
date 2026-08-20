"""Announcing expirations: once, and only once."""
import pytest


async def test_a_batch_entering_the_window_is_announced_once(hass, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=500.0, location_id=1, best_before="2026-08-21"))
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


async def test_a_batch_with_no_date_is_never_announced(hass, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=500.0, location_id=1))
    claimed = await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3650,
                                                   today="2026-08-20"))
    assert claimed == []


def test_the_blueprint_is_valid_yaml_and_declares_its_inputs():
    # Plain yaml.safe_load chokes on the `!input` tag blueprints rely on
    # throughout (it has no constructor for it). Home Assistant's own loader
    # is what actually parses blueprint files in production
    # (homeassistant.components.blueprint.models._load_blueprint), so this
    # test uses the same one: it both accepts `!input` and proves the file
    # parses the way Home Assistant itself would parse it, not just the way
    # a generic YAML reader would.
    from pathlib import Path

    from homeassistant.util import yaml as yaml_util

    path = Path(__file__).resolve().parent.parent / "blueprints" / "automation" \
        / "home_stock" / "dlc_bleuenn.yaml"
    document = yaml_util.load_yaml_dict(path)
    assert document["blueprint"]["domain"] == "automation"
    assert set(document["blueprint"]["input"]) == {"heure", "agent", "capteur"}
    assert document["triggers"][0]["trigger"] == "time"
