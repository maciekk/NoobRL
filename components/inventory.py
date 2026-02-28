"""Component that manages item storage and stack merging."""

from __future__ import annotations

import copy
from typing import List, Optional, TYPE_CHECKING

from components.base_component import BaseComponent

if TYPE_CHECKING:
    from entity import Actor, Item


class Inventory(BaseComponent):
    """Manages an actor's items with support for stackable items and capacity limits."""
    parent: Actor

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.items: List[Item] = []

    def find_stack(self, name: str) -> Optional[Item]:
        """Return an existing stackable item with matching name, or None."""
        for item in self.items:
            if item.stackable and item.name == name:
                return item
        return None

    def add(self, item: Item, count: int = 0) -> bool:
        """Add an item (or merge into an existing stack).

        count overrides how many to add; 0 means use item.stack_count.
        Returns True on success.
        """
        if count <= 0:
            count = item.stack_count

        if item.stackable:
            existing = self.find_stack(item.name)
            if existing is not None:
                existing.stack_count += count
                return True

        if len(self.items) >= self.capacity:
            self.engine.message_log.add_message(
                f"You have no inventory space left to take {item.display_name}."
            )
            return False

        item.stack_count = count
        self.items.append(item)
        return True

    def drop(self, item: Item, count: int = 0) -> None:
        """Remove an item (or part of a stack) from inventory and place on the map.

        count=0 means drop the entire stack.
        """
        if count <= 0 or count >= item.stack_count:
            # Drop entire stack.
            dropped_count = item.stack_count
            self.items.remove(item)
            item.place(self.parent.x, self.parent.y, self.gamemap)
            self._merge_floor_stack(item)
        else:
            # Partial drop — split the stack.
            dropped_count = count
            item.stack_count -= count
            dropped = copy.deepcopy(item)
            dropped.stack_count = count
            dropped.place(self.parent.x, self.parent.y, self.gamemap)
            self._merge_floor_stack(dropped)

        count_text = ""
        if item.stackable and dropped_count > 1:
            count_text = f" (x{dropped_count})"
        self.engine.message_log.add_message(f"You dropped the {item.display_name}{count_text}.")

    def _merge_floor_stack(self, dropped: Item) -> None:
        """If a same-name stackable item already sits at this location, merge."""
        if not dropped.stackable:
            return
        for entity in list(self.gamemap.entities):
            same_location = entity.x == dropped.x and entity.y == dropped.y
            is_stack = (
                hasattr(entity, "stackable")
                and entity.stackable
                and entity.name == dropped.name
                and isinstance(entity, type(dropped))
            )
            if entity is not dropped and same_location and is_stack:
                entity.stack_count += dropped.stack_count
                self.gamemap.entities.discard(dropped)
                return
