"""`peut_fermer` — le drapeau qui empêche de refermer quatorze tâches.

Ces tests EXÉCUTENT réellement l'automation de référence dans un Home
Assistant de test, avec des services `todo.*` factices. On n'inspecte pas ses
variables internes : on regarde ce qu'elle APPELLE, parce que c'est cela qui
ferme une tâche dans la vraie maison.
"""
import json
from pathlib import Path

import pytest
import yaml
from homeassistant.core import SupportsResponse
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def expected_lingering_timers():
    """Le déclencheur `time_pattern` de l'automation pose un minuteur que
    l'arrêt du Home Assistant de test ne défait pas. C'est le comportement
    normal d'un `time_pattern`, pas une fuite du raccord."""
    return True

RACINE = Path(__file__).resolve().parent.parent
SYNC_YAML = RACINE / "docs" / "raccord" / "maintenance_sync.yaml"
AVANT_YAML = RACINE / "tests" / "fixtures" / "maintenance" / "automation_avant.yaml"
RACCORD = RACINE / "docs" / "raccord" / "maintenance.jinja"
AVANT = RACINE / "tests" / "fixtures" / "maintenance" / "avant.jinja"
ETATS = json.loads(
    (RACINE / "tests" / "fixtures" / "maintenance" / "etats.json").read_text(
        encoding="utf-8"))

# L'entité que le garde-fou de l'automation interroge. Extraite du YAML plutôt
# que recopiée : un test plus bas vérifie qu'elle existe vraiment.
GARDE_FOU = "sensor.home_stock_batteries_low"

PLAN_COMPLET = {
    "items": [{"summary": "Pile à changer — Velux (CH)", "description": "18 %",
               "entity": "sensor.velux_ch_batterie"}],
    "keep": ["Pile à changer — Velux (CH)"],
    "complete": True,
}


def _annonce(bloc):
    """Le texte que l'automation envoie à Bleuenn, quel que soit son
    emplacement dans la séquence."""
    trouve = []

    def _marche(noeud):
        if isinstance(noeud, dict):
            if noeud.get("action") == "personas_home.send_event":
                trouve.append(noeud["data"]["text"])
            for valeur in noeud.values():
                _marche(valeur)
        elif isinstance(noeud, list):
            for valeur in noeud:
                _marche(valeur)

    _marche(bloc)
    return trouve


class _Journal:
    """Ce que l'automation a appelé, dans l'ordre."""

    def __init__(self) -> None:
        self.appels: list[tuple[str, dict]] = []

    def services(self) -> list[str]:
        return [nom for nom, _ in self.appels]

    def fermetures(self) -> list[str]:
        return [data.get("item") for nom, data in self.appels
                if nom == "todo.update_item" and data.get("status") == "completed"]

    def ajouts(self) -> list[str]:
        return [data.get("item") for nom, data in self.appels
                if nom == "todo.add_item"]


async def _preparer(hass, *, service_repond, taches_presentes=(), plan_macro=None):
    """Monte l'automation de référence avec des `todo.*` factices.

    `service_repond=None` simule `home_stock` injoignable : le service n'est
    PAS enregistré du tout, ce qui est exactement ce qui se passe quand
    l'intégration est déchargée ou que Home Assistant démarre.
    """
    journal = _Journal()
    await async_setup_component(hass, "homeassistant", {})

    def _enregistre(domaine, service, reponse=None):
        def _cb(call):
            journal.appels.append((f"{domaine}.{service}", dict(call.data)))
            return reponse
        hass.services.async_register(
            domaine, service, _cb,
            supports_response=(SupportsResponse.ONLY if reponse is not None
                               else SupportsResponse.NONE))

    # `home_stock` « injoignable » se joue en ne déclarant AUCUNE entité de ce
    # domaine : c'est ce que l'automation teste par `integration_entities`.
    if service_repond is not None:
        hass.states.async_set(GARDE_FOU, "0")

    presents = {"todo.maintenance": {"items": [
        {"summary": s, "description": ""} for s in taches_presentes]}}
    _enregistre("todo", "get_items", presents)
    _enregistre("todo", "add_item")
    _enregistre("todo", "update_item")
    _enregistre("todo", "remove_completed_items")
    _enregistre("personas_home", "send_event")
    if service_repond is not None:
        _enregistre("home_stock", "maintenance_plan", service_repond)

    # Le macro : monté dans le `config/` TEMPORAIRE du Home Assistant de test.
    from homeassistant.helpers import template as template_helper
    dossier = Path(hass.config.path("custom_templates"))
    await hass.async_add_executor_job(lambda: dossier.mkdir(parents=True, exist_ok=True))
    contenu = (plan_macro if plan_macro is not None
               else RACCORD.read_text(encoding="utf-8"))
    await hass.async_add_executor_job(
        lambda: (dossier / "maintenance.jinja").write_text(contenu, encoding="utf-8"))
    await template_helper.async_load_custom_templates(hass)

    bloc = yaml.safe_load(SYNC_YAML.read_text(encoding="utf-8"))
    assert await async_setup_component(hass, "automation", {"automation": bloc})
    await hass.async_block_till_done()
    return journal


