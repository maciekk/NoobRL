"""Keyboard and mouse input handling via a state machine of handler classes."""
# pylint: disable=too-many-lines,fixme,cyclic-import,duplicate-code

from __future__ import annotations

import os
import time
from typing import Optional, Tuple, TYPE_CHECKING, Union

import tcod  # pylint: disable=import-error
from tcod import libtcodpy  # pylint: disable=import-error

import actions
import sounds
from actions import (
    Action,
    BumpAction,
    CarefulMovementAction,
    MovementRepeatedAction,
    PickupAction,
    WaitAction,
)
import color
import exceptions
import recorder as recorder_module
from tile_types import TILE_DOOR_CLOSED, TILE_DOOR_OPEN
from entity import Actor, Chest, Item, Trap

if TYPE_CHECKING:
    from engine import Engine


MOVE_KEYS = {
    # Arrow keys.
    tcod.event.KeySym.UP: (0, -1),
    tcod.event.KeySym.DOWN: (0, 1),
    tcod.event.KeySym.LEFT: (-1, 0),
    tcod.event.KeySym.RIGHT: (1, 0),
    tcod.event.KeySym.HOME: (-1, -1),
    tcod.event.KeySym.END: (-1, 1),
    tcod.event.KeySym.PAGEUP: (1, -1),
    tcod.event.KeySym.PAGEDOWN: (1, 1),
    # Numpad keys.
    tcod.event.KeySym.KP_1: (-1, 1),
    tcod.event.KeySym.KP_2: (0, 1),
    tcod.event.KeySym.KP_3: (1, 1),
    tcod.event.KeySym.KP_4: (-1, 0),
    tcod.event.KeySym.KP_6: (1, 0),
    tcod.event.KeySym.KP_7: (-1, -1),
    tcod.event.KeySym.KP_8: (0, -1),
    tcod.event.KeySym.KP_9: (1, -1),
    # Vi keys.
    tcod.event.KeySym.h: (-1, 0),
    tcod.event.KeySym.j: (0, 1),
    tcod.event.KeySym.k: (0, -1),
    tcod.event.KeySym.l: (1, 0),
    tcod.event.KeySym.y: (-1, -1),
    tcod.event.KeySym.u: (1, -1),
    tcod.event.KeySym.b: (-1, 1),
    tcod.event.KeySym.n: (1, 1),
}

WAIT_KEYS = {
    tcod.event.KeySym.PERIOD,
    tcod.event.KeySym.KP_5,
    tcod.event.KeySym.CLEAR,
}

CONFIRM_KEYS = {
    tcod.event.KeySym.RETURN,
    tcod.event.KeySym.KP_ENTER,
}

SCROLL_SPEED = 5

MIN_FRAME_INTERVAL = 0.025

# Set by main.py so handle_action can render between repeated steps.
context: Optional["tcod.context.Context"] = None  # pylint: disable=invalid-name
root_console: Optional["tcod.console.Console"] = None  # pylint: disable=invalid-name


# Modifier key helpers
def has_shift(mod: int) -> bool:
    """Check if Shift modifier is held."""
    return bool(mod & (tcod.event.Modifier.LSHIFT | tcod.event.Modifier.RSHIFT))


def has_ctrl(mod: int) -> bool:
    """Check if Ctrl modifier is held."""
    return bool(mod & (tcod.event.Modifier.LCTRL | tcod.event.Modifier.RCTRL))


def has_alt(mod: int) -> bool:
    """Check if Alt modifier is held."""
    return bool(mod & (tcod.event.Modifier.LALT | tcod.event.Modifier.RALT))


def is_shifted(event: tcod.event.KeyDown, key: tcod.event.KeySym) -> bool:
    """Check if a specific key was pressed with Shift modifier."""
    return event.sym == key and has_shift(event.mod)


def is_ctrl(event: tcod.event.KeyDown, key: tcod.event.KeySym) -> bool:
    """Check if a specific key was pressed with Ctrl modifier."""
    return event.sym == key and has_ctrl(event.mod)


# TODO: theoretically newer notation is preferred:
#        Action | "BaseEventHandler"
# See:
#   https://docs.python.org/3/library/stdtypes.html#union-type

ActionOrHandler = Union[Action, "BaseEventHandler"]
"""An event handler return value which can trigger an action or switch active handlers.

If a handler is returned then it will become the active handler for future events.
If an action is returned it will be attempted and if it's valid then
MainGameEventHandler will become the active handler.
"""


class BaseEventHandler(tcod.event.EventDispatch[ActionOrHandler]):
    """Base class for all event handlers; implements the state machine interface."""

    def handle_events(self, event: tcod.event.Event) -> BaseEventHandler:
        """Handle an event and return the next active event handler."""
        state = self.dispatch(event)
        if isinstance(state, BaseEventHandler):
            return state
        assert not isinstance(state, Action), f"{self!r} can not handle actions."
        return self

    def on_render(self, console: tcod.Console) -> None:
        """Render the current UI state to the console."""
        raise NotImplementedError()

    def ev_quit(self, event: tcod.event.Quit) -> Optional[Action]:
        """Handle window close or application quit."""
        raise SystemExit()


