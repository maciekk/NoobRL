"""Keyboard and mouse input handling via a state machine of handler classes."""
# pylint: disable=too-many-lines,fixme

from __future__ import annotations

import os
import time

from typing import Callable, Optional, Tuple, TYPE_CHECKING, Union

import tcod  # pylint: disable=import-error
from tcod import libtcodpy  # pylint: disable=import-error

import actions
from actions import (
    Action,
    BumpAction,
    CarefulMovementAction,
    MovementRepeatedAction,
    PickupAction,
    TargetMovementAction,
    ThrowAction,
    WaitAction,
)
import color
import exceptions
import tile_types
from entity import Actor, Item
from equipment_types import EquipmentType

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

MIN_FRAME_INTERVAL = 0.01


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

    def handle_events(self, event: tcod.event.Event) -> BaseEventHandler:
        """Handle events and dispatch actions; check for death and level-up conditions."""
        action_or_state = self.dispatch(event)
        if isinstance(action_or_state, BaseEventHandler):
            return action_or_state
        if self.handle_action(action_or_state):
            # A valid action was performed.
            if not self.engine.player.is_alive:
                # The player was killed sometime during or after the action.
                return GameOverEventHandler(self.engine)
            if self.engine.player.level.requires_level_up:
                self.engine.message_log.add_message("You leveled up!", stack=False)
                return LevelUpEventHandler(self.engine)
            return MainGameEventHandler(self.engine)  # Return to the main handler.
        return self

    def handle_action(self, action: Optional[Action]) -> bool:
        """Execute an action and advance the turn if valid; return True if turn advanced."""
        if action is None:
            return False

        while True:
            try:
                should_repeat = action.perform()
            except exceptions.Impossible as exc:
                self.engine.message_log.add_message(exc.args[0], color.impossible)
                return False  # Skip enemy turn on exceptions.

            self.engine.end_turn()
            if not should_repeat:
                break

            time.sleep(MIN_FRAME_INTERVAL)

        return True

    def ev_mousemotion(self, event: tcod.event.MouseMotion) -> None:
        """Track mouse position within map bounds."""
        if self.engine.game_map.in_bounds(event.tile.x, event.tile.y):
            self.engine.mouse_location = int(event.tile.x), int(event.tile.y)

    def ev_quit(self, event: tcod.event.Quit) -> Optional[Action]:
        """Handle window close by raising SystemExit."""
        raise SystemExit()

    def on_render(self, console: tcod.Console) -> None:
        """Render the full game state."""
        self.engine.render(console)


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

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

        y = 0

        item_strings = []
        for i, item in enumerate(items):
            item_key = chr(ord("a") + i)
            item_strings.append(f"({item_key}) {self.get_display_string(i, item)}")

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

        index = key - tcod.event.KeySym.a
        if 0 <= index <= 25:
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
                strings.append(f"(?) {description}")
        return strings

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)

        items = self.get_directional_items()
        num_items = len(items)
        height = max(num_items + 2, 3)
        x = 40 if self.engine.player.x <= 30 else 0
        y = 0
        item_strings = self._build_direction_strings(items)
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

        if key in key_to_item:
            dx, dy, target = key_to_item[key]
            return self.on_directional_selection(dx, dy, target)

        return super().ev_keydown(event)


