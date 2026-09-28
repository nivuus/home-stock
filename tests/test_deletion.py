"""Deleting a product or an article: refuse, erase, or hide.

Every fixture holds two subjects — the one being deleted and an unrelated one
— so a query that forgets its WHERE clause touches the wrong product and fails.
"""
from __future__ import annotations

import pytest

from custom_components.home_stock.deletion import (
    DeleteBlocked,
    delete_article,
    delete_product,
    set_article_active,
)

NOW = "2026-09-28T10:00:00"


def _dump(db) -> list[str]:
    """Every row of every table: a refused delete must leave this identical."""
    return list(db.read().iterdump())


def _one(db, sql, *args):
    return db.read().execute(sql, args).fetchone()


def _count(db, table, where="1", *args) -> int:
    return db.read().execute(
        f"SELECT COUNT(*) AS n FROM {table} WHERE {where}", args).fetchone()["n"]


@pytest.fixture
def two(manager):
    """Riz (the subject) and Lait (the bystander), each fully dressed: an
    article, a barcode, an article packaging, a product packaging, a price and
    an ingredient alias. Neither has ever served."""
    ids = {}
    with manager.db.write() as conn:
        ids["frigo"] = conn.execute(
            "INSERT INTO location (name, kind) VALUES ('Frigo', 'fridge')").lastrowid
        for key, name, code in (("riz", "Riz", "3000000000001"),
                                ("lait", "Lait", "3000000000002")):
            product = conn.execute(
                "INSERT INTO product (name, base_unit) VALUES (?, 'g')", (name,)).lastrowid
            article = conn.execute(
                "INSERT INTO article (product_id, label) VALUES (?, ?)",
                (product, f"{name} 1 kg")).lastrowid
            conn.execute("INSERT INTO barcode (code, article_id) VALUES (?, ?)",
                         (code, article))
            conn.execute(
                "INSERT INTO packaging (scope, target_id, name, base_quantity)"
                " VALUES ('article', ?, 'paquet', 1000)", (article,))
            conn.execute(
                "INSERT INTO packaging (scope, target_id, name, base_quantity)"
                " VALUES ('product', ?, 'bol', 80)", (product,))
            conn.execute(
                "INSERT INTO price (article_id, observed_on, price_per_base_unit, source)"
                " VALUES (?, '2026-09-01', 0.002, 'manual')", (article,))
            conn.execute(
                "INSERT INTO ingredient_alias (normalised, product_id, created_at)"
                " VALUES (?, ?, ?)", (name.lower(), product, NOW))
            ids[key] = product
            ids[f"{key}_article"] = article
    return ids


def _recipe(conn, name, *, active=1, product=None, leftover=None) -> int:
    recipe = conn.execute(
        "INSERT INTO recipe (name, source, created_at, active, leftover_product_id)"
        " VALUES (?, 'manual', ?, ?, ?)", (name, NOW, active, leftover)).lastrowid
    if product is not None:
        conn.execute(
            "INSERT INTO recipe_ingredient (recipe_id, position, product_id, raw_text,"
            " match_state) VALUES (?, 1, ?, 'riz', 'confirmed')", (recipe, product))
    return recipe


def _batch(conn, article, location, *, closed=False) -> int:
    return conn.execute(
        "INSERT INTO batch (article_id, location_id, remaining, initial, entered_at,"
        " closed_at) VALUES (?, ?, ?, 1000, ?, ?)",
        (article, location, 0 if closed else 1000, NOW, NOW if closed else None),
    ).lastrowid


# --- what blocks a product -------------------------------------------------

def _open_batch(conn, t):
    _batch(conn, t["riz_article"], t["frigo"])
    _batch(conn, t["riz_article"], t["frigo"])


def _active_recipes(conn, t):
    for name in ("Curry", "Risotto", "Tajine", "Paella"):
        _recipe(conn, name, product=t["riz"])


def _planned_meal(conn, t):
    conn.execute(
        "INSERT INTO meal (uid, day, slot_key, product_id, created_at)"
        " VALUES ('m1', '2026-09-30', 'dinner', ?, ?)", (t["riz"], NOW))


def _shopping_item(conn, t):
    conn.execute("INSERT INTO shopping_list_item (product_id, added_at) VALUES (?, ?)",
                 (t["riz"], NOW))


