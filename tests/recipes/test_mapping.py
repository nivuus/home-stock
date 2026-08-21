"""La fiche TheMealDB, lue sans rien deviner."""
import json
from pathlib import Path

import pytest

from custom_components.home_stock.recipes.mapping import (
    SLOT_COUNT,
    map_meal,
    parse_measure,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "recipes"
CARD = json.loads(
    (FIXTURES / "themealdb_lookup.json").read_text(encoding="utf-8"))["meals"][0]


@pytest.mark.parametrize("text, expected", [
    ("2 tbsp", (2.0, "tbsp")),
    ("1/2 cup", (0.5, "cup")),
    ("½ tsp", (0.5, "tsp")),
    ("250g", (250.0, "g")),
    ("1.5 kg", (1.5, "kg")),
    ("1-2 cloves", (1.0, "cloves")),
    ("a handful", (None, None)),
    ("", (None, None)),
    (None, (None, None)),
    ("to taste", (None, None)),
    ("2", (2.0, None)),
    ("   ", (None, None)),
    ("1 1/2 cups", (1.5, "cups")),
    ("1½ tsp", (1.5, "tsp")),
    ("3/4 cup", (0.75, "cup")),
    ("1,5 l", (1.5, "l")),
])
def test_parse_measure(text, expected):
    amount, unit = parse_measure(text)
    expected_amount, expected_unit = expected
    if expected_amount is None:
        assert amount is None
    else:
        assert amount == pytest.approx(expected_amount)
    assert unit == expected_unit


def test_a_range_keeps_its_low_bound():
    """Prévoir la borne basse se complète à la main ; prévoir la haute prend
    en silence du stock dont personne n'avait besoin."""
    assert parse_measure("1-2 cloves") == (1.0, "cloves")
    assert parse_measure("2 - 3 tbsp") == (2.0, "tbsp")


def test_the_unit_is_never_converted_here():
    """L'unité ressort telle que la source l'écrit. Convertir ici cacherait
    l'endroit où la conversion a eu lieu, et le même texte se résout
    différemment selon le produit auquel la ligne sera appariée."""
    assert parse_measure("2 tbsp")[1] == "tbsp"
    assert parse_measure("1 cup")[1] == "cup"


# --- la fiche entière -------------------------------------------------------

def test_map_meal_pairs_the_twenty_slots():
    recipe = map_meal(CARD)
    filled = [slot for slot in range(1, SLOT_COUNT + 1)
              if (CARD[f"strIngredient{slot}"] or "").strip()]
    assert len(recipe.ingredients) == len(filled)
    assert recipe.name == "Teriyaki Chicken Casserole"
    assert recipe.source_ref == "52772"
    assert recipe.image_url.startswith("https://")
    assert recipe.instructions.startswith("Preheat oven")

    first = recipe.ingredients[0]
    assert first.name == "soy sauce"
    assert first.raw_text == "3/4 cup soy sauce"
    assert first.amount == pytest.approx(0.75)
    assert first.unit == "cup"


def test_map_meal_skips_an_empty_ingredient_in_the_middle():
    """TheMealDB laisse des trous : strIngredient7 vide entre deux pleins.
    Les positions se renumérotent, elles ne se décalent pas."""
    card = {"idMeal": "1", "strMeal": "Trous",
            "strIngredient1": "sel", "strMeasure1": "1 tsp",
            "strIngredient2": "  ", "strMeasure2": "",
            "strIngredient3": "poivre", "strMeasure3": "2 tsp"}
    recipe = map_meal(card)
    assert [i.position for i in recipe.ingredients] == [1, 2]
    assert [i.name for i in recipe.ingredients] == ["sel", "poivre"]


def test_map_meal_keeps_an_ingredient_whose_measure_is_empty():
    """Un nom sans mesure est une ligne parfaitement légitime (§ 9)."""
    card = {"idMeal": "1", "strMeal": "R", "strIngredient1": "sel", "strMeasure1": ""}
    [line] = map_meal(card).ingredients
    assert line.raw_text == "sel"
    assert line.amount is None and line.unit is None


@pytest.mark.parametrize("card", [
    {"idMeal": "1"},                       # pas de nom
    {"strMeal": "Sans identifiant"},       # pas d'identifiant
    {"idMeal": "", "strMeal": ""},
    {"idMeal": "1", "strMeal": "   "},
])
def test_map_meal_refuses_a_card_without_a_name_or_an_id(card):
    """Une fiche qu'on ne saurait jamais retrouver n'est pas une recette."""
    assert map_meal(card) is None


@pytest.mark.parametrize("payload", [None, [], "texte", 42])
def test_map_meal_refuses_a_payload_that_is_not_a_mapping(payload):
    assert map_meal(payload) is None


def test_map_meal_reads_exactly_the_twenty_slots_of_the_source():
    """Lire au-delà inventerait des créneaux, lire en deçà tronquerait en
    silence une recette longue."""
    card = {"idMeal": "1", "strMeal": "R"}
    for slot in range(1, SLOT_COUNT + 6):
        card[f"strIngredient{slot}"] = f"ingrédient {slot}"
        card[f"strMeasure{slot}"] = "1 g"
    recipe = map_meal(card)
    assert len(recipe.ingredients) == SLOT_COUNT
    assert recipe.ingredients[-1].name == f"ingrédient {SLOT_COUNT}"


def test_the_raw_text_is_the_source_verbatim_and_nothing_computed():
    """`raw_text` a le statut d'`article.off_raw` : provenance, jamais calcul.

    Même quand la mesure est parfaitement lisible, le texte conserve
    l'orthographe de la source — c'est ce qui permettra de rejouer un
    appariement, ou de comprendre un import douteux six mois plus tard.
    """
    card = {"idMeal": "1", "strMeal": "R",
            "strIngredient1": "olive oil", "strMeasure1": "2 tbsp"}
    [line] = map_meal(card).ingredients
    assert line.raw_text == "2 tbsp olive oil"
    assert (line.amount, line.unit) == (2.0, "tbsp")


def test_a_non_string_slot_does_not_crash_the_card():
    card = {"idMeal": "1", "strMeal": "R",
            "strIngredient1": None, "strMeasure1": None,
            "strIngredient2": 42, "strMeasure2": [],
            "strIngredient3": "sel", "strMeasure3": "1 g"}
    [line] = map_meal(card).ingredients
    assert line.name == "sel"
