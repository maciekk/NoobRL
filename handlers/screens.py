"""Screen-style handlers split out from input_handlers.py."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import tcod  # pylint: disable=import-error

from entity import Actor, Item
from tile_types import OUT_OF_BOUNDS

if TYPE_CHECKING:
    from engine import Engine
    from input_handlers import ActionOrHandler


# Block chars for 2x2 wall patterns in overview map (CP437-safe).
# Index = TL*8 + TR*4 + BL*2 + BR*1 where 1=wall, 0=floor.
QUADRANT_CHARS = (
    ord(" "), 0x2584, 0x2584, 0x2584,
    0x2580, 0x2590, 0x2588, 0x2588,
    0x2580, 0x2588, 0x258C, 0x2588,
    0x2580, 0x2588, 0x2588, 0x2588,
)

CURSOR_Y_KEYS = {
    tcod.event.KeySym.UP: -1,
    tcod.event.KeySym.DOWN: 1,
    tcod.event.KeySym.PAGEUP: -10,
    tcod.event.KeySym.PAGEDOWN: 10,
}


class HistoryViewer(__import__("input_handlers").EventHandler):
    """Print the history on a larger window which can be navigated."""

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.log_length = len(engine.message_log.messages)
        self.cursor = self.log_length - 1

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)

        log_console = tcod.Console(console.width - 6, console.height - 6)
        log_console.draw_frame(0, 0, log_console.width, log_console.height)
        log_console.print_box(0, 0, log_console.width, 1, "┤Message history├", alignment=tcod.CENTER)

        self.engine.message_log.render_messages(
            log_console,
            1,
            1,
            log_console.width - 2,
            log_console.height - 2,
            self.engine.message_log.messages[: self.cursor + 1],
        )
        log_console.blit(console, 3, 3)

    def ev_keydown(self, event: tcod.event.KeyDown):
        if event.sym in CURSOR_Y_KEYS:
            adjust = CURSOR_Y_KEYS[event.sym]
            if adjust < 0 and self.cursor == 0:
                self.cursor = self.log_length - 1
            elif adjust > 0 and self.cursor == self.log_length - 1:
                self.cursor = 0
            else:
                self.cursor = max(0, min(self.cursor + adjust, self.log_length - 1))
        elif event.sym == tcod.event.KeySym.HOME:
            self.cursor = 0
        elif event.sym == tcod.event.KeySym.END:
            self.cursor = self.log_length - 1
        else:
            from input_handlers import MainGameEventHandler

            return MainGameEventHandler(self.engine)
        return None


class OverviewMapHandler(__import__("input_handlers").EventHandler):
    """Zoomed-out overview of the entire dungeon floor using 2x2 block mapping."""

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)
        self._render_overview(console)

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        if event.sym in (tcod.event.KeySym.z, tcod.event.KeySym.ESCAPE):
            from input_handlers import MainGameEventHandler

            return MainGameEventHandler(self.engine)
        return None

    def _render_overview(self, console: tcod.Console) -> None:
        engine = self.engine
        game_map = engine.game_map
        mw, mh = game_map.width, game_map.height
        vp_w = engine.viewport_width
        vp_h = engine.viewport_height

        ov_w = (mw + 1) // 2
        ov_h = (mh + 1) // 2

        player = engine.player
        p_ox, p_oy = player.x // 2, player.y // 2
        cam_x = p_ox - vp_w // 2
        cam_y = p_oy - vp_h // 2
        if ov_w + 2 <= vp_w:
            cam_x = -(vp_w - (ov_w + 2)) // 2 - 1
        else:
            cam_x = max(-1, min(cam_x, ov_w - vp_w + 1))
        if ov_h + 2 <= vp_h:
            cam_y = -(vp_h - (ov_h + 2)) // 2 - 1
        else:
            cam_y = max(-1, min(cam_y, ov_h - vp_h + 1))

        console.rgb[0:vp_w, 0:vp_h] = OUT_OF_BOUNDS
        map_cx = max(0, -cam_x)
        map_cy = max(0, -cam_y)
        map_cw = min(vp_w, ov_w + max(0, -cam_x)) - map_cx
        map_ch = min(vp_h, ov_h + max(0, -cam_y)) - map_cy
        if map_cw > 0 and map_ch > 0:
            console.rgb[map_cx:map_cx + map_cw, map_cy:map_cy + map_ch] = (
                ord(" "), (0, 0, 0), (0, 0, 0)
            )

        walkable = game_map.tiles["walkable"]
        visible = game_map.visible
        explored = game_map.explored
        revealed = game_map.revealed
        known = visible | explored | revealed

        for sx in range(min(vp_w, ov_w)):
            for sy in range(min(vp_h, ov_h)):
                ox = sx + max(0, cam_x)
                oy = sy + max(0, cam_y)
                if ox >= ov_w or oy >= ov_h:
                    continue
                cx = sx + max(0, -cam_x)
                cy = sy + max(0, -cam_y)
                if cx >= vp_w or cy >= vp_h:
                    continue

                wx0, wy0 = ox * 2, oy * 2
                wx1, wy1 = min(wx0 + 1, mw - 1), min(wy0 + 1, mh - 1)

                tl_known = known[wx0, wy0]
                tr_known = known[wx1, wy0] if wx1 < mw else False
                bl_known = known[wx0, wy1] if wy1 < mh else False
                br_known = known[wx1, wy1] if wx1 < mw and wy1 < mh else False

                if not (tl_known or tr_known or bl_known or br_known):
                    continue

                tl_wall = not walkable[wx0, wy0] or not tl_known
                tr_wall = (wx0 + 1 >= mw) or not walkable[wx0 + 1, wy0] or not tr_known
                bl_wall = (wy0 + 1 >= mh) or not walkable[wx0, wy0 + 1] or not bl_known
                br_wall = (wx0 + 1 >= mw or wy0 + 1 >= mh) or not walkable[wx0 + 1, wy0 + 1] or not br_known

                idx = tl_wall * 8 + tr_wall * 4 + bl_wall * 2 + br_wall
                ch = QUADRANT_CHARS[idx]

                any_visible = (
                    visible[wx0, wy0]
                    or (wx0 + 1 < mw and visible[wx0 + 1, wy0])
                    or (wy0 + 1 < mh and visible[wx0, wy0 + 1])
                    or (wx0 + 1 < mw and wy0 + 1 < mh and visible[wx0 + 1, wy0 + 1])
                )
                fg = (64, 64, 32) if any_visible else (50, 50, 100)
                bg = (32, 32, 0) if any_visible else (0, 0, 0)

                console.ch[cx, cy] = ch
                console.fg[cx, cy] = fg
                console.bg[cx, cy] = bg

        entity_cells: dict[tuple[int, int], tuple[int, str, tuple[int, int, int]]] = {}
        entity_cells[(p_ox, p_oy)] = (5, "@", (255, 255, 255))

        ds_x, ds_y = game_map.downstairs_location
        if known[ds_x, ds_y]:
            ds_key = (ds_x // 2, ds_y // 2)
            if ds_key not in entity_cells or entity_cells[ds_key][0] < 4:
                entity_cells[ds_key] = (4, ">", (255, 255, 0))
        us_x, us_y = game_map.upstairs_location
        if (us_x != 0 or us_y != 0) and known[us_x, us_y]:
            us_key = (us_x // 2, us_y // 2)
            if us_key not in entity_cells or entity_cells[us_key][0] < 4:
                entity_cells[us_key] = (4, "<", (255, 255, 0))

        for entity in game_map.entities:
            if entity is player:
                continue
            should_show = visible[entity.x, entity.y]
            if not should_show and player.is_detecting_monsters and isinstance(entity, Actor) and entity.is_alive:
                should_show = True
            if not should_show and player.is_detecting_items and isinstance(entity, Item):
                should_show = True
            if not should_show:
                continue

            ekey = (entity.x // 2, entity.y // 2)
            if isinstance(entity, Actor) and entity.is_alive:
                prio = 3
                existing = entity_cells.get(ekey)
                if existing and existing[0] > prio:
                    continue
                if existing and existing[0] == prio and existing[1] != entity.char:
                    entity_cells[ekey] = (prio, "M", (255, 100, 100))
                    continue
                entity_cells[ekey] = (prio, entity.char, entity.color)
            elif isinstance(entity, Item):
                prio = 2
                existing = entity_cells.get(ekey)
                if existing and existing[0] > prio:
                    continue
                if existing and existing[0] == prio and existing[1] != entity.char:
                    entity_cells[ekey] = (prio, "&", (255, 255, 255))
                    continue
                fg = entity.display_color if hasattr(entity, "display_color") else entity.color
                entity_cells[ekey] = (prio, entity.char, fg)

        for (ox, oy), (_, char, fg) in entity_cells.items():
            cx = ox - max(0, cam_x) + max(0, -cam_x)
            cy = oy - max(0, cam_y) + max(0, -cam_y)
            if 0 <= cx < vp_w and 0 <= cy < vp_h:
                console.ch[cx, cy] = ord(char)
                console.fg[cx, cy] = fg
                wx0, wy0 = ox * 2, oy * 2
                wall_count = sum(
                    1
                    for wx, wy in ((wx0, wy0), (wx0 + 1, wy0), (wx0, wy0 + 1), (wx0 + 1, wy0 + 1))
                    if wx < mw and wy < mh and not walkable[wx, wy]
                )
                if wall_count >= 2:
                    console.bg[cx, cy] = (20, 20, 50)

        label = " OVERVIEW "
        lx = (vp_w - len(label)) // 2
        console.print(x=lx, y=0, string=label, fg=(255, 255, 0), bg=(0, 0, 40))


class ViewKeybinds(__import__("input_handlers").AskUserEventHandler):
    """Display the keybind list."""

    TITLE = "KEYBOARD SHORTCUTS"
    TEXT = [
        ";: log", "?: keybinds", "g: get item", "o: open (chest/door)", "c: close door",
        "q: quaff potion", "t: throw item", "i: inventory", "d: drop", "C: character stats",
        ">: descend", "<: ascend", "v: examine dungeon (Enter: inspect)", "V: view surroundings",
        "w: walk", "z: overview map",
    ]

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)
        x = self.menu_x
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
