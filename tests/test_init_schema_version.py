"""Set-up refuses, without retrying, a database written by a newer release."""
from types import MappingProxyType

from homeassistant.config_entries import SOURCE_USER, ConfigEntry, ConfigEntryState

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import (
    CURRENT_VERSION,
    apply_migrations,
)


def _entry() -> ConfigEntry:
    return ConfigEntry(
        data={}, discovery_keys=MappingProxyType({}), domain=DOMAIN, minor_version=1,
        options={}, source=SOURCE_USER, subentries_data=None, title="Garde-manger",
        unique_id=None, version=1,
    )


async def test_setup_fails_for_good_on_a_newer_schema(hass):
    def _newer() -> None:
        db = Database(hass.config.path("home_stock.db"))
        db.connect()
        with db.write() as conn:
            apply_migrations(conn)
            conn.execute("UPDATE schema_version SET version = ?", (CURRENT_VERSION + 1,))
        db.close()

    await hass.async_add_executor_job(_newer)
    entry = _entry()
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()

    # SETUP_RETRY would retry for ever against a schema that cannot change.
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert str(CURRENT_VERSION + 1) in (entry.reason or "")
