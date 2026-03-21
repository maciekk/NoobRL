"""Tile type definitions and NumPy dtypes for the game map."""
import json
import os
from typing import Tuple

import numpy as np  # type: ignore  # pylint: disable=import-error

# Tile graphics structured type compatible with Console.tiles_rgb.
graphic_dt = np.dtype(
    [
        ("ch", np.int32),  # Unicode codepoint.
        ("fg", "3B"),  # 3 unsigned bytes, for RGB colors.
        ("bg", "3B"),
    ]
)

# Tile struct used for statically defined tile data.
tile_dt = np.dtype(
    [
        ("walkable", np.bool),  # True if this tile can be walked over.
        ("transparent", np.bool),  # True if this tile doesn't block FOV.
        ("dark", graphic_dt),  # Graphics for when this tile is not in FOV.
        ("revealed", graphic_dt),  # Graphics for clairvoyance-revealed tiles.
        ("light", graphic_dt),  # Graphics for when the tile is in FOV.
    ]
)


def new_tile(
    *,  # Enforce the use of keywords, so that parameter order doesn't matter.
    walkable: int,
    transparent: int,
    dark: Tuple[int, Tuple[int, int, int], Tuple[int, int, int]],
    revealed: Tuple[int, Tuple[int, int, int], Tuple[int, int, int]],
    light: Tuple[int, Tuple[int, int, int], Tuple[int, int, int]],
) -> np.ndarray:
    """Helper function for defining individual tile types"""
    return np.array((walkable, transparent, dark, revealed, light), dtype=tile_dt)


def _parse_graphic(raw):
    """Convert a JSON graphic entry [char, [r,g,b], [r,g,b]] to new_tile args."""
    return (ord(raw[0]), tuple(raw[1]), tuple(raw[2]))


def _load_tiles():
    """Load tile definitions from data/tiles.json."""
    data_path = os.path.join(os.path.dirname(__file__), "data", "tiles.json")
    with open(data_path) as f:
        entries = json.load(f)

    tiles = {}
    for entry in entries:
        tile = new_tile(
            walkable=entry["walkable"],
            transparent=entry["transparent"],
            dark=_parse_graphic(entry["dark"]),
            revealed=_parse_graphic(entry["revealed"]),
            light=_parse_graphic(entry["light"]),
        )
        tiles[entry["id"]] = tile
    return tiles


# SHROUD represents unexplored, unseen tiles
SHROUD = np.array((ord(" "), (255, 255, 255), (0, 0, 0)), dtype=graphic_dt)

# OUT_OF_BOUNDS represents areas beyond the map edge
OUT_OF_BOUNDS = np.array((ord("X"), (20, 20, 20), (0, 0, 0)), dtype=graphic_dt)

_tiles = _load_tiles()

TILE_FLOOR = _tiles["floor"]
TILE_WALL = _tiles["wall"]
TILE_DOWN_STAIRS = _tiles["down_stairs"]
TILE_UP_STAIRS = _tiles["up_stairs"]
TILE_DOOR_CLOSED = _tiles["door_closed"]
TILE_DOOR_OPEN = _tiles["door_open"]
TILE_TALL_GRASS = _tiles["tall_grass"]

# Tiles that should cause careful movement to stop when stepped on.
INTERESTING_TILES = [TILE_DOWN_STAIRS, TILE_UP_STAIRS, TILE_DOOR_CLOSED, TILE_DOOR_OPEN, TILE_TALL_GRASS]
