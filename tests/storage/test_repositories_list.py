"""La liste de courses au niveau du dépôt : lignes, revendications, récurrences.

Le dépôt ne décide rien — c'est `domain/shoppinglist.reconcile()` qui décide.
Deux responsabilités, deux couches.
"""
import sqlite3

import pytest

from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.migrations import apply_migrations


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    apply_migrations(connection)
    connection.execute("INSERT INTO location (id, name, kind) VALUES (1, 'Placard', 'pantry')")
    connection.execute(
        "INSERT INTO product (id, name, base_unit, aisle_id) VALUES "
        "(1, 'Pâtes', 'g', (SELECT id FROM aisle WHERE name = 'Épicerie salée')),"
        "(2, 'Yaourt', 'piece', (SELECT id FROM aisle WHERE name = 'Crémerie')),"
        "(3, 'Éponge', 'piece', NULL)"
    )
    connection.execute(
        "INSERT INTO article (id, product_id, label, is_generic) VALUES "
        "(1, 1, 'Panzani 500 g', 0), (2, 2, 'Nature x4', 0), (3, 1, 'Générique', 1)"
    )
    return connection


def _items(conn, **kwargs):
    return repo.list_items(conn, **kwargs)


def _add(conn, **fields):
    fields.setdefault("added_at", "2026-08-21T09:00:00")
    return repo.insert_list_item(conn, **fields)


# --- l'ordre ----------------------------------------------------------------

def test_the_list_falls_back_to_the_default_order_without_a_store(conn):
    """Aucun `store_id` : l'ordre par défaut du lot 1, inchangé."""
    _add(conn, product_id=3)                       # sans rayon → 999
    _add(conn, product_id=2)                       # Crémerie
    _add(conn, product_id=1)                       # Épicerie salée

    names = [row["product_name"] for row in _items(conn)]
    crem = repo.list_aisles(conn)
    order = {row["name"]: row["position"] for row in crem}
    assert names[-1] == "Éponge"
    assert order["Crémerie"] < order["Épicerie salée"] or names[0] == "Pâtes"


def test_the_list_is_ordered_by_the_store_route_when_there_is_one(conn):
    """`store_aisle.position` d'abord, `aisle.position` en repli, 999 pour
    un produit sans rayon."""
    store_id = repo.upsert_store(conn, name="Leclerc")
    aisles = {row["name"]: row["id"] for row in repo.list_aisles(conn)}
    # On inverse volontairement l'ordre par défaut des deux rayons.
    repo.set_store_aisle(conn, store_id=store_id, aisle_id=aisles["Épicerie salée"],
                         position=1, source="learned")
    repo.set_store_aisle(conn, store_id=store_id, aisle_id=aisles["Crémerie"],
                         position=2, source="learned")
    _add(conn, product_id=2)
    _add(conn, product_id=1)
    _add(conn, product_id=3)

    names = [row["product_name"] for row in _items(conn, store_id=store_id)]
    assert names == ["Pâtes", "Yaourt", "Éponge"]


def test_a_free_text_line_sorts_last_and_needs_no_product(conn):
    _add(conn, product_id=1)
    _add(conn, free_text="Piles télécommande salon")
    rows = _items(conn)
    assert rows[-1]["free_text"] == "Piles télécommande salon"
    assert rows[-1]["product_id"] is None


def test_the_list_carries_the_claims_of_each_line(conn):
    item_id = _add(conn, product_id=1)
    repo.set_claim(conn, item_id=item_id, origin="shortage", quantity=500.0,
                   detail="seuil 500", claimed_at="2026-08-21T09:00:00")
    repo.set_claim(conn, item_id=item_id, origin="meal_plan", quantity=300.0,
                   detail="Dîner de jeudi", claimed_at="2026-08-21T09:00:00")
    [row] = _items(conn)
    assert {claim["origin"] for claim in row["claims"]} == {"shortage", "meal_plan"}


# --- cocher, décocher, retirer ----------------------------------------------

def test_checking_an_item_records_who_checked_it(conn):
    """`session_id` et `line_id` : c'est le SCAN qui coche, et la ligne de
    panier doit rester retrouvable pour pouvoir décocher."""
    session_id = repo.open_session(conn, started_at="2026-08-21T09:00:00",
                                   store="Leclerc")
    line_id = repo.add_line(conn, session_id=session_id, article_id=1, quantity=500,
                            unit_price=None, scanned_at="2026-08-21T10:00:00",
                            idempotency_key=None)
    item_id = _add(conn, product_id=1)

    repo.check_list_item(conn, item_id, at="2026-08-21T10:00:00",
                         session_id=session_id, line_id=line_id)

    [row] = _items(conn)
    assert row["checked_at"] == "2026-08-21T10:00:00"
    assert row["session_id"] == session_id and row["line_id"] == line_id


