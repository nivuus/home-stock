"""Les ancres, les relevés, et `last_reading_at` en base.

Ce que ce fichier protège tient en une phrase : `last_reading_at` doit dire
« l'appareil a parlé », jamais « on a regardé ». C'est ce qui autorise à
remonter le seuil « Pile HS ? » de 1 h à 26 h sans recréer le trou de neuf
jours d'août 2026, où la porte d'entrée est restée muette sans jamais
produire de tâche faute d'un uptime de Home Assistant assez long.
"""
import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.home_stock.coordinator import (
    resolve_battery_anchors, undeclared_battery_sensors,
)


def _register_battery_sensor(hass, *, entity_id: str, unique_id: str,
                             state: str | None = None, device_id: str | None = None):
    """Une entité `sensor` de device_class `battery` dans le registre, comme
    MQTT discovery en crée une."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        "sensor", "mqtt", unique_id, suggested_object_id=entity_id.split(".", 1)[1],
        original_device_class="battery", device_id=device_id,
    )
    if state is not None:
        hass.states.async_set(entry.entity_id, state,
                              {"device_class": "battery", "unit_of_measurement": "%"})
    return entry


def _declare(integration, **kwargs):
    return integration.runtime_data.manager.declare_battery(**kwargs)


async def _refresh(hass, integration):
    await integration.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()


def _rows(integration):
    return integration.runtime_data.coordinator.data["batteries"]


def _undeclared(integration):
    return [row["entity_id"]
            for row in integration.runtime_data.coordinator.data["undeclared_batteries"]]


def _batteries(integration):
    return integration.runtime_data.manager.list_batteries()


async def test_a_numeric_reading_is_written_to_the_database(hass, setup_entry):
    integration = await setup_entry()
    entry = _register_battery_sensor(hass, entity_id="sensor.velux_ch_batterie",
                                     unique_id="u1", state="18")
    _declare(integration, label="Velux (CH)", kind="primary",
             entity_registry_id=entry.id)
    await _refresh(hass, integration)
    row = _batteries(integration)[0]
    assert row["last_percent"] == 18.0
    assert row["last_reading_at"] is not None


async def test_an_unavailable_state_writes_nothing(hass, setup_entry):
    """La date doit dire « l'appareil a parlé », pas « on a regardé ». La
    confondre avec la seconde vide le seuil de 26 h de tout son sens."""
    integration = await setup_entry()
    entry = _register_battery_sensor(hass, entity_id="sensor.x_batterie",
                                     unique_id="u1", state="18")
    _declare(integration, label="X", kind="primary", entity_registry_id=entry.id)
    await _refresh(hass, integration)
    avant = _batteries(integration)[0]["last_reading_at"]
    hass.states.async_set(entry.entity_id, "unavailable", {"device_class": "battery"})
    await _refresh(hass, integration)
    assert _batteries(integration)[0]["last_reading_at"] == avant


@pytest.mark.parametrize("state", ["unknown", "faible", ""])
async def test_a_non_numeric_state_writes_nothing(hass, setup_entry, state):
    integration = await setup_entry()
    entry = _register_battery_sensor(hass, entity_id="sensor.x_batterie",
                                     unique_id="u1", state="18")
    _declare(integration, label="X", kind="primary", entity_registry_id=entry.id)
    await _refresh(hass, integration)
    avant = _batteries(integration)[0]["last_reading_at"]
    hass.states.async_set(entry.entity_id, state, {"device_class": "battery"})
    await _refresh(hass, integration)
    assert _batteries(integration)[0]["last_reading_at"] == avant
    assert _batteries(integration)[0]["last_percent"] == 18.0


async def test_the_reading_survives_a_reload(hass, setup_entry):
    """LE test de l'amélioration : `last_changed` repart au démarrage de HA,
    `last_reading_at` non — il vit en base."""
    integration = await setup_entry()
    entry = _register_battery_sensor(hass, entity_id="sensor.x_batterie",
                                     unique_id="u1", state="18")
    _declare(integration, label="X", kind="primary", entity_registry_id=entry.id)
    await _refresh(hass, integration)
    attendu = _batteries(integration)[0]["last_reading_at"]

    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    assert integration.runtime_data.manager.list_batteries()[0]["last_reading_at"] \
        == attendu


async def test_renaming_the_entity_changes_nothing(hass, setup_entry):
    """L'ancre est l'`id` du registre, un UUID que l'interface n'expose même
    pas. C'est tout l'intérêt du choix."""
    integration = await setup_entry()
    entry = _register_battery_sensor(hass, entity_id="sensor.x_batterie",
                                     unique_id="u1", state="18")
    _declare(integration, label="X", kind="primary", entity_registry_id=entry.id)
    er.async_get(hass).async_update_entity(
        entry.entity_id, new_entity_id="sensor.completement_autre_chose")
    hass.states.async_set("sensor.completement_autre_chose", "12",
                          {"device_class": "battery"})
    await _refresh(hass, integration)
    assert _batteries(integration)[0]["last_percent"] == 12.0


async def test_a_vanished_registry_entry_makes_the_battery_orphaned(hass, setup_entry):
    integration = await setup_entry()
    _declare(integration, label="X", kind="primary",
             entity_registry_id="uuid-disparu")
    await _refresh(hass, integration)
    ligne = _rows(integration)[0]
    assert ligne["orphaned"] is True
    assert ligne["entity_id"] is None


async def test_an_orphaned_battery_never_closes_its_task(hass, setup_entry):
    """Une migration d'intégration (ZHA → Z2M, le 2026-07-14) en frappe
    plusieurs d'un coup ; c'est le jour où fermer serait le plus faux."""
    integration = await setup_entry()
    _declare(integration, label="X", kind="primary",
             entity_registry_id="uuid-disparu", tracked=True)
    await _refresh(hass, integration)
    plan = await integration.runtime_data.coordinator.async_maintenance_plan()
    assert plan["items"] == []
    assert "Pile à changer — X" in plan["keep"]
    assert plan["complete"] is True


async def test_an_orphan_is_still_tracked_not_excluded(hass, setup_entry):
    """`orphaned` n'est pas `tracked = 0` : la pile reste suivie, elle est
    juste injoignable."""
    integration = await setup_entry()
    _declare(integration, label="X", kind="primary",
             entity_registry_id="uuid-disparu", tracked=True)
    await _refresh(hass, integration)
    assert _rows(integration)[0]["tracked"] is True


async def test_undeclared_sensors_are_counted_not_created(hass, setup_entry):
    """Le coordinateur ne déclare rien tout seul : il compte. La déclaration
    est un geste, au panneau ou par l'import."""
    integration = await setup_entry()
    _register_battery_sensor(hass, entity_id="sensor.nouveau_batterie",
                             unique_id="u-neuf", state="12")
    await _refresh(hass, integration)
    assert integration.runtime_data.manager.list_batteries() == []
    assert _undeclared(integration) == ["sensor.nouveau_batterie"]


