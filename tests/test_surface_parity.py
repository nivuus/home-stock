"""Aucune des deux surfaces n'a le droit d'être la plus faible.

La règle du lot 1, répétée au lot 2, tient sans exception : ce que le
websocket refuse, le service le refuse, et réciproquement. Un refus d'un seul
côté n'est pas une asymétrie mineure — c'est une porte dérobée dans la
validation, et elle s'ouvre toujours du côté qu'on n'a pas testé.

Écrit AVANT les services, comme `test_offline_queue_contract.py` l'a été pour
la file : c'est un contrat, pas une vérification a posteriori.
"""
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

# (commande websocket, service, charge, attendu)
CAS_LIMITES = [
    ("home_stock/list/add", "add_to_shopping_list",
     {"free_text": "Pain", "quantity": 0}, "refusé"),
    ("home_stock/list/add", "add_to_shopping_list",
     {"free_text": "Pain", "quantity": -1}, "refusé"),
    ("home_stock/list/add", "add_to_shopping_list",
     {"free_text": "Pain", "quantity": 100_001}, "refusé"),
    ("home_stock/list/add", "add_to_shopping_list",
     {"free_text": "x" * 300}, "refusé"),
    ("home_stock/list/add", "add_to_shopping_list", {}, "refusé"),
    ("home_stock/list/add", "add_to_shopping_list",
     {"free_text": "Pain", "quantity": 500}, "accepté"),
    ("home_stock/movement/correct", "correct_movement",
     {"movement_id": 4242}, "refusé"),
    ("home_stock/movement/correct", "correct_movement",
     {"movement_id": -3}, "refusé"),
    ("home_stock/meal/correct", "correct_meal", {"meal_id": -3}, "refusé"),
    ("home_stock/meal/correct", "correct_meal", {"meal_id": 4242}, "refusé"),
    ("home_stock/list/refresh", "refresh_shopping_list", {}, "accepté"),
    # Lot 7 : le contrôle de bascule. Les deux surfaces lisent le MÊME schéma.
    ("home_stock/migration/check", "check_grocy_migration",
     {"database_path": "../secrets.yaml"}, "refusé"),
    ("home_stock/migration/check", "check_grocy_migration",
     {"database_path": "/etc/passwd"}, "refusé"),
    ("home_stock/migration/check", "check_grocy_migration",
     {"acknowledged": ["all"]}, "refusé"),
    ("home_stock/migration/check", "check_grocy_migration",
     {"acknowledged": "grocy:stock:419"}, "refusé"),   # une chaîne, pas une liste
    ("home_stock/migration/check", "check_grocy_migration",
     {"archive": False}, "accepté"),
]


async def _websocket_verdict(hass, client, id_, command, payload):
    await client.send_json({"id": id_, "type": command, **payload})
    answer = await client.receive_json()
    return "accepté" if answer.get("success") else "refusé"


async def _service_verdict(hass, service, payload):
    from homeassistant.helpers.service import async_get_all_descriptions

    descriptions = await async_get_all_descriptions(hass)
    supports_response = descriptions["home_stock"][service].get("response") is not None
    try:
        await hass.services.async_call(
            "home_stock", service, dict(payload), blocking=True,
            return_response=supports_response)
    except (HomeAssistantError, vol_invalid()) as err:
        assert str(err)
        return "refusé"
    return "accepté"


def vol_invalid():
    import voluptuous as vol
    return vol.Invalid


@pytest.mark.parametrize("command, service, payload, expected", CAS_LIMITES)
async def test_neither_surface_is_weaker_than_the_other(
        hass: HomeAssistant, setup_entry, hass_ws_client,
        command, service, payload, expected):
    """Un refus d'un seul côté n'est pas une asymétrie mineure : c'est une
    porte dérobée dans la validation, et elle s'ouvre toujours du côté qu'on
    n'a pas testé."""
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    from_websocket = await _websocket_verdict(hass, client, 1, command, payload)
    from_service = await _service_verdict(hass, service, payload)

    assert from_websocket == from_service == expected, (
        f"{command} → {from_websocket}, home_stock.{service} → {from_service}")


