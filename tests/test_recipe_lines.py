"""The rules behind the two recipe-line gestures: change one quantity, take one line out."""
import pytest
import voluptuous as vol

from custom_components.home_stock import recipe_lines
from custom_components.home_stock.messages import french_error
from custom_components.home_stock.storage import repositories as repo


@pytest.fixture
def breakfast(manager):
    """A recipe shaped like Maxime's breakfast (recipe 193): three lines, one step."""
    with manager.db.write() as conn:
        krisprolls = repo.insert_product(conn, name="Krisprolls", base_unit="g")
        ail = repo.insert_product(conn, name="Ail", base_unit="g")
        recipe_id = repo.insert_recipe(conn, name="Petit-déj", source="manual",
                                       created_at="2026-10-01T08:00:00", servings=1)
        ids = {
            "recipe": recipe_id,
            "krisprolls": repo.insert_ingredient(
                conn, recipe_id=recipe_id, position=1, raw_text="320 g krisprolls",
                product_id=krisprolls, amount=320.0, match_state="confirmed"),
            "ail": repo.insert_ingredient(
                conn, recipe_id=recipe_id, position=2, raw_text="1 gousse d'ail",
                product_id=ail, amount=5.0, match_state="auto"),
            "eau": repo.insert_ingredient(
                conn, recipe_id=recipe_id, position=3, raw_text="eau",
                match_state="ignored"),
        }
        conn.execute("INSERT INTO recipe_step (recipe_id, position, title)"
                     " VALUES (?, 1, 'Tartiner')", (recipe_id,))
        other = repo.insert_recipe(conn, name="Autre", source="manual",
                                   created_at="2026-10-01T08:00:00", servings=1)
        ids["other_recipe"] = other
    return ids


def _dump(manager, recipe_id):
    """Everything a recipe is made of, as rows."""
    conn = manager.db.read()
    recipe = dict(conn.execute("SELECT * FROM recipe WHERE id = ?",
                               (recipe_id,)).fetchone())
    lines = [dict(r) for r in conn.execute(
        "SELECT * FROM recipe_ingredient WHERE recipe_id = ? ORDER BY id", (recipe_id,))]
    steps = [dict(r) for r in conn.execute(
        "SELECT * FROM recipe_step WHERE recipe_id = ? ORDER BY id", (recipe_id,))]
    return recipe, lines, steps


def test_set_quantity_changes_that_line_and_nothing_else(manager, breakfast):
    recipe_before, lines_before, steps_before = _dump(manager, breakfast["recipe"])

    line = recipe_lines.set_ingredient_quantity(
        manager.db, breakfast["krisprolls"], 50, recipe_id=breakfast["recipe"])

    assert line["id"] == breakfast["krisprolls"]
    assert line["amount"] == 50.0
    recipe_after, lines_after, steps_after = _dump(manager, breakfast["recipe"])
    assert recipe_after == recipe_before
    assert steps_after == steps_before
    expected = [dict(row) for row in lines_before]
    expected[0]["amount"] = 50.0
    assert lines_after == expected


def test_set_quantity_keeps_the_provenance_text(manager, breakfast):
    line = recipe_lines.set_ingredient_quantity(manager.db, breakfast["krisprolls"], 50)
    assert line["raw_text"] == "320 g krisprolls"


def test_set_quantity_writes_a_base_quantity_over_a_packaging(manager, breakfast):
    """`amount` counts packagings when a packaging is set: 50 must mean 50 g."""
    with manager.db.write() as conn:
        product_id = conn.execute("SELECT product_id FROM recipe_ingredient WHERE id = ?",
                                  (breakfast["krisprolls"],)).fetchone()[0]
        packaging_id = repo.insert_packaging(conn, scope="product", target_id=product_id,
                                             name="paquet", base_quantity=225)
        conn.execute("UPDATE recipe_ingredient SET packaging_id = ?, amount = 1"
                     " WHERE id = ?", (packaging_id, breakfast["krisprolls"]))

    line = recipe_lines.set_ingredient_quantity(manager.db, breakfast["krisprolls"], 50)

    assert (line["amount"], line["packaging_id"], line["measure_id"]) == (50.0, None, None)


