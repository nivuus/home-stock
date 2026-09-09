import pytest

from custom_components.home_stock.const import MACRO_COLUMNS, NUTRITION_COLUMNS
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations


@pytest.fixture
def conn(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.connect()
    with db.write() as c:
        apply_migrations(c)
    with db.write() as c:
        yield c
    db.close()


@pytest.fixture
def seeded_conn(conn):
    """`conn`, plus one location, one product in grams, one article and an
    open batch of 500 g — all landing on id 1 in a fresh test database, so
    tests can hardcode product_id=1/article_id=1 the way this file's
    insert_movement tests already do.
    """
    repo.insert_location(conn, name="Placard", kind="pantry")
    product_id = repo.insert_product(conn, name="Article", base_unit="g")
    article_id = repo.insert_article(conn, product_id=product_id)
    repo.insert_batch(conn, article_id=article_id, location_id=1,
                      quantity=500, entered_at="2026-08-01T10:00:00")
    return conn


def test_product_round_trip(conn):
    product_id = repo.insert_product(conn, name="Moutarde", base_unit="g")
    product = repo.get_product(conn, product_id)
    assert product["name"] == "Moutarde"
    assert product["base_unit"] == "g"
    assert product["active"] == 1


def test_find_product_by_name(conn):
    repo.insert_product(conn, name="Moutarde", base_unit="g")
    assert repo.find_product_by_name(conn, "Moutarde")["name"] == "Moutarde"
    assert repo.find_product_by_name(conn, "Ketchup") is None


def test_barcode_resolves_to_an_article(conn):
    product_id = repo.insert_product(conn, name="Moutarde", base_unit="g")
    small = repo.insert_article(conn, product_id=product_id, label="Savora 265 g",
                                net_quantity=265, kcal_per_base_unit=1.2)
    large = repo.insert_article(conn, product_id=product_id, label="Savora 385 g",
                                net_quantity=385, kcal_per_base_unit=1.2)
    repo.link_barcode(conn, "3011360002105", small)
    repo.link_barcode(conn, "3011360002204", large)
    found = repo.find_article_by_barcode(conn, "3011360002204")
    assert found["id"] == large
    assert found["net_quantity"] == 385
    assert repo.find_article_by_barcode(conn, "0000000000000") is None


def test_latest_price_is_the_most_recent(conn):
    product_id = repo.insert_product(conn, name="Moutarde", base_unit="g")
    article_id = repo.insert_article(conn, product_id=product_id)
    repo.insert_price(conn, article_id=article_id, observed_on="2026-01-01",
                      price_per_base_unit=0.004, source="manual")
    repo.insert_price(conn, article_id=article_id, observed_on="2026-08-01",
                      price_per_base_unit=0.005, source="receipt")
    assert repo.latest_price(conn, article_id) == 0.005


def test_latest_price_is_none_without_history(conn):
    product_id = repo.insert_product(conn, name="Sel", base_unit="g")
    article_id = repo.insert_article(conn, product_id=product_id)
    assert repo.latest_price(conn, article_id) is None


def test_list_batches_excludes_closed_ones(conn):
    location_id = repo.insert_location(conn, name="Placard", kind="pantry")
    product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
    article_id = repo.insert_article(conn, product_id=product_id)
    open_batch = repo.insert_batch(conn, article_id=article_id, location_id=location_id,
                                   quantity=500, entered_at="2026-08-01T10:00:00")
    closed = repo.insert_batch(conn, article_id=article_id, location_id=location_id,
                               quantity=500, entered_at="2026-07-01T10:00:00")
    repo.set_batch_remaining(conn, closed, 0, closed_at="2026-08-10T10:00:00")
    batches = repo.list_batches_for_product(conn, product_id)
    assert [b["id"] for b in batches] == [open_batch]


def test_movement_idempotency(conn):
    product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
    article_id = repo.insert_article(conn, product_id=product_id)
    repo.insert_movement(conn, occurred_at="2026-08-18T10:00:00", product_id=product_id,
                         article_id=article_id, quantity=-200, reason="consumption",
                         base_unit="g", kcal=700.0, cost=0.6, idempotency_key="k1")
    assert repo.movement_exists(conn, "k1") is True
    assert repo.movement_exists(conn, "k2") is False


def test_stock_rows_join_names(conn):
    location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
    product_id = repo.insert_product(conn, name="Lait", base_unit="ml")
    article_id = repo.insert_article(conn, product_id=product_id, label="Lactel 1 l")
    repo.insert_batch(conn, article_id=article_id, location_id=location_id,
                      quantity=1000, entered_at="2026-08-01T10:00:00",
                      best_before="2026-08-25", price_per_base_unit=0.0012)
    row = repo.stock_rows(conn)[0]
    assert row["product_name"] == "Lait"
    assert row["location_name"] == "Frigo"
    assert row["base_unit"] == "ml"
    assert row["remaining"] == 1000


def test_stock_rows_kcal_falls_back_to_the_product_reference(conn):
    """home_stock/batches/list (the future panel) is served straight from this
    query: without the same COALESCE as list_batches_for_product (spec 7.4),
    it would show no calories for exactly the generic/produce articles the
    fallback exists for."""
    location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
    product_id = repo.insert_product(conn, name="Pomme", base_unit="g",
                                     reference_kcal=0.52)
    article_id = repo.insert_article(conn, product_id=product_id, label="Générique")
    repo.insert_batch(conn, article_id=article_id, location_id=location_id,
                      quantity=200, entered_at="2026-08-01T10:00:00")
    row = repo.stock_rows(conn)[0]
    assert row["kcal_per_base_unit"] == pytest.approx(0.52)


def test_resolve_kcal_rate_falls_back_to_the_product_reference(conn):
    product_id = repo.insert_product(conn, name="Pomme", base_unit="g",
                                     reference_kcal=0.52)
    article_id = repo.insert_article(conn, product_id=product_id, label="Générique")
    article = repo.get_article(conn, article_id)
    assert repo.resolve_kcal_rate(conn, article) == pytest.approx(0.52)

    with_own_rate = repo.insert_article(conn, product_id=product_id,
                                        kcal_per_base_unit=1.1)
    assert repo.resolve_kcal_rate(conn, repo.get_article(conn, with_own_rate)) == 1.1


def test_barcodes_to_resync_everything_lists_every_barcoded_article(conn):
    product_id = repo.insert_product(conn, name="Muesli", base_unit="g")
    with_code = repo.insert_article(conn, product_id=product_id)
    _without_code = repo.insert_article(conn, product_id=product_id)
    repo.link_barcode(conn, "111", with_code)

    found = repo.barcodes_to_resync(conn, article_id=None, product_id=None, everything=True)

    # _without_code never scanned, so it has nothing to resync from: silently
    # left out rather than reported as an error.
    assert found == [("111", with_code)]


def test_barcodes_to_resync_narrows_to_one_article(conn):
    product_id = repo.insert_product(conn, name="Muesli", base_unit="g")
    first = repo.insert_article(conn, product_id=product_id)
    second = repo.insert_article(conn, product_id=product_id)
    repo.link_barcode(conn, "111", first)
    repo.link_barcode(conn, "222", second)

    found = repo.barcodes_to_resync(conn, article_id=second, product_id=None,
                                    everything=False)

    assert found == [("222", second)]


def test_barcodes_to_resync_narrows_to_one_product(conn):
    wanted_product = repo.insert_product(conn, name="Muesli", base_unit="g")
    other_product = repo.insert_product(conn, name="Riz", base_unit="g")
    wanted_article = repo.insert_article(conn, product_id=wanted_product)
    other_article = repo.insert_article(conn, product_id=other_product)
    repo.link_barcode(conn, "111", wanted_article)
    repo.link_barcode(conn, "222", other_article)

    found = repo.barcodes_to_resync(conn, article_id=None, product_id=wanted_product,
                                    everything=False)

    assert found == [("111", wanted_article)]


def test_barcodes_to_resync_picks_the_lowest_code_of_several(conn):
    """An article scanned under more than one code (a relabelled pack, a
    duplicate scan) still resyncs once, not once per code."""
    product_id = repo.insert_product(conn, name="Muesli", base_unit="g")
    article_id = repo.insert_article(conn, product_id=product_id)
    repo.link_barcode(conn, "222", article_id)
    repo.link_barcode(conn, "111", article_id)

    found = repo.barcodes_to_resync(conn, article_id=None, product_id=None, everything=True)

    assert found == [("111", article_id)]


def test_barcodes_to_resync_with_nothing_selected_returns_nothing(conn):
    product_id = repo.insert_product(conn, name="Muesli", base_unit="g")
    article_id = repo.insert_article(conn, product_id=product_id)
    repo.link_barcode(conn, "111", article_id)

    assert repo.barcodes_to_resync(conn, article_id=None, product_id=None,
                                   everything=False) == []


def test_insert_product_keeps_the_default_shelf_life(conn):
    """`default_shelf_life_days` is added by this lot's own m002 migration and
    accepted by the creation schema, but was missing from PRODUCT_FIELDS —
    the whitelist insert_product filters against. It was therefore writable
    on an edit and silently dropped on a creation, with a success answer."""
    product_id = repo.insert_product(
        conn, name="Yaourts nature", base_unit="piece", default_shelf_life_days=21)

    assert repo.get_product(conn, product_id)["default_shelf_life_days"] == 21


def test_pending_lines_of_a_closed_session_no_longer_count(conn):
    """A line never put away used to block its product's unit conversion for
    good: it cannot be deleted once its session is closed, and the count
    ignored the session's state. Closing a session is how a trip is given up."""
    product_id = repo.insert_product(conn, name="Yaourts nature", base_unit="piece")
    article_id = repo.insert_article(conn, product_id=product_id)
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store="Lidl")
    repo.add_line(conn, session_id=session_id, article_id=article_id, quantity=6,
                  unit_price=None, scanned_at="2026-08-19T10:01:00",
                  idempotency_key=None)

    assert repo.count_pending_lines_for_product(conn, product_id) == 1

    repo.set_session_state(conn, session_id, "done", closed_at="2026-08-19T12:00:00")

    assert repo.count_pending_lines_for_product(conn, product_id) == 0


