"""L'appariement rejoué sur les lignes réelles, avec les seuils du lot 1.

Les deux fixtures sont VRAIES : `products.json` est le catalogue de 299 produits
actifs et `ingredients.json` les 250 textes d'ingrédients distincts de
`recipes_pos`, chacun avec le produit qu'un humain lui a réellement associé
dans Grocy. Ils ont été extraits une fois, en lecture seule, depuis une COPIE de
`grocy.db` — jamais celle en production. Aucun script de génération n'est
versionné.

Cette vérité de terrain est ce qui donne un sens à la mesure : on ne compare pas
l'appariement à lui-même, on le compare à ce qu'un humain a tranché.
"""
import json
from pathlib import Path

import pytest

from custom_components.home_stock.application import (
    StockManager,
    resolve_ingredient_match,
)
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "recipes"
PRODUCTS = json.loads((FIXTURES / "products.json").read_text(encoding="utf-8"))
LINES = json.loads((FIXTURES / "ingredients.json").read_text(encoding="utf-8"))
NAMES = {product["id"]: product["name"] for product in PRODUCTS}


@pytest.fixture
def manager(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.connect()
    with db.write() as conn:
        apply_migrations(conn)
    yield StockManager(db)
    db.close()


@pytest.fixture
def conn(manager):
    with manager.db.write() as c:
        yield c


def _catalogue(conn, names):
    """Insère `names` comme produits et rend la liste attendue par le matching."""
    products = []
    for name in names:
        products.append({"id": repo.insert_product(conn, name=name, base_unit="g"),
                         "name": name})
    return products


def _recipe_line(conn, raw_text):
    recipe_id = repo.insert_recipe(conn, name="R", source="manual",
                                   created_at="2026-08-21T18:00:00")
    return repo.insert_ingredient(conn, recipe_id=recipe_id, position=1,
                                  raw_text=raw_text)


# --- l'ordre de résolution --------------------------------------------------

def test_a_confirmed_alias_beats_a_higher_scoring_preselect(conn):
    """Chaque arbitrage humain vaut pour toujours, y compris contre un score
    supérieur : c'est ce qui rend le travail décroissant."""
    products = _catalogue(conn, ["Crème fraîche", "Coriandre"])
    creme, coriandre = products[0]["id"], products[1]["id"]

    state, product_id, _, _ = resolve_ingredient_match(
        conn, raw_text="crème fraîche", ingredient_name=None, products=products)
    assert (state, product_id) == ("auto", creme)

    repo.upsert_alias(conn, normalised="creme fraiche", product_id=coriandre,
                      created_at="2026-08-21T18:00:00")
    state, product_id, score, candidates = resolve_ingredient_match(
        conn, raw_text="crème fraîche", ingredient_name=None, products=products)
    assert (state, product_id, score, candidates) == ("confirmed", coriandre, 1.0, [])


def test_the_quantity_is_stripped_before_scoring(conn):
    """« 2 cs d'huile d'olive » doit trouver « Huile d'olive » : c'est la
    quantité en tête qui rend le texte brut inutilisable tel quel."""
    products = _catalogue(conn, ["Huile d'olive", "Vinaigre"])
    state, product_id, _, _ = resolve_ingredient_match(
        conn, raw_text="2 cs d'huile d'olive", ingredient_name=None, products=products)
    assert (state, product_id) == ("auto", products[0]["id"])


def test_an_unmatched_line_offers_its_candidates_rather_than_nothing(conn):
    """`unmatched` n'est pas une impasse : l'écran d'appariement a besoin des
    cinq meilleurs pour que l'humain tranche en un appui."""
    products = _catalogue(conn, ["Crème fraîche", "Menthe fraîche", "Poivron"])
    state, product_id, score, candidates = resolve_ingredient_match(
        conn, raw_text="coriandre fraîche", ingredient_name=None, products=products)
    assert (state, product_id, score) == ("unmatched", None, None)
    assert [c.name for c in candidates][:2] == ["Crème fraîche", "Menthe fraîche"]


# --- ce que l'appariement automatique n'a PAS le droit de faire -------------

def test_an_auto_match_never_writes_an_alias(conn):
    """Un appariement automatique faux deviendrait permanent et contaminerait
    toutes les recettes suivantes — c'est le ré-appariement par nom qui a
    produit 35 doublons dans Grocy en avril 2026."""
    products = _catalogue(conn, ["Ketchup"])
    state, _, _, _ = resolve_ingredient_match(
        conn, raw_text="ketchup", ingredient_name=None, products=products)
    assert state == "auto"
    assert conn.execute("SELECT COUNT(*) c FROM ingredient_alias").fetchone()["c"] == 0


def test_confirming_by_hand_writes_the_alias_once(manager):
    with manager.db.write() as conn:
        [product] = _catalogue(conn, ["Coriandre"])
        ingredient_id = _recipe_line(conn, "coriandre fraîche")

    manager.match_ingredient(ingredient_id, product_id=product["id"],
                             state="confirmed", create_alias=True)
    manager.match_ingredient(ingredient_id, product_id=product["id"],
                             state="confirmed", create_alias=True)

    read = manager.db.read()
    assert read.execute("SELECT COUNT(*) c FROM ingredient_alias").fetchone()["c"] == 1
    alias = read.execute("SELECT * FROM ingredient_alias").fetchone()
    assert alias["normalised"] == "coriandre fraiche"
    assert alias["product_id"] == product["id"]


def test_confirming_without_asking_teaches_nothing(manager):
    """`create_alias` est un choix explicite de l'écran, pas un effet de bord
    de la confirmation."""
    with manager.db.write() as conn:
        [product] = _catalogue(conn, ["Coriandre"])
        ingredient_id = _recipe_line(conn, "coriandre fraîche")
    manager.match_ingredient(ingredient_id, product_id=product["id"],
                             state="confirmed")
    assert manager.db.read().execute(
        "SELECT COUNT(*) c FROM ingredient_alias").fetchone()["c"] == 0


def test_confirming_a_second_product_moves_the_alias(manager):
    with manager.db.write() as conn:
        products = _catalogue(conn, ["Coriandre", "Persil"])
        ingredient_id = _recipe_line(conn, "coriandre fraîche")

    manager.match_ingredient(ingredient_id, product_id=products[0]["id"],
                             state="confirmed", create_alias=True)
    manager.match_ingredient(ingredient_id, product_id=products[1]["id"],
                             state="confirmed", create_alias=True)

    read = manager.db.read()
    assert read.execute("SELECT COUNT(*) c FROM ingredient_alias").fetchone()["c"] == 1
    assert repo.find_alias(read, "coriandre fraiche")["product_id"] == products[1]["id"]


def test_marking_a_line_ignored_needs_no_product(manager):
    """Sel, poivre, eau : `ignored` est un état de plein droit. La ligne
    s'affiche, ne décrémente rien, et ne réapparaît jamais dans les manques."""
    with manager.db.write() as conn:
        ingredient_id = _recipe_line(conn, "sel")
    line = manager.match_ingredient(ingredient_id, product_id=None, state="ignored")
    assert line["match_state"] == "ignored"
    assert line["product_id"] is None


def test_marking_a_line_auto_without_a_product_is_refused(manager):
    """La contrainte de schéma le refuse déjà ; la couche du dessus doit le
    refuser AVANT, avec une phrase française — et sans prendre le verrou
    d'écriture juste pour abandonner dedans."""
    with manager.db.write() as conn:
        ingredient_id = _recipe_line(conn, "sel")
    with pytest.raises(ValueError, match="suppose un produit"):
        manager.match_ingredient(ingredient_id, product_id=None, state="auto")


def test_an_unknown_match_state_is_refused_by_name(manager):
    with manager.db.write() as conn:
        ingredient_id = _recipe_line(conn, "sel")
    with pytest.raises(ValueError, match="peut-être"):
        manager.match_ingredient(ingredient_id, product_id=None, state="peut-être")


# --- les cas nommés ---------------------------------------------------------

@pytest.mark.parametrize("raw_text, expected_product", [
    ("2 cs d'huile d'olive", "Huile d'olive"),
    ("3 œufs", "Œufs"),
    ("½ concombre", "Concombre"),
    ("riz basmati", "Riz Basmati"),
    ("crème fraîche", "Crème fraîche"),
])
def test_the_named_cases_that_must_work(conn, raw_text, expected_product):
    state, product_id, _, _ = resolve_ingredient_match(
        conn, raw_text=raw_text, ingredient_name=None, products=PRODUCTS)
    assert state == "auto"
    assert NAMES[product_id] == expected_product


@pytest.mark.parametrize("raw_text", [
    "un peu de tout", "garniture", "selon le goût", "300 g (sec)", "2 tranches",
    "coriandre fraîche",
])
def test_the_cases_that_must_stay_unmatched_rather_than_be_guessed(conn, raw_text):
    """Deviner ici, c'est écrire un décrément faux dans un journal en ajout
    seul. `unmatched` est un résultat, pas un échec.

    Écart assumé au plan, qui listait ici « sel », « poivre du moulin » et
    « eau ». Le catalogue réel contient bel et bien les produits « Sel »,
    « Poivre » et « Eau » : les apparier est JUSTE, on en a en stock. Ce que le
    plan visait — qu'ils ne décrémentent rien — est l'affaire de l'état
    `ignored`, testé plus haut, pas d'un refus d'appariement. « coriandre
    fraîche » le remplace : le produit n'existe pas au catalogue, et « Crème
    fraîche » marque 0,53 — exactement le genre de proximité qu'il ne faut pas
    prendre pour une réponse.
    """
    state, product_id, _, _ = resolve_ingredient_match(
        conn, raw_text=raw_text, ingredient_name=None, products=PRODUCTS)
    assert (state, product_id) == ("unmatched", None)


# --- la mesure sur les lignes réelles ---------------------------------------

def _replay_all(conn):
    """Rejoue les 250 lignes réelles. Rend (taux d'auto, exactitude des auto)."""
    auto = exact = 0
    for line in LINES:
        state, product_id, _, _ = resolve_ingredient_match(
            conn, raw_text=line["raw_text"], ingredient_name=None, products=PRODUCTS)
        if state == "auto":
            auto += 1
            exact += product_id == line["product_id"]
    return auto / len(LINES), (exact / auto if auto else 0.0)


def test_the_automatic_match_rate_on_the_real_lines(conn):
    """Mesure, et épingle un plancher. Ce test n'a pas vocation à monter tout
    seul : s'il baisse, c'est que les seuils ou la normalisation ont bougé.

    Plancher écrit APRÈS la première mesure (40 %), arrondi vers le bas au
    multiple de 5 %. Il n'a pas été inventé, et il ne doit pas être baissé
    pour faire passer une régression.
    """
    rate, _ = _replay_all(conn)
    assert rate >= 0.40, f"taux d'appariement automatique tombé à {rate:.0%}"


def test_the_automatic_matches_agree_with_the_human_who_did_it_first(conn):
    """Le chiffre qui compte vraiment. Un `auto` faux écrit un décrément faux
    dans un journal en ajout seul : mieux vaut apparier moins que se tromper.

    Les rares désaccords restants sont des quasi-doublons du catalogue
    (« Pain burger » contre « Pains Burger Géant x4 ») où les deux réponses
    sont défendables, pas des erreurs franches.
    """
    _, exactness = _replay_all(conn)
    assert exactness >= 0.90, f"exactitude des appariements automatiques : {exactness:.0%}"


def test_the_replay_is_deterministic(conn):
    """Deux passes sur les mêmes fixtures donnent exactement le même verdict
    ligne par ligne — sinon aucune mesure n'a de sens."""
    def verdicts():
        return [resolve_ingredient_match(conn, raw_text=line["raw_text"],
                                         ingredient_name=None, products=PRODUCTS)[:3]
                for line in LINES]
    assert verdicts() == verdicts()


def test_the_fixtures_are_the_real_ones_and_not_a_stub():
    """Si quelqu'un remplace les fixtures par un échantillon inventé, la mesure
    ci-dessus ne veut plus rien dire. On épingle donc leur taille."""
    assert len(PRODUCTS) == 299
    assert len(LINES) >= 200
    assert all(line["product_id"] in NAMES for line in LINES)
