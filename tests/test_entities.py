from datetime import UTC, date, datetime, timedelta

import pytest
from homeassistant.components.todo import DATA_COMPONENT, TodoItem, TodoItemStatus
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.storage import repositories as repo


@pytest.fixture
async def loaded(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities_are_created_empty(hass, loaded):
    assert hass.states.get("sensor.home_stock_stock_value").state == "0.0"
    assert hass.states.get("sensor.home_stock_batches").state == "0"
    assert hass.states.get("binary_sensor.home_stock_expirations").state == "off"
    assert hass.states.get("binary_sensor.home_stock_shortages").state == "off"
    assert hass.states.get("sensor.home_stock_cart_total").state == "0.0"
    assert hass.states.get("sensor.home_stock_to_store").state == "0"


async def test_entities_reflect_the_stock(hass, loaded):
    manager = loaded.runtime_data.manager

    def _seed() -> None:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
            product_id = repo.insert_product(conn, name="Lait", base_unit="ml",
                                             min_quantity=2000)
            article_id = repo.insert_article(conn, product_id=product_id,
                                             kcal_per_base_unit=0.46)
        manager.add_stock(article_id=article_id, quantity=1000,
                          location_id=location_id, best_before="2026-08-19",
                          price_per_base_unit=0.0012,
                          occurred_at="2026-08-18T10:00:00")

    await hass.async_add_executor_job(_seed)
    await loaded.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.home_stock_batches").state == "1"
    stock_value = hass.states.get("sensor.home_stock_stock_value")
    assert float(stock_value.state) == 1.2
    assert stock_value.attributes["by_location"] == {"Frigo": pytest.approx(1.2)}
    assert hass.states.get("binary_sensor.home_stock_shortages").state == "on"
    shortages = hass.states.get("binary_sensor.home_stock_shortages")
    assert shortages.attributes["products"] == ["Lait"]


async def test_the_cumulative_counters_only_count_what_left_the_stock(hass, loaded):
    manager = loaded.runtime_data.manager

    def _seed() -> None:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Placard", kind="pantry")
            product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
            article_id = repo.insert_article(conn, product_id=product_id,
                                             kcal_per_base_unit=3.5)
        manager.add_stock(article_id=article_id, quantity=500,
                          location_id=location_id, price_per_base_unit=0.004,
                          occurred_at="2026-08-18T10:00:00")
        manager.consume(product_id=product_id, quantity=200,
                        occurred_at="2026-08-18T19:00:00")

    await hass.async_add_executor_job(_seed)
    await loaded.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    # The purchase of 500 g must not count: only the 200 g that left the stock.
    assert float(hass.states.get("sensor.home_stock_kcal_total").state) == 700.0
    assert float(hass.states.get("sensor.home_stock_cost_total").state) == 0.8


async def test_the_todo_list_holds_the_expiring_batches(hass, loaded):
    manager = loaded.runtime_data.manager

    def _seed() -> int:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
            product_id = repo.insert_product(conn, name="Yaourt", base_unit="piece")
            article_id = repo.insert_article(conn, product_id=product_id)
        # A date relative to today: a hard-coded one would stop expiring one day.
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        return manager.add_stock(article_id=article_id, quantity=4,
                                 location_id=location_id, best_before=tomorrow,
                                 occurred_at="2026-08-18T10:00:00")

    await hass.async_add_executor_job(_seed)
    await loaded.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    items = await hass.services.async_call(
        "todo", "get_items", {"entity_id": "todo.home_stock_expirations"},
        blocking=True, return_response=True,
    )
    listed = items["todo.home_stock_expirations"]["items"]
    assert len(listed) == 1
    assert "Yaourt" in listed[0]["summary"]


def _seed_expiring_yaourt(manager, *, price_per_base_unit=None):
    """A closure ready for hass.async_add_executor_job: seeds one expiring
    batch and returns its batch id."""
    def _seed() -> int:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
            product_id = repo.insert_product(conn, name="Yaourt", base_unit="piece")
            article_id = repo.insert_article(conn, product_id=product_id)
        # A date relative to today: a hard-coded one would stop expiring one day.
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        return manager.add_stock(article_id=article_id, quantity=4,
                                 location_id=location_id, best_before=tomorrow,
                                 price_per_base_unit=price_per_base_unit,
                                 occurred_at="2026-08-18T10:00:00")
    return _seed


async def test_checking_an_item_consumes_the_whole_batch(hass, loaded):
    manager = loaded.runtime_data.manager
    seed = _seed_expiring_yaourt(manager, price_per_base_unit=0.3)
    batch_id = await hass.async_add_executor_job(seed)
    await loaded.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    await hass.services.async_call(
        "todo", "update_item",
        {"entity_id": "todo.home_stock_expirations", "item": str(batch_id),
         "status": "completed"},
        blocking=True,
    )
    await hass.async_block_till_done()

    def _check():
        with manager.db.write() as conn:
            batch = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
            movement = conn.execute(
                "SELECT * FROM movement WHERE batch_id = ? AND reason = 'consumption'",
                (batch_id,),
            ).fetchone()
        return batch, movement

    batch, movement = await hass.async_add_executor_job(_check)
    assert batch["remaining"] == 0
    assert movement is not None


async def test_an_uncompleted_update_does_nothing(hass, loaded):
    manager = loaded.runtime_data.manager
    seed = _seed_expiring_yaourt(manager)
    batch_id = await hass.async_add_executor_job(seed)
    await loaded.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    await hass.services.async_call(
        "todo", "update_item",
        {"entity_id": "todo.home_stock_expirations", "item": str(batch_id),
         "status": "needs_action"},
        blocking=True,
    )
    await hass.async_block_till_done()

    def _check():
        with manager.db.write() as conn:
            batch = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM movement WHERE reason = 'consumption'"
            ).fetchone()["n"]
        return batch, count

    batch, count = await hass.async_add_executor_job(_check)
    assert batch["remaining"] == 4
    assert count == 0


