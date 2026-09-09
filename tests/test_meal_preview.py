"""Simuler un repas, sans écrire une seule ligne — et sur le MÊME FIFO."""
import pytest

from custom_components.home_stock.application import StockManager
from custom_components.home_stock.domain import stock
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations

TABLES = ("movement", "batch", "product", "article", "meal", "recipe",
          "recipe_ingredient", "ingredient_alias")


@pytest.fixture
def manager(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.connect()
    with db.write() as conn:
        apply_migrations(conn)
    yield StockManager(db)
    db.close()


def _snapshot(manager):
    read = manager.db.read()
    return {table: read.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
            for table in TABLES}


def _kitchen(manager, *, recipe_servings=2, lines=(), stock_of=()):
    """Une recette, ses lignes, et du stock. Rend (recipe_id, {nom: product_id})."""
    ids = {}
    with manager.db.write() as conn:
        location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
        recipe_id = repo.insert_recipe(conn, name="Gratin de courgettes",
                                       source="manual",
                                       created_at="2026-08-21T10:00:00",
                                       servings=recipe_servings)
        for position, spec in enumerate(lines, start=1):
            product_id = None
            if spec.get("product"):
                product_id = ids.get(spec["product"])
                if product_id is None:
                    product_id = repo.insert_product(
                        conn, name=spec["product"], base_unit=spec.get("unit", "g"))
                    ids[spec["product"]] = product_id
            repo.insert_ingredient(
                conn, recipe_id=recipe_id, position=position,
                raw_text=spec.get("raw_text", spec.get("product", "ligne")),
                product_id=product_id, amount=spec.get("amount"),
                measure_id=spec.get("measure_id"),
                match_state=spec.get("state", "auto" if product_id else "unmatched"))
        for name, quantity, extra in stock_of:
            article_id = repo.insert_article(conn, product_id=ids[name],
                                             **extra.get("article", {}))
            repo.insert_batch(conn, article_id=article_id, location_id=location_id,
                              quantity=quantity, entered_at="2026-08-01T10:00:00",
                              best_before=extra.get("best_before"),
                              price_per_base_unit=extra.get("price"),
                              nutrition=extra.get("nutrition"))
    return recipe_id, ids


def _meal(manager, recipe_id, servings=3.0):
    return manager.plan_meal(day="2026-08-21", slot_key="dinner",
                             recipe_id=recipe_id, servings=servings)["meal_id"]


# --- la simulation n'écrit rien --------------------------------------------

def test_a_preview_writes_absolutely_nothing(manager):
    recipe_id, _ = _kitchen(
        manager, lines=[{"product": "Courgette", "amount": 300.0}],
        stock_of=[("Courgette", 900.0, {})])
    meal_id = _meal(manager, recipe_id)
    before = _snapshot(manager)
    manager.preview_meal(meal_id)
    assert _snapshot(manager) == before


def test_the_preview_uses_the_same_allocation_function_as_the_write(manager,
                                                                    monkeypatch):
    """Épingle le partage de code : si quelqu'un écrit un second FIFO un jour,
    ce test tombe."""
    recipe_id, _ = _kitchen(
        manager, lines=[{"product": "Courgette", "amount": 300.0}],
        stock_of=[("Courgette", 900.0, {})])
    meal_id = _meal(manager, recipe_id)

    calls = []
    original = stock.allocate

    def counting(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(
        "custom_components.home_stock.domain.recipes.allocate", counting)
    manager.preview_meal(meal_id)
    assert calls, "la simulation doit passer par domain.stock.allocate"


# --- les lignes -------------------------------------------------------------

def test_the_scaling_applies_to_the_base_quantity(manager):
    """Un repas à 3 parts sur une recette à 2 : facteur 1,5."""
    recipe_id, _ = _kitchen(
        manager, recipe_servings=2,
        lines=[{"product": "Courgette", "amount": 300.0}],
        stock_of=[("Courgette", 900.0, {})])
    preview = manager.preview_meal(_meal(manager, recipe_id, servings=3.0))
    assert preview["factor"] == 1.5
    assert preview["servings"] == 3.0
    [line] = preview["lines"]
    assert line["needed"] == 450.0
    assert line["status"] == "ok"


def test_a_line_across_two_batches_lists_both_with_their_shares(manager):
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"product": "Courgette", "amount": 700.0}],
        stock_of=[("Courgette", 500.0, {}), ("Courgette", 400.0, {})])
    [line] = manager.preview_meal(_meal(manager, recipe_id, servings=1.0))["lines"]
    assert [b["quantity"] for b in line["batches"]] == [500.0, 200.0]


