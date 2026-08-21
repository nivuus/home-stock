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
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL")]
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
