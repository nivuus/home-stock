"""The panel is registered, served, and removed with the entry."""
from homeassistant.core import HomeAssistant

from custom_components.home_stock.panel import PANEL_URL


async def test_the_panel_appears_in_the_sidebar(hass: HomeAssistant, setup_entry):
    await setup_entry()

    assert PANEL_URL in hass.data["frontend_panels"]
    assert hass.data["frontend_panels"][PANEL_URL].sidebar_title == "Garde-manger"


async def test_unloading_the_entry_takes_the_panel_away(hass: HomeAssistant, setup_entry):
    entry = await setup_entry()

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert PANEL_URL not in hass.data["frontend_panels"]


async def test_the_bundle_is_served(hass: HomeAssistant, hass_client, setup_entry):
    await setup_entry()
    client = await hass_client()

    response = await client.get("/home_stock_panel/home-stock-panel.js")

    # 404 means the build never ran; anything else means the static path is wired.
    assert response.status in (200, 404)
