"""Les 102 recettes, leurs étapes, leurs instructions, leurs images.

L'amendement le plus important du lot est ici : le lot 3 § 18 écrit que les 15
recettes de type `1` « sont les copies fantômes ». C'est faux. Ce sont 15
vraies recettes, créées le 2026-06-27 par un outil qui a écrit `type = 1` au
lieu de `type = 'normal'`. Un `WHERE type = 'normal'` strict perdrait 15
recettes et 96 lignes d'ingrédients EN SILENCE.

Tous les tests de ce fichier traversent un import complet et portent donc
--timeout=60 : Database._lock n'est pas réentrant.
"""
import pytest

from custom_components.home_stock.import_grocy import import_catalog
from custom_components.home_stock.import_grocy_recipes import (
    RecipeImportError,
    import_recipes,
)
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations

AUJOURD_HUI = "2026-08-21"


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
    """La base après le rejeu du catalogue : c'est l'ordre de la bascule."""
    import_catalog(db, grocy_reel_db, apply=True)
    return db


@pytest.fixture
def tmp_media(tmp_path):
    dossier = tmp_path / "media" / "home_stock"
    dossier.mkdir(parents=True)
    return dossier


def test_a_hundred_and_two_recipes_come_over(db_catalogue, grocy_reel_db, tmp_media):
    """87 normal + 15 de type 1. Le lot 3 §18 disait 87 et traitait les 15
    comme des fantômes : c'était faux, et ce test est l'amendement."""
    rapport = import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                             apply=True)
    assert rapport.recipes == 102


def test_the_fifteen_type_one_recipes_are_named(db_catalogue, grocy_reel_db,
                                                tmp_media):
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    noms = {r["name"] for r in repo.list_recipes(db_catalogue.read())}
    assert "Salade de lentilles fraîche" in noms
    assert "Bowl protéiné fromage blanc" in noms
    assert "Taboulé quinoa été" in noms


def test_no_phantom_copy_gets_through(db_catalogue, grocy_reel_db, tmp_media):
    """166 copies générées par trois triggers de meal_plan, toutes à
    identifiant NÉGATIF. Les importer créerait 166 recettes fantômes."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    refs = [r["source_ref"] for r in db_catalogue.read().execute(
        "SELECT source_ref FROM recipe")]
    assert all(int(ref) > 0 for ref in refs)
    assert len(refs) == 102


def test_recipes_nestings_is_never_read():
    """5 651 lignes, presque toutes produites par les mêmes triggers.
    Abandonnée — décision reprise du lot 3 §20."""
    import inspect

    from custom_components.home_stock import import_grocy_recipes
    assert "recipes_nestings" not in inspect.getsource(import_grocy_recipes)


def test_two_hundred_and_fifty_one_steps(db_catalogue, grocy_reel_db, tmp_media):
    """251, pas 338.

    La spec (§ 14) écrit « 338 (323 pages moins 87 blocs Ingrédients, plus une
    page par recette de type 1, plus les couvertures) ». Cette arithmétique
    compte les 87 couvertures DEUX FOIS : elles sont déjà dans les 323. Le
    compte juste est 323 − 87 + 15 = 251, et c'est exactement ce que le
    découpeur trouve. Amendement A6 du § 22.
    """
    rapport = import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                             apply=True)
    assert rapport.steps == 251
    assert db_catalogue.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_step").fetchone()["n"] == 251


def test_five_hundred_and_sixty_one_instructions(db_catalogue, grocy_reel_db,
                                                 tmp_media):
    rapport = import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                             apply=True)
    assert rapport.instructions == 561


def test_a_hundred_and_sixteen_timers_land_in_the_database(db_catalogue,
                                                           grocy_reel_db,
                                                           tmp_media):
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db_catalogue.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_instruction WHERE timer_seconds IS NOT NULL"
    ).fetchone()["n"] == 116


def test_the_ingredients_page_is_never_imported_as_a_step(db_catalogue,
                                                          grocy_reel_db,
                                                          tmp_media):
    """Elle est un RENDU de recipes_pos, jamais une source. La réimporter
    serait la deuxième écriture d'une même quantité, encore."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    titres = {row["title"] for row in db_catalogue.read().execute(
        "SELECT title FROM recipe_step WHERE title IS NOT NULL")}
    assert "Ingrédients" not in titres


