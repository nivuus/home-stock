"""Le calcul des 108 lots, avant toute écriture.

Toute cette partie est pure : elle reçoit des lignes et rend des lots. Ce qui
touche SQLite vient ensuite, et la séparation est ce qui permet de tester les
sept prix aberrants sans ouvrir une base.
"""
import pytest

from custom_components.home_stock.grocy.units import base_unit
from custom_components.home_stock.import_grocy import import_catalog
from custom_components.home_stock.import_grocy_stock import (
    CatalogueEntry,
    Locations,
    StockImportError,
    import_stock,
    plan_batches,
)
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations

# Le jour de la bascule, tel que les fixtures l'ont figé.
AUJOURD_HUI = "2026-08-21"
# La date de l'import du catalogue par le lot 0. Un produit Grocy créé après
# n'est PAS au catalogue de home_stock : c'est le Sorbet Fraise, et c'est ce
# que le rejeu du catalogue (geste 6) rattrape.
IMPORT_LOT0 = "2026-08-19"

# Les emplacements de home_stock ne portent pas les identifiants de Grocy :
# l'import du lot 0 les a créés par NOM. Le décalage est volontaire ici, pour
# qu'un test qui confondrait les deux échoue.
_LOCATIONS_HOME = {2: 102, 3: 103, 4: 104, 5: 105}


def _catalogue(grocy_reel, *, cree_avant: str | None = None
               ) -> dict[int, CatalogueEntry]:
    unites = {q["id"]: q["name"] for q in grocy_reel["quantity_units"]}
    catalogue: dict[int, CatalogueEntry] = {}
    for numero, ligne in enumerate(grocy_reel["products"]):
        if not ligne["active"]:
            continue
        if cree_avant and (ligne["row_created_timestamp"] or "") >= cree_avant:
            continue
        mappee = base_unit(unites.get(ligne["qu_id_stock"], "?"))
        if mappee is None:
            continue
        catalogue[ligne["id"]] = CatalogueEntry(
            product_id=1000 + numero,
            article_id=2000 + numero,
            name=ligne["name"],
            base_unit=mappee[0],
            default_location_id=_LOCATIONS_HOME.get(ligne["location_id"]),
        )
    return catalogue


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "home_stock.db"))
    database.connect()
    with database.write() as conn:
        apply_migrations(conn)
    yield database
    database.close()


@pytest.fixture
def db_catalogue(db, grocy_reel_db):
    """La base après le REJEU du catalogue — geste 6 de la procédure.

    L'import du stock ne tourne jamais sur une base vide : il tourne après
    l'import du catalogue, et c'est cet ordre-là qu'on teste. Un catalogue
    fabriqué à la main dans le test ne prouverait rien de cet ordre.
    """
    import_catalog(db, grocy_reel_db, apply=True)
    return db


@pytest.fixture
def catalogue_reel(grocy_reel) -> dict[int, CatalogueEntry]:
    """Le catalogue de home_stock APRÈS le rejeu de l'import du catalogue.

    C'est l'état dans lequel l'import du stock est lancé : le geste 6 de la
    procédure rejoue `import_grocy_catalog` en tête de bascule, précisément
    pour que les 108 lots aient tous leur produit. Les 300 produits actifs
    dont l'unité de stock se convertit y sont, Sorbet Fraise compris.
    """
    return _catalogue(grocy_reel)


@pytest.fixture
def catalogue_avant_rejeu(grocy_reel) -> dict[int, CatalogueEntry]:
    """Le catalogue tel qu'il est AUJOURD'HUI, avant le rejeu : 299 produits.

    Le Sorbet Fraise, créé le 21 août à 18 h 54, en est absent. C'est la cible
    mobile, et c'est le seul lot des 108 qui ne se résout pas contre lui.
    """
    return _catalogue(grocy_reel, cree_avant=IMPORT_LOT0)


@pytest.fixture
def locations_reelles() -> Locations:
    """Les quatre emplacements de Grocy, appariés par nom au lot 0.

    L'identifiant 1 n'y est PAS : il a été supprimé du référentiel de Grocy,
    et deux lots le désignent encore. C'est le troisième cran de la cascade.
    """
    return Locations(by_grocy_id=dict(_LOCATIONS_HOME), fallback_id=105)


