"""Écrire une recette importée : rejouable, et sans jamais écraser un humain."""
import pytest

from custom_components.home_stock.application import StockManager
from custom_components.home_stock.const import MAX_RECIPE_STEPS
from custom_components.home_stock.recipes.mapping import (
    SourceIngredient,
    SourceRecipe,
)
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


def _products(manager, *specs):
    """(nom, unité de base) → identifiants, dans une base neuve."""
    ids = {}
    with manager.db.write() as conn:
        for name, base_unit in specs:
            ids[name] = repo.insert_product(conn, name=name, base_unit=base_unit)
    return ids


def _source(*ingredients, name="Teriyaki", source_ref="52772"):
    return SourceRecipe(
        name=name, source_ref=source_ref,
        image_url="https://img/x.jpg", source_url="https://src/x",
        instructions="Preheat oven.",
        ingredients=tuple(ingredients))


def _ingredient(position, name, raw_text, amount, unit):
    return SourceIngredient(position=position, name=name, raw_text=raw_text,
                            amount=amount, unit=unit)


# --- l'import et sa rejouabilité -------------------------------------------

def test_a_source_recipe_lands_with_its_ingredients(manager):
    _products(manager, ("Soy sauce", "ml"))
    recipe_id, created = manager.write_source_recipe(_source(
        _ingredient(1, "soy sauce", "3/4 cup soy sauce", 0.75, "cup"),
        _ingredient(2, "brown sugar", "1/4 cup brown sugar", 0.25, "cup")))

    assert created is True
    view = manager.get_recipe_view(recipe_id)
    assert view["recipe"]["name"] == "Teriyaki"
    assert view["recipe"]["source"] == "themealdb"
    assert view["recipe"]["source_ref"] == "52772"
    # Import brut : la langue reste celle de la source et la relecture est due.
    assert view["recipe"]["language"] == "en"
    assert view["recipe"]["needs_review"] == 1
    assert view["recipe"]["adapted_at"] is None
    assert [line["raw_text"] for line in view["ingredients"]] == [
        "3/4 cup soy sauce", "1/4 cup brown sugar"]


def test_importing_the_same_source_ref_twice_updates_and_does_not_duplicate(manager):
    first, created_first = manager.write_source_recipe(_source(
        _ingredient(1, "soy sauce", "3/4 cup soy sauce", 0.75, "cup")))
    second, created_second = manager.write_source_recipe(_source(
        _ingredient(1, "soy sauce", "1 cup soy sauce", 1.0, "cup"),
        name="Teriyaki Chicken Casserole"))

    assert (first, created_first) == (second, True)
    assert created_second is False
    read = manager.db.read()
    assert read.execute("SELECT COUNT(*) c FROM recipe").fetchone()["c"] == 1
    assert repo.get_recipe(read, first)["name"] == "Teriyaki Chicken Casserole"
    assert [l["raw_text"] for l in repo.list_ingredients(read, first)] == [
        "1 cup soy sauce"]


def test_a_reimport_never_overwrites_a_confirmed_ingredient(manager):
    """Même règle qu'`article.manual_fields` face à une resynchronisation OFF :
    la machine rafraîchit ce qu'elle a écrit, jamais ce qu'un humain a corrigé."""
    ids = _products(manager, ("Sauce soja", "ml"))
    recipe_id, _ = manager.write_source_recipe(_source(
        _ingredient(1, "soy sauce", "3/4 cup soy sauce", 0.75, "cup")))
    [line] = repo.list_ingredients(manager.db.read(), recipe_id)
    manager.match_ingredient(line["id"], product_id=ids["Sauce soja"],
                             state="confirmed")

    manager.write_source_recipe(_source(
        _ingredient(1, "soy sauce", "TEXTE REMPLACÉ", 99.0, "cup")))

    [after] = repo.list_ingredients(manager.db.read(), recipe_id)
    assert after["raw_text"] == "3/4 cup soy sauce"
    assert after["match_state"] == "confirmed"
    assert after["product_id"] == ids["Sauce soja"]


