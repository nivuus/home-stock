"""Les onze contrôles, et surtout : un contrôle qui ne mesure rien échoue.

Les premiers tests de ce fichier sont les plus importants du lot 7. Ils
rejouent, un par un, les trois cas réels du § 16.3 — ceux qu'un contrôle naïf
laisse passer en affichant « écart : 0 ». Le lot 6 a démontré qu'un
vérificateur qui mesure du vide déclare tout conforme ; ces tests sont ce qui
empêche cette panne de se rejouer.
"""
import json
import sqlite3
from pathlib import Path

import pytest

from custom_components.home_stock.import_grocy import import_catalog
from custom_components.home_stock.import_grocy_recipes import import_recipes
from custom_components.home_stock.import_grocy_stock import import_stock
from custom_components.home_stock.migration_check import check_migration
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import (
    MIGRATIONS,
    apply_migrations,
)

AUJOURD_HUI = "2026-08-21"

# Les sept lots dont le prix a été écarté (§ 8.4). Acquittés NOMINATIVEMENT.
SEPT_LOTS = ["grocy:stock:241", "grocy:stock:250", "grocy:stock:255",
             "grocy:stock:256", "grocy:stock:257", "grocy:stock:264",
             "grocy:stock:419"]


def _check(rapport, code):
    return next(c for c in rapport.checks if c.code == code)


def _ids_unmatched(db):
    return [str(row["id"]) for row in db.read().execute(
        "SELECT id FROM recipe_ingredient WHERE match_state = 'unmatched'"
        " ORDER BY id")]


def _empreinte_dossier(dossier):
    chemin = Path(dossier)
    return sorted((p.relative_to(chemin).as_posix(), p.stat().st_size,
                   p.stat().st_mtime_ns)
                  for p in chemin.rglob("*") if p.is_file())


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "home_stock.db"))
    database.connect()
    with database.write() as conn:
        apply_migrations(conn)
    yield database
    database.close()


@pytest.fixture
def db_vide(db):
    """Migrée, et rien dedans. Deux bases vides ne prouvent rien."""
    return db


@pytest.fixture
def db_schema_seven(tmp_path):
    """Arrêtée à m007 : c'est l'état d'une instance qui n'a pas redémarré."""
    database = Database(str(tmp_path / "sept.db"))
    database.connect()
    with database.write() as conn:
        for migration in MIGRATIONS:
            if migration.VERSION > 7:
                break
            conn.executescript(migration.SQL)
            hook = getattr(migration, "apply", None)
            if hook is not None:
                hook(conn)
        conn.execute("CREATE TABLE IF NOT EXISTS schema_version"
                     " (version INTEGER NOT NULL)")
        conn.execute("INSERT INTO schema_version (version) VALUES (7)")
    yield database
    database.close()


@pytest.fixture
def tmp_media(tmp_path):
    dossier = tmp_path / "media" / "home_stock"
    dossier.mkdir(parents=True)
    return dossier


@pytest.fixture
def db_migre(db, grocy_reel_db, tmp_media):
    """La base après TOUTE la bascule : catalogue, stock, recettes, planning."""
    import_catalog(db, grocy_reel_db, apply=True)
    import_stock(db, grocy_reel_db, apply=True)
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today=AUJOURD_HUI)
    return db


@pytest.fixture
def grocy_vide(tmp_path, grocy_reel_db):
    """Les mêmes tables, sans une seule ligne. Le cas « la copie est vide »."""
    chemin = tmp_path / "grocy_vide.db"
    source = sqlite3.connect(grocy_reel_db)
    schema = [ligne[0] for ligne in source.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL"
        "   AND name NOT LIKE 'sqlite_%'")]
    source.close()
    conn = sqlite3.connect(str(chemin))
    for instruction in schema:
        conn.execute(instruction)
    conn.commit()
    conn.close()
    return str(chemin)


