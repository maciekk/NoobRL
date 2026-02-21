"""Actions that entities can perform to interact with the game world."""

from __future__ import annotations

import copy
import math
import random
from typing import Optional, Tuple, TYPE_CHECKING

import tcod

import color
import sounds
from components.effect import (
    BlindnessEffect,
    InvisibilityEffect,
    RageEffect,
    SleepEffect,
    SpeedEffect,
)
from equipment_types import EquipmentType
import exceptions
import options
import tile_types

if TYPE_CHECKING:
    from engine import Engine
    from entity import Actor, Entity, Item


def compute_damage(attack_power, defense, crit_chance=0.05, crit_mult=1.5):
    """Compute damage with optional critical hit."""
    is_crit = False
    damage = attack_power - defense
    if random.random() <= crit_chance:
        is_crit = True
        damage *= crit_mult
        if damage <= 0:
            damage = 1
    return math.ceil(damage), is_crit


class Action:
    """Base class for all entity actions."""

    def __init__(self, entity: Actor) -> None:
        super().__init__()
        self.entity = entity

    @property
    def engine(self) -> Engine:
        """Return the engine this action belongs to."""
        return self.entity.gamemap.engine

    def perform(self) -> None:
        """Perform this action with the objects needed to determine its scope.
        `self.engine` is the scope this action is being performed in.
        `self.entity` is the object performing the action.
        This method must be overridden by Action subclasses.
        """
        raise NotImplementedError()


class IdentifyAction(Action):
    """Use a scroll of identification to identify an item."""

    def __init__(self, entity: Actor, scroll_item: Item, target_item: Item):
        super().__init__(entity)
        self.scroll_item = scroll_item
        self.target_item = target_item

    def perform(self) -> None:
        self.engine.identified_items.add(self.target_item.item_id)
        self.engine.message_log.add_message(
            f"You identify it as the {self.target_item.name}!",
            color.status_effect_applied,
        )
        self.scroll_item.consumable.consume()


class WishAction(Action):
    """Use a wishing wand to wish for an item."""

    def __init__(self, entity: Actor, wand_item: Item, wish_item_id: str):
        super().__init__(entity)
        self.wand_item = wand_item
        self.wish_item_id = wish_item_id

    def perform(self) -> None:
        item = self.engine.item_manager.clone(self.wish_item_id)
        if item is None:
            raise exceptions.Impossible("Nothing happens.")

        # Try to add to inventory first
        item.parent = self.entity.inventory
        if not self.entity.inventory.add(item):
            # Inventory is full, drop on floor instead
            item.place(self.entity.x, self.entity.y, self.engine.game_map)
            self.engine.message_log.add_message(
                f"You wished for a {item.name}," " but your inventory is full!",
                color.impossible,
            )
        else:
            self.engine.message_log.add_message(
                f"You wished for a {item.name}!",
                color.status_effect_applied,
            )
        sounds.play("sfx/643876__sushiman2000__smoke-poof.ogg")
        self.wand_item.consumable.consume()


class PickupAction(Action):
    """Pickup an item and add it to the inventory."""

    def perform(self) -> None:
        actor_location_x = self.entity.x
        actor_location_y = self.entity.y
        inventory = self.entity.inventory

        items_here = [
            item
            for item in self.engine.game_map.items
            if item.x == actor_location_x and item.y == actor_location_y
        ]

        if not items_here:
            raise exceptions.Impossible("There is nothing here to pick up.")

        for item in items_here:
            can_stack = item.stackable and inventory.find_stack(item.name) is not None
            if not can_stack and len(inventory.items) >= inventory.capacity:
                self.engine.message_log.add_message(
                    "Your inventory is full.", color.impossible
                )
                break

            pickup_count = item.stack_count
            self.engine.game_map.entities.remove(item)
            item.parent = self.entity.inventory
            inventory.add(item)

            count_text = (
                f" (x{pickup_count})" if item.stackable and pickup_count > 1 else ""
            )
            self.engine.message_log.add_message(
                f"You picked up the {item.display_name}{count_text}!"
            )