def test_the_meta_line_fills_minutes_and_utensils(db_catalogue, grocy_reel_db,
                                                  tmp_media):
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    row = db_catalogue.read().execute(
        "SELECT total_minutes, utensils, summary FROM recipe WHERE source_ref = '1'"
    ).fetchone()
    assert row["total_minutes"] and row["utensils"] and row["summary"]


def test_the_calculated_kcal_of_the_meta_line_is_not_stored(db_catalogue):
    """C'est une valeur calculée par recettes_miseenpage.py depuis le
    catalogue. La recalculer à l'affichage vaut mieux que graver un chiffre
    daté — le lot 3 §20 a déjà différé « nutriments avant cuisson »."""
    colonnes = {r["name"] for r in db_catalogue.read().execute(
        "PRAGMA table_info(recipe)")}
    assert "reference_kcal" not in colonnes


def test_the_seventeen_rewritten_recipes_need_review(db_catalogue, grocy_reel_db,
                                                     tmp_media):
    """41, 43-50, 96-103 : le README de grocy-off dit que leurs étapes, leurs
    minutages et leurs ustensiles sont INVENTÉS."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    refs = {row["source_ref"] for row in db_catalogue.read().execute(
        "SELECT source_ref FROM recipe WHERE needs_review = 1")}
    assert refs == {"41", *(str(n) for n in range(43, 51)),
                    *(str(n) for n in range(96, 104))}
    assert len(refs) == 17


def test_adapted_at_stays_null(db_catalogue, grocy_reel_db, tmp_media):
    """Aucun agent n'a adapté ces recettes."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db_catalogue.read().execute(
        "SELECT COUNT(*) AS n FROM recipe WHERE adapted_at IS NOT NULL"
    ).fetchone()["n"] == 0


def test_the_sixty_two_inline_images_become_files(db_catalogue, grocy_reel_db,
                                                  tmp_media):
    rapport = import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                             apply=True)
    ecrits = list((tmp_media / "recipes").glob("*-inline-*.jpg"))
    assert len(ecrits) == 62
    assert rapport.pictures == 62


def test_no_image_url_still_points_at_grocy(db_catalogue, grocy_reel_db,
                                            tmp_media):
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    conn = db_catalogue.read()
    for table in ("recipe", "recipe_step"):
        assert conn.execute(
            f"SELECT COUNT(*) AS n FROM {table}"
            " WHERE image_url LIKE '%grocy.allanic.me%'").fetchone()["n"] == 0


def test_the_fifty_five_hosted_images_point_at_media(db_catalogue, grocy_reel_db,
                                                     tmp_media):
    """Elles ne sont pas COPIÉES par l'import — le conteneur Home Assistant ne
    voit pas le dossier de Grocy, c'est le geste 3 du propriétaire. Mais leur
    URL est réécrite dès maintenant, sinon elle mourrait avec le conteneur."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    urls = [row["image_url"] for row in db_catalogue.read().execute(
        "SELECT image_url FROM recipe_step WHERE image_url LIKE 'media-source:%'")]
    assert len(urls) >= 55
    assert all(u.startswith("media-source://media_source/local/") for u in urls)


def test_unsplash_urls_are_left_exactly_as_they_are(db_catalogue, grocy_reel_db,
                                                    tmp_media):
    """46 images distinctes, laissées à leur source : elles ne meurent pas
    avec le conteneur, et rien ici ne va les chercher sur le réseau."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db_catalogue.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_step"
        " WHERE image_url LIKE '%images.unsplash.com%'").fetchone()["n"] > 0


