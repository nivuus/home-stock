"""Valider un repas : cuisiner puis manger, en une transaction. Jamais deux."""
import math
from zoneinfo import ZoneInfo

import pytest

from custom_components.home_stock.application import StockManager
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations

PARIS = ZoneInfo("Europe/Paris")
TABLES = ("movement", "batch", "product", "article", "meal", "recipe",
          "recipe_ingredient")


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
    return {t: read.execute(f"SELECT * FROM {t} ORDER BY id").fetchall()
            for t in TABLES}


def _kitchen(manager, *, recipe_servings=1, lines=(), stock_of=()):
    ids = {}
    with manager.db.write() as conn:
        repo.insert_location(conn, name="Placard", kind="pantry")
        fridge = repo.insert_location(conn, name="Frigo", kind="fridge")
        recipe_id = repo.insert_recipe(conn, name="Gratin", source="manual",
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
                match_state=spec.get("state", "auto" if product_id else "unmatched"))
        for name, quantity, extra in stock_of:
            article_id = repo.insert_article(conn, product_id=ids[name])
            repo.insert_batch(conn, article_id=article_id, location_id=fridge,
                              quantity=quantity, entered_at="2026-08-01T10:00:00",
                              best_before=extra.get("best_before"),
                              price_per_base_unit=extra.get("price"),
                              nutrition=extra.get("nutrition"))
    return recipe_id, ids


def _simple(manager, *, amount=300.0, available=900.0, nutrition=None, price=None):
    recipe_id, ids = _kitchen(
        manager, recipe_servings=1,
        lines=[{"product": "Courgette", "amount": amount}],
        stock_of=[("Courgette", available,
                   {"nutrition": nutrition, "price": price})])
    meal_id = manager.plan_meal(day="2026-08-21", slot_key="dinner",
                                recipe_id=recipe_id, servings=3.0)["meal_id"]
    return recipe_id, ids, meal_id


def _movements(manager, reason=None):
    sql = "SELECT * FROM movement"
    args = ()
    if reason:
        sql += " WHERE reason = ?"
        args = (reason,)
    return manager.db.read().execute(sql + " ORDER BY id", args).fetchall()


# --- la simulation par défaut ----------------------------------------------

def test_dry_run_is_the_default_and_writes_nothing(manager):
    _, _, meal_id = _simple(manager)
    before = _snapshot(manager)
    result = manager.validate_meal(meal_id, portions_eaten=1)
    assert _snapshot(manager) == before
    assert "movement_ids" not in result


# --- les trois écritures ----------------------------------------------------

def test_the_ingredients_leave_as_cooked_with_ref_type_meal(manager):
    """Les deux colonnes que le lot 0 a posées « pour les lots ultérieurs »
    trouvent ici leur premier usage."""
    _, _, meal_id = _simple(manager)
    manager.validate_meal(meal_id, portions_eaten=1, dry_run=False)
    [out] = [m for m in _movements(manager, "cooked") if m["quantity"] < 0]
    assert out["quantity"] == -900.0        # 300 x facteur 3
    assert out["ref_type"] == "meal" and out["ref_id"] == meal_id
    assert out["idempotency_key"] == f"meal:{meal_id}:ing:1"


def test_the_ingredients_leave_in_fifo_with_one_movement_per_batch(manager):
    recipe_id, ids = _kitchen(
        manager, recipe_servings=1,
        lines=[{"product": "Courgette", "amount": 700.0}],
        stock_of=[("Courgette", 500.0, {}), ("Courgette", 400.0, {})])
    meal_id = manager.plan_meal(day="2026-08-21", slot_key="dinner",
                                recipe_id=recipe_id, servings=1.0)["meal_id"]
    manager.validate_meal(meal_id, portions_eaten=1, dry_run=False)
    out = [m for m in _movements(manager, "cooked") if m["quantity"] < 0]
    assert [m["quantity"] for m in out] == [-500.0, -200.0]
    assert [m["idempotency_key"] for m in out] == [
        f"meal:{meal_id}:ing:1", f"meal:{meal_id}:ing:1#1"]


