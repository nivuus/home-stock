"""Every Grocy import reads a copy under config/, read-only, and nothing else.

`validators.grocy_database_path` states the rule (relative, under the
configuration directory, never climbs); every service that opens a Grocy copy
must apply it, and the copy must be opened read-only whatever characters its
name holds.
"""
import importlib
import shutil
import sqlite3
from pathlib import Path

import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError

from custom_components.home_stock.const import DOMAIN

# (service, name of its path field)
IMPORT_SERVICES = [
    ("import_grocy_catalog", "path"),
    ("import_grocy_equipment", "database_path"),
    ("import_grocy_stock", "database_path"),
    ("import_grocy_recipes", "database_path"),
    ("check_grocy_migration", "database_path"),
]

OPENERS = [
    "import_grocy", "import_grocy_equipment", "import_grocy_stock",
    "import_grocy_recipes", "migration_check",
]


async def _refusal(hass, service, payload) -> Exception | None:
    try:
        await hass.services.async_call(
            DOMAIN, service, payload, blocking=True, return_response=True)
    except (HomeAssistantError, vol.Invalid) as err:
        assert str(err)
        return err
    return None


@pytest.mark.parametrize("service, field", IMPORT_SERVICES)
@pytest.mark.parametrize("value", ["/etc/hostname", "../outside.db", "sub/../../outside.db"])
async def test_every_import_refuses_a_path_outside_config(
        hass, setup_entry, service, field, value):
    await setup_entry()
    assert await _refusal(hass, service, {field: value}) is not None, (
        f"home_stock.{service} accepted {field}={value!r}")


@pytest.mark.parametrize("service, field", IMPORT_SERVICES)
async def test_every_import_refuses_a_link_leading_out_of_config(
        hass, setup_entry, tmp_path_factory, grocy_reel_db, service, field):
    outside = tmp_path_factory.mktemp("outside") / "grocy.db"
    shutil.copy(grocy_reel_db, outside)
    await setup_entry()
    Path(hass.config.path("linked.db")).symlink_to(outside)
    refusal = await _refusal(hass, service, {field: "linked.db"})
    # Refused for the path itself, not because the copy failed to import.
    assert type(getattr(refusal, "__cause__", None)).__name__ == "GrocyCopyOutsideConfig", (
        f"home_stock.{service} followed a link out of config/: {refusal!r}")


@pytest.mark.parametrize("module", OPENERS)
@pytest.mark.parametrize("name", ["grocy#copy.db", "grocy?mode=rwc.db", "grocy%20copy.db"])
def test_the_copy_is_opened_read_only_whatever_its_name(
        tmp_path, grocy_reel_db, module, name):
    target = tmp_path / "dir" / name
    target.parent.mkdir()
    shutil.copy(grocy_reel_db, target)
    before = sorted(p.name for p in target.parent.iterdir())

    opener = importlib.import_module(f"custom_components.home_stock.{module}")._open_grocy
    conn = opener(str(target))
    try:
        # The file named, not a truncation of its name.
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] > 0
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("CREATE TABLE probe (x)")
    finally:
        conn.close()
    assert sorted(p.name for p in target.parent.iterdir()) == before


async def test_a_copy_inside_config_is_still_imported(hass, setup_entry, grocy_reel_db):
    await setup_entry()
    shutil.copy(grocy_reel_db, hass.config.path("grocy#import.db"))
    answer = await hass.services.async_call(
        DOMAIN, "import_grocy_catalog", {"path": "grocy#import.db"},
        blocking=True, return_response=True)
    assert answer["products"] > 0