class ItemAction(Action):
    """Action involving an inventory item."""

    def __init__(
        self,
        entity: Actor,
        item: Item,
        target_xy: Optional[Tuple[int, int]] = None,
    ):
        super().__init__(entity)
        self.item = item
        if not target_xy:
            target_xy = entity.x, entity.y
        self.target_xy = target_xy

    @property
    def target_actor(self) -> Optional[Actor]:
        """Return the actor at this actions destination."""
        return self.engine.game_map.get_actor_at_location(*self.target_xy)

    def perform(self) -> None:
        """Invoke the items ability."""
        if self.item.consumable:
            self.item.consumable.activate(self)


class DropItem(ItemAction):
    """Drop an item from inventory."""

    def __init__(
        self,
        entity: Actor,
        item: Item,
        target_xy: Optional[Tuple[int, int]] = None,
        count: int = 0,
    ):
        super().__init__(entity, item, target_xy)
        self.count = count

    def perform(self) -> None:
        if self.entity.equipment.item_is_equipped(self.item):
            self.entity.equipment.toggle_equip(self.item)

        self.entity.inventory.drop(self.item, self.count)


class EquipAction(Action):
    """Toggle equipping an item."""

    def __init__(self, entity: Actor, item: Item):
        super().__init__(entity)
        self.item = item

    def perform(self) -> None:
        self.entity.equipment.toggle_equip(self.item)


class OpenAction(Action):
    """Open something at the entity's location."""

    def perform(self) -> None:
        x, y = self.entity.x, self.entity.y
        for entity in self.engine.game_map.entities:
            if entity.x == x and entity.y == y and hasattr(entity, "open"):
                entity.open(self.entity)
                return
        raise exceptions.Impossible("There is nothing here to open.")


class OpenDoorAction(Action):
    """Open a door at a specific location."""

    def __init__(self, entity: Actor, x: int, y: int):
        super().__init__(entity)
        self.x = x
        self.y = y

    def perform(self) -> None:
        if not self.engine.game_map.in_bounds(self.x, self.y):
            raise exceptions.Impossible("There is no door there.")

        tile = self.engine.game_map.tiles[self.x, self.y]
        if tile == tile_types.door_closed:
            self.engine.game_map.tiles[self.x, self.y] = tile_types.door_open
            self.engine.message_log.add_message("You open the door.", color.white)
        else:
            raise exceptions.Impossible("There is no closed door there.")


class CloseDoorAction(Action):
    """Close a door at a specific location."""

    def __init__(self, entity: Actor, x: int, y: int):
        super().__init__(entity)
        self.x = x
        self.y = y

    def perform(self) -> None:
        if not self.engine.game_map.in_bounds(self.x, self.y):
            raise exceptions.Impossible("There is no door there.")

        # Check for entities at the door location
        for entity in self.engine.game_map.entities:
            if entity.x == self.x and entity.y == self.y and entity is not self.entity:
                raise exceptions.Impossible("There is something in the way.")

        tile = self.engine.game_map.tiles[self.x, self.y]
        if tile == tile_types.door_open:
            self.engine.game_map.tiles[self.x, self.y] = tile_types.door_closed
            self.engine.message_log.add_message("You close the door.", color.white)
        else:
            raise exceptions.Impossible("There is no open door there.")


class WaitAction(Action):
    """Skip the current turn."""

    def perform(self) -> None:
        pass


class TakeStairsAction(Action):
    """Descend stairs to the next floor."""

    def perform(self) -> None:
        if (self.entity.x, self.entity.y) == (self.engine.game_map.downstairs_location):
            self.engine.game_world.generate_floor()
            self.engine.message_log.add_message(
                "You descend the staircase.", color.descend
            )
        else:
            raise exceptions.Impossible("There are no stairs here.")


class TakeUpStairsAction(Action):
    """Ascend stairs to the previous floor."""

    def perform(self) -> None:
        if (self.entity.x, self.entity.y) == (self.engine.game_map.upstairs_location):
            if self.engine.game_world.current_floor <= 1:
                raise exceptions.Impossible("You cannot go further up.")
            self.engine.game_world.generate_floor(direction=-1)
            self.engine.message_log.add_message(
                "You ascend the staircase.", color.ascend
            )
        else:
            raise exceptions.Impossible("There are no stairs here.")


