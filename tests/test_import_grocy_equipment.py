"""L'import des piles et équipements Grocy, et le contrôle « 0 écart ».

Le contrôle qui compte est `summary_diff` : il compare les résumés que le
NOUVEAU plan produirait aux résumés qu'aurait produits le bloc 3 du macro sur
le MÊME état. S'il n'est pas vide, la bascule fermerait des tâches et en
rouvrirait d'autres, et Bleuenn annoncerait la maison entière.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from custom_components.home_stock.import_grocy_equipment import (
    import_grocy_equipment, macro_label, macro_summaries,
)
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations
from custom_components.home_stock.application import StockManager

FIXTURES = Path(__file__).parent / "fixtures"
ETATS = json.loads((FIXTURES / "maintenance" / "etats.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 8, 21, 12, 0, 0)

# Les piles du registre, telles que le coordinateur les verrait : une entrée
# par capteur `device_class: battery` de l'instantané.
REGISTRE = [
    {"entity_registry_id": f"uuid-{index}", "entity_id": row["entity_id"],
     "device_id": None,
     "name": row["attributes"].get("friendly_name") or row["entity_id"],
     "model": None}
    for index, row in enumerate(ETATS)
    if row["attributes"].get("device_class") == "battery"
]
ETATS_PAR_ID = {row["entity_id"]: row for row in ETATS}


@pytest.fixture
def manager(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.connect()
    with db.write() as conn:
        apply_migrations(conn)
        repo.insert_location(conn, name="Placard", kind="cupboard")
    yield StockManager(db)
    db.close()


@pytest.fixture
def grocy(tmp_path):
    """Une base Grocy jetable, reconstruite depuis l'extrait versionné."""
    chemin = tmp_path / "grocy.db"
    conn = sqlite3.connect(str(chemin))
    conn.executescript((FIXTURES / "grocy" / "equipment.sql").read_text(encoding="utf-8"))
    conn.commit()
    conn.close()
    return str(chemin)


def _import(manager, grocy, *, apply=True, registre=None, etats=None):
    return import_grocy_equipment(
        manager.db, grocy, hass_states=etats if etats is not None else ETATS,
        registry_rows=REGISTRE if registre is None else registre, apply=apply)


def _battery_for(manager, entity_id: str):
    cible = next(r for r in REGISTRE if r["entity_id"] == entity_id)
    return next(b for b in manager.list_batteries()
                if b["entity_registry_id"] == cible["entity_registry_id"])


def _battery_named(manager, label: str):
    return next(b for b in manager.list_batteries() if b["label"] == label)


def _stock_of_named(manager, name: str) -> float:
    conn = manager.db.read()
    row = conn.execute("SELECT id FROM product WHERE name = ?", (name,)).fetchone()
    return repo.spare_stock(conn, [row["id"]])[row["id"]]


def _snapshot(manager):
    return ([{k: v for k, v in b.items() if k != "spare"}
             for b in manager.list_batteries()],
            sorted(p["name"] for p in
                   manager.db.read().execute("SELECT name FROM product")),
            sorted(e["name"] for e in manager.list_equipment()))


def test_a_dry_run_writes_nothing_but_reports_everything(manager, grocy):
    rapport = _import(manager, grocy, apply=False)
    assert rapport.batteries == 5 and rapport.products == 5 and rapport.equipment == 34
    assert manager.list_batteries() == []


def test_the_eighteen_spare_cells_become_five_products(manager, grocy):
    """18 lignes Grocy pour 18 cellules, c'est un inventaire par objet. Ce
    qu'on veut savoir, c'est « combien de CR2032 au placard »."""
    _import(manager, grocy)
    noms = sorted(p["name"] for p in manager.db.read().execute(
        "SELECT name FROM product WHERE edible = 0"))
    assert len(noms) == 5
    assert _stock_of_named(manager, "CR2032") == 3.0
    assert _stock_of_named(manager, "AAA") == 4.0
    assert _stock_of_named(manager, "9 V") == 5.0
    assert _stock_of_named(manager, "C/LR14") == 4.0
    assert _stock_of_named(manager, "AA") == 2.0


def test_the_spares_are_not_edible_and_have_no_nutrition(manager, grocy):
    _import(manager, grocy)
    for row in manager.db.read().execute(
            "SELECT edible, reference_kcal FROM product WHERE edible = 0"):
        assert row["edible"] == 0
        assert row["reference_kcal"] is None


