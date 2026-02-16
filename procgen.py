from __future__ import annotations

import random
from typing import Dict, Iterator, List, Tuple, TYPE_CHECKING

import tcod, string

from game_map import GameMap
import tile_types


if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity

max_items_by_floor = [
    (1, 1),
    (4, 2),
]

max_monsters_by_floor = [
    (1, 2),
    (4, 3),
    (6, 5),
]

item_chances: Dict[int, List[Tuple[string, int]]] = {
    0: [('p_heal', 35)],
    2: [('s_confusion', 10)],
    3: [('s_blink', 15), ('p_damage', 1), ('p_invisibility', 5), ('p_speed', 5)],
    4: [('s_lightning', 25), ('sword', 5), ('p_clairvoyance', 5)],
    5: [('sword', 3), ('long_sword', 3), ('odachi', 2), ('p_damage', 3)],
    6: [('s_fireball', 25), ('chain_mail', 15), ('steel_armor', 5), ('wand_wishing', 1)],
    7: [('odachi', 4)],
    8: [('steel_armor', 10), ("p_damage", 6)],
}

enemy_chances: Dict[int, List[Tuple[string, int]]] = {
    0: [('orc', 80)],
    2: [('crawler', 20)],
    3: [('troll', 5)],
    5: [('troll', 15), ('crawler', 35)],
    6: [('wizard', 8), ('troll', 20)],
    7: [('troll', 60), ('dragon', 1), ('ender_dragon', 1), ('hydra', 1), ('wizard', 12)],
    10: [('troll', 65), ('dragon', 2), ('ender_dragon', 2), ('hydra', 2)],
}

def get_max_value_for_floor(
    max_value_by_floor: List[Tuple[int, int]], floor: int
) -> int:
    current_value = 0

    for floor_minimum, value in max_value_by_floor:
        if floor_minimum > floor:
            break
        else:
            current_value = value

    return current_value

def get_entities_at_random(
    engine: Engine,
    weighted_chances_by_floor: Dict[int, List[Tuple[string, int]]],
    number_of_entities: int,
    floor: int,
) -> List[Entity]:
    entity_weighted_chances = {}

    for key, values in weighted_chances_by_floor.items():
        if key > floor:
            break
        else:
            for value in values:
                id = value[0]
                entity = engine.item_manager.items.get(id)
                if entity is None:
                    entity = engine.monster_manager.monsters.get(id)
                weighted_chance = value[1]
                entity_weighted_chances[entity] = weighted_chance

    entities = list(entity_weighted_chances.keys())
    entity_weighted_chance_values = list(entity_weighted_chances.values())

    chosen_entities = random.choices(
        entities, weights=entity_weighted_chance_values, k=number_of_entities
    )

    return chosen_entities


class RectangularRoom:
    def __init__(self, x: int, y: int, width: int, height: int):
        self.x1 = x
        self.y1 = y
        self.x2 = x + width
        self.y2 = y + height

    @property
    def center(self) -> Tuple[int, int]:
        center_x = int((self.x1 + self.x2) / 2)
        center_y = int((self.y1 + self.y2) / 2)

        return center_x, center_y

    @property
    def inner(self) -> Tuple[slice, slice]:
        """Return the inner area of this room as a 2D array index."""
        return slice(self.x1 + 1, self.x2), slice(self.y1 + 1, self.y2)

    def intersects(self, other: RectangularRoom) -> bool:
        """Return True if this room overlaps with another RectangularRoom."""
        return (
            self.x1 <= other.x2
            and self.x2 >= other.x1
            and self.y1 <= other.y2
            and self.y2 >= other.y1
        )


