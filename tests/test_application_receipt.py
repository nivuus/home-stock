"""Appliquer un ticket : relire des prix, et jamais nourrir le catalogue."""
import pytest

from custom_components.home_stock.storage import repositories as repo

from test_application import manager  # noqa: F401


@pytest.fixture
def trip(manager):
    """Un voyage : un magasin, deux articles scannés, une photo de ticket."""
    with manager.db.write() as conn:
        location_id = repo.insert_location(conn, name="Placard", kind="pantry")
        store_id = repo.upsert_store(conn, name="Leclerc")
        milk = repo.insert_product(conn, name="Lait", base_unit="ml")
        pieces = repo.insert_product(conn, name="Éponge", base_unit="piece")
        milk_article = repo.insert_article(conn, product_id=milk,
                                           label="Lait demi-écrémé 1 L",
                                           net_quantity=1000)
        sponge_article = repo.insert_article(conn, product_id=pieces,
                                             label="Éponge x3", net_quantity=3)
        session_id = repo.open_session(conn, started_at="2026-08-21T19:00:00",
                                       store="Leclerc", store_id=store_id)
        milk_line = repo.add_line(conn, session_id=session_id,
                                  article_id=milk_article, quantity=1000,
                                  unit_price=0.0009, scanned_at="2026-08-21T19:05:00",
                                  idempotency_key=None, price_source="open_prices")
        sponge_line = repo.add_line(conn, session_id=session_id,
                                    article_id=sponge_article, quantity=1,
                                    unit_price=2.0, scanned_at="2026-08-21T19:06:00",
                                    idempotency_key=None, price_source="open_prices")
        receipt_id = repo.insert_receipt(
            conn, media_content_id="media-source://media_source/local/t.jpg",
            captured_at="2026-08-21T20:00:00", session_id=session_id,
            store_id=store_id, state="read")
        repo.set_receipt_state(conn, receipt_id, "read", purchased_on="2026-08-21")
        repo.replace_receipt_lines(conn, receipt_id, [
            {"position": 1, "label": "LT DEMI ECR 1L", "quantity": 1,
             "unit_price": 1.05, "total_price": 1.05, "line_id": milk_line,
             "match_state": "auto"},
            {"position": 2, "label": "EPONGE X3", "quantity": 1,
             "unit_price": 2.40, "total_price": 2.40, "line_id": sponge_line,
             "match_state": "auto"},
            {"position": 3, "label": "SAC CABAS", "quantity": 1,
             "unit_price": 0.60, "total_price": 0.60},
        ])
    return {"receipt_id": receipt_id, "session_id": session_id,
            "store_id": store_id, "milk_line": milk_line,
            "sponge_line": sponge_line, "milk_article": milk_article,
            "sponge_article": sponge_article, "location_id": location_id}


def _line(manager, line_id):
    return repo.get_line(manager.db.read(), line_id)


def test_applying_sets_the_line_price_in_base_units(manager, trip):
    """Divisé par le poids net en `g`/`ml`, JAMAIS en `piece`."""
    manager.apply_receipt(trip["receipt_id"], moment="2026-08-21T21:00:00")

    assert _line(manager, trip["milk_line"])["unit_price"] == pytest.approx(0.00105)
    assert _line(manager, trip["sponge_line"])["unit_price"] == pytest.approx(2.40)


def test_applying_marks_the_line_price_source_receipt(manager, trip):
    manager.apply_receipt(trip["receipt_id"], moment="2026-08-21T21:00:00")
    assert _line(manager, trip["milk_line"])["price_source"] == "receipt"


def test_applying_writes_one_price_observation_per_corrected_line(manager, trip):
    """Avec le `store_id` de la session et la date du TICKET, pas celle du
    jour : c'est ce qui a été payé, le jour où ça l'a été."""
    manager.apply_receipt(trip["receipt_id"], moment="2026-08-25T09:00:00")

    prices = manager.db.read().execute(
        "SELECT * FROM price ORDER BY id").fetchall()
    assert len(prices) == 2
    assert {row["source"] for row in prices} == {"receipt"}
    assert {row["observed_on"] for row in prices} == {"2026-08-21"}
    assert {row["store_id"] for row in prices} == {trip["store_id"]}