class PopupMessage(BaseEventHandler):
    """Displays a dimmed overlay with a centered message; any key dismisses it."""

    def __init__(self, parent_handler: BaseEventHandler, text: str):
        super().__init__()
        self.parent = parent_handler
        self.text = text

    def on_render(self, console: tcod.Console) -> None:
        """Render the parent and dim the result, then print the message on top."""
        self.parent.on_render(console)
        console.rgb["fg"] //= 8
        console.rgb["bg"] //= 8

        console.print(
            console.width // 2,
            console.height // 2,
            self.text,
            fg=color.white,
            bg=color.black,
            alignment=libtcodpy.CENTER,
        )

    def ev_keydown(self, _event: tcod.event.KeyDown) -> Optional[BaseEventHandler]:
        """Any key returns to the parent handler."""
        return self.parent


class EventHandler(BaseEventHandler):
    """Base handler for handlers that operate within the game engine."""

    def __init__(self, engine: Engine):
        super().__init__()
        self.engine = engine

    @property
    def menu_x(self) -> int:
        """Return x for a popup menu opposite the player's screen position."""
        return 40 if self.engine.player.x <= 30 else 0

    def handle_events(self, event: tcod.event.Event) -> BaseEventHandler:
        """Handle events and dispatch actions; check for death and level-up conditions."""
        # Record keystrokes (exclude debug handlers and the @ key that opens them)
        if (
            isinstance(event, tcod.event.KeyDown)
            and recorder_module.active_recorder is not None
            and type(self).__module__ != "debug"
            and not (event.sym == tcod.event.KeySym.N2
                     and event.mod & (tcod.event.Modifier.LSHIFT | tcod.event.Modifier.RSHIFT))
        ):
            recorder_module.active_recorder.record_key(event.sym, event.mod)
        try:
            action_or_state = self.dispatch(event)
        except exceptions.Impossible as exc:
            self.engine.message_log.add_message(exc.args[0], color.impossible)
            return self
        if isinstance(action_or_state, BaseEventHandler):
            return action_or_state
        if self.handle_action(action_or_state):
            # A valid action was performed.
            if not self.engine.player.is_alive:
                # The player was killed sometime during or after the action.
                return GameOverEventHandler(self.engine)
            if self.engine.player.level.requires_level_up:
                self.engine.message_log.add_message("You leveled up!", stack=False)
                sounds.play_sfx(sounds.Sfx.LEVEL_UP)
                return LevelUpEventHandler(self.engine)
            return MainGameEventHandler(self.engine)  # Return to the main handler.
        return self

    def handle_action(self, action: Optional[Action]) -> bool:
        """Execute an action and advance the turn if valid; return True if turn advanced."""
        if action is None:
            return False

        sounds.consume_sound_heard()  # Discard stale sounds from before this action.
        while True:
            try:
                should_repeat = action.perform()
            except exceptions.Impossible as exc:
                self.engine.message_log.add_message(exc.args[0], color.impossible)
                return False  # Skip enemy turn on exceptions.

            self.engine.end_turn()
            if not should_repeat:
                break
            if sounds.consume_sound_heard():
                break

            if context is not None and root_console is not None:
                root_console.clear()
                self.engine.render(root_console)
                context.present(root_console, keep_aspect=True, integer_scaling=False)
            time.sleep(MIN_FRAME_INTERVAL)

        return True

    def ev_mousemotion(self, event: tcod.event.MouseMotion) -> None:
        """Track mouse position, converting screen coords to world coords."""
        sx, sy = event.tile.x, event.tile.y
        if 0 <= sx < self.engine.viewport_width and 0 <= sy < self.engine.viewport_height:
            wx, wy = self.engine.screen_to_world(sx, sy)
            if self.engine.game_map.in_bounds(wx, wy):
                self.engine.mouse_location = wx, wy

    def ev_quit(self, event: tcod.event.Quit) -> Optional[Action]:
        """Handle window close by raising SystemExit."""
        raise SystemExit()

    def on_render(self, console: tcod.Console) -> None:
        """Render the full game state."""
        self.engine.render(console)


class QuitConfirmHandler(EventHandler):
    """Yes/no dialog confirming the player wants to quit."""

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)
        console.rgb["fg"] //= 4
        console.rgb["bg"] //= 4

        msg = "Really quit? (y/n)"
        width = len(msg) + 4
        x = (console.width - width) // 2
        y = console.height // 2 - 2
        console.draw_frame(x, y, width, 3, clear=True, fg=color.white, bg=color.black)
        console.print(x + 2, y + 1, msg, fg=color.white, bg=color.black)

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        """Quit on 'y', otherwise return to game."""
        if event.sym == tcod.event.KeySym.y:
            raise SystemExit()
        return MainGameEventHandler(self.engine)


