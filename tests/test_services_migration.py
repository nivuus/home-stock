"""Les trois services de la bascule, tous en simulation par défaut.

Ils suivent exactement la forme d'`import_grocy_catalog` (lot 0) et
d'`import_grocy_equipment` (lot 5) : `SupportsResponse.ONLY`, un rapport
complet en retour, et un rafraîchissement du coordinateur UNIQUEMENT si
`apply`. Rafraîchir après une simulation ne ferait que gâcher une lecture.
"""
import shutil
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError
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
    """La copie de grocy.db, posée dans config/ — geste 3 de la procédure.

    Le conteneur Home Assistant ne voit que config/ et media/ : c'est ce qui
    rend cette copie obligatoire, et c'est pour ça que le chemin est validé
    comme relatif au dossier de configuration.
    """
    cible = hass.config.path("grocy_import.db")
    shutil.copy(grocy_reel_db, cible)
    return cible


def _batches(hass, entree) -> int:
    return entree.runtime_data.manager.db.read().execute(
        "SELECT COUNT(*) AS n FROM batch").fetchone()["n"]


async def test_the_three_services_are_registered(hass, entree):
    for nom in ("import_grocy_stock", "import_grocy_recipes",
                "check_grocy_migration"):
        assert hass.services.has_service(DOMAIN, nom)


async def _catalogue(hass):
    """Geste 6 : rejouer l'import du catalogue avant tout import de stock."""
    return await hass.services.async_call(
        DOMAIN, "import_grocy_catalog", {"apply": True},
        blocking=True, return_response=True)


async def test_the_stock_import_stops_loudly_without_the_catalogue(
        hass, entree, grocy_dans_config):
    """Sans le geste 6, aucun lot ne se résout — et l'import le DIT au lieu de
    rendre un rapport vide et vert. C'est ce qui rend le rejeu du catalogue
    obligatoire au lieu de recommandé."""
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "import_grocy_stock", {}, blocking=True,
            return_response=True)


async def test_a_dry_run_is_the_default(hass, entree, grocy_dans_config):
    await _catalogue(hass)
    reponse = await hass.services.async_call(
        DOMAIN, "import_grocy_stock", {}, blocking=True, return_response=True)
    assert reponse["batches"] == 108
    # Rien écrit : le défaut ne peut pas être destructeur.
    assert await hass.async_add_executor_job(_batches, hass, entree) == 0


async def test_apply_true_refreshes_the_coordinator(hass, entree,
                                                    grocy_dans_config):
    await _catalogue(hass)
    entree.runtime_data.coordinator.async_request_refresh = AsyncMock()
    await hass.services.async_call(
        DOMAIN, "import_grocy_stock", {"apply": True},
        blocking=True, return_response=True)
    entree.runtime_data.coordinator.async_request_refresh.assert_called_once()
    assert await hass.async_add_executor_job(_batches, hass, entree) == 108


async def test_a_dry_run_does_not_refresh_the_coordinator(hass, entree,
                                                          grocy_dans_config):
    """Rafraîchir après une simulation ne ferait que gâcher une lecture —
    query_stock et export_journal ne le font pas non plus."""
    await _catalogue(hass)
    entree.runtime_data.coordinator.async_request_refresh = AsyncMock()
    await hass.services.async_call(
        DOMAIN, "import_grocy_stock", {}, blocking=True, return_response=True)
    entree.runtime_data.coordinator.async_request_refresh.assert_not_called()


@pytest.mark.parametrize("chemin", [
    "/etc/passwd", "../secrets.yaml", "../../grocy.db", "", "   ",
])
async def test_a_path_outside_config_is_refused(hass, entree, chemin):
    with pytest.raises((vol.Invalid, HomeAssistantError)):
        await hass.services.async_call(
            DOMAIN, "import_grocy_stock", {"database_path": chemin},
            blocking=True, return_response=True)


@pytest.mark.parametrize("dossier", [
    "www/home_stock", "/config/www", "../media", "config/home_stock", "",
])
async def test_a_picture_dir_outside_media_is_refused(hass, entree, dossier):
    """Le lot 5 a tranché : jamais sous www/, qui est servi SANS
    authentification à tout le réseau de la maison."""
    with pytest.raises((vol.Invalid, HomeAssistantError)):
        await hass.services.async_call(
            DOMAIN, "import_grocy_recipes", {"picture_dir": dossier},
            blocking=True, return_response=True)


@pytest.mark.parametrize("valeur", ["all", "*", ["all"], ["*"], ["tout"]])
async def test_acknowledging_everything_does_not_exist(hass, entree,
                                                       grocy_dans_config,
                                                       valeur):
    """« Un bouton "tout va bien" finit toujours par être pressé sans
    regarder. » L'acquittement est NOMINATIF, et ces valeurs sont des
    tentatives de contournement, pas des identifiants."""
    with pytest.raises((vol.Invalid, HomeAssistantError)):
        await hass.services.async_call(
            DOMAIN, "check_grocy_migration", {"acknowledged": valeur},
            blocking=True, return_response=True)


async def test_the_check_returns_twelve_lines_and_a_verdict(hass, entree,
                                                            grocy_dans_config):
    reponse = await hass.services.async_call(
        DOMAIN, "check_grocy_migration", {"archive": False},
        blocking=True, return_response=True)
    assert len(reponse["checks"]) == 12
    assert "blocking" in reponse and "ok" in reponse


async def test_the_check_never_claims_everything_is_fine_on_an_empty_base(
        hass, entree, grocy_dans_config):
    """Le plancher tient jusque dans le service : rien d'importé, donc rouge."""
    reponse = await hass.services.async_call(
        DOMAIN, "check_grocy_migration", {"archive": False},
        blocking=True, return_response=True)
    assert reponse["ok"] is False
    assert reponse["blocking"]


async def test_services_yaml_describes_all_three(hass, entree):
    from homeassistant.helpers.service import async_get_all_descriptions
    d = await async_get_all_descriptions(hass)
    for nom in ("import_grocy_stock", "import_grocy_recipes",
                "check_grocy_migration"):
        assert d[DOMAIN][nom]["description"]
        assert d[DOMAIN][nom].get("response") is not None


async def test_no_service_can_stop_a_container(hass, entree):
    """Le composant n'arrête JAMAIS Grocy."""
    assert not hass.services.has_service(DOMAIN, "stop_grocy")
    assert not hass.services.has_service(DOMAIN, "shutdown_grocy")
    assert not hass.services.has_service(DOMAIN, "apply_raccord")
