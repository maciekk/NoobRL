from __future__ import annotations

import random
from typing import Optional, TYPE_CHECKING
import numpy as np
import actions
import color
import components.ai
from components.effect import InvisibilityEffect, RageEffect
import components.inventory
from components.base_component import BaseComponent
from exceptions import Impossible
from input_handlers import (
    ActionOrHandler,
    AreaRangedAttackHandler,
    SingleRangedAttackHandler,
    WishItemHandler,
)

if TYPE_CHECKING:
    from entity import Actor, Item


class Consumable(BaseComponent):
    parent: Item

    def get_action(self, consumer: Actor) -> Optional[ActionOrHandler]:
        """Try to return the action for this item."""
        return actions.ItemAction(consumer, self.parent)

    def activate(self, action: actions.ItemAction) -> None:
        """Invoke this item's ability.
        `action` is the context for this activation.
        """
        raise NotImplementedError()

    def get_description(self) -> list[str]:
        """Return description lines for the item detail screen."""
        return []

    def consume(self) -> None:
        """Decrement stack count; remove when it reaches 0."""
        entity = self.parent
        inventory = entity.parent
        if isinstance(inventory, components.inventory.Inventory):
            entity.stack_count -= 1
            if entity.stack_count <= 0:
                inventory.items.remove(entity)


class WishingWandConsumable(Consumable):
    def get_description(self) -> list[str]:
        return ["Grants a wish for any item"]

    def get_action(self, consumer: Actor) -> WishItemHandler:
        self.engine.message_log.add_message(
            "What do you wish for?", color.needs_target
        )
        return WishItemHandler(self.engine, self.parent)


class ConfusionConsumable(Consumable):
    def __init__(self, number_of_turns: int):
        self.number_of_turns = number_of_turns

    def get_description(self) -> list[str]:
        return [f"Confuses target for {self.number_of_turns} turns"]

    def get_action(self, consumer: Actor) -> SingleRangedAttackHandler:
        self.engine.message_log.add_message(
            "Select a target location.", color.needs_target
        )
        return SingleRangedAttackHandler(
            self.engine,
            callback=lambda xy: actions.ItemAction(consumer, self.parent, xy),
        )

    def activate(self, action: actions.ItemAction) -> None:
        consumer = action.entity
        target = action.target_actor

        if not self.engine.game_map.visible[action.target_xy]:
            raise Impossible("You cannot target an area that you cannot see.")
        if not target:
            raise Impossible("You must select an enemy to target.")
        if target is consumer:
            raise Impossible("You cannot confuse yourself!")

        self.engine.message_log.add_message(
            f"The eyes of the {target.name} look vacant, as it starts to stumble around!",
            color.status_effect_applied,
        )
        target.ai = components.ai.ConfusedEnemy(
            entity=target, previous_ai=target.ai, turns_remaining=self.number_of_turns,
        )
        self.consume()


class HealingConsumable(Consumable):
    def __init__(self, amount: int):
        self.amount = amount

    def get_description(self) -> list[str]:
        return [f"Restores up to {self.amount} HP"]

    def activate(self, action: actions.ItemAction) -> None:
        consumer = action.entity
        amount_recovered = consumer.fighter.heal(self.amount)

        if amount_recovered > 0:
            self.engine.message_log.add_message(
                f"You consume the {self.parent.name}, and recover {amount_recovered} HP!",
                color.health_recovered,
            )
            self.consume()
        else:
            raise Impossible(f"Your health is already full.")


class RageConsumable(Consumable):
    def __init__(self, amount: int):
        self.amount = amount

    def get_description(self) -> list[str]:
        return [f"Increases damage by +1 for 10 turns"]

    def activate(self, action: actions.ItemAction) -> None:
        consumer = action.entity
        eff = RageEffect(engine= self.engine, dmg_mult=self.amount, duration=10)
        consumer.effects.append(eff)
        eff.parent = consumer
        self.engine.message_log.add_message(
            f"You are filled in with rage! (Damage increased by +1)",
            color.damage_increased
        )
        eff.activate()
        self.consume()


class InvisibilityConsumable(Consumable):
    def __init__(self, duration: int):
        self.duration = duration

    def get_description(self) -> list[str]:
        return [f"Grants invisibility for {self.duration} turns"]

    def activate(self, action: actions.ItemAction) -> None:
        consumer = action.entity
        eff = InvisibilityEffect(engine=self.engine, duration=self.duration)
        consumer.effects.append(eff)
        eff.parent = consumer
        self.engine.message_log.add_message(
            "You fade from sight!",
            color.status_effect_applied,
        )
        eff.activate()
        self.consume()