def test_every_written_file_weighs_more_than_zero(db_catalogue, grocy_reel_db,
                                                  tmp_media):
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    for chemin in (tmp_media / "recipes").iterdir():
        assert chemin.stat().st_size > 0


def test_a_dry_run_writes_neither_rows_nor_files(db_catalogue, grocy_reel_db,
                                                 tmp_media):
    """Un import en simulation qui écrirait quand même les images serait une
    écriture déguisée. Le rollback SQL ne couvre pas le disque : c'est au code
    de ne pas écrire."""
    rapport = import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                             apply=False)
    assert rapport.recipes == 102
    assert repo.list_recipes(db_catalogue.read()) == []
    assert not list(tmp_media.rglob("*.jpg"))


def test_a_second_run_changes_nothing(db_catalogue, grocy_reel_db, tmp_media):
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    second = import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                            apply=True)
    assert second.recipes == 0
    assert len(repo.list_recipes(db_catalogue.read())) == 102


def test_a_replayed_inline_image_overwrites_instead_of_accumulating(
        db_catalogue, grocy_reel_db, tmp_media):
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    avant = sorted(p.name for p in (tmp_media / "recipes").iterdir())
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert sorted(p.name for p in (tmp_media / "recipes").iterdir()) == avant


def test_the_import_runs_in_one_transaction(db_catalogue, grocy_reel_db,
                                            tmp_media):
    """Database._lock n'est pas réentrant. Ce test rend la main ou il gèle."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)


# --- ingrédients ------------------------------------------------------------

def test_five_hundred_and_ten_ingredient_rows(db_catalogue, grocy_reel_db,
                                              tmp_media):
    rapport = import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                             apply=True)
    assert rapport.ingredients == 510


def test_the_two_hundred_orphan_rows_are_left_out(db_catalogue, grocy_reel_db,
                                                  tmp_media):
    """710 lignes dans recipes_pos, 200 orphelines : leur recipe_id ne
    correspond à aucune ligne de recipes. Un LEFT JOIN les ramènerait ; le
    JOIN du filtre les écarte."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db_catalogue.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_ingredient").fetchone()["n"] == 510


def test_four_hundred_and_eighty_five_are_confirmed(db_catalogue, grocy_reel_db,
                                                    tmp_media):
    """« confirmed », pas « auto » : le lot 3 réserve auto à un appariement
    deviné et scoré. Ici le produit vient d'un identifiant."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    compte = {row["match_state"]: row["n"] for row in db_catalogue.read().execute(
        "SELECT match_state, COUNT(*) AS n FROM recipe_ingredient"
        " GROUP BY match_state")}
    assert compte == {"confirmed": 485, "unmatched": 25}


def test_match_score_is_never_written(db_catalogue, grocy_reel_db, tmp_media):
    """Écrire 1.0 laisserait croire qu'un algorithme a été très sûr de lui."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db_catalogue.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_ingredient WHERE match_score IS NOT NULL"
    ).fetchone()["n"] == 0