def test_a_short_line_is_offered_reduced_and_reported_blocking(manager):
    """Servir 200 g quand on en demande 500 sans le dire écrit un chiffre faux."""
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"product": "Courgette", "amount": 500.0}],
        stock_of=[("Courgette", 200.0, {})])
    preview = manager.preview_meal(_meal(manager, recipe_id, servings=1.0))
    [line] = preview["lines"]
    assert line["status"] == "short"
    assert line["available"] == 200.0
    assert sum(b["quantity"] for b in line["batches"]) == 200.0
    assert preview["blocking"] == ["short"]


def test_a_line_with_no_batch_at_all_is_short_and_blocking(manager):
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"product": "Courgette", "amount": 500.0}])
    preview = manager.preview_meal(_meal(manager, recipe_id, servings=1.0))
    [line] = preview["lines"]
    assert line["status"] == "short" and line["batches"] == []
    assert preview["blocking"] == ["short"]


def test_an_unmatched_line_lands_in_by_hand_and_blocks_nothing(manager):
    """Refuser un dîner entier parce qu'une gousse d'ail n'est pas appariée
    serait une leçon de morale, pas un outil."""
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"raw_text": "une gousse d'ail"},
               {"product": "Courgette", "amount": 100.0}],
        stock_of=[("Courgette", 900.0, {})])
    preview = manager.preview_meal(_meal(manager, recipe_id, servings=1.0))
    assert [ligne["raw_text"] for ligne in preview["by_hand"]] == ["une gousse d'ail"]
    assert preview["blocking"] == []


def test_an_unquantified_line_lands_in_by_hand_and_blocks_nothing(manager):
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"product": "Huile", "unit": "ml", "raw_text": "un filet d'huile"}])
    preview = manager.preview_meal(_meal(manager, recipe_id, servings=1.0))
    assert [ligne["status"] for ligne in preview["by_hand"]] == ["unquantified"]
    assert preview["blocking"] == []


def test_an_ignored_line_is_silent_and_appears_nowhere(manager):
    """Sel, poivre, eau : ignorés, sans signalement. Sans cet état, le même
    arbitrage serait à reprendre à chaque recette."""
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"raw_text": "sel", "state": "ignored"},
               {"product": "Courgette", "amount": 100.0}],
        stock_of=[("Courgette", 900.0, {})])
    preview = manager.preview_meal(_meal(manager, recipe_id, servings=1.0))
    assert [ligne["raw_text"] for ligne in preview["lines"]] == ["Courgette"]
    assert preview["by_hand"] == []
    assert preview["blocking"] == []


def test_skipping_a_line_clears_the_block(manager):
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"product": "Courgette", "amount": 500.0}],
        stock_of=[("Courgette", 200.0, {})])
    meal_id = _meal(manager, recipe_id, servings=1.0)
    ingredient_id = repo.list_ingredients(manager.db.read(), recipe_id)[0]["id"]

    assert manager.preview_meal(meal_id)["blocking"] == ["short"]
    cleared = manager.preview_meal(meal_id, skip_ingredient_ids={ingredient_id})
    assert cleared["blocking"] == []
    assert cleared["lines"] == []


def test_two_lines_of_the_same_product_share_the_stock(manager):
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"product": "Oignon", "amount": 300.0},
               {"product": "Oignon", "amount": 300.0}],
        stock_of=[("Oignon", 500.0, {})])
    preview = manager.preview_meal(_meal(manager, recipe_id, servings=1.0))
    assert [ligne["status"] for ligne in preview["lines"]] == ["ok", "short"]


# --- le plat ----------------------------------------------------------------

def test_the_dish_summary_carries_the_parts_and_the_default_shelf_life(manager):
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"product": "Courgette", "amount": 300.0}],
        stock_of=[("Courgette", 900.0, {})])
    dish = manager.preview_meal(_meal(manager, recipe_id, servings=3.0),
                                today="2026-08-21")["dish"]
    assert dish["product_name"] == "Reste — Gratin de courgettes"
    assert dish["parts"] == 3.0
    assert dish["best_before"] == "2026-08-24"        # trois jours au frigo


def test_a_recipe_shelf_life_overrides_the_default_three_days(manager):
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"product": "Courgette", "amount": 300.0}],
        stock_of=[("Courgette", 900.0, {})])
    with manager.db.write() as conn:
        repo.update_recipe_fields(conn, recipe_id, {"leftover_shelf_life_days": 30})
    dish = manager.preview_meal(_meal(manager, recipe_id, servings=1.0),
                                today="2026-08-21")["dish"]
    assert dish["best_before"] == "2026-09-20"