class BlinkConsumable(Consumable):
    def get_description(self) -> list[str]:
        return ["Teleports randomly up to 5 tiles"]

    def activate(self, action: actions.ItemAction) -> None:
        max_range = 5  # TODO: parametrize this (JSON, etc)

        # TODO: make this more robust; e.g., ask GameMap to give you all possible free locations within max_range.
        max_tries = 10
        for i in range(max_tries):
            dx, dy = random.randint(-max_range, max_range), random.randint(-max_range, max_range)
            x = self.engine.player.x + dx
            y = self.engine.player.y + dy
            # TODO: check for out of bounds (x,y)
            if (self.engine.game_map.tiles["walkable"][x, y] and
                    self.engine.game_map.get_blocking_entity_at_location(x, y) is None):
                self.engine.message_log.add_message("You blinked.")
                self.engine.player.x, self.engine.player.y = x, y
                self.consume()
                return
        self.engine.message_log.add_message("Mysterious force prevents you from blinking.")


class FireballDamageConsumable(Consumable):
    def __init__(self, damage: int, radius: int):
        self.damage = damage
        self.radius = radius

    def get_description(self) -> list[str]:
        return [f"Deals {self.damage} damage in radius {self.radius}"]

    def get_action(self, consumer: Actor) -> AreaRangedAttackHandler:
        self.engine.message_log.add_message(
            "Select a target location.", color.needs_target
        )
        return AreaRangedAttackHandler(
            self.engine,
            radius=self.radius,
            callback=lambda xy: actions.ItemAction(consumer, self.parent, xy),
        )

    def activate(self, action: actions.ItemAction) -> None:
        target_xy = action.target_xy

        if not self.engine.game_map.visible[target_xy]:
            raise Impossible("You cannot target an area that you cannot see.")

        targets_hit = False
        for actor in self.engine.game_map.actors:
            if actor.distance(*target_xy) <= self.radius:
                self.engine.message_log.add_message(
                    f"The {actor.name} is engulfed in a fiery explosion, taking {self.damage} damage!"
                )
                actor.fighter.take_damage(self.damage)
                targets_hit = True

        if not targets_hit:
            raise Impossible("There are no targets in the radius.")
        self.consume()


def apply_clairvoyance(engine) -> None:
    """Reveal the dungeon layout (walls adjacent to walkable tiles)."""
    game_map = engine.game_map
    walkable = game_map.tiles["walkable"]
    reveal = walkable.copy()
    h, w = walkable.shape
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            if dx == 0 and dy == 0:
                continue
            shifted = np.roll(np.roll(walkable, dy, axis=0), dx, axis=1)
            # Zero out wrapped edges
            if dy == -1:
                shifted[-1, :] = False
            elif dy == 1:
                shifted[0, :] = False
            if dx == -1:
                shifted[:, -1] = False
            elif dx == 1:
                shifted[:, 0] = False
            reveal |= shifted
    game_map.revealed |= reveal
    engine.message_log.add_message(
        "The dungeon layout is revealed to you!",
        color.status_effect_applied,
    )


class ClairvoyanceConsumable(Consumable):
    def get_description(self) -> list[str]:
        return ["Reveals the dungeon layout"]

    def activate(self, action: actions.ItemAction) -> None:
        apply_clairvoyance(self.engine)
        self.consume()


class LightningDamageConsumable(Consumable):
    def __init__(self, damage: int, maximum_range: int):
        self.damage = damage
        self.maximum_range = maximum_range

    def get_description(self) -> list[str]:
        return [f"Deals {self.damage} damage to nearest enemy",
                f"Range: {self.maximum_range}"]

    def activate(self, action: actions.ItemAction) -> None:
        consumer = action.entity
        target = None
        closest_distance = self.maximum_range + 1.0

        for actor in self.engine.game_map.actors:
            if actor is not consumer and self.parent.gamemap.visible[actor.x, actor.y]:
                distance = consumer.distance(actor.x, actor.y)

                if distance < closest_distance:
                    target = actor
                    closest_distance = distance

        if target:
            self.engine.message_log.add_message(
                f"A lightning bolt strikes the {target.name} with a loud thunder, for {self.damage} damage!"
            )
            target.fighter.take_damage(self.damage)
            self.consume()
        else:
            raise Impossible("No enemy is close enough to strike.")
