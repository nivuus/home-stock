"""Poser, déplacer, annuler un repas. Un repas validé ne bouge jamais."""
import math
from zoneinfo import ZoneInfo

import pytest

from custom_components.home_stock.application import StockManager
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations

PARIS = ZoneInfo("Europe/Paris")


@pytest.fixture
def manager(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.connect()
    with db.write() as conn:
        apply_migrations(conn)
    yield StockManager(db)
    db.close()


def _recipe(manager, name="Kapsalon", servings=2):
    return manager.create_recipe(name=name, servings=servings)


def _product(manager, name="Yaourt", base_unit="piece"):
    with manager.db.write() as conn:
        return repo.insert_product(conn, name=name, base_unit=base_unit)


# --- poser ------------------------------------------------------------------

def test_a_recipe_meal_lands_with_a_uid(manager):
    recipe_id = _recipe(manager)
    posted = manager.plan_meal(day="2026-08-21", slot_key="dinner",
                               recipe_id=recipe_id, servings=4.0)
    assert posted["uid"].startswith("home-stock-meal-")
    meal = repo.get_meal(manager.db.read(), posted["meal_id"])
    assert meal["recipe_id"] == recipe_id
    assert meal["servings"] == 4.0
    assert meal["state"] == "planned"
    assert meal["day"] == "2026-08-21"


def test_a_product_meal_and_a_note_meal_are_both_legitimate(manager):
    product_id = _product(manager)
    first = manager.plan_meal(day="2026-08-21", slot_key="snack",
                              product_id=product_id, amount=1.0)
    second = manager.plan_meal(day="2026-08-21", slot_key="lunch",
                               note="Restaurant avec Anne")
    read = manager.db.read()
    assert repo.get_meal(read, first["meal_id"])["product_id"] == product_id
    assert repo.get_meal(read, second["meal_id"])["note"] == "Restaurant avec Anne"


def test_a_meal_that_is_two_things_at_once_is_refused(manager):
    """La contrainte de schéma le dit ; la couche du dessus doit le dire AVANT,
    plutôt que de laisser remonter une IntegrityError sans contexte."""
    recipe_id = _recipe(manager)
    product_id = _product(manager)
    with pytest.raises(ValueError, match="exactly one"):
        manager.plan_meal(day="2026-08-21", slot_key="dinner",
                          recipe_id=recipe_id, product_id=product_id)


def test_a_meal_that_is_nothing_at_all_is_refused(manager):
    with pytest.raises(ValueError, match="exactly one"):
        manager.plan_meal(day="2026-08-21", slot_key="dinner")


@pytest.mark.parametrize("servings", [0, -1, math.inf, math.nan])
def test_servings_must_be_strictly_positive_and_finite(manager, servings):
    with pytest.raises(ValueError):
        manager.plan_meal(day="2026-08-21", slot_key="dinner", note="x",
                          servings=servings)


def test_an_unknown_slot_is_refused_by_name(manager):
    with pytest.raises(ValueError, match="brunch"):
        manager.plan_meal(day="2026-08-21", slot_key="brunch", note="x")


@pytest.mark.parametrize("day", ["2026-8-1", "20260801", "2026-13-01", "hier", "",
                                 "2026-W01-1", None])
def test_a_malformed_day_is_refused(manager, day):
    """La forme étendue AAAA-MM-JJ et rien d'autre : `date.fromisoformat`
    accepte la forme compacte et la forme semaine depuis Python 3.11, et
    `julianday()` rend alors NULL — le repas disparaîtrait du planning."""
    with pytest.raises(ValueError):
        manager.plan_meal(day=day, slot_key="dinner", note="x")


def test_two_meals_in_the_same_slot_get_distinct_positions(manager):
    first = manager.plan_meal(day="2026-08-21", slot_key="dinner", note="entrée")
    second = manager.plan_meal(day="2026-08-21", slot_key="dinner", note="plat")
    read = manager.db.read()
    assert repo.get_meal(read, first["meal_id"])["position"] == 0
    assert repo.get_meal(read, second["meal_id"])["position"] == 1


def test_the_uid_is_injectable_so_tests_stay_deterministic(manager):
    posted = manager.plan_meal(day="2026-08-21", slot_key="dinner", note="x",
                               uid="home-stock-meal-fixe")
    assert posted["uid"] == "home-stock-meal-fixe"


def test_two_meals_never_share_a_uid(manager):
    uids = {manager.plan_meal(day="2026-08-21", slot_key="dinner",
                              note=f"repas {i}")["uid"] for i in range(20)}
    assert len(uids) == 20


# --- déplacer ---------------------------------------------------------------

def test_moving_a_planned_meal_changes_day_slot_and_position(manager):
    posted = manager.plan_meal(day="2026-08-21", slot_key="dinner", note="x")
    manager.move_meal(posted["meal_id"], day="2026-08-23", slot_key="lunch")
    meal = repo.get_meal(manager.db.read(), posted["meal_id"])
    assert (meal["day"], meal["slot_key"]) == ("2026-08-23", "lunch")


def test_moving_appends_to_the_target_slot(manager):
    manager.plan_meal(day="2026-08-23", slot_key="lunch", note="déjà là")
    posted = manager.plan_meal(day="2026-08-21", slot_key="dinner", note="x")
    manager.move_meal(posted["meal_id"], day="2026-08-23", slot_key="lunch")
    assert repo.get_meal(manager.db.read(), posted["meal_id"])["position"] == 1


def test_moving_a_done_meal_is_refused(manager):
    """Ses mouvements portent une date que rien ne peut plus changer : déplacer
    la ligne les décorrélerait en silence."""
    posted = manager.plan_meal(day="2026-08-21", slot_key="dinner", note="x")
    with manager.db.write() as conn:
        repo.update_meal_fields(conn, posted["meal_id"], {"state": "done"})
    with pytest.raises(ValueError, match="already done"):
        manager.move_meal(posted["meal_id"], day="2026-08-23", slot_key="lunch")


def test_moving_an_unknown_meal_is_refused_by_id(manager):
    with pytest.raises(ValueError, match="999"):
        manager.move_meal(999, day="2026-08-23", slot_key="lunch")


def test_moving_to_an_unknown_slot_is_refused(manager):
    posted = manager.plan_meal(day="2026-08-21", slot_key="dinner", note="x")
    with pytest.raises(ValueError, match="brunch"):
        manager.move_meal(posted["meal_id"], day="2026-08-23", slot_key="brunch")


# --- annuler ----------------------------------------------------------------

def test_cancelling_a_planned_meal_deletes_the_row(manager):
    posted = manager.plan_meal(day="2026-08-21", slot_key="dinner", note="x")
    assert manager.cancel_meal(posted["meal_id"]) == "deleted"
    assert repo.get_meal(manager.db.read(), posted["meal_id"]) is None


def test_cancelling_a_done_meal_marks_it_skipped_and_keeps_the_row(manager):
    """Supprimer un repas validé détruirait la référence
    `movement.ref_type = 'meal'` que le journal porte déjà — et le journal est
    en ajout seul précisément pour que cela n'arrive pas."""
    posted = manager.plan_meal(day="2026-08-21", slot_key="dinner", note="x")
    with manager.db.write() as conn:
        repo.update_meal_fields(conn, posted["meal_id"], {"state": "done"})
    assert manager.cancel_meal(posted["meal_id"]) == "skipped"
    meal = repo.get_meal(manager.db.read(), posted["meal_id"])
    assert meal is not None and meal["state"] == "skipped"


def test_cancelling_an_unknown_meal_is_refused_by_id(manager):
    with pytest.raises(ValueError, match="999"):
        manager.cancel_meal(999)


def test_a_meal_whose_time_has_passed_stays_planned(manager):
    """Le composant ne décide pas tout seul qu'un repas n'a pas eu lieu."""
    posted = manager.plan_meal(day="2020-01-01", slot_key="dinner", note="oublié")
    assert repo.get_meal(manager.db.read(), posted["meal_id"])["state"] == "planned"
    assert manager.list_meals("2020-01-01", "2020-01-01")[0]["state"] == "planned"


# --- lire -------------------------------------------------------------------

def test_list_meals_bounds_are_inclusive_at_both_ends(manager):
    for day in ("2026-08-19", "2026-08-20", "2026-08-21", "2026-08-22"):
        manager.plan_meal(day=day, slot_key="dinner", note=day)
    assert [m["day"] for m in manager.list_meals("2026-08-20", "2026-08-21")] == [
        "2026-08-20", "2026-08-21"]


def test_meal_summary_names_the_next_unvalidated_meal(manager):
    recipe_id = _recipe(manager, name="Kapsalon")
    manager.plan_meal(day="2026-08-21", slot_key="lunch", note="passé")
    manager.plan_meal(day="2026-08-22", slot_key="dinner", recipe_id=recipe_id)
    summary = manager.meal_summary(
        tz=PARIS, now=_at("2026-08-22T10:00:00"))
    assert summary["next"]["recipe_name"] == "Kapsalon"
    assert summary["next"]["slot_key"] == "dinner"


def test_meal_summary_skips_a_done_meal(manager):
    posted = manager.plan_meal(day="2026-08-22", slot_key="lunch", note="mangé")
    manager.plan_meal(day="2026-08-22", slot_key="dinner", note="à venir")
    with manager.db.write() as conn:
        repo.update_meal_fields(conn, posted["meal_id"], {"state": "done"})
    summary = manager.meal_summary(tz=PARIS, now=_at("2026-08-22T10:00:00"))
    assert summary["next"]["note"] == "à venir"


def test_meal_summary_counts_the_missing_products_over_the_horizon(manager):
    recipe_id = _recipe(manager, servings=1)
    product_id = _product(manager, name="Oignon", base_unit="g")
    with manager.db.write() as conn:
        repo.insert_ingredient(conn, recipe_id=recipe_id, position=1,
                               raw_text="oignon", product_id=product_id,
                               amount=500.0, match_state="auto")
    manager.plan_meal(day="2026-08-23", slot_key="dinner", recipe_id=recipe_id)
    summary = manager.meal_summary(tz=PARIS, now=_at("2026-08-22T10:00:00"))
    assert [m["product_name"] for m in summary["missing"]] == ["Oignon"]


def test_meal_summary_ignores_what_is_beyond_the_horizon(manager):
    recipe_id = _recipe(manager, servings=1)
    product_id = _product(manager, name="Oignon", base_unit="g")
    with manager.db.write() as conn:
        repo.insert_ingredient(conn, recipe_id=recipe_id, position=1,
                               raw_text="oignon", product_id=product_id,
                               amount=500.0, match_state="auto")
    manager.plan_meal(day="2026-09-30", slot_key="dinner", recipe_id=recipe_id)
    summary = manager.meal_summary(tz=PARIS, now=_at("2026-08-22T10:00:00"))
    assert summary["missing"] == []


def test_meal_summary_counts_the_recipes(manager):
    _recipe(manager, name="Kapsalon")
    manager.create_recipe(name="À relire", needs_review=1)
    summary = manager.meal_summary(tz=PARIS, now=_at("2026-08-22T10:00:00"))
    assert summary["recipes"]["total"] == 2
    assert summary["recipes"]["to_review"] == 1


def test_meal_summary_is_empty_without_any_meal_and_never_raises(manager):
    summary = manager.meal_summary(tz=PARIS, now=_at("2026-08-22T10:00:00"))
    assert summary["next"] is None
    assert summary["missing"] == []
    assert summary["recipes"]["total"] == 0


def test_meal_summary_uses_the_food_day_not_the_calendar_day(manager):
    """À une heure du matin on finit encore la soirée de la veille : le repas
    du 21 est toujours « le prochain », pas un repas manqué."""
    manager.plan_meal(day="2026-08-21", slot_key="dinner", note="tard")
    summary = manager.meal_summary(tz=PARIS, now=_at("2026-08-22T01:00:00"))
    assert summary["next"]["note"] == "tard"


def _at(text):
    from datetime import datetime
    return datetime.fromisoformat(text).replace(tzinfo=PARIS)
