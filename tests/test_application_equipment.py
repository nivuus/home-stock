"""Les équipements : fiche, garantie calculée, consommables du catalogue."""
import sqlite3
from datetime import date

import pytest
import voluptuous as vol

from custom_components.home_stock.application import StockManager
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations


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
    with manager.db.write() as conn:
        product_id = repo.insert_product(conn, name=name, base_unit="piece", edible=0)
        article_id = repo.insert_article(conn, product_id=product_id, is_generic=1)
    if quantity:
        manager.add_stock(article_id=article_id, quantity=quantity, location_id=1,
                          occurred_at="2026-08-01T10:00:00")
    return product_id


def _stock_of(manager, product_id: int) -> float:
    return repo.spare_stock(manager.db.read(), [product_id])[product_id]


def test_creating_an_equipment_writes_no_movement(manager):
    """Une télévision à 900 € dans un journal dont `cost_today` alimente la
    dépense alimentaire du jour rendrait ce capteur inutilisable pour toujours
    — et le journal est en ajout seul, donc la faute ne serait pas corrigible."""
    avant = len(manager.export_journal())
    manager.create_equipment(name="Télévision", purchase_price=900.0,
                             purchased_on="2024-05-02", warranty_months=24)
    assert len(manager.export_journal()) == avant


def test_an_equipment_without_a_device_is_perfectly_normal(manager):
    """Une poêle n'a pas de `device_id`. Exiger un appareil reviendrait à ne
    suivre que ce qui est connecté, ce qui exclut la moitié de la cuisine."""
    equipment_id = manager.create_equipment(name="Poêle 28 cm")
    assert manager.get_equipment(equipment_id)["device_id"] is None


def test_the_name_is_unique(manager):
    manager.create_equipment(name="Purificateur")
    with pytest.raises(sqlite3.IntegrityError):
        manager.create_equipment(name="Purificateur")


def test_creating_is_idempotent_on_its_key(manager):
    first = manager.create_equipment(name="Purificateur", idempotency_key="k")
    second = manager.create_equipment(name="Purificateur", idempotency_key="k")
    assert first == second


def test_warranties_are_computed_sorted_and_forward_looking(manager):
    manager.create_equipment(name="A", purchased_on="2025-01-01", warranty_months=24)
    manager.create_equipment(name="B", purchased_on="2024-01-01", warranty_months=24)
    manager.create_equipment(name="C", purchased_on="2020-01-01", warranty_months=24)
    noms = [w["name"] for w in manager.warranties(today=date(2026, 8, 21))]
    assert noms == ["A"]          # B a expiré en janvier 2026, C en 2022
    assert manager.warranties(today=date(2026, 8, 21))[0]["days_left"] == 133


def test_a_duration_without_a_purchase_date_is_simply_absent(manager):
    manager.create_equipment(name="A", warranty_months=24)
    assert manager.warranties(today=date(2026, 8, 21)) == []


def test_a_bad_purchase_date_is_refused_before_it_can_break_the_coordinator(manager):
    """`iso_date` existe pour ça : une date mal formée devient un ValueError à
    CHAQUE rafraîchissement du coordinateur, et toutes les entités partent en
    `unavailable` — dans une table qu'un design en ajout seul ne répare pas."""
    for mauvais in ("02/05/2024", "2024-13-01", "pas une date", 20240502):
        with pytest.raises(vol.Invalid):
            manager.create_equipment(name=f"X{mauvais}", purchased_on=mauvais)


def test_a_manual_path_that_escapes_media_is_refused(manager):
    for mauvais in ("../config/secrets.yaml", "/etc/passwd", "www/notice.pdf"):
        with pytest.raises(vol.Invalid):
            manager.create_equipment(name=f"Y{mauvais}", manual_media_id=mauvais)
    manager.create_equipment(name="OK", manual_media_id="notices/purificateur.pdf")


def test_a_receipt_path_is_guarded_exactly_like_a_manual(manager):
    with pytest.raises(vol.Invalid):
        manager.create_equipment(name="Z", receipt_media_id="../../etc/shadow")


def test_updating_an_unknown_field_is_refused(manager):
    equipment_id = manager.create_equipment(name="A")
    with pytest.raises(ValueError):
        manager.update_equipment(equipment_id, {"nom": "faute de frappe"})


