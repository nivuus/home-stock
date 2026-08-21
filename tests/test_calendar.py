"""`calendar.home_stock_meals` : le planning, posable depuis n'importe quelle carte."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from homeassistant.components.calendar import CalendarEntityFeature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from custom_components.home_stock.storage import repositories as repo

ENTITY = "calendar.home_stock_meals"
PARIS = ZoneInfo("Europe/Paris")


@pytest.fixture(autouse=True)
async def _paris(hass):
    await hass.config.async_set_time_zone("Europe/Paris")


async def _entity(hass):
    return hass.data["entity_components"]["calendar"].get_entity(ENTITY)


async def _seed(hass, entry, *, recipes=(), meals=()):
    manager = entry.runtime_data.manager

    def _write():
        ids = {}
        with manager.db.write() as conn:
            for name in recipes:
                ids[name] = repo.insert_recipe(
                    conn, name=name, source="manual",
                    created_at="2026-08-21T10:00:00", servings=2)
        return ids

    ids = await hass.async_add_executor_job(_write)
    posted = []
    for meal in meals:
        kwargs = dict(meal)
        if "recipe" in kwargs:
            kwargs["recipe_id"] = ids[kwargs.pop("recipe")]
        posted.append(await hass.async_add_executor_job(
            lambda k=kwargs: manager.plan_meal(**k)))
    return ids, posted


# --- l'entité ---------------------------------------------------------------

async def test_the_calendar_entity_exists(hass, setup_entry):
    await setup_entry()
    assert hass.states.get(ENTITY) is not None


async def test_the_entity_supports_create_update_and_delete(hass, setup_entry):
    await setup_entry()
    features = hass.states.get(ENTITY).attributes["supported_features"]
    for wanted in (CalendarEntityFeature.CREATE_EVENT,
                   CalendarEntityFeature.DELETE_EVENT,
                   CalendarEntityFeature.UPDATE_EVENT):
        assert features & wanted


# --- la lecture -------------------------------------------------------------

async def test_get_events_returns_one_event_per_meal(hass, setup_entry):
    entry = await setup_entry()
    await _seed(hass, entry, recipes=["Gratin"], meals=[
        {"day": "2026-08-21", "slot_key": "dinner", "recipe": "Gratin"},
        {"day": "2026-08-21", "slot_key": "lunch", "note": "Restaurant"}])
    entity = await _entity(hass)
    events = await entity.async_get_events(
        hass, datetime(2026, 8, 20, tzinfo=PARIS), datetime(2026, 8, 22, tzinfo=PARIS))
    assert [e.summary for e in events] == ["Restaurant", "Gratin"]   # lunch, dinner


async def test_an_event_starts_at_the_slot_default_time_in_the_local_zone(hass, setup_entry):
    entry = await setup_entry()
    await _seed(hass, entry, recipes=["Gratin"], meals=[
        {"day": "2026-08-21", "slot_key": "dinner", "recipe": "Gratin"}])
    entity = await _entity(hass)
    [event] = await entity.async_get_events(
        hass, datetime(2026, 8, 21, tzinfo=PARIS), datetime(2026, 8, 22, tzinfo=PARIS))
    assert event.start.hour == 20 and event.start.minute == 0
    # Vingt heures locales font dix-huit heures UTC en été.
    assert event.start.astimezone(dt_util.UTC).hour == 18


async def test_an_event_ends_after_the_slot_duration(hass, setup_entry):
    entry = await setup_entry()
    await _seed(hass, entry, recipes=["Gratin"], meals=[
        {"day": "2026-08-21", "slot_key": "dinner", "recipe": "Gratin"}])
    entity = await _entity(hass)
    [event] = await entity.async_get_events(
        hass, datetime(2026, 8, 21, tzinfo=PARIS), datetime(2026, 8, 22, tzinfo=PARIS))
    assert event.end - event.start == timedelta(minutes=45)


async def test_the_uid_is_the_meal_uid(hass, setup_entry):
    entry = await setup_entry()
    _, [posted] = await _seed(hass, entry, meals=[
        {"day": "2026-08-21", "slot_key": "dinner", "note": "Restaurant"}])
    entity = await _entity(hass)
    [event] = await entity.async_get_events(
        hass, datetime(2026, 8, 21, tzinfo=PARIS), datetime(2026, 8, 22, tzinfo=PARIS))
    assert event.uid == posted["uid"]


async def test_the_description_lists_the_ingredients_and_what_is_missing(hass, setup_entry):
    entry = await setup_entry()
    ids, _ = await _seed(hass, entry, recipes=["Gratin"], meals=[
        {"day": "2026-08-21", "slot_key": "dinner", "recipe": "Gratin"}])
    manager = entry.runtime_data.manager

    def _lines():
        with manager.db.write() as conn:
            product_id = repo.insert_product(conn, name="Courgette", base_unit="g")
            repo.insert_ingredient(conn, recipe_id=ids["Gratin"], position=1,
                                   raw_text="300 g de courgettes",
                                   product_id=product_id, amount=300.0,
                                   match_state="auto")
            repo.insert_ingredient(conn, recipe_id=ids["Gratin"], position=2,
                                   raw_text="une gousse d'ail")

    await hass.async_add_executor_job(_lines)
    entity = await _entity(hass)
    [event] = await entity.async_get_events(
        hass, datetime(2026, 8, 21, tzinfo=PARIS), datetime(2026, 8, 22, tzinfo=PARIS))
    assert "300 g de courgettes" in event.description
    assert "À sortir à la main : une gousse d'ail" in event.description


async def test_a_note_meal_has_the_note_as_summary(hass, setup_entry):
    entry = await setup_entry()
    await _seed(hass, entry, meals=[
        {"day": "2026-08-21", "slot_key": "lunch", "note": "Restaurant avec Anne"}])
    entity = await _entity(hass)
    [event] = await entity.async_get_events(
        hass, datetime(2026, 8, 21, tzinfo=PARIS), datetime(2026, 8, 22, tzinfo=PARIS))
    assert event.summary == "Restaurant avec Anne"


async def test_no_rrule_is_ever_produced(hass, setup_entry):
    """Un menu de la semaine n'est pas un événement récurrent, et l'annoncer
    récurrent promettrait un comportement qu'on ne veut pas écrire."""
    entry = await setup_entry()
    await _seed(hass, entry, meals=[
        {"day": "2026-08-21", "slot_key": "dinner", "note": "x"}])
    entity = await _entity(hass)
    [event] = await entity.async_get_events(
        hass, datetime(2026, 8, 21, tzinfo=PARIS), datetime(2026, 8, 22, tzinfo=PARIS))
    assert not getattr(event, "rrule", None)
    assert not getattr(event, "recurrence_id", None)