def test_the_dish_enters_with_the_right_number_of_parts(manager):
    _, _, meal_id = _simple(manager)
    result = manager.validate_meal(meal_id, portions_eaten=1, dry_run=False)
    batch = manager.db.read().execute(
        "SELECT * FROM batch WHERE id = ?", (result["batch_id"],)).fetchone()
    assert batch["initial"] == 3.0
    assert batch["remaining"] == 2.0        # une part mangée, deux au frigo


def test_the_dish_best_before_is_the_day_plus_three(manager):
    _, _, meal_id = _simple(manager)
    result = manager.validate_meal(meal_id, portions_eaten=1, dry_run=False,
                                   occurred_at="2026-08-21T20:00:00")
    batch = manager.db.read().execute(
        "SELECT * FROM batch WHERE id = ?", (result["batch_id"],)).fetchone()
    assert batch["best_before"] == "2026-08-24"


def test_the_dish_lands_in_the_first_fridge_location(manager):
    _, _, meal_id = _simple(manager)
    result = manager.validate_meal(meal_id, portions_eaten=1, dry_run=False)
    read = manager.db.read()
    batch = read.execute("SELECT * FROM batch WHERE id = ?",
                         (result["batch_id"],)).fetchone()
    location = read.execute("SELECT * FROM location WHERE id = ?",
                            (batch["location_id"],)).fetchone()
    assert location["kind"] == "fridge"


def test_the_eaten_part_leaves_as_consumption_with_its_parts(manager):
    _, _, meal_id = _simple(manager)
    manager.validate_meal(meal_id, portions_eaten=1, dry_run=False,
                          parts_total=4, parts_mine=1)
    [eaten] = _movements(manager, "consumption")
    assert eaten["quantity"] == -1.0
    assert (eaten["parts_total"], eaten["parts_mine"]) == (4, 1)
    assert eaten["ref_type"] == "meal" and eaten["ref_id"] == meal_id


def test_eating_every_part_closes_the_batch_in_the_same_transaction(manager):
    """La poussière flottante du lot 0 § 7.2 : rien de spécial n'a été écrit."""
    _, _, meal_id = _simple(manager)
    result = manager.validate_meal(meal_id, portions_eaten=3, dry_run=False)
    batch = manager.db.read().execute(
        "SELECT * FROM batch WHERE id = ?", (result["batch_id"],)).fetchone()
    assert batch["remaining"] == 0.0
    assert batch["closed_at"] is not None


def test_cooking_without_eating_is_a_legitimate_sunday(manager):
    """Cuisiner un grand plat le dimanche pour la semaine : zéro part mangée
    n'est pas un refus, c'est le cas d'usage même des restes."""
    _, _, meal_id = _simple(manager)
    result = manager.validate_meal(meal_id, portions_eaten=0, dry_run=False)
    batch = manager.db.read().execute(
        "SELECT * FROM batch WHERE id = ?", (result["batch_id"],)).fetchone()
    assert batch["remaining"] == 3.0
    assert _movements(manager, "consumption") == []


def test_the_meal_is_marked_done_with_its_portions(manager):
    _, _, meal_id = _simple(manager)
    manager.validate_meal(meal_id, portions_eaten=2, dry_run=False)
    meal = repo.get_meal(manager.db.read(), meal_id)
    assert meal["state"] == "done"
    assert meal["portions_eaten"] == 2.0
    assert meal["validated_at"] is not None


# --- ce que `cooked` ne fait pas -------------------------------------------

def test_cooked_never_reaches_kcal_today_nor_the_costs(manager):
    _, _, meal_id = _simple(
        manager, nutrition={"kcal_per_base_unit": 2.0}, price=0.004)
    manager.validate_meal(meal_id, portions_eaten=0, dry_run=False,
                          occurred_at="2026-08-21T20:00:00")
    summary = manager.summary(expiration_alert_days=3, tz=PARIS,
                              now=_at("2026-08-21T21:00:00"))
    assert summary["today"]["kcal"] == 0
    assert summary["today"]["cost"] == 0
    assert summary["cost_waste_total"] == 0


