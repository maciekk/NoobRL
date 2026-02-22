import random
import re
from collections import deque
from typing import List, Optional, Tuple

import tcod

import color
import sounds
from engine import Engine
from game_map import GameMap
from input_handlers import (
    AskUserEventHandler,
    ListSelectionHandler,
    MainGameEventHandler,
    SelectIndexHandler,
)

CHEST_OF_WONDER_ID = "__chest_of_wonder__"

_POTIONS = [
    "p_heal", "p_damage", "p_clairvoyance", "p_invisibility",
    "p_speed", "p_detect_monster", "p_sleep", "p_blindness",
]
_SCROLLS = ["s_confusion", "s_fireball", "s_blink", "s_lightning", "s_identify"]
_WANDS = ["wand_wishing"]
_WEAPONS = ["dagger", "sword", "long_sword", "odachi"]
_ARMOR = ["leather_armor", "chain_mail", "steel_armor"]


def spawn_chest_of_wonder(game_map: GameMap) -> None:
    from entity import Chest

    player = game_map.engine.player
    px, py = player.x, player.y

    # Try the 8 surrounding tiles; fall back to player's tile.
    neighbors = [
        (px + dx, py + dy)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        if (dx, dy) != (0, 0)
    ]
    def _has_chest(gm, cx, cy):
        return any(isinstance(e, Chest) and e.x == cx and e.y == cy for e in gm.entities)

    random.shuffle(neighbors)
    x, y = None, None
    for nx, ny in neighbors:
        if (
            game_map.in_bounds(nx, ny)
            and game_map.tiles["walkable"][nx, ny]
            and game_map.get_blocking_entity_at_location(nx, ny) is None
            and not _has_chest(game_map, nx, ny)
        ):
            x, y = nx, ny
            break

    if x is None:
        # Fall back to player's tile if it has no chest.
        if not _has_chest(game_map, px, py):
            x, y = px, py
        else:
            game_map.engine.message_log.add_message(
                "No room for the Chest of Wonder!", color.impossible
            )
            return

    item_ids = (
        random.choices(_POTIONS, k=5)
        + random.choices(_SCROLLS, k=5)
        + random.choices(_WANDS, k=3)
        + random.choices(_WEAPONS, k=1)
        + random.choices(_ARMOR, k=1)
    )

    chest = Chest(name="Chest of Wonder")
    chest.stored_item_ids = item_ids
    chest.spawn(game_map, x, y)
    sounds.play("sfx/643876__sushiman2000__smoke-poof.ogg")

    game_map.engine.message_log.add_message("A Chest of Wonder appears!")


def parse_query(buffer: str) -> Tuple[str, int]:
    """Parse buffer into (search_string, count).

    Accepts: "orc", "orc 5", "5 orc", "orc x5", "5x orc".
    """
    parts = buffer.strip().split()
    if not parts:
        return ("", 1)

    count_re = re.compile(r"^x?(\d+)x?$", re.IGNORECASE)

    # Check last token
    m = count_re.match(parts[-1])
    if m and len(parts) > 1:
        return (" ".join(parts[:-1]), int(m.group(1)))

    # Check first token
    m = count_re.match(parts[0])
    if m and len(parts) > 1:
        return (" ".join(parts[1:]), int(m.group(1)))

    return (" ".join(parts), 1)


def find_cluster_positions(
    cx: int, cy: int, count: int, game_map: GameMap
) -> List[Tuple[int, int]]:
    """Find up to `count` walkable, unoccupied tiles near (cx, cy) using BFS."""
    positions = []
    visited = set()
    queue = deque()
    queue.append((cx, cy))
    visited.add((cx, cy))

    while queue and len(positions) < count:
        x, y = queue.popleft()
        if (
            game_map.tiles["walkable"][x, y]
            and game_map.get_blocking_entity_at_location(x, y) is None
        ):
            positions.append((x, y))
        for dx, dy in (
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
            (-1, -1),
            (-1, 1),
            (1, -1),
            (1, 1),
        ):
            nx, ny = x + dx, y + dy
            if (
                0 <= nx < game_map.width
                and 0 <= ny < game_map.height
                and (nx, ny) not in visited
            ):
                visited.add((nx, ny))
                queue.append((nx, ny))

    return positions


