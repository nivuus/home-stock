"""Les services du lot 5, et la règle « aucune surface n'est la plus faible ».

`import_grocy_equipment` n'est PAS ici : son module et sa fixture Grocy
naissent à la tâche 13, et un service ne se teste pas deux tâches avant son
implémentation. Il est enregistré et testé là-bas.
"""
import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.home_stock.const import DOMAIN


def _declare(integration, **kwargs):
    return integration.runtime_data.manager.declare_battery(**kwargs)


def _sensor(hass, entity_id: str, *, unique_id: str, state: str):
    entry = er.async_get(hass).async_get_or_create(
        "sensor", "mqtt", unique_id, suggested_object_id=entity_id.split(".", 1)[1],
        original_device_class="battery")
    hass.states.async_set(entry.entity_id, state, {"device_class": "battery"})
    return entry


async def test_maintenance_plan_called_bare_returns_the_batteries_alone(hass, setup_entry):
    await setup_entry()
    reponse = await hass.services.async_call(
        DOMAIN, "maintenance_plan", {}, blocking=True, return_response=True)
    assert set(reponse) == {"items", "keep", "complete"}
    assert reponse["complete"] is True


async def test_maintenance_plan_merges_the_macro_plan(hass, setup_entry):
    await setup_entry()
    reponse = await hass.services.async_call(
        DOMAIN, "maintenance_plan",
        {"extra_items": [{"summary": "Arroser Plante", "description": "18 %",
                          "entity": "sensor.plante_humidite"}],
         "extra_keep": ["Arroser Plante"]},
        blocking=True, return_response=True)
    assert [i["summary"] for i in reponse["items"]][0] == "Arroser Plante"
    assert reponse["keep"] == ["Arroser Plante"]


async def test_maintenance_plan_copies_what_it_does_not_understand(hass, setup_entry):
    """Un service qui refuserait un item malformé ferait disparaître la tâche
    du purificateur au premier changement de macro."""
    await setup_entry()
    reponse = await hass.services.async_call(
        DOMAIN, "maintenance_plan",
        {"extra_items": [{"summary": "Vider la poubelle"}, {"forme": "inconnue"}],
         "extra_keep": ["Vider la poubelle"]},
        blocking=True, return_response=True)
    assert {"forme": "inconnue"} in reponse["items"]


async def test_maintenance_plan_refuses_a_container_that_is_not_a_list(hass, setup_entry):
    """La validation porte sur la FORME DU CONTENEUR, pas sur le contenu de
    chaque item : c'est le raccord qui est cassé si `extra_items` n'est pas
    une liste, et le raccord doit alors désarmer la fermeture."""
    await setup_entry()
    with pytest.raises((vol.Invalid, HomeAssistantError)):
        await hass.services.async_call(
            DOMAIN, "maintenance_plan", {"extra_items": "pas une liste"},
            blocking=True, return_response=True)


async def test_maintenance_plan_sees_the_battery_of_a_resolved_anchor(hass, setup_entry):
    integration = await setup_entry()
    entry = _sensor(hass, "sensor.velux_ch_batterie", unique_id="u1", state="18")
    _declare(integration, label="Velux (CH)", kind="primary",
             entity_registry_id=entry.id, tracked=True)
    await integration.runtime_data.coordinator.async_refresh()
    reponse = await hass.services.async_call(
        DOMAIN, "maintenance_plan", {}, blocking=True, return_response=True)
    assert [i["summary"] for i in reponse["items"]] == ["Pile à changer — Velux (CH)"]
    assert reponse["items"][0]["description"] == "18 %"


async def test_record_battery_event_refuses_a_charge_on_a_primary(hass, setup_entry):
    """La règle du lot 2 : ce que le websocket refuse, le service le refuse.
    Le message est en français, parce qu'un service est aussi une réponse
    vocale."""
    integration = await setup_entry()
    battery_id = _declare(integration, label="X", kind="primary")
    with pytest.raises(HomeAssistantError, match="ne se recharge pas"):
        await hass.services.async_call(
            DOMAIN, "record_battery_event",
            {"battery_id": battery_id, "kind": "charge"}, blocking=True)