def test_a_reimport_refreshes_a_line_nobody_confirmed(manager):
    recipe_id, _ = manager.write_source_recipe(_source(
        _ingredient(1, "soy sauce", "3/4 cup soy sauce", 0.75, "cup")))
    manager.write_source_recipe(_source(
        _ingredient(1, "soy sauce", "1 cup soy sauce", 1.0, "cup")))
    [after] = repo.list_ingredients(manager.db.read(), recipe_id)
    assert after["raw_text"] == "1 cup soy sauce"


# --- le tableau du § 9, à l'écriture ---------------------------------------

def test_a_convertible_mass_lands_converted_with_no_measure_id(manager):
    """250 g sur un produit en g : amount = 250, measure_id NULL."""
    _products(manager, ("Farine", "g"))
    recipe_id, _ = manager.write_source_recipe(_source(
        _ingredient(1, "farine", "250 g farine", 250.0, "g")))
    [line] = repo.list_ingredients(manager.db.read(), recipe_id)
    assert line["amount"] == 250.0
    assert line["measure_id"] is None


def test_a_kilogram_lands_in_base_units(manager):
    _products(manager, ("Farine", "g"))
    recipe_id, _ = manager.write_source_recipe(_source(
        _ingredient(1, "farine", "1.5 kg farine", 1.5, "kg")))
    [line] = repo.list_ingredients(manager.db.read(), recipe_id)
    assert line["amount"] == 1500.0


def test_a_culinary_measure_lands_as_amount_plus_measure_id(manager):
    """2 cs d'huile : amount = 2, measure_id = celui de la cuillère à soupe.
    La quantité en unité de base reste CALCULÉE, jamais stockée."""
    _products(manager, ("Huile", "ml"))
    recipe_id, _ = manager.write_source_recipe(_source(
        _ingredient(1, "huile", "2 tbsp huile", 2.0, "tbsp")))
    [line] = repo.list_ingredients(manager.db.read(), recipe_id)
    assert line["amount"] == 2.0
    assert line["measure_name"] == "cuillère à soupe"
    assert line["measure_base_quantity"] == 15.0


def test_an_unconvertible_measure_lands_as_a_null_amount(manager):
    """« 1 tbsp » sur un produit suivi à la pièce : la ligne existe, s'affiche,
    et ne décrémente rien. NULL veut dire inconnu, jamais zéro."""
    _products(manager, ("Yaourt", "piece"))
    recipe_id, _ = manager.write_source_recipe(_source(
        _ingredient(1, "yaourt", "1 tbsp yaourt", 1.0, "tbsp")))
    [line] = repo.list_ingredients(manager.db.read(), recipe_id)
    assert line["amount"] is None
    assert line["measure_id"] is None
    assert line["raw_text"] == "1 tbsp yaourt"


def test_a_mass_for_a_piece_product_is_refused(manager):
    """Le lot 1 refuse déjà d'inventer un diviseur : un poids par pièce deviné
    écrit un chiffre faux dans un journal en ajout seul."""
    _products(manager, ("Yaourt", "piece"))
    recipe_id, _ = manager.write_source_recipe(_source(
        _ingredient(1, "yaourt", "100 g yaourt", 100.0, "g")))
    [line] = repo.list_ingredients(manager.db.read(), recipe_id)
    assert line["amount"] is None


def test_a_volume_for_a_gram_product_is_refused(manager):
    _products(manager, ("Farine", "g"))
    recipe_id, _ = manager.write_source_recipe(_source(
        _ingredient(1, "farine", "20 cl farine", 20.0, "cl")))
    [line] = repo.list_ingredients(manager.db.read(), recipe_id)
    assert line["amount"] is None


def test_a_bare_number_counts_only_for_a_piece_product(manager):
    """« 3 œufs » veut dire trois pièces. « 2 farine » ne veut rien dire."""
    ids = _products(manager, ("Œufs", "piece"), ("Farine", "g"))
    recipe_id, _ = manager.write_source_recipe(_source(
        _ingredient(1, "œufs", "3 œufs", 3.0, None),
        _ingredient(2, "farine", "2 farine", 2.0, None)))
    eggs, flour = repo.list_ingredients(manager.db.read(), recipe_id)
    assert eggs["amount"] == 3.0 and eggs["product_id"] == ids["Œufs"]
    assert flour["amount"] is None