@pytest.fixture
def grocy_ecrit_apres(grocy_reel_db):
    """Grocy a écrit APRÈS la copie. C'est le scénario du Sorbet Fraise."""
    conn = sqlite3.connect(grocy_reel_db)
    conn.execute(
        "UPDATE products SET row_created_timestamp = '2099-01-01 12:00:00'"
        " WHERE id = (SELECT MAX(id) FROM products)")
    conn.commit()
    conn.close()
    return grocy_reel_db


# --- les planchers ----------------------------------------------------------

def test_a_forgotten_copy_of_grocy_db_fails_before_anything_else(db, tmp_path):
    """Cas 1 du §16.3 : la copie a été oubliée. Sans plancher, C1 compare
    0 lot à 0 lot et affiche « écart : 0 ». C0 doit échouer D'ABORD, sur la
    fraîcheur — sinon les dix autres contrôles mentent en cascade."""
    rapport = check_migration(db, str(tmp_path / "absente.db"), archive=False)
    assert rapport.ok is False
    c0 = _check(rapport, "C0")
    assert c0.verdict == "empty"
    assert c0.blocking is True
    assert "C0" in rapport.blocking


def test_a_dry_run_left_in_simulation_is_red_not_green(db, grocy_reel_db):
    """Cas 2 du §16.3 : l'import est resté en simulation. C1 trouve 0 batch
    et ÉCHOUE, au lieu de « 0 écart sur 0 lot »."""
    rapport = check_migration(db, grocy_reel_db, archive=False)
    c1 = _check(rapport, "C1")
    assert c1.home_count == 0
    assert c1.grocy_count == 108
    assert c1.verdict == "empty"        # et surtout PAS "ok"
    assert c1.blocking is True


def test_a_check_that_compares_zero_to_zero_is_never_green(db, grocy_vide):
    """Le principe, isolé : deux bases vides ne prouvent rien. Ce test tient
    pour LES DOUZE contrôles, pas seulement pour C1 — c'est ce qui interdit
    d'en ajouter un treizième sans plancher."""
    rapport = check_migration(db, grocy_vide, archive=False)
    for controle in rapport.checks:
        assert controle.verdict != "ok", controle.code
    assert rapport.ok is False


# --- C0 ---------------------------------------------------------------------

def test_c0_refuses_a_schema_below_eight(db_schema_seven, grocy_reel_db):
    rapport = check_migration(db_schema_seven, grocy_reel_db, archive=False)
    c0 = _check(rapport, "C0")
    assert c0.verdict != "ok"
    assert "8" in " ".join(c0.details)


def test_c0_refuses_a_copy_older_than_two_hours(db_migre, grocy_reel_db):
    rapport = check_migration(db_migre, grocy_reel_db, archive=False,
                              now="2099-01-01T09:00:00")
    assert _check(rapport, "C0").verdict != "ok"


def test_c0_catches_a_write_that_happened_after_the_copy(db_migre,
                                                         grocy_ecrit_apres):
    """LA cible mobile. Un produit créé dans Grocy après la copie invalide
    TOUS les autres contrôles : C0 le dit avant qu'ils mentent. C'est
    exactement le scénario du Sorbet Fraise, créé le 21 août à 18 h 54."""
    rapport = check_migration(db_migre, grocy_ecrit_apres, archive=False)
    c0 = _check(rapport, "C0")
    assert c0.blocking is True
    assert any("écrit" in d for d in c0.details)


def test_c0_is_green_on_a_fresh_copy_of_a_frozen_grocy(db_migre, grocy_reel_db):
    rapport = check_migration(db_migre, grocy_reel_db, archive=False)
    assert _check(rapport, "C0").verdict == "ok"


# --- C1, C2, C3 -------------------------------------------------------------

def test_c1_matches_batch_for_batch(db_migre, grocy_reel_db):
    rapport = check_migration(db_migre, grocy_reel_db, archive=False)
    c1 = _check(rapport, "C1")
    assert c1.grocy_count == 108 and c1.home_count == 108
    assert c1.gap == 0 and c1.verdict == "ok"


