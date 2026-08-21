"""`home_stock/migration/check` — une commande, et la parité.

Aucune des deux surfaces n'a le droit d'être la plus faible. Les deux lisent
la MÊME constante de schéma et appellent la MÊME fonction : une divergence
serait une porte dérobée dans la validation, et elle s'ouvre toujours du côté
qu'on n'a pas testé.
"""
import shutil

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import DOMAIN


@pytest.fixture
async def entree(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
def grocy_dans_config(hass, grocy_reel_db):
    shutil.copy(grocy_reel_db, hass.config.path("grocy_import.db"))
    return hass.config.path("grocy_import.db")


async def test_the_command_answers_the_twelve_checks(hass, entree,
                                                     hass_ws_client,
                                                     grocy_dans_config):
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "home_stock/migration/check",
                            "archive": False})
    reponse = await client.receive_json()
    assert reponse["success"]
    assert len(reponse["result"]["checks"]) == 12


async def test_both_surfaces_return_the_very_same_object(hass, entree,
                                                         hass_ws_client,
                                                         grocy_dans_config):
    """Même code, même réponse. Une divergence ici serait une porte dérobée
    dans la validation, et elle s'ouvre toujours du côté qu'on n'a pas testé."""
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "home_stock/migration/check",
                            "archive": False})
    par_ws = (await client.receive_json())["result"]
    par_service = await hass.services.async_call(
        DOMAIN, "check_grocy_migration", {"archive": False},
        blocking=True, return_response=True)
    assert par_ws == par_service


async def test_the_two_imports_have_no_websocket_twin(hass, entree,
                                                      hass_ws_client):
    """Choix inscrit, pas oubli : un import de masse se lance depuis Outils
    de développement, une fois, en lisant son rapport en entier."""
    client = await hass_ws_client(hass)
    for numero, commande in enumerate(
            ("home_stock/migration/import_stock",
             "home_stock/migration/import_recipes"), start=9):
        await client.send_json({"id": numero, "type": commande})
        assert not (await client.receive_json())["success"]


async def test_no_new_entity_is_created(hass, entree):
    """La bascule est un événement, pas un état. Un
    binary_sensor.home_stock_migration_ok resterait `on` pour toujours après
    le premier passage et n'apprendrait plus rien à personne."""
    assert hass.states.get("binary_sensor.home_stock_migration_ok") is None


@pytest.mark.parametrize("charge", [
    {"database_path": "../secrets.yaml"},
    {"database_path": "/etc/passwd"},
    {"acknowledged": ["all"]},
    {"acknowledged": "grocy:stock:419"},
])
async def test_the_command_refuses_what_the_service_refuses(hass, entree,
                                                            hass_ws_client,
                                                            charge):
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "home_stock/migration/check",
                            **charge})
    assert not (await client.receive_json())["success"]


async def test_the_command_never_writes_the_archive_without_being_asked(
        hass, entree, hass_ws_client, grocy_dans_config):
    """Le panneau relance ce contrôle vingt fois pendant la bascule : écrire
    l'archive à chaque fois recopierait 1 123 lignes vingt fois."""
    from pathlib import Path
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "home_stock/migration/check",
                            "archive": False})
    reponse = await client.receive_json()
    assert reponse["result"]["archive_path"] is None
    assert not list(Path(hass.config.path("")).glob(
        "home_stock_grocy_archive_*.json"))