def test_remove_takes_out_that_line_and_nothing_else(manager, breakfast):
    recipe_before, lines_before, steps_before = _dump(manager, breakfast["recipe"])

    removed = recipe_lines.remove_ingredient(
        manager.db, breakfast["ail"], recipe_id=breakfast["recipe"])

    assert removed == lines_before[1]
    recipe_after, lines_after, steps_after = _dump(manager, breakfast["recipe"])
    assert recipe_after == recipe_before
    assert steps_after == steps_before
    assert lines_after == [lines_before[0], lines_before[2]]


def test_remove_then_set_on_the_breakfast_trial(manager, breakfast):
    """The first real trial, in order: 320 g → 50 g, garlic and water out."""
    recipe_lines.set_ingredient_quantity(manager.db, breakfast["krisprolls"], 50)
    recipe_lines.remove_ingredient(manager.db, breakfast["ail"])
    recipe_lines.remove_ingredient(manager.db, breakfast["eau"])
    _, lines, steps = _dump(manager, breakfast["recipe"])
    assert [(row["raw_text"], row["amount"]) for row in lines] == [
        ("320 g krisprolls", 50.0)]
    assert len(steps) == 1


@pytest.mark.parametrize("gesture", ["set", "remove"])
def test_an_unknown_line_is_refused_and_nothing_is_written(manager, breakfast, gesture):
    before = _dump(manager, breakfast["recipe"])
    with pytest.raises(ValueError, match=r"^unknown ingredient line 999999$") as caught:
        if gesture == "set":
            recipe_lines.set_ingredient_quantity(manager.db, 999999, 50)
        else:
            recipe_lines.remove_ingredient(manager.db, 999999)
    assert french_error(caught.value) == (
        "not_found", "Ligne d'ingrédient 999999 introuvable.")
    assert _dump(manager, breakfast["recipe"]) == before


@pytest.mark.parametrize("gesture", ["set", "remove"])
def test_a_line_of_another_recipe_is_refused(manager, breakfast, gesture):
    before = _dump(manager, breakfast["recipe"])
    line_id, other = breakfast["krisprolls"], breakfast["other_recipe"]
    with pytest.raises(ValueError) as caught:
        if gesture == "set":
            recipe_lines.set_ingredient_quantity(manager.db, line_id, 50, recipe_id=other)
        else:
            recipe_lines.remove_ingredient(manager.db, line_id, recipe_id=other)
    assert french_error(caught.value) == (
        "invalid_value",
        f"La ligne d'ingrédient {line_id} n'appartient pas à la recette {other}.")
    assert _dump(manager, breakfast["recipe"]) == before


@pytest.mark.parametrize("quantity", [0, -5, float("nan"), float("inf"), 100_001, "abc"])
def test_an_impossible_quantity_is_refused_and_nothing_is_written(
        manager, breakfast, quantity):
    before = _dump(manager, breakfast["recipe"])
    with pytest.raises(ValueError):
        recipe_lines.set_ingredient_quantity(manager.db, breakfast["krisprolls"], quantity)
    assert _dump(manager, breakfast["recipe"]) == before


def test_the_validator_bounds(manager):
    assert recipe_lines.ingredient_quantity("50") == 50.0
    assert recipe_lines.ingredient_quantity(100_000) == 100_000.0
    for refused in (0, -1, 100_000.5, True):
        with pytest.raises(vol.Invalid):
            recipe_lines.ingredient_quantity(refused)


def test_the_new_refusals_read_in_french():
    assert french_error(ValueError("quantity must not exceed 100000, got 200000")) == (
        "invalid_value", "Quantité trop grande : 200000 (au plus 100000).")
    assert french_error(ValueError("expected a finite number, got 'inf'")) == (
        "invalid_format", "Un nombre est attendu (reçu : 'inf').")
    assert french_error(ValueError("missing field ingredient_id")) == (
        "invalid_format", "Champ obligatoire manquant : ingredient_id.")


def test_a_line_is_designated_by_its_id_or_by_its_product_in_a_recipe(manager, breakfast):
    recipe = breakfast["recipe"]
    assert recipe_lines.designated_line(manager.db, {"ingredient_id": 7}) == 7
    assert recipe_lines.designated_line(
        manager.db, {"recipe_id": recipe, "product": " KRISPROLLS "}) == breakfast["krisprolls"]
    assert recipe_lines.designated_line(
        manager.db, {"recipe_id": recipe, "product": "ail"}) == breakfast["ail"]
    # A line with no product answers to its imported text.
    assert recipe_lines.designated_line(
        manager.db, {"recipe_id": recipe, "product": "Eau"}) == breakfast["eau"]
    # The id wins over the name.
    assert recipe_lines.designated_line(
        manager.db, {"ingredient_id": breakfast["ail"], "recipe_id": recipe,
                     "product": "Krisprolls"}) == breakfast["ail"]