def test_insert_movement_freezes_the_eight_macros(seeded_conn):
    movement_id = repo.insert_movement(
        seeded_conn, occurred_at="2026-08-20T10:00:00", product_id=1, article_id=1,
        quantity=-200.0, reason="consumption", base_unit="g", kcal=240.0, cost=0.8,
        macros={"proteins": 10.0, "salt": 0.2},
    )
    row = seeded_conn.execute(
        "SELECT * FROM movement WHERE id = ?", (movement_id,)).fetchone()
    assert row["proteins"] == 10.0
    assert row["salt"] == 0.2
    # A macro absent from the dict stays NULL, not 0.
    assert row["fiber"] is None


def test_insert_movement_without_macros_writes_eight_nulls(seeded_conn):
    movement_id = repo.insert_movement(
        seeded_conn, occurred_at="2026-08-20T10:00:00", product_id=1, article_id=1,
        quantity=-200.0, reason="consumption", base_unit="g")
    row = seeded_conn.execute(
        "SELECT * FROM movement WHERE id = ?", (movement_id,)).fetchone()
    assert all(row[column] is None for column in MACRO_COLUMNS)


def test_macro_rates_reads_the_eight_columns_of_a_row():
    row = {"proteins": 0.05, "carbohydrates": None, "sugars": 0.01,
           "added_sugars": None, "fat": 0.02, "saturated_fat": None,
           "fiber": 0.0, "salt": 0.001, "kcal_per_base_unit": 1.2}
    rates = repo.macro_rates(row)
    assert set(rates) == set(MACRO_COLUMNS)
    assert rates["proteins"] == 0.05
    assert rates["carbohydrates"] is None
    assert rates["fiber"] == 0.0       # measured at zero, not missing
    assert "kcal_per_base_unit" not in rates


