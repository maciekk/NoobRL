"""Entity classes for game objects: Entity, Actor, Item, and their managers."""
from __future__ import annotations

import copy
import json
import math
import numpy as np
import string
from typing import Optional, List, Tuple, Type, TypeVar, TYPE_CHECKING, Union

import tcod

import components.ai
import components.equipment
import components.fighter
import components.inventory
import components.level
from render_order import RenderOrder

if TYPE_CHECKING:
    from components.ai import BaseAI
    from components.consumable import Consumable
    from components.equipment import Equipment
    from components.equippable import Equippable
    from components.fighter import Fighter
    from components.inventory import Inventory
    from components.level import Level
    from game_map import GameMap

from components import consumable, equippable

T = TypeVar("T", bound="Entity")

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


class Entity:
    """
    A generic object to represent players, enemies, items, etc.
    """

    parent: Union[GameMap, Inventory, None]

    def __init__(
        self,
        parent: Optional[GameMap] = None,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed>",
        blocks_movement: bool = False,
        render_order: RenderOrder = RenderOrder.CORPSE,
    ):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.blocks_movement = blocks_movement
        self.render_order = render_order
        if parent:
            # If parent isn't provided now then it will be set later.
            self.parent = parent
            parent.entities.add(self)
        else:
            self.parent = None

    @property
    def gamemap(self) -> Optional[GameMap]:
        """Get the GameMap containing this entity, if any."""
        if self.parent is None:
            return None
        return self.parent.gamemap

    def spawn(self: T, gamemap: GameMap, x: int, y: int) -> T:
        """Spawn a copy of this instance at the given location."""
        clone = copy.deepcopy(self)
        clone.x = x
        clone.y = y
        clone.parent = gamemap
        gamemap.entities.add(clone)
        return clone

    def place(self, x: int, y: int, gamemap: Optional[GameMap] = None) -> None:
        """Place this entitiy at a new location.  Handles moving across GameMaps."""
        self.x = x
        self.y = y
        if gamemap:
            if hasattr(self, "parent"):  # Possibly uninitialized.
                if self.parent is not None and self.parent is self.gamemap:
                    self.gamemap.entities.remove(self)
            self.parent = gamemap
            gamemap.entities.add(self)

    def distance(self, x: int, y: int) -> float:
        """
        Return the distance between the current entity and the given (x, y) coordinate.
        """
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def move(self, dx: int, dy: int) -> None:
        """Move the entity by a given offset."""
        self.x += dx
        self.y += dy

    def get_path_to(self, dest_x: int, dest_y: int) -> List[Tuple[int, int]]:
        """Compute and return a path to the target position.
        If there is no valid path then returns an empty list.
        """
        # Copy the walkable array.
        cost = np.array(self.gamemap.tiles["walkable"], dtype=np.int8)

        for entity in self.gamemap.entities:
            # Check that an entity blocks movement and the cost isn't zero (blocking.)
            if entity.blocks_movement and cost[entity.x, entity.y]:
                # Add to the cost of a blocked position.
                # A lower number means more enemies will crowd behind each other in
                # hallways.  A higher number means enemies will take longer paths in
                # order to surround the player.
                cost[entity.x, entity.y] += 10

        # Create a graph from the cost array and pass that graph to a new pathfinder.
        graph = tcod.path.SimpleGraph(cost=cost, cardinal=2, diagonal=3)
        pathfinder = tcod.path.Pathfinder(graph)

        pathfinder.add_root((self.x, self.y))  # Start position.

        # Compute the path to the destination and remove the starting point.
        path: List[List[int]] = pathfinder.path_to((dest_x, dest_y))[1:].tolist()

        # Convert from List[List[int]] to List[Tuple[int, int]].
        return [(index[0], index[1]) for index in path]


class Actor(Entity):
    """A living entity with combat stats, AI, inventory, and equipment."""

    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed>",
        ai_cls: Type[BaseAI],
        equipment: Equipment,
        fighter: Fighter,
        inventory: Inventory,
        level: Level,
        base_speed: int = 100,
        attack_range: int = 1,
        ranged_attack: bool = False,
        death_explosion: dict = None,
        sight_range: int = 6,
    ):
        super().__init__(
            x=x,
            y=y,
            char=char,
            color=color,
            name=name,
            blocks_movement=True,
            render_order=RenderOrder.ACTOR,
        )

        self.ai: Optional[BaseAI] = ai_cls(self)

        self.inventory = inventory
        self.inventory.parent = self

        self.equipment = equipment
        self.equipment.parent = self

        if self.equipment.armor:
            self.take_and_equip(self.equipment.armor)
        if self.equipment.weapon:
            self.take_and_equip(self.equipment.weapon)

        self.fighter = fighter
        self.fighter.parent = self

        self.level = level
        self.level.parent = self

        self.effects = []

        self.noticed_player = False
        self.is_invisible = False
        self.is_asleep = False
        self.is_blind = False
        self.base_speed = base_speed
        self.attack_range = attack_range
        self.ranged_attack = ranged_attack
        self.energy = 0
        self.is_hasted = False
        self.is_detecting_monsters = False
        self.death_explosion = death_explosion
        self.sight_range = sight_range

    @property
    def speed(self) -> int:
        """Effective speed; doubled if hasted."""
        return self.base_speed * (2 if self.is_hasted else 1)

    @property
    def is_alive(self) -> bool:
        """Returns True as long as this actor can perform actions."""
        return bool(self.ai)

    def take(self, item: Item) -> None:
        """Add an item to this actor's inventory."""
        if item not in self.inventory.items:
            self.inventory.add(item)

    def take_and_equip(self, item: Item) -> None:
        """Add an item to inventory and equip it."""
        self.take(item)
        if not self.equipment.item_is_equipped(item):
            self.equipment.toggle_equip(item)


