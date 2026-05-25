"""Directional interaction helpers and handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import actions
import color
import exceptions
from actions import Action
from tile_types import TILE_DOOR_CLOSED, TILE_DOOR_OPEN

if TYPE_CHECKING:
    from engine import Engine
    from input_handlers import ActionOrHandler


_DOOR_DIRECTIONS: dict[tuple[int, int], str] = {
    (0, -1): "north",
    (0, 1): "south",
    (-1, 0): "west",
    (1, 0): "east",
    (0, 0): "here",
    (-1, -1): "northwest",
    (1, -1): "northeast",
    (-1, 1): "southwest",
    (1, 1): "southeast",
}


def find_pickup_squares(engine: Engine) -> list:
    targets = []
    px, py = engine.player.x, engine.player.y
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            if dx == 0 and dy == 0:
                continue
            x, y = px + dx, py + dy
            if not engine.game_map.in_bounds(x, y):
                continue
            items = [item for item in engine.game_map.items if item.x == x and item.y == y]
            if items:
                desc = items[0].display_name if len(items) == 1 else f"{len(items)} items"
                targets.append((dx, dy, desc, items))
    return targets


def find_openable_targets(engine: Engine) -> list:
    targets = []
    px, py = engine.player.x, engine.player.y

    for dx in range(-1, 2):
        for dy in range(-1, 2):
            x, y = px + dx, py + dy
            if not engine.game_map.in_bounds(x, y):
                continue

            if engine.game_map.tiles[x, y] == TILE_DOOR_CLOSED:
                direction = _DOOR_DIRECTIONS.get((dx, dy), "")
                targets.append((dx, dy, f"Door ({direction})", actions.OpenDoorAction(engine.player, x, y)))

            for entity in engine.game_map.entities:
                if entity.x == x and entity.y == y and hasattr(entity, "open") and not getattr(entity, "opened", False):
                    direction = "here" if (dx == 0 and dy == 0) else "nearby"
                    targets.append((dx, dy, f"{entity.name.capitalize()} ({direction})", entity))

    return targets


class OpenableSelectionHandler(__import__("input_handlers").DirectionalSelectionHandler):
    TITLE = "Open what?"
    EMPTY_TEXT = "(Nothing to open)"

    def __init__(self, engine: Engine, targets: list):
        super().__init__(engine)
        self.targets = targets

    def get_directional_items(self) -> list:
        return self.targets

    def on_directional_selection(self, dx: int, dy: int, target) -> Optional[ActionOrHandler]:
        if isinstance(target, Action):
            return target
        try:
            target.open(self.engine.player)
        except exceptions.Impossible as exc:
            self.engine.message_log.add_message(exc.args[0], color.impossible)
        from input_handlers import MainGameEventHandler

        return MainGameEventHandler(self.engine)


class PickupDirectionHandler(__import__("input_handlers").DirectionalSelectionHandler):
    TITLE = "Pick up from where?"
    EMPTY_TEXT = "(No items nearby)"

    def __init__(self, engine: Engine, targets: list):
        super().__init__(engine)
        self.targets = targets

    def get_directional_items(self) -> list:
        return self.targets

    def on_directional_selection(self, dx: int, dy: int, target) -> Optional[ActionOrHandler]:
        px, py = self.engine.player.x, self.engine.player.y
        return actions.PickupAction(self.engine.player, px + dx, py + dy)


def find_closeable_doors(engine: Engine) -> list:
    targets = []
    px, py = engine.player.x, engine.player.y

    for dx in range(-1, 2):
        for dy in range(-1, 2):
            x, y = px + dx, py + dy
            if not engine.game_map.in_bounds(x, y):
                continue

            if engine.game_map.tiles[x, y] == TILE_DOOR_OPEN:
                direction = _DOOR_DIRECTIONS.get((dx, dy), "")
                targets.append((dx, dy, f"Door ({direction})", actions.CloseDoorAction(engine.player, x, y)))

    return targets


class CloseableSelectionHandler(__import__("input_handlers").DirectionalSelectionHandler):
    TITLE = "Close what?"
    EMPTY_TEXT = "(No open doors)"

    def __init__(self, engine: Engine, targets: list):
        super().__init__(engine)
        self.targets = targets

    def get_directional_items(self) -> list:
        return self.targets

    def on_directional_selection(self, dx: int, dy: int, target) -> Optional[ActionOrHandler]:
        return target