@pytest.fixture
def lignes_reelles(grocy_reel) -> list[dict]:
    """Les 108 lignes de stock, jointes à leur produit comme la requête du
    §8.1 le fait : `s` pour stock, `prod` pour products, aucun alias `b`."""
    produits = {p["id"]: p for p in grocy_reel["products"]}
    unites = {q["id"]: q["name"] for q in grocy_reel["quantity_units"]}
    lignes = []
    for ligne in grocy_reel["stock"]:
        produit = produits[ligne["product_id"]]
        lignes.append({**ligne,
                       "unit": unites.get(produit["qu_id_stock"], "?"),
                       "product_name": produit["name"]})
    return lignes


def _lot(*, product_id=7, amount=1.0, unit="g", best_before="2026-12-31",
         price=None, note=None, open=0, opened_date=None,
         purchased="2026-05-02", location_id=2, stock_id=900,
         product_name="Mozzarella"):
    """Une ligne de stock de Grocy, jointe à son produit."""
    return {"id": stock_id, "product_id": product_id, "amount": amount,
            "best_before_date": best_before, "purchased_date": purchased,
            "price": price, "open": open, "opened_date": opened_date,
            "location_id": location_id, "note": note,
            "row_created_timestamp": "2026-05-02 10:00:00",
            "unit": unit, "product_name": product_name}


def test_the_hundred_and_eight_batches_resolve_after_the_replay(
        lignes_reelles, catalogue_reel, locations_reelles):
    """Cent-huit, pas cent-sept.

    La spec (§ 8.1) et le plan disent l'un « 107 lots sur 108 se résolvent »,
    l'autre « un lot non résolu ARRÊTE l'import », et les deux à la fois sont
    impossibles : si le 108ᵉ arrête tout, l'import ne rend pas 107 lots, il ne
    rend rien. Les deux phrases décrivent en fait deux MOMENTS.

    Le contrat retenu est celui du contrôle C1, qui attend 108 chez Grocy et
    108 chez nous : l'import tourne APRÈS le rejeu du catalogue (geste 6), et
    les 108 se résolvent. Le « 107 sur 108 » de la spec est une mesure de
    l'état d'aujourd'hui, épinglée par le test suivant. Amendement A4 du § 22.
    """
    lots, _ = plan_batches(lignes_reelles, catalogue_reel, locations_reelles,
                           today=AUJOURD_HUI)
    assert len(lots) == 108


def test_today_one_batch_of_the_hundred_and_eight_stops_the_import(
        lignes_reelles, catalogue_avant_rejeu, locations_reelles):
    """LE seul arrêt dur du §8, et il se déclenche pour de vrai aujourd'hui.

    107 des 108 lots se résolvent contre le catalogue actuel ; le 108ᵉ est le
    Sorbet Fraise créé le 21 août à 18 h 54. Lancer l'import sans avoir rejoué
    le catalogue s'arrête là, en le nommant — c'est ce qui rend le geste 6
    obligatoire au lieu de recommandé.
    """
    resolus = [ligne for ligne in lignes_reelles
               if ligne["product_id"] in catalogue_avant_rejeu]
    assert len(resolus) == 107
    with pytest.raises(StockImportError) as err:
        plan_batches(lignes_reelles, catalogue_avant_rejeu, locations_reelles,
                     today=AUJOURD_HUI)
    assert "350" in str(err.value)
    assert "import_grocy_catalog" in str(err.value)


def test_a_batch_without_a_product_stops_the_import(catalogue_reel,
                                                    locations_reelles):
    """S'il existe après le rejeu, quelqu'un a écrit dans Grocy pendant la
    bascule, et alors rien de ce qui suit n'a de valeur."""
    with pytest.raises(StockImportError) as err:
        plan_batches([_lot(product_id=99999)], catalogue_reel,
                     locations_reelles, today=AUJOURD_HUI)
    assert "99999" in str(err.value)


