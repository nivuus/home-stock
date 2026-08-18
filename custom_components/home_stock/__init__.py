"""The Garde-manger integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .application import StockManager
from .const import DATABASE_FILENAME
from .coordinator import HomeStockCoordinator
from .services import async_register_services
from .storage.database import Database
from .storage.migrations import apply_migrations

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.TODO]


@dataclass
class HomeStockData:
    """What the entry keeps alive while it is loaded."""

    database: Database
    manager: StockManager
    coordinator: HomeStockCoordinator


type HomeStockConfigEntry = ConfigEntry[HomeStockData]


async def async_setup_entry(hass: HomeAssistant, entry: HomeStockConfigEntry) -> bool:
    """Open the database, migrate it, and start the coordinator."""
    database = Database(hass.config.path(DATABASE_FILENAME))

    def _open() -> None:
        database.connect()
        with database.write() as conn:
            apply_migrations(conn)

    try:
        await hass.async_add_executor_job(_open)
    except Exception as err:
        # Close whatever got opened so the retry does not inherit a dangling
        # connection and a stale lock on the file.
        await hass.async_add_executor_job(database.close)
        raise ConfigEntryNotReady(
            f"Could not open the database at {database.path}: {err}"
        ) from err

    manager = StockManager(database)
    coordinator = HomeStockCoordinator(hass, entry, manager)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = HomeStockData(database, manager, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    async_register_services(hass)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: HomeStockConfigEntry) -> None:
    """Options changed: reload so the new threshold is applied."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HomeStockConfigEntry) -> bool:
    """Close the database when the entry goes away."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await hass.async_add_executor_job(entry.runtime_data.database.close)
    return unloaded
