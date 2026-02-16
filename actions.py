from __future__ import annotations

import math
import random
from typing import Optional, Tuple, TYPE_CHECKING

import color
import exceptions
import options
import tile_types

if TYPE_CHECKING:
    from engine import Engine
    from entity import Actor, Entity, Item

def compute_damage(attack_power, defense, crit_chance=0.05, crit_mult=1.5):
    is_crit = False
    damage = attack_power - defense
    if random.random() <= crit_chance:
        is_crit = True
        damage *= crit_mult
        if damage <= 0:
            damage = 1
    return math.ceil(damage), is_crit

class Action:
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


class WishAction(Action):
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
                f"You wished for a {item.name}, but your inventory is full!", color.impossible
            )
        else:
            self.engine.message_log.add_message(
                f"You wished for a {item.name}!", color.status_effect_applied
            )
        self.wand_item.consumable.consume()


class PickupAction(Action):
    """Pickup an item and add it to the inventory, if there is room for it."""

    def __init__(self, entity: Actor):
        super().__init__(entity)

    def perform(self) -> None:
        actor_location_x = self.entity.x
        actor_location_y = self.entity.y
        inventory = self.entity.inventory

        items_here = [
            item for item in self.engine.game_map.items
            if item.x == actor_location_x and item.y == actor_location_y
        ]

        if not items_here:
            raise exceptions.Impossible("There is nothing here to pick up.")

        for item in items_here:
            can_stack = item.stackable and inventory.find_stack(item.name) is not None
            if not can_stack and len(inventory.items) >= inventory.capacity:
                self.engine.message_log.add_message("Your inventory is full.", color.impossible)
                break

            pickup_count = item.stack_count
            self.engine.game_map.entities.remove(item)
            item.parent = self.entity.inventory
            inventory.add(item)

            count_text = f" (x{pickup_count})" if item.stackable and pickup_count > 1 else ""
            self.engine.message_log.add_message(f"You picked up the {item.name}{count_text}!")


