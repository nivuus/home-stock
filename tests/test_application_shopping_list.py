"""Les quatre origines, une seule liste, réconciliée en une transaction."""
from datetime import date

import pytest

from custom_components.home_stock.storage import repositories as repo

from test_application import manager  # noqa: F401

TODAY = date(2026, 8, 21)


@pytest.fixture
def pantry(manager):
    """Un placard, trois produits avec seuil, un rayon chacun."""
    with manager.db.write() as conn:
        location_id = repo.insert_location(conn, name="Placard", kind="pantry")
        aisles = {row["name"]: row["id"] for row in repo.list_aisles(conn)}
        pasta = repo.insert_product(conn, name="Pâtes", base_unit="g",
                                    min_quantity=500,
                                    aisle_id=aisles["Épicerie salée"])
        milk = repo.insert_product(conn, name="Lait", base_unit="ml",
                                   min_quantity=2000,
                                   aisle_id=aisles["Crémerie"])
        coffee = repo.insert_product(conn, name="Café", base_unit="g")
        for product_id in (pasta, milk, coffee):
            repo.insert_article(conn, product_id=product_id, is_generic=1)
    return {"location_id": location_id, "pasta": pasta, "milk": milk,
            "coffee": coffee}


def _names(rows):
    return [row["product_name"] or row["free_text"] for row in rows]


def _origins(manager, item_id):
    return {row["origin"] for row in repo.claims_of(manager.db.read(), item_id)}


# --- les quatre origines ----------------------------------------------------

def test_a_shortage_creates_a_line_with_its_missing_quantity(manager, pantry):
    result = manager.reconcile_shopping_list(today=TODAY)

    assert result["created"] == 2                 # Pâtes et Lait, pas le Café
    rows = manager.shopping_list()
    assert _names(rows) == ["Lait", "Pâtes"] or _names(rows) == ["Pâtes", "Lait"]
    pasta = next(row for row in rows if row["product_name"] == "Pâtes")
    assert pasta["quantity"] == pytest.approx(500.0)
    assert _origins(manager, pasta["id"]) == {"shortage"}


def test_a_product_without_a_threshold_is_never_claimed(manager, pantry):
    manager.reconcile_shopping_list(today=TODAY)
    assert "Café" not in _names(manager.shopping_list())


def test_a_spare_battery_below_its_threshold_appears_like_any_other_product(manager, pantry):
    """Aucun code spécifique : le résultat le plus satisfaisant du découpage.
    La ligne se distingue seulement par son rayon, « Entretien et maison » —
    ce qui est exactement l'information utile."""
    with manager.db.write() as conn:
        aisle_id = next(row["id"] for row in repo.list_aisles(conn)
                        if row["name"] == "Entretien et maison")
        product_id = repo.insert_product(conn, name="Pile CR2032", base_unit="piece",
                                         min_quantity=2, edible=0, aisle_id=aisle_id)
        repo.insert_article(conn, product_id=product_id, is_generic=1)

    manager.reconcile_shopping_list(today=TODAY)

    row = next(r for r in manager.shopping_list() if r["product_name"] == "Pile CR2032")
    assert row["aisle_name"] == "Entretien et maison"
    assert _origins(manager, row["id"]) == {"shortage"}


def test_the_same_product_from_two_origins_stays_one_line(manager, pantry):
    _plan_a_meal(manager, pantry, product_id=pantry["pasta"], amount=800.0,
                 day="2026-08-22")

    manager.reconcile_shopping_list(today=TODAY)

    rows = [row for row in manager.shopping_list() if row["product_name"] == "Pâtes"]
    assert len(rows) == 1
    assert _origins(manager, rows[0]["id"]) == {"shortage", "meal_plan"}
    # Le MAXIMUM, jamais la somme : 800 réclamés par le repas, 500 par le seuil.
    assert rows[0]["quantity"] == pytest.approx(800.0)


def test_a_missing_ingredient_creates_a_line_scaled_to_the_guests(manager, pantry):
    _plan_a_meal(manager, pantry, product_id=pantry["coffee"], amount=100.0,
                 day="2026-08-22", servings=3.0)

    manager.reconcile_shopping_list(today=TODAY)

    row = next(r for r in manager.shopping_list() if r["product_name"] == "Café")
    assert row["quantity"] == pytest.approx(300.0)


def test_a_recurring_line_appears_when_it_is_due_and_marks_itself_added(manager, pantry):
    with manager.db.write() as conn:
        recurring_id = repo.upsert_recurring(conn, product_id=pantry["coffee"],
                                             quantity=250.0, every_days=21)

    manager.reconcile_shopping_list(today=TODAY)

    row = next(r for r in manager.shopping_list() if r["product_name"] == "Café")
    assert _origins(manager, row["id"]) == {"recurring"}
    assert row["quantity"] == pytest.approx(250.0)
    line = repo.list_recurring(manager.db.read(), active_only=False)[0]
    assert line["last_added_on"] == "2026-08-21"
    assert repo.due_recurring(manager.db.read(), "2026-08-21") == []
    assert recurring_id


