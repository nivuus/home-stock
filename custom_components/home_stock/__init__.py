"""The Garde-manger integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration

from .application import StockManager
from .const import DATABASE_FILENAME, DOMAIN
from .coordinator import HomeStockCoordinator
from .off.client import AiohttpTransport, OffClient
from .services import async_register_services
from .shopping import ShoppingService
from .storage.database import Database
from .storage.migrations import apply_migrations
from .websocket_api import async_register_websocket

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.TODO]


@dataclass
class HomeStockData:
    """What the entry keeps alive while it is loaded."""

    database: Database
    manager: StockManager
    coordinator: HomeStockCoordinator
    shopping: ShoppingService
    off_client: OffClient
    # The single transport both the OFF cascade (via off_client) and the
    # websocket handlers' Open Prices calls run over. Held here, once, rather
    # than each caller building its own AiohttpTransport(async_get_clientsession(hass)):
    # a test that swaps this one field out for a fake closes every network
    # path at once, instead of having to know about every call site that
    # happens to construct its own transport.
    transport: AiohttpTransport
    user_agent: str


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

    # OFF refuses anonymous clients, so the agent names the integration, its
    # version and a way to reach its owner — the contact OFF asks for.
    version = (await async_get_integration(hass, DOMAIN)).version or "1.0"
    user_agent = f"home_stock/{version} (Home Assistant; maxime@allanic.me)"
    transport = AiohttpTransport(async_get_clientsession(hass))
    off_client = OffClient(transport, user_agent=user_agent)
    shopping = ShoppingService(manager)

    entry.runtime_data = HomeStockData(
        database, manager, coordinator, shopping, off_client, transport, user_agent
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    async_register_services(hass)
    async_register_websocket(hass)
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
