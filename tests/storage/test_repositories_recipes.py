"""Les dépôts du lot 3 : recettes, étapes, ingrédients, mesures, alias, repas.

Aucune transaction n'est ouverte ici — le caller la possède. Ces tests
travaillent donc sur une connexion déjà en écriture, comme ceux de
`test_repositories.py`.
"""
import pytest

from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations


@pytest.fixture
def conn(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.connect()
    with db.write() as c:
        apply_migrations(c)
    with db.write() as c:
        yield c
    db.close()


def _product(conn, name="Oignon", base_unit="g", **fields):
    product_id = repo.insert_product(conn, name=name, base_unit=base_unit)
    if fields:
        repo.update_product_fields(conn, product_id, fields)
    return product_id


def _recipe(conn, name="Kapsalon", source="manual", source_ref=None, **fields):
    return repo.insert_recipe(conn, name=name, source=source,
                              created_at="2026-08-21T18:00:00",
                              source_ref=source_ref, **fields)


def _stocked(conn, product_id, quantity):
    """Un lot ouvert de `quantity` sur ce produit, via un article neuf."""
    location_id = repo.insert_location(conn, name="Placard", kind="pantry")
    article_id = repo.insert_article(conn, product_id=product_id)
    return repo.insert_batch(conn, article_id=article_id, location_id=location_id,
                             quantity=quantity, entered_at="2026-08-01T10:00:00")


# --- recettes ---------------------------------------------------------------

def test_a_recipe_round_trips_with_its_steps_and_bullets(conn):
    recipe_id = _recipe(conn, servings=4, total_minutes=35, summary="Un plat")
    step_id = repo.insert_step(conn, recipe_id=recipe_id, position=1,
                               title="Préparer la sauce")
    repo.insert_instruction(conn, step_id=step_id, position=1,
                            text="Émincer l'oignon")
    repo.insert_instruction(conn, step_id=step_id, position=2, text="Cuire",
                            timer_label="Cuisson", timer_seconds=600)

    recipe = repo.get_recipe(conn, recipe_id)
    assert recipe["name"] == "Kapsalon"
    assert recipe["servings"] == 4

    [step] = repo.list_steps(conn, recipe_id)
    assert step["title"] == "Préparer la sauce"
    assert [b["text"] for b in step["instructions"]] == ["Émincer l'oignon", "Cuire"]
    assert step["instructions"][1]["timer_seconds"] == 600


def test_list_recipes_counts_the_unmatched_ingredients(conn):
    """Le badge « n non appariés » de l'écran Recettes vient d'ici, pas d'un
    comptage refait côté panneau."""
    recipe_id = _recipe(conn)
    product_id = _product(conn)
    repo.insert_ingredient(conn, recipe_id=recipe_id, position=1, raw_text="oignon",
                           product_id=product_id, match_state="auto")
    repo.insert_ingredient(conn, recipe_id=recipe_id, position=2, raw_text="cumin")
    repo.insert_ingredient(conn, recipe_id=recipe_id, position=3, raw_text="sumac")

    [row] = repo.list_recipes(conn)
    assert row["unmatched_count"] == 2


def test_list_recipes_filters_on_review_and_on_search(conn):
    _recipe(conn, name="Kapsalon", needs_review=1)
    _recipe(conn, name="Tartiflette")
    assert {r["name"] for r in repo.list_recipes(conn)} == {"Kapsalon", "Tartiflette"}
    assert [r["name"] for r in repo.list_recipes(conn, only_reviewable=True)] == ["Kapsalon"]
    assert [r["name"] for r in repo.list_recipes(conn, search="tarti")] == ["Tartiflette"]


def test_list_recipes_search_is_accent_and_case_insensitive(conn):
    _recipe(conn, name="Bœuf bourguignon à l'ancienne")
    for query in ("BOEUF", "bœuf", "Bourguignon", "ancienne"):
        assert len(repo.list_recipes(conn, search=query)) == 1, query


def test_list_recipes_hides_the_inactive_ones(conn):
    _recipe(conn, name="Kapsalon")
    _recipe(conn, name="Ancienne", active=0)
    assert [r["name"] for r in repo.list_recipes(conn)] == ["Kapsalon"]


def test_find_recipe_by_source_is_what_makes_an_import_replayable(conn):
    _recipe(conn, name="Kapsalon", source="themealdb", source_ref="52942")
    assert repo.find_recipe_by_source(conn, "themealdb", "52942")["name"] == "Kapsalon"
    assert repo.find_recipe_by_source(conn, "themealdb", "00000") is None


def test_delete_recipe_removes_its_steps_bullets_and_ingredients(conn):
    recipe_id = _recipe(conn)
    step_id = repo.insert_step(conn, recipe_id=recipe_id, position=1)
    repo.insert_instruction(conn, step_id=step_id, position=1, text="Cuire")
    repo.insert_ingredient(conn, recipe_id=recipe_id, position=1, raw_text="oignon")

    repo.delete_recipe(conn, recipe_id)

    assert repo.get_recipe(conn, recipe_id) is None
    for table in ("recipe_step", "recipe_instruction", "recipe_ingredient"):
        assert conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"] == 0


def test_a_recipe_referenced_by_a_done_meal_is_detected(conn):
    """La suppression sera refusée par-dessus (§ 17) ; le dépôt se contente de
    dire la vérité."""
    recipe_id = _recipe(conn)
    repo.insert_meal(conn, uid="u1", day="2026-08-21", slot_key="dinner",
                     created_at="2026-08-21T18:00:00", recipe_id=recipe_id)
    assert repo.recipe_is_referenced_by_a_done_meal(conn, recipe_id) is False

    repo.insert_meal(conn, uid="u2", day="2026-08-20", slot_key="dinner",
                     created_at="2026-08-20T18:00:00", recipe_id=recipe_id,
                     state="done")
    assert repo.recipe_is_referenced_by_a_done_meal(conn, recipe_id) is True


# --- ingrédients, mesures, alias -------------------------------------------

def test_list_ingredients_joins_the_product_the_packaging_and_the_measure(conn):
    recipe_id = _recipe(conn)
    product_id = _product(conn, name="Huile", base_unit="ml")
    packaging_id = repo.insert_packaging(conn, scope="product", target_id=product_id,
                                         name="tranche", base_quantity=30.0)
    [measure] = [m for m in repo.list_measures(conn) if m["name"] == "cuillère à soupe"]

    repo.insert_ingredient(conn, recipe_id=recipe_id, position=1, raw_text="2 tbsp oil",
                           product_id=product_id, amount=2.0,
                           measure_id=measure["id"], match_state="auto")
    repo.insert_ingredient(conn, recipe_id=recipe_id, position=2, raw_text="1 tranche",
                           product_id=product_id, amount=1.0,
                           packaging_id=packaging_id, match_state="auto")

    first, second = repo.list_ingredients(conn, recipe_id)
    assert first["product_base_unit"] == "ml"
    assert first["measure_name"] == "cuillère à soupe"
    assert first["measure_base_unit"] == "ml"
    assert first["measure_base_quantity"] == 15.0
    assert first["packaging_base_quantity"] is None
    assert second["packaging_name"] == "tranche"
    assert second["packaging_base_quantity"] == 30.0
    assert second["measure_name"] is None


def test_list_ingredients_keeps_a_line_whose_product_is_null(conn):
    """Une ligne non appariée doit rester visible : c'est elle qu'on vient
    apparier à l'écran. Une jointure interne la ferait disparaître."""
    recipe_id = _recipe(conn)
    repo.insert_ingredient(conn, recipe_id=recipe_id, position=1, raw_text="sumac")
    [line] = repo.list_ingredients(conn, recipe_id)
    assert line["raw_text"] == "sumac"
    assert line["product_id"] is None
    assert line["product_base_unit"] is None


def test_list_ingredients_is_ordered_by_position(conn):
    recipe_id = _recipe(conn)
    for position in (3, 1, 2):
        repo.insert_ingredient(conn, recipe_id=recipe_id, position=position,
                               raw_text=f"ligne {position}")
    assert [l["position"] for l in repo.list_ingredients(conn, recipe_id)] == [1, 2, 3]


def test_update_ingredient_match_writes_the_three_columns(conn):
    recipe_id = _recipe(conn)
    product_id = _product(conn)
    ingredient_id = repo.insert_ingredient(conn, recipe_id=recipe_id, position=1,
                                           raw_text="oignon")
    repo.update_ingredient_match(conn, ingredient_id, product_id=product_id,
                                 state="confirmed", score=0.92)
    [line] = repo.list_ingredients(conn, recipe_id)
    assert (line["product_id"], line["match_state"]) == (product_id, "confirmed")
    assert line["match_score"] == 0.92


def test_the_four_measures_are_seeded_and_readable(conn):
    measures = {m["name"]: (m["base_unit"], m["base_quantity"])
                for m in repo.list_measures(conn)}
    assert measures == {"cuillère à soupe": ("ml", 15.0), "cuillère à café": ("ml", 5.0),
                        "verre": ("ml", 200.0), "pincée": ("g", 1.0)}


def test_upsert_alias_is_idempotent_and_moves_an_existing_alias(conn):
    coriandre = _product(conn, name="Coriandre")
    persil = _product(conn, name="Persil")
    repo.upsert_alias(conn, normalised="coriandre fraiche", product_id=coriandre,
                      created_at="2026-08-21T18:00:00")
    repo.upsert_alias(conn, normalised="coriandre fraiche", product_id=coriandre,
                      created_at="2026-08-21T18:00:00")
    assert conn.execute("SELECT COUNT(*) c FROM ingredient_alias").fetchone()["c"] == 1

    repo.upsert_alias(conn, normalised="coriandre fraiche", product_id=persil,
                      created_at="2026-08-22T18:00:00")
    alias = repo.find_alias(conn, "coriandre fraiche")
    assert alias["product_id"] == persil
    assert conn.execute("SELECT COUNT(*) c FROM ingredient_alias").fetchone()["c"] == 1


def test_find_alias_says_nothing_rather_than_guessing(conn):
    assert repo.find_alias(conn, "jamais vu") is None


# --- créneaux et repas ------------------------------------------------------

def test_the_four_slots_are_seeded_in_their_display_order(conn):
    assert [s["key"] for s in repo.list_slots(conn)] == [
        "breakfast", "lunch", "dinner", "snack"]
    assert repo.get_slot(conn, "dinner")["default_time"] == "20:00"
    assert repo.get_slot(conn, "brunch") is None


def test_list_meals_returns_the_slot_order_then_the_position(conn):
    """Le planning affiche petit-déjeuner, déjeuner, dîner, en-cas — dans cet
    ordre, y compris pour un repas ajouté après coup."""
    for index, slot in enumerate(("dinner", "breakfast", "snack", "lunch")):
        repo.insert_meal(conn, uid=f"u{index}", day="2026-08-21", slot_key=slot,
                         created_at="2026-08-21T10:00:00", note=f"repas {slot}")
    repo.insert_meal(conn, uid="u9", day="2026-08-21", slot_key="dinner",
                     created_at="2026-08-21T19:00:00", note="ajouté après", position=1)

    meals = repo.list_meals(conn, "2026-08-21", "2026-08-21")
    assert [m["slot_key"] for m in meals] == [
        "breakfast", "lunch", "dinner", "dinner", "snack"]
    assert [m["note"] for m in meals][2:4] == ["repas dinner", "ajouté après"]


def test_list_meals_is_bounded_at_both_ends(conn):
    for day in ("2026-08-19", "2026-08-20", "2026-08-21", "2026-08-22"):
        repo.insert_meal(conn, uid=f"u{day}", day=day, slot_key="dinner",
                         created_at="2026-08-01T10:00:00", note="x")
    days = [m["day"] for m in repo.list_meals(conn, "2026-08-20", "2026-08-21")]
    assert days == ["2026-08-20", "2026-08-21"]


def test_list_meals_joins_the_recipe_and_the_product_names(conn):
    recipe_id = _recipe(conn, name="Kapsalon")
    product_id = _product(conn, name="Yaourt", base_unit="piece")
    repo.insert_meal(conn, uid="u1", day="2026-08-21", slot_key="lunch",
                     created_at="2026-08-21T10:00:00", recipe_id=recipe_id)
    repo.insert_meal(conn, uid="u2", day="2026-08-21", slot_key="snack",
                     created_at="2026-08-21T10:00:00", product_id=product_id, amount=1.0)

    meals = repo.list_meals(conn, "2026-08-21", "2026-08-21")
    assert meals[0]["recipe_name"] == "Kapsalon"
    assert meals[1]["product_name"] == "Yaourt"
    assert meals[0]["slot_position"] == 2       # lunch avant snack


def test_next_meal_ignores_a_done_and_a_skipped_one(conn):
    repo.insert_meal(conn, uid="u1", day="2026-08-21", slot_key="breakfast",
                     created_at="2026-08-21T06:00:00", note="mangé", state="done")
    repo.insert_meal(conn, uid="u2", day="2026-08-21", slot_key="lunch",
                     created_at="2026-08-21T06:00:00", note="sauté", state="skipped")
    repo.insert_meal(conn, uid="u3", day="2026-08-21", slot_key="dinner",
                     created_at="2026-08-21T06:00:00", note="à venir")
    assert repo.next_meal(conn, "2026-08-21")["note"] == "à venir"


def test_next_meal_looks_forward_never_backward(conn):
    repo.insert_meal(conn, uid="u1", day="2026-08-20", slot_key="dinner",
                     created_at="2026-08-20T06:00:00", note="hier")
    assert repo.next_meal(conn, "2026-08-21") is None
    repo.insert_meal(conn, uid="u2", day="2026-08-23", slot_key="lunch",
                     created_at="2026-08-20T06:00:00", note="après-demain")
    assert repo.next_meal(conn, "2026-08-21")["note"] == "après-demain"


def test_next_meal_position_appends_rather_than_colliding(conn):
    assert repo.next_meal_position(conn, "2026-08-21", "dinner") == 0
    repo.insert_meal(conn, uid="u1", day="2026-08-21", slot_key="dinner",
                     created_at="2026-08-21T10:00:00", note="a", position=0)
    assert repo.next_meal_position(conn, "2026-08-21", "dinner") == 1
    assert repo.next_meal_position(conn, "2026-08-21", "lunch") == 0


def test_a_meal_round_trips_by_id_and_by_uid(conn):
    meal_id = repo.insert_meal(conn, uid="abc", day="2026-08-21", slot_key="dinner",
                               created_at="2026-08-21T10:00:00", note="Restaurant")
    assert repo.get_meal(conn, meal_id)["uid"] == "abc"
    assert repo.get_meal_by_uid(conn, "abc")["id"] == meal_id
    assert repo.get_meal_by_uid(conn, "jamais") is None


def test_update_meal_fields_and_delete(conn):
    meal_id = repo.insert_meal(conn, uid="abc", day="2026-08-21", slot_key="dinner",
                               created_at="2026-08-21T10:00:00", note="Restaurant")
    repo.update_meal_fields(conn, meal_id, {"day": "2026-08-22", "slot_key": "lunch"})
    meal = repo.get_meal(conn, meal_id)
    assert (meal["day"], meal["slot_key"]) == ("2026-08-22", "lunch")
    repo.delete_meal(conn, meal_id)
    assert repo.get_meal(conn, meal_id) is None


# --- ce qui manque pour la semaine -----------------------------------------

def test_missing_products_between_lists_a_product_without_enough_stock(conn):
    recipe_id = _recipe(conn, servings=1)
    product_id = _product(conn, name="Oignon")
    repo.insert_ingredient(conn, recipe_id=recipe_id, position=1, raw_text="oignon",
                           product_id=product_id, amount=500.0, match_state="auto")
    _stocked(conn, product_id, 200.0)
    repo.insert_meal(conn, uid="u1", day="2026-08-21", slot_key="dinner",
                     created_at="2026-08-21T10:00:00", recipe_id=recipe_id)

    [missing] = repo.missing_products_between(conn, "2026-08-21", "2026-08-27")
    assert missing["product_id"] == product_id
    assert missing["needed"] == 500.0
    assert missing["available"] == 200.0


def test_missing_products_between_says_nothing_when_the_stock_covers_it(conn):
    recipe_id = _recipe(conn, servings=1)
    product_id = _product(conn, name="Oignon")
    repo.insert_ingredient(conn, recipe_id=recipe_id, position=1, raw_text="oignon",
                           product_id=product_id, amount=100.0, match_state="auto")
    _stocked(conn, product_id, 500.0)
    repo.insert_meal(conn, uid="u1", day="2026-08-21", slot_key="dinner",
                     created_at="2026-08-21T10:00:00", recipe_id=recipe_id)
    assert repo.missing_products_between(conn, "2026-08-21", "2026-08-27") == []


def test_missing_products_between_ignores_unmatched_and_ignored_lines(conn):
    """On ne réclame pas d'acheter ce qu'on n'a pas su identifier ; ce serait
    une liste de courses fausse, et c'est le lot 4 qui la construira."""
    recipe_id = _recipe(conn, servings=1)
    product_id = _product(conn, name="Sumac")
    repo.insert_ingredient(conn, recipe_id=recipe_id, position=1, raw_text="sumac")
    repo.insert_ingredient(conn, recipe_id=recipe_id, position=2, raw_text="sel",
                           product_id=product_id, amount=10.0, match_state="ignored")
    repo.insert_meal(conn, uid="u1", day="2026-08-21", slot_key="dinner",
                     created_at="2026-08-21T10:00:00", recipe_id=recipe_id)
    assert repo.missing_products_between(conn, "2026-08-21", "2026-08-27") == []


def test_missing_products_between_scales_by_the_meal_servings(conn):
    recipe_id = _recipe(conn, servings=2)
    product_id = _product(conn, name="Oignon")
    repo.insert_ingredient(conn, recipe_id=recipe_id, position=1, raw_text="oignon",
                           product_id=product_id, amount=200.0, match_state="auto")
    _stocked(conn, product_id, 300.0)
    repo.insert_meal(conn, uid="u1", day="2026-08-21", slot_key="dinner",
                     created_at="2026-08-21T10:00:00", recipe_id=recipe_id, servings=4.0)

    [missing] = repo.missing_products_between(conn, "2026-08-21", "2026-08-27")
    assert missing["needed"] == 400.0      # 200 x (4 / 2)


def test_missing_products_between_ignores_a_done_meal(conn):
    """Ce qui est déjà mangé n'a plus besoin d'être acheté."""
    recipe_id = _recipe(conn, servings=1)
    product_id = _product(conn, name="Oignon")
    repo.insert_ingredient(conn, recipe_id=recipe_id, position=1, raw_text="oignon",
                           product_id=product_id, amount=500.0, match_state="auto")
    repo.insert_meal(conn, uid="u1", day="2026-08-21", slot_key="dinner",
                     created_at="2026-08-21T10:00:00", recipe_id=recipe_id, state="done")
    assert repo.missing_products_between(conn, "2026-08-21", "2026-08-27") == []
