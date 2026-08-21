from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import (
    CONF_EXPIRATION_ALERT_DAYS,
    CONF_RECIPE_AGENT,
    CONF_RECIPE_SOURCE_KEY,
    DEFAULT_EXPIRATION_ALERT_DAYS,
    DEFAULT_RECIPE_SOURCE_KEY,
    DOMAIN,
)


async def test_user_flow_creates_the_entry(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garde-manger"


async def test_only_one_entry_is_allowed(hass):
    MockConfigEntry(domain=DOMAIN, data={}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_sets_the_alert_threshold(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_EXPIRATION_ALERT_DAYS: 7}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_EXPIRATION_ALERT_DAYS] == 7
    assert DEFAULT_EXPIRATION_ALERT_DAYS == 3


# --- lot 3 : l'agent conversationnel et la clé de la source -----------------

async def _open_options(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, await hass.config_entries.options.async_init(entry.entry_id)


async def test_the_options_flow_offers_the_conversation_agent_and_the_source_key(hass):
    _, result = await _open_options(hass)
    keys = {str(key) for key in result["data_schema"].schema}
    assert {CONF_EXPIRATION_ALERT_DAYS, CONF_RECIPE_AGENT,
            CONF_RECIPE_SOURCE_KEY} <= keys


async def test_an_empty_agent_is_a_valid_choice(hass):
    """Vide = aucune adaptation. C'est un réglage, pas une erreur — et c'est le
    seul état possible sur une installation sans agent conversationnel."""
    entry, result = await _open_options(hass)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_EXPIRATION_ALERT_DAYS: 3})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert not entry.options.get(CONF_RECIPE_AGENT)


async def test_an_agent_can_be_chosen_and_read_back(hass):
    entry, result = await _open_options(hass)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_EXPIRATION_ALERT_DAYS: 3,
                    CONF_RECIPE_AGENT: "conversation.bleuenn"})
    await hass.async_block_till_done()
    assert entry.options[CONF_RECIPE_AGENT] == "conversation.bleuenn"


async def test_the_source_key_defaults_to_one(hass):
    entry, result = await _open_options(hass)
    await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_EXPIRATION_ALERT_DAYS: 3})
    await hass.async_block_till_done()
    assert entry.options.get(
        CONF_RECIPE_SOURCE_KEY, DEFAULT_RECIPE_SOURCE_KEY) == DEFAULT_RECIPE_SOURCE_KEY


async def test_the_source_key_reaches_the_client_after_a_reload(hass):
    """Changer la clé ne doit pas demander de redémarrer Home Assistant : le
    client est reconstruit à chaque rechargement de l'entrée."""
    entry, result = await _open_options(hass)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_EXPIRATION_ALERT_DAYS: 3,
                    CONF_RECIPE_SOURCE_KEY: "9973533"})
    await hass.async_block_till_done()
    assert entry.runtime_data.recipe_source is not None
    assert entry.runtime_data.recipe_source._key == "9973533"