def test_c1_names_a_missing_batch(db_migre, grocy_reel_db):
    with db_migre.write() as conn:
        conn.execute("UPDATE batch SET external_ref = NULL WHERE id ="
                     " (SELECT MIN(id) FROM batch WHERE external_ref IS NOT NULL)")
    rapport = check_migration(db_migre, grocy_reel_db, archive=False)
    c1 = _check(rapport, "C1")
    assert c1.gap == 1 and c1.blocking is True
    assert c1.details                     # nommé, pas juste compté


def test_c2_compares_quantities_to_a_millionth(db_migre, grocy_reel_db):
    """10⁻⁶ unité de base : assez serré pour attraper une conversion ratée,
    assez lâche pour ne pas se battre avec les flottants."""
    rapport = check_migration(db_migre, grocy_reel_db, archive=False)
    assert _check(rapport, "C2").verdict == "ok"
    with db_migre.write() as conn:
        conn.execute("UPDATE batch SET remaining = remaining + 0.01"
                     " WHERE external_ref = 'grocy:stock:419'")
    assert _check(check_migration(db_migre, grocy_reel_db, archive=False),
                  "C2").verdict == "gap"


def test_c2_tolerates_a_millionth(db_migre, grocy_reel_db):
    with db_migre.write() as conn:
        conn.execute("UPDATE batch SET remaining = remaining + 1e-9"
                     " WHERE external_ref = 'grocy:stock:419'")
    assert _check(check_migration(db_migre, grocy_reel_db, archive=False),
                  "C2").verdict == "ok"


def test_c3_expects_the_ten_sentinels_at_null(db_migre, grocy_reel_db):
    rapport = check_migration(db_migre, grocy_reel_db, archive=False)
    c3 = _check(rapport, "C3")
    assert c3.verdict == "ok"
    assert any("2999-12-31" in d for d in c3.details)   # documenté, pas caché


def test_c3_flags_a_null_that_is_not_a_sentinel(db_migre, grocy_reel_db):
    with db_migre.write() as conn:
        conn.execute("UPDATE batch SET best_before = NULL"
                     " WHERE external_ref = 'grocy:stock:255'")
    assert _check(check_migration(db_migre, grocy_reel_db, archive=False),
                  "C3").blocking is True


# --- C4 ---------------------------------------------------------------------

def test_c4_expects_exactly_ninety_two_unpriced_batches(db_migre, grocy_reel_db):
    """85 sans prix chez Grocy + les 7 écartés du §8.4. « Exactement » : un
    prix perdu en plus est aussi grave qu'un prix aberrant conservé."""
    c4 = _check(check_migration(db_migre, grocy_reel_db, archive=False), "C4")
    assert c4.home_count == 92


def test_c4_blocks_until_the_seven_are_acknowledged(db_migre, grocy_reel_db):
    c4 = _check(check_migration(db_migre, grocy_reel_db, archive=False), "C4")
    assert c4.verdict == "unacknowledged"
    assert c4.blocking is True
    assert len(c4.details) == 7
    assert any("Fromage blanc 1kg" in d for d in c4.details)   # la note, mot pour mot


def test_c4_passes_once_the_seven_are_named(db_migre, grocy_reel_db):
    c4 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                acknowledged=SEPT_LOTS), "C4")
    assert c4.verdict == "ok" and c4.blocking is False


def test_acknowledging_six_of_seven_is_not_acknowledging(db_migre, grocy_reel_db):
    c4 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                acknowledged=SEPT_LOTS[:-1]), "C4")
    assert c4.blocking is True


# --- C5, C6 -----------------------------------------------------------------

def test_c5_wants_one_purchase_movement_per_batch(db_migre, grocy_reel_db):
    c5 = _check(check_migration(db_migre, grocy_reel_db, archive=False), "C5")
    assert c5.verdict == "ok" and c5.home_count == 108


def test_c5_checks_the_sum_per_product_too(db_migre, grocy_reel_db):
    """Un mouvement par lot ne suffit pas : SUM(quantity) par produit doit
    égaler le stock du produit, sinon le journal ne reconstruit plus rien."""
    with db_migre.write() as conn:
        conn.execute("UPDATE batch SET remaining = remaining / 2"
                     " WHERE external_ref = 'grocy:stock:419'")
    assert _check(check_migration(db_migre, grocy_reel_db, archive=False),
                  "C5").verdict == "gap"