class CharacterScreenEventHandler(AskUserEventHandler):
    """Displays player statistics, experience, and kill counts."""

    TITLE = "Character Information"

    def on_render(self, console: tcod.Console) -> None:  # pylint: disable=too-many-locals
        super().on_render(console)

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

        y = 0

        kills = self.engine.kill_counts
        sorted_kills = sorted(kills.items(), key=lambda kv: kv[1], reverse=True)
        kill_lines = [f"  {name}: {count}" for name, count in sorted_kills]
        total_kills = sum(kills.values())

        stats_height = 7
        kills_height = len(kill_lines) + 2 if kill_lines else 0
        height = stats_height + kills_height

        kill_strings = [f"Kills: {total_kills}"] + kill_lines if kill_lines else []
        all_strings = [
            f"Level: {self.engine.player.level.current_level}",
            f"XP: {self.engine.player.level.current_xp}",
            f"XP for next Level: {self.engine.player.level.experience_to_next_level}",
            f"Attack: {self.engine.player.fighter.power}",
            f"Defense: {self.engine.player.fighter.defense}",
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
            x=x + 1, y=y + 4, string=f"Attack: {self.engine.player.fighter.power}"
        )
        console.print(
            x=x + 1, y=y + 5, string=f"Defense: {self.engine.player.fighter.defense}"
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
        monsters = sorted(
            (dist2(px, py, a.x, a.y), a.name, direction(px, py, a.x, a.y))
            for a in game_map.actors
            if a is not self.engine.player and visible[a.x, a.y]
        )
        corpses = sorted(
            (dist2(px, py, e.x, e.y), e.name, direction(px, py, e.x, e.y))
            for e in game_map.entities
            if isinstance(e, Actor) and not e.is_alive and visible[e.x, e.y]
        )
        items_sorted = sorted(
            (dist2(px, py, it.x, it.y), it.name, direction(px, py, it.x, it.y))
            for it in game_map.items
            if visible[it.x, it.y]
        )
        features: list = []
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
        """Build display strings from sorted entity and feature collections."""
        lines: list[str] = []
        if monsters:
            lines.append("Monsters:")
            lines.extend(f"  {name} {d}" for _, name, d in monsters)
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
        x = 40 if self.engine.player.x <= 30 else 0
        y = 0
        height = len(lines) + 2
        max_line_width = max(len(s) for s in lines)
        width = max(len(self.TITLE) + 4, max_line_width + 2)
        console.draw_frame(
            x=x, y=y, width=width, height=height, title=self.TITLE,
            clear=True, fg=(255, 255, 255), bg=(0, 0, 0),
        )
        for i, line in enumerate(lines):
            console.print(x=x + 1, y=y + 1 + i, string=line)


class LevelUpEventHandler(AskUserEventHandler):
    """Allows player to choose which stat to increase when leveling up (1-3 keys)."""

    TITLE = "Level Up"

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

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


class InventoryEventHandler(ListSelectionHandler):
    """Base for inventory selection menus (subclasses handle specific actions)."""

    TITLE = "<missing title>"
    use_cursor = True

    def get_items(self) -> list:
        """Return the player's inventory items."""
        return self.engine.player.inventory.items

    def get_display_string(self, index: int, item) -> str:
        """Return display string with stack count and equipped status."""
        s = item.display_name
        if item.stackable and item.stack_count > 1:
            s += f" (x{item.stack_count})"
        if self.engine.player.equipment.item_is_equipped(item):
            s += " (E)"
        return s

    def on_selection(self, index: int, item) -> Optional[ActionOrHandler]:
        """Dispatch selection to subclass handler."""
        return self.on_item_selected(item)

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        """Called when the user selects a valid item; implement in subclass."""
        raise NotImplementedError()


class InventoryActivateHandler(InventoryEventHandler):
    """Lets player select an item to use; opens item detail screen."""

    TITLE = "Select an item to use"

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        """Show item details for the selected item."""
        return ItemDetailHandler(self.engine, item, self.cursor)


class InventoryDropHandler(InventoryEventHandler):
    """Lets player select an item to drop from inventory."""

    TITLE = "Select an item to drop"

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        """Drop item or ask quantity for stacks."""
        if item.stackable and item.stack_count > 1:
            return DropQuantityHandler(self.engine, item)
        return actions.DropItem(self.engine.player, item)


class QuaffHandler(ListSelectionHandler):
    """Lets the player select a potion to drink from inventory."""

    TITLE = "Quaff which potion?"
    EMPTY_TEXT = "(No potions)"
    use_cursor = True

    def get_items(self) -> list:
        """Return only potion items from inventory."""
        return [item for item in self.engine.player.inventory.items if item.char == "!"]

    def get_display_string(self, index: int, item) -> str:
        """Return display string with stack count for potions."""
        s = item.display_name
        if item.stackable and item.stack_count > 1:
            s += f" (x{item.stack_count})"
        return s

    def on_selection(self, index: int, item) -> Optional[ActionOrHandler]:
        """Get and return the consumable action for the selected potion."""
        return item.consumable.get_action(self.engine.player)


def _item_type_and_stat_lines(item: "Item") -> list:  # pylint: disable=too-many-branches
    """Build type label, description, and stat lines common to all item detail views."""
    lines: list = []
    if item.equippable:
        eq_type = item.equippable.equipment_type
        if eq_type == EquipmentType.WEAPON:
            lines.append(("Weapon", color.white))
        elif eq_type == EquipmentType.AMULET:
            lines.append(("Amulet", color.white))
        elif eq_type == EquipmentType.THROWN:
            if item.stackable and item.stack_count > 1:
                lines.append((f"Thrown weapon (x{item.stack_count})", color.white))
            else:
                lines.append(("Thrown weapon", color.white))
        else:
            lines.append(("Armor", color.white))
    elif item.consumable:
        if item.stackable and item.stack_count > 1:
            lines.append((f"Consumable (x{item.stack_count})", color.white))
        else:
            lines.append(("Consumable", color.white))
    else:
        lines.append(("Item", color.white))
    if item.consumable:
        if item.display_name != item.name:
            lines.append(("???", color.white))
        else:
            for desc_line in item.consumable.get_description():
                lines.append((desc_line, color.white))
    if item.equippable:
        if item.equippable.power_bonus:
            lines.append((f"Attack bonus: +{item.equippable.power_bonus}", color.white))
        if item.equippable.defense_bonus:
            lines.append((f"Defense bonus: +{item.equippable.defense_bonus}", color.white))
    return lines


class ItemDetailHandler(AskUserEventHandler):
    """Displays item stats and offers equip/use/throw/drop actions."""

    def __init__(self, engine: Engine, item: Item, inventory_cursor: int = 0):
        super().__init__(engine)
        self.item = item
        self.inventory_cursor = inventory_cursor

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)

        item = self.item
        player = self.engine.player

        lines: list[tuple[str, tuple[int, int, int]]] = []

        # Item name with symbol.
        lines.append((f"{item.char} {item.display_name}", item.display_color))

        # Type, description, and stats.
        lines.extend(_item_type_and_stat_lines(item))

        # Equipped status for non-thrown equippables.
        if item.equippable and item.equippable.equipment_type != EquipmentType.THROWN:
            if player.equipment.item_is_equipped(item):
                lines.append(("Currently equipped", color.safe))
            else:
                lines.append(("Not equipped", color.white))

        # Separator.
        lines.append(("", color.white))

        # Actions.
        if item.equippable and item.equippable.equipment_type != EquipmentType.THROWN:
            if player.equipment.item_is_equipped(item):
                lines.append(("(e) Unequip", color.white))
            else:
                lines.append(("(e) Equip", color.white))
        if item.consumable:
            lines.append(("(a) Apply", color.white))
        lines.append(("(t) Throw", color.white))
        lines.append(("(d) Drop", color.white))
        lines.append(("(Esc) Back", color.white))

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

        y = 0
        max_line_width = max(len(text) for text, _ in lines)
        width = max(len(item.display_name) + 6, max_line_width + 2)
        height = len(lines) + 2

        console.draw_frame(
            x=x,
            y=y,
            width=width,
            height=height,
            title=item.display_name,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        for i, (text, fg) in enumerate(lines):
            console.print(x + 1, y + 1 + i, text, fg=fg)

    def _get_equip_action(
        self, player: "Actor", item: "Item"
    ) -> Optional[ActionOrHandler]:
        """Return equip/unequip action, or None for thrown weapons."""
        if item.equippable.equipment_type == EquipmentType.THROWN:
            return None
        return actions.EquipAction(player, item)

    def _get_drop_action(
        self, player: "Actor", item: "Item"
    ) -> Optional[ActionOrHandler]:
        """Return drop-quantity handler for stacks, or drop action for singles."""
        if item.stackable and item.stack_count > 1:
            return DropQuantityHandler(self.engine, item)
        return actions.DropItem(player, item)

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        key = event.sym
        item = self.item
        player = self.engine.player

        if key == tcod.event.KeySym.e and item.equippable:
            return self._get_equip_action(player, item)
        if key == tcod.event.KeySym.a and item.consumable:
            return item.consumable.get_action(player)
        if key == tcod.event.KeySym.t:
            return ThrowTargetHandler(self.engine, item)
        if key == tcod.event.KeySym.d:
            return self._get_drop_action(player, item)
        if key == tcod.event.KeySym.ESCAPE:
            return InventoryActivateHandler(self.engine, cursor=self.inventory_cursor)
        return None


class DropQuantityHandler(AskUserEventHandler):
    """Prompts for a number to specify how many items to drop from a stack."""

    def __init__(self, engine: Engine, item: Item):
        super().__init__(engine)
        self.item = item
        self.text = ""

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

        prompt = f"Drop how many {self.item.display_name}? (1-{self.item.stack_count})"
        max_digits = len(str(self.item.stack_count))
        # frame border (2) + prompt + space + max digits + cursor + padding
        width = len(prompt) + max_digits + 4

        console.draw_frame(
            x=x,
            y=0,
            width=width,
            height=3,
            title="Drop",
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )
        console.print(x + 1, 1, f"{prompt} {self.text}_")

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        key = event.sym
        if key == tcod.event.KeySym.ESCAPE:
            return MainGameEventHandler(self.engine)
        if key in CONFIRM_KEYS:
            try:
                count = int(self.text)
            except ValueError:
                self.engine.message_log.add_message("Enter a number.", color.invalid)
                return None
            if count < 1 or count > self.item.stack_count:
                self.engine.message_log.add_message(
                    f"Enter a number between 1 and {self.item.stack_count}.",
                    color.invalid,
                )
                return None
            return actions.DropItem(self.engine.player, self.item, count=count)
        if key == tcod.event.KeySym.BACKSPACE:
            self.text = self.text[:-1]
        else:
            # Handle digit keys directly (0-9 have ASCII values 48-57).
            try:
                c = chr(key)
                if c.isdigit():
                    self.text += c
            except (ValueError, OverflowError):
                pass
        return None


class WishItemHandler(ListSelectionHandler):
    """Displays all available items for selection via Wand of Wishing."""

    TITLE = "Wish for an item"

    def __init__(self, engine: Engine, wand_item: Item):
        super().__init__(engine)
        self.wand_item = wand_item
        self._item_list = sorted(
            [
                (id, item.name)
                for id, item in engine.item_manager.items.items()
                if id != "wand_wishing"
            ],
            key=lambda x: x[1],
        )

    def get_items(self) -> list:
        return self._item_list

    def get_display_string(self, index: int, item) -> str:
        return item[1]

    def on_selection(self, index: int, item) -> Optional[ActionOrHandler]:
        item_id, _ = item
        return actions.WishAction(self.engine.player, self.wand_item, item_id)


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


def find_openable_targets(engine: Engine) -> list:
    """Find openable targets (chests, closed doors) in 3x3 area; return (dx, dy, desc, action)."""
    targets = []
    px, py = engine.player.x, engine.player.y

    for dx in range(-1, 2):
        for dy in range(-1, 2):
            x, y = px + dx, py + dy
            if not engine.game_map.in_bounds(x, y):
                continue

            if engine.game_map.tiles[x, y] == tile_types.door_closed:
                direction = _DOOR_DIRECTIONS.get((dx, dy), "")
                targets.append(
                    (dx, dy, f"Door ({direction})", actions.OpenDoorAction(engine.player, x, y))
                )

            for entity in engine.game_map.entities:
                if entity.x == x and entity.y == y and hasattr(entity, "open"):
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
        target.open(self.engine.player)
        return MainGameEventHandler(self.engine)


def find_closeable_doors(engine: Engine) -> list:
    """Find open doors in 3x3 area; return (dx, dy, description, action) tuples."""
    targets = []
    px, py = engine.player.x, engine.player.y

    for dx in range(-1, 2):
        for dy in range(-1, 2):
            x, y = px + dx, py + dy
            if not engine.game_map.in_bounds(x, y):
                continue

            if engine.game_map.tiles[x, y] == tile_types.door_open:
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


class SelectIndexHandler(AskUserEventHandler):
    """Handles asking the user for an index on the map."""

    def __init__(self, engine: Engine):
        """Sets the cursor to the player when this handler is constructed."""
        super().__init__(engine)
        player = self.engine.player
        engine.mouse_location = player.x, player.y

    def on_render(self, console: tcod.Console) -> None:
        """Highlight the tile under the cursor."""
        super().on_render(console)
        x, y = self.engine.mouse_location
        console.rgb["bg"][x, y] = color.white
        console.rgb["fg"][x, y] = color.black

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        """Check for key movement or confirmation keys."""
        key = event.sym
        if key in MOVE_KEYS:
            modifier = 1  # Holding modifier keys will speed up key movement.
            if has_shift(event.mod):
                modifier *= 5
            if has_ctrl(event.mod):
                modifier *= 10
            if has_alt(event.mod):
                modifier *= 20

            x, y = self.engine.mouse_location
            dx, dy = MOVE_KEYS[key]
            x += dx * modifier
            y += dy * modifier
            # Clamp the cursor index to the map size.
            x = max(0, min(x, self.engine.game_map.width - 1))
            y = max(0, min(y, self.engine.game_map.height - 1))
            self.engine.mouse_location = x, y
            return None
        if key in CONFIRM_KEYS:
            return self.on_index_selected(*self.engine.mouse_location)
        return super().ev_keydown(event)

    def ev_mousebuttondown(
        self, event: tcod.event.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """Left click confirms a selection."""
        if self.engine.game_map.in_bounds(*event.tile):
            if event.button == 1:
                return self.on_index_selected(*event.tile)
        return super().ev_mousebuttondown(event)

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        """Called when an index is selected."""
        raise NotImplementedError()


class LookHandler(SelectIndexHandler):
    """Lets the player look around using the keyboard."""

    def __init__(
        self, engine: Engine, look_x: Optional[int] = None, look_y: Optional[int] = None
    ):
        super().__init__(engine)
        if look_x is not None and look_y is not None:
            engine.mouse_location = look_x, look_y

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        """Inspect what's under the cursor, or return to main handler."""
        game_map = self.engine.game_map

        # Check for a visible monster (not the player).
        if game_map.visible[x, y]:
            actor = game_map.get_actor_at_location(x, y)
            if actor and actor is not self.engine.player and actor.is_alive:
                return MonsterDetailHandler(self.engine, actor, x, y)

            # Check for visible items on this tile.
            items_here = [
                item for item in game_map.items if item.x == x and item.y == y
            ]
            if items_here:
                if len(items_here) == 1:
                    return FloorItemDetailHandler(self.engine, items_here[0], x, y)
                return FloorItemListHandler(self.engine, items_here, x, y)

        return MainGameEventHandler(self.engine)


class MonsterDetailHandler(AskUserEventHandler):
    """Shows detailed stats for a monster under the look cursor."""

    def __init__(self, engine: Engine, actor: "Actor", look_x: int, look_y: int):
        super().__init__(engine)
        self.actor = actor
        self.look_x = look_x
        self.look_y = look_y

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)

        actor = self.actor
        lines: list[tuple[str, tuple[int, int, int]]] = []

        lines.append((f"{actor.char} {actor.name}", actor.color))
        lines.append((f"HP: {actor.fighter.hp}/{actor.fighter.max_hp}", color.white))
        lines.append((f"Attack: {actor.fighter.power}", color.white))
        lines.append((f"Defense: {actor.fighter.defense}", color.white))
        lines.append((f"XP: {actor.level.xp_given}", color.white))
        for eff in actor.effects:
            lines.append((f"{eff.name} ({eff.turns_left}t)", color.risky))
        if actor.noticed_player:
            ai = actor.ai
            if hasattr(ai, "last_known_target") and ai.last_known_target:
                lines.append(("Hunting", color.dangerous))
            else:
                lines.append(("Aware of you", color.risky))
        else:
            lines.append(("Unaware", color.safe))
        lines.append(("", color.white))
        lines.append(("(Esc) Back", color.white))

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

        y = 0
        max_line_width = max(len(text) for text, _ in lines)
        width = max(len(actor.name) + 6, max_line_width + 2)
        height = len(lines) + 2

        console.draw_frame(
            x=x,
            y=y,
            width=width,
            height=height,
            title=actor.name,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        for i, (text, fg) in enumerate(lines):
            console.print(x + 1, y + 1 + i, text, fg=fg)

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        key = event.sym
        if key == tcod.event.KeySym.ESCAPE:
            return LookHandler(self.engine, self.look_x, self.look_y)
        if key in {
            tcod.event.KeySym.LSHIFT,
            tcod.event.KeySym.RSHIFT,
            tcod.event.KeySym.LCTRL,
            tcod.event.KeySym.RCTRL,
            tcod.event.KeySym.LALT,
            tcod.event.KeySym.RALT,
        }:
            return None
        return None


class FloorItemListHandler(ListSelectionHandler):
    """Lets the player select from multiple items on a floor tile."""

    TITLE = "Items on floor"

    def __init__(self, engine: Engine, items: list, look_x: int, look_y: int):
        super().__init__(engine)
        self.items_list = items
        self.look_x = look_x
        self.look_y = look_y

    def get_items(self) -> list:
        return self.items_list

    def get_display_string(self, index: int, item) -> str:
        return item.display_name

    def on_selection(self, index: int, item) -> Optional[ActionOrHandler]:
        return FloorItemDetailHandler(self.engine, item, self.look_x, self.look_y)

    def on_exit(self) -> Optional[ActionOrHandler]:
        return LookHandler(self.engine, self.look_x, self.look_y)


class FloorItemDetailHandler(AskUserEventHandler):
    """Shows read-only item details for an item on the floor."""

    def __init__(self, engine: Engine, item: Item, look_x: int, look_y: int):
        super().__init__(engine)
        self.item = item
        self.look_x = look_x
        self.look_y = look_y

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)

        item = self.item
        lines: list[tuple[str, tuple[int, int, int]]] = []

        # Item name with symbol.
        lines.append((f"{item.char} {item.display_name}", item.display_color))

        # Type, description, and stats.
        lines.extend(_item_type_and_stat_lines(item))

        lines.append(("", color.white))
        lines.append(("(Esc) Back", color.white))

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

        y = 0
        max_line_width = max(len(text) for text, _ in lines)
        width = max(len(item.display_name) + 6, max_line_width + 2)
        height = len(lines) + 2

        console.draw_frame(
            x=x,
            y=y,
            width=width,
            height=height,
            title=item.display_name,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        for i, (text, fg) in enumerate(lines):
            console.print(x + 1, y + 1 + i, text, fg=fg)

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        key = event.sym
        if key == tcod.event.KeySym.ESCAPE:
            return LookHandler(self.engine, self.look_x, self.look_y)
        if key in {
            tcod.event.KeySym.LSHIFT,
            tcod.event.KeySym.RSHIFT,
            tcod.event.KeySym.LCTRL,
            tcod.event.KeySym.RCTRL,
            tcod.event.KeySym.LALT,
            tcod.event.KeySym.RALT,
        }:
            return None
        return None


class WalkChoiceHandler(SelectIndexHandler):
    """Lets the player click or cursor-select a destination tile to walk to."""

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        game_map = self.engine.game_map

        # '>' jumps cursor to downstairs if known.
        if is_shifted(event, tcod.event.KeySym.PERIOD):
            sx, sy = game_map.downstairs_location
            if (
                game_map.visible[sx, sy]
                or game_map.explored[sx, sy]
                or game_map.revealed[sx, sy]
            ):
                self.engine.mouse_location = sx, sy
            return None

        # '<' jumps cursor to upstairs if known.
        if is_shifted(event, tcod.event.KeySym.COMMA):
            ux, uy = game_map.upstairs_location
            if (ux, uy) != (0, 0) and (
                game_map.visible[ux, uy]
                or game_map.explored[ux, uy]
                or game_map.revealed[ux, uy]
            ):
                self.engine.mouse_location = ux, uy
            return None

        return super().ev_keydown(event)

    def on_index_selected(self, x: int, y: int):
        return TargetMovementAction(self.engine.player, x, y)


class SingleRangedAttackHandler(SelectIndexHandler):
    """Handles targeting a single enemy. Only the enemy selected will be affected."""

    def __init__(
        self, engine: Engine, callback: Callable[[Tuple[int, int]], Optional[Action]]
    ):
        super().__init__(engine)

        self.callback = callback

    def on_index_selected(self, x: int, y: int) -> Optional[Action]:
        return self.callback((x, y))


class AreaRangedAttackHandler(SelectIndexHandler):
    """Handles targeting an area within a given radius.

    Any entity within the area will be affected.
    """

    def __init__(
        self,
        engine: Engine,
        radius: int,
        callback: Callable[[Tuple[int, int]], Optional[Action]],
    ):
        super().__init__(engine)

        self.radius = radius
        self.callback = callback

    def on_render(self, console: tcod.Console) -> None:
        """Highlight the tile under the cursor."""
        super().on_render(console)

        x, y = self.engine.mouse_location

        # Draw a rectangle around the targeted area, so the player can see the affected tiles.
        console.draw_frame(
            x=x - self.radius - 1,
            y=y - self.radius - 1,
            width=self.radius**2,
            height=self.radius**2,
            fg=color.red,
            clear=False,
        )

    def on_index_selected(self, x: int, y: int) -> Optional[Action]:
        return self.callback((x, y))


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
                wand.parent = self.engine.player.inventory
                self.engine.player.inventory.add(wand)
                self.engine.message_log.add_message(
                    "A Wand of Wishing appears in your pack!"
                )
            return None

        if is_shifted(event, tcod.event.KeySym.COMMA):
            return actions.TakeUpStairsAction(player)

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
            raise SystemExit()
        elif key == tcod.event.KeySym.SEMICOLON:
            return HistoryViewer(self.engine)
        elif is_shifted(event, tcod.event.KeySym.SLASH):
            return ViewKeybinds(self.engine)
        elif key == tcod.event.KeySym.g:
            action = PickupAction(player)
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
            return LookHandler(self.engine)
        elif key == tcod.event.KeySym.w:
            return WalkChoiceHandler(self.engine)
        elif key == tcod.event.KeySym.q:
            return QuaffHandler(self.engine)
        elif key == tcod.event.KeySym.t:
            return ThrowItemHandler(self.engine)
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


CURSOR_Y_KEYS = {
    tcod.event.KeySym.UP: -1,
    tcod.event.KeySym.DOWN: 1,
    tcod.event.KeySym.PAGEUP: -10,
    tcod.event.KeySym.PAGEDOWN: 10,
}


class HistoryViewer(EventHandler):
    """Print the history on a larger window which can be navigated."""

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.log_length = len(engine.message_log.messages)
        self.cursor = self.log_length - 1

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)  # Draw the main state as the background.

        log_console = tcod.Console(console.width - 6, console.height - 6)

        # Draw a frame with a custom banner title.
        log_console.draw_frame(0, 0, log_console.width, log_console.height)
        log_console.print_box(
            0, 0, log_console.width, 1, "┤Message history├", alignment=tcod.CENTER
        )

        # Render the message log using the cursor parameter.
        self.engine.message_log.render_messages(
            log_console,
            1,
            1,
            log_console.width - 2,
            log_console.height - 2,
            self.engine.message_log.messages[: self.cursor + 1],
        )
        log_console.blit(console, 3, 3)

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[MainGameEventHandler]:
        """Scroll message log; any other key returns to the main game."""
        # Fancy conditional movement to make it feel right.
        if event.sym in CURSOR_Y_KEYS:
            adjust = CURSOR_Y_KEYS[event.sym]
            if adjust < 0 and self.cursor == 0:
                # Only move from the top to the bottom when you're on the edge.
                self.cursor = self.log_length - 1
            elif adjust > 0 and self.cursor == self.log_length - 1:
                # Same with bottom to top movement.
                self.cursor = 0
            else:
                # Otherwise move while staying clamped to the bounds of the history log.
                self.cursor = max(0, min(self.cursor + adjust, self.log_length - 1))
        elif event.sym == tcod.event.KeySym.HOME:
            self.cursor = 0  # Move directly to the top message.
        elif event.sym == tcod.event.KeySym.END:
            self.cursor = self.log_length - 1  # Move directly to the last message.
        else:  # Any other key moves back to the main game state.
            return MainGameEventHandler(self.engine)
        return None


class ViewKeybinds(AskUserEventHandler):
    """Print the history on a larger window which can be navigated."""

    TITLE = "KEYBOARD SHORTCUTS"
    TEXT = [
        ";: log",
        "?: keybinds",
        "g: get item",
        "o: open (chest/door)",
        "c: close door",
        "q: quaff potion",
        "t: throw item",
        "i: inventory",
        "d: drop",
        "C: character stats",
        ">: descend",
        "<: ascend",
        "v: examine dungeon (Enter: inspect)",
        "V: view surroundings",
        "w: walk",
    ]

    def on_render(self, console: tcod.Console) -> None:
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
            height=len(self.TEXT) + 2,
            title=self.TITLE,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        for i, line in enumerate(self.TEXT):
            console.print(x=x + 1, y=y + 1 + i, string=line)


class ThrowItemHandler(InventoryEventHandler):
    """Lets the player select an item to throw."""

    TITLE = "Throw what?"
    use_cursor = True

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        return ThrowTargetHandler(self.engine, item)


class ThrowTargetHandler(SelectIndexHandler):
    """Lets the player aim a thrown item with a cursor.

    Controls:
        Direction keys: move cursor (Shift = 5x, Ctrl = 10x speed)
        Alt + direction: throw immediately in that direction
        Tab: snap cursor to closest visible enemy
        Enter / click: throw at cursor position
        Escape: back to item selection
    """

    def __init__(self, engine: Engine, item: Item):
        super().__init__(engine)
        self.item = item
        engine.message_log.add_message(
            "Aim: move keys, Tab=nearest enemy, Alt+dir=throw, Enter=confirm",
            color.white,
        )

    def _snap_to_nearest_enemy(self) -> None:
        """Move cursor to the closest visible enemy relative to current cursor position."""
        game_map = self.engine.game_map
        cx, cy = self.engine.mouse_location
        best_dist = float("inf")
        best_pos = None

        for actor in game_map.actors:
            if actor is self.engine.player:
                continue
            if not actor.is_alive:
                continue
            if not game_map.visible[actor.x, actor.y]:
                continue
            if (actor.x, actor.y) == (cx, cy):
                continue
            dist = (actor.x - cx) ** 2 + (actor.y - cy) ** 2
            if dist < best_dist:
                best_dist = dist
                best_pos = (actor.x, actor.y)

        if best_pos:
            self.engine.mouse_location = best_pos

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        key = event.sym

        if key == tcod.event.KeySym.ESCAPE:
            return ThrowItemHandler(self.engine)

        # Tab: snap to nearest visible enemy.
        if key == tcod.event.KeySym.TAB:
            self._snap_to_nearest_enemy()
            return None

        # Alt + direction: throw immediately in that direction.
        if key in MOVE_KEYS and has_alt(event.mod):
            dx, dy = MOVE_KEYS[key]
            player = self.engine.player
            target_x = player.x + dx * ThrowAction.MAX_RANGE
            target_y = player.y + dy * ThrowAction.MAX_RANGE
            return ThrowAction(player, self.item, (target_x, target_y))

        # Everything else (cursor movement, confirm) handled by SelectIndexHandler.
        # Override Alt speed-up: only Shift and Ctrl modify cursor speed.
        if key in MOVE_KEYS:
            modifier = 1
            if has_shift(event.mod):
                modifier *= 5
            if has_ctrl(event.mod):
                modifier *= 10

            x, y = self.engine.mouse_location
            dx, dy = MOVE_KEYS[key]
            x += dx * modifier
            y += dy * modifier
            x = max(0, min(x, self.engine.game_map.width - 1))
            y = max(0, min(y, self.engine.game_map.height - 1))
            self.engine.mouse_location = x, y
            return None

        if key in CONFIRM_KEYS:
            return self.on_index_selected(*self.engine.mouse_location)

        return super().ev_keydown(event)

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        return ThrowAction(self.engine.player, self.item, (x, y))


# Import at end, to avoid circular dependency.
from debug import DebugHandler  # pylint: disable=wrong-import-position