def test_updating_an_unknown_equipment_says_so(manager):
    with pytest.raises(ValueError, match="unknown equipment 999"):
        manager.update_equipment(999, {"name": "X"})


def test_updating_still_guards_the_paths_and_the_dates(manager):
    equipment_id = manager.create_equipment(name="A")
    with pytest.raises(vol.Invalid):
        manager.update_equipment(equipment_id, {"manual_media_id": "www/x.pdf"})
    with pytest.raises(vol.Invalid):
        manager.update_equipment(equipment_id, {"purchased_on": "02/05/2024"})


def test_linking_a_consumable_uses_the_catalogue_and_nothing_else(manager):
    equipment_id = manager.create_equipment(name="Purificateur")
    product_id = _seed_spare(manager, name="Filtre HEPA MB4", quantity=1)
    manager.link_consumable(equipment_id=equipment_id, product_id=product_id,
                            role="filter", label="filtre HEPA",
                            low_value=15.0, keep_value=20.0, unit="percent")
    fiche = manager.get_equipment(equipment_id)
    assert fiche["consumables"][0]["product_name"] == "Filtre HEPA MB4"
    assert fiche["consumables"][0]["in_stock"] == 1.0


def test_the_same_product_can_be_two_roles_but_not_twice_the_same(manager):
    equipment_id = manager.create_equipment(name="Aspirateur")
    product_id = _seed_spare(manager, name="Brosse", quantity=2)
    manager.link_consumable(equipment_id=equipment_id, product_id=product_id, role="brush")
    manager.link_consumable(equipment_id=equipment_id, product_id=product_id, role="other")
    with pytest.raises(sqlite3.IntegrityError):
        manager.link_consumable(equipment_id=equipment_id, product_id=product_id,
                                role="brush")


def test_an_unknown_role_is_refused(manager):
    equipment_id = manager.create_equipment(name="Aspirateur")
    product_id = _seed_spare(manager, name="Brosse", quantity=2)
    with pytest.raises(vol.Invalid):
        manager.link_consumable(equipment_id=equipment_id, product_id=product_id,
                                role="courroie")


def test_unlinking_leaves_the_product_alone(manager):
    """Délier n'efface pas un produit : le filtre reste au catalogue, avec son
    stock et son historique de prix."""
    equipment_id = manager.create_equipment(name="Purificateur")
    product_id = _seed_spare(manager, name="Filtre", quantity=1)
    link_id = manager.link_consumable(equipment_id=equipment_id, product_id=product_id,
                                      role="filter")
    manager.unlink_consumable(link_id)
    assert manager.get_equipment(equipment_id)["consumables"] == []
    assert _stock_of(manager, product_id) == 1.0


def test_the_sheet_carries_the_batteries_attached_to_the_equipment(manager):
    equipment_id = manager.create_equipment(name="Interrupteur cuisine")
    manager.declare_battery(label="Interrupteur cuisine", kind="primary",
                            equipment_id=equipment_id)
    assert [b["label"] for b in manager.get_equipment(equipment_id)["batteries"]] \
        == ["Interrupteur cuisine"]


def test_list_equipment_carries_the_warranty_and_its_days_left(manager):
    manager.create_equipment(name="A", purchased_on="2025-01-01", warranty_months=24)
    manager.create_equipment(name="B")
    lignes = {row["name"]: row for row in manager.list_equipment(today=date(2026, 8, 21))}
    assert lignes["A"]["warranty_ends_on"] == "2027-01-01"
    assert lignes["A"]["days_left"] == 133
    assert lignes["B"]["warranty_ends_on"] is None and lignes["B"]["days_left"] is None


def test_an_expired_warranty_keeps_its_date_in_the_list_but_leaves_the_deadlines(manager):
    """Trois états, trois phrases distinctes côté panneau : à venir, terminée,
    absente. La liste doit donc porter la date même expirée — c'est
    `warranties()` seule qui ne regarde que l'avenir."""
    manager.create_equipment(name="Vieux", purchased_on="2020-01-01",
                             warranty_months=24)
    ligne = manager.list_equipment(today=date(2026, 8, 21))[0]
    assert ligne["warranty_ends_on"] == "2022-01-01"
    assert ligne["days_left"] == -1693
    assert manager.warranties(today=date(2026, 8, 21)) == []
