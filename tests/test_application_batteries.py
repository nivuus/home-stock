"""Déclarer une pile, la corriger, la relever — et rendre le plan.

Le fichier couvre les tâches 6 et 7 du lot 5. Les helpers `_seed_spare`,
`_stock_of` et `_movement` servent aux deux.
"""
import sqlite3
from datetime import datetime

import pytest
import voluptuous as vol

from custom_components.home_stock.application import StockManager
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations

NOW = datetime(2026, 8, 21, 12, 0, 0)


@pytest.fixture
def manager(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.connect()
    with db.write() as conn:
        apply_migrations(conn)
        repo.insert_location(conn, name="Placard", kind="cupboard")
    yield StockManager(db)
    db.close()


def _seed_spare(manager, *, name: str, quantity: float) -> int:
    """Une rechange au catalogue : un produit non comestible, son article
    générique, et un lot au placard — le même chemin qu'un yaourt."""
    with manager.db.write() as conn:
        product_id = repo.insert_product(conn, name=name, base_unit="piece", edible=0)
        article_id = repo.insert_article(conn, product_id=product_id, is_generic=1)
    if quantity:
        manager.add_stock(article_id=article_id, quantity=quantity, location_id=1,
                          occurred_at="2026-08-01T10:00:00")
    return product_id


def _stock_of(manager, product_id: int) -> float:
    return repo.spare_stock(manager.db.read(), [product_id])[product_id]


def _movement(manager, movement_id: int) -> dict:
    return dict(manager.db.read().execute(
        "SELECT * FROM movement WHERE id = ?", (movement_id,)).fetchone())


# --- tâche 6 : déclarer, corriger, relever ----------------------------------

def test_declaring_a_battery_returns_its_id_and_stores_the_label(manager):
    manager.declare_battery(label="Velux (CH)", kind="primary")
    assert manager.list_batteries()[0]["label"] == "Velux (CH)"


def test_declaring_is_idempotent_on_its_key(manager):
    first = manager.declare_battery(label="X", kind="primary", idempotency_key="k")
    second = manager.declare_battery(label="X", kind="primary", idempotency_key="k")
    assert first == second
    assert len(manager.list_batteries()) == 1


def test_declaring_twice_on_the_same_anchor_is_refused(manager):
    manager.declare_battery(label="A", kind="primary", entity_registry_id="abc")
    with pytest.raises(sqlite3.IntegrityError):
        manager.declare_battery(label="B", kind="primary", entity_registry_id="abc")


def test_the_application_refuses_what_the_surfaces_refuse(manager):
    """Troisième porte : l'import. Une règle vérifiée seulement aux surfaces
    est une règle qu'un import de 14 lignes contourne."""
    with pytest.raises(vol.Invalid):
        manager.declare_battery(label="X", kind="primary",
                                low_percent=20.0, keep_percent=10.0)
    with pytest.raises(vol.Invalid):
        manager.declare_battery(label="X", kind="built_in", product_id=1)
    with pytest.raises(vol.Invalid):
        manager.declare_battery(label="X", kind="primary", tracked=False)


def test_declaring_an_unknown_kind_is_refused(manager):
    with pytest.raises(vol.Invalid):
        manager.declare_battery(label="X", kind="nimh")


def test_updating_an_unknown_field_is_refused(manager):
    battery_id = manager.declare_battery(label="X", kind="primary")
    with pytest.raises(ValueError):
        manager.update_battery(battery_id, {"labell": "faute de frappe"})


def test_updating_an_unknown_battery_says_so(manager):
    with pytest.raises(ValueError, match="unknown battery 999"):
        manager.update_battery(999, {"label": "X"})


def test_updating_still_checks_the_invariants(manager):
    """Corriger un seuil est une écriture comme une autre : le `keep` sous le
    `low` doit être aussi impossible ici qu'à la déclaration."""
    battery_id = manager.declare_battery(label="X", kind="primary")
    with pytest.raises(vol.Invalid):
        manager.update_battery(battery_id, {"low_percent": 30.0, "keep_percent": 10.0})


def test_updating_checks_the_invariant_against_the_stored_kind(manager):
    """`product_id` sur une batterie intégrée doit être refusé même quand la
    nature n'est pas dans la même requête : elle est en base."""
    battery_id = manager.declare_battery(label="Rideau", kind="built_in")
    with pytest.raises(vol.Invalid):
        manager.update_battery(battery_id, {"product_id": 1})


def test_record_reading_stores_the_percent_and_the_moment(manager):
    battery_id = manager.declare_battery(label="X", kind="primary")
    manager.record_reading(battery_id, percent=18.0, at="2026-08-21T06:00:00")
    row = manager.list_batteries()[0]
    assert row["last_percent"] == 18.0 and row["last_reading_at"] == "2026-08-21T06:00:00"


def test_list_batteries_gives_the_domain_exactly_what_it_expects(manager):
    """Le contrat entre `application` et `domain/maintenance` : si une clé
    manque, `battery_plan` la lira à None et la pile deviendra silencieusement
    « jamais relevée » — le genre de panne qui ne lève rien."""
    manager.declare_battery(label="X", kind="primary", tracked=True)
    row = manager.list_batteries()[0]
    assert {"id", "label", "kind", "tracked", "active", "last_percent",
            "last_reading_at", "low_percent", "keep_percent", "spare"} <= set(row)


def test_list_batteries_carries_the_spare_and_its_stock(manager):
    product_id = _seed_spare(manager, name="CR2032", quantity=3)
    manager.declare_battery(label="X", kind="primary", product_id=product_id,
                            cell_count=2)
    spare = manager.list_batteries()[0]["spare"]
    assert spare == {"label": "CR2032", "cell_count": 2, "in_stock": 3.0}


def test_a_battery_without_a_spare_says_none_not_an_empty_dict(manager):
    manager.declare_battery(label="X", kind="primary")
    assert manager.list_batteries()[0]["spare"] is None


def test_maintenance_plan_marks_itself_complete(manager):
    manager.declare_battery(label="X", kind="primary", tracked=True)
    plan = manager.maintenance_plan(now=NOW, readings={})
    assert plan["complete"] is True
    assert set(plan) == {"items", "keep", "complete"}


def test_maintenance_plan_reports_incomplete_instead_of_raising(manager, monkeypatch):
    """Le risque n°1 du lot : un plan qui lève ferait disparaître les items de
    pile de `items` ET de `keep`, et une seule synchro à 5 h 05 refermerait les
    14 tâches. Le refus doit être une donnée, pas une exception qui se perd."""
    monkeypatch.setattr(manager, "list_batteries",
                        lambda **kw: (_ for _ in ()).throw(sqlite3.OperationalError("boom")))
    plan = manager.maintenance_plan(now=NOW, readings={})
    assert plan["complete"] is False
    assert plan["items"] == [] and plan["keep"] == []


def test_maintenance_plan_uses_the_readings_the_coordinator_resolved(manager):
    """`application` ne connaît ni `entity_id` ni `state` : seul le
    coordinateur sait résoudre une ancre. Il les passe par `readings`."""
    battery_id = manager.declare_battery(label="Velux (CH)", kind="primary",
                                         tracked=True)
    manager.record_reading(battery_id, percent=18.0, at="2026-08-21T11:00:00")
    plan = manager.maintenance_plan(
        now=NOW, readings={battery_id: {"entity_id": "sensor.velux_ch_batterie",
                                        "state": "18"}})
    assert [i["summary"] for i in plan["items"]] == ["Pile à changer — Velux (CH)"]
    assert plan["items"][0]["entity"] == "sensor.velux_ch_batterie"


def test_a_battery_with_no_reading_entry_is_treated_as_orphaned(manager):
    """Aucune entrée dans `readings` veut dire « l'ancre n'a rien résolu » :
    keep, et surtout aucune fermeture."""
    manager.declare_battery(label="X", kind="primary", tracked=True)
    plan = manager.maintenance_plan(now=NOW, readings={})
    assert plan["items"] == []
    assert plan["keep"] == ["Pile à changer — X"]


def test_maintenance_plan_merges_the_macro_plan(manager):
    plan = manager.maintenance_plan(
        now=NOW, readings={},
        extra_items=[{"summary": "Arroser Plante", "description": "18 %",
                      "entity": "sensor.plante"}],
        extra_keep=["Arroser Plante"])
    assert [i["summary"] for i in plan["items"]] == ["Arroser Plante"]
    assert plan["complete"] is True


def test_an_explicit_external_ref_is_not_overwritten_by_a_queue_key(manager):
    """`battery` n'a pas de colonne `idempotency_key` (le DDL est celui de la
    spec, et on n'y ajoute aucune colonne) : le marqueur de rejeu voyage dans
    `external_ref`, la colonne que l'import Grocy utilise aussi. Les deux ne
    peuvent cohabiter que parce qu'ils sont préfixés — et parce qu'une
    référence explicite gagne toujours, sinon l'import perdrait la sienne et
    cesserait d'être rejouable."""
    battery_id = manager.declare_battery(label="X", kind="primary",
                                         external_ref="grocy:battery:7",
                                         idempotency_key="k")
    row = manager.db.read().execute(
        "SELECT external_ref FROM battery WHERE id = ?", (battery_id,)).fetchone()
    assert row["external_ref"] == "grocy:battery:7"


# --- tâche 7 : l'événement de pile et la rechange qui sort du placard -------

def test_replacing_a_primary_consumes_one_spare(manager):
    product_id = _seed_spare(manager, name="CR2032", quantity=3)
    battery_id = manager.declare_battery(label="Velux (CH)", kind="primary",
                                         product_id=product_id, cell_count=1)
    result = manager.record_battery_event(battery_id, kind="replacement")
    assert result["movement_id"] is not None
    assert _stock_of(manager, product_id) == 2.0


def test_a_two_cell_device_consumes_two(manager):
    product_id = _seed_spare(manager, name="AAA", quantity=4)
    battery_id = manager.declare_battery(label="Interrupteur cuisine", kind="primary",
                                         product_id=product_id, cell_count=2)
    manager.record_battery_event(battery_id, kind="replacement")
    assert _stock_of(manager, product_id) == 2.0


def test_the_movement_is_a_plain_consumption(manager):
    """Aucun motif `battery` : ajouter un motif aurait obligé à repasser sur
    CONSUME_REASONS, totals_between, journal_entries et les onze capteurs du
    lot 2, pour une distinction qui se lit déjà dans `product.edible = 0`."""
    product_id = _seed_spare(manager, name="CR2032", quantity=3)
    battery_id = manager.declare_battery(label="X", kind="primary", product_id=product_id)
    movement_id = manager.record_battery_event(battery_id, kind="replacement")["movement_id"]
    row = _movement(manager, movement_id)
    assert row["reason"] == "consumption"
    assert row["kcal"] is None              # aucune table nutritionnelle : NULL, pas 0.0


def test_a_rechargeable_cell_consumes_nothing_by_default(manager):
    product_id = _seed_spare(manager, name="LADDA AAA", quantity=4)
    battery_id = manager.declare_battery(label="Capteur", kind="rechargeable_cell",
                                         product_id=product_id)
    result = manager.record_battery_event(battery_id, kind="charge")
    assert result["movement_id"] is None
    assert _stock_of(manager, product_id) == 4.0


def test_a_rechargeable_cell_consumes_when_asked_explicitly(manager):
    product_id = _seed_spare(manager, name="LADDA AAA", quantity=4)
    battery_id = manager.declare_battery(label="Capteur", kind="rechargeable_cell",
                                         product_id=product_id)
    manager.record_battery_event(battery_id, kind="replacement", consume_spare=True)
    assert _stock_of(manager, product_id) == 3.0


def test_a_built_in_battery_never_consumes(manager):
    battery_id = manager.declare_battery(label="Rideau cuisine", kind="built_in")
    assert manager.record_battery_event(battery_id, kind="charge")["movement_id"] is None
    with pytest.raises(vol.Invalid):
        manager.record_battery_event(battery_id, kind="replacement")


def test_a_primary_cannot_be_charged(manager):
    battery_id = manager.declare_battery(label="X", kind="primary")
    with pytest.raises(vol.Invalid):
        manager.record_battery_event(battery_id, kind="charge")


def test_an_unknown_event_kind_is_refused(manager):
    battery_id = manager.declare_battery(label="X", kind="primary")
    with pytest.raises(vol.Invalid):
        manager.record_battery_event(battery_id, kind="explosion")


def test_replaying_the_key_writes_neither_a_second_event_nor_a_second_decrement(manager):
    product_id = _seed_spare(manager, name="CR2032", quantity=3)
    battery_id = manager.declare_battery(label="X", kind="primary", product_id=product_id)
    first = manager.record_battery_event(battery_id, kind="replacement",
                                         idempotency_key="k")
    second = manager.record_battery_event(battery_id, kind="replacement",
                                          idempotency_key="k")
    assert first["event_id"] == second["event_id"]
    assert first["movement_id"] == second["movement_id"]
    assert _stock_of(manager, product_id) == 2.0
    assert len(manager.list_battery_events(battery_id)) == 1


def test_an_empty_cupboard_still_records_the_replacement(manager):
    """On ne perd pas « la pile a été changée » parce que le placard n'était
    pas à jour. Le refus est une donnée rendue, pas une exception avalée."""
    product_id = _seed_spare(manager, name="CR2032", quantity=0)
    battery_id = manager.declare_battery(label="X", kind="primary", product_id=product_id)
    result = manager.record_battery_event(battery_id, kind="replacement")
    assert result["movement_id"] is None
    assert "Stock insuffisant" in result["spare_refused"]
    assert len(manager.list_battery_events(battery_id)) == 1


def test_a_successful_replacement_reports_no_refusal(manager):
    product_id = _seed_spare(manager, name="CR2032", quantity=3)
    battery_id = manager.declare_battery(label="X", kind="primary", product_id=product_id)
    assert manager.record_battery_event(battery_id,
                                        kind="replacement")["spare_refused"] is None


def test_a_replacement_forgets_the_old_reading(manager):
    battery_id = manager.declare_battery(label="X", kind="primary")
    manager.record_reading(battery_id, percent=4.0, at="2026-08-20T00:00:00")
    manager.record_battery_event(battery_id, kind="replacement",
                                 occurred_at="2026-08-21T10:00:00")
    row = manager.list_batteries()[0]
    assert row["last_percent"] is None and row["last_reading_at"] is None
    assert row["installed_on"] == "2026-08-21"


def test_a_charge_does_not_forget_the_reading(manager):
    """Recharger une cellule ne la remplace pas : le dernier relevé reste
    valable, et l'effacer ferait croire à une pile jamais relevée."""
    battery_id = manager.declare_battery(label="Capteur", kind="rechargeable_cell")
    manager.record_reading(battery_id, percent=4.0, at="2026-08-20T00:00:00")
    manager.record_battery_event(battery_id, kind="charge")
    assert manager.list_batteries()[0]["last_percent"] == 4.0


def test_a_fresh_replacement_produces_no_task_at_all(manager):
    """Le corollaire du test précédent, vu depuis le plan : une pile qu'on
    vient de changer ne doit produire ni item de niveau ni « Pile HS ? »."""
    battery_id = manager.declare_battery(label="X", kind="primary", tracked=True)
    manager.record_reading(battery_id, percent=4.0, at="2026-08-20T00:00:00")
    manager.record_battery_event(battery_id, kind="replacement")
    plan = manager.maintenance_plan(now=NOW, readings={})
    assert plan["items"] == []
    assert plan["keep"] == ["Pile à changer — X"]


def test_a_charge_on_an_unknown_battery_says_so(manager):
    with pytest.raises(ValueError, match="unknown battery 999"):
        manager.record_battery_event(999, kind="charge")