def test_a_free_text_recurring_line_needs_no_product(manager, pantry):
    with manager.db.write() as conn:
        repo.upsert_recurring(conn, free_text="Sacs poubelle", quantity=None,
                              every_days=30)
    manager.reconcile_shopping_list(today=TODAY)
    assert "Sacs poubelle" in _names(manager.shopping_list())


# --- les règles de la réconciliation ---------------------------------------

def test_reconciling_twice_changes_nothing(manager, pantry):
    """Idempotence : la deuxième passe rend `created == 0`."""
    first = manager.reconcile_shopping_list(today=TODAY)
    second = manager.reconcile_shopping_list(today=TODAY)
    assert first["created"] == 2
    assert second == {"created": 0, "updated": 0, "removed": 0, "open": 2}


def test_the_hysteresis_keeps_a_line_just_above_the_threshold(manager, pantry):
    manager.reconcile_shopping_list(today=TODAY)
    _stock(manager, pantry, pantry["pasta"], 550.0)     # 500 < 550 <= 575

    manager.reconcile_shopping_list(today=TODAY)

    assert "Pâtes" in _names(manager.shopping_list())
    _stock(manager, pantry, pantry["pasta"], 600.0)     # au-delà de 575
    manager.reconcile_shopping_list(today=TODAY)
    assert "Pâtes" not in _names(manager.shopping_list())


def test_reconciling_while_a_session_is_open_leaves_checked_items_alone(manager, pantry):
    manager.reconcile_shopping_list(today=TODAY)
    row = next(r for r in manager.shopping_list() if r["product_name"] == "Pâtes")
    with manager.db.write() as conn:
        session_id = repo.open_session(conn, started_at="2026-08-21T10:00:00",
                                       store=None)
        repo.check_list_item(conn, row["id"], at="2026-08-21T10:05:00",
                             session_id=session_id, line_id=None)

    result = manager.reconcile_shopping_list(today=TODAY)

    assert result["removed"] == 0 and result["created"] == 0
    kept = next(r for r in manager.shopping_list() if r["id"] == row["id"])
    assert kept["checked_at"] == "2026-08-21T10:05:00"


def test_reconciling_after_the_session_closes_purges_and_may_recreate(manager, pantry):
    manager.reconcile_shopping_list(today=TODAY)
    row = next(r for r in manager.shopping_list() if r["product_name"] == "Pâtes")
    with manager.db.write() as conn:
        session_id = repo.open_session(conn, started_at="2026-08-21T10:00:00",
                                       store=None)
        repo.check_list_item(conn, row["id"], at="2026-08-21T10:05:00",
                             session_id=session_id, line_id=None)
        repo.set_session_state(conn, session_id, "done", closed_at="2026-08-21T11:00:00")

    result = manager.reconcile_shopping_list(today=TODAY)

    assert result["removed"] == 1 and result["created"] == 1
    fresh = next(r for r in manager.shopping_list() if r["product_name"] == "Pâtes")
    assert fresh["id"] != row["id"] and fresh["checked_at"] is None


def test_a_manual_line_survives_every_pass(manager, pantry):
    manager.add_to_shopping_list(free_text="Piles télécommande salon")
    for _ in range(3):
        manager.reconcile_shopping_list(today=TODAY)
    assert "Piles télécommande salon" in _names(manager.shopping_list())


def test_a_line_removed_by_hand_is_not_put_back(manager, pantry):
    manager.reconcile_shopping_list(today=TODAY)
    row = next(r for r in manager.shopping_list() if r["product_name"] == "Pâtes")
    manager.remove_list_item(row["id"])

    manager.reconcile_shopping_list(today=TODAY)

    assert "Pâtes" not in _names(manager.shopping_list())


def test_the_horizon_option_changes_the_meal_window(manager, pantry):
    """3 jours ne réclame pas les ingrédients du dîner de dimanche ;
    14 jours si. « Ce que je prépare » et « ce pour quoi je fais les
    courses » ne sont pas forcément la même durée."""
    _plan_a_meal(manager, pantry, product_id=pantry["coffee"], amount=100.0,
                 day="2026-08-30")

    manager.reconcile_shopping_list(today=TODAY, horizon_days=3)
    assert "Café" not in _names(manager.shopping_list())

    manager.reconcile_shopping_list(today=TODAY, horizon_days=14)
    assert "Café" in _names(manager.shopping_list())