def test_the_twenty_three_diverging_units_lose_their_quantity(db_catalogue,
                                                              grocy_reel_db,
                                                              tmp_media):
    """Onze disent « 1 Bouteille » d'huile d'olive quand variable_amount dit
    « 1 cs ». Importées telles quelles, elles retireraient 750 ml d'huile pour
    une cuillère à soupe, À CHAQUE REPAS VALIDÉ."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    lignes = db_catalogue.read().execute(
        "SELECT amount, product_id FROM recipe_ingredient"
        " WHERE match_state = 'unmatched' AND product_id IS NOT NULL").fetchall()
    assert len(lignes) == 23
    assert all(l["amount"] is None for l in lignes)
    assert all(l["product_id"] is not None for l in lignes)   # le produit est certain


def test_the_two_inactive_product_rows_have_no_product(db_catalogue,
                                                       grocy_reel_db, tmp_media):
    """« Riz basmati (doublon) » est désactivé chez Grocy, donc jamais importé
    au lot 0. Le rapport le nomme : c'est un appariement que seul un humain
    peut signer."""
    rapport = import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                             apply=True)
    lignes = db_catalogue.read().execute(
        "SELECT amount FROM recipe_ingredient"
        " WHERE match_state = 'unmatched' AND product_id IS NULL").fetchall()
    assert len(lignes) == 2
    assert any("Riz basmati" in a for a in rapport.anomalies)


def test_every_diverging_line_is_named_in_the_report(db_catalogue, grocy_reel_db,
                                                     tmp_media):
    """Avec sa recette, son produit, la quantité Grocy, LES DEUX unités et le
    variable_amount. Sans ça, « 25 lignes à arbitrer » n'est pas actionnable.

    Onze lignes d'huile d'olive, pas treize : la spec en annonçait treize, la
    base en porte onze. Amendement A7 du § 22.
    """
    rapport = import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                             apply=True)
    citees = [a for a in rapport.anomalies if "unité" in a]
    assert len(citees) == 23
    huile = [a for a in citees if "Huile d" in a]
    assert len(huile) == 11
    assert all("Bouteille" in a and "cs" in a for a in huile)


def test_variable_amount_is_never_parsed_into_a_quantity(db_catalogue,
                                                         grocy_reel_db,
                                                         tmp_media):
    """Règle du lot 3 §18. Le grief n° 2 du lot 0 ne revient pas par la porte
    de derrière : aucune ligne unmatched ne repart avec une quantité."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db_catalogue.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_ingredient"
        " WHERE match_state = 'unmatched' AND amount IS NOT NULL"
    ).fetchone()["n"] == 0
    import inspect

    from custom_components.home_stock import import_grocy_recipes
    assert "culinary_measure" not in inspect.getsource(import_grocy_recipes)


def test_variable_amount_travels_as_provenance(db_catalogue, grocy_reel_db,
                                               tmp_media):
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    row = db_catalogue.read().execute(
        "SELECT raw_text FROM recipe_ingredient"
        " WHERE match_state = 'unmatched' AND raw_text LIKE '%cs%' LIMIT 1"
    ).fetchone()
    assert row is not None


def test_the_fifty_six_rows_without_variable_amount_get_a_composed_raw_text(
        db_catalogue, grocy_reel_db, tmp_media):
    """raw_text est NOT NULL et 56 lignes n'ont pas de variable_amount. Il est
    composé mécaniquement — « 500 g », « 2 Pièce » : le même nombre dans la
    même unité, ce que la source disait. Rien d'inventé."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db_catalogue.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_ingredient"
        " WHERE raw_text IS NULL OR raw_text = ''").fetchone()["n"] == 0


def test_group_name_stays_null(db_catalogue, grocy_reel_db, tmp_media):
    """ingredient_group est VIDE sur les 510 lignes : la ligne du lot 3 §18
    (« → group_name, direct ») est sans objet."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db_catalogue.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_ingredient WHERE group_name IS NOT NULL"
    ).fetchone()["n"] == 0