def test_list_batches_for_product_reports_the_macro_rates(seeded_conn):
    seeded_conn.execute("UPDATE article SET proteins = 0.05, salt = 0.001 WHERE id = 1")
    [row] = repo.list_batches_for_product(seeded_conn, 1)
    assert row["proteins"] == 0.05
    assert row["salt"] == 0.001


# --- lot 3 : la cascade ne doit jamais être masquée par une colonne du lot ---

def test_no_query_selects_the_whole_batch_row_next_to_a_resolved_rate():
    """`SELECT b.*` est interdit dès lors que `batch` porte des nutriments.

    Depuis m004, `batch` a ses propres `kcal_per_base_unit` et ses huit macros.
    Une requête qui écrit `SELECT b.*, COALESCE(...) AS kcal_per_base_unit`
    renvoie donc DEUX colonnes du même nom, et `dict(sqlite3.Row)` garde la
    PREMIÈRE — celle du lot, encore NULL partout. Toutes les calories du stock
    passeraient à NULL sans qu'aucune exception ne soit levée et sans qu'aucun
    test existant ne s'en aperçoive : c'est exactement la panne silencieuse
    que ce test rend impossible. On interdit le motif à la source plutôt que
    de courir après ses symptômes un site d'appel à la fois.
    """
    from pathlib import Path

    component = Path(repo.__file__).resolve().parent.parent
    offenders = []
    for path in component.rglob("*.py"):
        for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1):
            # Les commentaires ont le droit de nommer le piège — c'est même là
            # qu'il est expliqué. Seul le SQL réel est interdit.
            if line.lstrip().startswith("#"):
                continue
            if "SELECT b.*" in line:
                offenders.append(f"{path.relative_to(component).as_posix()}:{number}")
    assert offenders == []