def test_a_line_with_no_quantity_at_all_is_legitimate(manager):
    """« un filet d'huile », « selon le goût » : la ligne s'affiche et ne
    décrémente rien."""
    _products(manager, ("Huile", "ml"))
    recipe_id, _ = manager.write_source_recipe(_source(
        _ingredient(1, "huile", "a drizzle of huile", None, None)))
    [line] = repo.list_ingredients(manager.db.read(), recipe_id)
    assert line["amount"] is None
    assert line["raw_text"] == "a drizzle of huile"


def test_an_unknown_source_unit_never_invents_an_equivalence(manager):
    """« 2 knobs » n'a pas de mesure derrière : la quantité est inconnue, pas
    approximée."""
    _products(manager, ("Beurre", "g"))
    recipe_id, _ = manager.write_source_recipe(_source(
        _ingredient(1, "beurre", "2 knobs beurre", 2.0, "knobs")))
    [line] = repo.list_ingredients(manager.db.read(), recipe_id)
    assert line["amount"] is None


# --- la création manuelle ---------------------------------------------------

def test_create_recipe_writes_its_steps_and_bullets(manager):
    recipe_id = manager.create_recipe(
        name="Tartiflette", servings=4,
        steps=[{"title": "Préparer", "instructions": [
            {"text": "Éplucher"}, {"text": "Cuire", "timer_label": "Cuisson",
                                   "timer_seconds": 900}]}],
        ingredients=[{"raw_text": "1 kg de pommes de terre"}])
    view = manager.get_recipe_view(recipe_id)
    assert view["recipe"]["servings"] == 4
    assert view["steps"][0]["instructions"][1]["timer_seconds"] == 900
    assert len(view["ingredients"]) == 1


def test_create_recipe_refuses_more_steps_than_max(manager):
    with pytest.raises(ValueError, match=str(MAX_RECIPE_STEPS)):
        manager.create_recipe(
            name="Trop", steps=[{"title": f"{i}"} for i in range(MAX_RECIPE_STEPS + 1)])


def test_create_recipe_writes_nothing_when_one_ingredient_is_invalid(manager):
    """Transaction unique : jamais une demi-recette. Une recette dont le
    huitième ingrédient est refusé ne doit laisser aucune trace, sinon
    l'import suivant trouverait une coquille indiscernable d'une vraie."""
    with pytest.raises(Exception):
        manager.create_recipe(
            name="Moitié", ingredients=[
                {"raw_text": "correcte"},
                # `match_state` hors des quatre valeurs permises : le CHECK du
                # schéma le refuse AU MILIEU de la transaction, donc après que
                # la recette et le premier ingrédient ont déjà été écrits.
                # C'est exactement le cas que la transaction unique doit
                # rattraper. (Une colonne inventée, elle, ne prouverait rien :
                # la liste blanche la filtre avant même le SQL.)
                {"raw_text": "fautive", "match_state": "impossible"},
            ])
    read = manager.db.read()
    assert read.execute("SELECT COUNT(*) c FROM recipe").fetchone()["c"] == 0
    assert read.execute(
        "SELECT COUNT(*) c FROM recipe_ingredient").fetchone()["c"] == 0


def test_create_recipe_refuses_an_unknown_source(manager):
    with pytest.raises(ValueError, match="unknown recipe source"):
        manager.create_recipe(name="R", source="marmiton")


# --- la vue, et la suppression ---------------------------------------------

def test_get_recipe_view_returns_the_candidates_for_an_unmatched_line(manager):
    _products(manager, ("Crème fraîche", "ml"), ("Menthe fraîche", "g"))
    recipe_id = manager.create_recipe(
        name="R", ingredients=[{"raw_text": "coriandre fraîche"}])
    [line] = manager.get_recipe_view(recipe_id)["ingredients"]
    assert line["match_state"] == "unmatched"
    assert [c["name"] for c in line["candidates"]][:2] == [
        "Crème fraîche", "Menthe fraîche"]