class ActionWithDirection(Action):
    """Action with a direction component."""

    def __init__(self, entity: Actor, dx: int, dy: int):
        super().__init__(entity)

        self.dx = dx
        self.dy = dy

    @property
    def dest_xy(self) -> Tuple[int, int]:
        """Returns this actions destination."""
        return self.entity.x + self.dx, self.entity.y + self.dy

    @property
    def blocking_entity(self) -> Optional[Entity]:
        """Return the blocking entity at this actions destination."""
        return self.engine.game_map.get_blocking_entity_at_location(*self.dest_xy)

    @property
    def target_actor(self) -> Optional[Actor]:
        """Return the actor at this actions destination."""
        return self.engine.game_map.get_actor_at_location(*self.dest_xy)

    def perform(self) -> None:
        raise NotImplementedError()


class MeleeAction(ActionWithDirection):
    """Attack an adjacent actor with a melee strike."""

    def perform(self) -> None:
        target = self.target_actor
        if not target:
            raise exceptions.Impossible("Nothing to attack.")

        big_monsters = ("Dragon", "Ender Dragon", "Hydra")
        if self.entity.name in big_monsters:
            crit_chance = 0.3
        else:
            crit_chance = 0.05
        damage, is_crit = compute_damage(
            self.entity.fighter.power,
            target.fighter.defense,
            crit_chance,
        )
        attack_desc = f"{self.entity.name.capitalize()} attacks {target.name}"
        crit_text = ""
        if self.entity is self.engine.player:
            attack_color = color.player_atk
        else:
            attack_color = color.enemy_atk
        if is_crit:
            attack_color = color.crit_atk
            crit_text = " [CRIT!]"
        if damage > 0:
            self.engine.message_log.add_message(
                f"{attack_desc} for {damage} hit points" f"{crit_text}.",
                attack_color,
            )
            target.fighter.take_damage(damage)
        else:
            self.engine.message_log.add_message(
                f"{attack_desc} but does no damage.",
                attack_color,
            )


class RangedAttackAction(ActionWithDirection):
    """Ranged attack targeting the player."""

    def perform(self) -> None:
        target = self.engine.player
        damage, is_crit = compute_damage(
            self.entity.fighter.power, target.fighter.defense
        )

        attack_desc = f"{self.entity.name.capitalize()} zaps {target.name}"
        crit_text = ""
        attack_color = color.enemy_atk
        if is_crit:
            attack_color = color.crit_atk
            crit_text = " [CRIT!]"

        if damage > 0:
            self.engine.message_log.add_message(
                f"{attack_desc} for {damage} hit points." f"{crit_text}",
                attack_color,
            )
            target.fighter.take_damage(damage)
        else:
            self.engine.message_log.add_message(
                f"{attack_desc} but does no damage.",
                attack_color,
            )


class MovementAction(ActionWithDirection):
    """Move in a direction."""

    def perform(self) -> None:
        dest_x, dest_y = self.dest_xy

        if not self.engine.game_map.in_bounds(dest_x, dest_y):
            # Destination is out of bounds.
            raise exceptions.Impossible("That way is blocked.")
        if not self.engine.game_map.tiles["walkable"][dest_x, dest_y]:
            # Destination is blocked by a tile.
            raise exceptions.Impossible("That way is blocked.")
        if self.engine.game_map.get_blocking_entity_at_location(dest_x, dest_y):
            # Destination is blocked by an entity.
            raise exceptions.Impossible("That way is blocked.")

        self.entity.move(self.dx, self.dy)


class BumpAction(ActionWithDirection):
    """Context-sensitive action: attack if actor present, else move."""

    def perform(self) -> None:
        if self.target_actor:
            MeleeAction(self.entity, self.dx, self.dy).perform()
            return

        dest_x, dest_y = self.dest_xy
        if self.engine.game_map.in_bounds(dest_x, dest_y):
            if (dest_x, dest_y) in (self.engine.game_map.secret_doors):
                self.engine.game_map.secret_doors.discard((dest_x, dest_y))
                self.engine.game_map.tiles[dest_x, dest_y] = tile_types.door_closed
                self.engine.message_log.add_message(
                    "You discover a secret door!", color.white
                )
                return
            if (
                options.auto_open_doors
                and self.engine.game_map.tiles[dest_x, dest_y] == tile_types.door_closed
            ):
                OpenDoorAction(self.entity, dest_x, dest_y).perform()
                return

        MovementAction(self.entity, self.dx, self.dy).perform()


