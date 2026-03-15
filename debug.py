"""Debug console and spawn utilities for in-game testing."""
# pylint: disable=cyclic-import,duplicate-code
import random
import re
from collections import deque
from typing import List, Tuple

import tcod  # pylint: disable=import-error

import actions
import color
import exceptions
import recorder as recorder_module
import sounds
from engine import Engine
from game_map import GameMap
from input_handlers import (
    AskUserEventHandler,
    BaseEventHandler,
    EventHandler,
    GameOverEventHandler,
    LevelUpEventHandler,
    ListSelectionHandler,
    MainGameEventHandler,
    SelectIndexHandler,
)

CHEST_OF_WONDER_ID = "__chest_of_wonder__"
TRAPDOOR_ID = "__trapdoor__"
SQUEAKY_BOARD_ID = "__squeaky_board__"

_POTIONS = [
    "p_heal", "p_damage", "p_clairvoyance", "p_invisibility",
    "p_speed", "p_detect_monster", "p_sleep", "p_blindness",
]
_SCROLLS = ["s_confusion", "s_fireball", "s_blink", "s_lightning", "s_identify"]
_WANDS = ["wand_wishing", "wand_digging"]
_WEAPONS = ["dagger", "sword", "long_sword", "odachi"]
_ARMOR = ["leather_armor", "chain_mail", "steel_armor"]


def spawn_chest_of_wonder(game_map: GameMap) -> None:
    """Spawn a Chest of Wonder near the player on the given map."""
    from entity import Chest  # pylint: disable=import-outside-toplevel

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


def spawn_trap(game_map: GameMap, trap_type: str, x: int, y: int) -> None:
    """Spawn a trap of the given type at the given location."""
    from entity import Trap  # pylint: disable=import-outside-toplevel

    trap = Trap(trap_type=trap_type)
    trap.spawn(game_map, x, y)
    sounds.play("sfx/643876__sushiman2000__smoke-poof.ogg")
    game_map.engine.message_log.add_message(f"A {trap.name} appears!")


def spawn_entity(entity_id, game_map: GameMap, x: int, y: int):
    """Clone entity by ID, adding items to inventory or placing monsters on the map."""
    if entity_id in game_map.engine.item_manager.items:
        item, added = game_map.engine.give_item_to_player(entity_id)
        if not added:
            game_map.engine.message_log.add_message(
                f"Your inventory is full; {item.name} dropped on floor."
            )
        sounds.play("sfx/643876__sushiman2000__smoke-poof.ogg")
        return item

    entity = game_map.engine.monster_manager.clone(entity_id)
    if entity is None:
        game_map.engine.message_log.add_message(
            f"Unknown object '{entity_id}' requested."
        )
        return None
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
    if q in "trapdoor trap":
        matches.append((TRAPDOOR_ID, "Trapdoor Trap"))
    if q in "squeaky board trap":
        matches.append((SQUEAKY_BOARD_ID, "Squeaky Board Trap"))
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
        prompt = f"Enter entity to spawn: {self.buffer}"
        width = max(38, len(prompt) + 3)

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
        console.print(x=x + 1, y=y + 1, string=prompt)

    def ev_keydown(  # pylint: disable=too-many-return-statements,too-many-branches
        self, event: tcod.event.KeyDown
    ):
        key = event.sym
        if key == tcod.event.KeySym.RETURN:
            # Handle record commands before entity spawning.
            buf = self.buffer.strip()
            if buf.startswith("record "):
                return self._handle_record_command(buf)

            query, count = parse_query(self.buffer)
            if not query:
                return MainGameEventHandler(self.engine)
            matches = find_matches(self.engine, query)
            if len(matches) == 0:
                self.engine.message_log.add_message(f"No match for '{query}'.")
                return MainGameEventHandler(self.engine)
            if len(matches) == 1:
                entity_id, name = matches[0]
                if entity_id == CHEST_OF_WONDER_ID:
                    spawn_chest_of_wonder(self.engine.game_map)
                    return MainGameEventHandler(self.engine)
                if entity_id == TRAPDOOR_ID:
                    return DebugPlaceTrapHandler(self.engine, "trapdoor")
                if entity_id == SQUEAKY_BOARD_ID:
                    return DebugPlaceTrapHandler(self.engine, "squeaky_board")
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
            return DebugSelectHandler(self.engine, matches, count)
        if key == tcod.event.KeySym.ESCAPE:
            return MainGameEventHandler(self.engine)
        if key == tcod.event.KeySym.BACKSPACE:
            self.buffer = self.buffer[:-1]
        elif key == tcod.event.KeySym.SPACE:
            self.buffer += " "
        else:
            try:
                c = chr(key)
                if c.isalnum() or c in "_./":
                    self.buffer += c
            except (ValueError, OverflowError):
                pass
        return None

    def _handle_record_command(self, buf: str):
        """Process 'record start/stop/play' debug commands."""
        parts = buf.split(None, 2)
        subcmd = parts[1] if len(parts) > 1 else ""

        if subcmd == "start":
            filename = parts[2] if len(parts) > 2 else "recording.rec"
            if recorder_module.active_recorder is not None:
                self.engine.message_log.add_message(
                    "Previous recording discarded."
                )
            recorder_module.active_recorder = recorder_module.Recorder(
                self.engine, filename
            )
            self.engine.message_log.add_message(
                f"Recording started → {filename}"
            )
            return MainGameEventHandler(self.engine)

        if subcmd == "stop":
            rec = recorder_module.active_recorder
            if rec is None:
                self.engine.message_log.add_message("No active recording.")
                return MainGameEventHandler(self.engine)
            rec.save()
            recorder_module.active_recorder = None
            self.engine.message_log.add_message(
                f"Recording saved → {rec.filename}"
            )
            return MainGameEventHandler(self.engine)

        if subcmd == "play":
            filename = parts[2] if len(parts) > 2 else "recording.rec"
            try:
                engine, rand_state, keystrokes = recorder_module.load_recording(
                    filename
                )
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self.engine.message_log.add_message(f"Load failed: {exc}")
                return MainGameEventHandler(self.engine)
            import random as rand_mod  # pylint: disable=import-outside-toplevel
            rand_mod.setstate(rand_state)
            recorder_module.playback_active = True
            engine.message_log.add_message(
                f"Playing back {len(keystrokes)} keystrokes from {filename}"
            )
            return PlaybackHandler(engine, keystrokes)

        self.engine.message_log.add_message(
            "Usage: record start|stop|play [filename]"
        )
        return MainGameEventHandler(self.engine)