def test_unchecking_clears_the_three_columns_together(conn):
    """Sinon un item décoché garderait un `line_id` mort, et le décochage
    suivant viserait une ligne qui n'existe plus."""
    session_id = repo.open_session(conn, started_at="2026-08-21T09:00:00", store=None)
    line_id = repo.add_line(conn, session_id=session_id, article_id=1, quantity=500,
                            unit_price=None, scanned_at="2026-08-21T10:00:00",
                            idempotency_key=None)
    item_id = _add(conn, product_id=1)
    repo.check_list_item(conn, item_id, at="2026-08-21T10:00:00",
                         session_id=session_id, line_id=line_id)

    repo.uncheck_list_item(conn, item_id)

    [row] = _items(conn)
    assert (row["checked_at"], row["session_id"], row["line_id"]) == (None, None, None)


def test_removing_is_a_timestamp_never_a_delete(conn):
    """La réconciliation doit se SOUVENIR qu'on n'en veut pas."""
    item_id = _add(conn, product_id=1)
    repo.remove_list_item(conn, item_id, at="2026-08-21T11:00:00")

    assert _items(conn) == []
    row = conn.execute("SELECT * FROM shopping_list_item WHERE id = ?",
                       (item_id,)).fetchone()
    assert row["removed_at"] == "2026-08-21T11:00:00"


def test_purging_is_the_only_delete_and_takes_the_claims_with_it(conn):
    item_id = _add(conn, product_id=1)
    repo.set_claim(conn, item_id=item_id, origin="shortage", quantity=None,
                   detail=None, claimed_at="2026-08-21T09:00:00")
    repo.purge_list_item(conn, item_id)
    assert conn.execute("SELECT COUNT(*) AS n FROM shopping_list_item"
                        ).fetchone()["n"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM shopping_list_claim"
                        ).fetchone()["n"] == 0


def test_open_item_for_product_sees_only_the_open_one(conn):
    item_id = _add(conn, product_id=1)
    assert repo.open_item_for_product(conn, 1)["id"] == item_id
    repo.remove_list_item(conn, item_id, at="2026-08-21T11:00:00")
    assert repo.open_item_for_product(conn, 1) is None


def test_include_checked_false_hides_what_is_in_the_cart(conn):
    item_id = _add(conn, product_id=1)
    _add(conn, product_id=2)
    repo.check_list_item(conn, item_id, at="2026-08-21T10:00:00",
                         session_id=None, line_id=None)
    assert len(_items(conn)) == 2
    assert len(_items(conn, include_checked=False)) == 1


# --- les revendications -----------------------------------------------------

def test_a_claim_is_upserted_per_origin(conn):
    """Deux passages de la même origine mettent à jour, n'empilent pas."""
    item_id = _add(conn, product_id=1)
    repo.set_claim(conn, item_id=item_id, origin="shortage", quantity=500.0,
                   detail="seuil 500", claimed_at="2026-08-21T09:00:00")
    repo.set_claim(conn, item_id=item_id, origin="shortage", quantity=200.0,
                   detail="seuil 500", claimed_at="2026-08-21T09:15:00")

    claims = repo.claims_of(conn, item_id)
    assert len(claims) == 1
    assert claims[0]["quantity"] == pytest.approx(200.0)
    assert claims[0]["claimed_at"] == "2026-08-21T09:15:00"


def test_dropping_the_last_claim_leaves_the_item_intact(conn):
    """Le dépôt ne décide rien : c'est `reconcile()` qui décide, le dépôt
    exécute. Deux responsabilités, deux couches."""
    item_id = _add(conn, product_id=1)
    repo.set_claim(conn, item_id=item_id, origin="shortage", quantity=None,
                   detail=None, claimed_at="2026-08-21T09:00:00")
    repo.drop_claim(conn, item_id=item_id, origin="shortage")

    assert repo.claims_of(conn, item_id) == []
    assert len(_items(conn)) == 1


def test_deleting_an_item_takes_its_claims_with_it(conn):
    """`ON DELETE CASCADE` sur les revendications."""
    item_id = _add(conn, product_id=1)
    repo.set_claim(conn, item_id=item_id, origin="manual", quantity=None,
                   detail=None, claimed_at="2026-08-21T09:00:00")
    conn.execute("DELETE FROM shopping_list_item WHERE id = ?", (item_id,))
    assert conn.execute("SELECT COUNT(*) AS n FROM shopping_list_claim"
                        ).fetchone()["n"] == 0


# --- les récurrences --------------------------------------------------------