def test_cooking_leaves_the_total_stock_value_unchanged(manager):
    """La valeur quitte les ingrédients et entre dans le plat. C'est la
    définition même de `cooked` : un changement de forme, pas une perte."""
    _, _, meal_id = _simple(manager, amount=300.0, available=900.0, price=0.004)
    before = manager.summary(expiration_alert_days=3, tz=PARIS,
                             now=_at("2026-08-21T21:00:00"))["stock_value"]
    manager.validate_meal(meal_id, portions_eaten=0, dry_run=False,
                          occurred_at="2026-08-21T20:00:00")
    after = manager.summary(expiration_alert_days=3, tz=PARIS,
                            now=_at("2026-08-21T21:00:00"))["stock_value"]
    assert after == pytest.approx(before)


def test_only_the_eaten_part_moves_kcal_today(manager):
    _, _, meal_id = _simple(manager, nutrition={"kcal_per_base_unit": 2.0})
    manager.validate_meal(meal_id, portions_eaten=1, dry_run=False,
                          occurred_at="2026-08-21T20:00:00")
    summary = manager.summary(expiration_alert_days=3, tz=PARIS,
                              now=_at("2026-08-21T21:00:00"))
    # 900 g x 2 kcal = 1800 pour le plat entier, soit 600 par part.
    assert summary["today"]["kcal"] == pytest.approx(600.0)


# --- les nutriments, valeur par valeur -------------------------------------

def test_one_null_nutrient_nulls_that_one_and_not_the_other_eight(manager):
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"product": "Courgette", "amount": 100.0},
               {"product": "Crème", "unit": "ml", "amount": 100.0}],
        stock_of=[("Courgette", 900.0,
                   {"nutrition": {"kcal_per_base_unit": 2.0, "proteins": 0.1}}),
                  ("Crème", 900.0, {"nutrition": {"kcal_per_base_unit": 3.0}})])
    meal_id = manager.plan_meal(day="2026-08-21", slot_key="dinner",
                                recipe_id=recipe_id, servings=1.0)["meal_id"]
    result = manager.validate_meal(meal_id, portions_eaten=0, dry_run=False)
    batch = manager.db.read().execute(
        "SELECT * FROM batch WHERE id = ?", (result["batch_id"],)).fetchone()
    assert batch["kcal_per_base_unit"] == pytest.approx(500.0)
    assert batch["proteins"] is None
    assert batch["fiber"] is None


# --- ce qui manque ----------------------------------------------------------

def test_an_unmatched_line_is_recorded_as_provenance_only(manager):
    """`skipped_ingredient_ids` est de la provenance. Rien ne le relit pour
    calculer quoi que ce soit — ce qui est réellement sorti est dans les
    mouvements, seule arithmétique qui existe."""
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"raw_text": "une gousse d'ail"},
               {"product": "Courgette", "amount": 100.0}],
        stock_of=[("Courgette", 900.0, {})])
    meal_id = manager.plan_meal(day="2026-08-21", slot_key="dinner",
                                recipe_id=recipe_id, servings=1.0)["meal_id"]
    manager.validate_meal(meal_id, portions_eaten=0, dry_run=False)
    meal = repo.get_meal(manager.db.read(), meal_id)
    assert "1" in meal["skipped_ingredient_ids"]
    out = [m for m in _movements(manager, "cooked") if m["quantity"] < 0]
    assert len(out) == 1        # seule la courgette est réellement sortie


def test_a_short_line_without_arbitration_refuses_the_whole_validation(manager):
    _, _, meal_id = _simple(manager, amount=500.0, available=200.0)
    with pytest.raises(ValueError, match="short"):
        manager.validate_meal(meal_id, portions_eaten=1, dry_run=False)
    assert _movements(manager) == []