def test_list_batches_for_product_still_resolves_kcal_after_m004(seeded_conn):
    """La régression que le piège ci-dessus aurait provoquée, prise sur le fait.

    Le lot porte `kcal_per_base_unit` à NULL ; l'article, lui, a un taux. C'est
    le taux de l'article qui doit ressortir — pas le NULL du lot.
    """
    seeded_conn.execute("UPDATE article SET kcal_per_base_unit = 3.5 WHERE id = 1")
    [row] = repo.list_batches_for_product(seeded_conn, 1)
    assert row["kcal_per_base_unit"] == 3.5


# --- lot 3 (amendement A2) : le lot peut porter sa propre nutrition ---------

def _batch(conn, *, article_kcal=None, product_reference_kcal=None,
           nutrition=None, article_macros=None):
    """Un produit, un article et un lot ouvert, avec la nutrition qu'on veut
    à chacun des trois étages de la cascade. Rend l'identifiant du lot.

    Écrit dans une base neuve, donc product_id == article_id == 1 : les tests
    de ce fichier tiennent déjà cette convention (voir `seeded_conn`).
    """
    repo.insert_location(conn, name="Placard", kind="pantry")
    product_id = repo.insert_product(conn, name="Article", base_unit="g")
    if product_reference_kcal is not None:
        repo.update_product_fields(
            conn, product_id, {"reference_kcal": product_reference_kcal})
    article_id = repo.insert_article(conn, product_id=product_id)
    fields = dict(article_macros or {})
    if article_kcal is not None:
        fields["kcal_per_base_unit"] = article_kcal
    if fields:
        repo.update_article_fields(conn, article_id, fields)
    return repo.insert_batch(
        conn, article_id=article_id, location_id=1, quantity=500.0,
        entered_at="2026-08-21T18:00:00", nutrition=nutrition)