class MovementRepeatedAction(MovementAction):
    """Auto-repeating movement that follows corridors."""

    def _walkable(self, x, y):
        gm = self.engine.game_map
        return gm.in_bounds(x, y) and gm.tiles["walkable"][x, y]

    def _find_corridor_turn(self):
        """If in a corridor, return the unique continuation dir."""
        px, py = self.entity.x, self.entity.y
        cardinal = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        backward = (-self.dx, -self.dy)

        # Don't follow turns near open areas (room corners).
        for d in cardinal:
            nx, ny = px + d[0], py + d[1]
            if self._walkable(nx, ny):
                count = sum(
                    1 for dd in cardinal if self._walkable(nx + dd[0], ny + dd[1])
                )
                if count >= 3:
                    return None

        candidates = [
            d
            for d in cardinal
            if d != backward and self._walkable(px + d[0], py + d[1])
        ]

        if len(candidates) == 1:
            return candidates[0]
        return None

    def perform(self):
        # First, check if any monsters are visible.
        if self.engine.game_map.any_monsters_visible():
            return None

        try:
            super().perform()
            return True
        except exceptions.Impossible:
            # Try to follow a corridor turn.
            px, py = self.entity.x, self.entity.y
            cardinal = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            neighbors = sum(1 for d in cardinal if self._walkable(px + d[0], py + d[1]))
            if neighbors >= 3:
                return None  # In open area, don't turn.
            turn = self._find_corridor_turn()
            if turn is None:
                return None
            self.dx, self.dy = turn
            try:
                super().perform()
                return True
            except exceptions.Impossible:
                return None


class CarefulMovementAction(MovementAction):
    """Repeated movement stopping at intersections."""

    def __init__(self, entity: Actor, dx: int, dy: int):
        super().__init__(entity, dx, dy)
        self._has_moved = False

    def _walkable(self, x, y):
        gm = self.engine.game_map
        return gm.in_bounds(x, y) and gm.tiles["walkable"][x, y]

    def _count_neighbors(self, x, y):
        """Count walkable cardinal neighbors of a tile."""
        cardinal = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        return sum(1 for d in cardinal if self._walkable(x + d[0], y + d[1]))

    def _on_interesting_tile(self) -> bool:
        """True if standing on a notable feature or item."""
        tile = self.engine.game_map.tiles[self.entity.x, self.entity.y]
        if any(tile == t for t in tile_types.interesting_tiles):
            return True
        px, py = self.entity.x, self.entity.y
        return any(item.x == px and item.y == py for item in self.engine.game_map.items)

    def _find_corridor_turn(self):
        """Return the unique continuation direction in a corridor.

        Looks at walkable cardinal neighbors, excludes the backward
        direction, and returns (dx, dy) if exactly one forward/side
        option remains. Returns None at dead ends, T-junctions, or
        open areas.
        """
        px, py = self.entity.x, self.entity.y
        cardinal = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        backward = (-self.dx, -self.dy)

        # Don't follow turns near open areas (room corners).
        for d in cardinal:
            nx, ny = px + d[0], py + d[1]
            if self._walkable(nx, ny):
                count = sum(
                    1 for dd in cardinal if self._walkable(nx + dd[0], ny + dd[1])
                )
                if count >= 3:
                    return None

        candidates = [
            d
            for d in cardinal
            if d != backward and self._walkable(px + d[0], py + d[1])
        ]

        if len(candidates) == 1:
            return candidates[0]
        return None

    def _try_step_open(self):
        """Attempt one step in an open area."""
        try:
            super().perform()
            if self._on_interesting_tile():
                return None
            return True
        except exceptions.Impossible:
            return None

    def _try_step(self):
        """Attempt one movement step through a corridor."""
        try:
            super().perform()
            self._has_moved = True
            if self._on_interesting_tile():
                return None
            return True
        except exceptions.Impossible:
            return None

    def _enter_room_or_stop(self):
        """Enter a room on the first step, otherwise stop."""
        if not self._has_moved:
            return self._try_step()
        return None

    def perform(self):
        if self.engine.game_map.any_monsters_visible():
            return None

        px, py = self.entity.x, self.entity.y
        if self._count_neighbors(px, py) >= 3:
            return self._try_step_open()

        dest_x, dest_y = self.dest_xy
        if self._count_neighbors(dest_x, dest_y) >= 3:
            return self._enter_room_or_stop()

        if not self._walkable(dest_x, dest_y):
            turn = self._find_corridor_turn()
            if turn is None:
                return None
            self.dx, self.dy = turn
            dest_x, dest_y = self.dest_xy
            if self._count_neighbors(dest_x, dest_y) >= 3:
                return self._enter_room_or_stop()

        return self._try_step()