def test_a_short_line_removed_by_hand_goes_through(manager):
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"product": "Courgette", "amount": 500.0}],
        stock_of=[("Courgette", 200.0, {})])
    meal_id = manager.plan_meal(day="2026-08-21", slot_key="dinner",
                                recipe_id=recipe_id, servings=1.0)["meal_id"]
    ingredient_id = repo.list_ingredients(manager.db.read(), recipe_id)[0]["id"]
    result = manager.validate_meal(meal_id, portions_eaten=1, dry_run=False,
                                   skip_ingredient_ids={ingredient_id})
    assert result["batch_id"] is not None


def test_an_ignored_line_decrements_nothing_and_is_not_reported(manager):
    recipe_id, _ = _kitchen(
        manager, recipe_servings=1,
        lines=[{"raw_text": "sel", "state": "ignored"},
               {"product": "Courgette", "amount": 100.0}],
        stock_of=[("Courgette", 900.0, {})])
    meal_id = manager.plan_meal(day="2026-08-21", slot_key="dinner",
                                recipe_id=recipe_id, servings=1.0)["meal_id"]
    manager.validate_meal(meal_id, portions_eaten=0, dry_run=False)
    out = [m for m in _movements(manager, "cooked") if m["quantity"] < 0]
    assert len(out) == 1
    assert "1" not in repo.get_meal(manager.db.read(),
                                    meal_id)["skipped_ingredient_ids"]


# --- l'idempotence et l'atomicité ------------------------------------------

def test_replaying_the_validation_returns_the_same_movement_ids(manager):
    _, _, meal_id = _simple(manager)
    first = manager.validate_meal(meal_id, portions_eaten=1, dry_run=False)
    with manager.db.write() as conn:
        repo.update_meal_fields(conn, meal_id, {"state": "planned"})
    second = manager.validate_meal(meal_id, portions_eaten=1, dry_run=False)
    assert second["movement_ids"] == first["movement_ids"]
    assert second["batch_id"] == first["batch_id"]
    # Les trois mouvements du repas — les ingrédients qui sortent, le plat qui
    # entre, la part qu'on mange — et rien de plus : le rejeu n'a rien écrit.
    assert len(_movements(manager)) == len(first["movement_ids"]) == 3


def test_a_failure_halfway_leaves_no_movement_and_no_batch(manager, monkeypatch):
    """Transaction unique : jamais un demi-repas. On fait échouer l'écriture du
    plat et on vérifie que les sorties d'ingrédients ont été annulées aussi."""
    _, _, meal_id = _simple(manager)
    before = _snapshot(manager)

    original = repo.insert_batch

    def boom(*args, **kwargs):
        raise RuntimeError("disque plein")

    monkeypatch.setattr(repo, "insert_batch", boom)
    with pytest.raises(RuntimeError):
        manager.validate_meal(meal_id, portions_eaten=1, dry_run=False)
    monkeypatch.setattr(repo, "insert_batch", original)
    assert _snapshot(manager) == before


def test_validating_a_meal_marked_done_by_hand_is_refused(manager):
    """`done` sans aucun mouvement sous `meal:<id>:` n'est pas un rejeu : c'est
    un repas que quelqu'un a marqué validé par un autre chemin. On refuse
    plutôt que de cuisiner par-dessus.

    Le rejeu, lui, se reconnaît aux mouvements et non à l'état — c'est ce que
    prouve le test précédent. Le plan demandait les deux comportements sans
    dire comment les distinguer ; la distinction est là.
    """
    _, _, meal_id = _simple(manager)
    with manager.db.write() as conn:
        repo.update_meal_fields(conn, meal_id, {"state": "done"})
    with pytest.raises(ValueError, match="already done"):
        manager.validate_meal(meal_id, portions_eaten=1, dry_run=False)
    assert _movements(manager) == []


# --- les bornes, aux deux bouts --------------------------------------------

@pytest.mark.parametrize("portions", [-1, math.nan, math.inf])
def test_portions_eaten_must_be_finite_and_not_negative(manager, portions):
    _, _, meal_id = _simple(manager)
    with pytest.raises(ValueError):
        manager.validate_meal(meal_id, portions_eaten=portions, dry_run=False)


