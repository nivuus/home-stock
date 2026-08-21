"""One entry, no credentials: everything is local."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
)

from .const import (
    CONF_EXPIRATION_ALERT_DAYS,
    CONF_RECIPE_AGENT,
    CONF_RECIPE_SOURCE_KEY,
    DEFAULT_EXPIRATION_ALERT_DAYS,
    DEFAULT_RECIPE_SOURCE_KEY,
    DOMAIN,
)
from .validators import bounded_text


class HomeStockConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the single entry."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title="Garde-manger", data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HomeStockOptionsFlow()


class HomeStockOptionsFlow(OptionsFlow):
    """How many days before a date counts as expiring, plus lot 3's two.

    The conversation agent is deliberately OPTIONAL: leaving it empty is a
    setting, not an error. It means imported recipes stay in the source's
    language and are flagged for review — a perfectly usable state, and the
    only one available on an installation with no agent at all.
    """

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        current = options.get(CONF_EXPIRATION_ALERT_DAYS, DEFAULT_EXPIRATION_ALERT_DAYS)
        source_key = options.get(CONF_RECIPE_SOURCE_KEY, DEFAULT_RECIPE_SOURCE_KEY)
        # The agent carries a SUGGESTED value, not a default. `EntitySelector`
        # refuses the empty string as an entity id, so a `default=""` would
        # make "no agent" unrepresentable — and clearing the field would fail
        # validation instead of turning adaptation off. Suggested-value plus
        # `vol.Optional` means an emptied field simply omits the key, which
        # reads back as None: no agent, no adaptation, no error.
        agent_field = vol.Optional(CONF_RECIPE_AGENT)
        if options.get(CONF_RECIPE_AGENT):
            agent_field = vol.Optional(
                CONF_RECIPE_AGENT,
                description={"suggested_value": options[CONF_RECIPE_AGENT]})
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_EXPIRATION_ALERT_DAYS, default=current):
                    vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
                agent_field:
                    EntitySelector(EntitySelectorConfig(domain="conversation")),
                vol.Optional(CONF_RECIPE_SOURCE_KEY, default=source_key):
                    vol.All(TextSelector(), bounded_text),
            }),
        )
