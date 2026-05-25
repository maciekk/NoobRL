"""Targeting/look handlers split from input_handlers.py."""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Callable, Optional, Tuple

import tcod  # pylint: disable=import-error

import color
from actions import Action, TargetMovementAction, ThrowAction
from entity import Actor, Item
from handlers.inventory import _item_type_and_stat_lines

if TYPE_CHECKING:
    from engine import Engine
    from input_handlers import ActionOrHandler


class SelectIndexHandler(__import__("input_handlers").AskUserEventHandler):
    """Handles asking the user for an index on the map."""

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self._saved_camera = (engine.camera_x, engine.camera_y)
        pos = self._resolve_last_target_pos()
        if pos:
            engine.mouse_location = pos
        else:
            player = self.engine.player
            engine.mouse_location = player.x, player.y
        self._pan_to_cursor()

    def _resolve_last_target_pos(self) -> Optional[Tuple[int, int]]:
        actor = self.engine.last_target_actor
        if actor is None or not actor.is_alive:
            return None
        game_map = self.engine.game_map
        if actor in game_map.actors and game_map.visible[actor.x, actor.y]:
            self.engine.last_target_pos = (actor.x, actor.y)
            return actor.x, actor.y
        return self.engine.last_target_pos

    def _pan_to_cursor(self) -> None:
        wx, wy = self.engine.mouse_location
        sx, sy = self.engine.world_to_screen(wx, wy)
        vw, vh = self.engine.viewport_width, self.engine.viewport_height
        margin = 3
        if sx < margin:
            self.engine.camera_x -= margin - sx
        elif sx >= vw - margin:
            self.engine.camera_x += sx - (vw - margin) + 1
        if sy < margin:
            self.engine.camera_y -= margin - sy
        elif sy >= vh - margin:
            self.engine.camera_y += sy - (vh - margin) + 1
        self.engine.clamp_camera()

    def _restore_camera(self) -> None:
        self.engine.camera_x, self.engine.camera_y = self._saved_camera

    def _save_target_actor(self, x: int, y: int) -> None:
        actor = self.engine.game_map.get_actor_at_location(x, y)
        if actor and actor is not self.engine.player:
            self.engine.last_target_actor = actor
            self.engine.last_target_pos = (x, y)

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)
        wx, wy = self.engine.mouse_location
        sx, sy = self.engine.world_to_screen(wx, wy)
        if 0 <= sx < console.width and 0 <= sy < self.engine.viewport_height:
            console.rgb["bg"][sx, sy] = color.white
            console.rgb["fg"][sx, sy] = color.black

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        from handlers.keys import CONFIRM_KEYS, MOVE_KEYS, has_alt, has_ctrl, has_shift

        key = event.sym
        if key in MOVE_KEYS:
            modifier = 1
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
            x = max(0, min(x, self.engine.game_map.width - 1))
            y = max(0, min(y, self.engine.game_map.height - 1))
            self.engine.mouse_location = x, y
            self._pan_to_cursor()
            return None
        if key in CONFIRM_KEYS:
            self._save_target_actor(*self.engine.mouse_location)
            self._restore_camera()
            return self.on_index_selected(*self.engine.mouse_location)
        return super().ev_keydown(event)

    def ev_mousebuttondown(self, event: tcod.event.MouseButtonDown) -> Optional[ActionOrHandler]:
        sx, sy = event.tile
        if 0 <= sx < self.engine.viewport_width and 0 <= sy < self.engine.viewport_height and event.button == 1:
            wx, wy = self.engine.screen_to_world(sx, sy)
            if self.engine.game_map.in_bounds(wx, wy):
                self._save_target_actor(wx, wy)
                self._restore_camera()
                return self.on_index_selected(wx, wy)
        return super().ev_mousebuttondown(event)

    def on_exit(self) -> Optional[ActionOrHandler]:
        self._restore_camera()
        return super().on_exit()

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        raise NotImplementedError()


class TabTargets(Enum):
    MONSTERS_ONLY = auto()
    MONSTERS_AND_ITEMS = auto()


