"""Manages the dungeon map grid, entities, and field-of-view state for a single floor."""
# pylint: disable=cyclic-import

from __future__ import annotations

from typing import Iterable, Iterator, Optional, TYPE_CHECKING

import numpy as np  # type: ignore[import]  # pylint: disable=import-error
from tcod.console import Console  # pylint: disable=import-error

from entity import Actor, Item
from location import Location
from tile_types import OUT_OF_BOUNDS, SHROUD, TILE_FLOOR, TILE_TALL_GRASS, TILE_WALL

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity


class GameMap:  # pylint: disable=too-many-instance-attributes
    """Represents a single dungeon floor with tile data, entities, and visibility state."""
    def __init__(
        self, engine: Engine, width: int, height: int, entities: Iterable[Entity] = ()
    ):
        self.engine = engine
        self.width, self.height = width, height
        self.entities = set(entities)
        self.tiles = np.full((width, height), fill_value=TILE_WALL, order="F")

        self.visible = np.full(
            (width, height), fill_value=False, order="F"
        )  # Tiles the player can currently see
        self.explored = np.full(
            (width, height), fill_value=False, order="F"
        )  # Tiles the player has seen before
        self.revealed = np.full(
            (width, height), fill_value=False, order="F"
        )  # Tiles revealed by clairvoyance but not yet visited
        self.downstairs_location = (0, 0)
        self.upstairs_location = (0, 0)
        self.secret_doors: set[tuple[int, int]] = set()

    def __getattr__(self, name: str):
        # Backward-compat for saves created before secret_doors existed.
        if name == "secret_doors":
            self.secret_doors: set[tuple[int, int]] = set()
            return self.secret_doors
        raise AttributeError(name)

    @property
    def gamemap(self) -> GameMap:
        """Returns self (for compatibility with component access chain)."""
        return self

    @property
    def actors(self) -> Iterator[Actor]:
        """Iterate over living actors on this map."""
        yield from (
            entity
            for entity in self.entities
            if isinstance(entity, Actor) and entity.is_alive
        )

    @property
    def items(self) -> Iterator[Item]:
        """Iterate over all items on this map."""
        yield from (entity for entity in self.entities if isinstance(entity, Item))

    def any_monsters_visible(self) -> bool:
        """Check if any non-player monsters are currently visible."""
        for a in self.actors:
            if a == self.engine.player:
                continue
            if self.visible[a.x, a.y]:
                return True
        return False

    def get_blocking_entity_at_location(
        self,
        location_x: int,
        location_y: int,
    ) -> Optional[Entity]:
        """Return the blocking entity at a location, or None if empty."""
        for entity in self.entities:
            if (
                entity.blocks_movement
                and entity.x == location_x
                and entity.y == location_y
            ):
                return entity

        return None

    def get_actor_at_location(self, x: int, y: int) -> Optional[Actor]:
        """Return the living actor at a location, or None if empty."""
        for actor in self.actors:
            if actor.x == x and actor.y == y:
                return actor

        return None

    def is_visible(self, loc: Location) -> bool:
        """Return True if the given location is within the player's current FOV."""
        return self.visible[loc.x, loc.y]

    def in_bounds(self, x: int, y: int) -> bool:
        """Return True if x and y are inside of the bounds of this map."""
        return 0 <= x < self.width and 0 <= y < self.height

    def render(self, console: Console) -> None:
        """Render the map viewport to the console using visibility, exploration, and clairvoyance states."""
        engine = self.engine
        cx, cy = engine.camera_x, engine.camera_y
        vp_w, vp_h = engine.viewport_width, engine.viewport_height

        # Map slice bounds — clamp to valid map indices
        mx1 = max(0, cx)
        my1 = max(0, cy)
        mx2 = min(self.width, cx + vp_w)
        my2 = min(self.height, cy + vp_h)
        # Console destination offset (non-zero when camera is past map edge)
        dx, dy = mx1 - cx, my1 - cy

        # Fill entire viewport with OUT_OF_BOUNDS first, then paint the map slice on top
        console.rgb[0:vp_w, 0:vp_h] = OUT_OF_BOUNDS
        if mx2 > mx1 and my2 > my1:
            sw, sh = mx2 - mx1, my2 - my1
            console.rgb[dx:dx + sw, dy:dy + sh] = np.select(
                condlist=[self.visible[mx1:mx2, my1:my2], self.explored[mx1:mx2, my1:my2], self.revealed[mx1:mx2, my1:my2]],
                choicelist=[self.tiles["light"][mx1:mx2, my1:my2], self.tiles["dark"][mx1:mx2, my1:my2], self.tiles["revealed"][mx1:mx2, my1:my2]],
                default=SHROUD,
            )

        # Track tiles with multiple items for pile display
        item_counts: dict[tuple[int, int], int] = {}
        for entity in self.entities:
            if isinstance(entity, Item) and self.visible[entity.x, entity.y]:
                pos = (entity.x, entity.y)
                item_counts[pos] = item_counts.get(pos, 0) + 1

        for entity in sorted(self.entities, key=lambda x: x.render_order.value):
            sx, sy = engine.world_to_screen(entity.x, entity.y)
            if not (0 <= sx < vp_w and 0 <= sy < vp_h):
                continue
            # Render if visible, or if detecting monsters and entity is a non-player Actor
            should_render = self.visible[entity.x, entity.y]
            if (
                not should_render
                and engine.player.is_detecting_monsters
                and isinstance(entity, Actor)
                and entity is not engine.player
            ):
                should_render = True

            detecting_this_trap = (
                engine.player.is_detecting_traps
                and hasattr(entity, "trap_type")
            )
            if should_render and not (
                hasattr(entity, "is_revealed") and not entity.is_revealed
                and not detecting_this_trap
            ):
                fg = entity.display_color if isinstance(entity, Item) else entity.color
                if entity is engine.player and entity.is_invisible:
                    fg = (100, 100, 100)
                console.print(x=sx, y=sy, string=entity.char, fg=fg)

        # Draw pile symbol on top of tiles with 2+ items (but not if an actor is there)
        for (wx, wy), count in item_counts.items():
            if count >= 2 and self.get_actor_at_location(wx, wy) is None:
                engine.print_at_world(console, wx, wy, string="&", fg=(255, 255, 255))