@pytest.mark.parametrize("last_added_on, due", [
    (None, True),                       # jamais ajoutée
    ("2026-08-16", False),              # il y a 5 jours, tous les 7
    ("2026-08-14", True),               # il y a exactement 7 jours
    ("2026-08-01", True),               # largement en retard
])
def test_due_recurring_uses_last_added_on_plus_every_days(conn, last_added_on, due):
    """Jamais ajoutée → due. Ajoutée il y a `every_days − 1` → pas due.
    Ajoutée il y a exactement `every_days` → due. Les trois."""
    repo.upsert_recurring(conn, product_id=1, quantity=500.0, every_days=7,
                          last_added_on=last_added_on)
    assert bool(repo.due_recurring(conn, "2026-08-21")) is due


def test_an_inactive_recurring_line_is_never_due(conn):
    recurring_id = repo.upsert_recurring(conn, product_id=1, quantity=None,
                                         every_days=1)
    assert repo.due_recurring(conn, "2026-08-21")
    repo.upsert_recurring(conn, recurring_id=recurring_id, product_id=1,
                          quantity=None, every_days=1, active=0)
    assert repo.due_recurring(conn, "2026-08-21") == []
    assert repo.list_recurring(conn) == []
    assert len(repo.list_recurring(conn, active_only=False)) == 1


def test_marking_a_recurring_added_pushes_it_back(conn):
    recurring_id = repo.upsert_recurring(conn, product_id=1, quantity=None,
                                         every_days=7)
    repo.mark_recurring_added(conn, recurring_id, "2026-08-21")
    assert repo.due_recurring(conn, "2026-08-21") == []
    assert repo.due_recurring(conn, "2026-08-28")


def test_deleting_a_recurring_line_removes_it(conn):
    recurring_id = repo.upsert_recurring(conn, free_text="Sacs poubelle",
                                         quantity=None, every_days=30)
    repo.delete_recurring(conn, recurring_id)
    assert repo.list_recurring(conn, active_only=False) == []


# --- l'estimation -----------------------------------------------------------

def test_list_estimate_rows_prefers_the_last_bought_article(conn):
    """« ça va faire combien ? » se répond avec l'article qu'on achète
    d'habitude, pas avec le moins cher du catalogue."""
    repo.insert_batch(conn, article_id=1, location_id=1, quantity=500,
                      entered_at="2026-08-10T10:00:00", price_per_base_unit=0.004)
    repo.insert_price(conn, article_id=1, observed_on="2026-08-10",
                      price_per_base_unit=0.004, source="manual", store="Leclerc")
    repo.insert_price(conn, article_id=3, observed_on="2026-08-20",
                      price_per_base_unit=0.001, source="manual", store="Leclerc")
    item_id = _add(conn, product_id=1, quantity=1000.0)

    [row] = repo.list_estimate_rows(conn)

    assert row["item_id"] == item_id
    assert row["article_id"] == 1
    assert row["price_per_base_unit"] == pytest.approx(0.004)
    assert row["estimate"] == pytest.approx(4.0)


def test_list_estimate_rows_reports_lines_it_could_not_price(conn):
    """C'est ce qui alimente `confidence` : la proportion de lignes
    réellement chiffrées, dite en clair plutôt que noyée dans un total."""
    repo.insert_batch(conn, article_id=1, location_id=1, quantity=500,
                      entered_at="2026-08-10T10:00:00", price_per_base_unit=0.004)
    repo.insert_price(conn, article_id=1, observed_on="2026-08-10",
                      price_per_base_unit=0.004, source="manual", store=None)
    _add(conn, product_id=1, quantity=1000.0)
    _add(conn, product_id=2, quantity=4.0)
    _add(conn, free_text="Piles")

    rows = repo.list_estimate_rows(conn)

    priced = [row for row in rows if row["estimate"] is not None]
    assert len(rows) == 3 and len(priced) == 1


def test_a_line_without_a_quantity_is_estimated_on_one_package(conn):
    """« ce qu'il faut » n'est pas « rien » : sans quantité, on estime un
    conditionnement — sinon le total afficherait moins que la réalité et
    personne ne s'en méfierait."""
    conn.execute("UPDATE article SET net_quantity = 500 WHERE id = 1")
    repo.insert_batch(conn, article_id=1, location_id=1, quantity=500,
                      entered_at="2026-08-10T10:00:00", price_per_base_unit=0.004)
    repo.insert_price(conn, article_id=1, observed_on="2026-08-10",
                      price_per_base_unit=0.004, source="manual", store=None)
    _add(conn, product_id=1)

    [row] = repo.list_estimate_rows(conn)
    assert row["estimate"] == pytest.approx(2.0)