def test_packaging_and_measure_stay_null_on_the_confirmed_lines(
        db_catalogue, grocy_reel_db, tmp_media):
    """0 ligne dont qu_id diffère du qu_id_stock, sur les 414 normal : il n'y
    a rien à exprimer dans une autre mesure."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db_catalogue.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_ingredient"
        " WHERE match_state = 'confirmed'"
        "   AND (packaging_id IS NOT NULL OR measure_id IS NOT NULL)"
    ).fetchone()["n"] == 0


def test_not_check_stock_fulfillment_is_reported_not_stored(db_catalogue,
                                                            grocy_reel_db,
                                                            tmp_media):
    """39 lignes, pas 4 — amendement A8 du § 22. Aucune colonne équivalente,
    sans effet sur la validation d'un repas qui vérifie le stock de toute
    façon. Mentionné au rapport, une seule fois, avec son compte."""
    rapport = import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                             apply=True)
    citees = [a for a in rapport.anomalies if "hors stock" in a]
    assert len(citees) == 1
    assert "39" in citees[0]


def test_a_confirmed_quantity_is_converted_into_the_base_unit(db_catalogue,
                                                              grocy_reel_db,
                                                              tmp_media):
    """Une ligne « 1 kg » sur un produit stocké en grammes vaut 1 000, pas 1.
    C'est la même table de correspondance que partout, jamais une seconde."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True)
    row = db_catalogue.read().execute(
        "SELECT ri.amount FROM recipe_ingredient AS ri"
        " JOIN product AS prod ON prod.id = ri.product_id"
        " WHERE ri.match_state = 'confirmed' AND prod.base_unit = 'g'"
        "   AND ri.amount > 0 LIMIT 1").fetchone()
    assert row is not None and row["amount"] > 0


# --- planning ---------------------------------------------------------------

def test_forty_two_future_meals_come_over(db_catalogue, grocy_reel_db, tmp_media):
    rapport = import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                             apply=True, today=AUJOURD_HUI)
    assert rapport.meals == 42


def test_the_sixty_six_past_entries_stay_out(db_catalogue, grocy_reel_db,
                                             tmp_media):
    """Un plan passé n'est ni un repas mangé ni un repas à cuisiner."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today=AUJOURD_HUI)
    assert db_catalogue.read().execute(
        "SELECT COUNT(*) AS n FROM meal WHERE day < ?", (AUJOURD_HUI,)
    ).fetchone()["n"] == 0


def test_no_meal_is_ever_written_done(db_catalogue, grocy_reel_db, tmp_media):
    """Valider un repas écrit des mouvements. Un repas done sans mouvement
    derrière est un mensonge dans une base dont le journal est la seule
    source de vérité — et meal_plan.done est donc IGNORÉ."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today=AUJOURD_HUI)
    etats = {row["state"] for row in db_catalogue.read().execute(
        "SELECT state FROM meal")}
    assert etats == {"planned"}


def test_the_minus_one_section_never_has_to_be_mapped(db_catalogue, grocy_reel_db,
                                                      tmp_media):
    """30 entrées utilisent la section -1 (le « sans section » de Grocy, que
    m004 n'a pas semée) et LES TRENTE SONT DANS LE PASSÉ. La décision de ne
    reprendre que l'avenir referme ce problème d'elle-même."""
    rapport = import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                             apply=True, today=AUJOURD_HUI)
    assert not [a for a in rapport.anomalies if "section" in a.lower()]


def test_the_three_slots_get_their_share(db_catalogue, grocy_reel_db, tmp_media):
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today=AUJOURD_HUI)
    compte = {row["slot_key"]: row["n"] for row in db_catalogue.read().execute(
        "SELECT slot_key, COUNT(*) AS n FROM meal GROUP BY slot_key")}
    assert compte == {"breakfast": 12, "lunch": 19, "dinner": 11}


def test_the_two_notes_travel_without_a_recipe(db_catalogue, grocy_reel_db,
                                               tmp_media):
    """20 des 108 entrées sont des notes ; 2 d'entre elles sont à venir."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today=AUJOURD_HUI)
    assert db_catalogue.read().execute(
        "SELECT COUNT(*) AS n FROM meal WHERE recipe_id IS NULL"
        " AND note IS NOT NULL").fetchone()["n"] == 2


def test_the_eleven_notes_carried_by_a_recipe_entry_are_reported(
        db_catalogue, grocy_reel_db, tmp_media):
    """meal impose « une recette OU un produit OU une note, jamais deux ».
    Onze entrées à venir portent les deux : la recette gagne, et la note est
    RAPPORTÉE au lieu d'être avalée. Le plan ne prévoyait pas ce cas."""
    rapport = import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                             apply=True, today=AUJOURD_HUI)
    citees = [a for a in rapport.anomalies if "note" in a.lower()]
    assert len(citees) == 11
    assert any("Curry de lentilles corail" in a for a in citees)