class ItemAction(Action):
    def __init__(
        self, entity: Actor, item: Item, target_xy: Optional[Tuple[int, int]] = None
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
        """Invoke the items ability, this action will be given to provide context."""
        if self.item.consumable:
            self.item.consumable.activate(self)

class DropItem(ItemAction):
    def __init__(
        self, entity: Actor, item: Item, target_xy: Optional[Tuple[int, int]] = None, count: int = 0
    ):
        super().__init__(entity, item, target_xy)
        self.count = count

    def perform(self) -> None:
        if self.entity.equipment.item_is_equipped(self.item):
            self.entity.equipment.toggle_equip(self.item)

        self.entity.inventory.drop(self.item, self.count)

class EquipAction(Action):
    def __init__(self, entity: Actor, item: Item):
        super().__init__(entity)

        self.item = item

    def perform(self) -> None:
        self.entity.equipment.toggle_equip(self.item)


class OpenAction(Action):
    def perform(self) -> None:
        x, y = self.entity.x, self.entity.y
        for entity in self.engine.game_map.entities:
            if entity.x == x and entity.y == y and hasattr(entity, 'open'):
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
        import tile_types

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
        import tile_types

        if not self.engine.game_map.in_bounds(self.x, self.y):
            raise exceptions.Impossible("There is no door there.")

        # Check if there's a blocking entity at the door location
        if self.engine.game_map.get_blocking_entity_at_location(self.x, self.y):
            raise exceptions.Impossible("Something is blocking the door.")

        tile = self.engine.game_map.tiles[self.x, self.y]
        if tile == tile_types.door_open:
            self.engine.game_map.tiles[self.x, self.y] = tile_types.door_closed
            self.engine.message_log.add_message("You close the door.", color.white)
        else:
            raise exceptions.Impossible("There is no open door there.")


class WaitAction(Action):
    def perform(self) -> None:
        pass

class TakeStairsAction(Action):
    def perform(self) -> None:
        """
        Take the stairs, if any exist at the entity's location.
        """
        if (self.entity.x, self.entity.y) == self.engine.game_map.downstairs_location:
            self.engine.game_world.generate_floor()
            self.engine.message_log.add_message(
                "You descend the staircase.", color.descend
            )
        else:
            raise exceptions.Impossible("There are no stairs here.")

class TakeUpStairsAction(Action):
    def perform(self) -> None:
        if (self.entity.x, self.entity.y) == self.engine.game_map.upstairs_location:
            if self.engine.game_world.current_floor <= 1:
                raise exceptions.Impossible("You cannot go further up.")
            self.engine.game_world.generate_floor(direction=-1)
            self.engine.message_log.add_message(
                "You ascend the staircase.", color.ascend
            )
        else:
            raise exceptions.Impossible("There are no stairs here.")

class ActionWithDirection(Action):
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
        """Return the blocking entity at this actions destination.."""
        return self.engine.game_map.get_blocking_entity_at_location(*self.dest_xy)

    @property
    def target_actor(self) -> Optional[Actor]:
        """Return the actor at this actions destination."""
        return self.engine.game_map.get_actor_at_location(*self.dest_xy)

    def perform(self) -> None:
        raise NotImplementedError()


class MeleeAction(ActionWithDirection):
    def perform(self) -> None:
        target = self.target_actor
        if not target:
            raise exceptions.Impossible("Nothing to attack.")

        if self.entity.name == "Dragon" or self.entity.name == "Ender Dragon" or self.entity.name == "Hydra":
            crit_chance = 0.3
        else:
            crit_chance = 0.05
        damage, is_crit = compute_damage(self.entity.fighter.power, target.fighter.defense, crit_chance)
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
                f"{attack_desc} for {damage} hit points{crit_text}.", attack_color
            )
            target.fighter.hp -= damage
        else:
            self.engine.message_log.add_message(
                f"{attack_desc} but does no damage.", attack_color
            )

class RangedAttackAction(ActionWithDirection):
    def perform(self) -> None:
        target = self.engine.player
        damage, is_crit = compute_damage(self.entity.fighter.power, target.fighter.defense)

        attack_desc = f"{self.entity.name.capitalize()} zaps {target.name}"
        crit_text = ""
        attack_color = color.enemy_atk
        if is_crit:
            attack_color = color.crit_atk
            crit_text = " [CRIT!]"

        if damage > 0:
            self.engine.message_log.add_message(
                f"{attack_desc} for {damage} hit points.{crit_text}", attack_color
            )
            target.fighter.hp -= damage
        else:
            self.engine.message_log.add_message(
                f"{attack_desc} but does no damage.", attack_color
            )


class MovementAction(ActionWithDirection):
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
    def perform(self) -> None:
        if self.target_actor:
            return MeleeAction(self.entity, self.dx, self.dy).perform()

        dest_x, dest_y = self.dest_xy
        if self.engine.game_map.in_bounds(dest_x, dest_y):
            if (dest_x, dest_y) in self.engine.game_map.secret_doors:
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
                return OpenDoorAction(self.entity, dest_x, dest_y).perform()

        return MovementAction(self.entity, self.dx, self.dy).perform()