def test_get_recipe_view_offers_no_candidate_for_a_settled_line(manager):
    ids = _products(manager, ("Huile", "ml"))
    recipe_id = manager.create_recipe(
        name="R", ingredients=[{"raw_text": "huile", "product_id": ids["Huile"],
                                "match_state": "confirmed"}])
    [line] = manager.get_recipe_view(recipe_id)["ingredients"]
    assert line["candidates"] == []


def test_get_recipe_view_computes_the_display_label(manager):
    _products(manager, ("Huile", "ml"))
    recipe_id, _ = manager.write_source_recipe(_source(
        _ingredient(1, "huile", "2 tbsp huile", 2.0, "tbsp")))
    [line] = manager.get_recipe_view(recipe_id)["ingredients"]
    assert line["display_amount"] == "2 cuillères à soupe"


def test_deleting_a_recipe_referenced_by_a_done_meal_is_refused(manager):
    recipe_id = manager.create_recipe(name="Kapsalon")
    with manager.db.write() as conn:
        repo.insert_meal(conn, uid="u1", day="2026-08-20", slot_key="dinner",
                         created_at="2026-08-20T18:00:00", recipe_id=recipe_id,
                         state="done")
    with pytest.raises(ValueError, match="already been cooked"):
        manager.delete_recipe(recipe_id)
    assert repo.get_recipe(manager.db.read(), recipe_id) is not None


def test_deactivating_is_the_path_instead(manager):
    recipe_id = manager.create_recipe(name="Kapsalon")
    with manager.db.write() as conn:
        repo.insert_meal(conn, uid="u1", day="2026-08-20", slot_key="dinner",
                         created_at="2026-08-20T18:00:00", recipe_id=recipe_id,
                         state="done")
    manager.update_recipe(recipe_id, {"active": 0})
    assert manager.list_recipes() == []
    assert repo.get_recipe(manager.db.read(), recipe_id) is not None


def test_deleting_a_planned_meals_recipe_is_allowed(manager):
    """Un repas seulement PRÉVU n'est pas de l'histoire : rien n'a été écrit
    dans le journal, la recette peut disparaître — et le repas avec elle,
    sans quoi le calendrier afficherait un repas sans recette."""
    recipe_id = manager.create_recipe(name="Kapsalon")
    with manager.db.write() as conn:
        repo.insert_meal(conn, uid="u1", day="2026-08-22", slot_key="dinner",
                         created_at="2026-08-20T18:00:00", recipe_id=recipe_id)
    manager.delete_recipe(recipe_id)
    read = manager.db.read()
    assert repo.get_recipe(read, recipe_id) is None
    assert read.execute("SELECT COUNT(*) c FROM meal").fetchone()["c"] == 0


def test_an_unknown_recipe_is_named_in_the_error(manager):
    for call in (lambda: manager.get_recipe_view(999),
                 lambda: manager.update_recipe(999, {"name": "x"}),
                 lambda: manager.delete_recipe(999)):
        with pytest.raises(ValueError, match="999"):
            call()


# --- lot 3 : adaptée ou pas, jamais à moitié --------------------------------

def _adapted(**overrides):
    from custom_components.home_stock.recipes.adapt import AdaptedRecipe, AdaptedStep
    payload = dict(
        name="Gratin de poulet teriyaki", summary="Un gratin sucré-salé",
        total_minutes=35, utensils="poêle, four", servings=4,
        steps=(AdaptedStep(title="Préparer la sauce", bullets=(
            ("Émincer l'oignon", None, None),
            ("Cuire", "Cuisson", 600))),),
        ingredient_names=("sauce soja",),
        ingredient_amounts=((None, None),))
    payload.update(overrides)
    return AdaptedRecipe(**payload)


