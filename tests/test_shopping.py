"""The shopping session, end to end, without Home Assistant."""
import sqlite3

import pytest

from custom_components.home_stock import application as application_module
from custom_components.home_stock import shopping as shopping_module
from custom_components.home_stock.application import StockManager
from custom_components.home_stock.shopping import ShoppingError, ShoppingService
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations


@pytest.fixture
def service(tmp_path) -> ShoppingService:
    database = Database(str(tmp_path / "home_stock.db"))
    database.connect()
    with database.write() as conn:
        apply_migrations(conn)
        conn.execute("INSERT INTO location (id, name, kind) VALUES (1, 'Placard', 'pantry')")
        conn.execute(
            "INSERT INTO product (id, name, base_unit, default_location_id, "
            "aisle_id) VALUES (1, 'Pâtes', 'g', 1, "
            "(SELECT id FROM aisle WHERE name = 'Épicerie salée'))"
        )
        conn.execute(
            "INSERT INTO article (id, product_id, label, net_quantity) "
            "VALUES (10, 1, 'Panzani 500 g', 500)"
        )
    return ShoppingService(StockManager(database))


def test_a_session_starts_and_is_the_current_one(service):
    service.start(store="Leclerc")

    current = service.current()
    assert current["session"]["state"] == "shopping"
    assert current["session"]["store"] == "Leclerc"
    assert current["lines"] == []


def test_only_one_session_can_be_open(service):
    service.start(store="Leclerc")

    with pytest.raises(ShoppingError, match="déjà"):
        service.start(store="Lidl")


def test_scanning_adds_a_line_and_records_the_price_observed(service):
    service.start(store="Leclerc")

    service.add_line(article_id=10, quantity=500, unit_price=0.002, idempotency_key="a")

    with service.manager.db.write() as conn:
        row = conn.execute("SELECT store, source, price_per_base_unit FROM price").fetchone()
    assert (row["store"], row["source"]) == ("Leclerc", "manual")
    assert row["price_per_base_unit"] == pytest.approx(0.002)


def test_a_line_with_no_price_records_no_price(service):
    service.start(store="Leclerc")
    service.add_line(article_id=10, quantity=500, unit_price=None, idempotency_key="a")

    with service.manager.db.write() as conn:
        assert conn.execute("SELECT COUNT(*) FROM price").fetchone()[0] == 0


def test_replaying_the_same_scan_adds_nothing(service):
    """The offline queue replays. Two identical keys are one packet of pasta."""
    service.start(store="Leclerc")
    first = service.add_line(article_id=10, quantity=500, unit_price=0.002,
                             idempotency_key="scan-1")
    again = service.add_line(article_id=10, quantity=500, unit_price=0.002,
                             idempotency_key="scan-1")

    assert first["id"] == again["id"]
    assert len(service.current()["lines"]) == 1


def test_the_running_total_is_what_the_cart_costs(service):
    service.start(store="Leclerc")
    service.add_line(article_id=10, quantity=500, unit_price=0.002, idempotency_key="a")
    service.add_line(article_id=10, quantity=1000, unit_price=0.002, idempotency_key="b")

    assert service.current()["totals"]["total"] == pytest.approx(3.0)


def test_scanning_outside_a_session_is_refused(service):
    with pytest.raises(ShoppingError, match="aucune session"):
        service.add_line(article_id=10, quantity=500, unit_price=None, idempotency_key="a")


def test_checkout_moves_the_session_to_put_away(service):
    service.start(store="Leclerc")
    service.add_line(article_id=10, quantity=500, unit_price=0.002, idempotency_key="a")

    service.checkout()

    assert service.current()["session"]["state"] == "to_store"


def test_storing_a_line_creates_the_batch_and_writes_the_purchase(service):
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=0.002,
                            idempotency_key="a")
    service.checkout()

    result = service.store_line(line["id"], location_id=1, best_before="2027-01-01")

    with service.manager.db.write() as conn:
        batch = conn.execute("SELECT * FROM batch WHERE id = ?",
                             (result["batch_id"],)).fetchone()
        movement = conn.execute(
            "SELECT reason, quantity, base_unit FROM movement").fetchone()
    assert batch["remaining"] == pytest.approx(500.0)
    assert batch["best_before"] == "2027-01-01"
    assert batch["price_per_base_unit"] == pytest.approx(0.002)
    assert (movement["reason"], movement["quantity"], movement["base_unit"]) == (
        "purchase", 500.0, "g")


