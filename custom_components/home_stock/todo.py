"""The expiring batches, as a checkable list.

Checking an item means EATEN: a checkbox carries one bit and cannot tell "eaten"
from "thrown away". Throwing away goes through home_stock.consume with the waste
reason (spec 8.1).
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
from .entity import HomeStockEntity


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


async def async_setup_entry(hass: HomeAssistant, entry: HomeStockConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([ExpirationsTodoList(entry.runtime_data.coordinator)])
