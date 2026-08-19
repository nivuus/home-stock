"""Register the panel and serve its bundle.

The panel is a Home Assistant custom panel, not a page under /local/: it is
handed the `hass` object, so it inherits the connection and the authentication
instead of reading a token out of localStorage.
"""
from __future__ import annotations

import os

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PANEL_URL = "home-stock"
STATIC_URL = "/home_stock_panel"
MODULE_URL = f"{STATIC_URL}/home-stock-panel.js"
PANEL_TITLE = "Garde-manger"
PANEL_ICON = "mdi:fridge-outline"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Serve the bundle and put the panel in the sidebar. Idempotent."""
    if DOMAIN in hass.data.get("home_stock_panel_registered", set()):
        return

    directory = os.path.join(os.path.dirname(__file__), "panel")
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, directory, cache_headers=False)]
    )
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="home-stock-panel",
        frontend_url_path=PANEL_URL,
        module_url=MODULE_URL,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
        embed_iframe=False,
    )
    hass.data.setdefault("home_stock_panel_registered", set()).add(DOMAIN)


def async_remove_panel(hass: HomeAssistant) -> None:
    """Take the panel back out when the entry is unloaded."""
    frontend.async_remove_panel(hass, PANEL_URL)
    hass.data.get("home_stock_panel_registered", set()).discard(DOMAIN)