class MovementRepeatedAction(MovementAction):
    def _walkable(self, x, y):
        gm = self.engine.game_map
        return gm.in_bounds(x, y) and gm.tiles["walkable"][x, y]

    def _find_corridor_turn(self):
        """If the player is in a corridor, return the unique continuation direction."""
        px, py = self.entity.x, self.entity.y
        cardinal = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        backward = (-self.dx, -self.dy)

        # Don't follow turns near open areas (e.g. room corners).
        for d in cardinal:
            nx, ny = px + d[0], py + d[1]
            if self._walkable(nx, ny):
                if sum(1 for dd in cardinal if self._walkable(nx + dd[0], ny + dd[1])) >= 3:
                    return None

        options = [
            d for d in cardinal
            if d != backward and self._walkable(px + d[0], py + d[1])
        ]

        if len(options) == 1:
            return options[0]
        return None

    def perform(self):
        # First, check if any monsters are visible (in which case do NOT move).
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
    """Repeated movement that stops at intersections and side passages."""

    def __init__(self, entity: Actor, dx: int, dy: int):
        super().__init__(entity, dx, dy)
        self._has_moved = False

    def _walkable(self, x, y):
        gm = self.engine.game_map
        return gm.in_bounds(x, y) and gm.tiles["walkable"][x, y]

    def _on_interesting_tile(self) -> bool:
        """True if the entity is standing on a notable dungeon feature or item."""
        import tile_types
        tile = self.engine.game_map.tiles[self.entity.x, self.entity.y]
        if any(tile == t for t in tile_types.interesting_tiles):
            return True
        px, py = self.entity.x, self.entity.y
        return any(item.x == px and item.y == py for item in self.engine.game_map.items)

    def _find_corridor_turn(self):
        """If the player is in a corridor, return the unique continuation direction.

        Looks at walkable cardinal neighbors, excludes the backward direction,
        and returns (dx, dy) if exactly one forward/side option remains.
        Returns None at dead ends, T-junctions, or open areas.
        """
        px, py = self.entity.x, self.entity.y
        cardinal = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        backward = (-self.dx, -self.dy)

        # Don't follow turns near open areas (e.g. room corners).
        for d in cardinal:
            nx, ny = px + d[0], py + d[1]
            if self._walkable(nx, ny):
                if sum(1 for dd in cardinal if self._walkable(nx + dd[0], ny + dd[1])) >= 3:
                    return None

        options = [
            d for d in cardinal
            if d != backward and self._walkable(px + d[0], py + d[1])
        ]

        if len(options) == 1:
            return options[0]
        return None

    def perform(self):
        if self.engine.game_map.any_monsters_visible():
            return None

        px, py = self.entity.x, self.entity.y
        cardinal = [(1, 0), (-1, 0), (0, 1), (0, -1)]

        # If already in an open room, just run until wall/monster.
        current_neighbors = sum(1 for d in cardinal if self._walkable(px + d[0], py + d[1]))
        if current_neighbors >= 3:
            try:
                super().perform()
                if self._on_interesting_tile():
                    return None
                return True
            except exceptions.Impossible:
                return None

        dest_x, dest_y = self.dest_xy

        dest_neighbors = sum(1 for d in cardinal if self._walkable(dest_x + d[0], dest_y + d[1]))
        if dest_neighbors >= 3:
            if not self._has_moved:
                # First step from corridor into room: enter and keep running.
                try:
                    super().perform()
                    self._has_moved = True
                    if self._on_interesting_tile():
                        return None
                    return True
                except exceptions.Impossible:
                    return None
            else:
                # Was running through corridor; stop at boundary.
                return None

        # If the destination ahead is blocked, try to follow a corridor turn.
        if not self._walkable(dest_x, dest_y):
            turn = self._find_corridor_turn()
            if turn is None:
                return None
            self.dx, self.dy = turn
            dest_x, dest_y = self.dest_xy

            # Re-check: the new destination must also be a corridor tile.
            dest_neighbors = sum(1 for d in cardinal if self._walkable(dest_x + d[0], dest_y + d[1]))
            if dest_neighbors >= 3:
                if not self._has_moved:
                    try:
                        super().perform()
                        self._has_moved = True
                        if self._on_interesting_tile():
                            return None
                        return True
                    except exceptions.Impossible:
                        return None
                else:
                    return None

        try:
            super().perform()
            self._has_moved = True
        except exceptions.Impossible:
            return None

        if self._on_interesting_tile():
            return None
        return True


class TargetMovementAction(Action):
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
