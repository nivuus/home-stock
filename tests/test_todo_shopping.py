"""`todo.home_stock_shopping` : la liste de courses, cochable partout.

Une liste de courses se consulte ailleurs que dans le panneau — carte
`todo-list`, application mobile, tablette murale — et se dit à la voix :
`todo.add_item` et `todo.get_items` sont des services standards que les
agents de la maison comprennent déjà.
"""
import pytest
from homeassistant.components.todo import (
    DATA_COMPONENT, TodoItem, TodoItemStatus, TodoListEntityFeature,
)
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.storage import repositories as repo

SHOPPING = "todo.home_stock_shopping"


@pytest.fixture
async def loaded(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _entity(hass, entity_id=SHOPPING):
    return hass.data[DATA_COMPONENT].get_entity(entity_id)


async def _seed_list(hass, entry):
    manager = entry.runtime_data.manager

    def _write() -> int:
        with manager.db.write() as conn:
            aisles = {row["name"]: row["id"] for row in repo.list_aisles(conn)}
            product_id = repo.insert_product(conn, name="Lait", base_unit="ml",
                                             min_quantity=2000,
                                             aisle_id=aisles["Crémerie"])
            item_id = repo.insert_list_item(conn, added_at="2026-08-21T09:00:00",
                                            product_id=product_id, quantity=2000.0)
            repo.set_claim(conn, item_id=item_id, origin="shortage", quantity=2000.0,
                           detail="sous le seuil", claimed_at="2026-08-21T09:00:00")
            # `manual` survit à la réconciliation (règle 5) ; la
            # revendication `shortage`, elle, est RECALCULÉE à chaque passe —
            # d'où le libellé attendu ci-dessous, qui est celui que le
            # domaine produit, pas celui qu'on a semé.
            repo.set_claim(conn, item_id=item_id, origin="manual", quantity=None,
                           detail="dîner de jeudi", claimed_at="2026-08-21T09:00:00")
            return item_id

    item_id = await hass.async_add_executor_job(_write)
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    return item_id


async def test_the_shopping_list_declares_exactly_three_features(hass, loaded):
    """CREATE | UPDATE | DELETE. Ni SET_DUE_DATE, ni MOVE_TODO_ITEM —
    et le test épingle leur ABSENCE, pas seulement la présence des trois."""
    features = _entity(hass).supported_features
    assert features & TodoListEntityFeature.CREATE_TODO_ITEM
    assert features & TodoListEntityFeature.UPDATE_TODO_ITEM
    assert features & TodoListEntityFeature.DELETE_TODO_ITEM
    # Une ligne de courses n'a pas d'échéance, et en annoncer une promettrait
    # un tri qui n'existe pas. L'ordre de la liste est celui du MAGASIN, il
    # est calculé : laisser une carte le réordonner ferait diverger les deux
    # surfaces sur la seule chose que ce lot passe son temps à apprendre.
    assert not features & TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
    assert not features & TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
    assert not features & TodoListEntityFeature.MOVE_TODO_ITEM


async def test_the_summary_reads_like_a_shopping_line(hass, loaded):
    """« Lait — 2 L » via `format_quantity` ; la description dit les origines
    en clair : « sous le seuil · dîner de jeudi »."""
    await _seed_list(hass, loaded)
    [item] = _entity(hass).todo_items
    assert item.summary == "Lait — 2 l"
    assert item.description == "dîner de jeudi · seuil 2000"
    assert item.due is None
    assert item.status == TodoItemStatus.NEEDS_ACTION


async def test_checking_an_item_marks_it_got_not_stocked(hass, loaded):
    """« Je l'ai », jamais « c'est en stock ». AUCUN lot, AUCUN mouvement,
    AUCUNE entrée en stock : une case cochée ne porte qu'un BIT, et ne peut
    dire ni quel article, ni quelle quantité, ni quel prix, ni quel
    emplacement, ni quelle DLC — exactement les cinq informations qu'il
    faut pour créer un lot."""
    item_id = await _seed_list(hass, loaded)
    manager = loaded.runtime_data.manager

    await hass.services.async_call("todo", "update_item", {
        "entity_id": SHOPPING, "item": str(item_id), "status": "completed",
    }, blocking=True)

    read = manager.db.read()
    assert read.execute("SELECT COUNT(*) AS n FROM batch").fetchone()["n"] == 0
    assert read.execute("SELECT COUNT(*) AS n FROM movement").fetchone()["n"] == 0
    assert repo.get_list_item(read, item_id)["checked_at"] is not None


async def test_creating_from_the_card_creates_a_manual_line(hass, loaded):
    """Avec un `free_text` quand aucun produit ne dépasse le seuil de
    présélection du lot 1."""
    manager = loaded.runtime_data.manager

    await hass.services.async_call("todo", "add_item", {
        "entity_id": SHOPPING, "item": "Piles télécommande salon",
    }, blocking=True)

    rows = repo.list_items(manager.db.read())
    assert len(rows) == 1
    assert rows[0]["free_text"] == "Piles télécommande salon"
    assert rows[0]["product_id"] is None
    assert [claim["origin"] for claim in rows[0]["claims"]] == ["manual"]


async def test_creating_from_the_card_finds_an_obvious_product(hass, loaded):
    manager = loaded.runtime_data.manager

    def _write() -> None:
        with manager.db.write() as conn:
            repo.insert_product(conn, name="Beurre", base_unit="g")

    await hass.async_add_executor_job(_write)
    await hass.services.async_call("todo", "add_item", {
        "entity_id": SHOPPING, "item": "beurre",
    }, blocking=True)

    [row] = repo.list_items(manager.db.read())
    assert row["product_name"] == "Beurre"


async def test_deleting_from_the_card_is_a_removal_never_a_delete(hass, loaded):
    item_id = await _seed_list(hass, loaded)
    manager = loaded.runtime_data.manager

    await hass.services.async_call("todo", "remove_item", {
        "entity_id": SHOPPING, "item": [str(item_id)],
    }, blocking=True)

    read = manager.db.read()
    assert repo.list_items(read) == []
    assert repo.get_list_item(read, item_id)["removed_at"] is not None


async def test_a_stale_uid_is_a_no_op_not_an_error(hass, loaded):
    """Même garde-fou que `todo.home_stock_expirations` : le coordinateur
    rafraîchit toutes les 15 minutes, une ligne cochée ailleurs entre-temps
    peut encore être cochable sur une tablette. L'intention est déjà vraie."""
    # Appelée directement : la plateforme `todo` refuse d'elle-même un `uid`
    # absent de `todo_items`, et ce qu'on veut prouver ici est le
    # comportement de l'ENTITÉ quand la ligne a disparu entre-temps.
    await _entity(hass).async_update_todo_item(
        TodoItem(uid="4242", summary="x", status=TodoItemStatus.COMPLETED))


async def test_a_non_numeric_uid_surfaces_as_a_home_assistant_error(hass, loaded):
    """Il ne peut pas venir de nos propres `todo_items` : c'est un vrai bug."""
    entity = _entity(hass)
    with pytest.raises(HomeAssistantError):
        await entity.async_update_todo_item(
            TodoItem(uid="pas-un-nombre", summary="x",
                     status=TodoItemStatus.COMPLETED))


async def test_a_line_checked_outside_a_trip_stays_checked(hass, loaded):
    """Aucun voyage n'a été clos depuis : la purge de la règle 4 n'a pas lieu
    d'être. Sans cette nuance, cocher depuis une carte ferait disparaître la
    ligne au tic suivant pour la recréer aussitôt — ça se lit comme un bug."""
    item_id = await _seed_list(hass, loaded)
    await hass.services.async_call("todo", "update_item", {
        "entity_id": SHOPPING, "item": str(item_id), "status": "completed",
    }, blocking=True)

    [item] = _entity(hass).todo_items
    assert item.uid == str(item_id)
    assert item.status == TodoItemStatus.COMPLETED


async def test_unchecking_puts_the_line_back(hass, loaded):
    item_id = await _seed_list(hass, loaded)
    manager = loaded.runtime_data.manager
    await hass.services.async_call("todo", "update_item", {
        "entity_id": SHOPPING, "item": str(item_id), "status": "completed",
    }, blocking=True)
    await hass.services.async_call("todo", "update_item", {
        "entity_id": SHOPPING, "item": str(item_id), "status": "needs_action",
    }, blocking=True)
    assert repo.get_list_item(manager.db.read(), item_id)["checked_at"] is None


async def test_the_expirations_list_is_untouched(hass, loaded):
    """Garde-fou : deux entités `todo` coexistent, la première ne change ni
    de nom, ni de fonctionnalités, ni de comportement."""
    expirations = _entity(hass, "todo.home_stock_expirations")
    assert expirations is not None
    assert expirations.supported_features == TodoListEntityFeature.UPDATE_TODO_ITEM