def test_c6_proves_the_three_totals_never_moved(db_migre, grocy_reel_db):
    """La preuve MÉCANIQUE du §8.7 : un purchase n'entre jamais dans
    totals_between. C'est le même mécanisme qui interdit la réinjection de
    l'historique au §9."""
    c6 = _check(check_migration(db_migre, grocy_reel_db, archive=False), "C6")
    assert c6.verdict == "ok"
    assert set(c6.details) >= {"kcal_total", "cost_total", "cost_waste_total"}


def test_c6_fails_when_there_is_no_entry_movement_to_judge(db_vide,
                                                           grocy_reel_db):
    """Plancher : sans un seul mouvement d'entrée, il n'y a rien à prouver."""
    assert _check(check_migration(db_vide, grocy_reel_db, archive=False),
                  "C6").verdict == "empty"


def test_c6_catches_an_entry_movement_that_carries_money(db_migre, grocy_reel_db):
    """Le jour où quelqu'un ajoute un coût à un mouvement d'entrée, les trois
    cumuls sautent d'un bloc — et depuis le lot 4 ils sont state_class TOTAL,
    donc la marche d'escalier reste dans les statistiques POUR TOUJOURS."""
    with db_migre.write() as conn:
        conn.execute(
            "INSERT INTO movement (occurred_at, product_id, article_id,"
            " quantity, reason, base_unit, cost, idempotency_key)"
            " SELECT '2026-08-21T10:00:00', product_id, article_id, 1,"
            " 'purchase', base_unit, 12.5, 'grocy:stock:fauteur'"
            " FROM movement WHERE reason = 'purchase' LIMIT 1")
    assert _check(check_migration(db_migre, grocy_reel_db, archive=False),
                  "C6").verdict == "gap"


def test_details_are_capped_at_fifty(db_migre, grocy_reel_db):
    """Le reste part dans l'archive : un rapport de 500 lignes n'est pas lu."""
    with db_migre.write() as conn:
        conn.execute("UPDATE batch SET remaining = 0 WHERE external_ref IS NOT NULL")
    for controle in check_migration(db_migre, grocy_reel_db,
                                    archive=False).checks:
        assert len(controle.details) <= 50


# --- C7 à C11 ---------------------------------------------------------------

@pytest.fixture
def media_complet(db_migre, tmp_media, grocy_reel):
    """Le dossier media APRÈS le geste 3 : les 62 images en ligne écrites par
    l'import, plus les 55 fichiers hébergés copiés par le propriétaire."""
    from custom_components.home_stock.grocy import pictures as gp
    dossier = tmp_media / "recipes"
    for ligne in grocy_reel["recipes"]:
        for ref in gp.references(ligne["description"]):
            if ref.family == "grocy":
                (dossier / ref.filename).write_bytes(b"\xff\xd8fichier\xff\xd9")
    return tmp_media


@pytest.fixture
def db_piles(db_migre, grocy_reel_db):
    """La base après le geste 7 : piles et équipements importés.

    L'import du lot 5 est REJOUÉ ici, pas refait autrement : C7 vérifie ce
    qu'il a produit, et un ensemencement à la main prouverait seulement que
    le test sait remplir une table.
    """
    from custom_components.home_stock.import_grocy_equipment import (
        import_grocy_equipment,
    )
    etats = json.loads(
        (Path(__file__).parent / "fixtures" / "maintenance" / "etats.json")
        .read_text(encoding="utf-8"))
    registre = [
        {"entity_registry_id": f"uuid-{index}", "entity_id": row["entity_id"],
         "device_id": None,
         "name": row["attributes"].get("friendly_name") or row["entity_id"],
         "model": None}
        for index, row in enumerate(etats)
        if row["attributes"].get("device_class") == "battery"
    ]
    import_grocy_equipment(db_migre, grocy_reel_db, hass_states=etats,
                           registry_rows=registre, apply=True)
    return db_migre