async def test_a_stale_uid_is_a_no_op_not_an_error(hass, loaded):
    """The coordinator refreshes every 15 minutes: a batch consumed elsewhere
    in between is still checkable in the stale list. Ticking it must not blow
    up — the user's intent ("this is finished") is already true."""
    manager = loaded.runtime_data.manager
    seed = _seed_expiring_yaourt(manager)
    batch_id = await hass.async_add_executor_job(seed)
    await loaded.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    # Consumed directly, bypassing the coordinator: its cached data (and hence
    # entity.todo_items) still lists this batch as expiring.
    await hass.async_add_executor_job(manager.consume_batch, batch_id)

    # Must not raise: the frontend would otherwise show "Unknown error" for an
    # action whose intent was already satisfied.
    await hass.services.async_call(
        "todo", "update_item",
        {"entity_id": "todo.home_stock_expirations", "item": str(batch_id),
         "status": "completed"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_a_non_numeric_uid_raises_a_home_assistant_error(hass, loaded):
    """Unlike a stale batch id, this can only come from a genuine programming
    error and must surface to the frontend, not vanish as a bare ValueError."""
    entity = hass.data[DATA_COMPONENT].get_entity("todo.home_stock_expirations")
    with pytest.raises(HomeAssistantError, match="not-a-number"):
        await entity.async_update_todo_item(
            TodoItem(uid="not-a-number", status=TodoItemStatus.COMPLETED)
        )


async def test_the_four_daily_nutrients_are_on_by_default(hass, setup_entry):
    await setup_entry()
    for key in ("kcal_today", "proteins_today", "sugars_today", "salt_today",
                "cost_today", "cost_waste_total"):
        assert hass.states.get(f"sensor.home_stock_{key}") is not None, key


async def test_the_five_rarer_nutrients_are_created_but_disabled(hass, setup_entry):
    """They exist in the registry and turn on with one click — but they do not
    fill the sidebar with columns that are often empty."""
    entry = await setup_entry()
    registry = er.async_get(hass)
    for key in ("carbohydrates_today", "added_sugars_today", "fat_today",
                "saturated_fat_today", "fiber_today"):
        entity_id = f"sensor.home_stock_{key}"
        assert hass.states.get(entity_id) is None, key
        record = registry.async_get(entity_id)
        assert record is not None and record.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_kcal_today_reports_the_day_and_its_gaps(hass, setup_entry):
    # setup_entry(with_article=True) seeds an article with no
    # kcal_per_base_unit set (see conftest.py), so consuming it is genuinely
    # unvalued — this is the "gap" the test name and the sensor attribute
    # are both about, not an oversight.
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
    await hass.async_add_executor_job(
        lambda: manager.consume(product_id=1, quantity=100.0))
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_stock_kcal_today")
    assert state.attributes["unvalued_movements"] == 1
    assert state.attributes["food_day"] == entry.runtime_data.coordinator.data["today"]["food_day"]
    assert state.attributes["last_reset"] is not None


async def test_the_daily_sensors_declare_a_last_reset(hass, setup_entry):
    """TOTAL without a last_reset, a drop from 1 800 to 0 would be read as a
    meter rollover and would inflate the statistics.

    A prefix check on the year is blind to both a naive last_reset and a
    wrong-but-plausible one, so this compares against the exact aware
    datetime derived from today["start"] instead."""
    entry = await setup_entry()
    state = hass.states.get("sensor.home_stock_cost_today")
    assert state.attributes["state_class"] == "total"

    last_reset = datetime.fromisoformat(state.attributes["last_reset"])
    assert last_reset.tzinfo is not None

    expected_start = entry.runtime_data.coordinator.data["today"]["start"]
    expected = datetime.fromisoformat(expected_start).replace(tzinfo=UTC)
    assert last_reset == expected


# --- lot 5 : piles faibles, piles à déclarer, prochaine fin de garantie ------

from homeassistant.helpers import device_registry as lot5_dr
from homeassistant.helpers import entity_registry as lot5_er

import custom_components.home_stock as home_stock
from custom_components.home_stock.storage import repositories as lot5_repo


def _lot5_sensor(hass, entity_id: str, *, unique_id: str, state: str,
                 device_id: str | None = None):
    entry = lot5_er.async_get(hass).async_get_or_create(
        "sensor", "mqtt", unique_id, suggested_object_id=entity_id.split(".", 1)[1],
        original_device_class="battery", device_id=device_id)
    hass.states.async_set(entry.entity_id, state, {"device_class": "battery"})
    return entry


async def _lot5_refresh(hass, integration):
    await integration.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()


def _lot5_seed_spare(integration, *, name: str, quantity: float,
                     min_quantity: float | None = None) -> int:
    manager = integration.runtime_data.manager
    with manager.db.write() as conn:
        product_id = lot5_repo.insert_product(conn, name=name, base_unit="piece",
                                              edible=0, min_quantity=min_quantity)
        article_id = lot5_repo.insert_article(conn, product_id=product_id, is_generic=1)
        location_id = lot5_repo.insert_location(conn, name="Tiroir", kind="cupboard")
    if quantity:
        manager.add_stock(article_id=article_id, quantity=quantity,
                          location_id=location_id, occurred_at="2026-08-01T10:00:00")
    return product_id


async def test_the_three_sensors_exist_and_are_enabled(hass, setup_entry):
    await setup_entry()
    for entity_id in ("sensor.home_stock_batteries_low",
                      "sensor.home_stock_batteries_undeclared",
                      "sensor.home_stock_warranty_next"):
        assert hass.states.get(entity_id) is not None


async def test_a_zero_is_a_state_not_an_unavailable(hass, setup_entry):
    """Aucune pile faible se dit « 0 ». `unknown` ferait croire à une panne."""
    await setup_entry()
    assert hass.states.get("sensor.home_stock_batteries_low").state == "0"


async def test_batteries_low_publishes_the_list_lowest_first(hass, setup_entry):
    integration = await setup_entry()
    manager = integration.runtime_data.manager
    for label, unique_id, entity_id, percent in (
            ("A", "ua", "sensor.a_batterie", "18"),
            ("B", "ub", "sensor.b_batterie", "5")):
        entry = _lot5_sensor(hass, entity_id, unique_id=unique_id, state=percent)
        manager.declare_battery(label=label, kind="primary",
                                entity_registry_id=entry.id, tracked=True)
    await _lot5_refresh(hass, integration)
    state = hass.states.get("sensor.home_stock_batteries_low")
    assert state.state == "2"
    assert [b["label"] for b in state.attributes["batteries"]] == ["B", "A"]
    assert state.attributes["batteries"][0]["verb"] == "Pile à changer"


async def test_batteries_low_says_whether_the_spare_is_there(hass, setup_entry):
    """« 12 %, aucune en stock » est la phrase qui change ce qu'on fait le soir
    même. Elle doit être une donnée, pas une reconstruction dans une carte."""
    integration = await setup_entry()
    product_id = _lot5_seed_spare(integration, name="CR2032", quantity=0)
    entry = _lot5_sensor(hass, "sensor.velux_batterie", unique_id="u1", state="12")
    integration.runtime_data.manager.declare_battery(
        label="Velux (CH)", kind="primary", entity_registry_id=entry.id,
        tracked=True, product_id=product_id)
    await _lot5_refresh(hass, integration)
    state = hass.states.get("sensor.home_stock_batteries_low")
    assert state.attributes["batteries"][0]["spare_label"] == "CR2032"
    assert state.attributes["batteries"][0]["spare_in_stock"] == 0.0


async def test_batteries_low_counts_the_orphans_and_the_mutes_separately(hass, setup_entry):
    """Une orpheline n'est pas une pile faible : elle n'a pas de niveau du
    tout. La compter dans la valeur ferait mentir le chiffre ; ne pas la
    compter du tout la rendrait invisible."""
    integration = await setup_entry()
    integration.runtime_data.manager.declare_battery(
        label="Disparue", kind="primary", entity_registry_id="uuid-mort", tracked=True)
    await _lot5_refresh(hass, integration)
    state = hass.states.get("sensor.home_stock_batteries_low")
    assert state.state == "0"
    assert state.attributes["orphaned"] == 1
    assert state.attributes["mute"] == 0


async def test_undeclared_counts_a_brand_new_battery_sensor(hass, setup_entry):
    integration = await setup_entry()
    _lot5_sensor(hass, "sensor.nouveau_batterie", unique_id="u-neuf", state="12")
    await _lot5_refresh(hass, integration)
    state = hass.states.get("sensor.home_stock_batteries_undeclared")
    assert state.state == "1"
    assert state.attributes["entities"] == ["sensor.nouveau_batterie"]


async def test_undeclared_separates_never_seen_from_undecided(hass, setup_entry):
    integration = await setup_entry()
    _lot5_sensor(hass, "sensor.jamais_vu_batterie", unique_id="u-neuf", state="12")
    entry = _lot5_sensor(hass, "sensor.indecis_batterie", unique_id="u-ind", state="40")
    integration.runtime_data.manager.declare_battery(
        label="Indécis", kind="primary", entity_registry_id=entry.id, tracked=None)
    await _lot5_refresh(hass, integration)
    state = hass.states.get("sensor.home_stock_batteries_undeclared")
    assert state.state == "2"
    assert state.attributes["never_declared"] == 1
    assert state.attributes["undecided"] == 1


async def test_warranty_next_is_none_when_there_is_nothing_to_watch(hass, setup_entry):
    await setup_entry()
    assert hass.states.get("sensor.home_stock_warranty_next").state in ("unknown", "None")


async def test_warranty_next_counts_days_and_lists_the_deadlines(hass, setup_entry):
    integration = await setup_entry()
    integration.runtime_data.manager.create_equipment(
        name="Purificateur", purchased_on="2025-01-01", warranty_months=240)
    await _lot5_refresh(hass, integration)
    state = hass.states.get("sensor.home_stock_warranty_next")
    assert int(state.state) > 0
    assert state.attributes["warranties"][0]["name"] == "Purificateur"
    assert state.attributes["warranties"][0]["warranty_ends_on"] == "2045-01-01"


async def test_a_non_edible_spare_shows_up_in_shortages(hass, setup_entry):
    """La rupture existe déjà : c'est pour ça qu'aucun capteur de rechange
    manquante n'est créé. Ce test est ce qui rend cette absence défendable —
    sans lui, « ça marche déjà » est une supposition."""
    integration = await setup_entry()
    _lot5_seed_spare(integration, name="CR2032", quantity=0, min_quantity=2)
    await _lot5_refresh(hass, integration)
    state = hass.states.get("binary_sensor.home_stock_shortages")
    assert state.state == "on"
    assert "CR2032" in state.attributes["products"]


async def test_the_three_sensors_are_named_in_french(hass, setup_entry):
    """Les noms affichés vivent dans `translations/fr.json`, jamais en dur
    dans le code — c'est la règle de nommage du lot. Le test lit les deux
    fichiers de traduction plutôt que `friendly_name`, parce qu'un Home
    Assistant de test parle anglais : `friendly_name` y rendrait le libellé
    de `en.json`, et une assertion française passerait ou échouerait selon la
    langue du harnais, pas selon ce qui a été livré.
    """
    import json
    from pathlib import Path as _Path

    await setup_entry()
    racine = _Path(home_stock.__file__).parent / "translations"
    fr = json.loads((racine / "fr.json").read_text(encoding="utf-8"))
    en = json.loads((racine / "en.json").read_text(encoding="utf-8"))
    for cle, nom in (("batteries_low", "Piles faibles"),
                     ("batteries_undeclared", "Piles à déclarer"),
                     ("warranty_next", "Prochaine fin de garantie")):
        assert fr["entity"]["sensor"][cle]["name"] == nom
        # Les deux fichiers doivent couvrir les mêmes clés : une clé anglaise
        # manquante fait retomber le nom sur l'`entity_id` brut.
        assert en["entity"]["sensor"][cle]["name"]
        assert hass.states.get(f"sensor.home_stock_{cle}") is not None


# --- Lot 2bis : le capteur d'objectifs nutritionnels -------------------------

@pytest.fixture
async def _with_goals(hass):
    """Une entrée chargée dont les options portent des plafonds."""
    async def _load(goals):
        entry = MockConfigEntry(domain=DOMAIN, data={},
                                options={"nutrition_goals": goals})
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry
    return _load


def _seed_salty_meal(manager, *, salt_per_base_unit: float, grams: float) -> None:
    with manager.db.write() as conn:
        location_id = repo.insert_location(conn, name="Placard", kind="pantry")
        product_id = repo.insert_product(conn, name="Chips", base_unit="g")
        article_id = repo.insert_article(conn, product_id=product_id,
                                         kcal_per_base_unit=5.0,
                                         salt=salt_per_base_unit,
                                         fiber=salt_per_base_unit)
    manager.add_stock(article_id=article_id, quantity=1000.0, location_id=location_id)
    manager.consume(product_id=product_id, quantity=grams)


async def test_the_goals_sensor_is_off_when_no_goal_is_set(hass, _with_goals):
    entry = await _with_goals({})
    state = hass.states.get("binary_sensor.home_stock_nutrition_goals")
    assert state.state == "off"
    assert state.attributes["count"] == 0


async def test_a_day_over_its_salt_cap_turns_the_sensor_on(hass, _with_goals):
    entry = await _with_goals({"salt": 6.0})
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: _seed_salty_meal(manager, salt_per_base_unit=0.084, grams=100.0))
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.home_stock_nutrition_goals")
    assert state.state == "on"
    assert state.attributes["day_count"] == 1
    assert state.attributes["week_count"] == 0
    assert len(state.attributes["exceeded"]) == 1
    assert state.attributes["exceeded"][0]["nutrient"] == "salt"
    assert (state.attributes["food_day"]
            == entry.runtime_data.coordinator.data["today"]["food_day"])


async def test_a_goal_on_a_disabled_sensor_still_fires(hass, _with_goals):
    """Cinq des neuf capteurs quotidiens sont créés éteints. Un objectif posé
    sur l'un d'eux doit fonctionner sans qu'on l'allume : le calcul lit
    `coordinator.data["today"]`, jamais une entité."""
    entry = await _with_goals({"fiber": 6.0})
    registry = er.async_get(hass)
    entree = registry.async_get("sensor.home_stock_fiber_today")
    assert entree is not None and entree.disabled_by is not None

    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: _seed_salty_meal(manager, salt_per_base_unit=0.084, grams=100.0))
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.home_stock_fiber_today") is None
    state = hass.states.get("binary_sensor.home_stock_nutrition_goals")
    assert state.state == "on"
    assert state.attributes["exceeded"][0]["nutrient"] == "fiber"