def test_kilograms_become_grams(catalogue_reel, locations_reelles):
    lots, _ = plan_batches([_lot(product_id=7, amount=1.5, unit="kg")],
                           catalogue_reel, locations_reelles, today=AUJOURD_HUI)
    assert lots[0].quantity == 1500.0
    assert lots[0].base_unit == "g"


def test_no_unit_is_unknown_on_the_real_data(lignes_reelles, catalogue_reel,
                                             locations_reelles):
    """0 unité inconnue, 0 divergence entre l'unité du lot et l'unité de base
    du produit : c'est ce que la spec a mesuré, et c'est ce qui rend
    reference_kcal juste sans reconversion."""
    _, anomalies = plan_batches(lignes_reelles, catalogue_reel,
                                locations_reelles, today=AUJOURD_HUI)
    assert not [a for a in anomalies if "unité" in a]


def test_a_unit_that_diverges_from_the_catalogue_is_refused(catalogue_reel,
                                                            locations_reelles):
    """Le contraire du test précédent, sur une ligne fabriquée. Convertir des
    kilogrammes dans un produit stocké à la pièce écrirait 1 500 « pièces »
    de tomates. Aucune devinette : le lot n'entre pas, et l'anomalie nomme
    les deux unités."""
    lots, anomalies = plan_batches(
        [_lot(product_id=3, amount=1.5, unit="kg", product_name="Oignon rouge")],
        catalogue_reel, locations_reelles, today=AUJOURD_HUI)
    assert lots == []
    assert len([a for a in anomalies if "unité" in a]) == 1
    assert "piece" in anomalies[0] and "g" in anomalies[0]


def test_floating_dust_enters_closed_not_ignored(catalogue_reel,
                                                 locations_reelles):
    """Le lot #537 (« Fromage fouetté ») porte 5,55e-17. Sous 0,001 unité de
    base il entre avec remaining = 0 et un closed_at. Un lot IGNORÉ serait un
    écart de comptage au contrôle C1 — ce n'est pas la même chose."""
    lots, _ = plan_batches([_lot(product_id=7, amount=5.55e-17)],
                           catalogue_reel, locations_reelles, today=AUJOURD_HUI)
    assert len(lots) == 1
    assert lots[0].quantity == 0.0
    assert lots[0].closed is True


def test_fractional_pieces_are_never_rounded(catalogue_reel, locations_reelles):
    """0,08 concombre et 12,875 œufs existent. L'arrondi est un geste
    d'affichage, jamais de stockage — le lot 0 stocke des REAL pour ça."""
    for quantite in (0.08, 12.875, 5.98):
        lots, _ = plan_batches(
            [_lot(product_id=3, amount=quantite, unit="Pièce")],
            catalogue_reel, locations_reelles, today=AUJOURD_HUI)
        assert lots[0].quantity == quantite


def test_the_eighteen_fractional_piece_batches_on_real_data(
        lignes_reelles, catalogue_reel, locations_reelles):
    lots, _ = plan_batches(lignes_reelles, catalogue_reel, locations_reelles,
                           today=AUJOURD_HUI)
    fractionnaires = [ligne for ligne in lots
                      if ligne.base_unit == "piece" and ligne.quantity != int(ligne.quantity)]
    assert len(fractionnaires) == 18


def test_the_sentinel_becomes_null(catalogue_reel, locations_reelles):
    lots, _ = plan_batches([_lot(product_id=7, best_before="2999-12-31")],
                           catalogue_reel, locations_reelles, today=AUJOURD_HUI)
    assert lots[0].best_before is None


def test_the_ten_sentinels_and_the_ninety_eight_real_dates(
        lignes_reelles, catalogue_reel, locations_reelles):
    lots, _ = plan_batches(lignes_reelles, catalogue_reel, locations_reelles,
                           today=AUJOURD_HUI)
    assert len([ligne for ligne in lots if ligne.best_before is None]) == 10
    assert len([ligne for ligne in lots if ligne.best_before is not None]) == 98