def test_the_spares_get_a_min_quantity_so_a_shortage_can_exist(manager, grocy):
    """Sans `min_quantity`, une rechange épuisée ne remonterait jamais dans
    `binary_sensor.home_stock_shortages`, donc jamais dans la liste de
    courses — et tout l'intérêt de « savoir quoi acheter » disparaîtrait."""
    _import(manager, grocy)
    for row in manager.db.read().execute(
            "SELECT min_quantity FROM product WHERE edible = 0"):
        assert row["min_quantity"] == 2


def test_the_three_removed_devices_are_reported_not_imported(manager, grocy):
    """Les importer créerait trois piles orphelines dès le premier jour."""
    rapport = _import(manager, grocy)
    assert rapport.skipped == 3
    assert any("appareil retiré" in a for a in rapport.anomalies)


def test_the_cell_count_is_read_from_the_description(manager, grocy):
    _import(manager, grocy)
    pile = _battery_named(manager, "Interrupteur cuisine")
    assert pile["cell_count"] == 2 and pile["spare"]["label"] == "AAA"


def test_rechargeable_in_the_description_gives_the_right_kind(manager, grocy):
    """« 2x AAA rechargeable » est une cellule rechargeable ; « 1x CR2032 »
    est une pile jetable."""
    _import(manager, grocy)
    assert _battery_for(manager,
                        "sensor.capteur_humain_batterie")["kind"] == "rechargeable_cell"
    assert _battery_for(manager,
                        "sensor.interrupteur_sdb_batterie")["kind"] == "primary"


def test_running_it_twice_changes_nothing(manager, grocy):
    """`external_ref` garde l'id Grocy des deux côtés : le rejeu est sûr, et le
    lot 7 devient une jointure au lieu d'un appariement de noms."""
    _import(manager, grocy)
    avant = _snapshot(manager)
    _import(manager, grocy)
    assert _snapshot(manager) == avant


def test_the_sweep_proposes_what_the_macro_tracks_today(manager, grocy):
    """Le balayage ne devine pas : il recopie la décision que le macro prend
    aujourd'hui. Ce qu'il suit devient `tracked = 1`, ce qu'il écarte devient
    `tracked = 0` avec son motif. C'est ce qui rend la bascule neutre — et
    `tracked = NULL` reste ce qu'il doit être : un capteur apparu APRÈS
    l'import, que le compteur réclamera."""
    _import(manager, grocy)
    piles = manager.list_batteries()
    assert len(piles) == 28
    assert sum(1 for b in piles if b["tracked"] is True) == 14
    assert sum(1 for b in piles if b["tracked"] is False) == 14
    assert [b for b in piles if b["tracked"] is None] == []


def test_the_fourteen_exclusions_are_saved_before_the_macro_is_shortened(manager, grocy):
    """La seule information que le macro possède et qu'on perdrait en le
    raccourcissant : QUI est exclu, et POURQUOI."""
    _import(manager, grocy)
    exclues = [b for b in manager.list_batteries() if b["tracked"] is False]
    assert len(exclues) == 14
    assert all(b["exclusion_reason"] for b in exclues)
    motifs = {b["label"]: b["exclusion_reason"] for b in exclues}
    assert "secteur" in motifs["Tablette Salon"]


def test_the_two_e208_batteries_are_excluded_but_not_the_key_tag(manager, grocy):
    """CLAUDE.md avertit qu'un motif `peugeot|e208` écarterait aussi le tag BLE
    du trousseau, qui est une CR2032 légitimement suivie. Sans motif,
    l'avertissement n'a plus d'objet : deux lignes disent non, une troisième
    dit oui, et aucune ne dépend de l'orthographe d'une autre."""
    _import(manager, grocy)
    assert _battery_for(manager,
                        "sensor.peugeot_e208_batterie_niveau")["tracked"] is False
    assert _battery_for(manager,
                        "sensor.peugeot_e208_batterie_de_service")["tracked"] is False
    assert _battery_for(
        manager, "sensor.cle_de_la_peugeot_e208_batterie_ble")["tracked"] is True


def test_the_two_swapped_ble_tags_are_reported_and_not_arbitrated(manager, grocy):
    """Le lot 5 ne renomme rien : il rend la question posable une fois pour
    toutes. L'inventaire dit MiTag, le registre dit « Sac » ; aucune donnée du
    système ne tranche."""
    rapport = _import(manager, grocy)
    assert sum("BLE" in a for a in rapport.anomalies) == 2
    assert _battery_for(manager, "sensor.sac_batterie_ble")["label"] \
        != _battery_for(manager, "sensor.cle_de_la_peugeot_e208_batterie_ble")["label"]