class SelectEntityHandler(SelectIndexHandler):
    def __init__(
        self,
        engine: Engine,
        callback: Callable[[Tuple[int, int]], Optional[ActionOrHandler]],
        tab_targets: TabTargets = TabTargets.MONSTERS_ONLY,
        initial_xy: Optional[Tuple[int, int]] = None,
    ):
        super().__init__(engine)
        self.callback = callback
        self.tab_targets = tab_targets
        if initial_xy is not None:
            engine.mouse_location = initial_xy
            self._pan_to_cursor()

    def _tab_entity_list(self) -> list:
        game_map = self.engine.game_map
        entities: list = [
            a for a in game_map.actors if a is not self.engine.player and a.is_alive and game_map.visible[a.x, a.y]
        ]
        if self.tab_targets == TabTargets.MONSTERS_AND_ITEMS:
            entities.extend(item for item in game_map.items if game_map.visible[item.x, item.y])
        return entities

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        if event.sym == tcod.event.KeySym.TAB:
            cx, cy = self.engine.mouse_location
            entities = self._tab_entity_list()
            if entities:
                entities.sort(key=lambda e: max(abs(e.x - cx), abs(e.y - cy)))
                if entities[0].x == cx and entities[0].y == cy:
                    entities = entities[1:] + entities[:1]
                self.engine.mouse_location = entities[0].x, entities[0].y
                self._pan_to_cursor()
            return None
        return super().ev_keydown(event)

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        return self.callback((x, y))


class MonsterDetailHandler(__import__("input_handlers").AskUserEventHandler):
    def __init__(self, engine: Engine, actor: Actor, back_handler: SelectEntityHandler):
        super().__init__(engine)
        self.actor = actor
        self.back_handler = back_handler

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
            lines.append((f"{eff.name}", color.risky))
        player = self.engine.player
        distance = max(abs(actor.x - player.x), abs(actor.y - player.y))
        can_see_player = (not actor.is_asleep and not actor.is_blind and self.engine.game_map.visible[actor.x, actor.y] and not player.is_invisible and distance <= actor.sight_range)
        if can_see_player:
            lines.append(("Sees you", color.dangerous))
        elif actor.noticed_player:
            ai = actor.ai
            lines.append(("Hunting", color.risky) if hasattr(ai, "last_known_target") and ai.last_known_target else ("Aware of you", color.risky))
        else:
            lines.append(("Unaware", color.safe))
        lines.append(("", color.white))
        lines.append((("(Esc) Back"), color.white))

        x = self.menu_x
        width = max(len(actor.name) + 6, max(len(text) for text, _ in lines) + 2)
        console.draw_frame(x=x, y=0, width=width, height=len(lines) + 2, title=actor.name, clear=True, fg=(255, 255, 255), bg=(0, 0, 0))
        for i, (text, fg) in enumerate(lines):
            console.print(x + 1, 1 + i, text, fg=fg)

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        if event.sym == tcod.event.KeySym.ESCAPE:
            return self.back_handler
        return None


class FloorItemListHandler(__import__("input_handlers").ListSelectionHandler):
    TITLE = "Items on floor"

    def __init__(self, engine: Engine, items: list, back_handler: SelectEntityHandler):
        super().__init__(engine)
        self.items_list = items
        self.back_handler = back_handler

    def get_items(self) -> list:
        return self.items_list

    def get_display_string(self, index: int, item) -> str:
        return item.display_name

    def on_selection(self, index: int, item) -> Optional[ActionOrHandler]:
        return FloorItemDetailHandler(self.engine, item, self.back_handler)

    def on_exit(self) -> Optional[ActionOrHandler]:
        return self.back_handler


class FloorItemDetailHandler(__import__("input_handlers").AskUserEventHandler):
    def __init__(self, engine: Engine, item: Item, back_handler: SelectEntityHandler):
        super().__init__(engine)
        self.item = item
        self.back_handler = back_handler

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)
        item = self.item
        lines = [(f"{item.char} {item.display_name}", item.display_color)]
        lines.extend(_item_type_and_stat_lines(item))
        lines.append(("", color.white))
        lines.append(("(Esc) Back", color.white))

        x = self.menu_x
        width = max(len(item.display_name) + 6, max(len(text) for text, _ in lines) + 2)
        console.draw_frame(x=x, y=0, width=width, height=len(lines) + 2, title=item.display_name, clear=True, fg=(255, 255, 255), bg=(0, 0, 0))
        for i, (text, fg) in enumerate(lines):
            console.print(x + 1, 1 + i, text, fg=fg)

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        if event.sym == tcod.event.KeySym.ESCAPE:
            return self.back_handler
        return None


class WalkChoiceHandler(SelectIndexHandler):
    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        from input_handlers import is_shifted

        game_map = self.engine.game_map
        if is_shifted(event, tcod.event.KeySym.PERIOD):
            sx, sy = game_map.downstairs_location
            if game_map.visible[sx, sy] or game_map.explored[sx, sy] or game_map.revealed[sx, sy]:
                self.engine.mouse_location = sx, sy
            return None
        if is_shifted(event, tcod.event.KeySym.COMMA):
            ux, uy = game_map.upstairs_location
            if (ux, uy) != (0, 0) and (game_map.visible[ux, uy] or game_map.explored[ux, uy] or game_map.revealed[ux, uy]):
                self.engine.mouse_location = ux, uy
            return None
        return super().ev_keydown(event)

    def on_index_selected(self, x: int, y: int):
        return TargetMovementAction(self.engine.player, x, y)