class GameWorld:  # pylint: disable=too-few-public-methods
    """
    Holds the settings for the GameMap, and generates new maps when moving down the stairs.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        engine: Engine,
        map_width: int,
        map_height: int,
        max_room_attempts: int,
        room_min_size: int,
        room_max_size: int,
        current_floor: int = 0,
    ):
        self.engine = engine

        self.map_width = map_width
        self.map_height = map_height

        self.max_room_attempts = max_room_attempts

        self.room_min_size = room_min_size
        self.room_max_size = room_max_size

        self.current_floor = current_floor

    def generate_floor(self, direction: int = 1, trapdoor: bool = False) -> None:
        """Generate a new dungeon floor and apply any persistent map effects."""
        from procgen import generate_dungeon  # pylint: disable=import-outside-toplevel

        self.current_floor += direction

        self.engine.game_map = generate_dungeon(
            max_room_attempts=self.max_room_attempts,
            room_min_size=self.room_min_size,
            room_max_size=self.room_max_size,
            map_width=self.map_width,
            map_height=self.map_height,
            engine=self.engine,
            ascending=direction < 0,
            trapdoor=trapdoor,
        )

        equipment = self.engine.player.equipment
        for item in (equipment.weapon, equipment.armor, equipment.amulet):
            if item is not None:
                item.equippable.on_floor_change()


def apply_explosion(
    engine: "Engine",
    x: int,
    y: int,
    radius: int,
    damage: int,
    exclude=None,
    hit_message=None,
    hit_color=None,
    animate=True,
) -> tuple:
    """Apply an explosion at (x, y): animate, damage actors, clear tall grass.

    exclude: collection of actors to skip (e.g. the exploding entity itself).
    hit_message: callable(actor_name: str) -> str for per-actor log messages.
    hit_color: color for hit messages (defaults to white).
    animate: if False, skip the built-in explosion animation (caller handles it).

    Returns (actors_hit: int, grass_burned: int).
    """
    import input_handlers as _ih  # pylint: disable=import-outside-toplevel
    if animate and _ih.context is not None and _ih.root_console is not None:
        from render_functions import animate_explosion  # pylint: disable=import-outside-toplevel
        animate_explosion(engine, x, y, radius, _ih.root_console, _ih.context)

    import color as _color  # pylint: disable=import-outside-toplevel
    if hit_color is None:
        hit_color = _color.white
    exclude = set(exclude) if exclude else set()

    game_map = engine.game_map
    actors_hit = 0
    for actor in list(game_map.actors):
        if actor in exclude:
            continue
        if actor.distance(x, y) <= radius:
            if hit_message is not None:
                engine.message_log.add_message(hit_message(actor.name), hit_color)
            actor.fighter.take_damage(damage)
            actors_hit += 1

    grass_burned = 0
    for tx in range(x - radius, x + radius + 1):
        for ty in range(y - radius, y + radius + 1):
            if (tx - x) ** 2 + (ty - y) ** 2 <= radius ** 2:
                if game_map.in_bounds(tx, ty) and game_map.tiles[tx, ty] == TILE_TALL_GRASS:
                    game_map.tiles[tx, ty] = TILE_FLOOR
                    grass_burned += 1

    return actors_hit, grass_burned
