"""Component that makes items equippable with stat bonuses and hooks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from components.base_component import BaseComponent
from components.consumable import apply_clairvoyance
from equipment_types import EquipmentType
import enchantment_data

if TYPE_CHECKING:
    from entity import Actor, Item


def _flag_effect(attr: str):
    """Return an (on_equip, on_unequip) pair that toggles a boolean Actor flag."""
    def equip(eq: Equippable) -> None:
        setattr(eq.actor, attr, True)
    def unequip(eq: Equippable) -> None:
        setattr(eq.actor, attr, False)
    return equip, unequip


# Maps effect id -> (on_equip_fn, on_unequip_fn, on_floor_change_fn).
# Any element can be None.
_EFFECT_REGISTRY = {
    "clairvoyance": (lambda eq: apply_clairvoyance(eq.engine), None, lambda eq: apply_clairvoyance(eq.engine)),
    "detect_monster": (*_flag_effect("is_detecting_monsters"), None),
    "detect_item": (*_flag_effect("is_detecting_items"), None),
    "trap_detection": (*_flag_effect("is_detecting_traps"), None),
}


class Equippable(BaseComponent):
    """Makes an item equippable with power/defense bonuses and equip/unequip hooks."""
    parent: Item

    def __init__(
        self,
        equipment_type: EquipmentType,
        power_bonus: int = 0,
        defense_bonus: int = 0,
        damage_dice: str = "",
        enchantment: int = 0,
        enchantment_name: "str | None" = None,
    ):
        self.equipment_type = equipment_type

        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus
        self.damage_dice = damage_dice
        self.enchantment = enchantment
        self.enchantment_name = enchantment_name

    @property
    def actor(self) -> Actor:
        """The actor wearing this item (Item -> Inventory -> Actor)."""
        return self.parent.parent.parent

    def _apply_enchantment(self, event: str) -> None:
        """Shared logic for on_equip/on_unequip. event is 'equip' or 'unequip'."""
        if not self.enchantment_name:
            return
        entry = enchantment_data.get(self.enchantment_name)
        if entry is None:
            return
        fns = _EFFECT_REGISTRY.get(entry["effect"])
        fn = fns[0 if event == "equip" else 1] if fns else None
        if fn is not None:
            fn(self)
        msg = entry[f"{event}_message"]
        if msg is not None:
            text, color = msg
            self.engine.message_log.add_message(text, tuple(color))

    def on_equip(self) -> None:
        """Called when this equippable is equipped; can be overridden for special effects."""
        self._apply_enchantment("equip")

    def on_unequip(self) -> None:
        """Called when this equippable is unequipped; can be overridden to reverse effects."""
        self._apply_enchantment("unequip")

    def on_floor_change(self) -> None:
        """Called when the player changes floors. Re-applies one-shot enchantment effects."""
        if not self.enchantment_name:
            return
        entry = enchantment_data.get(self.enchantment_name)
        if entry is None:
            return
        fns = _EFFECT_REGISTRY.get(entry["effect"])
        if fns and fns[2] is not None:
            fns[2](self)


class AmuletOfClairvoyance(Equippable):
    """An amulet that reveals the dungeon layout when equipped."""

    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.AMULET)

    def on_equip(self) -> None:
        apply_clairvoyance(self.engine)

    def on_floor_change(self) -> None:
        apply_clairvoyance(self.engine)


class AmuletOfDetectMonster(Equippable):
    """An amulet that reveals all monsters while equipped."""

    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.AMULET)

    def on_equip(self) -> None:
        self.actor.is_detecting_monsters = True
        self.engine.message_log.add_message(
            "You sense the presence of monsters!",
            (0xC0, 0xC0, 0xFF),
        )

    def on_unequip(self) -> None:
        self.actor.is_detecting_monsters = False
        self.engine.message_log.add_message(
            "Your monster sense fades.",
            (0x80, 0x80, 0x80),
        )


class AmuletOfDetectItem(Equippable):
    """An amulet that reveals all items while equipped."""

    def __init__(self) -> None:
        super().__init__(equipment_type=EquipmentType.AMULET)

    def on_equip(self) -> None:
        self.actor.is_detecting_items = True
        self.engine.message_log.add_message(
            "You sense the presence of items!",
            (0xFF, 0xD7, 0x00),
        )

    def on_unequip(self) -> None:
        self.actor.is_detecting_items = False
        self.engine.message_log.add_message(
            "Your item sense fades.",
            (0x80, 0x80, 0x80),
        )
