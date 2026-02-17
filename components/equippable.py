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
    ):
        self.equipment_type = equipment_type

        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus

    def on_equip(self) -> None:
        """Called when this equippable is equipped; can be overridden for special effects."""
        pass

    def on_unequip(self) -> None:
        """Called when this equippable is unequipped; can be overridden to reverse effects."""
        pass


class Dagger(Equippable):
    """A basic dagger with +2 power bonus."""
    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.WEAPON, power_bonus=2)


class Sword(Equippable):
    """A standard sword with +4 power bonus."""

    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.WEAPON, power_bonus=4)


class LongSword(Equippable):
    """A powerful sword with +6 power bonus."""

    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.WEAPON, power_bonus=6)


class Odachi(Equippable):
    """A legendary sword with +9 power bonus."""

    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.WEAPON, power_bonus=9)


class LeatherArmor(Equippable):
    """Basic leather armor with +1 defense bonus."""

    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.ARMOR, defense_bonus=1)


class ChainMail(Equippable):
    """Moderate armor with +3 defense bonus."""

    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.ARMOR, defense_bonus=3)


class SteelArmor(Equippable):
    """Heavy armor with +5 defense bonus."""

    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.ARMOR, defense_bonus=5)


class AmuletOfClairvoyance(Equippable):
    """An amulet that reveals the dungeon layout when equipped."""

    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.AMULET)

    def on_equip(self) -> None:
        from components.consumable import apply_clairvoyance

        apply_clairvoyance(self.engine)


class Dart(Equippable):
    """A thrown weapon with +4 power bonus."""

    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.THROWN, power_bonus=4)


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