async def test_record_battery_event_refuses_an_unknown_kind(hass, setup_entry):
    integration = await setup_entry()
    battery_id = _declare(integration, label="X", kind="primary")
    with pytest.raises((vol.Invalid, HomeAssistantError)):
        await hass.services.async_call(
            DOMAIN, "record_battery_event",
            {"battery_id": battery_id, "kind": "explosion"}, blocking=True)


async def test_record_battery_event_refuses_an_unknown_battery_in_french(hass, setup_entry):
    await setup_entry()
    with pytest.raises(HomeAssistantError, match="inconnue"):
        await hass.services.async_call(
            DOMAIN, "record_battery_event",
            {"battery_id": 999, "kind": "charge"}, blocking=True)


async def test_record_battery_event_refuses_a_bad_date(hass, setup_entry):
    integration = await setup_entry()
    battery_id = _declare(integration, label="X", kind="primary")
    with pytest.raises((vol.Invalid, HomeAssistantError)):
        await hass.services.async_call(
            DOMAIN, "record_battery_event",
            {"battery_id": battery_id, "kind": "replacement",
             "occurred_at": "02/05/2024"}, blocking=True)


async def test_record_battery_event_is_idempotent(hass, setup_entry):
    integration = await setup_entry()
    manager = integration.runtime_data.manager
    battery_id = _declare(integration, label="X", kind="primary")
    for _ in range(2):
        await hass.services.async_call(
            DOMAIN, "record_battery_event",
            {"battery_id": battery_id, "kind": "replacement",
             "idempotency_key": "k"}, blocking=True)
    assert len(manager.list_battery_events(battery_id)) == 1


async def test_record_battery_event_records_it(hass, setup_entry):
    integration = await setup_entry()
    manager = integration.runtime_data.manager
    battery_id = _declare(integration, label="Capteur", kind="rechargeable_cell")
    await hass.services.async_call(
        DOMAIN, "record_battery_event",
        {"battery_id": battery_id, "kind": "charge"}, blocking=True)
    assert [e["kind"] for e in manager.list_battery_events(battery_id)] == ["charge"]


async def test_the_two_services_are_described_in_services_yaml(hass, setup_entry):
    """Un service que personne n'appellera jamais à la main doit dire à quoi
    il sert ET qui l'appelle, sinon il devient indéchiffrable en six mois."""
    import yaml
    from pathlib import Path

    import custom_components.home_stock as home_stock

    decrit = yaml.safe_load(
        (Path(home_stock.__file__).parent / "services.yaml").read_text(encoding="utf-8"))
    assert "maintenance_plan" in decrit and "record_battery_event" in decrit
    assert "maintenance_sync_taches" in decrit["maintenance_plan"]["description"]


async def test_import_grocy_equipment_is_a_dry_run_by_default(hass, setup_entry, tmp_path):
    """`apply` faux parcourt tout et rapporte tout : c'est le seul contrôle
    avant une bascule irréversible côté tâches."""
    import sqlite3
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "grocy" / "equipment.sql"
    copie = tmp_path / "grocy.db"
    conn = sqlite3.connect(str(copie))
    conn.executescript(fixture.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()

    integration = await setup_entry()
    reponse = await hass.services.async_call(
        DOMAIN, "import_grocy_equipment", {"database_path": str(copie)},
        blocking=True, return_response=True)
    assert reponse["applied"] is False
    assert reponse["equipment"] == 34
    assert integration.runtime_data.manager.list_batteries() == []


async def test_import_grocy_equipment_writes_when_asked(hass, setup_entry, tmp_path):
    import sqlite3
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "grocy" / "equipment.sql"
    copie = tmp_path / "grocy.db"
    conn = sqlite3.connect(str(copie))
    conn.executescript(fixture.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()

    integration = await setup_entry()
    reponse = await hass.services.async_call(
        DOMAIN, "import_grocy_equipment",
        {"database_path": str(copie), "apply": True},
        blocking=True, return_response=True)
    assert reponse["applied"] is True
    assert len(integration.runtime_data.manager.list_equipment()) == 34
