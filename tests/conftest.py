"""Mock tcod and pygame before any game module is imported.

Placed at module level so it runs during pytest collection, before any
test file imports game code.
"""
import sys
from unittest.mock import MagicMock

_MOCK_MODULES = [
    "tcod",
    "tcod.console",
    "tcod.constants",
    "tcod.event",
    "tcod.libtcodpy",
    "tcod.los",
    "tcod.map",
    "pygame",
    "pygame.mixer",
]
for _mod in _MOCK_MODULES:
    sys.modules[_mod] = MagicMock()
