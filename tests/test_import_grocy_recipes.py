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
