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
    "BlindnessConsumable": consumable.BlindnessConsumable,
    "IdentificationConsumable": consumable.IdentificationConsumable,
}
EQUIPPABLE_MAP = {
    "Dagger": equippable.Dagger,
    "Sword": equippable.Sword,
    "LongSword": equippable.LongSword,
    "Odachi": equippable.Odachi,
    "LeatherArmor": equippable.LeatherArmor,
    "ChainMail": equippable.ChainMail,
    "SteelArmor": equippable.SteelArmor,
    "AmuletOfClairvoyance": equippable.AmuletOfClairvoyance,
    "AmuletOfDetectMonster": equippable.AmuletOfDetectMonster,
    "Dart": equippable.Dart,
}
AI_MAP = {
    "HostileEnemy": components.ai.HostileEnemy,
    "PatrollingEnemy": components.ai.PatrollingEnemy,
}


class ItemManager:
    """Loads and manages item templates from a JSON file."""

    def __init__(self, fname: string):
        self.items = {}
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
                    equippable_class = EQUIPPABLE_MAP[d.pop("name")]
                    item["equippable"] = equippable_class(**d)
                self.items[entity_id] = Item(**item)

    def clone(self, name: Optional[string]) -> Optional[Item]:
        """Return a deep copy of an item template by name."""
        if name is None:
            return None
        if name not in self.items:
            return None
        return copy.deepcopy(self.items[name])


class MonsterManager:
    """Loads and manages actor (monster) templates from a JSON file."""

    def __init__(self, fname: string, item_manager: ItemManager):
        self.monsters = {}
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

    def clone(self, name: string) -> Actor:
        """Return a deep copy of an actor template by name."""
        if name is None:
            return None
        if name not in self.monsters:
            return None
        return copy.deepcopy(self.monsters[name])