async def test_the_two_surfaces_share_the_same_validators():
    """Les bornes du lot 4 vivent UNE FOIS, dans `validators.py`, et sont
    utilisées des deux côtés. Deux copies, ce sont deux vocabulaires dans
    six mois — et une seule des deux corrigée."""
    from custom_components.home_stock import services, validators, websocket_api

    for name in ("list_quantity", "every_days", "store_name", "price_source"):
        shared = getattr(validators, name)
        assert getattr(websocket_api, name, shared) is shared
        assert getattr(services, name, shared) is shared


async def test_services_yaml_documents_every_new_field(hass: HomeAssistant,
                                                       setup_entry):
    """Un champ accepté par le schéma et absent de `services.yaml` est un
    champ que l'interface ne montrera jamais."""
    from pathlib import Path

    import yaml

    from custom_components.home_stock import services as module

    await setup_entry(with_article=True)
    described = yaml.safe_load(
        (Path(module.__file__).parent / "services.yaml").read_text(encoding="utf-8"))

    for service, schema in (
            ("add_to_shopping_list", module.ADD_TO_LIST_SCHEMA),
            ("refresh_shopping_list", module.REFRESH_LIST_SCHEMA),
            ("query_shopping_list", module.QUERY_LIST_SCHEMA),
            ("read_receipt", module.READ_RECEIPT_SCHEMA),
            ("correct_movement", module.CORRECT_MOVEMENT_SCHEMA),
            ("correct_meal", module.CORRECT_MEAL_SCHEMA),
    ):
        assert service in described, service
        fields = set(described[service].get("fields") or {})
        expected = {str(key) for key in schema.schema}
        assert expected <= fields, f"{service}: {expected - fields}"


# --- lot 6 : la SEULE asymétrie assumée du lot -----------------------------
#
# `slot_key` existe sur le service `query_meals` et PAS sur la commande
# websocket `home_stock/meals/list`. Ce n'est pas un oubli : `meals/list` rend
# la plage complète et le panneau la découpe lui-même, tandis que le filtrage
# par créneau est une commodité pour le VOCAL, qui n'a pas de tableau où
# chercher. Ajouter le filtre au websocket serait ajouter du code que personne
# n'exerce — et du code jamais exercé est du code faux qui s'ignore.
#
# Ce que la parité continue d'exiger : le REFUS d'une valeur hors
# `MEAL_SLOT_KEYS` doit être identique partout où ce champ existe, donc entre
# `query_meals` et `home_stock/meal/plan`, qui le porte depuis le lot 3.

async def test_slot_key_asymmetry_is_a_documented_choice(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """`meals/list` n'a pas de `slot_key`, et l'accepterait-il en silence que
    ce test tomberait — un champ ignoré est pire qu'un champ refusé."""
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    verdict = await _websocket_verdict(
        hass, client, 1, "home_stock/meals/list",
        {"start": "2026-08-21", "end": "2026-08-21", "slot_key": "dinner"})
    assert verdict == "refusé"

    # Et le service, lui, l'accepte : c'est l'asymétrie, écrite.
    assert await _service_verdict(
        hass, "query_meals",
        {"start": "2026-08-21", "end": "2026-08-21", "slot_key": "dinner"}
    ) == "accepté"


async def test_the_slot_vocabulary_is_the_same_on_both_surfaces(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """`query_meals` et `home_stock/meal/plan` refusent le même mot."""
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    from_websocket = await _websocket_verdict(
        hass, client, 1, "home_stock/meal/plan",
        {"day": "2026-08-21", "slot_key": "gouter", "note": "x"})
    from_service = await _service_verdict(
        hass, "query_meals",
        {"start": "2026-08-21", "end": "2026-08-21", "slot_key": "gouter"})

    assert from_websocket == from_service == "refusé"