async def test_a_declared_but_undecided_battery_counts_as_undeclared(hass, setup_entry):
    """`tracked = NULL` veut dire « découvert, pas décidé » : la pile est
    silencieuse dans todo.maintenance, mais visible dans le compteur."""
    integration = await setup_entry()
    entry = _register_battery_sensor(hass, entity_id="sensor.x_batterie",
                                     unique_id="u1", state="12")
    _declare(integration, label="X", kind="primary", entity_registry_id=entry.id,
             tracked=None)
    await _refresh(hass, integration)
    assert _undeclared(integration) == ["sensor.x_batterie"]


async def test_a_tracked_battery_is_not_counted_as_undeclared(hass, setup_entry):
    integration = await setup_entry()
    entry = _register_battery_sensor(hass, entity_id="sensor.x_batterie",
                                     unique_id="u1", state="12")
    _declare(integration, label="X", kind="primary", entity_registry_id=entry.id,
             tracked=True)
    await _refresh(hass, integration)
    assert _undeclared(integration) == []


async def test_an_excluded_battery_is_not_counted_as_undeclared(hass, setup_entry):
    """`tracked = 0` est une décision prise : elle ne doit plus réclamer
    d'attention, sinon le compteur ne descend jamais à zéro."""
    integration = await setup_entry()
    entry = _register_battery_sensor(hass, entity_id="sensor.tablette_batterie",
                                     unique_id="u1", state="80")
    _declare(integration, label="Tablette", kind="primary",
             entity_registry_id=entry.id, tracked=False,
             exclusion_reason="tablette sur secteur")
    await _refresh(hass, integration)
    assert _undeclared(integration) == []


async def test_the_device_name_comes_from_the_device_registry(hass, setup_entry):
    """Le `device_id` porte le NOM VIVANT — c'est ce qui remplace la chaîne de
    replace() du macro, qui suivait la langue de l'intégration d'origine."""
    integration = await setup_entry()
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={("mqtt", "velux")}, name="Velux (CH)", model="PARASOLL")
    entry = _register_battery_sensor(hass, entity_id="sensor.velux_ch_batterie",
                                     unique_id="u1", state="18", device_id=device.id)
    _declare(integration, label="Velux (CH)", kind="primary",
             entity_registry_id=entry.id)
    await _refresh(hass, integration)
    ligne = _rows(integration)[0]
    assert ligne["device_name"] == "Velux (CH)"
    assert ligne["model"] == "PARASOLL"


async def test_a_refresh_without_any_battery_costs_no_write(hass, setup_entry):
    """14 UPDATE toutes les 15 minutes dans une base à écrivain unique, c'est
    1 344 transactions par jour pour rien."""
    integration = await setup_entry()
    ecritures = []
    manager = integration.runtime_data.manager
    original = manager.record_readings
    manager.record_readings = lambda relevés: (ecritures.append(relevés),
                                               original(relevés))[1]
    await _refresh(hass, integration)
    assert ecritures == []


async def test_an_unchanged_percent_still_refreshes_the_moment(hass, setup_entry):
    """Une valeur identique n'est pas un silence : l'appareil a bien parlé.
    Sinon une pile stable à 100 % passerait pour muette au bout de 26 h."""
    integration = await setup_entry()
    entry = _register_battery_sensor(hass, entity_id="sensor.x_batterie",
                                     unique_id="u1", state="100")
    _declare(integration, label="X", kind="primary", entity_registry_id=entry.id)
    await _refresh(hass, integration)
    premier = _batteries(integration)[0]["last_reading_at"]
    manager = integration.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.record_readings([(1, 100.0, "2020-01-01T00:00:00")]))
    await _refresh(hass, integration)
    assert _batteries(integration)[0]["last_reading_at"] != "2020-01-01T00:00:00"
    assert premier is not None


async def test_the_warranties_land_in_the_coordinator_data(hass, setup_entry):
    integration = await setup_entry()
    integration.runtime_data.manager.create_equipment(
        name="Purificateur", purchased_on="2025-01-01", warranty_months=240)
    await _refresh(hass, integration)
    assert [w["name"] for w in
            integration.runtime_data.coordinator.data["warranties"]] == ["Purificateur"]


async def test_resolve_battery_anchors_is_callable_without_a_coordinator(hass):
    """Fonction module-level, testable sans démarrer un coordinateur."""
    assert resolve_battery_anchors(hass, []) == []
    assert undeclared_battery_sensors(hass, set()) == []
