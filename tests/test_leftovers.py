"""Les restes cuisinés : un lot comme un autre, et c'est tout l'intérêt."""
from zoneinfo import ZoneInfo

import pytest

from custom_components.home_stock.application import StockManager
from custom_components.home_stock.const import (
    LEFTOVER_CATEGORY_NAME,
    LEFTOVER_NAME_PREFIX,
)
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


def _recipe(manager, *, name="Gratin", kcal=2.0, quantity=900.0):
    with manager.db.write() as conn:
        repo.insert_location(conn, name="Placard", kind="pantry")
        fridge = repo.insert_location(conn, name="Frigo", kind="fridge")
        recipe_id = repo.insert_recipe(conn, name=name, source="manual",
                                       created_at="2026-08-21T10:00:00", servings=1)
        product_id = repo.insert_product(conn, name=f"Courgette {name}", base_unit="g")
        repo.insert_ingredient(conn, recipe_id=recipe_id, position=1,
                               raw_text="courgette", product_id=product_id,
                               amount=300.0, match_state="auto")
        article_id = repo.insert_article(conn, product_id=product_id)
        repo.insert_batch(conn, article_id=article_id, location_id=fridge,
                          quantity=quantity, entered_at="2026-08-01T10:00:00",
                          nutrition={"kcal_per_base_unit": kcal})
    return recipe_id


def _cook(manager, recipe_id, *, portions_eaten=0, day="2026-08-21", servings=3.0):
    meal_id = manager.plan_meal(day=day, slot_key="dinner", recipe_id=recipe_id,
                                servings=servings)["meal_id"]
    return manager.validate_meal(meal_id, portions_eaten=portions_eaten,
                                 dry_run=False,
                                 occurred_at=f"{day}T20:00:00")


def _leftover_product(manager, recipe_id):
    read = manager.db.read()
    recipe = repo.get_recipe(read, recipe_id)
    return repo.get_product(read, recipe["leftover_product_id"])


# --- le produit et son article ---------------------------------------------

def test_the_leftover_product_is_created_once_for_two_cookings(manager):
    """`recipe.leftover_product_id` retient le lien : une seconde cuisson
    réutilise le même produit et le même article générique."""
    recipe_id = _recipe(manager, quantity=2000.0)
    _cook(manager, recipe_id, day="2026-08-21")
    first = _leftover_product(manager, recipe_id)["id"]
    _cook(manager, recipe_id, day="2026-08-22")
    assert _leftover_product(manager, recipe_id)["id"] == first

    read = manager.db.read()
    assert read.execute(
        "SELECT COUNT(*) c FROM product WHERE name LIKE 'Reste — %'"
    ).fetchone()["c"] == 1
    assert read.execute(
        "SELECT COUNT(*) c FROM article WHERE product_id = ?", (first,)
    ).fetchone()["c"] == 1


def test_the_leftover_product_is_a_piece_product_in_the_cooked_category(manager):
    recipe_id = _recipe(manager)
    _cook(manager, recipe_id)
    product = _leftover_product(manager, recipe_id)
    assert product["name"] == f"{LEFTOVER_NAME_PREFIX}Gratin"
    assert product["base_unit"] == "piece"          # une pièce = une part
    category = manager.db.read().execute(
        "SELECT name FROM category WHERE id = ?", (product["category_id"],)).fetchone()
    assert category["name"] == LEFTOVER_CATEGORY_NAME


def test_a_generic_article_accompanies_it(manager):
    """Un lot pointe toujours vers un article : aucun cas particulier dans le
    code de sortie, de kcal ou de coût."""
    recipe_id = _recipe(manager)
    _cook(manager, recipe_id)
    product = _leftover_product(manager, recipe_id)
    article = manager.db.read().execute(
        "SELECT * FROM article WHERE product_id = ?", (product["id"],)).fetchone()
    assert article["is_generic"] == 1


def test_the_dish_lands_in_the_fridge_by_default(manager):
    recipe_id = _recipe(manager)
    result = _cook(manager, recipe_id)
    read = manager.db.read()
    batch = read.execute("SELECT * FROM batch WHERE id = ?",
                         (result["batch_id"],)).fetchone()
    location = read.execute("SELECT * FROM location WHERE id = ?",
                            (batch["location_id"],)).fetchone()
    assert location["kind"] == "fridge"
    assert _leftover_product(manager, recipe_id)["default_location_id"] == location["id"]