def test_storing_a_line_twice_creates_one_batch(service):
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            idempotency_key="a")
    service.checkout()

    first = service.store_line(line["id"], location_id=1, best_before=None)
    again = service.store_line(line["id"], location_id=1, best_before=None)

    assert first["batch_id"] == again["batch_id"]
    with service.manager.db.write() as conn:
        assert conn.execute("SELECT COUNT(*) FROM batch").fetchone()[0] == 1


def test_a_stored_line_can_no_longer_be_removed(service):
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            idempotency_key="a")
    service.checkout()
    service.store_line(line["id"], location_id=1, best_before=None)

    with pytest.raises(ShoppingError, match="rangée"):
        service.remove_line(line["id"])


def test_an_unstored_line_disappears_without_touching_the_stock(service):
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            idempotency_key="a")

    service.remove_line(line["id"])

    assert service.current()["lines"] == []
    with service.manager.db.write() as conn:
        assert conn.execute("SELECT COUNT(*) FROM movement").fetchone()[0] == 0


def test_storing_the_last_line_closes_the_session(service):
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            idempotency_key="a")
    service.checkout()

    service.store_line(line["id"], location_id=1, best_before=None)

    assert service.current() is None


def test_a_shelf_life_is_learned_from_what_was_actually_posed(service, monkeypatch):
    """The median of the last three, not the last one — pinned independently
    of the day this test happens to run.

    entered_at (read back by recent_shelf_lives) comes from
    application._now(), used inside StockManager.add_stock; scanned_at and
    stored_at come from shopping._now(). Both module-level clocks are frozen
    here — patching only one would leave the batch's entered_at floating on
    the real date, and the fix round exists precisely because that happened.
    """
    frozen_now = "2026-01-01T10:00:00"
    monkeypatch.setattr(shopping_module, "_now", lambda: frozen_now)
    monkeypatch.setattr(application_module, "_now", lambda: frozen_now)

    service.start(store="Leclerc")
    # entered_at is pinned to 2026-01-01. Offsets to best_before are the same
    # {13, 15, 14} days as the original test, stored out of date order so the
    # *last* line posed does not carry the middle offset.
    for index, best_before in enumerate(["2026-01-14", "2026-01-16", "2026-01-15"]):
        line = service.add_line(article_id=10, quantity=500, unit_price=None,
                                idempotency_key=f"a{index}")
        service.store_line(line["id"], location_id=1, best_before=best_before)

    with service.manager.db.write() as conn:
        row = conn.execute(
            "SELECT default_shelf_life_days FROM product WHERE id = 1").fetchone()
    # Median of {13, 15, 14} sorted -> {13, 14, 15} is 14 (2026-01-15, the
    # middle date entered) — not 15 (2026-01-16, the last one stored). This
    # literal is hand-computed, not re-derived with the production code's own
    # julianday/median arithmetic: doing that would only prove the code
    # agrees with itself.
    assert row["default_shelf_life_days"] == 14


def test_storing_a_priced_line_writes_exactly_one_price_row(service):
    """The observation happens once, in the aisle, with its shop.

    Regression for the fix round: add_stock used to insert a second,
    unconditional price row at put-away time, stamped with store=None,
    silently doubling every priced line in the price history that feeds the
    suggestion cascade. Asserting the count, not just presence, is the point.
    """
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=0.002,
                            idempotency_key="a")
    service.checkout()

    service.store_line(line["id"], location_id=1, best_before=None)

    with service.manager.db.write() as conn:
        rows = conn.execute("SELECT store, source FROM price").fetchall()
    assert len(rows) == 1
    assert (rows[0]["store"], rows[0]["source"]) == ("Leclerc", "manual")


def test_update_line_refuses_a_stored_line_and_writes_only_the_given_field(service):
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=0.002,
                            idempotency_key="a")

    updated = service.update_line(line["id"], quantity=750)

    assert updated["quantity"] == pytest.approx(750)
    assert updated["unit_price"] == pytest.approx(0.002)  # untouched by the update

    service.checkout()
    service.store_line(line["id"], location_id=1, best_before=None)

    with pytest.raises(ShoppingError, match="rangée"):
        service.update_line(line["id"], quantity=1000)


