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

PANEL_URL = "home-stock"
STATIC_URL = "/home_stock_panel"
MODULE_URL = f"{STATIC_URL}/home-stock-panel.js"
PANEL_TITLE = "Garde-manger"
PANEL_ICON = "mdi:fridge-outline"

# Set once the static path has been registered and never cleared: aiohttp's
# router offers no way to unregister a route (HomeAssistantHTTP._async_register
# _static_paths always does a bare app.router.add_route, no dedup). The
# sidebar panel, in contrast, is scoped to this config entry — it is added on
# setup and removed on unload through frontend.async_register_built_in_panel /
# async_remove_panel, which do dedupe (the former raises on a re-add unless
# the previous one was removed first). Gating both under one flag meant that
# discarding it on unload (so the panel could come back on the next setup,
# e.g. every options-change reload) also cleared it for the static path,
# which then got registered again — one more dead route behind the router,
# for the life of the process, on every reload. Hence two lifetimes, not one.
_STATIC_PATH_REGISTERED_KEY = "home_stock_static_path_registered"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Serve the bundle (once) and put the panel in the sidebar (every setup)."""
    if not hass.data.get(_STATIC_PATH_REGISTERED_KEY):
        directory = os.path.join(os.path.dirname(__file__), "panel")
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, directory, cache_headers=False)]
        )
        hass.data[_STATIC_PATH_REGISTERED_KEY] = True

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


def async_remove_panel(hass: HomeAssistant) -> None:
    """Take the sidebar panel back out when the entry is unloaded.

    Only the panel, never the static path: the bundle keeps being served
    (harmlessly — nobody links to it without the panel) because there is no
    way to take the route back out of aiohttp's router.
    """
    frontend.async_remove_panel(hass, PANEL_URL)