def _recurring(conn, t):
    conn.execute("INSERT INTO shopping_recurring (product_id, every_days) VALUES (?, 7)",
                 (t["riz"],))


def _equipment(conn, t):
    equipment = conn.execute(
        "INSERT INTO equipment (name) VALUES ('Cuiseur à riz')").lastrowid
    conn.execute(
        "INSERT INTO equipment_consumable (equipment_id, product_id, role)"
        " VALUES (?, ?, 'other')", (equipment, t["riz"]))


def _battery(conn, t):
    conn.execute(
        "INSERT INTO battery (label, kind, product_id) VALUES ('Télécommande',"
        " 'primary', ?)", (t["riz"],))


def _leftover(conn, t):
    _recipe(conn, "Riz cantonais", leftover=t["riz"])


def _in_the_cart(conn, t):
    """In the cart right now: hiding it would store a purchase on a hidden
    product the moment the session is put away."""
    session = conn.execute(
        "INSERT INTO shopping_session (started_at, state) VALUES (?, 'to_store')",
        (NOW,)).lastrowid
    conn.execute(
        "INSERT INTO shopping_line (session_id, article_id, quantity, scanned_at)"
        " VALUES (?, ?, 1000, ?)", (session, t["riz_article"], NOW))


PRODUCT_BLOCKERS = [
    (_open_batch, "Encore 2 lots en stock (Frigo)"),
    (_active_recipes, "Utilisé dans 4 recettes : Curry, Paella, Risotto, …"),
    (_planned_meal, "Prévu dans 1 repas : 2026-09-30 (dîner)"),
    (_shopping_item, "Sur la liste de courses"),
    (_recurring, "Dans 1 course récurrente"),
    (_equipment, "Consommable de 1 équipement : Cuiseur à riz"),
    (_battery, "Rechange de 1 pile : Télécommande"),
    (_leftover, "Reste de 1 recette : Riz cantonais"),
    (_in_the_cart, "Dans 1 ligne de la session de courses en cours"),
]


@pytest.mark.parametrize(("seed", "phrase"), PRODUCT_BLOCKERS,
                         ids=[s.__name__.strip("_") for s, _ in PRODUCT_BLOCKERS])
def test_a_blocked_product_is_refused_and_nothing_changes(manager, two, seed, phrase):
    with manager.db.write() as conn:
        seed(conn, two)
    before = _dump(manager.db)

    with pytest.raises(DeleteBlocked) as err:
        delete_product(manager.db, two["riz"])

    assert phrase in str(err.value)
    assert _dump(manager.db) == before


def test_the_bystander_of_a_blocker_deletes_fine(manager, two):
    """Every blocker on Riz, none on Lait: Lait's delete must not see them."""
    with manager.db.write() as conn:
        for seed, _ in PRODUCT_BLOCKERS:
            seed(conn, two)
    assert delete_product(manager.db, two["lait"]) == "deleted"


def test_several_blockers_are_named_together(manager, two):
    with manager.db.write() as conn:
        _open_batch(conn, two)
        _recurring(conn, two)
    with pytest.raises(DeleteBlocked) as err:
        delete_product(manager.db, two["riz"])
    assert str(err.value) == "Encore 2 lots en stock (Frigo) ; dans 1 course récurrente"


# --- what blocks an article ------------------------------------------------

def test_an_article_with_an_open_batch_is_refused(manager, two):
    with manager.db.write() as conn:
        _batch(conn, two["riz_article"], two["frigo"])
        _batch(conn, two["lait_article"], two["frigo"])
    before = _dump(manager.db)
    with pytest.raises(DeleteBlocked) as err:
        delete_article(manager.db, two["riz_article"])
    assert "Encore 1 lot en stock (Frigo)" in str(err.value)
    assert _dump(manager.db) == before


@pytest.mark.parametrize(("state", "blocked"), [
    ("shopping", True), ("to_store", True), ("done", False)])
def test_an_article_in_a_running_shopping_session_is_refused(manager, two, state, blocked):
    with manager.db.write() as conn:
        session = conn.execute(
            "INSERT INTO shopping_session (started_at, state) VALUES (?, ?)",
            (NOW, state)).lastrowid
        conn.execute(
            "INSERT INTO shopping_line (session_id, article_id, quantity, scanned_at)"
            " VALUES (?, ?, 1000, ?)", (session, two["riz_article"], NOW))
    before = _dump(manager.db)
    if blocked:
        with pytest.raises(DeleteBlocked) as err:
            delete_article(manager.db, two["riz_article"])
        assert "Dans 1 ligne de la session de courses en cours" in str(err.value)
        assert _dump(manager.db) == before
    else:
        # A line of a closed session is history: the article is hidden.
        assert delete_article(manager.db, two["riz_article"]) == "hidden"