@pytest.fixture
def db_sans_piles(db_migre):
    """Tout est là sauf l'import des piles : le geste 7 a été sauté."""
    with db_migre.write() as conn:
        conn.execute("DELETE FROM battery")
        conn.execute("DELETE FROM equipment")
    return db_migre


def _config(tmp_path, nom, *, raccord: bool):
    """Un dossier config/ jetable, bâti depuis les fixtures du dépôt.

    JAMAIS depuis /opt/nivuus/HomeAssistant/config/ : aucun test ne lit
    l'instance vivante, et aucun ne l'écrit.
    """
    racine = tmp_path / nom
    (racine / "custom_templates").mkdir(parents=True)
    fixtures = Path(__file__).parent / "fixtures" / "maintenance"
    if raccord:
        (racine / "custom_templates" / "maintenance.jinja").write_text(
            (Path(__file__).parent.parent / "docs" / "raccord"
             / "maintenance.jinja").read_text("utf-8"), "utf-8")
        (racine / "automations.yaml").write_text(
            (Path(__file__).parent.parent / "docs" / "raccord"
             / "maintenance_sync.yaml").read_text("utf-8"), "utf-8")
        (racine / "scripts.yaml").write_text("[]\n", "utf-8")
    else:
        (racine / "custom_templates" / "maintenance.jinja").write_text(
            (fixtures / "avant.jinja").read_text("utf-8"), "utf-8")
        (racine / "automations.yaml").write_text(
            (fixtures / "automation_avant.yaml").read_text("utf-8"), "utf-8")
        (racine / "scripts.yaml").write_text(
            "- alias: Afficher recette\n"
            "  sequence: [{ url: /local/grocy-recipes.html }]\n", "utf-8")
    return str(racine)


@pytest.fixture
def config_avec_raccord_absent(tmp_path):
    return _config(tmp_path, "config_avant", raccord=False)


@pytest.fixture
def config_avec_raccord_pose(tmp_path):
    return _config(tmp_path, "config_apres", raccord=True)


def test_every_declared_check_has_a_floor():
    """Garde-fou structurel : un contrôle sans plancher ne doit pas pouvoir
    exister dans le module."""
    from custom_components.home_stock import migration_check as mc
    from custom_components.home_stock.const import MIGRATION_CHECKS
    assert len(MIGRATION_CHECKS) == 12          # C0..C11
    for code in MIGRATION_CHECKS:
        assert code in mc.FLOORS, code
        assert callable(mc.FLOORS[code])


def test_c7_verifies_lot5_but_never_redoes_it():
    import inspect

    from custom_components.home_stock import migration_check as mc
    assert "import_grocy_equipment(" not in inspect.getsource(mc)


def test_c7_fails_when_batteries_are_empty(db_sans_piles, grocy_reel_db):
    """Sans cet import, le raccord du lot 5 FERME 14 tâches de pile au lieu
    de les déplacer. C'est la seule dépendance d'ordre du lot 5 vers le 7."""
    c7 = _check(check_migration(db_sans_piles, grocy_reel_db, archive=False), "C7")
    assert c7.verdict == "empty" and c7.blocking is True


def test_c7_matches_equipment_row_for_row(db_piles, grocy_reel_db):
    """34 équipements chez Grocy, 34 chez nous : c'est une recopie, et elle se
    compte ligne à ligne.

    Les PILES, elles, ne se comptent pas ainsi : l'import du lot 5 part du
    registre d'entités de Home Assistant et se sert des 26 lignes Grocy pour
    renseigner ce qu'il y trouve. Le plan attendait 26 = 26 ; les deux nombres
    n'ont aucune raison d'être égaux, et exiger l'égalité ferait échouer C7
    parce que l'import a bien fonctionné. Amendement A11 du § 22.
    """
    c7 = _check(check_migration(db_piles, grocy_reel_db, archive=False), "C7")
    assert c7.grocy_count == 34 and c7.home_count == 34
    assert c7.verdict == "ok"
    assert any("26 piles chez Grocy" in d for d in c7.details)


def test_c8_counts_all_four_numbers(db_migre, grocy_reel_db):
    c8 = _check(check_migration(db_migre, grocy_reel_db, archive=False), "C8")
    detail = " ".join(c8.details)
    assert "102" in detail and "510" in detail and "561" in detail and "116" in detail