def test_the_six_already_expired_batches_come_in_as_they_are(
        lignes_reelles, catalogue_reel, locations_reelles):
    """Ce sont de vrais produits périmés dans un vrai placard, et
    binary_sensor.home_stock_expirations doit s'allumer dessus le premier
    jour. Les masquer serait mentir au propriétaire sur son frigo."""
    lots, _ = plan_batches(lignes_reelles, catalogue_reel, locations_reelles,
                           today=AUJOURD_HUI)
    perimes = [ligne for ligne in lots if ligne.best_before and ligne.best_before < AUJOURD_HUI]
    assert len(perimes) == 6


def test_a_batch_worth_more_than_twenty_euros_loses_its_price(catalogue_reel,
                                                              locations_reelles):
    lots, anomalies = plan_batches(
        [_lot(product_id=7, amount=1487, price=2.45, note="Ticket Carrefour")],
        catalogue_reel, locations_reelles, today=AUJOURD_HUI)
    assert lots[0].price_per_base_unit is None
    assert any("2,45" in a or "2.45" in a for a in anomalies)


def test_a_price_is_never_zero_only_null(catalogue_reel, locations_reelles):
    """Règle du lot 0 §7.4 : zéro voudrait dire « mesuré à zéro », NULL veut
    dire « inconnu ». sensor.home_stock_stock_value publie unpriced_batches ;
    un prix inconnu est VISIBLE, un prix à zéro est invisible."""
    lots, _ = plan_batches([_lot(product_id=7, amount=1487, price=2.45)],
                           catalogue_reel, locations_reelles, today=AUJOURD_HUI)
    assert lots[0].price_per_base_unit != 0.0
    assert lots[0].price_per_base_unit is None


def test_a_price_recorded_as_zero_is_unknown_not_measured(catalogue_reel,
                                                          locations_reelles):
    """41 lignes de stock portent 0.0, et 44 portent NULL : chez Grocy, les
    deux veulent dire « pas de prix ». Recopier le 0.0 le ferait entrer dans
    la valeur du stock comme un prix MESURÉ à zéro, donc invisible."""
    lots, _ = plan_batches([_lot(product_id=7, amount=100, price=0.0)],
                           catalogue_reel, locations_reelles, today=AUJOURD_HUI)
    assert lots[0].price_per_base_unit is None


def test_the_seven_dropped_prices_and_the_sixteen_kept(
        lignes_reelles, catalogue_reel, locations_reelles):
    """7 lots portent 8 089 EUR des 8 140 EUR. Les autres pèsent 51 EUR : un
    chiffre petit et vrai plutôt qu'énorme et faux.

    Seize valorisés, pas cinquante-sept : sur les 108 lignes, 23 portent un
    prix strictement positif, 41 portent 0.0 et 44 portent NULL. Amendement
    A3 du § 22 — la valeur de 51 EUR de la spec est juste, son compte ne
    l'était pas.
    """
    lots, anomalies = plan_batches(lignes_reelles, catalogue_reel,
                                   locations_reelles, today=AUJOURD_HUI)
    values = [ligne for ligne in lots if ligne.price_per_base_unit is not None]
    assert len(values) == 16
    assert len([a for a in anomalies if "prix" in a.lower()]) == 7
    total = sum(ligne.quantity * ligne.price_per_base_unit for ligne in values)
    assert 45 <= total <= 60          # ~51 EUR, et surtout pas 8 140


def test_the_ninety_two_batches_without_a_usable_price(
        lignes_reelles, catalogue_reel, locations_reelles):
    """85 sans prix chez Grocy + les 7 écartés. C'est le compte que C4
    contrôlera, et il est nommé ici pour qu'un seul chiffre gouverne."""
    lots, _ = plan_batches(lignes_reelles, catalogue_reel, locations_reelles,
                           today=AUJOURD_HUI)
    assert len([ligne for ligne in lots if ligne.price_per_base_unit is None]) == 92


def test_the_boundary_is_a_ditch_not_a_line(catalogue_reel, locations_reelles):
    """Le lot le plus cher retenu vaut 13,80 EUR, le premier écarté en vaut
    46,68. Rien ne vit entre les deux."""
    garde, _ = plan_batches([_lot(product_id=3, amount=1, price=13.80,
                                  unit="Pièce")],
                            catalogue_reel, locations_reelles, today=AUJOURD_HUI)
    assert garde[0].price_per_base_unit == 13.80
    ecarte, _ = plan_batches([_lot(product_id=3, amount=1, price=47.0,
                                   unit="Pièce")],
                             catalogue_reel, locations_reelles, today=AUJOURD_HUI)
    assert ecarte[0].price_per_base_unit is None