class AreaRangedAttackHandler(SelectIndexHandler):
    def __init__(self, engine: Engine, radius: int, callback: Callable[[Tuple[int, int]], Optional[Action]]):
        super().__init__(engine)
        self.radius = radius
        self.callback = callback

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)
        x, y = self.engine.mouse_location
        for tx in range(x - self.radius, x + self.radius + 1):
            for ty in range(y - self.radius, y + self.radius + 1):
                if (tx - x) ** 2 + (ty - y) ** 2 <= self.radius ** 2 and self.engine.game_map.in_bounds(tx, ty):
                    sx, sy = self.engine.world_to_screen(tx, ty)
                    if 0 <= sx < console.width and 0 <= sy < self.engine.viewport_height:
                        console.rgb["bg"][sx, sy] = color.red

    def on_index_selected(self, x: int, y: int) -> Optional[Action]:
        return self.callback((x, y))


class FireballProjectileHandler(SelectEntityHandler):
    def __init__(self, engine: Engine, radius: int, callback: Callable[[Tuple[int, int]], Optional[Action]]):
        super().__init__(engine, callback)
        self.radius = radius

    def _get_projectile_path(self) -> list[tuple[int, int]]:
        player = self.engine.player
        px, py = player.x, player.y
        tx, ty = self.engine.mouse_location
        if (tx, ty) == (px, py):
            return []
        gm = self.engine.game_map
        line = tcod.los.bresenham((px, py), (tx, ty)).tolist()
        if line and (line[0][0], line[0][1]) == (px, py):
            line = line[1:]
        path: list[tuple[int, int]] = []
        for lx, ly in line:
            if not gm.in_bounds(lx, ly) or not gm.tiles["walkable"][lx, ly]:
                break
            path.append((lx, ly))
            actor = gm.get_actor_at_location(lx, ly)
            if actor and actor is not player:
                break
        return path

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)
        path = self._get_projectile_path()
        if not path:
            return
        for tx, ty in path[:-1]:
            self.engine.print_at_world(console, tx, ty, string=".", fg=(255, 140, 0))
        ix, iy = path[-1]
        self.engine.print_at_world(console, ix, iy, string="*", fg=(255, 255, 100))
        for tx in range(ix - self.radius, ix + self.radius + 1):
            for ty in range(iy - self.radius, iy + self.radius + 1):
                if (tx - ix) ** 2 + (ty - iy) ** 2 <= self.radius ** 2 and self.engine.game_map.in_bounds(tx, ty):
                    sx, sy = self.engine.world_to_screen(tx, ty)
                    if 0 <= sx < console.width and 0 <= sy < self.engine.viewport_height:
                        console.rgb["bg"][sx, sy] = color.red


class TeleportTargetHandler(SelectIndexHandler):
    def __init__(self, engine: Engine, callback: Callable[[Tuple[int, int]], Optional[Action]]):
        super().__init__(engine)
        self.callback = callback

    def on_index_selected(self, x: int, y: int) -> Optional[Action]:
        return self.callback((x, y))


class LightningRayTargetHandler(SelectIndexHandler):
    MAX_RAY_LENGTH = 16

    def __init__(self, engine: Engine, callback: Callable[[Tuple[int, int]], Optional[Action]]):
        super().__init__(engine)
        self.callback = callback

    def _ray_char(self) -> str:
        player = self.engine.player
        tx, ty = self.engine.mouse_location
        dx = tx - player.x
        dy = ty - player.y
        if dx == 0:
            return "|"
        if dy == 0:
            return "-"
        return "\\" if (dx > 0) == (dy > 0) else "/"

    def _get_ray_path(self) -> list[tuple[int, int]]:
        player = self.engine.player
        px, py = player.x, player.y
        tx, ty = self.engine.mouse_location
        if (tx, ty) == (px, py):
            return []
        dx = tx - px
        dy = ty - py
        length = max(abs(dx), abs(dy))
        scale = (self.MAX_RAY_LENGTH + 2) / length
        far_x = int(px + dx * scale)
        far_y = int(py + dy * scale)
        gm = self.engine.game_map
        line = tcod.los.bresenham((px, py), (far_x, far_y)).tolist()
        if line and (line[0][0], line[0][1]) == (px, py):
            line = line[1:]
        path: list[tuple[int, int]] = []
        for lx, ly in line:
            if len(path) >= self.MAX_RAY_LENGTH or not gm.in_bounds(lx, ly) or not gm.tiles["walkable"][lx, ly]:
                break
            path.append((lx, ly))
        return path

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)
        ray_char = self._ray_char()
        for tx, ty in self._get_ray_path():
            self.engine.print_at_world(console, tx, ty, string=ray_char, fg=(80, 160, 255))

    def on_index_selected(self, x: int, y: int) -> Optional[Action]:
        return self.callback((x, y))