def test_portions_eaten_above_the_parts_produced_is_refused(manager):
    """On ne mange pas quatre parts d'un plat qui en fait trois."""
    _, _, meal_id = _simple(manager)
    with pytest.raises(ValueError, match="exceeds"):
        manager.validate_meal(meal_id, portions_eaten=4, dry_run=False)


def test_parts_mine_above_parts_total_is_refused(manager):
    _, _, meal_id = _simple(manager)
    with pytest.raises(Exception):
        manager.validate_meal(meal_id, portions_eaten=1, dry_run=False,
                              parts_total=2, parts_mine=3)


def test_parts_total_above_twenty_four_is_refused(manager):
    _, _, meal_id = _simple(manager)
    with pytest.raises(Exception):
        manager.validate_meal(meal_id, portions_eaten=1, dry_run=False,
                              parts_total=25, parts_mine=1)


# --- la journée alimentaire -------------------------------------------------

def test_a_dinner_validated_at_one_in_the_morning_lands_on_the_evening(manager):
    """Le repas et le mouvement qu'il produit tombent dans la MÊME journée
    alimentaire — sinon le journal du panneau ne retrouve pas le repas qui a
    fait monter sa barre."""
    from custom_components.home_stock.domain.foodday import food_day_of
    _, _, meal_id = _simple(manager, nutrition={"kcal_per_base_unit": 2.0})
    manager.validate_meal(meal_id, portions_eaten=1, dry_run=False,
                          occurred_at="2026-08-22T01:00:00")
    [eaten] = _movements(manager, "consumption")
    assert food_day_of(_at(eaten["occurred_at"]), PARIS).isoformat() == "2026-08-21"


def _at(text):
    from datetime import datetime
    return datetime.fromisoformat(text).replace(tzinfo=PARIS)


# --- § 12.5 : corriger un repas validé --------------------------------------

def _ingredient_batches(manager):
    return {r["id"]: r["remaining"] for r in manager.db.read().execute(
        "SELECT b.id, b.remaining FROM batch b ORDER BY b.id")}


def test_correcting_a_meal_reverses_the_whole_block_in_reverse_order(manager):
    """N mouvements `cooked` négatifs, le lot de plat et son `cooked` positif,
    puis la `consumption` : contrepassés dans l'ordre INVERSE, en une
    transaction, et le repas repasse de `done` à `planned`."""
    _, _, meal_id = _simple(manager, nutrition={"kcal_per_base_unit": 2.0})
    written = manager.validate_meal(meal_id, portions_eaten=1, dry_run=False,
                                    occurred_at="2026-08-21T19:00:00")

    result = manager.correct_meal(meal_id, occurred_at="2026-08-22T09:00:00")

    assert result["meal_id"] == meal_id
    assert result["state"] == "planned"
    assert len(result["reversed_movements"]) == len(written["movement_ids"])
    reversed_targets = [
        r["corrects_id"] for r in manager.db.read().execute(
            "SELECT corrects_id FROM movement WHERE corrects_id IS NOT NULL"
            " ORDER BY id")]
    assert reversed_targets == list(reversed(written["movement_ids"]))
    meal = repo.get_meal(manager.db.read(), meal_id)
    assert meal["state"] == "planned"
    assert meal["validated_at"] is None


def test_correct_meal_is_the_only_caller_allowed_to_reverse_a_cooked(manager):
    """`correct_movement` sur un `cooked` de ce même repas reste refusé."""
    from custom_components.home_stock.domain.correction import CorrectionError
    _, _, meal_id = _simple(manager)
    written = manager.validate_meal(meal_id, portions_eaten=1, dry_run=False,
                                    occurred_at="2026-08-21T19:00:00")
    cooked = [r["id"] for r in _movements(manager, "cooked")]
    assert cooked
    with pytest.raises(CorrectionError):
        manager.correct_movement(cooked[0], occurred_at="2026-08-22T09:00:00")
    assert written["movement_ids"]


