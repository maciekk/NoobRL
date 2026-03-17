"""Entity classes for game objects: Entity, Actor, Item."""
from __future__ import annotations

import copy
import math
import random
from typing import Optional, List, Tuple, Type, TypeVar, TYPE_CHECKING, Union

import numpy as np  # pylint: disable=import-error
import tcod  # pylint: disable=import-error

import enchantment_data
from equipment_types import EquipmentType
from location import Location
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

T = TypeVar("T", bound="Entity")


class Entity:  # pylint: disable=too-many-instance-attributes
    """
    A generic object to represent players, enemies, items, etc.
    """

    parent: Union[GameMap, Inventory, None]

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
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

    @property
    def location(self) -> Location:
        """Return the current position as a Location."""
        return Location(self.x, self.y)

    def get_path_to(self, dest: Location) -> List[Location]:
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
        path: List[List[int]] = pathfinder.path_to(dest)[1:].tolist()

        # Convert from List[List[int]] to List[Location].
        return [Location(index[0], index[1]) for index in path]


class Actor(Entity):  # pylint: disable=too-many-instance-attributes
    """A living entity with combat stats, AI, inventory, and equipment."""

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
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
        self.is_detecting_traps = False
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
    """A container entity that holds items and can be opened."""

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
        # Parallel list of (enchantment, enchantment_name) for each stored_item_id.
        # None entries mean no enchantment.
        self.stored_enchantment_data: List[Optional[Tuple[int, Optional[str]]]] = []

    def open(self, _opener: Actor) -> None:
        """Open the chest and spawn its pre-determined items."""
        import exceptions  # pylint: disable=import-outside-toplevel

        if self.opened:
            raise exceptions.Impossible("This chest is already open.")

        names = []
        for i, item_id in enumerate(self.stored_item_ids):
            template = self.gamemap.engine.item_manager.items.get(item_id)
            if template is None:
                continue
            item = template.spawn(self.gamemap, self.x, self.y)
            if i < len(self.stored_enchantment_data) and self.stored_enchantment_data[i] is not None:
                enchantment, enchantment_name = self.stored_enchantment_data[i]
                if item.equippable is not None:
                    item.equippable.enchantment = enchantment
                    item.equippable.enchantment_name = enchantment_name
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


_TRAP_COLORS = {
    "trapdoor": (139, 90, 43),
    "squeaky_board": (180, 140, 60),
}


class Trap(Entity):
    """A hidden trap that activates when stepped on."""

    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        trap_type: str = "trapdoor",
    ):
        super().__init__(
            x=x,
            y=y,
            char="^",
            color=_TRAP_COLORS.get(trap_type, (139, 90, 43)),
            name=f"{trap_type.replace('_', ' ')} trap",
            blocks_movement=False,
            render_order=RenderOrder.ITEM,
        )
        self.trap_type = trap_type
        self.is_revealed = False

    def trigger(self, engine, triggering_entity=None) -> None:
        """Reveal and activate this trap."""
        import color as _color  # pylint: disable=import-outside-toplevel
        from sound_travel import SoundTravel, SOUND_ANIM_MAX_DIST  # pylint: disable=import-outside-toplevel

        if (
            triggering_entity is engine.player
            or engine.game_map.visible[self.x, self.y]
        ):
            self.is_revealed = True

        if self.trap_type == "trapdoor":
            floors = random.randint(1, 3)
            engine.message_log.add_message(
                "You fall through a trapdoor!", _color.descend
            )
            engine.game_world.current_floor += floors
            engine.game_world.generate_floor(direction=0, trapdoor=True)
            engine.message_log.add_message(
                f"You land on dungeon level {engine.game_world.current_floor}.",
                _color.descend,
            )

        elif self.trap_type == "squeaky_board":
            if triggering_entity is engine.player:
                engine.message_log.add_message(
                    "You step on a squeaky board! *CREAK*", _color.white
                )
            else:
                dist = abs(self.x - engine.player.x) + abs(self.y - engine.player.y)
                if dist <= SOUND_ANIM_MAX_DIST:
                    visible = (
                        triggering_entity is not None
                        and engine.game_map.visible[triggering_entity.x, triggering_entity.y]
                    )
                    if visible:
                        msg = f"The {triggering_entity.name} steps on a squeaky board! *CREAK*"
                    else:
                        msg = "Someone steps on a squeaky board! *CREAK*"
                    engine.message_log.add_message(msg, _color.white)
            engine.emit_sound((self.x, self.y), SoundTravel.SQUEAKY_BOARD, by_player=triggering_entity is engine.player)


class Item(Entity):
    """An item entity that can be picked up, used, or equipped."""

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
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
            base_name = self.name
        else:
            gamemap = self.gamemap
            if gamemap is None:
                base_name = self.name
            else:
                engine = gamemap.engine
                if self.item_id in engine.identified_items:
                    base_name = self.name
                elif self.item_id in engine.scroll_aliases:
                    return f"scroll of {engine.scroll_aliases[self.item_id]}"
                elif self.item_id in engine.potion_aliases:
                    return f"{engine.potion_aliases[self.item_id]} potion"
                else:
                    base_name = self.name

        if self.equippable:
            name = base_name
            if self.equippable.enchantment > 0:
                name = f"+{self.equippable.enchantment} {name}"
            if self.equippable.enchantment_name:
                label = enchantment_data.get_label(self.equippable.enchantment_name)
                name = f"{name} of {label}"
            return name

        return base_name

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
                    rng = random.Random(engine.turn * 997 + sum(ord(c) for c in self.item_id))
                    while True:
                        r, g, b = rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)
                        if max(r, g, b) > 128:
                            return (r, g, b)
        return self.color

    @property
    def stackable(self) -> bool:
        """True if this item can be stacked in inventory."""
        if self.char == "/":           # Wands use charges, not stacks
            return False
        if self.equippable is not None and self.equippable.equipment_type == EquipmentType.THROWN:
            return True
        return self.consumable is not None and self.equippable is None