def test_c8_catches_a_phantom_that_slipped_through(db_migre, grocy_reel_db):
    """Une copie fantôme a un source_ref NÉGATIF. Si une seule passe, le
    filtre type IN ('normal','1') a été relâché quelque part."""
    with db_migre.write() as conn:
        conn.execute("UPDATE recipe SET source_ref = '-42' WHERE source_ref = '1'")
    assert _check(check_migration(db_migre, grocy_reel_db, archive=False),
                  "C8").blocking is True


def test_c8_lists_the_twenty_five_unmatched_without_blocking_on_counts(
        db_migre, grocy_reel_db):
    c8 = _check(check_migration(db_migre, grocy_reel_db, archive=False), "C8")
    assert c8.verdict == "unacknowledged"
    assert len([d for d in c8.details if "sans quantité" in d]) == 25


def test_c8_passes_when_the_twenty_five_are_acknowledged(db_migre, grocy_reel_db):
    ids = _ids_unmatched(db_migre)
    assert len(ids) == 25
    c8 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                acknowledged=ids), "C8")
    assert c8.verdict == "ok"


def test_c9_stats_every_file(db_migre, grocy_reel_db, media_complet):
    """Cas 3 du §16.3 : les images sont dans le mauvais dossier, les
    image_url sont écrites, la base est cohérente avec elle-même, tout est
    vert — jusqu'à ce que C9 aille stat() chaque fichier."""
    c9 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                picture_dir=media_complet), "C9")
    # 82 fichiers : 27 images en ligne (62 balises <img>, mais une recette
    # réutilise la même image sur plusieurs pages) plus 55 fichiers hébergés.
    # La spec annonçait 117, en comptant des balises — amendement A10.
    assert c9.home_count == 82 and c9.verdict == "ok"


def test_c9_fails_when_the_folder_is_empty(db_migre, grocy_reel_db, tmp_path):
    c9 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                picture_dir=str(tmp_path / "nulle-part")), "C9")
    assert c9.verdict == "empty" and c9.blocking is True


def test_c9_refuses_a_zero_byte_file(db_migre, grocy_reel_db, media_complet):
    """Un fichier de 0 octet passerait tous les contrôles de base et
    n'afficherait rien sur la tablette."""
    cible = next((media_complet / "recipes").iterdir())
    cible.write_bytes(b"")
    c9 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                picture_dir=media_complet), "C9")
    assert c9.blocking is True
    assert any(cible.name in d for d in c9.details)


def test_c9_finds_no_residual_grocy_url(db_migre, grocy_reel_db, media_complet):
    c9 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                picture_dir=media_complet), "C9")
    assert not [d for d in c9.details if "grocy.allanic.me" in d]


def test_c9_catches_a_residual_grocy_url(db_migre, grocy_reel_db, media_complet):
    with db_migre.write() as conn:
        conn.execute("UPDATE recipe_step SET image_url ="
                     " 'https://grocy.allanic.me/api/files/recipepictures/x'"
                     " WHERE id = (SELECT MIN(id) FROM recipe_step)")
    c9 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                picture_dir=media_complet), "C9")
    assert c9.blocking is True
    assert any("grocy.allanic.me" in d for d in c9.details)


def test_c9_leaves_unsplash_alone(db_migre, grocy_reel_db, media_complet):
    """46 images distinctes, 112 emplacements, laissées à leur source. Le
    critère est « est-ce que ça meurt avec le conteneur ? » — Unsplash n'en
    dépend pas, et C9 ne va JAMAIS les chercher sur le réseau."""
    c9 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                picture_dir=media_complet), "C9")
    assert c9.verdict == "ok"


def test_c10_wants_forty_two_meals_and_nine_list_items(db_migre, grocy_reel_db):
    c10 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                 now="2026-08-21T12:00:00"), "C10")
    detail = " ".join(c10.details)
    assert "42" in detail and "23" in detail and "9" in detail