# --- erase or hide --------------------------------------------------------

def test_a_product_that_never_served_is_erased_with_its_dependencies(manager, two):
    assert delete_product(manager.db, two["riz"]) == "deleted"

    riz, article = two["riz"], two["riz_article"]
    assert _count(manager.db, "product", "id = ?", riz) == 0
    assert _count(manager.db, "article", "product_id = ?", riz) == 0
    assert _count(manager.db, "barcode", "article_id = ?", article) == 0
    assert _count(manager.db, "price", "article_id = ?", article) == 0
    assert _count(manager.db, "ingredient_alias", "product_id = ?", riz) == 0
    assert _count(manager.db, "packaging",
                  "(scope = 'article' AND target_id = ?)"
                  " OR (scope = 'product' AND target_id = ?)", article, riz) == 0
    # The bystander keeps everything.
    lait, lait_article = two["lait"], two["lait_article"]
    assert _count(manager.db, "product", "id = ?", lait) == 1
    assert _count(manager.db, "barcode", "article_id = ?", lait_article) == 1
    assert _count(manager.db, "price", "article_id = ?", lait_article) == 1
    assert _count(manager.db, "ingredient_alias", "product_id = ?", lait) == 1
    assert _count(manager.db, "packaging",
                  "(scope = 'article' AND target_id = ?)"
                  " OR (scope = 'product' AND target_id = ?)", lait_article, lait) == 2


def test_a_product_whose_only_batch_is_closed_is_hidden_with_its_journal(manager, two):
    manager.add_stock(article_id=two["riz_article"], quantity=500,
                      location_id=two["frigo"], occurred_at=NOW)
    manager.consume(product_id=two["riz"], quantity=500, occurred_at=NOW)
    assert _count(manager.db, "batch", "closed_at IS NULL") == 0
    journal = [dict(r) for r in manager.db.read().execute(
        "SELECT * FROM movement ORDER BY id")]
    assert journal

    assert delete_product(manager.db, two["riz"]) == "hidden"

    assert _one(manager.db, "SELECT active FROM product WHERE id = ?", two["riz"])[0] == 0
    assert [dict(r) for r in manager.db.read().execute(
        "SELECT * FROM movement ORDER BY id")] == journal
    assert _count(manager.db, "barcode", "article_id = ?", two["riz_article"]) == 1


@pytest.mark.parametrize("history", ["closed_batch", "inactive_recipe", "done_meal",
                                     "removed_list_item", "inactive_recurring",
                                     "receipt_line"])
def test_any_history_hides_instead_of_erasing(manager, two, history):
    with manager.db.write() as conn:
        match history:
            case "closed_batch":
                _batch(conn, two["riz_article"], two["frigo"], closed=True)
            case "inactive_recipe":
                _recipe(conn, "Vieux curry", active=0, product=two["riz"])
            case "done_meal":
                conn.execute(
                    "INSERT INTO meal (uid, day, slot_key, product_id, state, created_at)"
                    " VALUES ('m1', '2026-01-01', 'lunch', ?, 'done', ?)",
                    (two["riz"], NOW))
            case "removed_list_item":
                conn.execute(
                    "INSERT INTO shopping_list_item (product_id, added_at, removed_at)"
                    " VALUES (?, ?, ?)", (two["riz"], NOW, NOW))
            case "inactive_recurring":
                conn.execute(
                    "INSERT INTO shopping_recurring (product_id, every_days, active)"
                    " VALUES (?, 7, 0)", (two["riz"],))
            case "receipt_line":
                receipt = conn.execute(
                    "INSERT INTO receipt (media_content_id, captured_at, state)"
                    " VALUES ('media-source://x', ?, 'applied')", (NOW,)).lastrowid
                conn.execute(
                    "INSERT INTO receipt_line (receipt_id, position, label, article_id)"
                    " VALUES (?, 1, 'RIZ', ?)", (receipt, two["riz_article"]))
    assert delete_product(manager.db, two["riz"]) == "hidden"
    # Batches and receipt lines are the article's own history; the rest is
    # the product's, and leaves an article that never served free to go.
    article_history = history in ("closed_batch", "receipt_line")
    assert delete_article(manager.db, two["riz_article"]) == (
        "hidden" if article_history else "deleted")


