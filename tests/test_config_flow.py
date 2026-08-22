import pytest
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import (
    CONF_EXPIRATION_ALERT_DAYS,
    CONF_GOALS,
    CONF_RECIPE_AGENT,
    CONF_RECIPE_SOURCE_KEY,
    DEFAULT_EXPIRATION_ALERT_DAYS,
    DEFAULT_RECIPE_SOURCE_KEY,
    DOMAIN,
    GOAL_NUTRIENTS,
    MAX_GOAL,
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


# --- lot 4 ------------------------------------------------------------------

async def test_the_options_flow_offers_the_shopping_list_horizon(hass):
    """« Ce que je prépare » et « ce pour quoi je fais les courses » ne sont
    pas forcément la même durée : le planning garde `MEAL_HORIZON_DAYS`, la
    liste a la sienne."""
    from custom_components.home_stock.const import (
        CONF_SHOPPING_LIST_HORIZON_DAYS, DEFAULT_SHOPPING_LIST_HORIZON_DAYS,
    )
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    keys = {str(key) for key in result["data_schema"].schema}
    assert CONF_SHOPPING_LIST_HORIZON_DAYS in keys

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_EXPIRATION_ALERT_DAYS: DEFAULT_EXPIRATION_ALERT_DAYS,
                    CONF_SHOPPING_LIST_HORIZON_DAYS: 14})
    await hass.async_block_till_done()
    assert entry.options[CONF_SHOPPING_LIST_HORIZON_DAYS] == 14
    assert DEFAULT_SHOPPING_LIST_HORIZON_DAYS == 7


async def test_the_horizon_is_bounded(hass):
    """Zéro jour ne réclamerait jamais rien pour un repas ; un an de
    planning demanderait des courses pour des repas qui n'existent pas."""
    from custom_components.home_stock.const import CONF_SHOPPING_LIST_HORIZON_DAYS
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(Exception):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_EXPIRATION_ALERT_DAYS: DEFAULT_EXPIRATION_ALERT_DAYS,
                        CONF_SHOPPING_LIST_HORIZON_DAYS: 0})


async def test_the_options_flow_refuses_an_entity_without_attachments(hass):
    """En français, AU RÉGLAGE. Découvrir ça sur un parking à 21 h n'est pas
    un moment acceptable."""
    from homeassistant.components.ai_task import AITaskEntityFeature

    from custom_components.home_stock.const import CONF_RECEIPT_AGENT
    from custom_components.home_stock.receipt import task as receipt_task

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("ai_task.sans_photo", "unknown",
                          {"supported_features": AITaskEntityFeature.GENERATE_DATA})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_EXPIRATION_ALERT_DAYS: DEFAULT_EXPIRATION_ALERT_DAYS,
                    CONF_RECEIPT_AGENT: "ai_task.sans_photo"})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_RECEIPT_AGENT: "no_attachments"}
    assert receipt_task is not None


async def test_the_options_flow_accepts_an_entity_with_attachments(hass):
    from homeassistant.components.ai_task import AITaskEntityFeature

    from custom_components.home_stock.const import CONF_RECEIPT_AGENT

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        "ai_task.gemini", "unknown",
        {"supported_features": AITaskEntityFeature.GENERATE_DATA
                               | AITaskEntityFeature.SUPPORT_ATTACHMENTS})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_EXPIRATION_ALERT_DAYS: DEFAULT_EXPIRATION_ALERT_DAYS,
                    CONF_RECEIPT_AGENT: "ai_task.gemini"})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_RECEIPT_AGENT] == "ai_task.gemini"


async def test_an_empty_receipt_agent_is_a_valid_setting(hass):
    """Même forme que `recipe_agent` au lot 3 : `vol.Optional` plus
    `suggested_value`, jamais `default=""` — `EntitySelector` refuse la
    chaîne vide, et « pas d'agent » deviendrait irreprésentable."""
    from custom_components.home_stock.const import CONF_RECEIPT_AGENT

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    keys = {str(key) for key in result["data_schema"].schema}
    assert CONF_RECEIPT_AGENT in keys
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_EXPIRATION_ALERT_DAYS: DEFAULT_EXPIRATION_ALERT_DAYS})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options.get(CONF_RECEIPT_AGENT) is None


async def test_the_horizon_option_survives_a_round_trip(hass):
    from custom_components.home_stock.const import CONF_SHOPPING_LIST_HORIZON_DAYS

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_EXPIRATION_ALERT_DAYS: DEFAULT_EXPIRATION_ALERT_DAYS,
                    CONF_SHOPPING_LIST_HORIZON_DAYS: 10})
    await hass.async_block_till_done()

    again = await hass.config_entries.options.async_init(entry.entry_id)
    field = next(key for key in again["data_schema"].schema
                 if str(key) == CONF_SHOPPING_LIST_HORIZON_DAYS)
    assert field.default() == 10


# --- lot 2bis : les neuf plafonds journaliers -------------------------------

async def test_the_options_flow_offers_the_nine_goals_all_optional(hass):
    """Le schéma est FERMÉ sur GOAL_NUTRIENTS : un objectif sur un nutriment
    que le journal ne fige pas ne pourrait être comparé à rien."""
    _, result = await _open_options(hass)
    champs = {str(key): key for key in result["data_schema"].schema}
    attendus = {f"goal_{nutrient}" for nutrient in GOAL_NUTRIENTS}
    assert attendus <= set(champs)
    assert {c for c in champs if c.startswith("goal_")} == attendus
    for nom in attendus:
        assert isinstance(champs[nom], vol.Optional)


