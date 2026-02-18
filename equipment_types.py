"""Equipment slot categories for the item system."""
from enum import auto, Enum


class EquipmentType(Enum):
    """Equipment slot identifier for weapons, armor, amulets, and thrown items."""
    WEAPON = auto()
    ARMOR = auto()
    AMULET = auto()
    THROWN = auto()