def test_hiding_a_product_leaves_its_articles_untouched(manager, two):
    with manager.db.write() as conn:
        _batch(conn, two["riz_article"], two["frigo"], closed=True)
    delete_product(manager.db, two["riz"])
    assert _one(manager.db, "SELECT active FROM article WHERE id = ?",
                two["riz_article"])[0] == 1


def test_deleting_a_hidden_product_again_answers_hidden_and_writes_nothing(manager, two):
    with manager.db.write() as conn:
        _batch(conn, two["riz_article"], two["frigo"], closed=True)
    delete_product(manager.db, two["riz"])
    before = _dump(manager.db)
    assert delete_product(manager.db, two["riz"]) == "hidden"
    assert _dump(manager.db) == before


def test_an_article_that_never_served_is_erased_alone(manager, two):
    assert delete_article(manager.db, two["riz_article"]) == "deleted"
    assert _count(manager.db, "article", "id = ?", two["riz_article"]) == 0
    assert _count(manager.db, "barcode", "article_id = ?", two["riz_article"]) == 0
    assert _count(manager.db, "price", "article_id = ?", two["riz_article"]) == 0
    assert _count(manager.db, "packaging", "scope = 'article' AND target_id = ?",
                  two["riz_article"]) == 0
    # Its product and the product's own packaging stay.
    assert _count(manager.db, "product", "id = ?", two["riz"]) == 1
    assert _count(manager.db, "packaging", "scope = 'product' AND target_id = ?",
                  two["riz"]) == 1
    assert _count(manager.db, "article", "id = ?", two["lait_article"]) == 1


def test_hiding_the_last_article_leaves_the_product_visible(manager, two):
    with manager.db.write() as conn:
        _batch(conn, two["riz_article"], two["frigo"], closed=True)
    assert delete_article(manager.db, two["riz_article"]) == "hidden"
    assert _one(manager.db, "SELECT active FROM article WHERE id = ?",
                two["riz_article"])[0] == 0
    assert _one(manager.db, "SELECT active FROM product WHERE id = ?", two["riz"])[0] == 1


def test_unknown_ids_are_refused(manager, two):
    with pytest.raises(LookupError, match="^no product 999$"):
        delete_product(manager.db, 999)
    with pytest.raises(LookupError, match="^no article 999$"):
        delete_article(manager.db, 999)
    with pytest.raises(LookupError, match="^no article 999$"):
        set_article_active(manager.db, 999, True)


def test_restoring_an_article_of_a_hidden_product_restores_both(manager, two):
    with manager.db.write() as conn:
        _batch(conn, two["riz_article"], two["frigo"], closed=True)
    delete_article(manager.db, two["riz_article"])
    delete_product(manager.db, two["riz"])

    set_article_active(manager.db, two["riz_article"], True)

    assert _one(manager.db, "SELECT active FROM article WHERE id = ?",
                two["riz_article"])[0] == 1
    assert _one(manager.db, "SELECT active FROM product WHERE id = ?", two["riz"])[0] == 1
    assert _one(manager.db, "SELECT active FROM product WHERE id = ?", two["lait"])[0] == 1


def test_hiding_an_article_by_hand_leaves_its_product(manager, two):
    set_article_active(manager.db, two["riz_article"], False)
    assert _one(manager.db, "SELECT active FROM article WHERE id = ?",
                two["riz_article"])[0] == 0
    assert _one(manager.db, "SELECT active FROM product WHERE id = ?", two["riz"])[0] == 1


def test_a_product_hidden_by_hand_is_never_erased_by_a_delete(manager, two):
    """Already hidden answers hidden, even when nothing ever used it: the
    delete does not second-guess an earlier decision to keep it."""
    with manager.db.write() as conn:
        conn.execute("UPDATE product SET active = 0 WHERE id = ?", (two["riz"],))
        conn.execute("UPDATE article SET active = 0 WHERE id = ?", (two["lait_article"],))
    before = _dump(manager.db)
    assert delete_product(manager.db, two["riz"]) == "hidden"
    assert delete_article(manager.db, two["lait_article"]) == "hidden"
    assert _dump(manager.db) == before