def test_close_moves_an_open_session_to_done_and_stamps_closed_at(service):
    service.start(store="Leclerc")

    result = service.close()

    assert result["state"] == "done"
    assert result["closed_at"] is not None
    assert service.current() is None


def test_close_without_a_session_is_refused(service):
    with pytest.raises(ShoppingError):
        service.close()


# --- amendement A3 : d'où vient le prix d'une ligne -------------------------

def _prices(service):
    return service.manager.db.read().execute(
        "SELECT * FROM price ORDER BY id").fetchall()


def test_a_price_accepted_without_being_touched_is_written_as_open_prices(service):
    """Le coeur de A3 : `price_source='open_prices'` en entrée produit une
    observation `price` de source `open_prices`, pas `manual`."""
    service.start(store="Leclerc")
    service.add_line(article_id=10, quantity=500, unit_price=0.004,
                     price_source="open_prices", idempotency_key=None)
    [observation] = _prices(service)
    assert observation["source"] == "open_prices"
    assert observation["store"] == "Leclerc"


def test_a_price_typed_by_a_human_is_written_as_manual(service):
    """Et le rang 1 de la cascade lui appartient."""
    service.start(store="Leclerc")
    service.add_line(article_id=10, quantity=500, unit_price=0.004,
                     price_source="manual", idempotency_key=None)
    [observation] = _prices(service)
    assert observation["source"] == "manual"


def test_an_absent_price_source_defaults_to_manual(service):
    """Compatibilité : un appelant qui ne dit rien décrit un prix tapé —
    c'est ce que faisait le lot 1, et c'est le choix qui ne perd rien."""
    service.start(store="Leclerc")
    service.add_line(article_id=10, quantity=500, unit_price=0.004,
                     idempotency_key=None)
    [observation] = _prices(service)
    assert observation["source"] == "manual"


def test_correcting_a_price_at_the_till_always_writes_manual(service):
    """`update_line` avec une valeur DIFFÉRENTE est une saisie humaine, quelle
    que soit la source annoncée : on vient de la corriger devant l'étiquette."""
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=0.004,
                            price_source="open_prices", idempotency_key=None)
    service.update_line(line["id"], unit_price=0.006, price_source="open_prices")
    assert [row["source"] for row in _prices(service)] == ["open_prices", "manual"]


def test_the_shopping_line_remembers_where_its_price_came_from(service):
    """`shopping_line.price_source` est écrite, et relue par le panier."""
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=0.004,
                            price_source="open_prices", idempotency_key=None)
    assert line["price_source"] == "open_prices"
    updated = service.update_line(line["id"], unit_price=0.006)
    assert updated["price_source"] == "manual"


def test_a_line_without_a_price_records_no_observation_and_no_source(service):
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            price_source="open_prices", idempotency_key=None)
    assert _prices(service) == []
    assert line["price_source"] is None


# --- amendement A4 : le magasin promu en table ------------------------------

def _stores(service, **kwargs):
    from custom_components.home_stock.storage import repositories as repo
    return repo.list_stores(service.manager.db.read(), **kwargs)


def test_starting_a_session_by_name_creates_the_store_once(service):
    """Deux voyages « Leclerc » = un seul magasin, deux sessions observées."""
    first = service.start(store="Leclerc")
    service.close()
    second = service.start(store="Leclerc")
    service.close()

    assert first["store_id"] == second["store_id"]
    [store] = _stores(service)
    assert store["name"] == "Leclerc"
    assert store["observed_sessions"] == 2


def test_starting_a_session_by_id_ignores_the_name(service):
    """`store_id` prime : le panneau envoie une pastille, pas une chaîne."""
    opened = service.start(store="Leclerc")
    service.close()
    again = service.start(store="n'importe quoi", store_id=opened["store_id"])

    assert again["store_id"] == opened["store_id"]
    assert again["store"] == "Leclerc"
    assert len(_stores(service)) == 1


def test_starting_a_session_without_a_store_creates_none(service):
    opened = service.start(store=None)
    assert opened["store_id"] is None
    assert _stores(service) == []


