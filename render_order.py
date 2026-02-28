"""Rendering priority order for entities drawn on the map."""
from enum import auto, Enum


class RenderOrder(Enum):
    """Entity render priority: higher values are drawn on top."""

    CORPSE = auto()
    ITEM = auto()
    ACTOR = auto()