def test_a_receipt_observation_reaches_rank_one_next_trip(manager, trip):
    manager.apply_receipt(trip["receipt_id"], moment="2026-08-21T21:00:00")
    assert repo.latest_price_in_store(
        manager.db.read(), trip["milk_article"], "Leclerc") == pytest.approx(0.00105)


def test_the_usual_case_corrects_nothing_at_all(manager, trip):
    """Un ticket lu le soir même : `corrected_movements == 0`."""
    result = manager.apply_receipt(trip["receipt_id"], moment="2026-08-21T21:00:00")
    assert result["applied"] == 2
    assert result["corrected_movements"] == 0
    assert manager.db.read().execute(
        "SELECT COUNT(*) AS n FROM movement").fetchone()["n"] == 0


def test_an_already_stored_line_goes_through_correct_price(manager, trip):
    """Contrepassation puis réécriture, en une transaction (§ 12.4)."""
    manager.shopping_store_line = None
    batch_id = manager.add_stock(
        article_id=trip["milk_article"], quantity=1000,
        location_id=trip["location_id"], price_per_base_unit=0.0009,
        occurred_at="2026-08-21T20:30:00")
    with manager.db.write() as conn:
        repo.mark_line_stored(conn, trip["milk_line"], batch_id=batch_id,
                              stored_at="2026-08-21T20:30:00")

    result = manager.apply_receipt(trip["receipt_id"], moment="2026-08-21T21:00:00")

    assert result["corrected_movements"] == 1
    conn = manager.db.read()
    assert conn.execute("SELECT price_per_base_unit FROM batch WHERE id = ?",
                        (batch_id,)).fetchone()[0] == pytest.approx(0.00105)
    rows = repo.movements_of_batch(conn, batch_id)
    assert [row["corrects_id"] is not None for row in rows] == [False, True, False]
    assert rows[2]["cost"] == pytest.approx(1.05)


def test_a_line_stored_and_partly_eaten_corrects_every_movement(manager, trip):
    batch_id = manager.add_stock(
        article_id=trip["milk_article"], quantity=1000,
        location_id=trip["location_id"], price_per_base_unit=0.0009,
        occurred_at="2026-08-21T20:30:00")
    manager.consume_batch(batch_id, quantity=250.0,
                          occurred_at="2026-08-21T20:45:00")
    with manager.db.write() as conn:
        repo.mark_line_stored(conn, trip["milk_line"], batch_id=batch_id,
                              stored_at="2026-08-21T20:30:00")

    result = manager.apply_receipt(trip["receipt_id"], moment="2026-08-21T21:00:00")

    assert result["corrected_movements"] == 2
    conn = manager.db.read()
    totals = repo.totals_between(conn)
    assert totals["cost"] == pytest.approx(250 * 0.00105)


def test_an_unmatched_receipt_line_creates_nothing(manager, trip):
    """Ni article, ni produit, ni lot. Elle reste visible et `unmatched`.

    Un article passé en caisse sans avoir été scanné n'a ni EAN, ni article,
    ni produit, ni emplacement ; en fabriquer un depuis un libellé abrégé
    produirait des doublons de catalogue à chaque voyage.
    """
    before = manager.db.read().execute(
        "SELECT COUNT(*) AS n FROM article").fetchone()["n"]

    result = manager.apply_receipt(trip["receipt_id"], moment="2026-08-21T21:00:00")

    conn = manager.db.read()
    assert conn.execute("SELECT COUNT(*) AS n FROM article").fetchone()["n"] == before
    assert conn.execute("SELECT COUNT(*) AS n FROM batch").fetchone()["n"] == 0
    orphan = [line for line in repo.get_receipt(conn, trip["receipt_id"])["lines"]
              if line["label"] == "SAC CABAS"][0]
    assert orphan["match_state"] == "unmatched"
    assert orphan["applied_at"] is None
    assert result["skipped"] == 1


def test_applying_twice_is_a_no_op(manager, trip):
    """`receipt_line.applied_at` rend la seconde application sans effet."""
    first = manager.apply_receipt(trip["receipt_id"], moment="2026-08-21T21:00:00")
    second = manager.apply_receipt(trip["receipt_id"], moment="2026-08-21T21:05:00")

    assert first["applied"] == 2 and second["applied"] == 0
    assert manager.db.read().execute(
        "SELECT COUNT(*) AS n FROM price").fetchone()["n"] == 2