def test_a_name_collision_is_suffixed_with_the_recipe_id(manager):
    """`product.name` est UNIQUE depuis m001 : une collision se désambiguïse,
    elle ne fait pas échouer la cuisson."""
    recipe_id = _recipe(manager, name="Gratin")
    with manager.db.write() as conn:
        repo.insert_product(conn, name=f"{LEFTOVER_NAME_PREFIX}Gratin",
                            base_unit="piece")
    _cook(manager, recipe_id)
    product = _leftover_product(manager, recipe_id)
    assert product["name"] == f"{LEFTOVER_NAME_PREFIX}Gratin ({recipe_id})"


# --- les valeurs sont sur le LOT, jamais sur l'article partagé --------------

def test_the_values_land_on_the_batch_not_on_the_shared_article(manager):
    """Deux cuissons de la même recette n'ont ni les mêmes nutriments ni le
    même coût ; écrire sur l'article écraserait la cuisson précédente pendant
    que ses parts attendent encore au frigo."""
    recipe_id = _recipe(manager, kcal=2.0, quantity=2000.0)
    first = _cook(manager, recipe_id, day="2026-08-21")

    # Deuxième cuisson avec une courgette deux fois plus calorique.
    with manager.db.write() as conn:
        conn.execute("UPDATE batch SET kcal_per_base_unit = 4.0"
                     " WHERE closed_at IS NULL AND id = 1")
    second = _cook(manager, recipe_id, day="2026-08-22")

    read = manager.db.read()
    kcals = [read.execute("SELECT kcal_per_base_unit FROM batch WHERE id = ?",
                          (batch_id,)).fetchone()["kcal_per_base_unit"]
             for batch_id in (first["batch_id"], second["batch_id"])]
    assert kcals[0] != kcals[1]

    product = _leftover_product(manager, recipe_id)
    article = read.execute("SELECT * FROM article WHERE product_id = ?",
                           (product["id"],)).fetchone()
    assert article["kcal_per_base_unit"] is None


def test_the_default_shelf_life_is_three_days(manager):
    recipe_id = _recipe(manager)
    result = _cook(manager, recipe_id, day="2026-08-21")
    batch = manager.db.read().execute(
        "SELECT * FROM batch WHERE id = ?", (result["batch_id"],)).fetchone()
    assert batch["best_before"] == "2026-08-24"


def test_a_recipe_can_override_the_shelf_life(manager):
    """Une soupe congelée le dit sur sa fiche."""
    recipe_id = _recipe(manager)
    with manager.db.write() as conn:
        repo.update_recipe_fields(conn, recipe_id, {"leftover_shelf_life_days": 90})
    result = _cook(manager, recipe_id, day="2026-08-21")
    batch = manager.db.read().execute(
        "SELECT * FROM batch WHERE id = ?", (result["batch_id"],)).fetchone()
    assert batch["best_before"] == "2026-11-19"


def test_a_cooked_dish_records_no_price_observation(manager):
    """Un plat cuisiné n'a jamais été acheté : lui inventer une observation de
    prix empoisonnerait l'historique d'un produit sans magasin ni ticket."""
    recipe_id = _recipe(manager)
    _cook(manager, recipe_id)
    assert manager.db.read().execute(
        "SELECT COUNT(*) c FROM price").fetchone()["c"] == 0


# --- l'effet de bord voulu --------------------------------------------------

def test_a_leftover_batch_shows_up_in_expiry_candidates(manager):
    """Le blueprint DLC du lot 2 annoncera « le gratin de dimanche périme
    demain » sans une ligne de code de plus. C'est le principal intérêt de
    traiter un reste comme n'importe quel autre lot."""
    recipe_id = _recipe(manager)
    _cook(manager, recipe_id, day="2026-08-21")
    summary = manager.summary(expiration_alert_days=7, tz=PARIS,
                              today="2026-08-22")
    names = [row["product_name"] for row in summary["expiring"]]
    assert f"{LEFTOVER_NAME_PREFIX}Gratin" in names


def test_a_leftover_product_has_no_min_quantity_and_never_reports_a_shortage(manager):
    recipe_id = _recipe(manager)
    _cook(manager, recipe_id, portions_eaten=3)      # tout mangé, lot fermé
    product = _leftover_product(manager, recipe_id)
    assert product["min_quantity"] is None or product["min_quantity"] == 0
    summary = manager.summary(expiration_alert_days=7, tz=PARIS,
                              today="2026-08-22")
    assert all(row["product_name"] != f"{LEFTOVER_NAME_PREFIX}Gratin"
               for row in summary["shortages"])


def test_a_leftover_product_falls_back_to_the_other_aisle(manager):
    """Pas de rayon : « Autre » si quelque chose les mettait un jour sur une
    liste de courses — ce que le lot 4 devra explicitement empêcher."""
    recipe_id = _recipe(manager)
    _cook(manager, recipe_id)
    assert _leftover_product(manager, recipe_id)["aisle_id"] is None
