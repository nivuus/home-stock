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


# --- le paquet `intent_script` ----------------------------------------------

PAQUET = "packages/home_stock_intents.yaml"

# Ce qu'une étape de service porte en plus des champs déclarés dans
# `services.yaml` : ce ne sont pas des champs, et les compter comme tels
# ferait échouer le contrôle sur des clés parfaitement légitimes.
_NON_CHAMPS = {"action", "response_variable", "target", "entity_id", "alias",
               "enabled", "continue_on_error", "metadata"}


def _etapes_de_service(corps) -> list[dict]:
    return [etape for etape in corps.get("action") or []
            if isinstance(etape, dict) and "action" in etape]


def _champs_employes(etape: dict) -> set[str]:
    """Les noms de champs qu'une étape passe au service.

    `data` est tantôt un dictionnaire, tantôt un gabarit qui rend un
    dictionnaire (c'est le cas de `query_meals`, dont le créneau est
    facultatif). Les deux formes sont acceptées par Home Assistant, donc les
    deux doivent être lues ici — sinon le contrôle croirait qu'aucun champ
    n'est employé et passerait sans rien prouver.
    """
    data = etape.get("data")
    if isinstance(data, dict):
        return set(data)
    if isinstance(data, str):
        return set(re.findall(r"'(\w+)'\s*:", data))
    return set()


def test_the_package_defines_exactly_the_seven_intents():
    document = _load(PAQUET)
    assert set(document["intent_script"]) == SEPT_INTENTS


def test_every_sentence_intent_has_a_script_and_the_reverse():
    """L'appariement, le seul contrôle qui attrape la panne « Bleuenn a
    compris et n'a rien dit »."""
    phrases = set(_load(PHRASES)["intents"])
    scripts = set(_load(PAQUET)["intent_script"])
    assert phrases == scripts


def test_every_action_validates_through_home_assistant():
    """`cv.SCRIPT_SCHEMA`, pas un simple `isinstance(dict)` : la faute
    classique est d'écrire `service:` là où HA 2026.8 attend `action:`, et
    seul le schéma du produit la voit."""
    from homeassistant.helpers import config_validation as cv

    for nom, corps in _load(PAQUET)["intent_script"].items():
        if "action" not in corps:
            continue
        assert cv.SCRIPT_SCHEMA(corps["action"]), nom


# De quoi rendre chaque mise en phrase sur son cas PLEIN. Les clés sont celles
# que les services rendent réellement (`query_stock` → `products`,
# `query_shopping_list` → `items`/`count`, `validate_meal` → `lines`).
VARIABLES_PLEINES = {
    "HomeStockQueryStock": {
        "product": "lait",
        "reponse": {"products": [
            {"product_name": "Lait", "display": "1 l"},
            {"product_name": "Lait de coco", "display": "400 ml"},
        ]},
    },
    "HomeStockQueryMeals": {
        "reponse": {"meals": [
            {"recipe_name": "Gratin", "product_name": None, "note": None},
            {"recipe_name": None, "product_name": None, "note": "Restaurant"},
        ]},
    },
    "HomeStockQueryShoppingList": {
        "reponse": {"count": 3,
                    "items": {"Frais": [{"name": "Lait"}, {"name": "Beurre"}],
                              "Boulangerie": [{"name": "Pain"}]}},
    },
    "HomeStockAddToShoppingList": {
        "product": "beurre", "reponse": {"item_id": 4, "created": True},
    },
    "HomeStockQueryExpirations": {},
    "HomeStockValidateMeal": {
        "apercu": {"lines": [
            {"label": "200 g", "product_name": "Pommes de terre"},
            {"label": "2 pièces", "product_name": "Œufs"},
        ]},
    },
    "HomeStockQueryToday": {},
}


def test_every_speech_template_is_valid_jinja(hass):
    """Un template cassé rend l'intent muet à l'exécution, jamais au
    chargement. `ensure_valid` déplace la panne au moment où on peut la voir."""
    from homeassistant.helpers.template import Template

    for nom, corps in _load(PAQUET)["intent_script"].items():
        Template(corps["speech"]["text"], hass).ensure_valid()


# Le même jeu, mais rien à dire. `reponse` reste DÉFINI : c'est un
# `response_variable`, il existe toujours après l'appel — ce qui est vide,
# c'est son contenu. Les deux intents sans service n'ont, eux, aucune variable.
VARIABLES_VIDES = {
    "HomeStockQueryStock": {"product": "lait", "reponse": {"products": []}},
    "HomeStockQueryMeals": {"reponse": {"meals": []}},
    "HomeStockQueryShoppingList": {"reponse": {"count": 0, "items": {}}},
    "HomeStockAddToShoppingList": {"product": "beurre",
                                   "reponse": {"item_id": 4, "created": False}},
    "HomeStockQueryExpirations": {},
    # Aucun repas planifié : la condition arrête le script avant l'appel, donc
    # `apercu` n'est jamais posé. C'est exactement ce que la mise en phrase
    # doit savoir dire.
    "HomeStockValidateMeal": {},
    "HomeStockQueryToday": {},
}