class Chest(Entity):
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        color: Tuple[int, int, int] = (191, 128, 32),
        name: str = "chest",
    ):
        super().__init__(
            x=x,
            y=y,
            char="~",
            color=color,
            name=name,
            blocks_movement=False,
            render_order=RenderOrder.ITEM,
        )
        self.opened = False
        self.stored_item_ids: List[str] = []

    def open(self, opener: Actor) -> None:
        """Open the chest and spawn its pre-determined items."""
        import exceptions

        if self.opened:
            raise exceptions.Impossible("This chest is already open.")

        names = []
        for item_id in self.stored_item_ids:
            template = self.gamemap.engine.item_manager.items.get(item_id)
            if template is None:
                continue
            item = template.spawn(self.gamemap, self.x, self.y)
            names.append(item.display_name)

        self.char = "_"
        self.opened = True

        if names:
            self.gamemap.engine.message_log.add_message(
                f"You open the chest and find: {', '.join(names)}!"
            )
        else:
            self.gamemap.engine.message_log.add_message(
                "You open the chest, but it's empty."
            )


class Item(Entity):
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed>",
        consumable: Optional[Consumable] = None,
        equippable: Optional[Equippable] = None,
        stack_count: int = 1,
        item_id: str = "",
    ):
        super().__init__(
            x=x,
            y=y,
            char=char,
            color=color,
            name=name,
            blocks_movement=False,
            render_order=RenderOrder.ITEM,
        )

        self.consumable = consumable
        if self.consumable:
            self.consumable.parent = self

        self.equippable = equippable

        if self.equippable:
            self.equippable.parent = self

        self.stack_count = stack_count
        self.item_id = item_id

    @property
    def display_name(self) -> str:
        """Return the anonymized name if unidentified, otherwise the true name."""
        if not self.item_id:
            return self.name
        gamemap = self.gamemap
        if gamemap is None:
            return self.name
        engine = gamemap.engine
        if self.item_id in engine.identified_items:
            return self.name
        if self.item_id in engine.scroll_aliases:
            return f"scroll of {engine.scroll_aliases[self.item_id]}"
        if self.item_id in engine.potion_aliases:
            return f"{engine.potion_aliases[self.item_id]} potion"
        return self.name

    @property
    def display_color(self) -> Tuple[int, int, int]:
        """Return the alias color for potions (always), otherwise the true color."""
        if self.item_id:
            gamemap = self.gamemap
            if gamemap is not None:
                engine = gamemap.engine
                if self.item_id in engine.potion_alias_colors:
                    return engine.potion_alias_colors[self.item_id]
                alias = engine.potion_aliases.get(self.item_id, "")
                if "iridescent" in alias:
                    import random
                    rng = random.Random(engine.turn * 997 + sum(ord(c) for c in self.item_id))
                    while True:
                        r, g, b = rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)
                        if max(r, g, b) > 128:
                            return (r, g, b)
        return self.color

    @property
    def stackable(self) -> bool:
        """True if this item can be stacked in inventory."""
        from equipment_types import EquipmentType

        if self.char == "/":           # Wands use charges, not stacks
            return False
        if self.equippable is not None and self.equippable.equipment_type == EquipmentType.THROWN:
            return True
        return self.consumable is not None and self.equippable is None


class ItemManager:
    def __init__(self, fname: string):
        self.items = {}
        self.load(fname)

    def load(self, fname: string) -> None:
        """Load item templates from a JSON file."""
        with open(fname, "r") as f:
            data = f.read()
            for item in json.loads(data):
                id = item.pop("id")
                item["item_id"] = id
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
                self.items[id] = Item(**item)

    def clone(self, name: Optional[string]) -> Optional[Item]:
        """Return a deep copy of an item template by name."""
        if name is None:
            return None
        if name not in self.items:
            return None
        return copy.deepcopy(self.items[name])


class MonsterManager:
    def __init__(self, fname: string, item_manager: ItemManager):
        self.monsters = {}
        self.item_manager = item_manager
        self.load(fname)

    def load(self, fname: string) -> None:
        """Load actor templates from a JSON file."""
        with open(fname, "r") as f:
            data = f.read()
            for item in json.loads(data):
                id = item.pop("id")
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
                self.monsters[id] = Actor(**item)

    def clone(self, name: string) -> Actor:
        """Return a deep copy of an actor template by name."""
        if name is None:
            return None
        if name not in self.monsters:
            return None
        return copy.deepcopy(self.monsters[name])