@pytest.mark.parametrize(("data", "message"), [
    ({}, "line not designated"),
    ({"product": "Ail"}, "line not designated"),
    ({"recipe_id": "RECIPE", "product": "  "}, "line not designated"),
    ({"recipe_id": 999999, "product": "Ail"}, "unknown recipe 999999"),
    ({"recipe_id": "RECIPE", "product": "Beurre"}, "no line named <Beurre> in recipe RECIPE"),
])
def test_a_line_that_cannot_be_designated_is_refused(manager, breakfast, data, message):
    recipe = breakfast["recipe"]
    data = {key: recipe if value == "RECIPE" else value for key, value in data.items()}
    with pytest.raises(ValueError) as caught:
        recipe_lines.designated_line(manager.db, data)
    assert str(caught.value) == message.replace("RECIPE", str(recipe))


def test_two_lines_answering_to_one_name_are_refused(manager, breakfast):
    with manager.db.write() as conn:
        ail = conn.execute("SELECT product_id FROM recipe_ingredient WHERE id = ?",
                           (breakfast["ail"],)).fetchone()[0]
        repo.insert_ingredient(conn, recipe_id=breakfast["recipe"], position=4,
                               raw_text="ail haché", product_id=ail, amount=3.0,
                               match_state="auto")
    with pytest.raises(ValueError) as caught:
        recipe_lines.designated_line(
            manager.db, {"recipe_id": breakfast["recipe"], "product": "Ail"})
    assert french_error(caught.value) == (
        "invalid_value", f"2 lignes « Ail » dans la recette {breakfast['recipe']} :"
                         " désigne la ligne par son ingredient_id.")


def test_the_designation_refusals_read_in_french():
    assert french_error(ValueError("line not designated")) == (
        "invalid_format", "Indique la ligne : ingredient_id, ou recipe_id et product.")
    assert french_error(ValueError("no line named <Beurre> in recipe 193")) == (
        "not_found", "Aucune ligne « Beurre » dans la recette 193.")
    assert french_error(ValueError("unknown field foo")) == (
        "invalid_format", "Champ inconnu : foo.")
    assert french_error(ValueError("expected a number, got bool True")) == (
        "invalid_format", "Un nombre est attendu (reçu : vrai).")
    assert french_error(ValueError("expected a whole number, got bool False")) == (
        "invalid_format", "Un nombre entier est attendu (reçu : faux).")
    assert french_error(ValueError("expected a string, got 42")) == (
        "invalid_format", "Un texte est attendu (reçu : 42).")
    assert french_error(ValueError("text too long: 201 characters (max 200)")) == (
        "invalid_value", "Texte trop long : 201 caractères (au plus 200).")


def test_a_line_put_back_takes_the_place_it_had(manager, breakfast):
    removed = recipe_lines.remove_ingredient(manager.db, breakfast["ail"])
    line = recipe_lines.add_ingredient(
        manager.db, breakfast["recipe"], product="AIL", quantity=5,
        raw_text=removed["raw_text"], position=removed["position"])
    assert (line["product_id"], line["amount"], line["raw_text"], line["position"]) == (
        removed["product_id"], 5.0, "1 gousse d'ail", 2)
    text = recipe_lines.add_ingredient(manager.db, breakfast["recipe"], raw_text=" sel ")
    assert (text["product_id"], text["amount"], text["raw_text"], text["position"],
            text["match_state"]) == (None, None, "sel", 4, "ignored")


def test_two_products_answering_to_one_name_are_refused(manager, breakfast):
    with manager.db.write() as conn:
        repo.insert_product(conn, name="AIL", base_unit="g")
    with pytest.raises(ValueError) as caught:
        recipe_lines.add_ingredient(manager.db, breakfast["recipe"], product="ail")
    assert french_error(caught.value) == (
        "invalid_value", "2 produits s'appellent « ail ».")