def test_every_speech_template_actually_renders(hass):
    """`ensure_valid` ne COMPILE que : il laisse passer ce que le bac à sable
    Jinja de Home Assistant refuse à l'exécution — `list.append` en tête, qui
    a réellement cassé les trois mises en phrase de ce paquet et le blueprint
    du lot. Une compilation réussie ne prouve donc rien ; seul un rendu le
    fait. Les deux cas sont éprouvés : la liste pleine et la liste vide."""
    from homeassistant.helpers.template import Template

    for nom, corps in _load(PAQUET)["intent_script"].items():
        gabarit = Template(corps["speech"]["text"], hass)
        plein = gabarit.async_render(variables=VARIABLES_PLEINES[nom],
                                     parse_result=False).strip()
        vide = gabarit.async_render(variables=VARIABLES_VIDES[nom],
                                    parse_result=False).strip()
        assert plein, f"{nom} : rien à dire sur un cas plein"
        assert vide, f"{nom} : silence sur un cas vide — le silence est une panne"


def test_every_service_payload_actually_renders(hass):
    """La charge d'un appel est un gabarit comme un autre — celle de
    `query_meals` en est un en entier, pour rendre le créneau facultatif. Un
    filtre qui n'existe pas y serait invisible jusqu'au premier « qu'est-ce
    qu'on mange ce soir ? »."""
    from homeassistant.helpers.template import Template

    attendu = {
        "HomeStockQueryMeals": (
            {"jour": "2026-08-21", "creneau": "dinner"},
            {"start": "2026-08-21", "end": "2026-08-21", "slot_key": "dinner"}),
    }
    for nom, corps in _load(PAQUET)["intent_script"].items():
        for etape in _etapes_de_service(corps):
            data = etape.get("data")
            if not isinstance(data, str):
                continue
            variables, resultat = attendu[nom]
            rendu = Template(data, hass).async_render(variables=variables,
                                                      parse_result=True)
            assert rendu == resultat, f"{nom} : {rendu}"


def test_every_service_called_exists_with_the_fields_used():
    """Un `slot_key` mal orthographié dans l'intent serait refusé par
    `vol.In` au moment où quelqu'un parle. Ce test compare les champs
    employés à `services.yaml`, la déclaration qui fait foi."""
    from custom_components.home_stock import services as module

    declares = yaml.safe_load(
        (Path(module.__file__).parent / "services.yaml").read_text(encoding="utf-8"))

    for nom, corps in _load(PAQUET)["intent_script"].items():
        for etape in _etapes_de_service(corps):
            domaine, _, service = etape["action"].partition(".")
            if domaine != "home_stock":
                continue
            assert service in declares, f"{nom}: {service}"
            connus = set(declares[service].get("fields") or {})
            employes = _champs_employes(etape) - _NON_CHAMPS
            assert employes <= connus, f"{nom}: {employes - connus}"


def test_the_meal_intent_previews_before_it_writes(hass):
    """LA règle du lot 6 sur l'écriture vocale : le premier tour ne doit RIEN
    décrémenter. Si le `dry_run` cesse de dépendre de la confirmation, une
    phrase mal comprise vide un stock sans qu'on l'ait dit — et le journal
    étant en ajout seul, elle ne s'annule pas : elle se contrepasse, depuis
    le panneau.

    Le brief demandait de chercher la chaîne littérale « dry_run: true » dans
    le paquet. Impossible sans dupliquer l'appel de service dans un `choose`,
    dont le `response_variable` serait alors HORS DE PORTÉE de la mise en
    phrase — l'intent parlerait dans le vide. Le contrôle porte donc sur ce
    que le gabarit RÉPOND, ce qui prouve la même chose en plus fort :
    sans confirmation, `dry_run` vaut vrai.
    """
    from homeassistant.helpers.template import Template

    corps = _load(PAQUET)["intent_script"]["HomeStockValidateMeal"]
    appels = [e for e in _etapes_de_service(corps)
              if e["action"] == "home_stock.validate_meal"]
    assert len(appels) == 1, "un seul appel, sinon le second tour se dédouble"
    gabarit = str(appels[0]["data"]["dry_run"])

    premier_tour = Template(gabarit, hass).async_render(
        variables={}, parse_result=True)
    second_tour = Template(gabarit, hass).async_render(
        variables={"confirm": "yes"}, parse_result=True)
    assert premier_tour is True, gabarit
    assert second_tour is False, gabarit

    assert "confirme" in corps["speech"]["text"].lower()


def test_no_intent_calls_a_writing_service_other_than_the_two_allowed():
    """`add_stock`, `consume`, `waste`, `remove_from_shopping_list`,
    `correct_movement` n'ont RIEN à faire dans un paquet vocal. Deux verbes,
    et ce test est la barrière."""
    interdits = {"home_stock.add_stock", "home_stock.consume", "home_stock.waste",
                 "home_stock.remove_from_shopping_list", "home_stock.correct_movement",
                 "home_stock.correct_meal", "home_stock.plan_meal", "todo.remove_item"}
    rendu = json.dumps(_load(PAQUET), ensure_ascii=False)
    for service in interdits:
        assert service not in rendu, service


def test_every_intent_answers_something_when_there_is_nothing():
    """« Il ne reste plus d'œufs » est une réponse ; le silence est une panne.
    Chaque `speech.text` doit porter un `{% if %}…{% else %}…` — un template
    qui rend la chaîne vide sur une liste vide est un intent qui a l'air
    cassé."""
    for nom, corps in _load(PAQUET)["intent_script"].items():
        # `{%- else %}` autant que `{% else %}` : le tiret ne fait que manger
        # les blancs, il ne change rien à l'existence de la branche — et une
        # mise en phrase multiligne en a besoin partout.
        assert re.search(r"\{%-?\s*else\s*-?%\}", corps["speech"]["text"]), nom