def test_an_anomaly_quotes_the_note_word_for_word(catalogue_reel,
                                                  locations_reelles):
    """Les notes sont la PREUVE du défaut : quatre des sept portent le nom
    d'un autre produit que celui auquel le lot est attaché. Elles doivent se
    lire dans le rapport, parce que batch.note n'existe pas."""
    _, anomalies = plan_batches(
        [_lot(product_id=7, amount=1000, price=1.79,
              note="Ticket Carrefour 21/04/2026 — Fromage blanc 1kg (CORRIGÉ)")],
        catalogue_reel, locations_reelles, today=AUJOURD_HUI)
    assert any("Fromage blanc 1kg" in a for a in anomalies)


def test_the_location_cascade_in_its_three_cases(lignes_reelles, catalogue_reel,
                                                 locations_reelles):
    """29 lots sur 108 n'ont pas d'emplacement résoluble : 27 tombent sur le
    default_location du produit, 2 sur « Autre » (ils pointent l'emplacement
    id 1, SUPPRIMÉ du référentiel — le même défaut que l'unité id 1 que
    debloquer_unites.py a dû réparer en août)."""
    lots, anomalies = plan_batches(lignes_reelles, catalogue_reel,
                                   locations_reelles, today=AUJOURD_HUI)
    assert all(ligne.location_id is not None for ligne in lots)
    replis = [a for a in anomalies if "Autre" in a]
    assert len(replis) == 2
    assert any("Moutarde Burger Complet" in a for a in replis)
    assert any("Beurre Oméga-3" in a for a in replis)


def test_no_batch_is_ever_refused_for_its_location(lignes_reelles,
                                                   catalogue_reel,
                                                   locations_reelles):
    """Un paquet mal rangé reste un paquet qu'on possède."""
    lots, _ = plan_batches(lignes_reelles, catalogue_reel, locations_reelles,
                           today=AUJOURD_HUI)
    assert len(lots) == 108


def test_an_open_batch_without_an_open_date_uses_its_entry_date(
        catalogue_reel, locations_reelles):
    """Un seul lot est ouvert dans la base, et celui-là porte bien une date
    d'ouverture. La ligne fabriquée ici couvre le cas contraire, qui est
    celui d'un import futur : ouvert, sans date."""
    lots, _ = plan_batches(
        [_lot(product_id=7, open=1, opened_date=None, purchased="2026-05-02")],
        catalogue_reel, locations_reelles, today=AUJOURD_HUI)
    assert lots[0].opened_at.startswith("2026-05-02")


def test_a_closed_batch_has_no_open_date(catalogue_reel, locations_reelles):
    lots, _ = plan_batches([_lot(product_id=7, open=0)],
                           catalogue_reel, locations_reelles, today=AUJOURD_HUI)
    assert lots[0].opened_at is None


def test_opening_never_recomputes_the_best_before(catalogue_reel,
                                                  locations_reelles):
    """La règle du lot 0 §7.6 (avancer la DLC de days_after_opening jours)
    s'applique au GESTE d'ouverture, pas à la constatation qu'un paquet est
    ouvert depuis six mois. L'appliquer ici donnerait une DLC calculée depuis
    une date d'entrée : faux dans les deux sens."""
    lots, _ = plan_batches(
        [_lot(product_id=7, open=1, best_before="2026-09-30",
              purchased="2026-05-02")], catalogue_reel,
        locations_reelles, today=AUJOURD_HUI)
    assert lots[0].best_before == "2026-09-30"


def test_every_batch_carries_a_grocy_reference(lignes_reelles, catalogue_reel,
                                               locations_reelles):
    lots, _ = plan_batches(lignes_reelles, catalogue_reel, locations_reelles,
                           today=AUJOURD_HUI)
    refs = {ligne.external_ref for ligne in lots}
    assert len(refs) == 108
    assert all(r.startswith("grocy:stock:") for r in refs)


