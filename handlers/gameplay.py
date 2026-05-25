"""Gameplay handlers split from input_handlers.py."""
# pylint: disable=missing-function-docstring,missing-class-docstring,import-outside-toplevel,too-many-return-statements

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional, Tuple

import tcod  # pylint: disable=import-error

import actions
import color
import exceptions
import sounds
from actions import Action, BumpAction, CarefulMovementAction, MovementRepeatedAction, PickupAction, WaitAction
from handlers.interaction import (
    CloseableSelectionHandler,
    OpenableSelectionHandler,
    PickupDirectionHandler,
    find_closeable_doors,
    find_openable_targets,
    find_pickup_squares,
)
from handlers.inventory import InventoryActivateHandler, InventoryDropHandler, QuaffHandler, ReadHandler, ThrowItemHandler
from handlers.keys import CONFIRM_KEYS, MOVE_KEYS, SCROLL_SPEED, WAIT_KEYS, has_alt, has_ctrl, has_shift, is_shifted
from handlers.screens import HistoryViewer, OverviewMapHandler, ViewKeybinds
from handlers.targeting import (
    FloorItemDetailHandler,
    FloorItemListHandler,
    MonsterDetailHandler,
    SelectEntityHandler,
    TabTargets,
    WalkChoiceHandler,
)

if TYPE_CHECKING:
    from input_handlers import ActionOrHandler, BaseEventHandler


class QuitConfirmHandler(__import__("input_handlers").EventHandler):
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
        if event.sym == tcod.event.KeySym.y:
            raise SystemExit()
        return MainGameEventHandler(self.engine)


class MainGameEventHandler(__import__("input_handlers").EventHandler):
    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        from debug import DebugHandler
        from input_handlers import CharacterScreenEventHandler, ViewSurroundingsHandler

        action: Optional[Action] = None
        key = event.sym
        modifier = event.mod
        player = self.engine.player

        if player.is_asleep and key not in WAIT_KEYS | {tcod.event.KeySym.ESCAPE, tcod.event.KeySym.LSHIFT, tcod.event.KeySym.RSHIFT, tcod.event.KeySym.LCTRL, tcod.event.KeySym.RCTRL, tcod.event.KeySym.LALT, tcod.event.KeySym.RALT}:
            self.engine.message_log.add_message("You cannot act while asleep!")
            return None

        if is_shifted(event, tcod.event.KeySym.PERIOD):
            return actions.TakeStairsAction(player)

        if is_shifted(event, tcod.event.KeySym.N1):
            wand = self.engine.item_manager.clone("wand_wishing")
            if wand:
                if self.engine.player.inventory.add(wand):
                    sounds.play_sfx(sounds.Sfx.SMOKE_POOF)
                    self.engine.message_log.add_message("A Wand of Wishing appears in your pack!")
                else:
                    wand.place(self.engine.player.x, self.engine.player.y, self.engine.game_map)
                    self.engine.message_log.add_message("A Wand of Wishing appears at your feet!")
            return None

        if is_shifted(event, tcod.event.KeySym.COMMA):
            return actions.TakeUpStairsAction(player)

        if key in MOVE_KEYS and has_alt(modifier):
            dx, dy = MOVE_KEYS[key]
            self.engine.camera_x += dx * SCROLL_SPEED
            self.engine.camera_y += dy * SCROLL_SPEED
            self.engine.clamp_camera()
            return None

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
            player_items = [item for item in self.engine.game_map.items if item.x == player.x and item.y == player.y]
            if player_items:
                action = PickupAction(player)
            else:
                surrounding = find_pickup_squares(self.engine)
                if not surrounding:
                    self.engine.message_log.add_message("There is nothing here to pick up.", color.impossible)
                elif len(surrounding) == 1:
                    dx, dy, _, _ = surrounding[0]
                    action = PickupAction(player, player.x + dx, player.y + dy)
                else:
                    return PickupDirectionHandler(self.engine, surrounding)
        elif key == tcod.event.KeySym.i:
            return InventoryActivateHandler(self.engine)
        elif key == tcod.event.KeySym.o:
            targets = find_openable_targets(self.engine)
            if len(targets) == 0:
                self.engine.message_log.add_message("There is nothing here to open.", color.impossible)
                return None
            if len(targets) == 1:
                *_, target = targets[0]
                if isinstance(target, Action):
                    action = target
                else:
                    target.open(player)
                    return None
            else:
                return OpenableSelectionHandler(self.engine, targets)
        elif key == tcod.event.KeySym.d:
            return InventoryDropHandler(self.engine)
        elif is_shifted(event, tcod.event.KeySym.c):
            return CharacterScreenEventHandler(self.engine)
        elif key == tcod.event.KeySym.c:
            targets = find_closeable_doors(self.engine)
            if len(targets) == 0:
                self.engine.message_log.add_message("There are no open doors nearby.", color.impossible)
                return None
            if len(targets) == 1:
                *_, action = targets[0]
                return action
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
                        back = SelectEntityHandler(self.engine, look_callback, TabTargets.MONSTERS_AND_ITEMS, initial_xy=(x, y))
                        return MonsterDetailHandler(self.engine, actor, back)
                    items_here = [i for i in game_map.items if i.x == x and i.y == y]
                    if items_here:
                        back = SelectEntityHandler(self.engine, look_callback, TabTargets.MONSTERS_AND_ITEMS, initial_xy=(x, y))
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
        return action



class GameOverEventHandler(__import__("input_handlers").EventHandler):
    def on_quit(self) -> None:
        if os.path.exists("savegame.sav"):
            os.remove("savegame.sav")
        raise exceptions.QuitWithoutSaving()

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)
        kills = self.engine.kill_counts
        prompt_y = console.height // 2 + 1

        if kills:
            sorted_kills = sorted(kills.items(), key=lambda kv: kv[1], reverse=True)
            total_kills = sum(kills.values())
            lines = [f"Total kills: {total_kills}"] + [f"  {name}: {count}" for name, count in sorted_kills]
            width = max(max(len(s) for s in lines) + 4, len("Kill Stats") + 4)
            height = len(lines) + 2
            x = (console.width - width) // 2
            y = (console.height - height) // 2
            console.draw_frame(x=x, y=y, width=width, height=height, title="Kill Stats", clear=True, fg=(255, 255, 255), bg=(0, 0, 0))
            for i, line in enumerate(lines):
                console.print(x + 1, y + 1 + i, line)
            prompt_y = y + height + 1

        console.print(console.width // 2, prompt_y, "Press Enter for Main Menu, Esc to quit", fg=color.white, alignment=tcod.constants.CENTER)

    def ev_quit(self, _event: tcod.event.Quit) -> None:
        self.on_quit()

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[BaseEventHandler]:
        if event.sym in CONFIRM_KEYS:
            if os.path.exists("savegame.sav"):
                os.remove("savegame.sav")
            import setup_game  # pylint: disable=import-outside-toplevel

            return setup_game.MainMenu()
        if event.sym == tcod.event.KeySym.ESCAPE:
            self.on_quit()
        return None
