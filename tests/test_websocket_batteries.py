"""Les onze commandes du lot 5, et le contrôle croisé des deux surfaces.

Le test qui compte le plus ici est `test_neither_surface_is_weaker_than_the_
other` : la même charge doit être refusée PAR LES DEUX. C'est la divergence
qu'on cherche à empêcher, pas la couverture.
"""
import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.home_stock.const import DOMAIN


def _sensor(hass, entity_id: str, *, unique_id: str, state: str = "50"):
    entry = er.async_get(hass).async_get_or_create(
        "sensor", "mqtt", unique_id, suggested_object_id=entity_id.split(".", 1)[1],
        original_device_class="battery")
    hass.states.async_set(entry.entity_id, state, {"device_class": "battery"})
    return entry


async def _appel(client, charge):
    charge = {"id": charge.pop("id", 1), **charge}
    await client.send_json(charge)
    return await client.receive_json()


def _seed_spare(integration, *, name: str, quantity: float) -> int:
    from custom_components.home_stock.storage import repositories as repo
    manager = integration.runtime_data.manager
    with manager.db.write() as conn:
        product_id = repo.insert_product(conn, name=name, base_unit="piece", edible=0)
        article_id = repo.insert_article(conn, product_id=product_id, is_generic=1)
        location_id = repo.insert_location(conn, name="Tiroir", kind="cupboard")
    if quantity:
        manager.add_stock(article_id=article_id, quantity=quantity,
                          location_id=location_id, occurred_at="2026-08-01T10:00:00")
    return product_id


async def test_discover_writes_nothing(hass, setup_entry, hass_ws_client):
    """Une commande qui s'appelle « découvrir » ne doit rien créer : sinon le
    seul fait d'ouvrir l'écran Piles peuplerait la base de 28 lignes."""
    integration = await setup_entry()
    _sensor(hass, "sensor.x_batterie", unique_id="u1")
    client = await hass_ws_client(hass)
    reponse = await _appel(client, {"type": "home_stock/batteries/discover"})
    assert reponse["success"] and len(reponse["result"]["sensors"]) == 1
    assert integration.runtime_data.manager.list_batteries() == []


async def test_declare_then_list_round_trips(hass, setup_entry, hass_ws_client):
    await setup_entry()
    client = await hass_ws_client(hass)
    entry = _sensor(hass, "sensor.velux_batterie", unique_id="u1", state="18")
    cree = await _appel(client, {"type": "home_stock/battery/declare",
                                 "label": "Velux (CH)", "kind": "primary",
                                 "entity_registry_id": entry.id, "tracked": True})
    assert cree["success"]
    liste = await _appel(client, {"id": 2, "type": "home_stock/batteries/list"})
    ligne = liste["result"]["batteries"][0]
    assert ligne["label"] == "Velux (CH)"
    assert ligne["verb"] == "Pile à changer"
    assert ligne["entity_id"] == "sensor.velux_batterie"
    assert ligne["orphaned"] is False


async def test_list_says_an_orphan_is_an_orphan(hass, setup_entry, hass_ws_client):
    await setup_entry()
    client = await hass_ws_client(hass)
    await _appel(client, {"type": "home_stock/battery/declare", "label": "X",
                          "kind": "primary", "entity_registry_id": "uuid-mort"})
    liste = await _appel(client, {"id": 2, "type": "home_stock/batteries/list"})
    assert liste["result"]["batteries"][0]["orphaned"] is True


async def test_ignoring_a_battery_without_a_reason_is_refused(hass, setup_entry,
                                                              hass_ws_client):
    """Le bouton « ignorer » du panneau : la colonne exige un motif, donc le
    panneau doit en demander un, donc le serveur doit refuser sans."""
    await setup_entry()
    client = await hass_ws_client(hass)
    reponse = await _appel(client, {"type": "home_stock/battery/declare",
                                    "label": "Tablette", "kind": "primary",
                                    "tracked": False})
    assert not reponse["success"]
    assert "motif" in reponse["error"]["message"]


async def test_ignoring_a_battery_with_a_reason_is_accepted(hass, setup_entry,
                                                            hass_ws_client):
    integration = await setup_entry()
    client = await hass_ws_client(hass)
    reponse = await _appel(client, {"type": "home_stock/battery/declare",
                                    "label": "Tablette", "kind": "primary",
                                    "tracked": False,
                                    "exclusion_reason": "tablette sur secteur"})
    assert reponse["success"]
    assert integration.runtime_data.manager.list_batteries()[0]["tracked"] is False


