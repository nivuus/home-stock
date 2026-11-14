"""The adaptation targets Home Assistant's configured language, whatever it is.

One Latin-script and one non-Latin example, neither French nor English: the
prompt names the language, the agent is asked in it, and the stored recipe
says which language it is in.
"""
import json
from types import SimpleNamespace

import pytest

from custom_components.home_stock.application import StockManager
from custom_components.home_stock.recipes.adapt import adapt, build_prompt
from custom_components.home_stock.recipes.mapping import SourceIngredient, SourceRecipe
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations

SOURCE = SourceRecipe(
    name="Teriyaki", source_ref="52772", image_url=None, source_url=None,
    instructions="Preheat oven.",
    ingredients=(SourceIngredient(position=1, name="soy sauce",
                                  raw_text="3/4 cup soy sauce", amount=0.75,
                                  unit="cup"),))

ANSWERS = {
    "pl": {"name": "Zapiekanka teriyaki", "servings": 4,
           "steps": [{"title": "Sos", "bullets": [{"text": "Wymieszać"}]}],
           "ingredients": [{"name": "sos sojowy"}]},
    "ja": {"name": "照り焼きキャセロール", "servings": 4,
           "steps": [{"title": "ソース", "bullets": [{"text": "混ぜる"}]}],
           "ingredients": [{"name": "醤油"}]},
}


class _Services:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    async def async_call(self, domain, service, data, blocking=False,
                         return_response=False):
        self.calls.append(data)
        return {"response": {"speech": {"plain": {"speech": json.dumps(self.answer)}}}}


@pytest.fixture
def manager(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.connect()
    with db.write() as conn:
        apply_migrations(conn)
    yield StockManager(db)
    db.close()


@pytest.mark.parametrize("language", ["pl", "ja"])
def test_the_prompt_names_the_target_language_and_no_other(language):
    prompt = build_prompt(SOURCE, language=language)
    assert f"BCP 47 tag: {language}" in prompt
    for hardcoded in ("français", "French", "Tu adaptes", "Réponds"):
        assert hardcoded not in prompt


@pytest.mark.parametrize("language", ["pl", "ja"])
async def test_the_stored_recipe_is_in_the_configured_language(manager, language):
    hass = SimpleNamespace(config=SimpleNamespace(language=language),
                           services=_Services(ANSWERS[language]))
    adapted = await adapt(hass, agent_id="conversation.agent", recipe=SOURCE)
    assert adapted is not None
    [call] = hass.services.calls
    assert call["language"] == language
    assert f"BCP 47 tag: {language}" in call["text"]

    recipe_id, _ = manager.write_source_recipe(SOURCE, adapted=adapted)
    recipe = manager.get_recipe_view(recipe_id)["recipe"]
    assert recipe["language"] == language
    assert recipe["name"] == ANSWERS[language]["name"]