async def test_the_goals_sensor_reads_no_entity_at_all():
    """Garde-fou de lecture : `binary_sensor.py` ne consulte ni un capteur par
    nutriment, ni la machine à états."""
    from pathlib import Path as _Path

    import custom_components.home_stock as _home_stock

    source = (_Path(_home_stock.__file__).parent / "binary_sensor.py").read_text()
    assert "sensor." not in source
    assert "hass.states" not in source


async def test_the_goals_blueprint_is_a_valid_automation_nobody_installs(hass):
    """Le blueprint est livré, jamais installé par le composant. Il est donc
    validé ici comme Home Assistant le validerait à l'import — schéma de
    condition et d'actions compris, un `!input` substitué par son défaut —
    et sa phrase est réellement rendue, pour qu'un attribut mal nommé ne
    passe pas pour une annonce muette."""
    from pathlib import Path

    from homeassistant.helpers import config_validation as cv
    from homeassistant.helpers.template import Template
    from homeassistant.util import yaml as yaml_util

    path = Path(__file__).resolve().parent.parent / "blueprints" / "automation" \
        / "home_stock" / "objectifs_bleuenn.yaml"
    document = yaml_util.load_yaml_dict(path)
    assert document["blueprint"]["domain"] == "automation"
    assert set(document["blueprint"]["input"]) == {"heure", "agent", "capteur"}
    # Horaire, jamais un déclencheur d'état : un passage à `on` s'annoncerait
    # au rafraîchissement du coordinateur, donc à table.
    assert document["triggers"][0]["trigger"] == "time"
    assert document["blueprint"]["input"]["heure"]["default"] == "21:30:00"

    defaults = {name: spec["default"]
                for name, spec in document["blueprint"]["input"].items()}
    substituted = yaml_util.substitute(document, defaults)
    assert cv.CONDITION_SCHEMA(substituted["conditions"][0])["condition"] == "state"
    action = cv.SCRIPT_SCHEMA(substituted["actions"])[0]
    assert action["action"] == "conversation.process"

    # Aucune référence à un capteur par nutriment : `state()` y rendrait
    # `unavailable` sur une entité éteinte, et une automation qui ne se
    # déclenche jamais est le pire des états.
    texte = substituted["actions"][0]["data"]["text"]
    assert "home_stock_salt_today" not in texte
    assert substituted["variables"]["nom_capteur"] == defaults["capteur"]

    hass.states.async_set(
        defaults["capteur"], "on",
        {"exceeded": [{"nutrient": "salt", "scope": "day", "value": 8.4,
                       "goal": 6.0, "ratio": 1.4},
                      {"nutrient": "kcal", "scope": "week", "value": 2400.0,
                       "goal": 2000.0, "ratio": 1.2}]})
    rendu = Template(texte, hass).async_render(
        variables=substituted["variables"], parse_result=False)
    assert "le sel aujourd'hui" in " ".join(rendu.split())
    assert "l'énergie en moyenne sur la semaine" in " ".join(rendu.split())
