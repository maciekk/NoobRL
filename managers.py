"""Managers for loading and cloning item and monster templates from JSON."""
from __future__ import annotations

import copy
import json
import string
from typing import Optional

import components.ai
import components.equipment
import components.fighter
import components.inventory
import components.level
from components import consumable, equippable
from entity import Item, Actor
from equipment_types import EquipmentType

CONSUMABLE_MAP = {
    "ConfusionConsumable": consumable.ConfusionConsumable,
    "HealingConsumable": consumable.HealingConsumable,
    "BlinkConsumable": consumable.BlinkConsumable,
    "TeleportConsumable": consumable.TeleportConsumable,
    "FireballDamageConsumable": consumable.FireballDamageConsumable,
    "LightningDamageConsumable": consumable.LightningDamageConsumable,
    "RageConsumable": consumable.RageConsumable,
    "ClairvoyanceConsumable": consumable.ClairvoyanceConsumable,
    "WishingWandConsumable": consumable.WishingWandConsumable,
    "LightningWandConsumable": consumable.LightningWandConsumable,
    "DiggingWandConsumable": consumable.DiggingWandConsumable,
    "InvisibilityConsumable": consumable.InvisibilityConsumable,
    "SpeedConsumable": consumable.SpeedConsumable,
    "DetectMonsterConsumable": consumable.DetectMonsterConsumable,
    "SleepConsumable": consumable.SleepConsumable,
    "BombConsumable": consumable.BombConsumable,
    "FertilizerBombConsumable": consumable.FertilizerBombConsumable,
    "BlindnessConsumable": consumable.BlindnessConsumable,
    "IdentificationConsumable": consumable.IdentificationConsumable,
    "DetectTrapsConsumable": consumable.DetectTrapsConsumable,
    "EnchantWeaponConsumable": consumable.EnchantWeaponConsumable,
    "EnchantArmourConsumable": consumable.EnchantArmourConsumable,
}
EQUIPPABLE_MAP = {
    "AmuletOfClairvoyance": equippable.AmuletOfClairvoyance,
    "AmuletOfDetectMonster": equippable.AmuletOfDetectMonster,
}
AI_MAP = {
    "HostileEnemy": components.ai.HostileEnemy,
    "PatrollingEnemy": components.ai.PatrollingEnemy,
}


class BaseManager:
    """Base for template managers with a shared clone method."""

    def __init__(self):
        self._templates: dict = {}

    def clone(self, name: Optional[string]):
        """Return a deep copy of a template by name, or None."""
        if name is None or name not in self._templates:
            return None
        return copy.deepcopy(self._templates[name])


class ItemManager(BaseManager):
    """Loads and manages item templates from a JSON file."""

    def __init__(self, fname: string):
        super().__init__()
        self.items = self._templates
        self.load(fname)

    def load(self, fname: string) -> None:
        """Load item templates from a JSON file."""
        with open(fname, "r", encoding="utf-8") as f:
            data = f.read()
            for item in json.loads(data):
                entity_id = item.pop("id")
                item["item_id"] = entity_id
                if "charges" in item:
                    item["stack_count"] = item.pop("charges")
                d = item.get("consumable", None)
                if d:
                    consumable_class = CONSUMABLE_MAP[d.pop("name")]
                    item["consumable"] = consumable_class(**d)
                d = item.get("equippable", None)
                if d:
                    name = d.pop("name", None)
                    if name:
                        item["equippable"] = EQUIPPABLE_MAP[name](**d)
                    else:
                        eq_type = EquipmentType[d.pop("equipment_type")]
                        item["equippable"] = equippable.Equippable(equipment_type=eq_type, **d)
                self.items[entity_id] = Item(**item)


class MonsterManager(BaseManager):
    """Loads and manages actor (monster) templates from a JSON file."""

    def __init__(self, fname: string, item_manager: ItemManager):
        super().__init__()
        self.monsters = self._templates
        self.item_manager = item_manager
        self.load(fname)

    def load(self, fname: string) -> None:
        """Load actor templates from a JSON file."""
        with open(fname, "r", encoding="utf-8") as f:
            data = f.read()
            for item in json.loads(data):
                entity_id = item.pop("id")
                item["ai_cls"] = AI_MAP[item.pop("ai_cls")]
                d = item.get("equipment", None)
                if d is not None:
                    d["armor"] = self.item_manager.clone(d.get("armor"))
                    d["weapon"] = self.item_manager.clone(d.get("weapon"))
                    item["equipment"] = components.equipment.Equipment(**d)
                d = item.get("fighter", None)
                if d:
                    item["fighter"] = components.fighter.Fighter(**d)
                d = item.get("inventory", None)
                if d:
                    item["inventory"] = components.inventory.Inventory(**d)
                d = item.get("level", None)
                if d:
                    item["level"] = components.level.Level(**d)
                self.monsters[entity_id] = Actor(**item)
