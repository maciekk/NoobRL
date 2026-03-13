"""Component that makes items equippable with stat bonuses and hooks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from components.base_component import BaseComponent
from equipment_types import EquipmentType

if TYPE_CHECKING:
    from entity import Item


class Equippable(BaseComponent):
    """Makes an item equippable with power/defense bonuses and equip/unequip hooks."""
    parent: Item

    def __init__(
        self,
        equipment_type: EquipmentType,
        power_bonus: int = 0,
        defense_bonus: int = 0,
        damage_dice: str = "",
    ):
        self.equipment_type = equipment_type

        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus
        self.damage_dice = damage_dice

    def on_equip(self) -> None:
        """Called when this equippable is equipped; can be overridden for special effects."""

    def on_unequip(self) -> None:
        """Called when this equippable is unequipped; can be overridden to reverse effects."""


class AmuletOfClairvoyance(Equippable):
    """An amulet that reveals the dungeon layout when equipped."""

    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.AMULET)

    def on_equip(self) -> None:
        from components.consumable import apply_clairvoyance  # pylint: disable=import-outside-toplevel

        apply_clairvoyance(self.engine)


class AmuletOfDetectMonster(Equippable):
    """An amulet that reveals all monsters while equipped."""

    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.AMULET)

    def on_equip(self) -> None:
        # self.parent = Item, Item.parent = Inventory, Inventory.parent = Actor
        actor = self.parent.parent.parent
        actor.is_detecting_monsters = True
        self.engine.message_log.add_message(
            "You sense the presence of monsters!",
            (0xC0, 0xC0, 0xFF),
        )

    def on_unequip(self) -> None:
        # self.parent = Item, Item.parent = Inventory, Inventory.parent = Actor
        actor = self.parent.parent.parent
        actor.is_detecting_monsters = False
        self.engine.message_log.add_message(
            "Your monster sense fades.",
            (0x80, 0x80, 0x80),
        )
