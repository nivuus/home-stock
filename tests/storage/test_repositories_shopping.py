"""The shopping session repositories, on a real migrated database."""
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
        "(2, 'Yaourt', 'piece', (SELECT id FROM aisle WHERE name = 'Crémerie'))"
    )
    connection.execute(
        "INSERT INTO article (id, product_id, label) VALUES (1, 1, 'Panzani 500 g'),"
        "(2, 2, 'Nature x4')"
    )
    return connection


def test_a_session_opens_and_is_found_again(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store="Leclerc")

    current = repo.current_session(conn)
    assert current["id"] == session_id
    assert current["store"] == "Leclerc"
    assert current["state"] == "shopping"


def test_current_session_prefers_the_oldest_queued_trip(conn):
    """Among sessions waiting to be put away, the older one is the backlog to
    clear first — its chilled items have been out of a fridge the longest —
    even if a quicker, later trip was already checked out. An open shopping
    session still always wins over any of them."""
    older_id = repo.open_session(conn, started_at="2026-08-19T09:00:00", store=None)
    repo.set_session_state(conn, older_id, "to_store", closed_at="2026-08-19T09:30:00")

    newer_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
    repo.set_session_state(conn, newer_id, "to_store", closed_at="2026-08-19T10:15:00")

    current = repo.current_session(conn)
    assert current["id"] == older_id

    shopping_id = repo.open_session(conn, started_at="2026-08-19T11:00:00", store=None)

    current = repo.current_session(conn)
    assert current["id"] == shopping_id


def test_get_session_returns_none_for_an_unknown_id(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)

    assert repo.get_session(conn, session_id)["id"] == session_id
    assert repo.get_session(conn, session_id + 999) is None


def test_set_session_state_never_wipes_closed_at_as_a_side_effect(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)

    repo.set_session_state(conn, session_id, "to_store")
    assert repo.get_session(conn, session_id)["closed_at"] is None

    repo.set_session_state(conn, session_id, "done", closed_at="2026-08-19T12:00:00")
    assert repo.get_session(conn, session_id)["closed_at"] == "2026-08-19T12:00:00"

    # Regression test: a later state write with no closed_at must not erase
    # the timestamp already recorded above.
    repo.set_session_state(conn, session_id, "done")
    assert repo.get_session(conn, session_id)["closed_at"] == "2026-08-19T12:00:00"


