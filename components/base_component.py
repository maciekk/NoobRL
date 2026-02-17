"""Base class for all entity components providing access to the game world."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity
    from game_map import GameMap


class BaseComponent:
    """Base component providing parent reference and property access up the entity chain."""
    parent: Entity  # Owning entity instance.

    @property
    def gamemap(self) -> GameMap:
        """Get the game map from the parent entity chain."""
        return self.parent.gamemap

    @property
    def engine(self) -> Engine:
        """Get the engine from the parent entity chain."""
        return self.gamemap.engine