def test_the_cascade_reads_the_article_when_the_batch_says_nothing(conn):
    """Tout ce qui existe se lit exactement comme avant."""
    _batch(conn, article_kcal=2.5)
    assert repo.list_batches_for_product(conn, 1)[0]["kcal_per_base_unit"] == 2.5


def test_the_cascade_falls_back_to_the_product(conn):
    _batch(conn, article_kcal=None, product_reference_kcal=0.52)
    assert repo.list_batches_for_product(conn, 1)[0]["kcal_per_base_unit"] == 0.52


def test_the_batch_wins_over_the_article_and_the_product(conn):
    """Deux cuissons de la même recette n'ont pas la même valeur : l'article
    est partagé, le lot ne l'est pas."""
    _batch(conn, article_kcal=2.5, product_reference_kcal=0.52,
           nutrition={"kcal_per_base_unit": 180.0, "proteins": 9.0})
    row = repo.list_batches_for_product(conn, 1)[0]
    assert row["kcal_per_base_unit"] == 180.0
    assert row["proteins"] == 9.0


def test_a_batch_null_macro_still_reads_the_article(conn):
    """La cascade est par COLONNE, pas par ligne."""
    _batch(conn, nutrition={"kcal_per_base_unit": 180.0},
           article_macros={"proteins": 0.09})
    row = repo.list_batches_for_product(conn, 1)[0]
    assert row["kcal_per_base_unit"] == 180.0
    assert row["proteins"] == 0.09


def test_the_batch_star_no_longer_shadows_the_cascade(conn):
    """Régression : `SELECT b.*` ramenait deux colonnes du même nom, et
    dict(sqlite3.Row) gardait la première — donc le NULL du lot."""
    _batch(conn, article_kcal=2.5)
    row = repo.list_batches_for_product(conn, 1)[0]
    assert row["kcal_per_base_unit"] == 2.5
    assert list(row).count("kcal_per_base_unit") == 1


def test_stock_rows_reads_the_same_cascade(conn):
    _batch(conn, nutrition={"kcal_per_base_unit": 180.0})
    assert repo.stock_rows(conn)[0]["kcal_per_base_unit"] == 180.0


def test_insert_batch_freezes_the_nutrition_it_is_given(conn):
    batch_id = _batch(conn, nutrition={"kcal_per_base_unit": 180.0, "salt": 0.9})
    row = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
    assert row["kcal_per_base_unit"] == 180.0
    assert row["salt"] == 0.9
    assert row["fiber"] is None      # ce qui n'est pas dit reste inconnu, pas zéro


def test_insert_batch_without_nutrition_is_unchanged(conn):
    batch_id = _batch(conn)
    row = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
    assert all(row[column] is None for column in NUTRITION_COLUMNS)


def test_insert_batch_ignores_a_key_that_is_not_a_nutrient(conn):
    """`nutrition` vient d'un calcul de recette, pas d'un formulaire : on le
    filtre sur les neuf colonnes connues plutôt que de laisser une clé
    inventée atteindre un INSERT."""
    batch_id = _batch(conn, nutrition={"kcal_per_base_unit": 180.0, "remaining": 0.0})
    row = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
    assert row["kcal_per_base_unit"] == 180.0
    assert row["remaining"] == 500.0          # la quantité n'a pas été écrasée


def test_resolve_kcal_rate_prefers_the_batch(conn):
    """Le pendant Python de la cascade SQL, pour les appelants qui tiennent
    déjà leurs lignes en main. Les deux doivent dire la même chose."""
    _batch(conn, article_kcal=2.5, product_reference_kcal=0.52,
           nutrition={"kcal_per_base_unit": 180.0})
    article = repo.get_article(conn, 1)
    batch = conn.execute("SELECT * FROM batch WHERE id = 1").fetchone()
    assert repo.resolve_kcal_rate(conn, article, batch=batch) == 180.0
    assert repo.resolve_kcal_rate(conn, article) == 2.5