def test_the_dish_nutrients_are_the_frozen_rates_of_the_targeted_batches(manager):
    """Un chiffre montré avant l'écriture doit être celui qui sera écrit."""
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"product": "Courgette", "amount": 300.0}],
        stock_of=[("Courgette", 900.0,
                   {"price": 0.004,
                    "nutrition": {"kcal_per_base_unit": 2.0, "proteins": 0.1}})])
    # Recette pour 1, repas pour 3 : facteur 3, donc 900 g sortent réellement
    # du stock — puis la valeur du plat se divise par ses 3 parts.
    dish = manager.preview_meal(_meal(manager, recipe_id, servings=3.0),
                                today="2026-08-21")["dish"]
    assert dish["kcal"] == pytest.approx(900 * 2.0 / 3)
    assert dish["proteins"] == pytest.approx(900 * 0.1 / 3)
    assert dish["cost"] == pytest.approx(900 * 0.004 / 3)
    assert dish["unvalued"] == 0


def test_one_missing_nutrient_nulls_that_one_and_not_the_other_eight(manager):
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"product": "Courgette", "amount": 100.0},
               {"product": "Crème", "unit": "ml", "amount": 100.0}],
        stock_of=[("Courgette", 900.0,
                   {"nutrition": {"kcal_per_base_unit": 2.0, "proteins": 0.1}}),
                  ("Crème", 900.0,
                   {"nutrition": {"kcal_per_base_unit": 3.0}})])
    dish = manager.preview_meal(_meal(manager, recipe_id, servings=1.0),
                                today="2026-08-21")["dish"]
    assert dish["kcal"] == pytest.approx(100 * 2.0 + 100 * 3.0)
    assert dish["proteins"] is None
    assert dish["fiber"] is None


def test_a_batch_without_any_value_is_counted_as_unvalued(manager):
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"product": "Courgette", "amount": 300.0}],
        stock_of=[("Courgette", 900.0, {})])
    dish = manager.preview_meal(_meal(manager, recipe_id, servings=1.0),
                                today="2026-08-21")["dish"]
    assert dish["kcal"] is None
    assert dish["cost"] is None
    assert dish["unvalued"] == 1


# --- les repas qui ne sont pas des recettes --------------------------------

def test_preview_of_a_note_meal_has_no_lines_and_no_dish(manager):
    meal_id = manager.plan_meal(day="2026-08-21", slot_key="lunch",
                                note="Restaurant")["meal_id"]
    preview = manager.preview_meal(meal_id)
    assert preview["lines"] == [] and preview["by_hand"] == []
    assert preview["dish"] is None and preview["recipe"] is None
    assert preview["blocking"] == []


def test_preview_of_a_product_meal_plans_one_line(manager):
    with manager.db.write() as conn:
        location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
        product_id = repo.insert_product(conn, name="Yaourt", base_unit="piece")
        article_id = repo.insert_article(conn, product_id=product_id)
        repo.insert_batch(conn, article_id=article_id, location_id=location_id,
                          quantity=6.0, entered_at="2026-08-01T10:00:00")
    meal_id = manager.plan_meal(day="2026-08-21", slot_key="snack",
                                product_id=product_id, amount=2.0)["meal_id"]
    preview = manager.preview_meal(meal_id)
    [line] = preview["lines"]
    assert line["product_name"] == "Yaourt"
    assert line["needed"] == 2.0
    assert preview["dish"] is None


# --- les refus --------------------------------------------------------------

def test_preview_of_a_done_meal_is_refused(manager):
    meal_id = manager.plan_meal(day="2026-08-21", slot_key="dinner",
                                note="x")["meal_id"]
    with manager.db.write() as conn:
        repo.update_meal_fields(conn, meal_id, {"state": "done"})
    with pytest.raises(ValueError, match="already done"):
        manager.preview_meal(meal_id)


def test_preview_of_an_unknown_meal_raises_a_lookup_error(manager):
    with pytest.raises(LookupError, match="999"):
        manager.preview_meal(999)


@pytest.mark.parametrize("servings", [0, -1])
def test_preview_refuses_a_non_positive_serving_count(manager, servings):
    meal_id = manager.plan_meal(day="2026-08-21", slot_key="dinner",
                                note="x")["meal_id"]
    with pytest.raises(ValueError):
        manager.preview_meal(meal_id, servings=servings)
