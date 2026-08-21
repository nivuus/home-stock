"""L'adaptation par un agent conversationnel : facultative, jamais à moitié.

Aucun de ces tests ne monte l'intégration `conversation` : l'appel passe par le
service, et un double le remplace. C'est exactement pourquoi il passe par le
service plutôt que par un import.
"""
import json

import pytest

from custom_components.home_stock.recipes.adapt import (
    MAX_PROMPT_INSTRUCTIONS,
    AdaptedRecipe,
    adapt,
    build_prompt,
    extract_json,
    validate_adaptation,
)
from custom_components.home_stock.recipes.mapping import (
    SourceIngredient,
    SourceRecipe,
)


def _source(*, ingredients=2, instructions="Preheat oven."):
    return SourceRecipe(
        name="Teriyaki Chicken Casserole", source_ref="52772",
        image_url="https://img/x.jpg", source_url="https://src/x",
        instructions=instructions,
        ingredients=tuple(
            SourceIngredient(position=i, name=f"ingrédient {i}",
                             raw_text=f"{i} cup ingrédient {i}",
                             amount=float(i), unit="cup")
            for i in range(1, ingredients + 1)))


SOURCE = _source()


def _answer(**overrides):
    payload = {
        "name": "Gratin de poulet teriyaki",
        "summary": "Un gratin sucré-salé",
        "total_minutes": 35,
        "utensils": "poêle, four",
        "servings": 4,
        "steps": [{"title": "Préparer la sauce", "bullets": [
            {"text": "Émincer l'oignon"},
            {"text": "Cuire", "timer_label": "Cuisson", "timer_seconds": 600}]}],
        "ingredients": [{"name": "sauce soja"}, {"name": "sucre roux"}],
    }
    payload.update(overrides)
    return payload


# --- l'invite ---------------------------------------------------------------

def test_the_prompt_is_french_and_asks_for_json_and_nothing_else():
    prompt = build_prompt(SOURCE)
    assert "Réponds UNIQUEMENT par un objet JSON" in prompt
    assert "sans bloc de code" in prompt
    assert "Traduis en français" in prompt


def test_the_prompt_carries_every_ingredient_position():
    prompt = build_prompt(_source(ingredients=5))
    for position in range(1, 6):
        assert f"{position}. {position} cup ingrédient {position}" in prompt
    assert "Rends exactement 5 ingrédients" in prompt


def test_a_very_long_instruction_block_is_truncated_in_the_prompt():
    """On tronque la SOURCE, jamais la réponse : tronquer ce qu'on envoie se
    rattrape, tronquer ce qui revient perdrait des étapes en silence."""
    prompt = build_prompt(_source(instructions="x" * (MAX_PROMPT_INSTRUCTIONS + 500)))
    assert "x" * MAX_PROMPT_INSTRUCTIONS in prompt
    assert "x" * (MAX_PROMPT_INSTRUCTIONS + 1) not in prompt


# --- l'extraction -----------------------------------------------------------

def test_pure_json_is_read():
    assert extract_json('{"name": "x"}')["name"] == "x"


def test_json_wrapped_in_prose_is_read():
    """Un agent a le DROIT d'annoncer ce qu'il rend ; c'est même son métier."""
    assert extract_json(
        'Voici la recette adaptée :\n{"name": "x"}\nBon appétit !')["name"] == "x"


def test_json_inside_a_fenced_block_is_read():
    assert extract_json('```json\n{"name": "x"}\n```')["name"] == "x"


def test_nested_braces_do_not_cut_the_block_short():
    """Une regex non gloutonne couperait au premier `}` interne."""
    payload = extract_json(
        'Voici :\n{"a": {"b": {"c": 1}}, "name": "x"}\nvoilà')
    assert payload["name"] == "x"
    assert payload["a"]["b"]["c"] == 1


def test_a_brace_inside_a_string_does_not_end_the_scan():
    payload = extract_json('texte {"name": "un { drôle de titre", "n": 1} fin')
    assert payload["name"] == "un { drôle de titre"
    assert payload["n"] == 1


@pytest.mark.parametrize("text", [
    '{"name": "x"',                 # accolades déséquilibrées
    '{"name": ',                    # JSON tronqué
    '[{"name": "x"}]',              # tableau au premier niveau
    "aucune accolade ici",
    "", None, 42, {"name": "x"},
])
def test_an_unreadable_answer_gives_nothing(text):
    assert extract_json(text) is None


# --- la validation ----------------------------------------------------------

def test_a_valid_answer_maps_cleanly():
    adapted = validate_adaptation(_answer(), source=SOURCE)
    assert isinstance(adapted, AdaptedRecipe)
    assert adapted.name == "Gratin de poulet teriyaki"
    assert adapted.servings == 4
    assert adapted.total_minutes == 35
    assert adapted.ingredient_names == ("sauce soja", "sucre roux")
    [step] = adapted.steps
    assert step.title == "Préparer la sauce"
    assert step.bullets[0] == ("Émincer l'oignon", None, None)
    assert step.bullets[1] == ("Cuire", "Cuisson", 600)


