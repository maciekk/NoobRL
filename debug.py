from typing import List, Optional, Tuple

import tcod

from engine import Engine
from game_map import GameMap
from input_handlers import AskUserEventHandler, ListSelectionHandler, MainGameEventHandler


def spawn_entity(entity_id, game_map: GameMap, x: int, y: int):
    entity = game_map.engine.item_manager.clone(entity_id)
    if entity is None:
        entity = game_map.engine.monster_manager.clone(entity_id)
    if entity is None:
        game_map.engine.message_log.add_message(f"Unknown object '{entity_id}' requested.")
        return None
    return entity.spawn(game_map, x, y)


def find_matches(engine: Engine, query: str) -> List[Tuple[str, str]]:
    """Return list of (id, name) pairs matching query as case-insensitive substring."""
    q = query.lower()
    matches = []
    for entity_id, item in engine.item_manager.items.items():
        if q in entity_id.lower() or q in item.name.lower():
            matches.append((entity_id, item.name))
    for entity_id, monster in engine.monster_manager.monsters.items():
        if q in entity_id.lower() or q in monster.name.lower():
            matches.append((entity_id, monster.name))
    return sorted(matches, key=lambda x: x[1])


class DebugHandler(AskUserEventHandler):
    """Debug menu."""
    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.buffer = ""

    def on_render(self, console: tcod.console.Console) -> None:
        super().on_render(console)

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

        y = 0
        width = 38

        console.draw_frame(
            x=x,
            y=y,
            width=width,
            height=6,
            title="DEBUG MENU",
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )
        console.print(x=x + 1, y=y + 1, string=f"Enter item to spawn: {self.buffer}")

    def ev_keydown(self, event: tcod.event.KeyDown):
        key = event.sym
        if key == tcod.event.KeySym.RETURN:
            matches = find_matches(self.engine, self.buffer)
            if len(matches) == 0:
                self.engine.message_log.add_message(f"No match for '{self.buffer}'.")
                return MainGameEventHandler(self.engine)
            elif len(matches) == 1:
                entity_id, name = matches[0]
                self.engine.message_log.add_message(f"Spawning {name}.")
                spawn_entity(entity_id, self.engine.game_map, self.engine.player.x, self.engine.player.y)
                return MainGameEventHandler(self.engine)
            else:
                return DebugSelectHandler(self.engine, matches)
        elif key == tcod.event.KeySym.ESCAPE:
            return MainGameEventHandler(self.engine)
        elif key == tcod.event.KeySym.BACKSPACE:
            self.buffer = self.buffer[:-1]
        else:
            try:
                c = chr(key)
                if c.isalnum() or c == '_':
                    self.buffer += c
            except (ValueError, OverflowError):
                pass
        return None


class DebugSelectHandler(ListSelectionHandler):
    """Select from multiple matching entities."""

    TITLE = "Select entity to spawn"

    def __init__(self, engine: Engine, matches: List[Tuple[str, str]]):
        super().__init__(engine)
        self.matches = matches

    def get_items(self) -> list:
        return self.matches

    def get_display_string(self, index: int, item) -> str:
        return item[1]

    def on_selection(self, index: int, item):
        entity_id, name = item
        self.engine.message_log.add_message(f"Spawning {name}.")
        spawn_entity(entity_id, self.engine.game_map, self.engine.player.x, self.engine.player.y)
        return MainGameEventHandler(self.engine)