@pytest.mark.parametrize("charge,attendu", [
    ({"kind": "built_in", "product_id": 1}, "batterie intégrée"),
    ({"kind": "primary", "low_percent": 20, "keep_percent": 10}, "seuil de maintien"),
    ({"kind": "primary", "cell_count": 0}, None),
    ({"kind": "nimh"}, None),
    ({"kind": "primary", "low_percent": 120}, None),
    ({"kind": "primary", "installed_on": "02/05/2024"}, None),
    ({"kind": "primary", "tracked": False}, "motif"),
])
async def test_neither_surface_is_weaker_than_the_other(hass, setup_entry,
                                                        hass_ws_client, charge, attendu):
    """Le contrôle croisé du lot 2, appliqué à chaque contrainte du § 12.2 :
    la même charge doit être refusée PAR LES DEUX surfaces."""
    integration = await setup_entry()
    client = await hass_ws_client(hass)
    reponse = await _appel(client, {"type": "home_stock/battery/declare",
                                    "label": "X", **charge})
    assert not reponse["success"], reponse
    if attendu:
        assert attendu in reponse["error"]["message"]

    # ... et l'application, qui est la porte que l'import emprunte.
    with pytest.raises((vol.Invalid, ValueError)):
        integration.runtime_data.manager.declare_battery(label="X", **charge)


@pytest.mark.parametrize("kind,battery_kind", [
    ("charge", "primary"),
    ("replacement", "built_in"),
])
async def test_an_impossible_event_is_refused_by_both_surfaces(hass, setup_entry,
                                                               hass_ws_client,
                                                               kind, battery_kind):
    integration = await setup_entry()
    manager = integration.runtime_data.manager
    battery_id = manager.declare_battery(label="X", kind=battery_kind)
    client = await hass_ws_client(hass)
    reponse = await _appel(client, {"type": "home_stock/battery/event",
                                    "battery_id": battery_id, "kind": kind})
    assert not reponse["success"]
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "record_battery_event",
            {"battery_id": battery_id, "kind": kind}, blocking=True)


WRITE_COMMANDS = (
    "home_stock/battery/declare", "home_stock/battery/update",
    "home_stock/battery/event", "home_stock/equipment/create",
    "home_stock/equipment/update", "home_stock/equipment/consumable/link",
    "home_stock/equipment/consumable/unlink",
)


async def test_every_write_command_accepts_an_idempotency_key(hass, setup_entry,
                                                              hass_ws_client):
    """Le contrat du lot 1 : la file hors-ligne estampille TOUTE action d'une
    clé, sans notion de « cette commande n'en prend pas ». Un schéma strict
    sans la clé fait refuser le tout premier rejeu hors-ligne."""
    integration = await setup_entry()
    manager = integration.runtime_data.manager
    battery_id = manager.declare_battery(label="Pile", kind="rechargeable_cell")
    equipment_id = manager.create_equipment(name="Purificateur")
    product_id = _seed_spare(integration, name="Filtre", quantity=1)
    link_id = manager.link_consumable(equipment_id=equipment_id,
                                      product_id=product_id, role="filter")
    client = await hass_ws_client(hass)
    charges = {
        "home_stock/battery/declare": {"label": "Neuve", "kind": "primary"},
        "home_stock/battery/update": {"battery_id": battery_id,
                                      "fields": {"label": "Renommée"}},
        "home_stock/battery/event": {"battery_id": battery_id, "kind": "charge"},
        "home_stock/equipment/create": {"name": "Aspirateur"},
        "home_stock/equipment/update": {"equipment_id": equipment_id,
                                        "fields": {"brand": "Xiaomi"}},
        "home_stock/equipment/consumable/link": {"equipment_id": equipment_id,
                                                 "product_id": product_id,
                                                 "role": "brush"},
        "home_stock/equipment/consumable/unlink": {"consumable_id": link_id},
    }
    for index, type_ in enumerate(WRITE_COMMANDS, start=1):
        reponse = await _appel(client, {"id": index, "type": type_,
                                        **charges[type_],
                                        "idempotency_key": f"cle-{index}"})
        assert reponse["success"], (type_, reponse)


async def test_an_event_replayed_from_the_queue_decrements_once(hass, setup_entry,
                                                                hass_ws_client):
    integration = await setup_entry()
    manager = integration.runtime_data.manager
    product_id = _seed_spare(integration, name="CR2032", quantity=3)
    battery_id = manager.declare_battery(label="X", kind="primary",
                                         product_id=product_id)
    client = await hass_ws_client(hass)
    for index in (1, 2):
        reponse = await _appel(client, {"id": index, "type": "home_stock/battery/event",
                                        "battery_id": battery_id,
                                        "kind": "replacement",
                                        "idempotency_key": "k"})
        assert reponse["success"]
    from custom_components.home_stock.storage import repositories as repo
    assert repo.spare_stock(manager.db.read(), [product_id])[product_id] == 2.0
    assert len(manager.list_battery_events(battery_id)) == 1


async def test_an_event_reports_a_stock_refusal_instead_of_hiding_it(hass, setup_entry,
                                                                     hass_ws_client):
    """Perdre ce refus, c'est laisser croire qu'il reste une CR2032."""
    integration = await setup_entry()
    manager = integration.runtime_data.manager
    product_id = _seed_spare(integration, name="CR2032", quantity=0)
    battery_id = manager.declare_battery(label="X", kind="primary",
                                         product_id=product_id)
    client = await hass_ws_client(hass)
    reponse = await _appel(client, {"type": "home_stock/battery/event",
                                    "battery_id": battery_id, "kind": "replacement"})
    assert reponse["success"]
    assert "Stock insuffisant" in reponse["result"]["spare_refused"]