def test_applying_a_discarded_receipt_is_refused(manager, trip):
    from custom_components.home_stock.messages import french_message
    with manager.db.write() as conn:
        repo.set_receipt_state(conn, trip["receipt_id"], "discarded")

    with pytest.raises(ValueError) as refus:
        manager.apply_receipt(trip["receipt_id"], moment="2026-08-21T21:00:00")
    assert french_message(refus.value) == (
        "Ce ticket n'a pas été lu : rien à appliquer.")


def test_matching_a_line_by_hand_overrides_the_automatic_match(manager, trip):
    """`confirmed` et `ignored` : le même vocabulaire qu'au lot 3, les mêmes
    quatre mots, la même signification."""
    conn = manager.db.read()
    lines = repo.get_receipt(conn, trip["receipt_id"])["lines"]
    orphan = next(line for line in lines if line["label"] == "SAC CABAS")
    milk = next(line for line in lines if line["label"] == "LT DEMI ECR 1L")

    manager.match_receipt_line(orphan["id"], line_id=trip["sponge_line"],
                              state="confirmed")
    manager.match_receipt_line(milk["id"], line_id=None, state="ignored")
    result = manager.apply_receipt(trip["receipt_id"], moment="2026-08-21T21:00:00")

    assert result["applied"] == 2                # l'éponge, deux fois corrigée
    assert _line(manager, trip["milk_line"])["price_source"] == "open_prices"


def test_apply_receipt_runs_in_one_transaction(manager, trip):
    """`--timeout=60` : un `db.write()` imbriqué figerait le processus sans
    lever ni tracer."""
    batch_id = manager.add_stock(
        article_id=trip["milk_article"], quantity=1000,
        location_id=trip["location_id"], price_per_base_unit=0.0009,
        occurred_at="2026-08-21T20:30:00")
    with manager.db.write() as conn:
        repo.mark_line_stored(conn, trip["milk_line"], batch_id=batch_id,
                              stored_at="2026-08-21T20:30:00")
    assert manager.apply_receipt(trip["receipt_id"],
                                 moment="2026-08-21T21:00:00")["applied"] == 2


def test_the_receipt_becomes_applied(manager, trip):
    manager.apply_receipt(trip["receipt_id"], moment="2026-08-21T21:00:00")
    assert repo.get_receipt(manager.db.read(),
                            trip["receipt_id"])["state"] == "applied"


def test_preview_says_how_many_movements_will_be_corrected(manager, trip):
    assert manager.preview_receipt(trip["receipt_id"])["corrected_movements"] == 0
    batch_id = manager.add_stock(
        article_id=trip["milk_article"], quantity=1000,
        location_id=trip["location_id"], price_per_base_unit=0.0009,
        occurred_at="2026-08-21T20:30:00")
    with manager.db.write() as conn:
        repo.mark_line_stored(conn, trip["milk_line"], batch_id=batch_id,
                              stored_at="2026-08-21T20:30:00")

    preview = manager.preview_receipt(trip["receipt_id"])

    assert preview["corrected_movements"] == 1
    assert preview["applied"] == 2
    assert preview["skipped"] == 1
    # N'écrit rien.
    assert repo.get_receipt(manager.db.read(),
                            trip["receipt_id"])["state"] == "read"


def test_the_put_away_never_depends_on_the_receipt(manager, trip):
    """Deux fils PARALLÈLES à partir de la caisse : on vide les sacs pendant
    que le modèle lit, et on lit le lendemain matin si le réseau du parking
    était mauvais."""
    with manager.db.write() as conn:
        repo.set_receipt_state(conn, trip["receipt_id"], "failed",
                               error="Le modèle n'a pas répondu.")

    batch_id = manager.add_stock(
        article_id=trip["milk_article"], quantity=1000,
        location_id=trip["location_id"], price_per_base_unit=0.0009,
        occurred_at="2026-08-21T20:30:00")

    assert batch_id
    assert repo.get_receipt(manager.db.read(),
                            trip["receipt_id"])["state"] == "failed"