def spawn_entity(entity_id, game_map: GameMap, x: int, y: int):
    entity = game_map.engine.item_manager.clone(entity_id)
    is_item = entity is not None
    if entity is None:
        entity = game_map.engine.monster_manager.clone(entity_id)
    if entity is None:
        game_map.engine.message_log.add_message(
            f"Unknown object '{entity_id}' requested."
        )
        return None

    # Items go to inventory if there's room, otherwise drop on floor
    if is_item:
        player = game_map.engine.player
        entity.parent = player.inventory
        if not player.inventory.add(entity):
            # Inventory is full, drop on floor instead
            entity.spawn(game_map, x, y)
            game_map.engine.message_log.add_message(
                f"Your inventory is full; {entity.name} dropped on floor."
            )
        sounds.play("sfx/643876__sushiman2000__smoke-poof.ogg")
        # If added to inventory successfully, no need to spawn on map
        return entity
    else:
        # Monsters always spawn on the map
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
    if q in "chest of wonder":
        matches.append((CHEST_OF_WONDER_ID, "Chest of Wonder"))
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
        console.print(x=x + 1, y=y + 1, string=f"Enter entity to spawn: {self.buffer}")

    def ev_keydown(self, event: tcod.event.KeyDown):
        key = event.sym
        if key == tcod.event.KeySym.RETURN:
            query, count = parse_query(self.buffer)
            if not query:
                return MainGameEventHandler(self.engine)
            matches = find_matches(self.engine, query)
            if len(matches) == 0:
                self.engine.message_log.add_message(f"No match for '{query}'.")
                return MainGameEventHandler(self.engine)
            elif len(matches) == 1:
                entity_id, name = matches[0]
                if entity_id == CHEST_OF_WONDER_ID:
                    spawn_chest_of_wonder(self.engine.game_map)
                    return MainGameEventHandler(self.engine)
                if entity_id in self.engine.monster_manager.monsters:
                    return DebugPlaceMonsterHandler(self.engine, entity_id, name, count)
                label = f"{count}x {name}" if count > 1 else name
                self.engine.message_log.add_message(f"Spawning {label}.")
                for _ in range(count):
                    spawn_entity(
                        entity_id,
                        self.engine.game_map,
                        self.engine.player.x,
                        self.engine.player.y,
                    )
                return MainGameEventHandler(self.engine)
            else:
                return DebugSelectHandler(self.engine, matches, count)
        elif key == tcod.event.KeySym.ESCAPE:
            return MainGameEventHandler(self.engine)
        elif key == tcod.event.KeySym.BACKSPACE:
            self.buffer = self.buffer[:-1]
        elif key == tcod.event.KeySym.SPACE:
            self.buffer += " "
        else:
            try:
                c = chr(key)
                if c.isalnum() or c == "_":
                    self.buffer += c
            except (ValueError, OverflowError):
                pass
        return None


class DebugSelectHandler(ListSelectionHandler):
    """Select from multiple matching entities."""

    TITLE = "Select entity to spawn"

    def __init__(self, engine: Engine, matches: List[Tuple[str, str]], count: int = 1):
        super().__init__(engine)
        self.matches = matches
        self.count = count

    def get_items(self) -> list:
        return self.matches

    def get_display_string(self, index: int, item) -> str:
        return item[1]

    def on_selection(self, index: int, item):
        entity_id, name = item
        if entity_id == CHEST_OF_WONDER_ID:
            spawn_chest_of_wonder(self.engine.game_map)
            return MainGameEventHandler(self.engine)
        if entity_id in self.engine.monster_manager.monsters:
            return DebugPlaceMonsterHandler(self.engine, entity_id, name, self.count)
        label = f"{self.count}x {name}" if self.count > 1 else name
        self.engine.message_log.add_message(f"Spawning {label}.")
        for _ in range(self.count):
            spawn_entity(
                entity_id,
                self.engine.game_map,
                self.engine.player.x,
                self.engine.player.y,
            )
        return MainGameEventHandler(self.engine)


class DebugPlaceMonsterHandler(SelectIndexHandler):
    """Lets the user choose where to place a debug-spawned monster."""

    def __init__(self, engine: Engine, entity_id: str, name: str, count: int = 1):
        super().__init__(engine)
        self.entity_id = entity_id
        self.monster_name = name
        self.count = count
        label = f"{count}x {name}" if count > 1 else name
        engine.message_log.add_message(f"Where do you want to place {label}?")

    def on_index_selected(self, x: int, y: int):
        positions = find_cluster_positions(x, y, self.count, self.engine.game_map)
        label = (
            f"{len(positions)}x {self.monster_name}"
            if self.count > 1
            else self.monster_name
        )
        self.engine.message_log.add_message(f"Spawning {label}.")
        for px, py in positions:
            spawn_entity(self.entity_id, self.engine.game_map, px, py)
        return MainGameEventHandler(self.engine)