def test_an_adapted_recipe_lands_in_french_with_its_pages(manager):
    _products(manager, ("Sauce soja", "ml"))
    recipe_id, _ = manager.write_source_recipe(
        _source(_ingredient(1, "soy sauce", "3/4 cup soy sauce", 0.75, "cup")),
        adapted=_adapted())

    view = manager.get_recipe_view(recipe_id)
    assert view["recipe"]["name"] == "Gratin de poulet teriyaki"
    assert view["recipe"]["language"] == "fr"
    assert view["recipe"]["needs_review"] == 0
    assert view["recipe"]["adapted_at"] is not None
    assert view["recipe"]["servings"] == 4
    [step] = view["steps"]
    assert step["title"] == "Préparer la sauce"
    assert [b["text"] for b in step["instructions"]] == ["Émincer l'oignon", "Cuire"]
    assert step["instructions"][1]["timer_seconds"] == 600


def test_without_an_adaptation_the_recipe_stays_english_and_reviewable(manager):
    """Le contrat des cinq échecs : agent absent, en panne, hors quota,
    illisible ou hors bornes donnent tous CE résultat — la recette existe,
    entière, en anglais, marquée à relire, et sans une seule étape orpheline."""
    recipe_id, _ = manager.write_source_recipe(
        _source(_ingredient(1, "soy sauce", "3/4 cup soy sauce", 0.75, "cup")))
    view = manager.get_recipe_view(recipe_id)
    assert view["recipe"]["name"] == "Teriyaki"
    assert view["recipe"]["language"] == "en"
    assert view["recipe"]["needs_review"] == 1
    assert view["recipe"]["adapted_at"] is None
    assert view["steps"] == []          # aucune page à moitié écrite
    assert len(view["ingredients"]) == 1


def test_adapting_later_replaces_the_pages_instead_of_stacking_them(manager):
    """`home_stock.adapt_recipe` rattrape une recette importée sans agent. Le
    second passage ne doit pas empiler une deuxième série de pages."""
    source = _source(_ingredient(1, "soy sauce", "3/4 cup soy sauce", 0.75, "cup"))
    recipe_id, _ = manager.write_source_recipe(source)
    manager.write_source_recipe(source, adapted=_adapted())
    manager.write_source_recipe(source, adapted=_adapted())

    view = manager.get_recipe_view(recipe_id)
    assert len(view["steps"]) == 1
    assert len(view["steps"][0]["instructions"]) == 2
    assert view["recipe"]["language"] == "fr"


def test_the_agents_isolated_name_is_used_to_match(manager):
    """« 3/4 cup soy sauce » n'apparie rien ; « sauce soja », si. Le nom isolé
    que rend l'agent est une meilleure aiguille que le texte brut, qui traîne
    encore sa quantité."""
    ids = _products(manager, ("Sauce soja", "ml"))
    source = _source(_ingredient(1, "soy sauce", "3/4 cup soy sauce", 0.75, "cup"))

    recipe_id, _ = manager.write_source_recipe(source)
    [before] = repo.list_ingredients(manager.db.read(), recipe_id)
    assert before["product_id"] is None

    manager.write_source_recipe(source, adapted=_adapted())
    [after] = repo.list_ingredients(manager.db.read(), recipe_id)
    assert after["product_id"] == ids["Sauce soja"]


def test_adaptation_never_rewrites_a_confirmed_ingredient(manager):
    ids = _products(manager, ("Sauce soja", "ml"), ("Vinaigre", "ml"))
    source = _source(_ingredient(1, "soy sauce", "3/4 cup soy sauce", 0.75, "cup"))
    recipe_id, _ = manager.write_source_recipe(source)
    [line] = repo.list_ingredients(manager.db.read(), recipe_id)
    manager.match_ingredient(line["id"], product_id=ids["Vinaigre"],
                             state="confirmed")

    manager.write_source_recipe(source, adapted=_adapted())

    [after] = repo.list_ingredients(manager.db.read(), recipe_id)
    assert after["product_id"] == ids["Vinaigre"]
    assert after["match_state"] == "confirmed"