def test_a_meal_pointing_at_a_missing_recipe_cannot_even_be_written(db_migre):
    """La clé étrangère l'interdit AVANT que C10 ait à le voir.

    Le plan demandait de fabriquer un repas orphelin pour vérifier que C10 le
    signale ; la base refuse l'écriture. C10 garde sa mesure — elle sert si
    quelqu'un ouvre une base avec les clés étrangères coupées — mais la vraie
    garantie est ici, et elle est plus forte qu'un contrôle.
    """
    with pytest.raises(sqlite3.IntegrityError):
        with db_migre.write() as conn:
            conn.execute("UPDATE meal SET recipe_id = 999999 WHERE id ="
                         " (SELECT MIN(id) FROM meal WHERE recipe_id IS NOT NULL)")


def test_c11_blocks_while_the_lot5_raccord_is_not_applied(
        db_migre, grocy_reel_db, config_avec_raccord_absent):
    """Vérifié au 2026-08-21 : maintenance.jinja a encore ses 142 lignes et
    son bloc 3, et automations.yaml lit encore todo.grocy_batteries. Le poser
    est un PRÉALABLE à toute extinction — et ce plan ne le pose pas."""
    c11 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                 config_dir=config_avec_raccord_absent), "C11")
    assert c11.blocking is True
    assert any("maintenance.jinja" in d for d in c11.details)
    assert any("todo.grocy_batteries" in d for d in c11.details)


def test_c11_passes_once_the_raccord_is_in_place(db_migre, grocy_reel_db,
                                                 config_avec_raccord_pose):
    c11 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                 config_dir=config_avec_raccord_pose), "C11")
    assert c11.verdict == "ok"


def test_c11_is_empty_when_it_could_not_look(db_migre, grocy_reel_db, tmp_path):
    """Il ne prétend pas que la maison est propre parce qu'il n'a pas su
    regarder. C'est un plancher, comme les onze autres."""
    c11 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                 config_dir=str(tmp_path / "nulle-part")), "C11")
    assert c11.verdict == "empty"


def test_c11_never_writes_anything(db_migre, grocy_reel_db,
                                   config_avec_raccord_absent):
    """LE test qui empêche le composant de « réparer » la maison tout seul."""
    avant = _empreinte_dossier(config_avec_raccord_absent)
    check_migration(db_migre, grocy_reel_db, archive=False,
                    config_dir=config_avec_raccord_absent)
    assert _empreinte_dossier(config_avec_raccord_absent) == avant


def test_nothing_in_the_module_stops_a_container():
    """Le composant n'arrête JAMAIS Grocy. Arrêter un conteneur de la maison
    est un geste humain, et rien de ce module ne doit pouvoir le faire."""
    import inspect

    from custom_components.home_stock import migration_check as mc
    source = inspect.getsource(mc)
    for interdit in ("docker", "subprocess", "os.system", "Popen"):
        assert interdit not in source


def test_all_twelve_pass_on_a_fully_migrated_database(db_piles, grocy_reel_db,
                                                      media_complet,
                                                      config_avec_raccord_pose):
    """Le seul chemin vers ok: true — et il exige les deux acquittements."""
    rapport = check_migration(
        db_piles, grocy_reel_db, archive=False, picture_dir=media_complet,
        config_dir=config_avec_raccord_pose,
        acknowledged=[*SEPT_LOTS, *_ids_unmatched(db_piles)])
    assert rapport.blocking == []
    assert rapport.ok is True
    assert len(rapport.checks) == 12


# --- archive ----------------------------------------------------------------

def _archive(db, grocy_path, tmp_path):
    chemin = check_migration(db, grocy_path, archive=True,
                             archive_dir=str(tmp_path)).archive_path
    return json.loads(Path(chemin).read_text("utf-8"))


def test_the_archive_holds_all_eleven_hundred_and_twenty_three_rows(
        db_migre, grocy_reel_db, tmp_path):
    contenu = _archive(db_migre, grocy_reel_db, tmp_path)
    assert len(contenu["stock_log"]) == 1123


