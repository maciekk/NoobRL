from typing import Tuple

import numpy as np  # type: ignore

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
    """Helper function for defining individual tile types """
    return np.array((walkable, transparent, dark, revealed, light), dtype=tile_dt)


# SHROUD represents unexplored, unseen tiles
SHROUD = np.array((ord(" "), (255, 255, 255), (0, 0, 0)), dtype=graphic_dt)

floor = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord("."), (64, 64, 64), (0,0,0)),
    revealed=(ord("."), (20, 20, 20), (0, 0, 0)),
    light=(ord("."), (255, 255, 0), (32,32,0)),
)
wall = new_tile(
    walkable=False,
    transparent=False,
    dark=(ord("#"), (32,32,32), (50, 50, 100)),
    revealed=(ord("#"), (10, 10, 10), (15, 15, 30)),
    light=(ord("#"), (128,128,0), (64, 64, 32)),
)
down_stairs = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord(">"), (64, 64, 64), (0, 0, 0)),
    revealed=(ord(">"), (20, 20, 20), (0, 0, 0)),
    light=(ord(">"), (255, 255, 0), (32, 32, 0)),
)
up_stairs = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord("<"), (64, 64, 64), (0, 0, 0)),
    revealed=(ord("<"), (20, 20, 20), (0, 0, 0)),
    light=(ord("<"), (255, 255, 0), (32, 32, 0)),
)

# Tiles that should cause careful movement to stop when stepped on.
interesting_tiles = [down_stairs, up_stairs]
