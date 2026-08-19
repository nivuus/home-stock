"""The panel is registered, served, and removed with the entry."""
import os

import pytest
from homeassistant.core import HomeAssistant

from custom_components.home_stock import panel
from custom_components.home_stock.panel import PANEL_URL

# Same directory panel.async_register_panel serves from — kept in sync with
# it rather than hardcoded here, so this path can't silently drift from the
# one actually registered.
_BUNDLE_PATH = os.path.join(os.path.dirname(panel.__file__), "panel", "home-stock-panel.js")


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
    # Accepting either 200 or 404 here would pass whether or not the static
    # path was ever registered — no signal either way. A built tree must get
    # a real 200; an unbuilt one skips with a reason instead of lying green.
    if not os.path.isfile(_BUNDLE_PATH):
        pytest.skip(
            f"bundle not built: {_BUNDLE_PATH} does not exist "
            "(run `cd frontend && npm run build`)"
        )

    await setup_entry()
    client = await hass_client()

    response = await client.get("/home_stock_panel/home-stock-panel.js")

    assert response.status == 200