def test_the_six_undone_rows_keep_their_flag(db_migre, grocy_reel_db, tmp_path):
    """Une annulation fait partie de l'histoire."""
    contenu = _archive(db_migre, grocy_reel_db, tmp_path)
    assert len([l for l in contenu["stock_log"] if l["undone"]]) == 6


def test_each_row_carries_its_product_name(db_migre, grocy_reel_db, tmp_path):
    """Dans dix ans, un product_id de Grocy ne voudra plus rien dire."""
    contenu = _archive(db_migre, grocy_reel_db, tmp_path)
    assert all(l.get("product_name") for l in contenu["stock_log"])


def test_the_archive_also_holds_the_notes_the_chores_and_the_past_plan(
        db_migre, grocy_reel_db, tmp_path):
    contenu = _archive(db_migre, grocy_reel_db, tmp_path)
    assert len(contenu["batch_notes"]) == 25
    assert len(contenu["chores_log"]) == 39
    assert len(contenu["past_meal_plan"]) == 66


def test_the_six_chores_are_named_even_though_they_are_abandoned(
        db_migre, grocy_reel_db, tmp_path):
    """3,5 % de suivi sur six mois. Abandonnées — mais leurs 39 pointages sont
    archivés, et le chemin de repli est dans docs/exploitation.md, pas dans le
    code."""
    contenu = _archive(db_migre, grocy_reel_db, tmp_path)
    noms = {l["chore_name"] for l in contenu["chores_log"]}
    assert "Nettoyer la litière" in noms
    assert len(noms) == 6


def test_the_archive_is_json_not_sqlite(db_migre, grocy_reel_db, tmp_path):
    chemin = check_migration(db_migre, grocy_reel_db, archive=True,
                             archive_dir=str(tmp_path)).archive_path
    assert chemin.endswith(".json")
    assert Path(chemin).read_bytes()[:1] == b"{"


def test_the_file_name_carries_the_date(db_migre, grocy_reel_db, tmp_path):
    chemin = check_migration(db_migre, grocy_reel_db, archive=True,
                             archive_dir=str(tmp_path),
                             now="2026-09-04T21:00:00").archive_path
    assert Path(chemin).name == "home_stock_grocy_archive_2026-09-04.json"


def test_no_stock_log_row_ever_reaches_the_movement_table(db_migre, grocy_reel_db,
                                                          tmp_path):
    """LE test de la décision du §9. 353 sorties chiffrées feraient monter
    kcal_total de 2,8 millions en un rafraîchissement, et depuis le lot 4 ces
    compteurs sont state_class TOTAL : la marche d'escalier resterait dans
    les statistiques long terme POUR TOUJOURS."""
    avant = repo.totals_between(db_migre.read())
    check_migration(db_migre, grocy_reel_db, archive=True,
                    archive_dir=str(tmp_path))
    assert repo.totals_between(db_migre.read()) == avant
    assert db_migre.read().execute(
        "SELECT COUNT(*) AS n FROM movement WHERE idempotency_key LIKE 'grocy:log:%'"
    ).fetchone()["n"] == 0


def test_no_archive_movement_table_was_created(db_migre):
    """Envisagée et refusée : elle serait écrite une fois et lue jamais.
    L'archive est un fichier."""
    tables = {row["name"] for row in db_migre.read().execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "archive_movement" not in tables


def test_archive_false_writes_no_file(db_migre, grocy_reel_db, tmp_path):
    dossier = tmp_path / "archives"
    dossier.mkdir()
    rapport = check_migration(db_migre, grocy_reel_db, archive=False,
                              archive_dir=str(dossier))
    assert rapport.archive_path is None
    assert not list(dossier.iterdir())


def test_the_archive_is_readable_without_the_grocy_schema(db_migre, grocy_reel_db,
                                                          tmp_path):
    """Pas d'id nu, pas de code de statut : des noms, des dates, des
    quantités et des unités lisibles."""
    contenu = _archive(db_migre, grocy_reel_db, tmp_path)
    ligne = contenu["stock_log"][0]
    assert {"product_name", "amount", "unit", "used_date",
            "transaction_type", "undone"} <= set(ligne)