# --- écriture ---------------------------------------------------------------
#
# Tous les tests qui suivent traversent un import complet et portent donc
# --timeout=60 : Database._lock n'est PAS réentrant, deux db.write() imbriqués
# figent le processus sans lever, et un test gelé n'échoue jamais tout seul.

def _empreinte(db) -> list[tuple]:
    """De quoi dire qu'un second passage n'a rien changé."""
    conn = db.read()
    return [tuple(row) for row in conn.execute(
        "SELECT id, article_id, location_id, remaining, initial, best_before,"
        "       entered_at, opened_at, price_per_base_unit, closed_at,"
        "       external_ref FROM batch ORDER BY id")]


def test_a_dry_run_writes_nothing(db_catalogue, grocy_reel_db):
    rapport = import_stock(db_catalogue, grocy_reel_db, apply=False)
    assert rapport.batches == 108
    assert repo.stock_rows(db_catalogue.read()) == []


def test_a_dry_run_reports_the_same_anomalies_as_a_real_run(db_catalogue,
                                                            grocy_reel_db):
    """C'est tout l'intérêt de le lancer avant : le rapport de simulation doit
    être celui qu'on lira après. import_grocy.py du lot 0 tient déjà cette
    promesse ; elle ne se relâche pas ici."""
    sec = import_stock(db_catalogue, grocy_reel_db, apply=False)
    vrai = import_stock(db_catalogue, grocy_reel_db, apply=True)
    assert sec.anomalies == vrai.anomalies


def test_apply_writes_a_hundred_and_eight_batches(db_catalogue, grocy_reel_db):
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    conn = db_catalogue.read()
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM batch WHERE external_ref IS NOT NULL"
    ).fetchone()["n"] == 108


def test_every_batch_carries_its_grocy_reference(db_catalogue, grocy_reel_db):
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    refs = {row["external_ref"] for row in db_catalogue.read().execute(
        "SELECT external_ref FROM batch WHERE external_ref IS NOT NULL")}
    assert all(ref.startswith("grocy:stock:") for ref in refs)
    assert len(refs) == 108        # l'index unique partiel tient


def test_one_purchase_movement_per_batch(db_catalogue, grocy_reel_db):
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    conn = db_catalogue.read()
    lignes = conn.execute(
        "SELECT idempotency_key FROM movement WHERE reason = 'purchase'"
        " AND idempotency_key LIKE 'grocy:stock:%'").fetchall()
    assert len(lignes) == 108


def test_the_three_totals_do_not_move(db_catalogue, grocy_reel_db):
    """C6, prouvé mécaniquement. Un purchase n'entre jamais dans
    totals_between : ni kcal_total, ni cost_total, ni cost_waste_total."""
    avant = repo.totals_between(db_catalogue.read())
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    apres = repo.totals_between(db_catalogue.read())
    assert avant == apres


def test_entry_movements_carry_no_kcal_and_no_cost(db_catalogue, grocy_reel_db):
    """Aucun capteur ne les lit sur une entrée, et un chiffre que personne ne
    lit finit par être cru."""
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    for row in db_catalogue.read().execute(
            "SELECT kcal, cost FROM movement WHERE reason = 'purchase'"
            " AND idempotency_key LIKE 'grocy:stock:%'"):
        assert row["kcal"] is None and row["cost"] is None


def test_a_second_run_changes_nothing(db_catalogue, grocy_reel_db):
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    empreinte = _empreinte(db_catalogue)
    second = import_stock(db_catalogue, grocy_reel_db, apply=True)
    assert second.batches == 0
    assert second.skipped == 108
    assert _empreinte(db_catalogue) == empreinte