def test_resolve_kcal_rate_falls_through_a_silent_batch(conn):
    _batch(conn, article_kcal=2.5)
    article = repo.get_article(conn, 1)
    batch = conn.execute("SELECT * FROM batch WHERE id = 1").fetchone()
    assert repo.resolve_kcal_rate(conn, article, batch=batch) == 2.5


def test_batch_macro_rates_is_a_per_column_cascade(conn):
    # Des lignes complètes, comme celles que les appelants tiennent vraiment :
    # une colonne absente doit rester une KeyError, pas devenir un None muet.
    batch = {column: None for column in MACRO_COLUMNS} | {"proteins": 9.0}
    article = {column: 0.5 for column in MACRO_COLUMNS} | {"proteins": 0.09,
                                                           "salt": 0.001}
    rates = repo.batch_macro_rates(batch, article)
    assert rates["proteins"] == 9.0        # le lot l'emporte
    assert rates["salt"] == 0.001          # le lot se tait, l'article répond
    assert set(rates) == set(MACRO_COLUMNS)


def test_batch_macro_rates_without_a_batch_reads_the_article(conn):
    article = {column: 0.5 for column in MACRO_COLUMNS}
    assert repo.batch_macro_rates(None, article) == article


def test_a_batch_zero_is_not_a_batch_silence(conn):
    """`0.0` est une mesure, `NULL` est une absence. Un plat sans sel titre
    zéro gramme de sel ; il ne titre pas « demande à l'article »."""
    _batch(conn, nutrition={"salt": 0.0}, article_macros={"salt": 0.001})
    assert repo.list_batches_for_product(conn, 1)[0]["salt"] == 0.0


def test_manual_portion_is_writable_through_update_product(conn):
    """`NULL` est l'effacement : le produit repasse à la médiane apprise."""
    product_id = repo.insert_product(conn, name="Riz", base_unit="g")
    assert repo.get_product(conn, product_id)["manual_portion"] is None

    repo.update_product_fields(conn, product_id, {"manual_portion": 45.0})
    assert repo.get_product(conn, product_id)["manual_portion"] == 45.0

    repo.update_product_fields(conn, product_id, {"manual_portion": None})
    assert repo.get_product(conn, product_id)["manual_portion"] is None


def test_article_off_raw_returns_the_stored_record_or_none(conn):
    product_id = repo.insert_product(conn, name="Yaourt", base_unit="g")
    with_raw = repo.insert_article(conn, product_id=product_id,
                                   off_raw='{"product_name": "Yaourt"}')
    without = repo.insert_article(conn, product_id=product_id)

    assert repo.article_off_raw(conn, with_raw) == '{"product_name": "Yaourt"}'
    assert repo.article_off_raw(conn, without) is None
    assert repo.article_off_raw(conn, 999) is None


def test_max_net_quantity_is_the_largest_pack_known_for_the_product(conn):
    """Un même riz existe en 500 g et en 1 kg : 800 g reste une portion
    (indigeste), pas une faute de saisie. C'est le PLUS GRAND paquet connu
    qui borne, jamais le premier trouvé ni le lot FIFO."""
    product_id = repo.insert_product(conn, name="Riz", base_unit="g")
    repo.insert_article(conn, product_id=product_id, net_quantity=1000)
    repo.insert_article(conn, product_id=product_id, net_quantity=500)
    assert repo.max_net_quantity(conn, product_id) == 1000.0

    unknown = repo.insert_product(conn, name="Sel", base_unit="g")
    repo.insert_article(conn, product_id=unknown)
    assert repo.max_net_quantity(conn, unknown) is None

    empty = repo.insert_product(conn, name="Poivre", base_unit="g")
    assert repo.max_net_quantity(conn, empty) is None