def test_fractional_servings_pass_as_they_are(db_catalogue, grocy_reel_db,
                                              tmp_media):
    """0,15 ; 0,2 ; 0,25 sur 10 entrées. meal.servings est un REAL avec
    CHECK (servings > 0) : elles passent telles quelles, sans arrondi."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today=AUJOURD_HUI)
    valeurs = [row["servings"] for row in db_catalogue.read().execute(
        "SELECT servings FROM meal WHERE servings < 1")]
    assert len(valeurs) == 10
    assert 0.15 in valeurs


def test_the_uid_makes_replay_free(db_catalogue, grocy_reel_db, tmp_media):
    """meal.uid est UNIQUE : l'idempotence du planning est gratuite."""
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today=AUJOURD_HUI)
    uids = {row["uid"] for row in db_catalogue.read().execute("SELECT uid FROM meal")}
    assert len(uids) == 42
    assert all(u.startswith("grocy-meal-") and u.endswith("@home_stock")
               for u in uids)
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today=AUJOURD_HUI)
    assert db_catalogue.read().execute(
        "SELECT COUNT(*) AS n FROM meal").fetchone()["n"] == 42


def test_the_forty_two_reach_twenty_three_distinct_recipes(db_catalogue,
                                                           grocy_reel_db,
                                                           tmp_media):
    import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today=AUJOURD_HUI)
    ids = {row["recipe_id"] for row in db_catalogue.read().execute(
        "SELECT recipe_id FROM meal WHERE recipe_id IS NOT NULL")}
    assert len(ids) == 23


def test_an_entry_pointing_at_a_missing_recipe_stops_the_plan(db_catalogue,
                                                              grocy_reel_db,
                                                              tmp_media):
    """Le planning se réimporte en dix secondes ; une entrée orpheline se
    découvre au dîner."""
    import sqlite3
    conn = sqlite3.connect(grocy_reel_db)
    conn.execute(
        "UPDATE meal_plan SET recipe_id = 999999 WHERE id ="
        " (SELECT MIN(id) FROM meal_plan WHERE day >= ?"
        "    AND recipe_id IS NOT NULL)", (AUJOURD_HUI,))
    conn.commit()
    conn.close()
    with pytest.raises(RecipeImportError):
        import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                       apply=True, today=AUJOURD_HUI)


def test_the_horizon_moves_with_today(db_catalogue, grocy_reel_db, tmp_media):
    """« À venir » se calcule au jour de la bascule, jamais sur une date
    figée : la cible bouge, et le code compte ce qu'il trouve."""
    tot = import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                         apply=False, today="2026-03-01").meals
    tard = import_recipes(db_catalogue, grocy_reel_db, picture_dir=tmp_media,
                          apply=False, today="2026-08-31").meals
    # 108 entrées depuis mars, dont 30 sur la section -1 de Grocy, que m004
    # n'a pas semée : 78 repas. La spec annonçait 108, mais elle comptait des
    # lignes de meal_plan, pas des repas que meal accepte — amendement A9. Et
    # c'est bien la preuve que la section -1 n'existe QUE dans le passé : sur
    # l'horizon du 21 août, aucune entrée n'est perdue.
    assert tot == 78
    assert tard == 4
    assert tard < 42 < tot


def test_today_is_never_written_into_the_code():
    """La cible bouge : une date figée dans le code de production ferait de
    « à venir » un souvenir du jour où le lot a été écrit."""
    import inspect

    from custom_components.home_stock import import_grocy_recipes
    assert "2026-08-21" not in inspect.getsource(import_grocy_recipes)
