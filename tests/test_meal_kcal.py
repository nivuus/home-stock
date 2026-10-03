"""A validated meal counts in the day's kcal: what is eaten, never the leftover.

Rule decided by the owner on 2026-10-03 16:54: what is eaten counts, the part
put back in stock as a « Reste » is taken off the counter, and the leftover
carries those kcal to the day it is eaten. The case that broke it is the
breakfast of 2026-10-03 (movements 317-322): four ingredients, one of them
without any kcal value, and the whole meal counted zero.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.home_stock.application import StockManager
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations

PARIS = ZoneInfo("Europe/Paris")
# 2026-10-03 13:25 in Paris, stored the way movement.occurred_at is: naive UTC.
VALIDATED_AT = "2026-10-03T11:25:00"
SAME_DAY = datetime(2026, 10, 3, 16, 30, tzinfo=PARIS)
NEXT_DAY = datetime(2026, 10, 4, 12, 0, tzinfo=PARIS)

# name, base unit, reference_kcal per base unit, amount in the recipe, stock
CRISPBREAD = ("Krisprolls", "g", 4.2, 80.0, 225.0)
EGG = ("Œuf", "piece", 78.0, 1.0, 6.0)
CREAM_CHEESE = ("Fromage frais", "g", 0.9, 50.0, 300.0)
TOMATO = ("Tomate", "piece", 90.0, 1.0, 4.0)
BREAKFAST_KCAL = 80 * 4.2 + 78.0 + 50 * 0.9 + 90.0      # 549


@pytest.fixture
def manager(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.connect()
    with db.write() as conn:
        apply_migrations(conn)
    yield StockManager(db)
    db.close()


def _breakfast(manager, ingredients, *, servings=1.0, unvalued=()):
    """A one-serving recipe of these ingredients, in stock, planned as a meal.

    The kcal live on the PRODUCT (reference_kcal), as for loose produce at
    home; a name in `unvalued` gets none at all.
    """
    with manager.db.write() as conn:
        fridge = repo.insert_location(conn, name="Frigo", kind="fridge")
        recipe_id = repo.insert_recipe(conn, name="Petit-déjeuner", source="manual",
                                       created_at="2026-10-01T08:00:00", servings=1)
        for position, (name, unit, rate, amount, stock) in enumerate(ingredients, 1):
            product_id = repo.insert_product(
                conn, name=name, base_unit=unit,
                reference_kcal=None if name in unvalued else rate)
            repo.insert_ingredient(conn, recipe_id=recipe_id, position=position,
                                   raw_text=name, product_id=product_id,
                                   amount=amount, match_state="auto")
            article_id = repo.insert_article(conn, product_id=product_id)
            repo.insert_batch(conn, article_id=article_id, location_id=fridge,
                              quantity=stock, entered_at="2026-10-01T10:00:00")
    return manager.plan_meal(day="2026-10-03", slot_key="breakfast",
                             recipe_id=recipe_id, servings=servings)["meal_id"]


def _kcal(manager, now):
    return manager.summary(expiration_alert_days=3, tz=PARIS, now=now)["today"]


def _validate(manager, meal_id, eaten, **kwargs):
    return manager.validate_meal(meal_id, portions_eaten=eaten, dry_run=False,
                                 occurred_at=VALIDATED_AT, **kwargs)


# --- without a leftover -----------------------------------------------------

def test_a_meal_eaten_whole_adds_the_sum_of_its_ingredients(manager):
    meal_id = _breakfast(manager, [CRISPBREAD, EGG, CREAM_CHEESE, TOMATO])
    assert _kcal(manager, SAME_DAY)["kcal"] == 0
    _validate(manager, meal_id, 1)
    assert _kcal(manager, SAME_DAY)["kcal"] == pytest.approx(BREAKFAST_KCAL)


def test_grams_and_pieces_follow_the_consume_rule(manager):
    """Grams: rate per gram x grams (420 kcal/100 g x 80 g / 100 = 336).
    Pieces: rate per piece x pieces. The same rule stock/consume applies."""
    meal_id = _breakfast(manager, [CRISPBREAD, EGG])
    _validate(manager, meal_id, 1)
    assert _kcal(manager, SAME_DAY)["kcal"] == pytest.approx(420 * 80 / 100 + 78.0)


def test_the_03_10_breakfast_counts_what_is_known(manager):
    """Regression: the tomato carried no value, and the meal counted zero."""
    meal_id = _breakfast(manager, [CRISPBREAD, EGG, CREAM_CHEESE, TOMATO],
                         unvalued={"Tomate"})
    _validate(manager, meal_id, 1)
    assert _kcal(manager, SAME_DAY)["kcal"] == pytest.approx(BREAKFAST_KCAL - 90.0)


# --- with a leftover --------------------------------------------------------

def test_the_leftover_is_taken_off_the_counter_and_carries_its_kcal(manager):
    meal_id = _breakfast(manager, [CRISPBREAD, EGG], servings=2.0)
    whole = 2 * (80 * 4.2 + 78.0)
    result = _validate(manager, meal_id, 1)
    assert _kcal(manager, SAME_DAY)["kcal"] == pytest.approx(whole / 2)
    leftover = manager.db.read().execute(
        "SELECT * FROM batch WHERE id = ?", (result["batch_id"],)).fetchone()
    assert leftover["remaining"] == pytest.approx(1.0)
    assert leftover["remaining"] * leftover["kcal_per_base_unit"] == pytest.approx(
        whole / 2)


def test_the_leftover_counts_on_the_day_it_is_eaten_and_only_once(manager):
    meal_id = _breakfast(manager, [CRISPBREAD, EGG], servings=2.0)
    whole = 2 * (80 * 4.2 + 78.0)
    result = _validate(manager, meal_id, 1)
    leftover_product = manager.db.read().execute(
        "SELECT product_id FROM batch b JOIN article a ON a.id = b.article_id"
        " WHERE b.id = ?", (result["batch_id"],)).fetchone()["product_id"]
    manager.consume(product_id=leftover_product, quantity=1,
                    occurred_at="2026-10-04T10:00:00")
    assert _kcal(manager, SAME_DAY)["kcal"] == pytest.approx(whole / 2)
    assert _kcal(manager, NEXT_DAY)["kcal"] == pytest.approx(whole / 2)


def test_a_partly_valued_leftover_carries_the_known_part(manager):
    meal_id = _breakfast(manager, [CRISPBREAD, EGG], servings=2.0,
                         unvalued={"Œuf"})
    result = _validate(manager, meal_id, 1)
    leftover = manager.db.read().execute(
        "SELECT kcal_per_base_unit FROM batch WHERE id = ?",
        (result["batch_id"],)).fetchone()
    assert leftover["kcal_per_base_unit"] == pytest.approx(2 * 80 * 4.2 / 2)
    assert _kcal(manager, SAME_DAY)["kcal"] == pytest.approx(80 * 4.2)


# --- without any kcal -------------------------------------------------------

def test_a_meal_without_any_kcal_adds_zero_without_error(manager):
    meal_id = _breakfast(manager, [CRISPBREAD, EGG],
                         unvalued={"Krisprolls", "Œuf"})
    result = _validate(manager, meal_id, 1)
    assert result["movement_ids"]
    today = _kcal(manager, SAME_DAY)
    assert today["kcal"] == 0
    assert today["unvalued"] == 1


# --- when, and what does not move -------------------------------------------

def test_the_kcal_are_dated_at_the_validation(manager):
    meal_id = _breakfast(manager, [CRISPBREAD, EGG])
    _validate(manager, meal_id, 1)
    assert _kcal(manager, NEXT_DAY)["kcal"] == 0
    assert _kcal(manager, SAME_DAY)["kcal"] == pytest.approx(80 * 4.2 + 78.0)


def test_a_simulated_validation_adds_nothing(manager):
    meal_id = _breakfast(manager, [CRISPBREAD, EGG])
    manager.validate_meal(meal_id, portions_eaten=1, occurred_at=VALIDATED_AT)
    assert _kcal(manager, SAME_DAY)["kcal"] == 0


def test_a_direct_consumption_still_counts_beside_a_validated_meal(manager):
    meal_id = _breakfast(manager, [CRISPBREAD, EGG])
    _validate(manager, meal_id, 1)
    crispbread = manager.db.read().execute(
        "SELECT id FROM product WHERE name = 'Krisprolls'").fetchone()["id"]
    manager.consume(product_id=crispbread, quantity=20,
                    occurred_at="2026-10-03T14:00:00")
    assert _kcal(manager, SAME_DAY)["kcal"] == pytest.approx(
        80 * 4.2 + 78.0 + 20 * 4.2)