async def _executer(hass, journal):
    await hass.services.async_call(
        "automation", "trigger",
        {"entity_id": "automation.maintenance_synchronisation_liste_de_taches",
         "skip_condition": True}, blocking=True)
    await hass.async_block_till_done()
    return journal


async def test_the_new_automation_is_valid_yaml_and_keeps_its_id(hass):
    bloc = yaml.safe_load(SYNC_YAML.read_text(encoding="utf-8"))
    assert bloc[0]["id"] == "maintenance_sync_taches"
    assert bloc[0]["mode"] == "single"


async def test_grocy_is_gone_from_the_automation(hass):
    """Le livrable vérifiable du lot, du côté de l'automation."""
    assert "grocy" not in SYNC_YAML.read_text(encoding="utf-8").lower()


async def test_the_trigger_and_the_announcement_are_untouched(hass):
    """Les tablettes ne doivent demander aucune modification : c'est un
    OBJECTIF du raccord, pas un heureux hasard. `todo.maintenance` reste
    l'entité, son compte reste le compte, et `pieces.ts` ne bouge pas."""
    avant = yaml.safe_load(AVANT_YAML.read_text(encoding="utf-8"))
    apres = yaml.safe_load(SYNC_YAML.read_text(encoding="utf-8"))
    assert avant[0]["triggers"] == apres[0]["triggers"]
    assert _annonce(avant) == _annonce(apres)


async def test_a_reachable_and_complete_plan_arms_the_closing(hass):
    """Le cas nominal : le service répond, `complete` est vrai, on ferme ce qui
    doit être fermé."""
    journal = await _preparer(
        hass, service_repond=PLAN_COMPLET,
        taches_presentes=["Pile à changer — Ancienne", "Pile à changer — Velux (CH)"])
    await _executer(hass, journal)
    assert journal.fermetures() == ["Pile à changer — Ancienne"]
    assert "todo.remove_completed_items" in journal.services()


async def test_an_unreachable_service_closes_nothing_at_all(hass):
    """LE test du lot. Sans lui, une indisponibilité de home_stock refermerait
    les quatorze tâches de pile en une synchronisation, à 5 h 05, sans que
    personne ne le voie avant le lendemain."""
    journal = await _preparer(
        hass, service_repond=None,
        taches_presentes=["Pile à changer — Velux (CH)", "Pile à changer — Porte"])
    await _executer(hass, journal)
    assert journal.fermetures() == []
    assert "todo.remove_completed_items" not in journal.services()


async def test_an_incomplete_plan_closes_nothing_either(hass):
    """L'intégration répond mais sa base est illisible : `complete: false`.
    `fusionne is not none` ne suffit pas — c'est pourquoi le drapeau regarde
    `complete`."""
    journal = await _preparer(
        hass, service_repond={"items": [], "keep": [], "complete": False},
        taches_presentes=["Pile à changer — Velux (CH)"])
    await _executer(hass, journal)
    assert journal.fermetures() == []
    assert "todo.remove_completed_items" not in journal.services()


async def test_a_response_without_the_complete_key_disarms(hass):
    """Le défaut d'un garde-fou doit être « prudent », jamais « permissif »."""
    journal = await _preparer(
        hass, service_repond={"items": [], "keep": []},
        taches_presentes=["Pile à changer — Velux (CH)"])
    await _executer(hass, journal)
    assert journal.fermetures() == []


async def test_a_disarmed_run_still_adds_and_refreshes(hass):
    """« Quand le plan est incomplet, on a le droit d'ajouter et de rafraîchir,
    jamais de fermer. » Désarmer la fermeture ne doit pas geler la liste."""
    macro = (
        "{%- macro maintenance_plan() -%}\n"
        "{{- {'items': [{'summary': 'Nouvelle tâche', 'description': 'x',"
        " 'entity': ''}], 'keep': ['Nouvelle tâche']} | to_json -}}\n"
        "{%- endmacro -%}\n")
    journal = await _preparer(hass, service_repond=None, plan_macro=macro,
                              taches_presentes=["Pile à changer — Velux (CH)"])
    await _executer(hass, journal)
    assert journal.ajouts() == ["Nouvelle tâche"]
    assert journal.fermetures() == []