def test_the_session_keeps_the_free_text_of_the_store_it_was_given(service):
    opened = service.start(store="  Leclerc  ")
    assert opened["store"] == "Leclerc"
    assert _stores(service)[0]["name"] == "Leclerc"


def test_merging_a_store_with_an_open_session_is_refused(service):
    """« On ne déplace pas le sol sous une session. » Message français."""
    from custom_components.home_stock.storage import repositories as repo
    opened = service.start(store="Leclerc")
    with service.manager.db.write() as conn:
        other = repo.upsert_store(conn, name="E.Leclerc")

    with pytest.raises(ShoppingError, match="en cours"):
        service.merge_stores(keep_id=opened["store_id"], merge_id=other)
    with pytest.raises(ShoppingError, match="en cours"):
        service.merge_stores(keep_id=other, merge_id=opened["store_id"])


def test_merging_two_closed_stores_goes_through(service):
    from custom_components.home_stock.storage import repositories as repo
    opened = service.start(store="Leclerc")
    service.close()
    with service.manager.db.write() as conn:
        other = repo.upsert_store(conn, name="E.Leclerc")

    result = service.merge_stores(keep_id=opened["store_id"], merge_id=other)

    assert result["keep_id"] == opened["store_id"]
    assert len(_stores(service)) == 1


# --- § 8 : le pointage au scan ----------------------------------------------

def _list_item(service, **fields):
    from custom_components.home_stock.storage import repositories as repo
    fields.setdefault("added_at", "2026-08-21T09:00:00")
    with service.manager.db.write() as conn:
        item_id = repo.insert_list_item(conn, **fields)
        repo.set_claim(conn, item_id=item_id, origin="shortage", quantity=None,
                       detail="sous le seuil", claimed_at="2026-08-21T09:00:00")
    return item_id


def _item(service, item_id):
    from custom_components.home_stock.storage import repositories as repo
    return repo.get_list_item(service.manager.db.read(), item_id)


def test_scanning_a_listed_product_checks_its_line(service):
    item_id = _list_item(service, product_id=1)
    service.start(store="Leclerc")

    service.add_line(article_id=10, quantity=500, unit_price=None,
                     idempotency_key=None)

    assert _item(service, item_id)["checked_at"] is not None


def test_the_check_records_the_session_and_the_line(service):
    item_id = _list_item(service, product_id=1)
    session = service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            idempotency_key=None)

    row = _item(service, item_id)
    assert row["session_id"] == session["id"]
    assert row["line_id"] == line["id"]


def test_scanning_an_article_of_another_brand_still_checks_the_product_line(service):
    """Un article inconnu créé au scan et rattaché à « Pâtes » coche la ligne
    « Pâtes » sans rien de plus : la liste dit « des pâtes », le rayon
    propose un paquet de telle marque."""
    from custom_components.home_stock.storage import repositories as repo
    item_id = _list_item(service, product_id=1)
    with service.manager.db.write() as conn:
        other = repo.insert_article(conn, product_id=1, label="Barilla 500 g")
    service.start(store="Leclerc")

    service.add_line(article_id=other, quantity=500, unit_price=None,
                     idempotency_key=None)

    assert _item(service, item_id)["checked_at"] is not None


def test_scanning_something_not_on_the_list_does_nothing_at_all(service):
    """Acheter ce qu'on n'avait pas prévu est le comportement normal d'un
    être humain dans un magasin, pas une anomalie à signaler."""
    from custom_components.home_stock.storage import repositories as repo
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            idempotency_key=None)
    assert line["id"]
    assert repo.list_items(service.manager.db.read()) == []


def test_removing_a_line_unchecks_what_it_had_checked(service):
    """Retirer une ligne du panier, c'est reposer l'article sur l'étagère."""
    item_id = _list_item(service, product_id=1)
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            idempotency_key=None)

    service.remove_line(line["id"])

    row = _item(service, item_id)
    assert (row["checked_at"], row["session_id"], row["line_id"]) == (None, None, None)


def test_update_line_touches_nothing(service):
    item_id = _list_item(service, product_id=1)
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            idempotency_key=None)
    before = _item(service, item_id)["checked_at"]

    service.update_line(line["id"], quantity=1000)

    assert _item(service, item_id)["checked_at"] == before