def place_entities(room: RectangularRoom, dungeon: GameMap, floor_number: int,) -> None:
    number_of_monsters = random.randint(
        0, get_max_value_for_floor(max_monsters_by_floor, floor_number)
    )
    number_of_items = random.randint(
        0, get_max_value_for_floor(max_items_by_floor, floor_number)
    )

    monsters: List[Entity] = get_entities_at_random(
        dungeon.engine, enemy_chances, number_of_monsters, floor_number
    )
    items: List[Entity] = get_entities_at_random(
        dungeon.engine, item_chances, number_of_items, floor_number
    )


    for entity in monsters + items:
        if entity is None:
            print(f"WARNING: None entity in spawn list (floor {floor_number}, room at {room.x1},{room.y1})")
            continue
        x = random.randint(room.x1 + 1, room.x2 - 1)
        y = random.randint(room.y1 + 1, room.y2 - 1)

        if not any(entity.x == x and entity.y == y for entity in dungeon.entities):
            if entity is None:
                print(f"WARNING: None entity in dungeon (floor {floor_number}, room at {room.x1},{room.y1})")
                continue
            entity.spawn(dungeon, x, y)

    # 10% chance to place a chest in the room.
    if random.random() < 0.10:
        from entity import Chest
        x = random.randint(room.x1 + 1, room.x2 - 1)
        y = random.randint(room.y1 + 1, room.y2 - 1)
        if not any(e.x == x and e.y == y for e in dungeon.entities):
            Chest().spawn(dungeon, x, y)


def tunnel_between(
    start: Tuple[int, int], end: Tuple[int, int]
) -> Iterator[Tuple[int, int]]:
    """Return an L-shaped tunnel between these two points."""
    x1, y1 = start
    x2, y2 = end
    if random.random() < 0.5:  # 50% chance.
        # Move horizontally, then vertically.
        corner_x, corner_y = x2, y1
    else:
        # Move vertically, then horizontally.
        corner_x, corner_y = x1, y2

    # Generate the coordinates for this tunnel.
    for x, y in tcod.los.bresenham((x1, y1), (corner_x, corner_y)).tolist():
        yield x, y
    for x, y in tcod.los.bresenham((corner_x, corner_y), (x2, y2)).tolist():
        yield x, y


def _would_create_wide_corridor(tiles, x, y, planned_floor=None):
    """Check if setting (x, y) to floor would complete any 2x2 block of walkable tiles.

    planned_floor: optional set of (x, y) coords to treat as walkable even if
    they aren't yet (i.e. other tiles in the same tunnel being carved).
    """
    w, h = tiles.shape
    for dx, dy in [(0, 0), (-1, 0), (0, -1), (-1, -1)]:
        bx, by = x + dx, y + dy
        if bx < 0 or by < 0 or bx + 2 > w or by + 2 > h:
            continue
        all_floor = True
        for cx in range(bx, bx + 2):
            for cy in range(by, by + 2):
                if cx == x and cy == y:
                    continue
                if not tiles["walkable"][cx, cy]:
                    if planned_floor is None or (cx, cy) not in planned_floor:
                        all_floor = False
                        break
            if not all_floor:
                break
        if all_floor:
            return True
    return False


def find_door_locations(dungeon: GameMap, room_tiles: set) -> List[Tuple[int, int]]:
    """Find corridor-room junctions where doors can be placed.

    A junction is a corridor tile where:
    - Is NOT part of a room (it's a corridor)
    - Is cardinally adjacent to exactly ONE or TWO room tiles in a line
    - Not surrounded by room tiles (which would mean it's running parallel)
    - Only considers orthogonal (cardinal) adjacency, not diagonal
    """
    door_locations = []
    width, height = dungeon.width, dungeon.height

    for x in range(width):
        for y in range(height):
            # Skip if not walkable or is a room tile
            if not dungeon.tiles["walkable"][x, y] or (x, y) in room_tiles:
                continue

            # Count adjacent room tiles in each cardinal direction
            directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]  # N, S, W, E
            room_neighbors = []
            for i, (dx, dy) in enumerate(directions):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    if (nx, ny) in room_tiles:
                        room_neighbors.append(i)

            # Valid junction: adjacent to room in exactly one direction
            # (N or S, or W or E, but not multiple perpendicular directions)
            if len(room_neighbors) == 0:
                continue

            # Check if room neighbors are in opposite directions (0-1 are N-S, 2-3 are W-E)
            # or the same direction - this is good (entering room)
            # But if they're perpendicular, we're running along the room edge - skip
            if len(room_neighbors) == 1:
                # Single room neighbor - this is a valid entrance
                door_locations.append((x, y))
            elif len(room_neighbors) == 2:
                # Two room neighbors - only valid if they're in opposite directions
                # (forming a straight line through the junction)
                if (room_neighbors == [0, 1]) or (room_neighbors == [2, 3]):
                    door_locations.append((x, y))
                # Otherwise skip (perpendicular = running along edge)

    return door_locations