class AskUserEventHandler(EventHandler):
    """Base for modal dialogs and menus; dismissible by Escape or click."""

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        """By default, any key exits this input handler."""
        if event.sym in {  # Ignore modifier keys.
            tcod.event.KeySym.LSHIFT,
            tcod.event.KeySym.RSHIFT,
            tcod.event.KeySym.LCTRL,
            tcod.event.KeySym.RCTRL,
            tcod.event.KeySym.LALT,
            tcod.event.KeySym.RALT,
        }:
            return None
        return self.on_exit()

    def ev_mousebuttondown(
        self, _event: tcod.event.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """By default, any mouse click exits this input handler."""
        return self.on_exit()

    def on_exit(self) -> Optional[ActionOrHandler]:
        """Called when the user exits or cancels; default returns to main handler."""
        return MainGameEventHandler(self.engine)


_MOTION_KEYS = frozenset("jk")
_INVENTORY_KEYS = (
    [c for c in "abcdefghijklmnopqrstuvwxyz" if c not in _MOTION_KEYS]
    + [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c.lower() not in _MOTION_KEYS]
)
_INVENTORY_KEY_TO_INDEX = {c: i for i, c in enumerate(_INVENTORY_KEYS)}


class ListSelectionHandler(AskUserEventHandler):
    """Base class for item selection menus with (a) Label style letter-based selection.

    Subclasses must override get_items(), get_display_string(), and on_selection().
    Set TITLE, EMPTY_TEXT, and optionally use_cursor=True for arrow navigation.
    """

    TITLE: str = "<missing title>"
    EMPTY_TEXT: str = "(Empty)"
    use_cursor: bool = False

    def __init__(self, engine: Engine, cursor: int = 0):
        super().__init__(engine)
        self.cursor = cursor

    def get_items(self) -> list:
        """Return the list of items to display in the selection menu."""
        raise NotImplementedError()

    def get_display_string(self, index: int, item) -> str:
        """Return the display label for an item (letter prefix added automatically)."""
        raise NotImplementedError()

    def on_selection(self, index: int, item) -> Optional[ActionOrHandler]:
        """Handle selection of an item; return an Action or Handler."""
        raise NotImplementedError()

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)

        items = self.get_items()
        num_items = len(items)
        height = max(num_items + 2, 3)

        x = self.menu_x

        y = 0

        item_strings = []
        for i, item in enumerate(items):
            item_key = _INVENTORY_KEYS[i] if i < len(_INVENTORY_KEYS) else "?"
            item_strings.append(f"{item_key}. {self.get_display_string(i, item)}")

        max_item_width = max((len(s) for s in item_strings), default=0)
        width = max(len(self.TITLE) + 4, max_item_width + 2)

        console.draw_frame(
            x=x,
            y=y,
            width=width,
            height=height,
            title=self.TITLE,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        if item_strings:
            if self.use_cursor:
                self.cursor = max(0, min(self.cursor, num_items - 1))
            for i, s in enumerate(item_strings):
                if self.use_cursor and i == self.cursor:
                    console.print(x + 1, y + i + 1, s, fg=color.black, bg=color.white)
                else:
                    console.print(x + 1, y + i + 1, s)
        else:
            console.print(x + 1, y + 1, self.EMPTY_TEXT)

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        key = event.sym
        items = self.get_items()
        num_items = len(items)

        if self.use_cursor:
            if key in INVENTORY_CURSOR_UP_KEYS and num_items > 0:
                self.cursor = (self.cursor - 1) % num_items
                return None
            if key in INVENTORY_CURSOR_DOWN_KEYS and num_items > 0:
                self.cursor = (self.cursor + 1) % num_items
                return None
            if key in CONFIRM_KEYS and num_items > 0:
                self.cursor = max(0, min(self.cursor, num_items - 1))
                return self.on_selection(self.cursor, items[self.cursor])

        if tcod.event.KeySym.a <= key <= tcod.event.KeySym.z:
            char = chr(key).upper() if has_shift(event.mod) else chr(key)
            if char in _INVENTORY_KEY_TO_INDEX:
                index = _INVENTORY_KEY_TO_INDEX[char]
                if index < num_items:
                    if self.use_cursor:
                        self.cursor = index
                    return self.on_selection(index, items[index])
                self.engine.message_log.add_message("Invalid entry.", color.invalid)
                return None
        return super().ev_keydown(event)


# Mapping from (dx, dy) offsets to direction keys and key symbols
DIRECTION_KEY_MAP = {
    (0, -1): ("k", tcod.event.KeySym.k),  # north
    (0, 1): ("j", tcod.event.KeySym.j),  # south
    (-1, 0): ("h", tcod.event.KeySym.h),  # west
    (1, 0): ("l", tcod.event.KeySym.l),  # east
    (-1, -1): ("y", tcod.event.KeySym.y),  # northwest
    (1, -1): ("u", tcod.event.KeySym.u),  # northeast
    (-1, 1): ("b", tcod.event.KeySym.b),  # southwest
    (1, 1): ("n", tcod.event.KeySym.n),  # southeast
}


class DirectionalSelectionHandler(AskUserEventHandler):
    """Base for directional selection menus (h,j,k,l,y,u,b,n keys for directions).

    Subclasses must override get_directional_items() and on_directional_selection().
    """

    TITLE: str = "<missing title>"
    EMPTY_TEXT: str = "(Empty)"

    def get_directional_items(self) -> list:
        """Return list of (dx, dy, description, target) tuples for directional choices."""
        raise NotImplementedError()

    def on_directional_selection(
        self, dx: int, dy: int, target
    ) -> Optional[ActionOrHandler]:
        """Handle user selection of a direction; return an Action or Handler."""
        raise NotImplementedError()

    def _build_direction_strings(self, items: list) -> list:
        """Build display strings for each directional choice."""
        strings = []
        for dx, dy, description, _ in items:
            if (dx, dy) in DIRECTION_KEY_MAP:
                dir_key, _ = DIRECTION_KEY_MAP[(dx, dy)]
                strings.append(f"({dir_key}) {description}")
            else:
                strings.append(f"(.) {description}")
        if len(items) > 1:
            strings.append("(A) All")
        return strings

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)

        items = self.get_directional_items()
        x = self.menu_x
        y = 0
        item_strings = self._build_direction_strings(items)
        height = max(len(item_strings) + 2, 3)
        max_item_width = max((len(s) for s in item_strings), default=0)
        width = max(len(self.TITLE) + 4, max_item_width + 2)

        console.draw_frame(
            x=x, y=y, width=width, height=height, title=self.TITLE,
            clear=True, fg=(255, 255, 255), bg=(0, 0, 0),
        )

        if item_strings:
            for i, s in enumerate(item_strings):
                console.print(x + 1, y + i + 1, s)
        else:
            console.print(x + 1, y + 1, self.EMPTY_TEXT)

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        key = event.sym
        items = self.get_directional_items()

        # Build a map from key symbol to (dx, dy, target)
        key_to_item = {}
        for dx, dy, _, target in items:
            if (dx, dy) in DIRECTION_KEY_MAP:
                _, key_sym = DIRECTION_KEY_MAP[(dx, dy)]
                key_to_item[key_sym] = (dx, dy, target)
            elif (dx, dy) == (0, 0):
                key_to_item[tcod.event.KeySym.PERIOD] = (0, 0, target)

        if key in key_to_item:
            dx, dy, target = key_to_item[key]
            return self.on_directional_selection(dx, dy, target)

        if is_shifted(event, tcod.event.KeySym.a) and len(items) > 1:
            for dx, dy, _, target in items:
                result = self.on_directional_selection(dx, dy, target)
                if isinstance(result, Action):
                    try:
                        result.perform()
                    except exceptions.Impossible as exc:
                        self.engine.message_log.add_message(exc.args[0], color.impossible)
            return MainGameEventHandler(self.engine)

        return super().ev_keydown(event)