class DiggingRayTargetHandler(SelectIndexHandler):
    MAX_RAY_LENGTH = 5

    def __init__(self, engine: Engine, callback: Callable[[Tuple[int, int]], Optional[Action]]):
        super().__init__(engine)
        self.callback = callback

    def _ray_char(self) -> str:
        player = self.engine.player
        tx, ty = self.engine.mouse_location
        dx = tx - player.x
        dy = ty - player.y
        if dx == 0:
            return "|"
        if dy == 0:
            return "-"
        return "\\" if (dx > 0) == (dy > 0) else "/"

    def _get_ray_path(self) -> list[tuple[int, int]]:
        player = self.engine.player
        px, py = player.x, player.y
        tx, ty = self.engine.mouse_location
        if (tx, ty) == (px, py):
            return []
        dx = tx - px
        dy = ty - py
        length = max(abs(dx), abs(dy))
        scale = (self.MAX_RAY_LENGTH + 2) / length
        far_x = int(px + dx * scale)
        far_y = int(py + dy * scale)
        gm = self.engine.game_map
        line = tcod.los.bresenham((px, py), (far_x, far_y)).tolist()
        if line and (line[0][0], line[0][1]) == (px, py):
            line = line[1:]
        path: list[tuple[int, int]] = []
        for lx, ly in line:
            if len(path) >= self.MAX_RAY_LENGTH or not gm.in_bounds(lx, ly):
                break
            path.append((lx, ly))
        return path

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)
        ray_char = self._ray_char()
        gm = self.engine.game_map
        for tx, ty in self._get_ray_path():
            fg = (180, 120, 60) if gm.tiles["walkable"][tx, ty] else (220, 160, 50)
            self.engine.print_at_world(console, tx, ty, string=ray_char, fg=fg)

    def on_index_selected(self, x: int, y: int) -> Optional[Action]:
        return self.callback((x, y))


class ThrowTargetHandler(SelectIndexHandler):
    def __init__(self, engine: Engine, item: Item):
        super().__init__(engine)
        self.item = item
        engine.message_log.add_message("Aim: move keys, Tab=nearest enemy, Alt+dir=throw, Enter=confirm", color.white)

    def _snap_to_nearest_enemy(self) -> None:
        game_map = self.engine.game_map
        cx, cy = self.engine.mouse_location
        best_dist = float("inf")
        best_pos = None
        for actor in game_map.actors:
            if actor is self.engine.player or not actor.is_alive or not game_map.visible[actor.x, actor.y] or (actor.x, actor.y) == (cx, cy):
                continue
            dist = (actor.x - cx) ** 2 + (actor.y - cy) ** 2
            if dist < best_dist:
                best_dist = dist
                best_pos = (actor.x, actor.y)
        if best_pos:
            self.engine.mouse_location = best_pos

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        from handlers.inventory import ThrowItemHandler
        from handlers.keys import CONFIRM_KEYS, MOVE_KEYS, has_alt, has_ctrl, has_shift

        key = event.sym
        if key == tcod.event.KeySym.ESCAPE:
            return ThrowItemHandler(self.engine)
        if key == tcod.event.KeySym.TAB:
            self._snap_to_nearest_enemy()
            return None
        if key in MOVE_KEYS and has_alt(event.mod):
            dx, dy = MOVE_KEYS[key]
            player = self.engine.player
            return ThrowAction(player, self.item, (player.x + dx * ThrowAction.MAX_RANGE, player.y + dy * ThrowAction.MAX_RANGE))
        if key in MOVE_KEYS:
            modifier = 1
            if has_shift(event.mod):
                modifier *= 5
            if has_ctrl(event.mod):
                modifier *= 10
            x, y = self.engine.mouse_location
            dx, dy = MOVE_KEYS[key]
            x = max(0, min(x + dx * modifier, self.engine.game_map.width - 1))
            y = max(0, min(y + dy * modifier, self.engine.game_map.height - 1))
            self.engine.mouse_location = x, y
            return None
        if key in CONFIRM_KEYS:
            self._save_target_actor(*self.engine.mouse_location)
            return self.on_index_selected(*self.engine.mouse_location)
        return super().ev_keydown(event)

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        return ThrowAction(self.engine.player, self.item, (x, y))
