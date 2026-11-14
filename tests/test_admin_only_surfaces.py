"""Bulk and irreversible surfaces are admin-only; automations keep them.

The wall tablet runs as a standard user: it must not be able to start an
import, a migration check that writes archives, a catalogue-wide resync, or
hard-delete a recipe. A call with no user at all (an automation, a script)
is not a person and keeps working, exactly as Home Assistant's own admin
services behave.
"""
from __future__ import annotations

import itertools
import shutil

import pytest
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized

from custom_components.home_stock.const import DOMAIN

# (service, payload, answers)
ADMIN_SERVICES = [
    ("import_grocy_catalog", {}, True),
    ("import_grocy_stock", {}, True),
    ("import_grocy_recipes", {}, True),
    ("import_grocy_equipment", {"database_path": "grocy_import.db"}, True),
    ("check_grocy_migration", {"archive": False}, True),
    ("resync_off", {"all": True}, False),
]

_IDS = itertools.count(1)


@pytest.fixture
async def loaded(hass: HomeAssistant, setup_entry, grocy_reel_db):
    entry = await setup_entry()
    shutil.copy(grocy_reel_db, hass.config.path("grocy_import.db"))
    # The stock import refuses lots whose product is not in the catalogue.
    await hass.services.async_call(
        DOMAIN, "import_grocy_catalog", {"apply": True}, blocking=True,
        return_response=True)
    return entry


async def _call(hass, service, payload, answers, user):
    result = await hass.services.async_call(
        DOMAIN, service, dict(payload), blocking=True, return_response=answers,
        context=Context(user_id=user.id) if user else None)
    await hass.async_block_till_done()
    return result


def _dump(entry):
    return list(entry.runtime_data.manager.db.read().iterdump())


@pytest.mark.parametrize("service, payload, answers", ADMIN_SERVICES)
async def test_a_standard_user_is_refused(
        hass, loaded, hass_read_only_user, service, payload, answers):
    before = _dump(loaded)
    with pytest.raises(Unauthorized):
        await _call(hass, service, payload, answers, hass_read_only_user)
    assert _dump(loaded) == before
    assert loaded.runtime_data.resync_in_progress is False


@pytest.mark.parametrize("who", ["admin", "automation"])
@pytest.mark.parametrize("service, payload, answers", ADMIN_SERVICES)
async def test_an_admin_and_an_automation_still_run_it(
        hass, loaded, hass_admin_user, who, service, payload, answers):
    user = hass_admin_user if who == "admin" else None
    result = await _call(hass, service, payload, answers, user)
    if answers:
        assert isinstance(result, dict)


async def _recipe(hass, entry) -> int:
    return await hass.async_add_executor_job(
        lambda: entry.runtime_data.manager.create_recipe(name="Soupe"))


async def _ws(client, **payload):
    await client.send_json({"id": next(_IDS), **payload})
    return await client.receive_json()


async def test_the_tablet_cannot_hard_delete_a_recipe(
        hass, loaded, hass_ws_client, hass_read_only_access_token):
    recipe_id = await _recipe(hass, loaded)
    client = await hass_ws_client(hass, hass_read_only_access_token)
    answer = await _ws(client, type="home_stock/recipe/delete", recipe_id=recipe_id)
    assert answer["success"] is False
    assert answer["error"]["code"] == "unauthorized"
    assert loaded.runtime_data.manager.get_recipe_view(recipe_id)["recipe"]["name"] == "Soupe"


async def test_an_admin_still_deletes_a_recipe(hass, loaded, hass_ws_client):
    recipe_id = await _recipe(hass, loaded)
    client = await hass_ws_client(hass)
    answer = await _ws(client, type="home_stock/recipe/delete", recipe_id=recipe_id)
    assert answer["success"] is True, answer
    with pytest.raises(ValueError, match="unknown recipe"):
        loaded.runtime_data.manager.get_recipe_view(recipe_id)