def test_a_stored_line_no_longer_unchecks(service):
    """`remove_line` y est déjà refusé par le lot 1 (« corrigez le lot, pas
    la liste ») ; l'item est purgé ou recréé par la réconciliation."""
    item_id = _list_item(service, product_id=1)
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            idempotency_key=None)
    service.checkout()
    service.store_line(line["id"], location_id=1, best_before=None)

    with pytest.raises(ShoppingError, match="corrigez le lot"):
        service.remove_line(line["id"])
    assert _item(service, item_id)["checked_at"] is not None


def test_a_replayed_add_line_does_not_check_twice(service):
    """`add_line` rejoué avec la même clé rend la ligne DÉJÀ créée sans rien
    réécrire, donc sans re-cocher."""
    item_id = _list_item(service, product_id=1)
    service.start(store="Leclerc")
    service.add_line(article_id=10, quantity=500, unit_price=None,
                     idempotency_key="scan-1")
    first = _item(service, item_id)["checked_at"]
    service.uncheck_line_items = None            # rien à désactiver : on rejoue
    service.add_line(article_id=10, quantity=500, unit_price=None,
                     idempotency_key="scan-1")

    assert _item(service, item_id)["checked_at"] == first


def test_a_remove_replayed_after_an_add_leaves_the_item_unchecked(service):
    """La file hors ligne rejoue DANS L'ORDRE : décoche après avoir coché,
    et l'état final est le bon."""
    item_id = _list_item(service, product_id=1)
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            idempotency_key="scan-1")
    service.remove_line(line["id"])
    service.add_line(article_id=10, quantity=500, unit_price=None,
                     idempotency_key="scan-1")

    assert _item(service, item_id)["checked_at"] is not None


def test_a_failing_check_never_blocks_the_cart_line(service, monkeypatch):
    """Le pointage n'est jamais une condition du scan : ce qui est accessoire
    ne bloque jamais ce qui est essentiel."""
    from custom_components.home_stock.storage import repositories as repo
    _list_item(service, product_id=1)
    service.start(store="Leclerc")

    def _boom(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(repo, "check_list_item", _boom)
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            idempotency_key=None)

    assert line["id"]
    assert service.current()["lines"][0]["id"] == line["id"]


def test_checking_needs_no_open_session(service):
    """On coche une liste chez soi aussi : c'est le websocket `list/check`
    qui le permet, pas le scan."""
    item_id = _list_item(service, product_id=1)
    service.manager.check_list_item(item_id, at="2026-08-21T09:30:00")
    assert _item(service, item_id)["checked_at"] == "2026-08-21T09:30:00"
    assert _item(service, item_id)["session_id"] is None


# --- § 11 : apprendre le parcours à la clôture ------------------------------

def _walk(service, *, store="Leclerc", articles=(10,), close=True):
    from custom_components.home_stock.storage import repositories as repo
    session = service.start(store=store)
    for article_id in articles:
        service.add_line(article_id=article_id, quantity=1, unit_price=None,
                         idempotency_key=None)
    if close:
        service.checkout()
        service.close()
    return session


def _second_product(service):
    from custom_components.home_stock.storage import repositories as repo
    with service.manager.db.write() as conn:
        product_id = repo.insert_product(
            conn, name="Yaourt", base_unit="piece",
            aisle_id=(select := conn.execute(
                "SELECT id FROM aisle WHERE name = 'Crémerie'").fetchone())["id"])
        return repo.insert_article(conn, product_id=product_id, label="Nature x4")


def test_closing_a_session_recalculates_the_route(service):
    from custom_components.home_stock.storage import repositories as repo
    other = _second_product(service)
    _walk(service, articles=(other, 10))

    conn = service.manager.db.read()
    store_id = repo.find_store_by_name(conn, "Leclerc")["id"]
    route = {row["aisle_name"]: row for row in repo.store_route(conn, store_id)}
    assert route["Crémerie"]["observed_sessions"] == 1
    assert route["Crémerie"]["mean_rank"] == pytest.approx(0.0)
    assert route["Épicerie salée"]["mean_rank"] == pytest.approx(1.0)
    # Un seul voyage : les rangs sont ENREGISTRÉS mais ne déplacent encore
    # rien — un rayon vu une fois garde sa place par défaut (§ 11.3).
    assert route["Crémerie"]["position"] > route["Fruits et légumes"]["position"]