def test_correcting_a_meal_whose_dish_batch_was_started_is_refused(manager):
    """Une part mangée hors du repas rend le passé non reconstituable. Le
    refus DIT quoi faire : consommer le reste, ou corriger la seule
    consommation fautive."""
    from custom_components.home_stock.messages import french_message
    _, _, meal_id = _simple(manager)
    written = manager.validate_meal(meal_id, portions_eaten=1, dry_run=False,
                                    occurred_at="2026-08-21T19:00:00")
    manager.consume_batch(written["batch_id"], quantity=1.0,
                          occurred_at="2026-08-21T22:00:00")

    with pytest.raises(ValueError) as refus:
        manager.correct_meal(meal_id, occurred_at="2026-08-22T09:00:00")
    assert french_message(refus.value) == (
        "Ce plat a été entamé depuis : corrigez la consommation fautive, "
        "ou finissez le plat avant d'annuler le repas."
    )


def test_correcting_a_meal_leaves_the_stock_exactly_as_before(manager):
    """Le critère de recette : quantités de tous les lots d'ingrédients
    identiques à l'octet près avant validation et après correction."""
    _, _, meal_id = _simple(manager, nutrition={"kcal_per_base_unit": 2.0},
                            price=0.003)
    before = _ingredient_batches(manager)
    manager.validate_meal(meal_id, portions_eaten=1, dry_run=False,
                          occurred_at="2026-08-21T19:00:00")

    manager.correct_meal(meal_id, occurred_at="2026-08-22T09:00:00")

    after = _ingredient_batches(manager)
    for batch_id, remaining in before.items():
        assert after[batch_id] == pytest.approx(remaining)
    # Le lot de plat existe toujours, vide et clôturé : le journal reste lisible.
    dish = [r for r in manager.db.read().execute(
        "SELECT * FROM batch ORDER BY id") if r["id"] not in before]
    assert len(dish) == 1
    assert dish[0]["remaining"] == pytest.approx(0.0)
    assert dish[0]["closed_at"] == "2026-08-22T09:00:00"


def test_correcting_a_meal_zeroes_its_kcal_and_its_cost(manager):
    """La preuve de l'amendement A1 sur un bloc entier : le total de tous
    les temps revient exactement là où il était."""
    _, _, meal_id = _simple(manager, nutrition={"kcal_per_base_unit": 2.0},
                            price=0.003)
    before = dict(repo.totals_between(manager.db.read()))
    manager.validate_meal(meal_id, portions_eaten=1, dry_run=False,
                          occurred_at="2026-08-21T19:00:00")
    manager.correct_meal(meal_id, occurred_at="2026-08-22T09:00:00")

    after = dict(repo.totals_between(manager.db.read()))
    assert after["kcal"] == pytest.approx(before["kcal"])
    assert after["cost"] == pytest.approx(before["cost"])


def test_correcting_a_meal_is_idempotent_on_replay(manager):
    """Clé dérivée par mouvement ; un rejeu rend le même résultat."""
    _, _, meal_id = _simple(manager)
    manager.validate_meal(meal_id, portions_eaten=1, dry_run=False,
                          occurred_at="2026-08-21T19:00:00")
    first = manager.correct_meal(meal_id, occurred_at="2026-08-22T09:00:00")
    again = manager.correct_meal(meal_id, occurred_at="2026-08-22T09:05:00")

    assert again["reversed_movements"] == first["reversed_movements"]
    assert manager.db.read().execute(
        "SELECT COUNT(*) AS n FROM movement WHERE corrects_id IS NOT NULL"
    ).fetchone()["n"] == len(first["reversed_movements"])


def test_correcting_a_meal_that_was_never_validated_is_refused(manager):
    from custom_components.home_stock.messages import french_message
    _, _, meal_id = _simple(manager)
    with pytest.raises(ValueError) as refus:
        manager.correct_meal(meal_id, occurred_at="2026-08-22T09:00:00")
    assert french_message(refus.value) == (
        "Ce repas n'a pas été validé : il n'y a rien à annuler.")
