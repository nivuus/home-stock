"""The sentence file, loaded by the matcher Home Assistant itself uses (hassil).

Each intent's documented example, and every variant a template promises,
must be recognised: a template the matcher reads differently from its
author fails silently, the phrase simply never matches.
"""
from pathlib import Path

import pytest
import yaml
from hassil import Intents, recognize

SENTENCES = (Path(__file__).resolve().parents[1]
             / "custom_sentences" / "fr" / "home_stock.yaml")


@pytest.fixture(scope="module")
def intents() -> Intents:
    return Intents.from_dict(yaml.safe_load(SENTENCES.read_text(encoding="utf-8")))


@pytest.mark.parametrize("phrase, intent, entities", [
    ("Il me reste des œufs ?", "HomeStockQueryStock", {"product": "œufs"}),
    ("Qu'est-ce qu'on mange ce soir ?", "HomeStockQueryMeals", {"slot": "dinner"}),
    ("Qu'est-ce qu'il faut acheter ?", "HomeStockQueryShoppingList", {}),
    ("Ajoute du lait à la liste", "HomeStockAddToShoppingList", {"product": "lait"}),
    ("Il me faut du beurre", "HomeStockAddToShoppingList", {"product": "beurre"}),
    ("Il faut du beurre", "HomeStockAddToShoppingList", {"product": "beurre"}),
    ("Qu'est-ce qui périme ?", "HomeStockQueryExpirations", {}),
    ("J'ai mangé le dîner", "HomeStockValidateMeal", {}),
    ("Qu'est-ce que j'ai mangé aujourd'hui ?", "HomeStockQueryToday", {}),
])
def test_every_documented_phrase_is_recognised(intents, phrase, intent, entities):
    result = recognize(phrase, intents)
    assert result is not None, phrase
    assert result.intent.name == intent
    found = {name: entity.value for name, entity in result.entities.items()}
    for name, value in entities.items():
        assert str(found[name]).strip() == value, (phrase, found)