def test_the_whole_reconciliation_runs_in_one_write_transaction(manager, pantry):
    """Avec `--timeout=60` : un verrou imbriqué figerait le processus SANS
    lever, et ce test est ce qui le transforme en échec lisible."""
    _plan_a_meal(manager, pantry, product_id=pantry["coffee"], amount=100.0,
                 day="2026-08-22")
    with manager.db.write() as conn:
        repo.upsert_recurring(conn, free_text="Sacs poubelle", quantity=None,
                              every_days=30)

    result = manager.reconcile_shopping_list(today=TODAY)

    assert result["created"] == 4
    assert result["open"] == 4


# --- l'ajout à la main ------------------------------------------------------

def test_add_to_shopping_list_refuses_a_line_that_names_nothing(manager, pantry):
    with pytest.raises(ValueError):
        manager.add_to_shopping_list()


def test_add_to_shopping_list_is_idempotent_on_its_key(manager, pantry):
    first = manager.add_to_shopping_list(free_text="Pain", idempotency_key="voix-1")
    again = manager.add_to_shopping_list(free_text="Pain", idempotency_key="voix-1")
    assert again["item_id"] == first["item_id"]
    assert len(manager.shopping_list()) == 1


def test_adding_a_product_already_on_the_list_adds_a_claim_not_a_line(manager, pantry):
    manager.reconcile_shopping_list(today=TODAY)
    row = next(r for r in manager.shopping_list() if r["product_name"] == "Pâtes")

    added = manager.add_to_shopping_list(product_id=pantry["pasta"], quantity=1000.0)

    assert added["item_id"] == row["id"]
    assert _origins(manager, row["id"]) == {"shortage", "manual"}
    updated = next(r for r in manager.shopping_list() if r["id"] == row["id"])
    assert updated["quantity"] == pytest.approx(1000.0)


def test_checking_and_unchecking_move_only_the_three_columns(manager, pantry):
    item = manager.add_to_shopping_list(free_text="Pain")
    manager.check_list_item(item["item_id"], at="2026-08-21T10:00:00")
    assert manager.shopping_list()[0]["checked_at"] == "2026-08-21T10:00:00"
    manager.uncheck_list_item(item["item_id"])
    assert manager.shopping_list()[0]["checked_at"] is None


# --- l'estimation -----------------------------------------------------------

def test_list_estimate_reports_its_confidence(manager, pantry):
    """Entièrement estimé, et il le dit. Ce capteur répond à « ça va faire
    combien ? » et à rien d'autre : il n'entre dans aucune comptabilité."""
    manager.reconcile_shopping_list(today=TODAY)
    with manager.db.write() as conn:
        article_id = repo.list_articles_for_product(conn, pantry["pasta"])[0]["id"]
        repo.insert_batch(conn, article_id=article_id, location_id=pantry["location_id"],
                          quantity=500, entered_at="2026-08-10T10:00:00",
                          price_per_base_unit=0.004)
        repo.insert_price(conn, article_id=article_id, observed_on="2026-08-10",
                          price_per_base_unit=0.004, source="manual", store=None)

    estimate = manager.list_estimate()

    assert estimate["total"] == 2
    assert estimate["priced"] == 1
    assert estimate["confidence"] == pytest.approx(0.5)
    assert estimate["amount"] == pytest.approx(2.0)


def test_an_empty_list_is_fully_confident_and_worth_nothing(manager, pantry):
    estimate = manager.list_estimate()
    assert estimate == {"amount": 0.0, "confidence": 1.0, "priced": 0, "total": 0}


# --- outillage --------------------------------------------------------------

def _stock(manager, pantry, product_id, quantity):
    with manager.db.write() as conn:
        article_id = repo.list_articles_for_product(conn, product_id)[0]["id"]
        conn.execute("UPDATE batch SET closed_at = '2026-08-21T00:00:00'"
                     " WHERE article_id = ?", (article_id,))
        repo.insert_batch(conn, article_id=article_id,
                          location_id=pantry["location_id"], quantity=quantity,
                          entered_at="2026-08-20T10:00:00")


def _plan_a_meal(manager, pantry, *, product_id, amount, day, servings=1.0):
    with manager.db.write() as conn:
        recipe_id = repo.insert_recipe(conn, name=f"Plat {day}", source="manual",
                                       created_at="2026-08-21T10:00:00", servings=1)
        repo.insert_ingredient(conn, recipe_id=recipe_id, position=1,
                               raw_text="ligne", product_id=product_id,
                               amount=amount, match_state="auto")
    manager.plan_meal(day=day, slot_key="dinner", recipe_id=recipe_id,
                      servings=servings)
