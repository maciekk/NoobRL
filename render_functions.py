from __future__ import annotations

import time
from typing import Tuple, TYPE_CHECKING

import color
import tile_types
from entity import Actor, Item

if TYPE_CHECKING:
    from tcod import Console
    from engine import Engine
    from game_map import GameMap


def entity_brief(entity) -> str:
    """Provides a brief summary of entity."""
    if isinstance(entity, Item):
        s = entity.display_name
        if entity.char == "/":
            s += f" ({entity.stack_count}c)"
        elif entity.stackable and entity.stack_count > 1:
            s += f" (x{entity.stack_count})"
    else:
        s = f"{entity.name}"
        if isinstance(entity, Actor):
            s += f"[{entity.fighter.hp}/{entity.fighter.max_hp}]"
    return s


def get_tile_name(x: int, y: int, game_map: GameMap) -> str:
    tile = game_map.tiles[x, y]
    if tile == tile_types.down_stairs:
        return "stairs down"
    elif tile == tile_types.up_stairs:
        return "stairs up"
    elif tile == tile_types.wall:
        return "wall"
    elif tile == tile_types.floor:
        return "floor"
    elif tile == tile_types.tall_grass:
        return "tall grass"
    return ""


def get_names_at_location(x: int, y: int, game_map: GameMap) -> str:
    if not game_map.in_bounds(x, y) or not game_map.visible[x, y]:
        return ""

    parts = []

    entity_names = ", ".join(
        entity_brief(entity)
        for entity in game_map.entities
        if entity.x == x and entity.y == y
    )
    if entity_names:
        parts.append(entity_names)

    tile_name = get_tile_name(x, y, game_map)
    if tile_name:
        parts.append(f"({tile_name})")

    return " ".join(parts).capitalize()


def render_bar(
    console: Console,
    name,
    current_value: int,
    maximum_value: int,
    color_fg,
    color_bg,
    x: int,
    y: int,
    total_width: int,
) -> None:
    bar_width = int(float(current_value) / maximum_value * total_width)
    bar_width = min(bar_width, total_width)

    console.draw_rect(x=x, y=y, width=20, height=1, ch=1, bg=color_bg)

    if bar_width > 0:
        console.draw_rect(x=x, y=y, width=bar_width, height=1, ch=1, bg=color_fg)

    console.print(
        x=x + 1,
        y=y,
        string=f"{name}: {current_value}/{maximum_value}",
        fg=color.bar_text,
    )


def render_dungeon_level(
    console: Console, dungeon_level: int, location: Tuple[int, int]
) -> None:
    """
    Render the level the player is currently on, at the given location.
    """
    x, y = location

    console.print(x=x, y=y, string=f"Dungeon level: {dungeon_level}")


def render_names_at_mouse_location(
    console: Console, x: int, y: int, engine: Engine
) -> None:
    mouse_x, mouse_y = int(engine.mouse_location[0]), int(engine.mouse_location[1])

    names_at_mouse_location = get_names_at_location(
        x=mouse_x, y=mouse_y, game_map=engine.game_map
    )

    console.print(x=x, y=y, string=names_at_mouse_location)


def _explosion_color(heat: float) -> tuple:
    """Map heat [0.0, 1.0] to a color: dark-red (cold) → red → orange → yellow → white (hot)."""
    stops = [
        (0.00, (100,   0,   0)),
        (0.25, (200,  40,   0)),
        (0.50, (255, 140,   0)),
        (0.75, (255, 255,   0)),
        (1.00, (255, 255, 255)),
    ]
    heat = max(0.0, min(1.0, heat))
    for i in range(len(stops) - 1):
        h0, c0 = stops[i]
        h1, c1 = stops[i + 1]
        if h0 <= heat <= h1:
            t = (heat - h0) / (h1 - h0)
            return tuple(int(c0[j] + t * (c1[j] - c0[j])) for j in range(3))
    return stops[-1][1]


def animate_explosion(
    engine,
    x: int,
    y: int,
    radius: int,
    console,
    context,
) -> None:
    """Animate a 5-frame explosion centered at (x, y) with the given radius.

    Each frame uses a different character and cools down. Within each frame,
    tiles closer to the center are brighter and hotter. Game state is not mutated.
    """
    chars = ["*", "x", "+", "-", "."]
    tiles = [
        (tx, ty)
        for tx in range(x - radius, x + radius + 1)
        for ty in range(y - radius, y + radius + 1)
        if (tx - x) ** 2 + (ty - y) ** 2 <= radius ** 2
        and engine.game_map.in_bounds(tx, ty)
        and engine.game_map.visible[tx, ty]
    ]
    if not tiles:
        return
    r = max(radius, 1)
    for f, char in enumerate(chars):
        console.clear()
        engine.render(console)
        for tx, ty in tiles:
            d = ((tx - x) ** 2 + (ty - y) ** 2) ** 0.5
            heat = 1.0 - (f / 4) * 0.7 - (d / r) * 0.3
            console.print(x=tx, y=ty, string=char, fg=_explosion_color(heat))
        context.present(console, keep_aspect=True, integer_scaling=False)
        time.sleep(0.08)


def animate_projectile(
    engine,
    frames: list[tuple[int, int, str, tuple[int, int, int]]],
    console,
    context,
    frame_delay: float = 0.05,
) -> None:
    """Play a frame-by-frame animation on screen.

    Each frame is (x, y, char, fg_color). Only visible tiles are rendered;
    off-FOV frames are silently skipped. Game state is not mutated.
    """
    for x, y, char, fg in frames:
        if not engine.game_map.in_bounds(x, y):
            continue
        if not engine.game_map.visible[x, y]:
            continue
        console.clear()
        engine.render(console)
        console.print(x=x, y=y, string=char, fg=fg)
        context.present(console, keep_aspect=True, integer_scaling=False)
        time.sleep(frame_delay)
