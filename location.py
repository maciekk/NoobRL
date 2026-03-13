"""Location NamedTuple for 2D grid coordinates."""
from typing import NamedTuple


class Location(NamedTuple):
    """A 2D tile coordinate within the dungeon map."""

    x: int
    y: int