async def test_the_mute_component_never_removes_completed_items(hass):
    """`todo.remove_completed_items` purge la liste : le laisser tourner sur
    une liste qu'on vient de cocher à tort effacerait les quatorze tâches pour
    de bon. Il est DANS le `if`, pas après."""
    journal = await _preparer(hass, service_repond=None,
                              taches_presentes=["Pile à changer — Velux (CH)"])
    await _executer(hass, journal)
    assert "todo.remove_completed_items" not in journal.services()


async def test_the_macro_plan_is_handed_to_the_service(hass):
    """Le service reçoit les items du macro, sinon il ne pourrait pas les
    recopier et la tâche du purificateur disparaîtrait."""
    macro = (
        "{%- macro maintenance_plan() -%}\n"
        "{{- {'items': [{'summary': 'Purificateur — filtre à remplacer',"
        " 'description': '12 %', 'entity': 'sensor.purificateur_filtre'}],"
        " 'keep': ['Purificateur — filtre à remplacer']} | to_json -}}\n"
        "{%- endmacro -%}\n")
    journal = await _preparer(hass, service_repond=PLAN_COMPLET, plan_macro=macro)
    await _executer(hass, journal)
    appel = next(data for nom, data in journal.appels
                 if nom == "home_stock.maintenance_plan")
    assert appel["extra_items"][0]["summary"] == "Purificateur — filtre à remplacer"
    assert appel["extra_keep"] == ["Purificateur — filtre à remplacer"]


async def test_the_full_chain_on_the_real_snapshot_is_neutral(hass, setup_entry):
    """Déploiement neutre, bout en bout : sur les états de la fixture, et avec
    les piles importées, l'ensemble des résumés que l'automation VEUT est égal
    à celui que le macro d'AVANT produisait — et elle n'ajoute ni ne ferme
    rien."""
    import sqlite3

    from homeassistant.helpers import template as template_helper

    integration = await setup_entry()
    for row in ETATS:
        hass.states.async_set(row["entity_id"], row["state"], row["attributes"])

    # L'import réel, sur la fixture Grocy versionnée.
    fixture = RACINE / "tests" / "fixtures" / "grocy" / "equipment.sql"
    copie = Path(hass.config.path("grocy-copie.db"))

    def _semer():
        conn = sqlite3.connect(str(copie))
        conn.executescript(fixture.read_text(encoding="utf-8"))
        conn.commit()
        conn.close()

    await hass.async_add_executor_job(_semer)
    rapport = await hass.services.async_call(
        "home_stock", "import_grocy_equipment",
        {"database_path": str(copie), "apply": True},
        blocking=True, return_response=True)
    assert rapport["summary_diff"] == [], rapport["summary_diff"]
    await integration.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    # Ce que le macro d'AVANT produisait sur ces mêmes états.
    dossier = Path(hass.config.path("custom_templates"))
    await hass.async_add_executor_job(lambda: dossier.mkdir(parents=True, exist_ok=True))
    await hass.async_add_executor_job(
        lambda: (dossier / "maintenance.jinja").write_text(
            AVANT.read_text(encoding="utf-8"), encoding="utf-8"))
    await template_helper.async_load_custom_templates(hass)
    avant = json.loads(template_helper.Template(
        "{% from 'maintenance.jinja' import maintenance_plan %}"
        "{{ maintenance_plan() }}", hass).async_render(parse_result=False))

    # Ce que le nouveau plan, macro raccourci + service réel, produit.
    reponse = await hass.services.async_call(
        "home_stock", "maintenance_plan",
        {"extra_items": [], "extra_keep": []}, blocking=True, return_response=True)
    assert reponse["complete"] is True
    piles_avant = {s for s in avant["keep"]
                   if s.startswith(("Pile à changer — ", "Recharger — ", "Pile HS ? — "))}
    assert set(reponse["keep"]) == piles_avant


async def test_the_guard_names_an_entity_the_integration_really_creates(hass, setup_entry):
    """Le garde-fou nomme une entité en dur. La renommer désarmerait
    silencieusement le plan des piles pour toujours : plus aucun appel au
    service, `peut_fermer` faux à jamais, et quatorze tâches qui ne se
    fermeraient plus. Ce test est ce qui rend ce couplage visible."""
    texte = SYNC_YAML.read_text(encoding="utf-8")
    assert GARDE_FOU in texte
    await setup_entry()
    assert hass.states.get(GARDE_FOU) is not None


async def test_the_guard_disappears_when_the_entry_unloads(hass, setup_entry):
    """L'autre moitié : l'entité doit vraiment quitter la machine à états quand
    l'intégration se décharge, sinon le garde-fou laisserait passer l'appel et
    l'automation s'arrêterait sur « service introuvable »."""
    entry = await setup_entry()
    assert hass.states.get(GARDE_FOU) is not None
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    etat = hass.states.get(GARDE_FOU)
    assert etat is None or etat.state in ("unknown", "unavailable")
