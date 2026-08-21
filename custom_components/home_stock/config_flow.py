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
    CONF_GOALS,
    CONF_RECIPE_AGENT,
    CONF_RECEIPT_AGENT,
    CONF_RECIPE_SOURCE_KEY,
    CONF_SHOPPING_LIST_HORIZON_DAYS,
    DEFAULT_EXPIRATION_ALERT_DAYS,
    DEFAULT_RECIPE_SOURCE_KEY,
    DEFAULT_SHOPPING_LIST_HORIZON_DAYS,
    DOMAIN,
    GOAL_NUTRIENTS,
)
from .receipt.task import supports_attachments
from .validators import bounded_text, goal_quantity


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
        errors: dict[str, str] = {}
        if user_input is not None:
            # L'entité de lecture est validée QUAND ELLE EST CHOISIE, pas
            # quand elle sert : découvrir à 21 h sur un parking qu'elle
            # n'accepte pas de pièce jointe n'est pas un moment acceptable
            # pour l'apprendre.
            chosen = user_input.get(CONF_RECEIPT_AGENT)
            if chosen and not supports_attachments(self.hass, chosen):
                errors[CONF_RECEIPT_AGENT] = "no_attachments"
            if not errors:
                return self.async_create_entry(data=_fold_goals(user_input))
        options = self.config_entry.options
        current = options.get(CONF_EXPIRATION_ALERT_DAYS, DEFAULT_EXPIRATION_ALERT_DAYS)
        source_key = options.get(CONF_RECIPE_SOURCE_KEY, DEFAULT_RECIPE_SOURCE_KEY)
        # Une fenêtre distincte de MEAL_HORIZON_DAYS, et pas par symétrie :
        # « ce que je prépare » et « ce pour quoi je fais les courses » ne
        # sont pas forcément la même durée. Le planning garde la sienne.
        horizon = options.get(CONF_SHOPPING_LIST_HORIZON_DAYS,
                              DEFAULT_SHOPPING_LIST_HORIZON_DAYS)
        # The agent carries a SUGGESTED value, not a default. `EntitySelector`
        # refuses the empty string as an entity id, so a `default=""` would
        # make "no agent" unrepresentable — and clearing the field would fail
        # validation instead of turning adaptation off. Suggested-value plus
        # `vol.Optional` means an emptied field simply omits the key, which
        # reads back as None: no agent, no adaptation, no error.
        goals = options.get(CONF_GOALS, {}) or {}
        agent_field = vol.Optional(CONF_RECIPE_AGENT)
        if options.get(CONF_RECIPE_AGENT):
            agent_field = vol.Optional(
                CONF_RECIPE_AGENT,
                description={"suggested_value": options[CONF_RECIPE_AGENT]})
        # Même forme, et pour la même raison, que `recipe_agent`.
        receipt_field = vol.Optional(CONF_RECEIPT_AGENT)
        if options.get(CONF_RECEIPT_AGENT):
            receipt_field = vol.Optional(
                CONF_RECEIPT_AGENT,
                description={"suggested_value": options[CONF_RECEIPT_AGENT]})
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_EXPIRATION_ALERT_DAYS, default=current):
                    vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
                agent_field:
                    EntitySelector(EntitySelectorConfig(domain="conversation")),
                vol.Optional(CONF_RECIPE_SOURCE_KEY, default=source_key):
                    vol.All(TextSelector(), bounded_text),
                vol.Required(CONF_SHOPPING_LIST_HORIZON_DAYS, default=horizon):
                    vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                receipt_field:
                    EntitySelector(EntitySelectorConfig(domain="ai_task")),
                # Les neuf plafonds, ajoutés en fin de schéma et construits
                # par compréhension sur GOAL_NUTRIENTS : le formulaire est
                # fermé sur les nutriments que le journal fige, et une clé de
                # plus ne peut pas y entrer par recopie.
                **{_goal_field(nutrient, goals): goal_quantity
                   for nutrient in GOAL_NUTRIENTS},
            }),
            errors=errors,
        )


def _goal_field(nutrient: str, goals: dict[str, Any]) -> vol.Optional:
    """One optional cap field, carrying a SUGGESTED value, never a default.

    A `default=` would put the value back into a form somebody just emptied,
    making "no goal any more" unreachable — the same trap `CONF_RECIPE_AGENT`
    avoids for the same reason.
    """
    key = f"goal_{nutrient}"
    if goals.get(nutrient) is None:
        return vol.Optional(key)
    return vol.Optional(key, description={"suggested_value": goals[nutrient]})


def _fold_goals(user_input: dict[str, Any]) -> dict[str, Any]:
    """The nine flat `goal_*` fields, folded into one `nutrition_goals` dict.

    An emptied field OMITS its nutrient rather than writing 0: "no goal" has
    to stay expressible, and a cap of zero would make every day a breach. The
    rest of the component never sees the nine flat keys.
    """
    folded = dict(user_input)
    goals: dict[str, float] = {}
    for nutrient in GOAL_NUTRIENTS:
        value = folded.pop(f"goal_{nutrient}", None)
        if value is not None:
            goals[nutrient] = value
    folded[CONF_GOALS] = goals
    return folded