def test_update_line_only_writes_the_field_actually_passed(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
    line_id = repo.add_line(conn, session_id=session_id, article_id=1, quantity=500,
                            unit_price=0.002, scanned_at="2026-08-19T10:05:00",
                            idempotency_key="a")

    repo.update_line(conn, line_id, quantity=600)
    line = repo.list_lines(conn, session_id)[0]
    assert line["quantity"] == 600
    assert line["unit_price"] == pytest.approx(0.002)

    repo.update_line(conn, line_id, unit_price=0.0025)
    line = repo.list_lines(conn, session_id)[0]
    assert line["quantity"] == 600
    assert line["unit_price"] == pytest.approx(0.0025)


def test_remove_line_drops_only_that_line(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
    line_id = repo.add_line(conn, session_id=session_id, article_id=1, quantity=500,
                            unit_price=0.002, scanned_at="2026-08-19T10:05:00",
                            idempotency_key="a")
    other_id = repo.add_line(conn, session_id=session_id, article_id=2, quantity=4,
                             unit_price=0.35, scanned_at="2026-08-19T10:06:00",
                             idempotency_key="b")

    repo.remove_line(conn, line_id)

    remaining = repo.list_lines(conn, session_id)
    assert [line["id"] for line in remaining] == [other_id]


def test_session_totals_on_an_empty_session(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)

    totals = repo.session_totals(conn, session_id)

    assert {key: totals[key] for key in ("lines", "pending", "total")} == {
        "lines": 0, "pending": 0, "total": 0.0}
    assert totals["pending"] is not None


def test_list_stores_reads_the_store_table_not_the_free_text_of_price(conn):
    """Depuis le lot 4 le magasin est une LIGNE (amendement A4). Un prix
    observé chez « Carrefour » ne crée plus un magasin par effet de bord :
    c'est `m006` qui a promu l'existant, une fois."""
    repo.insert_price(conn, article_id=1, observed_on="2026-08-01",
                      price_per_base_unit=0.003, store="Carrefour", source="manual")
    assert repo.list_stores(conn) == []
    repo.upsert_store(conn, name="Carrefour")
    assert [row["name"] for row in repo.list_stores(conn)] == ["Carrefour"]


def test_latest_price_in_store_breaks_a_same_day_tie_by_insertion_order(conn):
    repo.insert_price(conn, article_id=1, observed_on="2026-08-02",
                      price_per_base_unit=0.002, store="Leclerc", source="manual")
    repo.insert_price(conn, article_id=1, observed_on="2026-08-02",
                      price_per_base_unit=0.0025, store="Leclerc", source="manual")

    assert repo.latest_price_in_store(conn, 1, "Leclerc") == pytest.approx(0.0025)


def test_lines_come_back_in_walking_order_not_scan_order(conn):
    """The cart is read while walking the shop, so the aisle order is the one
    that matters — not the order things were scanned in.

    The timestamps are deliberately in the opposite order of the expected
    result (Pâtes scanned first, Yaourt scanned second) so that an
    implementation that wrongly sorted by scan time would fail this test
    instead of passing it by accident.
    """
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
    repo.add_line(conn, session_id=session_id, article_id=1, quantity=500,
                  unit_price=0.002, scanned_at="2026-08-19T10:01:00", idempotency_key="a")
    repo.add_line(conn, session_id=session_id, article_id=2, quantity=4,
                  unit_price=0.35, scanned_at="2026-08-19T10:05:00", idempotency_key="b")

    lines = repo.list_lines(conn, session_id)

    assert [line["product_name"] for line in lines] == ["Yaourt", "Pâtes"]


def test_the_total_ignores_a_line_with_no_price(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
    repo.add_line(conn, session_id=session_id, article_id=1, quantity=500,
                  unit_price=0.002, scanned_at="2026-08-19T10:05:00", idempotency_key="a")
    repo.add_line(conn, session_id=session_id, article_id=2, quantity=4,
                  unit_price=None, scanned_at="2026-08-19T10:06:00", idempotency_key="b")

    totals = repo.session_totals(conn, session_id)

    assert {key: totals[key] for key in ("lines", "pending", "total")} == {
        "lines": 2, "pending": 2, "total": pytest.approx(1.0)}


def test_a_stored_line_leaves_the_pending_list(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
    line_id = repo.add_line(conn, session_id=session_id, article_id=1, quantity=500,
                            unit_price=0.002, scanned_at="2026-08-19T10:05:00",
                            idempotency_key="a")
    batch_id = repo.insert_batch(conn, article_id=1, location_id=1, quantity=500,
                                 best_before=None, entered_at="2026-08-19T12:00:00",
                                 price_per_base_unit=0.002)

    repo.mark_line_stored(conn, line_id, batch_id=batch_id, stored_at="2026-08-19T12:00:00")

    assert repo.list_lines(conn, session_id, pending_only=True) == []
    assert repo.session_totals(conn, session_id)["pending"] == 0


def test_a_replayed_scan_is_found_by_its_key(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
    line_id = repo.add_line(conn, session_id=session_id, article_id=1, quantity=500,
                            unit_price=None, scanned_at="2026-08-19T10:05:00",
                            idempotency_key="scan-42")

    assert repo.line_by_key(conn, "scan-42")["id"] == line_id
    assert repo.line_by_key(conn, "scan-43") is None


def test_the_price_of_this_shop_beats_the_price_of_another(conn):
    repo.insert_price(conn, article_id=1, observed_on="2026-08-01",
                      price_per_base_unit=0.003, store="Carrefour", source="manual")
    repo.insert_price(conn, article_id=1, observed_on="2026-08-02",
                      price_per_base_unit=0.002, store="Leclerc", source="manual")

    assert repo.latest_price_in_store(conn, 1, "Leclerc") == pytest.approx(0.002)
    assert repo.latest_price_in_store(conn, 1, "Lidl") is None


def test_known_shops_come_back_most_recent_first(conn):
    carrefour = repo.upsert_store(conn, name="Carrefour")
    leclerc = repo.upsert_store(conn, name="Leclerc")
    repo.open_session(conn, started_at="2026-08-01T09:00:00", store="Carrefour",
                      store_id=carrefour)
    repo.set_session_state(conn, 1, "done", closed_at="2026-08-01T10:00:00")
    repo.open_session(conn, started_at="2026-08-05T09:00:00", store="Leclerc",
                      store_id=leclerc)
    repo.set_session_state(conn, 2, "done", closed_at="2026-08-05T10:00:00")

    assert [row["name"] for row in repo.list_stores(conn)] == ["Leclerc", "Carrefour"]


# --- amendement A3 : la cascade ne se nourrit pas de ses suppositions -------

def _observe(conn, *, source, price, day, store="Leclerc"):
    return repo.insert_price(conn, article_id=1, observed_on=day,
                             price_per_base_unit=price, source=source, store=store)


def test_an_open_prices_observation_never_reaches_rank_one(conn):
    """LE test de la dette : deux lignes dans le même magasin, l'une
    `open_prices` plus récente, l'autre `manual` plus ancienne.
    `latest_price_in_store` rend la MANUELLE."""
    _observe(conn, source="manual", price=0.004, day="2026-08-01")
    _observe(conn, source="open_prices", price=0.009, day="2026-08-20")
    assert repo.latest_price_in_store(conn, 1, "Leclerc") == pytest.approx(0.004)


@pytest.mark.parametrize("source", ["receipt", "import", "manual"])
def test_a_receipt_and_an_import_observation_do_reach_rank_one(conn, source):
    """`receipt` et `import` sont des observations : le ticket et la reprise
    Grocy disent ce qui a réellement été payé."""
    _observe(conn, source=source, price=0.007, day="2026-08-20")
    assert repo.latest_price_in_store(conn, 1, "Leclerc") == pytest.approx(0.007)


@pytest.mark.parametrize("source", ["open_prices", "last_known", "store"])
def test_a_store_with_only_suggested_prices_answers_nothing(conn, source):
    """Et la cascade retombe alors sur Open Prices puis sur le dernier prix
    connu — comportement du lot 1, préservé."""
    _observe(conn, source=source, price=0.009, day="2026-08-20")
    assert repo.latest_price_in_store(conn, 1, "Leclerc") is None


# --- amendement A4 : le magasin promu en table ------------------------------

def _done_session(conn, *, store_id, name, started_at):
    session_id = repo.open_session(conn, started_at=started_at, store=name,
                                   store_id=store_id)
    repo.set_session_state(conn, session_id, "done", closed_at=started_at)
    return session_id


def test_list_stores_now_carries_an_id_and_a_session_count(conn):
    """Forme changée : les appelants du lot 1 (session.ts, websocket) sont
    tous mis à jour dans ce lot. Le test épingle les cinq clés."""
    store_id = repo.upsert_store(conn, name="Leclerc")
    _done_session(conn, store_id=store_id, name="Leclerc",
                  started_at="2026-08-01T09:00:00")
    [row] = repo.list_stores(conn)
    assert set(row) == {"id", "name", "position", "active",
                        "observed_sessions", "last_seen"}
    assert row["id"] == store_id
    assert row["name"] == "Leclerc"
    assert row["observed_sessions"] == 1
    assert row["last_seen"] == "2026-08-01T09:00:00"


def test_two_spellings_stay_two_stores(conn):
    """« Leclerc » et « E.Leclerc » restent distincts. Les réunir est une
    décision du propriétaire, prise dans les réglages, jamais devinée."""
    first = repo.upsert_store(conn, name="Leclerc")
    second = repo.upsert_store(conn, name="E.Leclerc")
    assert first != second
    assert repo.upsert_store(conn, name="Leclerc") == first
    # La casse compte : deviner qu'elle ne compte pas, c'est deviner.
    assert repo.upsert_store(conn, name="leclerc") not in (first, second)


def test_merging_reassigns_sessions_prices_and_aisle_orders(conn):
    """Et additionne les `observed_sessions` : un magasin fiable ne
    redevient pas incertain parce qu'on a corrigé son nom."""
    keep = repo.upsert_store(conn, name="Leclerc")
    merge = repo.upsert_store(conn, name="E.Leclerc")
    _done_session(conn, store_id=keep, name="Leclerc", started_at="2026-08-01T09:00:00")
    _done_session(conn, store_id=merge, name="E.Leclerc",
                  started_at="2026-08-08T09:00:00")
    repo.insert_price(conn, article_id=1, observed_on="2026-08-08",
                      price_per_base_unit=0.002, store="E.Leclerc", source="manual",
                      store_id=merge)
    aisle_id = repo.list_aisles(conn)[0]["id"]
    repo.set_store_aisle(conn, store_id=merge, aisle_id=aisle_id, position=3,
                         source="learned", mean_rank=1.5, observed_sessions=2,
                         updated_at="2026-08-08T10:00:00")

    result = repo.merge_stores(conn, keep_id=keep, merge_id=merge)

    assert result["keep_id"] == keep
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM shopping_session WHERE store_id = ?",
        (keep,)).fetchone()["n"] == 2
    assert conn.execute("SELECT store_id FROM price WHERE id = 1").fetchone()[0] == keep
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM store_aisle WHERE store_id = ?",
        (keep,)).fetchone()["n"] == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM store WHERE id = ?",
                        (merge,)).fetchone()["n"] == 0
    [row] = repo.list_stores(conn)
    assert row["observed_sessions"] == 2


def test_merging_leaves_the_free_text_of_price_untouched(conn):
    """`price.store` garde « E.Leclerc » : c'est ce qui a été observé.

    `price` est un journal d'observations. Réécrire le texte pour faire
    joli, c'est exactement ce que le lot 0 refuse au journal des mouvements.
    """
    keep = repo.upsert_store(conn, name="Leclerc")
    merge = repo.upsert_store(conn, name="E.Leclerc")
    repo.insert_price(conn, article_id=1, observed_on="2026-08-08",
                      price_per_base_unit=0.002, store="E.Leclerc", source="manual",
                      store_id=merge)

    repo.merge_stores(conn, keep_id=keep, merge_id=merge)

    row = conn.execute("SELECT store, store_id FROM price WHERE id = 1").fetchone()
    assert row["store"] == "E.Leclerc"
    assert row["store_id"] == keep


def test_merging_two_aisle_orders_keeps_the_one_of_the_surviving_store(conn):
    """Deux ordres pour le même rayon : celui du magasin conservé gagne. Il
    ne peut en rester qu'un, la clé primaire est (store_id, aisle_id)."""
    keep = repo.upsert_store(conn, name="Leclerc")
    merge = repo.upsert_store(conn, name="E.Leclerc")
    aisle_id = repo.list_aisles(conn)[0]["id"]
    repo.set_store_aisle(conn, store_id=keep, aisle_id=aisle_id, position=1,
                         source="manual", updated_at="2026-08-01T10:00:00")
    repo.set_store_aisle(conn, store_id=merge, aisle_id=aisle_id, position=9,
                         source="learned", updated_at="2026-08-08T10:00:00")

    repo.merge_stores(conn, keep_id=keep, merge_id=merge)

    rows = conn.execute("SELECT * FROM store_aisle").fetchall()
    assert len(rows) == 1
    assert rows[0]["position"] == 1 and rows[0]["source"] == "manual"


def test_deactivating_a_store_keeps_its_history(conn):
    """`active = 0` le retire des pastilles, pas des prix ni des parcours."""
    store_id = repo.upsert_store(conn, name="Leclerc")
    _done_session(conn, store_id=store_id, name="Leclerc",
                  started_at="2026-08-01T09:00:00")
    repo.upsert_store(conn, name="Leclerc", store_id=store_id, active=0)

    assert repo.list_stores(conn) == []
    assert [row["name"] for row in repo.list_stores(conn, active_only=False)] == ["Leclerc"]
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM shopping_session WHERE store_id = ?",
        (store_id,)).fetchone()["n"] == 1


def test_find_store_by_name_is_an_exact_match(conn):
    store_id = repo.upsert_store(conn, name="Leclerc")
    assert repo.find_store_by_name(conn, "Leclerc")["id"] == store_id
    assert repo.find_store_by_name(conn, "leclerc") is None
    assert repo.find_store_by_name(conn, "Lecler") is None
    assert repo.get_store(conn, store_id)["name"] == "Leclerc"


# --- § 9 : le coût du panier — estimé, constaté, hors liste -----------------

def _cart(conn, *, lines):
    session_id = repo.open_session(conn, started_at="2026-08-21T09:00:00",
                                   store="Leclerc")
    for article_id, quantity, price, source in lines:
        repo.add_line(conn, session_id=session_id, article_id=article_id,
                      quantity=quantity, unit_price=price,
                      scanned_at="2026-08-21T10:00:00", idempotency_key=None,
                      price_source=source)
    return session_id


def test_the_total_splits_into_observed_and_estimated(conn):
    """Somme inchangée, répartie. `observed + estimated == total`, exactement."""
    session_id = _cart(conn, lines=[
        (1, 500, 0.004, "manual"),          # 2,00 € constatés
        (1, 500, 0.006, "receipt"),         # 3,00 € constatés
        (2, 4, 0.5, "open_prices"),         # 2,00 € estimés
    ])
    totals = repo.session_totals(conn, session_id)

    assert totals["total"] == pytest.approx(7.0)
    assert totals["observed"] == pytest.approx(5.0)
    assert totals["estimated"] == pytest.approx(2.0)
    assert totals["observed"] + totals["estimated"] == pytest.approx(totals["total"])


def test_a_line_without_a_price_counts_zero_and_is_counted(conn):
    """`COALESCE` la comptait déjà zéro en silence ; désormais elle est DITE."""
    session_id = _cart(conn, lines=[
        (1, 500, 0.004, "manual"),
        (2, 4, None, None),
    ])
    totals = repo.session_totals(conn, session_id)

    assert totals["total"] == pytest.approx(2.0)
    assert totals["unpriced_lines"] == 1


@pytest.mark.parametrize("source", ["open_prices", "last_known", "store"])
def test_a_store_sourced_price_counts_as_estimated(conn, source):
    """`store` = le dernier prix relevé dans ce magasin, proposé et accepté
    sans y toucher : c'est une suggestion, pas l'étiquette d'aujourd'hui."""
    session_id = _cart(conn, lines=[(1, 500, 0.004, source)])
    totals = repo.session_totals(conn, session_id)
    assert totals["estimated"] == pytest.approx(2.0)
    assert totals["observed"] == pytest.approx(0.0)


def test_the_off_list_counter_counts_lines_not_units(conn):
    """« n hors liste » sert à UNE chose : savoir, à la caisse, combien
    d'articles se sont invités."""
    item_id = repo.insert_list_item(conn, added_at="2026-08-21T09:00:00",
                                    product_id=1)
    session_id = _cart(conn, lines=[
        (1, 500, 0.004, "manual"),
        (1, 500, 0.004, "manual"),
        (2, 4, 0.5, "manual"),
    ])
    line_id = conn.execute("SELECT MIN(id) AS id FROM shopping_line").fetchone()["id"]
    repo.check_list_item(conn, item_id, at="2026-08-21T10:00:00",
                         session_id=session_id, line_id=line_id)

    totals = repo.session_totals(conn, session_id)

    # Trois lignes, une seule a coché la liste : deux se sont invitées.
    assert totals["off_list_lines"] == 2


def test_the_progress_counts_checked_over_open(conn):
    """« 12 / 17 de la liste »."""
    first = repo.insert_list_item(conn, added_at="2026-08-21T09:00:00", product_id=1)
    repo.insert_list_item(conn, added_at="2026-08-21T09:00:00", product_id=2)
    repo.insert_list_item(conn, added_at="2026-08-21T09:00:00", free_text="Piles")
    session_id = _cart(conn, lines=[(1, 500, 0.004, "manual")])
    line_id = conn.execute("SELECT MIN(id) AS id FROM shopping_line").fetchone()["id"]
    repo.check_list_item(conn, first, at="2026-08-21T10:00:00",
                         session_id=session_id, line_id=line_id)

    totals = repo.session_totals(conn, session_id)

    assert totals["checked_items"] == 1
    assert totals["list_items"] == 3


def test_a_session_with_no_line_publishes_zeroes_not_nulls(conn):
    """Un capteur `unknown` en plein magasin est un capteur inutile."""
    session_id = repo.open_session(conn, started_at="2026-08-21T09:00:00", store=None)
    totals = repo.session_totals(conn, session_id)
    assert totals == {"lines": 0, "pending": 0, "total": 0.0, "observed": 0.0,
                      "estimated": 0.0, "unpriced_lines": 0, "off_list_lines": 0,
                      "checked_items": 0, "list_items": 0}


# --- § 11 : l'ordre des rayons par magasin ---------------------------------

def test_recent_session_aisle_sequences_reads_closed_sessions_only(conn):
    store_id = repo.upsert_store(conn, name="Leclerc")
    aisles = {row["name"]: row["id"] for row in repo.list_aisles(conn)}
    closed = repo.open_session(conn, started_at="2026-08-01T09:00:00",
                               store="Leclerc", store_id=store_id)
    repo.add_line(conn, session_id=closed, article_id=2, quantity=1,
                  unit_price=None, scanned_at="2026-08-01T09:05:00",
                  idempotency_key=None)
    repo.add_line(conn, session_id=closed, article_id=1, quantity=1,
                  unit_price=None, scanned_at="2026-08-01T09:02:00",
                  idempotency_key=None)
    repo.set_session_state(conn, closed, "done", closed_at="2026-08-01T10:00:00")
    still_open = repo.open_session(conn, started_at="2026-08-08T09:00:00",
                                   store="Leclerc", store_id=store_id)
    repo.add_line(conn, session_id=still_open, article_id=1, quantity=1,
                  unit_price=None, scanned_at="2026-08-08T09:01:00",
                  idempotency_key=None)

    sequences = repo.recent_session_aisle_sequences(conn, store_id)

    # Une seule session close, et ses lignes triées par `scanned_at` — pas
    # par `id` : on apprend l'ordre du PARCOURS.
    assert sequences == [[aisles["Épicerie salée"], aisles["Crémerie"]]]


def test_only_the_last_ten_sessions_are_read(conn):
    from custom_components.home_stock.const import ROUTE_SESSION_WINDOW
    store_id = repo.upsert_store(conn, name="Leclerc")
    for day in range(1, 15):
        session_id = repo.open_session(conn, started_at=f"2026-08-{day:02d}T09:00:00",
                                       store="Leclerc", store_id=store_id)
        repo.add_line(conn, session_id=session_id, article_id=1, quantity=1,
                      unit_price=None, scanned_at=f"2026-08-{day:02d}T09:05:00",
                      idempotency_key=None)
        repo.set_session_state(conn, session_id, "done",
                               closed_at=f"2026-08-{day:02d}T10:00:00")

    assert len(repo.recent_session_aisle_sequences(conn, store_id)) == ROUTE_SESSION_WINDOW


def test_save_store_route_never_overwrites_a_pinned_row(conn):
    from custom_components.home_stock.domain.route import RouteEntry
    store_id = repo.upsert_store(conn, name="Leclerc")
    aisles = {row["name"]: row["id"] for row in repo.list_aisles(conn)}
    repo.set_store_aisle(conn, store_id=store_id, aisle_id=aisles["Crémerie"],
                         position=1, source="manual",
                         updated_at="2026-08-01T10:00:00")

    repo.save_store_route(conn, store_id, [
        RouteEntry(aisles["Crémerie"], 9, 0.9, 3, "learned"),
        RouteEntry(aisles["Épicerie salée"], 2, 0.2, 3, "learned"),
    ], updated_at="2026-08-21T10:00:00")

    rows = {row["aisle_id"]: row for row in repo.store_aisles(conn, store_id)}
    assert rows[aisles["Crémerie"]]["position"] == 1
    assert rows[aisles["Crémerie"]]["source"] == "manual"
    # L'apprentissage reste VISIBLE sur la ligne épinglée : on voit qu'il la
    # contredit, sans qu'il la déplace.
    assert rows[aisles["Crémerie"]]["mean_rank"] == pytest.approx(0.9)
    assert rows[aisles["Épicerie salée"]]["position"] == 2


def test_pinning_and_unpinning_an_aisle(conn):
    store_id = repo.upsert_store(conn, name="Leclerc")
    aisles = [row["id"] for row in repo.list_aisles(conn)][:3]

    repo.pin_store_aisles(conn, store_id, aisles)

    rows = {row["aisle_id"]: row for row in repo.store_aisles(conn, store_id)}
    assert [rows[aisle_id]["position"] for aisle_id in aisles] == [1, 2, 3]
    assert all(rows[aisle_id]["source"] == "manual" for aisle_id in aisles)

    repo.unpin_store_aisle(conn, store_id, aisles[1])
    rows = {row["aisle_id"]: row for row in repo.store_aisles(conn, store_id)}
    assert rows[aisles[1]]["source"] == "learned"


def test_store_route_joins_the_aisle_names(conn):
    store_id = repo.upsert_store(conn, name="Leclerc")
    aisle_id = repo.list_aisles(conn)[0]["id"]
    repo.set_store_aisle(conn, store_id=store_id, aisle_id=aisle_id, position=1,
                         source="learned", mean_rank=0.1, observed_sessions=3,
                         updated_at="2026-08-21T10:00:00")
    [row] = repo.store_route(conn, store_id)
    assert row["aisle_name"]
    assert row["mean_rank"] == pytest.approx(0.1)
    assert row["observed_sessions"] == 3