def place_doors(dungeon: GameMap, door_locations: List[Tuple[int, int]]) -> None:
    """Place doors at junction locations.

    20% no door, 50% open door, 30% closed door.
    """
    for x, y in door_locations:
        roll = random.random()
        if roll < 0.20:
            # No door
            pass
        elif roll < 0.70:  # 0.20 + 0.50
            # Open door
            dungeon.tiles[x, y] = tile_types.door_open
        else:
            # Closed door
            dungeon.tiles[x, y] = tile_types.door_closed


def generate_dungeon(
    max_rooms: int,
    room_min_size: int,
    room_max_size: int,
    map_width: int,
    map_height: int,
    engine: Engine,
    ascending: bool = False,
) -> GameMap:
    """Generate a new dungeon map."""
    player = engine.player
    dungeon = GameMap(engine, map_width, map_height, entities=[player])

    rooms: List[RectangularRoom] = []
    room_tiles: set = set()  # Track which tiles are part of rooms

    center_of_last_room = (0, 0)
    center_of_first_room = (0, 0)

    for r in range(max_rooms):
        room_width = random.randint(room_min_size, room_max_size)
        room_height = random.randint(room_min_size, room_max_size)

        x = random.randint(0, dungeon.width - room_width - 1)
        y = random.randint(0, dungeon.height - room_height - 1)

        # "RectangularRoom" class makes rectangles easier to work with
        new_room = RectangularRoom(x, y, room_width, room_height)

        # Run through the other rooms and see if they intersect with this one.
        if any(new_room.intersects(other_room) for other_room in rooms):
            continue  # This room intersects, so go to the next attempt.
        # If there are no intersections then the room is valid.

        # Dig out this rooms inner area.
        dungeon.tiles[new_room.inner] = tile_types.floor

        # Track room tiles for door placement
        for x in range(new_room.x1 + 1, new_room.x2):
            for y in range(new_room.y1 + 1, new_room.y2):
                room_tiles.add((x, y))

        if len(rooms) == 0:
            # The first room, where the player starts.
            player.place(*new_room.center, dungeon)
            center_of_first_room = new_room.center
        else:  # All rooms after the first.
            # Dig out a tunnel between this room and the previous one.
            # Collect new tunnel tiles, then check for 2-wide corridors
            # considering the full planned tunnel (prevents comb artifacts).
            tunnel_tiles = []
            for x, y in tunnel_between(rooms[-1].center, new_room.center):
                if not dungeon.tiles["walkable"][x, y]:
                    tunnel_tiles.append((x, y))
            tunnel_set = set(tunnel_tiles)
            for x, y in tunnel_tiles:
                if _would_create_wide_corridor(dungeon.tiles, x, y, tunnel_set):
                    continue
                dungeon.tiles[x, y] = tile_types.floor
            center_of_last_room = new_room.center

        place_entities(new_room, dungeon, engine.game_world.current_floor)

        # Finally, append the new room to the list.
        rooms.append(new_room)

    # Place staircases after all rooms and tunnels are dug.
    if ascending:
        # Came from below: downstairs at spawn only, upstairs at far end.
        dungeon.tiles[center_of_first_room] = tile_types.down_stairs
        dungeon.downstairs_location = center_of_first_room
        if engine.game_world.current_floor > 1:
            dungeon.tiles[center_of_last_room] = tile_types.up_stairs
            dungeon.upstairs_location = center_of_last_room
    else:
        # Came from above (or initial): downstairs at far end, upstairs at spawn.
        dungeon.tiles[center_of_last_room] = tile_types.down_stairs
        dungeon.downstairs_location = center_of_last_room
        if engine.game_world.current_floor > 1:
            dungeon.tiles[center_of_first_room] = tile_types.up_stairs
            dungeon.upstairs_location = center_of_first_room

    # Place doors at corridor-room junctions.
    door_locations = find_door_locations(dungeon, room_tiles)
    place_doors(dungeon, door_locations)

    return dungeon