class PlaybackHandler(EventHandler):
    """Replays recorded keystrokes, delegating to the wrapped handler."""

    DELAY_NORMAL = 0.1
    DELAY_MENU = 1.0

    def __init__(self, engine: Engine, keystrokes: List[Tuple[int, int]]):
        super().__init__(engine)
        self.keystrokes = keystrokes
        self.index = 0
        self.current_handler = MainGameEventHandler(engine)

    @property
    def playback_delay(self) -> float:
        """Return a longer delay when a menu/dialog is on screen."""
        if isinstance(self.current_handler, AskUserEventHandler):
            return self.DELAY_MENU
        return self.DELAY_NORMAL

    def handle_events(self, event) -> "BaseEventHandler":
        """Ignore real input (except Escape); feed next recorded keystroke."""
        # Allow aborting playback with Escape
        if (
            event is not None
            and isinstance(event, tcod.event.KeyDown)
            and event.sym == tcod.event.KeySym.ESCAPE
        ):
            recorder_module.playback_active = False
            self.engine.message_log.add_message("Playback aborted.")
            return MainGameEventHandler(self.engine)

        if self.index >= len(self.keystrokes):
            recorder_module.playback_active = False
            self.engine.message_log.add_message("Playback complete.")
            return MainGameEventHandler(self.engine)

        sym, mod = self.keystrokes[self.index]
        self.index += 1
        synthetic = recorder_module.SyntheticKeyDown(sym=sym, mod=mod)

        # Call ev_keydown directly (tcod dispatch routes by class name,
        # which won't match our SyntheticKeyDown dataclass).
        handler = self.current_handler
        try:
            action_or_state = handler.ev_keydown(synthetic)
        except exceptions.Impossible:
            return self
        if isinstance(action_or_state, BaseEventHandler):
            self.current_handler = action_or_state
        elif isinstance(action_or_state, actions.Action):
            handler.handle_action(action_or_state)
            # Check for death / level-up like EventHandler.handle_events does
            if not self.engine.player.is_alive:
                recorder_module.playback_active = False
                return GameOverEventHandler(self.engine)
            if self.engine.player.level.requires_level_up:
                self.engine.message_log.add_message("You leveled up!", stack=False)
                self.current_handler = LevelUpEventHandler(self.engine)
            else:
                self.current_handler = MainGameEventHandler(self.engine)
        return self

    def on_render(self, console: tcod.console.Console) -> None:
        """Delegate rendering to the current wrapped handler."""
        self.current_handler.on_render(console)


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
        if entity_id == TRAPDOOR_ID:
            return DebugPlaceTrapHandler(self.engine, "trapdoor")
        if entity_id == SQUEAKY_BOARD_ID:
            return DebugPlaceTrapHandler(self.engine, "squeaky_board")
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


class DebugPlaceTrapHandler(SelectIndexHandler):
    """Lets the user choose where to place a debug-spawned trap."""

    def __init__(self, engine: Engine, trap_type: str):
        super().__init__(engine)
        self.trap_type = trap_type
        name = trap_type.replace("_", " ") + " trap"
        engine.message_log.add_message(f"Where do you want to place the {name}?")

    def on_index_selected(self, x: int, y: int):
        spawn_trap(self.engine.game_map, self.trap_type, x, y)
        return MainGameEventHandler(self.engine)
