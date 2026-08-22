"""La bascule dans l'ordre où le propriétaire l'exécute.

`docs/extinction/README.md` numérote les gestes : le catalogue est le **6**,
les équipements le **7**, le stock le **9**, les recettes le **10**. Toutes les
fixtures du dépôt montent la base dans l'ordre inverse — `db_migre` fait
catalogue/stock/recettes, et `db_piles` ajoute les équipements par-dessus. Cet
ordre-là passe ; celui du runbook plantait, parce que l'import des équipements
crée cinq produits dont l'`external_ref` n'est PAS un identifiant Grocy
(`grocy:spare:AAA`), et que trois lectures du catalogue faisaient `int()`
dessus.

Ce fichier joue l'ordre réel. Il ne remplace pas les autres : il ferme
l'angle mort qu'ils partagent.
"""
import json
from pathlib import Path

import pytest

from custom_components.home_stock.import_grocy import import_catalog
from custom_components.home_stock.import_grocy_equipment import (
    import_grocy_equipment,
)
from custom_components.home_stock.import_grocy_recipes import import_recipes
from custom_components.home_stock.import_grocy_stock import import_stock
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
def tmp_media(tmp_path):
    dossier = tmp_path / "media" / "home_stock"
    dossier.mkdir(parents=True)
    return dossier


def _importer_equipements(db, grocy_reel_db):
    """Le geste 7, tel que le service l'appelle."""
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
    return import_grocy_equipment(db, grocy_reel_db, hass_states=etats,
                                  registry_rows=registre, apply=True)


def _refs_non_numeriques(db) -> list[str]:
    return [row["external_ref"] for row in db.read().execute(
        "SELECT external_ref FROM product WHERE external_ref IS NOT NULL")
        if not (row["external_ref"] or "").lstrip("-").isdigit()]


def test_le_geste_7_pose_des_refs_qui_ne_sont_pas_des_identifiants_grocy(
        db, grocy_reel_db):
    """Le fait générateur, isolé : sans lui, les trois tests suivants
    passeraient pour de mauvaises raisons."""
    import_catalog(db, grocy_reel_db, apply=True)
    _importer_equipements(db, grocy_reel_db)
    assert _refs_non_numeriques(db), (
        "l'import des équipements ne crée plus de produit `grocy:spare:` —"
        " ce fichier ne teste alors plus rien")


def test_le_stock_s_importe_apres_les_equipements(db, grocy_reel_db):
    """Geste 7 puis geste 9, l'ordre du runbook."""
    import_catalog(db, grocy_reel_db, apply=True)
    _importer_equipements(db, grocy_reel_db)
    rapport = import_stock(db, grocy_reel_db, apply=True)
    assert rapport.batches > 0


def test_les_recettes_s_importent_apres_les_equipements(db, grocy_reel_db,
                                                        tmp_media):
    """Geste 7 puis geste 10."""
    import_catalog(db, grocy_reel_db, apply=True)
    _importer_equipements(db, grocy_reel_db)
    rapport = import_recipes(db, grocy_reel_db, picture_dir=tmp_media,
                             apply=True, today=AUJOURD_HUI)
    assert rapport.recipes > 0


def test_le_catalogue_se_rejoue_apres_les_equipements(db, grocy_reel_db):
    """Le geste 6 est REJOUABLE : le runbook le fait rattraper ce qui a été
    créé dans Grocy depuis le premier import. Rejoué après le geste 7, il
    relisait lui aussi les `grocy:spare:` comme des entiers."""
    import_catalog(db, grocy_reel_db, apply=True)
    _importer_equipements(db, grocy_reel_db)
    rapport = import_catalog(db, grocy_reel_db, apply=True)
    assert rapport.ok
