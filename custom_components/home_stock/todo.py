"""The two checkable lists: what is about to expire, and what to buy.

Checking an expiring batch means EATEN: a checkbox carries one bit and cannot
tell "eaten" from "thrown away". Throwing away goes through home_stock.consume
with the waste reason (spec 8.1).

Checking a shopping line means "I have it", never "it is in stock" (lot 4,
§ 7.5) — the same argument, taken one step further: one bit cannot say which
article, which quantity, which price, which location or which best-before
date, and those are exactly the five things it takes to create a batch.
"""
from __future__ import annotations

from functools import partial

from homeassistant.components.todo import (
    ENTITY_ID_FORMAT,
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeStockConfigEntry
from .coordinator import HomeStockCoordinator
from .domain.matching import candidates, preselect
from .domain.units import format_quantity
from .entity import HomeStockEntity
from .storage import repositories as repo


class ExpirationsTodoList(HomeStockEntity, TodoListEntity):
    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "expirations", ENTITY_ID_FORMAT)

    @property
    def todo_items(self) -> list[TodoItem]:
        return [
            TodoItem(
                uid=str(batch["batch_id"]),
                summary=f"{batch['product_name']} — {batch['display']}",
                due=None,
                description=f"Date limite {batch['best_before']}",
                status=TodoItemStatus.NEEDS_ACTION,
            )
            for batch in self.coordinator.data["expiring"]
        ]

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """A checked item is a consumed batch.

        The coordinator refreshes every 15 minutes: a batch consumed elsewhere
        (voice, a service call) in between can still be sitting, checkable, on
        a tablet. A stale uid there is not a failure — the user's intent
        ("this is finished") is already true, so it is a no-op, not an error.
        A non-numeric uid, on the other hand, cannot come from our own
        todo_items and is a genuine programming error: it must surface to the
        frontend as a HomeAssistantError, not a raw traceback.
        """
        # The todo.update_item service hands us a plain string, not the enum
        # instance: `is not TodoItemStatus.COMPLETED` would be true even for a
        # matching value, and checking off an item would silently do nothing.
        if item.status != TodoItemStatus.COMPLETED or item.uid is None:
            return
        try:
            batch_id = int(item.uid)
        except ValueError as err:
            raise HomeAssistantError(f"invalid batch id: {item.uid}") from err
        manager = self.coordinator.manager
        try:
            await self.hass.async_add_executor_job(
                partial(manager.consume_batch, batch_id)
            )
        except ValueError:
            # Already closed or gone: someone else finished it first.
            pass
        await self.coordinator.async_refresh()


class ShoppingTodoList(HomeStockEntity, TodoListEntity):
    """La liste de courses, cochable depuis n'importe quelle surface.

    Trois fonctionnalités, et l'absence des deux autres est un choix :

    - pas de `SET_DUE_DATE` — une ligne de courses n'a pas d'échéance, et en
      annoncer une promettrait un tri qui n'existe pas ;
    - pas de `MOVE_TODO_ITEM` — l'ordre de la liste est celui du MAGASIN, il
      est calculé (§ 11), et laisser une carte Lovelace le réordonner ferait
      diverger les deux surfaces sur la seule chose que ce lot passe son
      temps à apprendre.
    """

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "shopping", ENTITY_ID_FORMAT)

    @property
    def todo_items(self) -> list[TodoItem]:
        return [
            TodoItem(
                uid=str(row["id"]),
                summary=_summary(row),
                due=None,
                description=_description(row),
                status=(TodoItemStatus.COMPLETED if row["checked_at"]
                        else TodoItemStatus.NEEDS_ACTION),
            )
            for row in self.coordinator.data["shopping_list"]
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Une ligne posée depuis une carte est une ligne `manual`.

        Elle vise un produit du catalogue quand le nom en désigne un sans
        hésitation possible — le seuil de présélection du lot 1 — et reste
        un texte libre sinon. Deviner à mi-chemin est ce qui a produit 35
        doublons dans Grocy en avril 2026.
        """
        text = (item.summary or "").strip()
        if not text:
            raise HomeAssistantError("une ligne de liste a besoin d'un libellé")
        manager = self.coordinator.manager
        product_id = await self.hass.async_add_executor_job(
            partial(_obvious_product, manager, text))
        await self.hass.async_add_executor_job(partial(
            manager.add_to_shopping_list,
            product_id=product_id,
            free_text=None if product_id else text))
        await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Cocher, c'est « je l'ai ». Pas un lot, pas un mouvement, rien.

        Un `uid` périmé n'est pas une erreur : le coordinateur rafraîchit
        toutes les quinze minutes, et une ligne cochée ailleurs entre-temps
        peut encore être cochable sur une tablette — l'intention est déjà
        vraie. Un `uid` non numérique, lui, ne peut pas venir de nos propres
        `todo_items` : c'est un vrai bug, et il doit remonter.
        """
        item_id = _checked_uid(item)
        if item_id is None:
            return
        manager = self.coordinator.manager
        completed = item.status == TodoItemStatus.COMPLETED
        action = manager.check_list_item if completed else manager.uncheck_list_item
        await self.hass.async_add_executor_job(partial(action, item_id))
        await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Un retrait, jamais un DELETE : la réconciliation doit se SOUVENIR
        qu'on n'en veut pas, sinon elle remet la ligne un quart d'heure
        plus tard."""
        manager = self.coordinator.manager
        for uid in uids:
            try:
                item_id = int(uid)
            except ValueError as err:
                raise HomeAssistantError(f"invalid list item id: {uid}") from err
            await self.hass.async_add_executor_job(
                partial(manager.remove_list_item, item_id))
        await self.coordinator.async_refresh()


def _checked_uid(item: TodoItem) -> int | None:
    if item.uid is None:
        return None
    try:
        return int(item.uid)
    except ValueError as err:
        raise HomeAssistantError(f"invalid list item id: {item.uid}") from err


def _summary(row) -> str:
    """« Lait — 2 L ». Sans quantité, juste le nom : « ce qu'il faut » se dit
    en n'en disant rien, pas en écrivant « 0 »."""
    name = row["product_name"] or row["free_text"] or ""
    quantity = row["quantity"]
    if quantity is None or not row["base_unit"]:
        return name
    return f"{name} — {format_quantity(quantity, row['base_unit'])}"


def _description(row) -> str | None:
    """Les origines en clair : « sous le seuil · dîner de jeudi »."""
    details = [claim["detail"] for claim in row.get("claims") or ()
               if claim.get("detail")]
    return " · ".join(details) if details else None


def _obvious_product(manager, text: str) -> int | None:
    products = repo.list_products(manager.db.read())
    chosen = preselect(candidates(names=[text], products=products))
    return chosen.product_id if chosen else None


async def async_setup_entry(hass: HomeAssistant, entry: HomeStockConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities([
        ExpirationsTodoList(coordinator),
        ShoppingTodoList(coordinator),
    ])