async def test_equipment_get_carries_its_consumables_and_its_batteries(hass, setup_entry,
                                                                       hass_ws_client):
    integration = await setup_entry()
    manager = integration.runtime_data.manager
    equipment_id = manager.create_equipment(name="Purificateur")
    product_id = _seed_spare(integration, name="Filtre HEPA MB4", quantity=1)
    manager.link_consumable(equipment_id=equipment_id, product_id=product_id,
                            role="filter", unit="percent")
    manager.declare_battery(label="Télécommande", kind="primary",
                            equipment_id=equipment_id)
    client = await hass_ws_client(hass)
    reponse = await _appel(client, {"type": "home_stock/equipment/get",
                                    "equipment_id": equipment_id})
    fiche = reponse["result"]["equipment"]
    assert fiche["consumables"][0]["product_name"] == "Filtre HEPA MB4"
    assert fiche["consumables"][0]["in_stock"] == 1.0
    assert [b["label"] for b in fiche["batteries"]] == ["Télécommande"]


async def test_equipment_list_groups_nothing_but_carries_the_location(hass, setup_entry,
                                                                      hass_ws_client):
    integration = await setup_entry()
    integration.runtime_data.manager.create_equipment(name="Poêle")
    client = await hass_ws_client(hass)
    reponse = await _appel(client, {"type": "home_stock/equipment/list"})
    assert reponse["result"]["equipment"][0]["name"] == "Poêle"
    assert reponse["result"]["equipment"][0]["location_name"] is None


async def test_a_manual_path_under_www_is_refused(hass, setup_entry, hass_ws_client):
    """Tout ce qui est sous `www/` est servi sur `/local/` SANS
    authentification, et une notice porte un numéro de série."""
    await setup_entry()
    client = await hass_ws_client(hass)
    reponse = await _appel(client, {"type": "home_stock/equipment/create",
                                    "name": "X", "manual_media_id": "www/notice.pdf"})
    assert not reponse["success"]


@pytest.mark.parametrize("type_,charge", [
    ("home_stock/batteries/list", {}),
    ("home_stock/batteries/discover", {}),
    ("home_stock/battery/declare", {"label": "X", "kind": "primary"}),
    ("home_stock/battery/update", {"battery_id": 1, "fields": {"label": "X"}}),
    ("home_stock/battery/event", {"battery_id": 1, "kind": "charge"}),
    ("home_stock/equipment/list", {}),
    ("home_stock/equipment/get", {"equipment_id": 1}),
    ("home_stock/equipment/create", {"name": "X"}),
    ("home_stock/equipment/update", {"equipment_id": 1, "fields": {"brand": "X"}}),
    ("home_stock/equipment/consumable/link", {"equipment_id": 1, "product_id": 1,
                                              "role": "filter"}),
    ("home_stock/equipment/consumable/unlink", {"consumable_id": 1}),
])
async def test_commands_answer_not_loaded_when_the_entry_is_gone(hass, setup_entry,
                                                                 hass_ws_client,
                                                                 type_, charge):
    """Le comportement du lot 1 pour toutes les commandes : `_send_not_loaded`,
    pas une exception. C'est aussi ce qui fait que le panneau met en file au
    lieu de perdre l'écriture."""
    entry = await setup_entry()
    client = await hass_ws_client(hass)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    reponse = await _appel(client, {"type": type_, **charge})
    assert not reponse["success"]
    assert reponse["error"]["code"] == "not_loaded"


async def test_the_eleven_commands_are_all_registered(hass, setup_entry, hass_ws_client):
    """Onze, pas dix : une commande oubliée à l'enregistrement se voit
    autrement au premier appui sur un bouton du panneau, en production."""
    await setup_entry()
    client = await hass_ws_client(hass)
    for index, type_ in enumerate((
            "home_stock/batteries/list", "home_stock/batteries/discover",
            "home_stock/battery/declare", "home_stock/battery/update",
            "home_stock/battery/event", "home_stock/equipment/list",
            "home_stock/equipment/get", "home_stock/equipment/create",
            "home_stock/equipment/update",
            "home_stock/equipment/consumable/link",
            "home_stock/equipment/consumable/unlink"), start=1):
        reponse = await _appel(client, {"id": index, "type": type_})
        # Appelées sans argument : certaines réussissent (les lectures), les
        # autres refusent sur leur schéma. Ce qu'on interdit, c'est
        # `unknown_command` — une commande oubliée à l'enregistrement se
        # verrait autrement au premier appui sur un bouton, en production.
        code = reponse.get("error", {}).get("code")
        assert code != "unknown_command", type_