def test_scanning_does_not_recalculate_anything(service):
    from custom_components.home_stock.storage import repositories as repo
    other = _second_product(service)
    _walk(service, articles=(other, 10), close=False)

    conn = service.manager.db.read()
    store_id = repo.find_store_by_name(conn, "Leclerc")["id"]
    assert repo.store_aisles(conn, store_id) == []


def test_the_cart_is_sorted_by_the_store_route_once_it_is_reliable(service):
    from custom_components.home_stock.storage import repositories as repo
    other = _second_product(service)
    for _ in range(3):
        _walk(service, articles=(other, 10))

    session = _walk(service, articles=(10, other), close=False)
    lines = repo.list_lines(service.manager.db.read(), session["id"])

    assert [row["aisle_name"] for row in lines] == ["Crémerie", "Épicerie salée"]


def test_the_cart_keeps_the_default_order_below_three_sessions(service):
    """`store_aisle` est REMPLI et visible ; seul l'affichage attend."""
    from custom_components.home_stock.storage import repositories as repo
    other = _second_product(service)
    for _ in range(2):
        _walk(service, articles=(other, 10))

    conn = service.manager.db.read()
    store_id = repo.find_store_by_name(conn, "Leclerc")["id"]
    assert repo.store_aisles(conn, store_id)          # rempli

    session = _walk(service, articles=(10, other), close=False)
    lines = repo.list_lines(service.manager.db.read(), session["id"])
    default_order = [row["name"] for row in repo.list_aisles(conn)]
    assert default_order.index(lines[0]["aisle_name"]) < \
        default_order.index(lines[1]["aisle_name"])


def test_a_pinned_aisle_survives_the_next_close(service):
    from custom_components.home_stock.storage import repositories as repo
    other = _second_product(service)
    _walk(service, articles=(other, 10))
    conn = service.manager.db.read()
    store_id = repo.find_store_by_name(conn, "Leclerc")["id"]
    aisles = {row["name"]: row["id"] for row in repo.list_aisles(conn)}
    with service.manager.db.write() as write:
        repo.pin_store_aisles(write, store_id,
                              [aisles["Épicerie salée"], aisles["Crémerie"]])

    _walk(service, articles=(other, 10))

    rows = {row["aisle_id"]: row for row in
            repo.store_aisles(service.manager.db.read(), store_id)}
    assert rows[aisles["Épicerie salée"]]["position"] == 1
    assert rows[aisles["Épicerie salée"]]["source"] == "manual"


def test_unpinning_gives_the_line_back_to_learning(service):
    from custom_components.home_stock.storage import repositories as repo
    other = _second_product(service)
    _walk(service, articles=(other, 10))
    conn = service.manager.db.read()
    store_id = repo.find_store_by_name(conn, "Leclerc")["id"]
    aisles = {row["name"]: row["id"] for row in repo.list_aisles(conn)}
    with service.manager.db.write() as write:
        repo.pin_store_aisles(write, store_id, [aisles["Épicerie salée"]])
        repo.unpin_store_aisle(write, store_id, aisles["Épicerie salée"])

    _walk(service, articles=(other, 10))

    rows = {row["aisle_id"]: row for row in
            repo.store_aisles(service.manager.db.read(), store_id)}
    assert rows[aisles["Crémerie"]]["position"] == 1


def test_a_session_with_no_store_learns_nothing_and_raises_nothing(service):
    from custom_components.home_stock.storage import repositories as repo
    other = _second_product(service)
    _walk(service, store=None, articles=(other, 10))
    assert repo.list_stores(service.manager.db.read()) == []


def test_learning_runs_inside_the_close_transaction(service):
    """Avec `--timeout=60` : un `db.write()` imbriqué figerait la clôture
    d'une session en plein magasin, sans exception et sans trace."""
    other = _second_product(service)
    _walk(service, articles=(other, 10))
    assert service.current() is None


def test_the_put_away_screen_is_not_sorted_by_aisle(service):
    """Garde-fou explicite : le rangement groupe par emplacement dans la
    MAISON. Un test l'épingle pour que personne ne « corrige » ça."""
    import inspect

    from custom_components.home_stock import websocket_api
    source = inspect.getsource(websocket_api)
    assert "store_aisle" not in source