# --- poser un repas depuis la carte native ---------------------------------

async def test_creating_an_event_matches_a_recipe_by_summary(hass, setup_entry):
    """Un repas posé depuis Lovelace est un repas complet et décrémentable,
    pas une chaîne de caractères sans suite."""
    entry = await setup_entry()
    ids, _ = await _seed(hass, entry, recipes=["Gratin de courgettes"])
    entity = await _entity(hass)
    await entity.async_create_event(
        summary="Gratin de courgettes",
        dtstart=datetime(2026, 8, 21, 20, 30, tzinfo=PARIS))
    manager = entry.runtime_data.manager
    [meal] = await hass.async_add_executor_job(
        manager.list_meals, "2026-08-21", "2026-08-21")
    assert meal["recipe_id"] == ids["Gratin de courgettes"]
    assert meal["slot_key"] == "dinner"


async def test_creating_an_event_whose_summary_matches_nothing_makes_a_note_meal(
        hass, setup_entry):
    """Pas un échec : « Restaurant » est un repas parfaitement légitime."""
    entry = await setup_entry()
    await _seed(hass, entry, recipes=["Gratin de courgettes"])
    entity = await _entity(hass)
    await entity.async_create_event(
        summary="Restaurant japonais",
        dtstart=datetime(2026, 8, 21, 12, 30, tzinfo=PARIS))
    manager = entry.runtime_data.manager
    [meal] = await hass.async_add_executor_job(
        manager.list_meals, "2026-08-21", "2026-08-21")
    assert meal["recipe_id"] is None
    assert meal["note"] == "Restaurant japonais"


@pytest.mark.parametrize("hour, slot", [
    (8, "breakfast"), (13, "lunch"), (16, "snack"), (21, "dinner")])