@pytest.mark.parametrize("overrides, why", [
    ({"servings": "quatre"}, "un nombre de parts en toutes lettres"),
    ({"servings": 0}, "zéro part"),
    ({"name": "T" * 40_000}, "un titre de quarante mille caractères"),
    ({"name": ""}, "un titre vide"),
    ({"name": None}, "pas de titre du tout"),
    ({"total_minutes": -5}, "une durée négative"),
    ({"total_minutes": "trente"}, "une durée en toutes lettres"),
    ({"steps": [{"bullets": [{"text": "Cuire", "timer_seconds": -600,
                              "timer_label": "Cuisson"}]}]}, "un minuteur négatif"),
    ({"steps": [{"bullets": [{"text": "Cuire", "timer_label": "Cuisson"}]}]},
     "un libellé de minuteur sans durée"),
    ({"steps": [{"bullets": [{"text": "Cuire", "timer_seconds": 600}]}]},
     "une durée sans libellé"),
    ({"steps": [{"bullets": [{"text": ""}]}]}, "une puce vide"),
    ({"steps": "pas une liste"}, "des étapes qui ne sont pas une liste"),
    ({"steps": [{"bullets": "pas une liste"}]}, "des puces qui ne sont pas une liste"),
    ({"ingredients": [{"name": "a"}, {"name": "b"}, {"name": "c"}]},
     "plus d'ingrédients que la source n'en avait"),
    ({"ingredients": [{"name": ""}]}, "un ingrédient sans nom"),
    ({"ingredients": "pas une liste"}, "des ingrédients qui ne sont pas une liste"),
])
def test_any_anomaly_fails_the_whole_adaptation(overrides, why):
    """Il n'y a pas d'adaptation partielle. Un titre qui passe au-dessus de
    puces qui ne passent pas laisserait un intitulé français sur des étapes
    anglaises — indiscernable, pour qui cuisine, d'une vraie traduction."""
    assert validate_adaptation(_answer(**overrides), source=SOURCE) is None, why


@pytest.mark.parametrize("payload", [None, [], "texte", 42])
def test_a_payload_that_is_not_an_object_fails(payload):
    assert validate_adaptation(payload, source=SOURCE) is None


def test_fewer_ingredients_than_the_source_is_tolerated():
    """L'agent peut regrouper « sel et poivre » ; il ne peut pas en inventer."""
    adapted = validate_adaptation(_answer(ingredients=[{"name": "sauce soja"}]),
                                  source=SOURCE)
    assert adapted is not None
    assert adapted.ingredient_names == ("sauce soja",)


# --- l'appel, et ses échecs -------------------------------------------------

class _Service:
    """Un double du service `conversation.process`. Compte les appels."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.calls: list[dict] = []

    async def async_call(self, domain, service, data, blocking=False,
                         return_response=False):
        self.calls.append({"domain": domain, "service": service, "data": data})
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class _Hass:
    def __init__(self, outcome):
        self.services = _Service(outcome)


def _speech(text):
    return {"response": {"speech": {"plain": {"speech": text}}}}


async def test_no_agent_configured_means_no_adaptation_and_no_call():
    """Vide = aucune adaptation. C'est un réglage, pas une erreur."""
    hass = _Hass(_speech(json.dumps(_answer())))
    assert await adapt(hass, agent_id=None, recipe=SOURCE) is None
    assert await adapt(hass, agent_id="", recipe=SOURCE) is None
    assert hass.services.calls == []


async def test_a_configured_agent_is_asked_through_the_service():
    hass = _Hass(_speech(json.dumps(_answer())))
    adapted = await adapt(hass, agent_id="conversation.bleuenn", recipe=SOURCE)
    assert adapted.name == "Gratin de poulet teriyaki"
    [call] = hass.services.calls
    assert (call["domain"], call["service"]) == ("conversation", "process")
    assert call["data"]["agent_id"] == "conversation.bleuenn"
    assert "Réponds UNIQUEMENT" in call["data"]["text"]


@pytest.mark.parametrize("outcome, why", [
    (RuntimeError("l'agent explose"), "un agent qui lève"),
    (TimeoutError(), "un agent qui expire"),
    (Exception("quota dépassé"), "un agent hors quota"),
    (_speech("je ne sais pas faire"), "une réponse illisible"),
    (_speech('{"name": "x"'), "un JSON tronqué"),
    (_speech(json.dumps({"name": "x", "servings": "quatre"})), "un champ hors bornes"),
    (None, "pas de réponse du tout"),
    ({"forme": "inattendue"}, "une réponse d'une autre forme"),
    (_speech(None), "une parole absente"),
])
async def test_every_failure_leaves_the_recipe_unadapted(outcome, why):
    hass = _Hass(outcome)
    assert await adapt(hass, agent_id="conversation.bleuenn", recipe=SOURCE) is None, why
    assert len(hass.services.calls) == 1, "une seule tentative, jamais de reprise"
