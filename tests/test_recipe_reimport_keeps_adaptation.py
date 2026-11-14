"""Re-importing a recipe when the adaptation failed keeps what was adapted.

`adapt` returns None when the agent is absent, out of quota, times out or
answers something unusable. That must not cost an already adapted recipe its
title, its summary or its steps; only provenance and ingredients refresh.
"""
import pytest

from custom_components.home_stock.application import StockManager
from custom_components.home_stock.recipes.adapt import AdaptedRecipe, AdaptedStep
from custom_components.home_stock.recipes.mapping import SourceIngredient, SourceRecipe
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations


@pytest.fixture
def manager(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.connect()
    with db.write() as conn:
        apply_migrations(conn)
    yield StockManager(db)
    db.close()


def _source(raw_text="3/4 cup soy sauce", image="https://img/x.jpg"):
    return SourceRecipe(
        name="Teriyaki", source_ref="52772", image_url=image,
        source_url="https://src/x", instructions="Preheat oven.",
        ingredients=(SourceIngredient(position=1, name="soy sauce",
                                      raw_text=raw_text, amount=0.75, unit="cup"),))


def _adapted():
    return AdaptedRecipe(
        name="Gratin teriyaki", summary="Sucré-salé", total_minutes=35,
        utensils="four", servings=4,
        steps=(AdaptedStep(title="Sauce", bullets=(("Cuire", "Cuisson", 600),)),),
        ingredient_names=("sauce soja",), ingredient_amounts=((None, None),),
        language="fr")


def test_a_failed_adaptation_keeps_the_adapted_name_and_steps(manager):
    recipe_id, _ = manager.write_source_recipe(_source(), adapted=_adapted())
    before = manager.get_recipe_view(recipe_id)

    again, created = manager.write_source_recipe(
        _source(raw_text="1 cup soy sauce", image="https://img/y.jpg"), adapted=None)

    after = manager.get_recipe_view(recipe_id)
    assert (again, created) == (recipe_id, False)
    for field in ("name", "summary", "language", "needs_review", "adapted_at",
                  "servings", "total_minutes", "utensils"):
        assert after["recipe"][field] == before["recipe"][field], field
    assert after["steps"] == before["steps"]
    # Provenance and ingredients do refresh.
    assert after["recipe"]["image_url"] == "https://img/y.jpg"
    [line] = repo.list_ingredients(manager.db.read(), recipe_id)
    assert line["raw_text"] == "1 cup soy sauce"


def test_a_never_adapted_recipe_still_refreshes_from_its_source(manager):
    recipe_id, _ = manager.write_source_recipe(_source())
    manager.write_source_recipe(SourceRecipe(
        name="Teriyaki Chicken", source_ref="52772", image_url=None,
        source_url=None, instructions="", ingredients=()))
    assert manager.get_recipe_view(recipe_id)["recipe"]["name"] == "Teriyaki Chicken"
