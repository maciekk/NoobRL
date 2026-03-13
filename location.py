"""Location NamedTuple for 2D grid coordinates."""
from typing import NamedTuple


class Location(NamedTuple):
    """A 2D tile coordinate within the dungeon map."""

    x: int
    y: int

    def chebyshev_distance(self, other: "Location") -> int:
        """Return the Chebyshev (8-directional) distance to another location."""
        return max(abs(self.x - other.x), abs(self.y - other.y))