async def test_an_empty_goals_form_writes_no_goal_at_all(hass):
    """Un champ vidé OMET la clé, il n'écrit pas 0 : « pas d'objectif » doit
    rester exprimable, et 0 voudrait dire « tout est un dépassement »."""
    entry, result = await _open_options(hass)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_EXPIRATION_ALERT_DAYS: 3,
                    CONF_RECIPE_AGENT: "conversation.bleuenn",
                    CONF_RECIPE_SOURCE_KEY: "9973533"})
    await hass.async_block_till_done()

    assert entry.options.get(CONF_GOALS, {}) == {}
    # Les options voisines survivent : le repli ne les emporte pas.
    assert entry.options[CONF_EXPIRATION_ALERT_DAYS] == 3
    assert entry.options[CONF_RECIPE_AGENT] == "conversation.bleuenn"
    assert entry.options[CONF_RECIPE_SOURCE_KEY] == "9973533"


async def test_a_goal_is_folded_into_a_single_dict(hass):
    entry, result = await _open_options(hass)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_EXPIRATION_ALERT_DAYS: 3, "goal_salt": 6})
    await hass.async_block_till_done()

    assert entry.options[CONF_GOALS] == {"salt": 6.0}
    # Le reste du composant ne voit jamais les neuf clés plates.
    assert "goal_salt" not in entry.options


async def test_a_goal_is_suggested_not_imposed_and_can_be_cleared(hass):
    entry, result = await _open_options(hass)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_EXPIRATION_ALERT_DAYS: 3, "goal_salt": 6})
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    champ = next(key for key in result["data_schema"].schema
                 if str(key) == "goal_salt")
    assert champ.default is vol.UNDEFINED
    assert champ.description == {"suggested_value": 6.0}

    await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_EXPIRATION_ALERT_DAYS: 3})
    await hass.async_block_till_done()
    assert entry.options[CONF_GOALS] == {}


async def test_a_goal_out_of_bounds_fails_the_form_and_keeps_the_options(hass):
    """Refusé DANS le formulaire, en français, et sans rien écrire.

    Les bornes ne sont plus portées par le schéma mais par `_check_bounds` :
    une fonction Python posée dans un schéma ne se sérialise pas et rend le
    formulaire injoignable (cf.
    `test_le_formulaire_d_options_est_serialisable_pour_l_interface`). Le
    refus se lit donc en `errors`, là où l'écran l'affiche, au lieu de
    remonter en `vol.Invalid` — mêmes bornes, même refus d'écrire.
    """
    entry, result = await _open_options(hass)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_EXPIRATION_ALERT_DAYS: 3, "goal_salt": 6})
    await hass.async_block_till_done()
    avant = dict(entry.options)

    for mauvais in (0, -1, MAX_GOAL + 1):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_EXPIRATION_ALERT_DAYS: 3, "goal_salt": mauvais})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"goal_salt": "goal_out_of_bounds"}
        assert dict(entry.options) == avant


async def test_a_goal_that_is_not_a_number_is_refused_by_the_field_itself(hass):
    """Le sélecteur numérique tranche avant le formulaire : un mot ne peut
    même pas être saisi dans le champ, et arrive ici par programme."""
    entry, result = await _open_options(hass)
    avant = dict(entry.options)
    with pytest.raises(vol.Invalid):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_EXPIRATION_ALERT_DAYS: 3, "goal_salt": "beaucoup"})
    assert dict(entry.options) == avant



async def test_a_source_key_too_long_is_refused_in_the_form(hass):
    entry, result = await _open_options(hass)
    avant = dict(entry.options)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_EXPIRATION_ALERT_DAYS: 3,
                    CONF_RECIPE_SOURCE_KEY: "9" * 201})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_RECIPE_SOURCE_KEY: "text_too_long"}
    assert dict(entry.options) == avant


# --- le chemin réel de l'interface ------------------------------------------

async def test_le_formulaire_d_options_est_serialisable_pour_l_interface(hass):
    """Ouvrir les réglages depuis l'interface ne lit pas `data_schema.schema` :
    Home Assistant SÉRIALISE le schéma (`helpers/data_entry_flow._prepare_result_json`
    → `voluptuous_serialize.convert`) avant de l'envoyer au navigateur.

    Un validateur qui est une fonction Python nue n'y est pas convertible :
    `convert` lève `ValueError: Unable to convert schema`, aiohttp le rend en
    « 500 Internal Server Error » et l'écran dit seulement « Le flux de
    configuration n'a pas pu être chargé ». Tous les autres tests de ce fichier
    inspectent l'objet Python et ne touchent jamais ce chemin — d'où un
    formulaire vert en test et injoignable en production.
    """
    import voluptuous_serialize
    from homeassistant.helpers import config_validation as cv

    _, result = await _open_options(hass)
    champs = voluptuous_serialize.convert(
        result["data_schema"], custom_serializer=cv.custom_serializer)

    noms = {champ["name"] for champ in champs}
    assert CONF_EXPIRATION_ALERT_DAYS in noms
    assert CONF_RECIPE_SOURCE_KEY in noms
    assert {f"goal_{nutrient}" for nutrient in GOAL_NUTRIENTS} <= noms
