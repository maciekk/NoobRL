from __future__ import annotations

import copy
import json
import math
from typing import Optional, Tuple, Type, TypeVar, TYPE_CHECKING, Union

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
    "FireballDamageConsumable": consumable.FireballDamageConsumable,
    "LightningDamageConsumable": consumable.LightningDamageConsumable,
}
EQUIPPABLE_MAP = {
    "Dagger": equippable.Dagger,
    "Sword": equippable.Sword,
    "LongSword": equippable.LongSword,
    "Odachi": equippable.Odachi,
    "LeatherArmor": equippable.LeatherArmor,
    "ChainMail": equippable.ChainMail,
    "SteelArmor": equippable.SteelArmor,
}

class Entity:
    """
    A generic object to represent players, enemies, items, etc.
    """

    parent: Union[GameMap, Inventory]

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

    @property
    def gamemap(self) -> GameMap:
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
                if self.parent is self.gamemap:
                    self.gamemap.entities.remove(self)
            self.parent = gamemap
            gamemap.entities.add(self)

    def distance(self, x: int, y: int) -> float:
        """
        Return the distance between the current entity and the given (x, y) coordinate.
        """
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def move(self, dx: int, dy: int) -> None:
        # Move the entity by a given amount
        self.x += dx
        self.y += dy


class Actor(Entity):
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

        self.equipment: Equipment = equipment
        self.equipment.parent = self

        self.fighter = fighter
        self.fighter.parent = self

        self.inventory = inventory
        self.inventory.parent = self

        self.level = level
        self.level.parent = self

        self.noticed_player = False

    @property
    def is_alive(self) -> bool:
        """Returns True as long as this actor can perform actions."""
        return bool(self.ai)


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

class ItemManager:
    def __init__(self, fname: string):
        self.items = {}
        self.load(fname)

    def load(self, fname: string):
        with open(fname, 'r') as f:
            data = f.read()
            for item in json.loads(data):
                id = item.pop('id')
                #name = item.pop('name')
                d = item.get('consumable', None)
                if d:
                    consumable_class = CONSUMABLE_MAP[d.pop('name')]
                    item['consumable'] = consumable_class(**d)
                d = item.get('equippable', None)
                if d:
                    equippable_class = EQUIPPABLE_MAP[d.pop('name')]
                    item['equippable'] = equippable_class(**d)
                self.items[id] = Item(**item)
