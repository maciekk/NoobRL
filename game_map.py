from __future__ import annotations

from typing import Iterable, Iterator, Optional, TYPE_CHECKING

import numpy as np  # type: ignore
from tcod.console import Console

from entity import Actor, Chest, Item
import tile_types

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity


class GameMap:
    def __init__(
        self, engine: Engine, width: int, height: int, entities: Iterable[Entity] = ()
    ):
        self.engine = engine
        self.width, self.height = width, height
        self.entities = set(entities)
        self.tiles = np.full((width, height), fill_value=tile_types.wall, order="F")

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
        return self

    @property
    def actors(self) -> Iterator[Actor]:
        """Iterate over this maps living actors."""
        yield from (
            entity
            for entity in self.entities
            if isinstance(entity, Actor) and entity.is_alive
        )

    @property
    def items(self) -> Iterator[Item]:
        yield from (entity for entity in self.entities if isinstance(entity, Item))

    def any_monsters_visible(self):
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
        for entity in self.entities:
            if (
                entity.blocks_movement
                and entity.x == location_x
                and entity.y == location_y
            ):
                return entity

        return None

    def get_actor_at_location(self, x: int, y: int) -> Optional[Actor]:
        for actor in self.actors:
            if actor.x == x and actor.y == y:
                return actor

        return None

    def in_bounds(self, x: int, y: int) -> bool:
        """Return True if x and y are inside of the bounds of this map."""
        return 0 <= x < self.width and 0 <= y < self.height

    def render(self, console: Console) -> None:
        """
        Renders the map.
        If a tile is in the "visible" array, then draw it with the "light" colors.
        If it isn't, but it's in the "explored" array, then draw it with the "dark" colors.
        Otherwise, the default is "SHROUD".
        """
        console.rgb[0 : self.width, 0 : self.height] = np.select(
            condlist=[self.visible, self.explored, self.revealed],
            choicelist=[
                self.tiles["light"],
                self.tiles["dark"],
                self.tiles["revealed"],
            ],
            default=tile_types.SHROUD,
        )

        entities_sorted_for_rendering = sorted(
            self.entities, key=lambda x: x.render_order.value
        )

        # Track tiles with multiple items for pile display
        item_counts: dict[tuple[int, int], int] = {}
        for entity in self.entities:
            if isinstance(entity, Item) and self.visible[entity.x, entity.y]:
                pos = (entity.x, entity.y)
                item_counts[pos] = item_counts.get(pos, 0) + 1

        for entity in entities_sorted_for_rendering:
            if self.visible[entity.x, entity.y]:
                fg = entity.color
                if entity is self.engine.player and entity.is_invisible:
                    fg = (100, 100, 100)
                console.print(x=entity.x, y=entity.y, string=entity.char, fg=fg)

        # Draw pile symbol on top of tiles with 2+ items (but not if an actor is there)
        for (x, y), count in item_counts.items():
            if count >= 2 and self.get_actor_at_location(x, y) is None:
                console.print(x=x, y=y, string="&", fg=(255, 255, 255))


class GameWorld:
    """
    Holds the settings for the GameMap, and generates new maps when moving down the stairs.
    """

    def __init__(
        self,
        *,
        engine: Engine,
        map_width: int,
        map_height: int,
        max_rooms: int,
        room_min_size: int,
        room_max_size: int,
        current_floor: int = 0,
    ):
        self.engine = engine

        self.map_width = map_width
        self.map_height = map_height

        self.max_rooms = max_rooms

        self.room_min_size = room_min_size
        self.room_max_size = room_max_size

        self.current_floor = current_floor

    def generate_floor(self, direction: int = 1) -> None:
        from procgen import generate_dungeon

        self.current_floor += direction

        self.engine.game_map = generate_dungeon(
            max_rooms=self.max_rooms,
            room_min_size=self.room_min_size,
            room_max_size=self.room_max_size,
            map_width=self.map_width,
            map_height=self.map_height,
            engine=self.engine,
            ascending=direction < 0,
        )

        from components.equippable import AmuletOfClairvoyance

        amulet = self.engine.player.equipment.amulet
        if amulet and isinstance(amulet.equippable, AmuletOfClairvoyance):
            from components.consumable import apply_clairvoyance

            apply_clairvoyance(self.engine)