def test_the_seeded_label_is_the_one_the_macro_renders_today(manager, grocy):
    """Contre-intuitif et volontaire : c'est ce qui rend la bascule neutre.
    « Velux (CH) Batterie » devient « Velux (CH) », exactement comme la chaîne
    de replace() du macro le fait aujourd'hui."""
    _import(manager, grocy)
    assert _battery_for(manager, "sensor.velux_ch_batterie")["label"] == "Velux (CH)"
    assert _battery_for(manager,
                        "sensor.interrupteur_c_batterie")["label"] == "Interrupteur cuisine"
    assert _battery_for(manager,
                        "sensor.brya_battery_level")["label"] == "brya"


def test_the_seeded_kind_reproduces_todays_verb(manager, grocy):
    """Le macro dit « Recharger » sur un nom qui contient `rideau` ou `lock`,
    « Pile à changer » sinon. L'heuristique est appliquée UNE fois, ici, et
    jamais ailleurs."""
    _import(manager, grocy)
    assert _battery_for(manager,
                        "sensor.0xa4c1386d02de3c39_battery")["kind"] == "built_in"
    assert _battery_for(
        manager, "sensor.aqara_smart_lock_u200_lite_batterie")["kind"] == "built_in"
    assert _battery_for(manager, "sensor.velux_ch_batterie")["kind"] == "primary"


def test_the_report_proves_zero_summary_drift(manager, grocy):
    """LE contrôle qui garantit le déploiement neutre."""
    rapport = _import(manager, grocy)
    assert rapport.summary_diff == []
    assert rapport.ok is True


def test_the_zero_drift_check_still_holds_when_batteries_are_actually_low(manager, grocy):
    """L'instantané réel n'a aucune pile sous son seuil, ce qui rendrait le
    contrôle précédent vrai sans rien prouver. On abaisse donc quatre valeurs
    — une sous 20, une entre 20 et 25, une muette, une exclue — et on exige
    que les deux plans disent toujours exactement la même chose."""
    etats = [dict(row) for row in ETATS]
    truque = {"sensor.velux_ch_batterie": "18",
              "sensor.porte_entree_s_batterie": "22",
              "sensor.fenetre_c_batterie": "unavailable",
              "sensor.tablette_salon_batterie": "3"}
    for row in etats:
        if row["entity_id"] in truque:
            row["state"] = truque[row["entity_id"]]
    rapport = _import(manager, grocy, etats=etats)
    assert rapport.summary_diff == []
    assert any(s.startswith("Pile à changer") for s in macro_summaries(etats)["items"])


def test_the_drift_check_actually_catches_a_drift(manager, grocy):
    """Sans ce test, « summary_diff est vide » ne prouverait pas que le
    contrôle sait dire non. On change le verbe d'une pile après l'import et on
    exige que l'écart soit rapporté."""
    _import(manager, grocy)
    pile = _battery_for(manager, "sensor.velux_ch_batterie")
    manager.update_battery(pile["id"], {"label": "Velux renommé"})
    etats = [dict(row) for row in ETATS]
    for row in etats:
        if row["entity_id"] == "sensor.velux_ch_batterie":
            row["state"] = "18"
    rapport = _import(manager, grocy, etats=etats)
    assert rapport.summary_diff != []
    assert rapport.ok is False


def test_the_report_refuses_a_dead_anchor(manager, grocy):
    """Une ancre qui ne résout rien LE JOUR de l'import est une faute de
    saisie, pas un orphelin légitime."""
    rapport = _import(manager, grocy, apply=False, registre=[])
    assert rapport.ok is False
    assert any("ancre" in a for a in rapport.blocking)


def test_the_thirty_four_equipment_are_imported_without_a_device(manager, grocy):
    """Rien n'est deviné : ni date d'achat, ni garantie, ni notice, et AUCUN
    appariement automatique du nom vers le `device_registry` — trois appareils
    s'appellent « Télévision » dans ce registre."""
    _import(manager, grocy)
    equipements = manager.list_equipment()
    assert len(equipements) == 34
    assert all(e["device_id"] is None for e in equipements)
    assert all(e["purchased_on"] is None and e["warranty_months"] is None
               for e in equipements)


def test_the_macro_label_helper_reproduces_the_replace_chain():
    """L'heuristique est utilisée une fois puis jamais ; elle vit ici et nulle
    part ailleurs, ce qui la rend testable directement."""
    assert macro_label("Velux (CH) Batterie") == "Velux (CH)"
    assert macro_label("Batterie Capteur Cuisine") == "Capteur Cuisine"
    assert macro_label("brya Battery level") == "brya"
    assert macro_label("  Espaces  ") == "Espaces"
