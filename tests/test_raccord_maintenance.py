"""Le raccord, testé sans jamais toucher l'instance vivante.

Les copies de référence sont dans le dépôt ; le test les monte dans un Home
Assistant DE TEST, dont `config/` est un répertoire temporaire. Rien d'autre
n'est autorisé : pas de `docker compose`, pas de rechargement, pas de lecture
de jeton, aucune écriture dans le `config/` de la maison.
"""
import json
import re
from pathlib import Path

from homeassistant.helpers import template as template_helper

RACINE = Path(__file__).resolve().parent.parent
RACCORD = RACINE / "docs" / "raccord" / "maintenance.jinja"
AVANT = RACINE / "tests" / "fixtures" / "maintenance" / "avant.jinja"
AUTOMATION_AVANT = RACINE / "tests" / "fixtures" / "maintenance" / "automation_avant.yaml"
MAJAUTO_AVANT = RACINE / "tests" / "fixtures" / "maintenance" / "majauto_avant.yaml"
ETATS = json.loads(
    (RACINE / "tests" / "fixtures" / "maintenance" / "etats.json").read_text(
        encoding="utf-8"))

_REGEX_MAJ = re.compile(r"firmware\|micrologiciel\|system_apt\|docker_homeassistant")


def _peupler(hass):
    """L'instantané versionné, posé dans la machine à états du test."""
    for row in ETATS:
        hass.states.async_set(row["entity_id"], row["state"], row["attributes"])


async def _rendre(hass, fichier: Path) -> str:
    """Monte `fichier` comme `maintenance.jinja` dans le HA de test, puis rend
    le macro. `hass.config.path()` pointe sur un répertoire temporaire — jamais
    sur le `config/` de la maison."""
    dossier = Path(hass.config.path("custom_templates"))
    await hass.async_add_executor_job(lambda: dossier.mkdir(parents=True, exist_ok=True))
    cible = dossier / "maintenance.jinja"
    await hass.async_add_executor_job(
        lambda: cible.write_text(fichier.read_text(encoding="utf-8"), encoding="utf-8"))
    await template_helper.async_load_custom_templates(hass)
    rendu = template_helper.Template(
        "{% from 'maintenance.jinja' import maintenance_plan %}"
        "{{ maintenance_plan() }}", hass)
    return rendu.async_render(parse_result=False)


def _hors_piles(plan):
    """Tout ce qui n'est pas une tâche de pile, résumé ET description."""
    return sorted(
        (i["summary"], i["description"]) for i in plan["items"]
        if not i["summary"].startswith(
            ("Pile à changer — ", "Recharger — ", "Pile HS ? — ")))


def _extraire_regex(texte: str) -> str:
    trouve = _REGEX_MAJ.search(texte)
    return trouve.group(0) if trouve else ""


async def test_the_new_macro_still_returns_items_and_keep(hass):
    _peupler(hass)
    plan = json.loads(await _rendre(hass, RACCORD))
    assert set(plan) == {"items", "keep"}
    assert all({"summary", "description", "entity"} <= set(i) for i in plan["items"])


async def test_the_word_grocy_has_disappeared(hass):
    """Le livrable vérifiable du lot, littéralement."""
    assert "grocy" not in RACCORD.read_text(encoding="utf-8").lower()


async def test_the_battery_block_is_gone(hass):
    texte = RACCORD.read_text(encoding="utf-8")
    for disparu in ("piles_exclues", "motifs_exclus", "device_class", "states.sensor",
                    "Pile à changer", "Pile HS ?", "Battery level"):
        assert disparu not in texte, disparu


async def test_the_new_macro_is_fifty_four_lines_shorter(hass):
    avant = len(AVANT.read_text(encoding="utf-8").splitlines())
    apres = len(RACCORD.read_text(encoding="utf-8").splitlines())
    assert avant - apres == 54


async def test_blocks_one_two_four_and_five_are_untouched(hass):
    """Ce test est la seule preuve que la suppression n'a rien emporté
    d'autre : on rend l'AVANT et l'APRÈS sur les mêmes états, et on vérifie
    que la différence est exactement l'ensemble des tâches de pile."""
    _peupler(hass)
    avant = json.loads(await _rendre(hass, AVANT))
    apres = json.loads(await _rendre(hass, RACCORD))
    partis = {i["summary"] for i in avant["items"]} - {i["summary"] for i in apres["items"]}
    assert all(p.startswith(("Pile à changer — ", "Recharger — ", "Pile HS ? — "))
               for p in partis)
    assert {i["summary"] for i in apres["items"]} <= {i["summary"] for i in avant["items"]}
    # et rien n'a changé de description côté aspirateurs, filtres et plantes
    assert _hors_piles(avant) == _hors_piles(apres)
    assert set(apres["keep"]) <= set(avant["keep"])


async def test_the_removed_summaries_are_only_battery_ones(hass):
    """Le pendant du test précédent sur `keep` : ce qui disparaît de
    l'hystérésis doit être exactement les piles, sinon une tâche
    d'aspirateur se refermerait à la première synchro."""
    _peupler(hass)
    avant = json.loads(await _rendre(hass, AVANT))
    apres = json.loads(await _rendre(hass, RACCORD))
    partis = set(avant["keep"]) - set(apres["keep"])
    assert all(p.startswith(("Pile à changer — ", "Recharger — ", "Pile HS ? — "))
               for p in partis), partis


async def test_the_new_macro_never_walks_states_sensor(hass):
    """Le macro parcourait 28 capteurs à chaque appel. Il n'en parcourt plus
    aucun — les seuils des blocs 1, 2 et 4 nomment leurs entités."""
    texte = RACCORD.read_text(encoding="utf-8")
    assert "states.sensor" not in texte
    # `states.update` reste, et c'est voulu : le bloc 5 ne peut pas nommer à
    # l'avance les entités de mise à jour qui apparaîtront.
    assert "states.update" in texte


async def test_the_manual_update_regex_is_identical_in_both_reference_files(hass):
    """Dette ouverte depuis le 2026-07-31 : la regex est dupliquée dans le
    macro et dans l'automation « Système - Mises à jour automatiques ». Les
    deux doivent rester identiques, sinon une MAJ est soit installée d'office,
    soit réclamée à vie dans la liste."""
    depuis_macro = _extraire_regex(RACCORD.read_text(encoding="utf-8"))
    depuis_auto = _extraire_regex(MAJAUTO_AVANT.read_text(encoding="utf-8"))
    assert depuis_macro == depuis_auto != ""


async def test_the_render_is_valid_json_on_the_real_snapshot(hass):
    """Un macro qui rend du JSON invalide fait échouer la variable `plan` de
    l'automation, donc toute la réconciliation, en silence côté tablettes."""
    _peupler(hass)
    json.loads(await _rendre(hass, RACCORD))


async def test_the_reference_file_is_not_the_installed_one(hass):
    """Garde-fou explicite : ce dépôt LIVRE le raccord, il ne l'installe
    jamais. Si ce chemin existait sous `config/`, une tâche aurait écrit dans
    la maison."""
    assert RACCORD.is_file()
    assert RACCORD.parts[-3:] == ("docs", "raccord", "maintenance.jinja")
    assert "/config/custom_templates" not in str(RACCORD)
