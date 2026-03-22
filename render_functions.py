"""Helper functions for rendering UI elements and animations."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import color
import options
from tile_types import TILE_DOWN_STAIRS, TILE_FLOOR, TILE_TALL_GRASS, TILE_UP_STAIRS, TILE_WALL
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
    """Return a human-readable name for the tile at (x, y)."""
    tile = game_map.tiles[x, y]
    if tile == TILE_DOWN_STAIRS:
        return "stairs down"
    if tile == TILE_UP_STAIRS:
        return "stairs up"
    if tile == TILE_WALL:
        return "wall"
    if tile == TILE_FLOOR:
        return "floor"
    if tile == TILE_TALL_GRASS:
        return "tall grass"
    return ""


def get_names_at_location(x: int, y: int, game_map: GameMap) -> str:
    """Return a formatted string of entity and tile names at the given location."""
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


def render_bar(  # pylint: disable=too-many-arguments,too-many-positional-arguments
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
    """Render a colored progress bar with a label."""
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


def render_names_at_mouse_location(
    console: Console, x: int, y: int, engine: Engine
) -> None:
    """Print entity/tile names at the current mouse cursor position."""
    mouse_x, mouse_y = int(engine.mouse_location[0]), int(engine.mouse_location[1])

    names_at_mouse_location = get_names_at_location(
        x=mouse_x, y=mouse_y, game_map=engine.game_map
    )

    console.print(x=x, y=y, string=names_at_mouse_location)


def _begin_frame(engine, console) -> None:
    """Clear the console and re-render the game state for a new animation frame."""
    console.clear()
    engine.render(console)


def _end_frame(console, context, delay: float) -> None:
    """Present the current console contents and pause for one animation frame."""
    context.present(console, keep_aspect=True, integer_scaling=False)
    time.sleep(delay)


# ---------------------------------------------------------------------------
# Animation compositing
# ---------------------------------------------------------------------------
#
# A render op is a tuple describing one tile to draw in a frame:
#   (x, y, char, fg)            — print char with foreground color
#   (x, y, char, fg, bg)        — print char with foreground and background
#   (x, y, None, None, bg)      — set background only (keep existing char)
#
# A frame is a list of render ops.
# An animation layer is (delay, frames) where delay is the number of frames
# to wait before starting, and frames is an iterable of frame lists.
# Later layers overwrite earlier ones on overlapping tiles.


def composite_animations(engine, layers, console, context, frame_delay=0.04):
    """Play multiple animation layers composited together.

    Args:
        engine: the Engine (for rendering and world-to-screen conversion).
        layers: list of layer tuples. Each is either:
            (delay, frames) — no sound cues, or
            (delay, frames, sound_cues) — with sound cues.
            delay: number of global frames to skip before this layer starts.
            frames: iterable of frame lists (each frame is a list of render ops).
            sound_cues: dict mapping local frame index to a sound file path.
                The sound is played via sounds.play_sfx() when that frame is reached.
        console: tcod console to draw on.
        context: tcod context to present.
        frame_delay: seconds between frames.

    Render ops are processed in layer order — later layers paint over earlier
    ones on the same tile, giving predictable compositing.
    """
    import sounds as _sounds

    # Normalize layers to 3-tuples and materialize frames.
    materialized = []
    for layer in layers:
        if len(layer) == 3:
            delay, frames, cues = layer
        else:
            delay, frames = layer
            cues = None
        materialized.append((delay, list(frames), cues))

    total = max(
        (delay + len(frames) for delay, frames, _cues in materialized),
        default=0,
    )

    for frame_idx in range(total):
        _begin_frame(engine, console)
        for delay, frames, cues in materialized:
            local = frame_idx - delay
            if local < 0 or local >= len(frames):
                continue
            # Fire sound cue on the first frame this layer reaches local index.
            if cues and local in cues:
                _sounds.play_sfx(cues[local])
            for op in frames[local]:
                x, y = op[0], op[1]
                if not engine.game_map.in_bounds(x, y):
                    continue
                if not engine.game_map.visible[x, y]:
                    continue
                char = op[2]
                fg = op[3]
                bg = op[4] if len(op) > 4 else None
                if char is None:
                    # Background-only op
                    if bg is not None:
                        sx, sy = engine.world_to_screen(x, y)
                        if 0 <= sx < engine.viewport_width and 0 <= sy < engine.viewport_height:
                            console.rgb[sx, sy]["bg"] = bg
                elif bg is not None:
                    engine.print_at_world(console, x, y, string=char, fg=fg, bg=bg)
                else:
                    engine.print_at_world(console, x, y, string=char, fg=fg)
        _end_frame(console, context, frame_delay)


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


# ---------------------------------------------------------------------------
# Frame generators — produce frame lists for use with composite_animations
# ---------------------------------------------------------------------------


def explosion_frames(engine, x, y, radius):
    """Generate explosion frame data: 5 frames of expanding/cooling blast."""
    chars = ["*", "x", "+", "-", "."]
    tiles = [
        (tx, ty)
        for tx in range(x - radius, x + radius + 1)
        for ty in range(y - radius, y + radius + 1)
        if (tx - x) ** 2 + (ty - y) ** 2 <= radius ** 2
        and engine.game_map.in_bounds(tx, ty)
    ]
    r = max(radius, 1)
    frames = []
    for f, char in enumerate(chars):
        frame = []
        for tx, ty in tiles:
            d = ((tx - x) ** 2 + (ty - y) ** 2) ** 0.5
            heat = 1.0 - (f / 4) * 0.7 - (d / r) * 0.3
            frame.append((tx, ty, char, _explosion_color(heat)))
        frames.append(frame)
    return frames


def projectile_frames(path, trail_color=(255, 140, 0), tip_color=(255, 255, 100)):
    """Generate projectile travel frame data: one frame per path tile."""
    frames = []
    for i, (px, py) in enumerate(path):
        frame = []
        for tx, ty in path[:i]:
            frame.append((tx, ty, ".", trail_color))
        frame.append((px, py, "*", tip_color))
        frames.append(frame)
    return frames


def sound_wave_frames(engine, player_by_dist, monster_by_dist):
    """Generate sound wave frame data from BFS distance dicts."""
    wave_color = (255, 255, 255)
    wave_char = ","
    trail_bg = (40, 40, 40)
    all_dists = set(player_by_dist) | set(monster_by_dist)
    if not all_dists:
        return []
    max_dist = max(all_dists)
    frames = []
    trail_visited = []
    for dist in range(1, max_dist + 1):
        player_ring = list(player_by_dist.get(dist, []))
        monster_ring = list(monster_by_dist.get(dist, []))
        if not player_ring and not monster_ring:
            continue
        frame = []
        # Trail: bg-only ops for previously visited player tiles
        for tx, ty in trail_visited:
            frame.append((tx, ty, None, None, trail_bg))
        # Wavefront
        for tx, ty in player_ring + monster_ring:
            frame.append((tx, ty, wave_char, wave_color, trail_bg))
        frames.append(frame)
        trail_visited.extend(player_ring)
    return frames


def animate_explosion(  # pylint: disable=too-many-arguments,too-many-positional-arguments
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
        _begin_frame(engine, console)
        for tx, ty in tiles:
            d = ((tx - x) ** 2 + (ty - y) ** 2) ** 0.5
            heat = 1.0 - (f / 4) * 0.7 - (d / r) * 0.3
            engine.print_at_world(console, tx, ty, string=char, fg=_explosion_color(heat))
        _end_frame(console, context, 0.08)


def animate_grass_growth(
    engine,
    x: int,
    y: int,
    radius: int,
    console,
    context,
) -> None:
    """Animate grass sprouting outward from (x, y) with the given radius."""
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
    for f in range(4):
        _begin_frame(engine, console)
        for tx, ty in tiles:
            d = ((tx - x) ** 2 + (ty - y) ** 2) ** 0.5
            intensity = int(80 + 150 * (1.0 - f / 3) * (1.0 - d / r * 0.5))
            intensity = max(30, min(255, intensity))
            engine.print_at_world(console, tx, ty, string=";", fg=(0, intensity, 0))
        _end_frame(console, context, 0.08)


def animate_lightning_ray(
    engine,
    path: list[tuple[int, int]],
    ray_char: str,
    console,
    context,
) -> None:
    """Animate a lightning ray growing along the given path tiles.

    The ray extends tile-by-tile, then flickers at full extension. Game state is not mutated.
    """
    trail_color = (100, 180, 255)
    tip_color = (255, 255, 255)

    visible_path = [
        (x, y) for x, y in path
        if engine.game_map.in_bounds(x, y) and engine.game_map.visible[x, y]
    ]
    if not visible_path:
        return

    # Growing animation: each frame adds one more tile
    for i in range(1, len(visible_path) + 1):
        _begin_frame(engine, console)
        for j, (tx, ty) in enumerate(visible_path[:i]):
            clr = tip_color if j == i - 1 else trail_color
            engine.print_at_world(console, tx, ty, string=ray_char, fg=clr)
        _end_frame(console, context, 0.025)

    # Flicker at full extension
    for flicker_char, clr in [
        ("*", tip_color),
        (ray_char, (160, 220, 255)),
        ("*", (255, 255, 200)),
    ]:
        _begin_frame(engine, console)
        for tx, ty in visible_path:
            engine.print_at_world(console, tx, ty, string=flicker_char, fg=clr)
        _end_frame(console, context, 0.04)


def animate_digging_ray(
    engine,
    path: list[tuple[int, int]],
    ray_char: str,
    console,
    context,
) -> None:
    """Animate a digging beam growing along the given path tiles."""
    trail_color = (160, 100, 40)
    tip_color = (220, 180, 80)

    if not path:
        return

    for i in range(1, len(path) + 1):
        _begin_frame(engine, console)
        for j, (tx, ty) in enumerate(path[:i]):
            if engine.game_map.in_bounds(tx, ty) and engine.game_map.visible[tx, ty]:
                clr = tip_color if j == i - 1 else trail_color
                engine.print_at_world(console, tx, ty, string=ray_char, fg=clr)
        _end_frame(console, context, 0.025)


def animate_sound_wave(
    engine,
    player_by_dist: dict[int, "set"],
    monster_by_dist: dict[int, "set"],
    monster_burst_locs: list,
    console,
    context,
) -> None:
    """Animate sound with three distinct modes:

    Player sounds: dark gray trail on ALL tiles (ignores FOV) + wave front on visible tiles only.
    Monster sounds (visible source): wave front on visible tiles only, no trail.
    Monster sounds (invisible source): brief spherical burst of radius 3, ignores FOV.
    """
    wave_color = (255, 255, 255)
    wave_char = ","
    trail_bg = (40, 40, 40)

    # --- Expanding wave (player + monster visible) ---
    all_dists = set(player_by_dist) | set(monster_by_dist)
    trail_visited: list[tuple[int, int]] = []
    rendered_any = False
    if all_dists:
        max_dist = max(all_dists)
        for dist in range(1, max_dist + 1):
            player_ring = list(player_by_dist.get(dist, []))
            monster_ring = list(monster_by_dist.get(dist, []))
            if not player_ring and not monster_ring:
                continue
            _begin_frame(engine, console)
            # Trail: paint dark bg on all previously visited player tiles
            for tx, ty in trail_visited:
                sx, sy = engine.world_to_screen(tx, ty)
                if 0 <= sx < engine.viewport_width and 0 <= sy < engine.viewport_height:
                    console.rgb[sx, sy]["bg"] = trail_bg
            # Wavefront: visible tiles only, from both player and monster rings
            for tx, ty in player_ring + monster_ring:
                if engine.game_map.visible[tx, ty]:
                    engine.print_at_world(console, tx, ty, string=wave_char, fg=wave_color, bg=trail_bg)
            _end_frame(console, context, 0.03)
            trail_visited.extend(player_ring)
            rendered_any = True
        if rendered_any and options.sound_wave_linger > 0:
            time.sleep(options.sound_wave_linger)
        # Erase trail
        if trail_visited:
            _begin_frame(engine, console)
            _end_frame(console, context, 0)

    # --- Burst animation for invisible monster sounds (ring-by-ring, radius 3, no trail) ---
    if monster_burst_locs:
        for dist in range(1, 5):
            _begin_frame(engine, console)
            for loc in monster_burst_locs:
                for dx in range(-dist, dist + 1):
                    for dy in range(-dist, dist + 1):
                        d2 = dx * dx + dy * dy
                        if (dist - 1) * (dist - 1) < d2 <= dist * dist:
                            tx, ty = loc.x + dx, loc.y + dy
                            if engine.game_map.in_bounds(tx, ty):
                                engine.print_at_world(console, tx, ty, string=wave_char, fg=wave_color)
            _end_frame(console, context, 0.025)
        time.sleep(0.05)
        _begin_frame(engine, console)
        _end_frame(console, context, 0)


def animate_fireball_projectile(
    engine,
    path: list[tuple[int, int]],
    impact_x: int,
    impact_y: int,
    radius: int,
    console,
    context,
) -> None:
    """Animate fireball projectile travel followed by explosion, using the compositor."""
    import sounds as _sounds  # pylint: disable=import-outside-toplevel
    proj = projectile_frames(path)
    expl = explosion_frames(engine, impact_x, impact_y, radius)
    layers = [
        (0, proj),                # projectile travels first
        (len(proj), expl, {0: _sounds.Sfx.FIREBALL_EXPLOSION}),
    ]
    composite_animations(engine, layers, console, context, frame_delay=0.04)



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
        _begin_frame(engine, console)
        engine.print_at_world(console, x, y, string=char, fg=fg)
        _end_frame(console, context, frame_delay)