def test_a_replay_does_not_undo_a_real_consumption(db_catalogue, grocy_reel_db):
    """LE test de la rejouabilité. On a mangé depuis l'import ; un second
    passage qui remettrait remaining = initial défferait une consommation
    réelle SANS LAISSER DE TRACE — et movement est en ajout seul, donc on ne
    pourrait même pas la retrouver."""
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    with db_catalogue.write() as conn:
        lot = conn.execute(
            "SELECT id, remaining FROM batch WHERE external_ref IS NOT NULL"
            " AND remaining > 10 ORDER BY id LIMIT 1").fetchone()
        repo.set_batch_remaining(conn, lot["id"], lot["remaining"] - 10)
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    apres = db_catalogue.read().execute(
        "SELECT remaining FROM batch WHERE id = ?", (lot["id"],)).fetchone()
    assert apres["remaining"] == lot["remaining"] - 10


def test_the_fridge_is_finally_a_fridge(db_catalogue, grocy_reel_db):
    """Défaut hérité du lot 0 : l'import du catalogue mappe location.kind sur
    is_freezer, et Grocy n'a pas de drapeau « réfrigérateur ». « Frigo » est
    donc enregistré en pantry dans la base de production. Corrigé ici PAR NOM
    EXACT, une seule ligne, et rapporté. Aucun autre nom n'est deviné."""
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    row = db_catalogue.read().execute(
        "SELECT kind FROM location WHERE name = 'Frigo'").fetchone()
    assert row["kind"] == "fridge"


def test_no_other_location_name_is_guessed(db_catalogue, grocy_reel_db):
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    kinds = {row["name"]: row["kind"] for row in db_catalogue.read().execute(
        "SELECT name, kind FROM location")}
    assert kinds["Congélateur"] == "freezer"
    assert kinds["Placard"] == "pantry"
    assert kinds["Autre"] == "pantry"


def test_the_import_never_opens_a_second_transaction(db_catalogue, grocy_reel_db):
    """Database._lock n'est pas réentrant : deux db.write() imbriqués figent
    le processus SANS lever. Ce test ne peut donc pas échouer proprement — il
    expire. C'est pour lui que --timeout=60 est sur toute la suite."""
    import_stock(db_catalogue, grocy_reel_db, apply=True)     # doit rendre la main


# --- conversions et courses -------------------------------------------------

def test_fifteen_pairs_become_fourteen_packagings(db_catalogue, grocy_reel_db):
    """30 lignes, 15 paires aller-retour : le sens inverse est le même fait
    écrit deux fois. Et « 1 Lot = 1 Pot » est écartée — les deux deviennent
    piece, facteur 1, c'est un no-op."""
    rapport = import_stock(db_catalogue, grocy_reel_db, apply=True)
    assert rapport.packagings == 14


def test_a_bottle_of_olive_oil_is_seven_hundred_and_fifty_millilitres(
        db_catalogue, grocy_reel_db):
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    row = db_catalogue.read().execute(
        "SELECT pk.base_quantity FROM packaging AS pk"
        " JOIN product AS prod ON prod.id = pk.target_id"
        " WHERE pk.scope = 'product' AND pk.name = 'Bouteille'"
        "   AND prod.name LIKE 'Huile d%olive%'").fetchone()
    assert row["base_quantity"] == 750.0


def test_a_piece_packaging_carries_grams(db_catalogue, grocy_reel_db):
    """« Houmous bio Pascalou 160g » : 1 Pièce = 160 g."""
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    row = db_catalogue.read().execute(
        "SELECT pk.base_quantity FROM packaging AS pk"
        " JOIN product AS prod ON prod.id = pk.target_id"
        " WHERE pk.name = 'Pièce' AND prod.name LIKE 'Houmous%'").fetchone()
    assert row["base_quantity"] == 160.0


def test_a_no_op_conversion_is_dropped(db_catalogue, grocy_reel_db):
    """« 1 Lot = 1 Pot » sur le yaourt aux fruits : Lot et Pot deviennent tous
    deux piece, facteur 1. Une ligne packaging qui dit « une pièce vaut une
    pièce » est du bruit."""
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    assert db_catalogue.read().execute(
        "SELECT COUNT(*) AS n FROM packaging WHERE name = 'Lot'"
    ).fetchone()["n"] == 0