async def test_the_slot_is_the_nearest_default_time(hass, setup_entry, hour, slot):
    entry = await setup_entry()
    entity = await _entity(hass)
    await entity.async_create_event(
        summary="Repas", dtstart=datetime(2026, 8, 21, hour, tzinfo=PARIS))
    manager = entry.runtime_data.manager
    meals = await hass.async_add_executor_job(
        manager.list_meals, "2026-08-21", "2026-08-21")
    assert [m["slot_key"] for m in meals] == [slot]


async def test_an_event_created_at_one_in_the_morning_lands_on_the_previous_food_day(
        hass, setup_entry):
    entry = await setup_entry()
    entity = await _entity(hass)
    await entity.async_create_event(
        summary="Tard", dtstart=datetime(2026, 8, 22, 1, 0, tzinfo=PARIS))
    manager = entry.runtime_data.manager
    meals = await hass.async_add_executor_job(
        manager.list_meals, "2026-08-21", "2026-08-21")
    assert [m["note"] for m in meals] == ["Tard"]


# --- déplacer et supprimer --------------------------------------------------

async def test_updating_an_event_moves_the_meal(hass, setup_entry):
    entry = await setup_entry()
    _, [posted] = await _seed(hass, entry, meals=[
        {"day": "2026-08-21", "slot_key": "dinner", "note": "x"}])
    entity = await _entity(hass)
    await entity.async_update_event(
        posted["uid"], {"dtstart": datetime(2026, 8, 23, 12, 30, tzinfo=PARIS)})
    manager = entry.runtime_data.manager
    meal = await hass.async_add_executor_job(
        lambda: repo.get_meal(manager.db.read(), posted["meal_id"]))
    assert (meal["day"], meal["slot_key"]) == ("2026-08-23", "lunch")


async def test_updating_a_done_meal_is_refused(hass, setup_entry):
    entry = await setup_entry()
    _, [posted] = await _seed(hass, entry, meals=[
        {"day": "2026-08-21", "slot_key": "dinner", "note": "x"}])
    manager = entry.runtime_data.manager

    def _mark_done():
        with manager.db.write() as conn:
            repo.update_meal_fields(conn, posted["meal_id"], {"state": "done"})

    await hass.async_add_executor_job(_mark_done)
    entity = await _entity(hass)
    with pytest.raises(HomeAssistantError):
        await entity.async_update_event(
            posted["uid"], {"dtstart": datetime(2026, 8, 23, 12, 30, tzinfo=PARIS)})


async def test_deleting_a_planned_meal_removes_it(hass, setup_entry):
    entry = await setup_entry()
    _, [posted] = await _seed(hass, entry, meals=[
        {"day": "2026-08-21", "slot_key": "dinner", "note": "x"}])
    entity = await _entity(hass)
    await entity.async_delete_event(posted["uid"])
    manager = entry.runtime_data.manager
    assert await hass.async_add_executor_job(
        lambda: repo.get_meal(manager.db.read(), posted["meal_id"])) is None


async def test_deleting_a_done_meal_marks_it_skipped_and_keeps_the_row(hass, setup_entry):
    """La suppression détruirait la référence `movement.ref_type = 'meal'` que
    le journal porte déjà et qui, elle, est en ajout seul."""
    entry = await setup_entry()
    _, [posted] = await _seed(hass, entry, meals=[
        {"day": "2026-08-21", "slot_key": "dinner", "note": "x"}])
    manager = entry.runtime_data.manager

    def _mark_done():
        with manager.db.write() as conn:
            repo.update_meal_fields(conn, posted["meal_id"], {"state": "done"})

    await hass.async_add_executor_job(_mark_done)
    entity = await _entity(hass)
    await entity.async_delete_event(posted["uid"])
    meal = await hass.async_add_executor_job(
        lambda: repo.get_meal(manager.db.read(), posted["meal_id"]))
    assert meal is not None and meal["state"] == "skipped"


async def test_deleting_an_unknown_uid_raises_rather_than_passing_silently(
        hass, setup_entry):
    await setup_entry()
    entity = await _entity(hass)
    with pytest.raises(HomeAssistantError):
        await entity.async_delete_event("home-stock-meal-jamais-vu")
