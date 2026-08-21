"""Le paquet vocal est LIVRÉ, jamais installé — donc jamais chargé par un
test d'intégration. Ce qui reste vérifiable, et qui casse en silence sinon,
c'est sa COHÉRENCE : un intent nommé dans les phrases mais absent du
`intent_script` produit un agent qui reconnaît la phrase et ne répond rien.
C'est la panne la plus difficile à diagnostiquer de tout le lot, parce qu'elle
ressemble à « Bleuenn n'a pas compris ».

Aucun réseau, aucune instance : deux fichiers YAML lus sur le disque.
"""
import json
import re
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parent.parent

SEPT_INTENTS = {
    "HomeStockQueryStock", "HomeStockQueryMeals", "HomeStockQueryShoppingList",
    "HomeStockAddToShoppingList", "HomeStockQueryExpirations",
    "HomeStockValidateMeal", "HomeStockQueryToday",
}

PHRASES = "custom_sentences/fr/home_stock.yaml"


def _load(chemin: str):
    return yaml.safe_load((RACINE / chemin).read_text(encoding="utf-8"))


def _toutes_les_phrases(document) -> list[str]:
    return [phrase
            for corps in document["intents"].values()
            for bloc in corps["data"]
            for phrase in bloc["sentences"]]


# --- les phrases ------------------------------------------------------------

def test_the_sentences_file_declares_exactly_the_seven_intents():
    document = _load(PHRASES)
    assert document["language"] == "fr"
    assert set(document["intents"]) == SEPT_INTENTS


def test_every_intent_has_at_least_two_ways_of_being_said():
    """Une seule formulation par intent, c'est un intent qui ne marchera que
    pour la personne qui l'a écrite. La spec en promet des variantes ; ce test
    les exige."""
    document = _load(PHRASES)
    for nom, corps in document["intents"].items():
        phrases = [p for bloc in corps["data"] for p in bloc["sentences"]]
        assert len(phrases) >= 2, nom


def test_every_slot_used_in_a_sentence_is_declared_as_a_list():
    """`{product}` dans une phrase sans `lists: product:` fait échouer le
    chargement de tout le dossier `custom_sentences` — pas seulement de cette
    phrase-là. Une faute de frappe ici coûte les sept intents."""
    document = _load(PHRASES)
    declarees = set(document.get("lists", {}))
    utilisees: set[str] = set()
    for phrase in _toutes_les_phrases(document):
        utilisees |= set(re.findall(r"\{(\w+)\}", phrase))
    assert utilisees <= declarees, utilisees - declarees


def test_the_slot_list_uses_the_component_vocabulary():
    """Les valeurs rendues par la liste `slot` sont EXACTEMENT
    `MEAL_SLOT_KEYS`. Le vocabulaire des créneaux a un seul propriétaire ;
    « gouter » écrit ici serait refusé par `query_meals` au moment précis où
    quelqu'un parle."""
    from custom_components.home_stock.const import MEAL_SLOT_KEYS

    document = _load(PHRASES)
    valeurs = {v["out"] for v in document["lists"]["slot"]["values"]}
    assert valeurs == set(MEAL_SLOT_KEYS)


def test_the_two_writing_intents_are_the_only_two():
    """La règle du lot : une phrase peut écrire si son effet est BORNÉ et sa
    réparation possible sans urgence. Deux verbes, pas trois. Ce test épingle
    la frontière côté phrases ; `test_no_sentence_asks_to_throw_away` la tient
    côté vocabulaire."""
    document = _load(PHRASES)
    ecrivains = {nom for nom in document["intents"]
                 if not nom.startswith("HomeStockQuery")}
    assert ecrivains == {"HomeStockAddToShoppingList", "HomeStockValidateMeal"}


def test_no_sentence_asks_to_throw_away_or_to_remove_a_line():
    """`waste` est irréversible ET comptabilisé sur douze mois ; retirer une
    ligne de courses écrit un `removed_at` qui EMPÊCHE la ligne de revenir,
    silencieusement, à chaque réconciliation. Ce sont les deux pires erreurs
    vocales possibles — celles qui se réparent mal parce qu'elles ne se voient
    pas. Aucune phrase ne doit pouvoir les déclencher."""
    document = _load(PHRASES)
    texte = json.dumps(document, ensure_ascii=False).lower()
    for interdit in ("jette", "jeter", "poubelle", "enlève de la liste",
                     "retire de la liste", "supprime"):
        assert interdit not in texte, interdit


def test_the_confirmation_of_a_meal_is_not_a_bare_yes():
    """« Oui » tout court détournerait toutes les confirmations de la maison.
    Le second tour du repas se dit en nommant ce qu'on confirme."""
    document = _load(PHRASES)
    blocs = document["intents"]["HomeStockValidateMeal"]["data"]
    confirmations = [bloc for bloc in blocs
                     if (bloc.get("slots") or {}).get("confirm") == "yes"]
    assert confirmations, "aucun bloc de confirmation"
    for bloc in confirmations:
        for phrase in bloc["sentences"]:
            assert phrase.strip().lower() not in ("oui", "ok", "d'accord"), phrase