def test_an_existing_packaging_is_never_overwritten(db_catalogue, grocy_reel_db):
    """Le lot 1 a pu en créer depuis Open Food Facts, et une mesure
    d'emballage vaut mieux qu'une conversion de 2026."""
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    with db_catalogue.write() as conn:
        conn.execute("UPDATE packaging SET base_quantity = 700"
                     " WHERE name = 'Bouteille'")
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    assert db_catalogue.read().execute(
        "SELECT base_quantity FROM packaging WHERE name = 'Bouteille' LIMIT 1"
    ).fetchone()["base_quantity"] == 700


def test_only_the_nine_open_shopping_rows_come_over(db_catalogue, grocy_reel_db):
    """16 lignes cochées : une course faite n'a pas d'après."""
    rapport = import_stock(db_catalogue, grocy_reel_db, apply=True)
    assert rapport.list_items == 9
    assert len(repo.list_items(db_catalogue.read())) == 9


def test_each_line_gets_a_manual_claim(db_catalogue, grocy_reel_db):
    """Leur origine réelle est inconnaissable, et `manual` est la seule des
    quatre origines qui ne prétende rien."""
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    origines = {row["origin"] for row in db_catalogue.read().execute(
        "SELECT origin FROM shopping_list_claim")}
    assert origines == {"manual"}


def test_the_four_notes_travel_as_they_are(db_catalogue, grocy_reel_db):
    """Quatre, pas trois : trois sont des prescriptions médicamenteuses, la
    quatrième dit « bouteille ~1L » sur le savon noir. Amendement A5 du § 22 —
    la spec a compté les prescriptions, pas les notes. La colonne est faite
    pour les unes comme pour l'autre."""
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    avec_note = [i for i in repo.list_items(db_catalogue.read()) if i["note"]]
    assert len(avec_note) == 4
    assert any("2x/semaine" in i["note"] for i in avec_note)


def test_the_unique_open_product_index_passes_without_arbitration(
        db_catalogue, grocy_reel_db):
    """Les 9 produits sont actifs et distincts : idx_list_open_product tient
    sans qu'on ait à trancher quoi que ce soit."""
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    ids = [i["product_id"] for i in repo.list_items(db_catalogue.read())]
    assert len(ids) == len(set(ids)) == 9


def test_a_sachet_and_a_paquet_are_both_pieces(db_catalogue, grocy_reel_db):
    """« Cerneaux de noix » : Sachet contre Paquet. Les deux deviennent piece,
    facteur 1, aucune conversion — et surtout pas une division."""
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    ligne = next(i for i in repo.list_items(db_catalogue.read())
                 if "Cerneaux" in (i.get("product_name") or ""))
    assert ligne["quantity"] == 1.0


def test_a_quantity_in_grams_stays_in_grams(db_catalogue, grocy_reel_db):
    """« Savon noir liquide », 1 000 g : la ligne de courses est dans l'unité
    de base du produit, comme partout ailleurs dans home_stock."""
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    ligne = next(i for i in repo.list_items(db_catalogue.read())
                 if "Savon noir" in (i.get("product_name") or ""))
    assert ligne["quantity"] == 1000.0


def test_a_second_run_adds_no_second_list_line(db_catalogue, grocy_reel_db):
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    second = import_stock(db_catalogue, grocy_reel_db, apply=True)
    assert second.list_items == 0
    assert len(repo.list_items(db_catalogue.read())) == 9


def test_no_shopping_session_and_no_store_are_invented(db_catalogue,
                                                       grocy_reel_db):
    """shopping_locations est VIDE chez Grocy : rien pour amorcer l'ordre des
    rayons du lot 4, et on n'en fabrique pas."""
    import_stock(db_catalogue, grocy_reel_db, apply=True)
    conn = db_catalogue.read()
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM shopping_session").fetchone()["n"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM store").fetchone()["n"] == 0


def test_a_dry_run_creates_neither_packaging_nor_list_line(db_catalogue,
                                                           grocy_reel_db):
    rapport = import_stock(db_catalogue, grocy_reel_db, apply=False)
    assert rapport.packagings == 14 and rapport.list_items == 9
    conn = db_catalogue.read()
    assert conn.execute("SELECT COUNT(*) AS n FROM packaging").fetchone()["n"] == 0
    assert repo.list_items(conn) == []