class TargetMovementAction(Action):
    """Move along a path to a target location."""

    def __init__(self, entity: Actor, x: int, y: int):
        super().__init__(entity)
        self.x = x
        self.y = y
        self.path = self.entity.get_path_to(x, y)

    def perform(self):
        if not self.path:
            return False
        if self.engine.game_map.any_monsters_visible():
            return False
        x, y = self.path.pop(0)
        if self.engine.game_map.get_blocking_entity_at_location(x, y):
            return False
        self.entity.move(x - self.entity.x, y - self.entity.y)
        return True  # keep going


class ThrowAction(Action):
    """Throw an item from inventory in a direction."""

    MAX_RANGE = 10

    def __init__(self, entity: Actor, item: Item, target_xy: Tuple[int, int]):
        super().__init__(entity)
        self.item = item
        self.target_xy = target_xy

    def _compute_damage(self, item: Item) -> int:
        if item.equippable:
            if item.equippable.equipment_type == EquipmentType.THROWN:
                return item.equippable.power_bonus
            if item.equippable.equipment_type == EquipmentType.WEAPON:
                return max(1, item.equippable.power_bonus // 2)
        return 1

    def _apply_consumable_effect(
        self, item: Item, target: Actor = None, x: int = None, y: int = None
    ) -> None:
        """Apply a thrown consumable's effect to a target actor or at a location."""
        consumable = item.consumable
        class_name = consumable.__class__.__name__

        if class_name == "BombConsumable":
            # Use provided x, y if given, otherwise use target location
            if x is None or y is None:
                if target:
                    x, y = target.x, target.y
                else:
                    raise ValueError("Bomb needs a location to explode at")
            consumable.explode(x, y, self.engine.game_map, self.engine)
        elif class_name == "HealingConsumable":
            amount_recovered = target.fighter.heal(consumable.amount)
            if amount_recovered > 0:
                self.engine.message_log.add_message(
                    f"The {target.name} recovers {amount_recovered} HP!",
                    color.health_recovered,
                )
        elif class_name == "SleepConsumable":
            self.engine.message_log.add_message(
                f"The {target.name} falls asleep!",
                color.status_effect_applied,
            )
            eff = SleepEffect(engine=self.engine, duration=consumable.number_of_turns)
            target.effects.append(eff)
            eff.parent = target
            eff.activate()
        elif class_name == "SpeedConsumable":
            self.engine.message_log.add_message(
                f"The {target.name} feels themselves moving faster!",
                color.status_effect_applied,
            )
            eff = SpeedEffect(engine=self.engine, duration=consumable.duration)
            target.effects.append(eff)
            eff.parent = target
            eff.activate()
        elif class_name == "InvisibilityConsumable":
            self.engine.message_log.add_message(
                f"The {target.name} fades from sight!",
                color.status_effect_applied,
            )
            eff = InvisibilityEffect(engine=self.engine, duration=consumable.duration)
            target.effects.append(eff)
            eff.parent = target
            eff.activate()
        elif class_name == "RageConsumable":
            self.engine.message_log.add_message(
                f"The {target.name} is filled with rage!",
                color.damage_increased,
            )
            eff = RageEffect(engine=self.engine, dmg_mult=consumable.amount, duration=10)
            target.effects.append(eff)
            eff.parent = target
            eff.activate()
        elif class_name == "BlindnessConsumable":
            self.engine.message_log.add_message(
                f"The {target.name} is blinded!",
                color.status_effect_applied,
            )
            eff = BlindnessEffect(engine=self.engine, duration=consumable.duration)
            target.effects.append(eff)
            eff.parent = target
            eff.activate()
        else:
            # For other consumables, just log that the effect was applied
            self.engine.message_log.add_message(
                f"The {target.name} is affected by the {item.display_name}!",
                color.status_effect_applied,
            )

    def _trace_throw_path(self, game_map, sx: int, sy: int) -> Tuple[int, int, Optional[Actor]]:
        """Walk the Bresenham line from (sx, sy) to target_xy; return landing tile + hit actor."""
        tx, ty = self.target_xy
        line = tcod.los.bresenham((sx, sy), (tx, ty)).tolist()
        if line and (line[0][0], line[0][1]) == (sx, sy):
            line = line[1:]
        final_x, final_y = sx, sy
        hit_actor = None
        for i, (lx, ly) in enumerate(line):
            if i >= self.MAX_RANGE:
                break
            if not game_map.in_bounds(lx, ly):
                break
            if not game_map.tiles["walkable"][lx, ly]:
                break
            actor = game_map.get_actor_at_location(lx, ly)
            if actor:
                final_x, final_y = lx, ly
                hit_actor = actor
                break
            final_x, final_y = lx, ly
        return final_x, final_y, hit_actor

    def _place_thrown_item(self, thrown_item: Item, final_x: int, final_y: int, game_map) -> None:
        """Place thrown_item on the floor, merging with an existing stack if one is present."""
        thrown_item.place(final_x, final_y, game_map)
        if not thrown_item.stackable:
            return
        for entity in list(game_map.entities):
            if entity is thrown_item:
                continue
            if (hasattr(entity, "stackable")
                    and entity.stackable
                    and entity.name == thrown_item.name
                    and entity.x == final_x
                    and entity.y == final_y):
                entity.stack_count += thrown_item.stack_count
                game_map.entities.discard(thrown_item)
                break

    def perform(self) -> None:
        game_map = self.engine.game_map
        sx, sy = self.entity.x, self.entity.y
        final_x, final_y, hit_actor = self._trace_throw_path(game_map, sx, sy)

        # Remove one item from inventory.
        if self.item.stackable and self.item.stack_count > 1:
            self.item.stack_count -= 1
            thrown_item = copy.deepcopy(self.item)
            thrown_item.stack_count = 1
        else:
            if self.item in self.entity.inventory.items:
                self.entity.inventory.items.remove(self.item)
            thrown_item = self.item

        self.engine.message_log.add_message(
            f"You throw the {thrown_item.display_name}!", color.white
        )

        if hit_actor:
            if thrown_item.consumable:
                if thrown_item.consumable.__class__.__name__ != "BombConsumable":
                    self.engine.message_log.add_message(
                        f"The {thrown_item.display_name} hits the {hit_actor.name} and breaks!",
                        color.player_atk,
                    )
                self._apply_consumable_effect(thrown_item, hit_actor)
                return
            damage = self._compute_damage(thrown_item)
            self.engine.message_log.add_message(
                f"The {thrown_item.display_name} hits the {hit_actor.name} for {damage} damage!",
                color.player_atk,
            )
            hit_actor.fighter.take_damage(damage)
        elif not game_map.tiles["walkable"][final_x, final_y]:
            if thrown_item.consumable:
                if thrown_item.consumable.__class__.__name__ == "BombConsumable":
                    self.engine.message_log.add_message(
                        f"The {thrown_item.display_name} hits the wall and explodes!",
                        color.white,
                    )
                    self._apply_consumable_effect(thrown_item, None, final_x, final_y)
                    return
                self.engine.message_log.add_message(
                    f"The {thrown_item.display_name} breaks against the wall!",
                    color.white,
                )
                return

        # Bombs always explode at their final position
        if thrown_item.consumable and thrown_item.consumable.__class__.__name__ == "BombConsumable":
            self._apply_consumable_effect(thrown_item, None, final_x, final_y)
            return

        self._place_thrown_item(thrown_item, final_x, final_y, game_map)