def _attack_display(player: "Actor") -> str:
    """Return a human-readable attack string, e.g. '4+1d4+1' or '6'."""
    equipment = player.equipment
    if equipment and equipment.weapon and equipment.weapon.equippable:
        eq = equipment.weapon.equippable
        if eq.damage_dice:
            base = f"{player.fighter.power}+{eq.damage_dice}"
            if eq.enchantment > 0:
                return f"{base}+{eq.enchantment}"
            return base
    return str(player.fighter.power)


class CharacterScreenEventHandler(AskUserEventHandler):
    """Displays player statistics, experience, and kill counts."""

    TITLE = "Character Information"

    def on_render(self, console: tcod.Console) -> None:  # pylint: disable=too-many-locals
        super().on_render(console)

        x = self.menu_x

        y = 0

        kills = self.engine.kill_counts
        sorted_kills = sorted(kills.items(), key=lambda kv: kv[1], reverse=True)
        kill_lines = [f"  {name}: {count}" for name, count in sorted_kills]
        total_kills = sum(kills.values())

        stats_height = 7
        kills_height = len(kill_lines) + 2 if kill_lines else 0
        height = stats_height + kills_height

        player = self.engine.player
        attack_str = _attack_display(player)
        kill_strings = [f"Kills: {total_kills}"] + kill_lines if kill_lines else []
        all_strings = [
            f"Level: {player.level.current_level}",
            f"XP: {player.level.current_xp}",
            f"XP for next Level: {player.level.experience_to_next_level}",
            f"Attack: {attack_str}",
            f"Defense: {player.fighter.defense}",
        ] + kill_strings
        max_str_width = max((len(s) for s in all_strings), default=0)
        width = max(len(self.TITLE) + 4, max_str_width + 2)

        console.draw_frame(
            x=x,
            y=y,
            width=width,
            height=height,
            title=self.TITLE,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        console.print(
            x=x + 1, y=y + 1, string=f"Level: {self.engine.player.level.current_level}"
        )
        console.print(
            x=x + 1, y=y + 2, string=f"XP: {self.engine.player.level.current_xp}"
        )
        console.print(
            x=x + 1,
            y=y + 3,
            string=f"XP for next Level: {self.engine.player.level.experience_to_next_level}",
        )
        console.print(
            x=x + 1, y=y + 4, string=f"Attack: {attack_str}"
        )
        console.print(
            x=x + 1, y=y + 5, string=f"Defense: {player.fighter.defense}"
        )

        if kill_lines:
            row = y + stats_height
            console.print(x=x + 1, y=row, string=f"Kills: {total_kills}")
            for i, line in enumerate(kill_lines):
                console.print(x + 1, row + 1 + i, line)


class ViewSurroundingsHandler(AskUserEventHandler):
    """Lists visible monsters, corpses, items, and features with relative positions."""

    TITLE = "View Surroundings"

    @staticmethod
    def _direction(px: int, py: int, tx: int, ty: int) -> str:
        """Return relative direction string like '3N 5E' from player to target."""
        parts = []
        dy = py - ty  # positive = north (up on screen)
        dx = tx - px  # positive = east
        if dy > 0:
            parts.append(f"{dy}N")
        elif dy < 0:
            parts.append(f"{-dy}S")
        if dx > 0:
            parts.append(f"{dx}E")
        elif dx < 0:
            parts.append(f"{-dx}W")
        return " ".join(parts) if parts else "here"

    @staticmethod
    def _dist2(px: int, py: int, tx: int, ty: int) -> int:
        """Squared Euclidean distance (for sorting, no need for sqrt)."""
        return (tx - px) ** 2 + (ty - py) ** 2

    def _collect_surroundings(self, game_map, px: int, py: int) -> tuple:
        """Gather visible monsters, corpses, items, and features sorted by distance."""
        visible = game_map.visible
        direction = self._direction
        dist2 = self._dist2
        player = self.engine.player
        monsters = sorted(
            (
                dist2(px, py, a.x, a.y),
                a.name,
                direction(px, py, a.x, a.y),
                a.is_asleep,
                max(abs(a.x - px), abs(a.y - py)) <= a.sight_range and not player.is_invisible,
                bool(getattr(a.ai, "investigate_target", None)) or a.noticed_player,
            )
            for a in game_map.actors
            if a is not self.engine.player and visible[a.x, a.y]
        )
        corpses = sorted(
            (dist2(px, py, e.x, e.y), e.name, direction(px, py, e.x, e.y))
            for e in game_map.entities
            if isinstance(e, Actor) and not e.is_alive and visible[e.x, e.y]
        )
        items_sorted = sorted(
            (dist2(px, py, it.x, it.y), it.display_name, direction(px, py, it.x, it.y))
            for it in game_map.items
            if visible[it.x, it.y]
        )
        features: list = []
        for e in game_map.entities:
            if isinstance(e, Trap) and e.is_revealed and visible[e.x, e.y]:
                features.append((dist2(px, py, e.x, e.y), f"{e.name} {direction(px, py, e.x, e.y)}"))
            elif isinstance(e, Chest) and visible[e.x, e.y]:
                label = "chest (opened)" if e.opened else "chest"
                features.append((dist2(px, py, e.x, e.y), f"{label} {direction(px, py, e.x, e.y)}"))
        sx, sy = game_map.downstairs_location
        if visible[sx, sy]:
            features.append((dist2(px, py, sx, sy), f"Stairs down {direction(px, py, sx, sy)}"))
        ux, uy = game_map.upstairs_location
        if (ux, uy) != (0, 0) and visible[ux, uy]:
            features.append((dist2(px, py, ux, uy), f"Stairs up {direction(px, py, ux, uy)}"))
        features.sort()
        return monsters, corpses, items_sorted, features

    @staticmethod
    def _build_display_lines(monsters, corpses, items_sorted, features) -> list:
        """Build display strings from sorted entity and feature collections.

        Each item is either a plain str or a list of (text, color) segments
        where color is an RGB tuple or None for default white.
        """
        lines: list = []
        if monsters:
            lines.append("Monsters:")
            for _, name, d, asleep, noticed, investigating in monsters:
                if asleep:
                    lines.append([
                        (f"  {name} (", None),
                        ("S", (80, 255, 80)),
                        (f") {d}", None),
                    ])
                elif noticed:
                    lines.append([
                        (f"  {name} (", None),
                        ("!", (255, 80, 80)),
                        (f") {d}", None),
                    ])
                elif investigating:
                    lines.append([
                        (f"  {name} (", None),
                        ("!", (255, 220, 0)),
                        (f") {d}", None),
                    ])
                else:
                    lines.append(f"  {name} {d}")
        if corpses:
            if lines:
                lines.append("")
            lines.append("Corpses:")
            lines.extend(f"  {name} {d}" for _, name, d in corpses)
        if items_sorted:
            if lines:
                lines.append("")
            lines.append("Items:")
            lines.extend(f"  {name} {d}" for _, name, d in items_sorted)
        if features:
            if lines:
                lines.append("")
            lines.append("Features:")
            lines.extend(f"  {feat}" for _, feat in features)
        if not lines:
            lines.append("Nothing of interest.")
        return lines

    def on_render(self, console: tcod.Console) -> None:  # pylint: disable=too-many-locals
        super().on_render(console)
        game_map = self.engine.game_map
        px, py = self.engine.player.x, self.engine.player.y
        monsters, corpses, items_sorted, features = self._collect_surroundings(game_map, px, py)
        lines = self._build_display_lines(monsters, corpses, items_sorted, features)
        x = self.menu_x
        y = 0
        height = len(lines) + 2
        def _line_width(line):
            if isinstance(line, str):
                return len(line)
            return sum(len(t) for t, _ in line)

        max_line_width = max(_line_width(s) for s in lines)
        width = max(len(self.TITLE) + 4, max_line_width + 2)
        console.draw_frame(
            x=x, y=y, width=width, height=height, title=self.TITLE,
            clear=True, fg=(255, 255, 255), bg=(0, 0, 0),
        )
        for i, line in enumerate(lines):
            if isinstance(line, str):
                console.print(x=x + 1, y=y + 1 + i, string=line)
            else:
                cx = x + 1
                for text, fg in line:
                    kw = {"fg": fg} if fg is not None else {}
                    console.print(x=cx, y=y + 1 + i, string=text, **kw)
                    cx += len(text)


class LevelUpEventHandler(AskUserEventHandler):
    """Allows player to choose which stat to increase when leveling up (1-3 keys)."""

    TITLE = "Level Up"

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)

        x = self.menu_x

        console.draw_frame(
            x=x,
            y=0,
            width=35,
            height=8,
            title=self.TITLE,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        console.print(x=x + 1, y=1, string="Congratulations! You level up!")
        console.print(x=x + 1, y=2, string="Select an attribute to increase.")

        console.print(
            x=x + 1,
            y=4,
            string=f"1) CON: +5-10 HP (@{self.engine.player.fighter.max_hp})",
        )
        console.print(
            x=x + 1,
            y=5,
            string=f"2) STR: +1 attack (@{self.engine.player.fighter.power})",
        )
        console.print(
            x=x + 1,
            y=6,
            string=f"3) AGI: +1 defense (@{self.engine.player.fighter.defense})",
        )

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym
        index = key - tcod.event.KeySym.N1

        if 0 <= index <= 2:
            if index == 0:
                player.level.increase_max_hp()
            elif index == 1:
                player.level.increase_power()
            else:
                player.level.increase_defense()
        else:
            self.engine.message_log.add_message("Invalid entry.", color.invalid)

            return None

        return super().ev_keydown(event)

    def ev_mousebuttondown(
        self, _event: tcod.event.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """Don't allow the player to click to exit the menu, like normal."""
        return None


INVENTORY_CURSOR_UP_KEYS = {
    tcod.event.KeySym.UP,
    tcod.event.KeySym.k,
    tcod.event.KeySym.KP_8,
}

INVENTORY_CURSOR_DOWN_KEYS = {
    tcod.event.KeySym.DOWN,
    tcod.event.KeySym.j,
    tcod.event.KeySym.KP_2,
}

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
    """Find the 8 adjacent squares that have items. Returns (dx, dy, desc, items) tuples."""
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
                if len(items) == 1:
                    desc = items[0].display_name
                else:
                    desc = f"{len(items)} items"
                targets.append((dx, dy, desc, items))
    return targets


def find_openable_targets(engine: Engine) -> list:
    """Find openable targets (chests, closed doors) in 3x3 area; return (dx, dy, desc, action)."""
    targets = []
    px, py = engine.player.x, engine.player.y

    for dx in range(-1, 2):
        for dy in range(-1, 2):
            x, y = px + dx, py + dy
            if not engine.game_map.in_bounds(x, y):
                continue

            if engine.game_map.tiles[x, y] == TILE_DOOR_CLOSED:
                direction = _DOOR_DIRECTIONS.get((dx, dy), "")
                targets.append(
                    (dx, dy, f"Door ({direction})", actions.OpenDoorAction(engine.player, x, y))
                )

            for entity in engine.game_map.entities:
                if (entity.x == x and entity.y == y
                        and hasattr(entity, "open")
                        and not getattr(entity, "opened", False)):
                    direction = "here" if (dx == 0 and dy == 0) else "nearby"
                    targets.append(
                        (dx, dy, f"{entity.name.capitalize()} ({direction})", entity)
                    )

    return targets


class OpenableSelectionHandler(DirectionalSelectionHandler):
    """Allows player to select which openable to open using directional keys."""

    TITLE = "Open what?"
    EMPTY_TEXT = "(Nothing to open)"

    def __init__(self, engine: Engine, targets: list):
        super().__init__(engine)
        self.targets = targets

    def get_directional_items(self) -> list:
        """Return the list of available openable targets."""
        return self.targets

    def on_directional_selection(
        self, dx: int, dy: int, target
    ) -> Optional[ActionOrHandler]:
        """Execute the open action or method for the selected target."""
        if isinstance(target, Action):
            return target
        # It's an entity with open() method
        try:
            target.open(self.engine.player)
        except exceptions.Impossible as exc:
            self.engine.message_log.add_message(exc.args[0], color.impossible)
        return MainGameEventHandler(self.engine)


class PickupDirectionHandler(DirectionalSelectionHandler):
    """Lets the player pick a direction to pick up items from an adjacent tile."""

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
    """Find open doors in 3x3 area; return (dx, dy, description, action) tuples."""
    targets = []
    px, py = engine.player.x, engine.player.y

    for dx in range(-1, 2):
        for dy in range(-1, 2):
            x, y = px + dx, py + dy
            if not engine.game_map.in_bounds(x, y):
                continue

            if engine.game_map.tiles[x, y] == TILE_DOOR_OPEN:
                direction = _DOOR_DIRECTIONS.get((dx, dy), "")
                targets.append(
                    (dx, dy, f"Door ({direction})", actions.CloseDoorAction(engine.player, x, y))
                )

    return targets


class CloseableSelectionHandler(DirectionalSelectionHandler):
    """Lets the player choose which open door to close using directional keys."""

    TITLE = "Close what?"
    EMPTY_TEXT = "(No open doors)"

    def __init__(self, engine: Engine, targets: list):
        super().__init__(engine)
        self.targets = targets

    def get_directional_items(self) -> list:
        return self.targets

    def on_directional_selection(
        self, dx: int, dy: int, target
    ) -> Optional[ActionOrHandler]:
        return target


from handlers.inventory import (
    DropQuantityHandler,
    IdentifyItemHandler,
    InventoryActivateHandler,
    InventoryDropHandler,
    ItemDetailHandler,
    QuaffHandler,
    ReadHandler,
    ThrowItemHandler,
    WishItemHandler,
)
from handlers.screens import HistoryViewer, OverviewMapHandler, ViewKeybinds
from handlers.targeting import (
    AreaRangedAttackHandler,
    DiggingRayTargetHandler,
    FireballProjectileHandler,
    FloorItemDetailHandler,
    FloorItemListHandler,
    LightningRayTargetHandler,
    MonsterDetailHandler,
    SelectEntityHandler,
    TabTargets,
    TeleportTargetHandler,
    ThrowTargetHandler,
    WalkChoiceHandler,
)


class MainGameEventHandler(EventHandler):
    """Primary gameplay handler that maps keypresses to game actions."""

    def ev_keydown(  # pylint: disable=too-many-return-statements,too-many-branches,too-many-statements
        self, event: tcod.event.KeyDown
    ) -> Optional[ActionOrHandler]:
        """Dispatch keypresses to movement, item, and menu actions."""
        action: Optional[Action] = None

        key = event.sym
        modifier = event.mod

        player = self.engine.player

        # Player cannot act while asleep, except wait (to advance time for sleep to expire)
        if player.is_asleep and key not in WAIT_KEYS | {
            tcod.event.KeySym.ESCAPE,
            tcod.event.KeySym.LSHIFT,
            tcod.event.KeySym.RSHIFT,
            tcod.event.KeySym.LCTRL,
            tcod.event.KeySym.RCTRL,
            tcod.event.KeySym.LALT,
            tcod.event.KeySym.RALT,
        }:
            self.engine.message_log.add_message("You cannot act while asleep!")
            return None

        if is_shifted(event, tcod.event.KeySym.PERIOD):
            return actions.TakeStairsAction(player)

        if is_shifted(event, tcod.event.KeySym.N1):
            wand = self.engine.item_manager.clone("wand_wishing")
            if wand:
                if self.engine.player.inventory.add(wand):
                    sounds.play_sfx(sounds.Sfx.SMOKE_POOF)
                    self.engine.message_log.add_message(
                        "A Wand of Wishing appears in your pack!"
                    )
                else:
                    wand.place(self.engine.player.x, self.engine.player.y, self.engine.game_map)
                    self.engine.message_log.add_message(
                        "A Wand of Wishing appears at your feet!"
                    )
            return None

        if is_shifted(event, tcod.event.KeySym.COMMA):
            return actions.TakeUpStairsAction(player)

        if key in MOVE_KEYS and has_alt(modifier):
            dx, dy = MOVE_KEYS[key]
            self.engine.camera_x += dx * SCROLL_SPEED
            self.engine.camera_y += dy * SCROLL_SPEED
            self.engine.clamp_camera()
            return None  # no action, no turn consumed

        if key in MOVE_KEYS:
            dx, dy = MOVE_KEYS[key]
            if has_shift(modifier):
                action = CarefulMovementAction(player, dx, dy)
            elif has_ctrl(modifier):
                action = MovementRepeatedAction(player, dx, dy)
            else:
                action = BumpAction(player, dx, dy)
        elif key in WAIT_KEYS:
            action = WaitAction(player)
        elif key == tcod.event.KeySym.ESCAPE:
            return QuitConfirmHandler(self.engine)
        elif key == tcod.event.KeySym.SEMICOLON:
            return HistoryViewer(self.engine)
        elif is_shifted(event, tcod.event.KeySym.SLASH):
            return ViewKeybinds(self.engine)
        elif key == tcod.event.KeySym.g:
            player_items = [
                item for item in self.engine.game_map.items
                if item.x == player.x and item.y == player.y
            ]
            if player_items:
                action = PickupAction(player)
            else:
                surrounding = find_pickup_squares(self.engine)
                if not surrounding:
                    self.engine.message_log.add_message(
                        "There is nothing here to pick up.", color.impossible
                    )
                elif len(surrounding) == 1:
                    dx, dy, _, _ = surrounding[0]
                    action = PickupAction(player, player.x + dx, player.y + dy)
                else:
                    return PickupDirectionHandler(self.engine, surrounding)
        elif key == tcod.event.KeySym.i:
            return InventoryActivateHandler(self.engine)
        elif key == tcod.event.KeySym.o:
            # Find all openable targets in 3x3 area
            targets = find_openable_targets(self.engine)
            if len(targets) == 0:
                self.engine.message_log.add_message(
                    "There is nothing here to open.", color.impossible
                )
                return None
            if len(targets) == 1:
                # Only one target, open it directly
                *_, target = targets[0]
                if isinstance(target, Action):
                    action = target
                else:
                    # It's an entity, call its open method
                    target.open(player)
                    return None
            else:
                # Multiple targets, show selection menu
                return OpenableSelectionHandler(self.engine, targets)
        elif key == tcod.event.KeySym.d:
            return InventoryDropHandler(self.engine)
        elif is_shifted(event, tcod.event.KeySym.c):
            return CharacterScreenEventHandler(self.engine)
        elif key == tcod.event.KeySym.c:
            # Find all closeable doors in 3x3 area
            targets = find_closeable_doors(self.engine)
            if len(targets) == 0:
                self.engine.message_log.add_message(
                    "There are no open doors nearby.", color.impossible
                )
                return None
            if len(targets) == 1:
                # Only one target, close it directly
                *_, action = targets[0]
                return action
            # Multiple targets, show selection menu
            return CloseableSelectionHandler(self.engine, targets)
        elif is_shifted(event, tcod.event.KeySym.v):
            return ViewSurroundingsHandler(self.engine)
        elif key == tcod.event.KeySym.v:
            def look_callback(xy: Tuple[int, int]) -> Optional[ActionOrHandler]:
                x, y = xy
                game_map = self.engine.game_map
                if game_map.visible[x, y]:
                    actor = game_map.get_actor_at_location(x, y)
                    if actor and actor is not self.engine.player and actor.is_alive:
                        back = SelectEntityHandler(
                            self.engine, look_callback, TabTargets.MONSTERS_AND_ITEMS,
                            initial_xy=(x, y),
                        )
                        return MonsterDetailHandler(self.engine, actor, back)
                    items_here = [i for i in game_map.items if i.x == x and i.y == y]
                    if items_here:
                        back = SelectEntityHandler(
                            self.engine, look_callback, TabTargets.MONSTERS_AND_ITEMS,
                            initial_xy=(x, y),
                        )
                        if len(items_here) == 1:
                            return FloorItemDetailHandler(self.engine, items_here[0], back)
                        return FloorItemListHandler(self.engine, items_here, back)
                return MainGameEventHandler(self.engine)
            return SelectEntityHandler(self.engine, look_callback, TabTargets.MONSTERS_AND_ITEMS)
        elif key == tcod.event.KeySym.w:
            return WalkChoiceHandler(self.engine)
        elif key == tcod.event.KeySym.q:
            return QuaffHandler(self.engine)
        elif key == tcod.event.KeySym.r:
            return ReadHandler(self.engine)
        elif key == tcod.event.KeySym.t:
            return ThrowItemHandler(self.engine)
        elif key == tcod.event.KeySym.z:
            return OverviewMapHandler(self.engine)
        elif is_shifted(event, tcod.event.KeySym.N2):
            return DebugHandler(self.engine)
        # No valid key was pressed
        return action


class GameOverEventHandler(EventHandler):
    """Handles input on the game-over screen (shows kill stats, return to menu)."""

    def on_quit(self) -> None:
        """Handle exiting out of a finished game."""
        if os.path.exists("savegame.sav"):
            os.remove("savegame.sav")  # Deletes the active save file.
        raise exceptions.QuitWithoutSaving()  # Avoid saving a finished game.

    def on_render(self, console: tcod.Console) -> None:  # pylint: disable=too-many-locals
        super().on_render(console)

        kills = self.engine.kill_counts
        prompt_y = console.height // 2 + 1

        if kills:
            sorted_kills = sorted(kills.items(), key=lambda kv: kv[1], reverse=True)
            total_kills = sum(kills.values())

            lines = [f"Total kills: {total_kills}"]
            for name, count in sorted_kills:
                lines.append(f"  {name}: {count}")

            width = max(len(s) for s in lines) + 4
            height = len(lines) + 2
            title = "Kill Stats"
            width = max(width, len(title) + 4)

            x = (console.width - width) // 2
            y = (console.height - height) // 2

            console.draw_frame(
                x=x,
                y=y,
                width=width,
                height=height,
                title=title,
                clear=True,
                fg=(255, 255, 255),
                bg=(0, 0, 0),
            )
            for i, line in enumerate(lines):
                console.print(x + 1, y + 1 + i, line)

            prompt_y = y + height + 1

        console.print(
            console.width // 2,
            prompt_y,
            "Press Enter for Main Menu, Esc to quit",
            fg=color.white,
            alignment=tcod.constants.CENTER,
        )

    def ev_quit(self, event: tcod.event.Quit) -> None:
        self.on_quit()

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[BaseEventHandler]:
        """Return to main menu on Enter, or quit on Escape."""
        if event.sym in CONFIRM_KEYS:
            if os.path.exists("savegame.sav"):
                os.remove("savegame.sav")
            import setup_game  # pylint: disable=import-outside-toplevel

            return setup_game.MainMenu()
        if event.sym == tcod.event.KeySym.ESCAPE:
            self.on_quit()
        return None




# Import at end, to avoid circular dependency.
from debug import DebugHandler  # pylint: disable=wrong-import-position
