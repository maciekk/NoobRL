"""Artificial intelligence behavior for enemies and effects."""

from __future__ import annotations

import random
from typing import List, Optional, Tuple, TYPE_CHECKING

import numpy as np

import color
import tile_types
from exceptions import Impossible
from actions import (
    Action,
    BumpAction,
    MeleeAction,
    MovementAction,
    RangedAttackAction,
    OpenDoorAction,
)

if TYPE_CHECKING:
    from entity import Actor


class BaseAI(Action):
    """Base class for AI behaviors that act as actions on entities."""
    def perform(self) -> None:
        raise NotImplementedError()

    def _wander_randomly(self) -> None:
        """Move in a random direction (Brownian motion). Just moves; doesn't attack."""
        direction_x, direction_y = random.choice(
            [
                (-1, -1),  # Northwest
                (0, -1),   # North
                (1, -1),   # Northeast
                (-1, 0),   # West
                (1, 0),    # East
                (-1, 1),   # Southwest
                (0, 1),    # South
                (1, 1),    # Southeast
            ]
        )
        try:
            MovementAction(self.entity, direction_x, direction_y).perform()
        except Impossible:
            pass


class ConfusedEnemy(BaseAI):
    """A confused enemy stumbles aimlessly for a set number of turns,
    then reverts to its previous AI. Attacks if it randomly moves into an actor.
    """

    def __init__(
        self, entity: Actor, previous_ai: Optional[BaseAI], turns_remaining: int
    ):
        super().__init__(entity)

        self.previous_ai = previous_ai
        self.turns_remaining = turns_remaining

    def perform(self) -> None:
        # Asleep entities don't act even if confused
        if self.entity.is_asleep:
            return

        # Revert the AI back to the original state if the effect has run its course.
        if self.turns_remaining <= 0:
            self.engine.message_log.add_message(
                f"The {self.entity.name} is no longer confused."
            )
            self.entity.ai = self.previous_ai
        else:
            # Pick a random direction
            direction_x, direction_y = random.choice(
                [
                    (-1, -1),  # Northwest
                    (0, -1),  # North
                    (1, -1),  # Northeast
                    (-1, 0),  # West
                    (1, 0),  # East
                    (-1, 1),  # Southwest
                    (0, 1),  # South
                    (1, 1),  # Southeast
                ]
            )

            self.turns_remaining -= 1

            # The actor will either try to move or attack in the chosen random direction.
            # Its possible the actor will just bump into the wall, wasting a turn.
            BumpAction(
                self.entity,
                direction_x,
                direction_y,
            ).perform()


class ExplodingCorpseAI(BaseAI):
    """AI for a dead Puffball corpse counting down to explosion."""

    def __init__(self, entity: Actor, delay: int, radius: int, damage: int):
        super().__init__(entity)
        self.delay = delay
        self.radius = radius
        self.damage = damage

    def perform(self) -> None:
        self.delay -= 1
        if self.delay <= 0:
            self.explode()
        else:
            self.engine.message_log.add_message("Tick...", color.enemy_atk)

    def explode(self) -> None:
        """Explode, damaging all nearby actors and removing the corpse from the map."""
        engine = self.engine
        gamemap = engine.game_map
        x, y = self.entity.x, self.entity.y

        # Defuse self first to prevent re-triggering during chain reactions
        self.entity.ai = None

        engine.message_log.add_message("BOOM!", color.enemy_atk)
        engine.message_log.add_message(
            f"The {self.entity.name} explodes!", color.enemy_atk
        )

        # Damage all actors in radius (including player), excluding self
        for actor in set(gamemap.actors) | {engine.player}:
            if actor is self.entity:
                continue
            if actor.distance(x, y) <= self.radius:
                engine.message_log.add_message(
                    f"The {actor.name} is hit by the explosion for {self.damage} damage!",
                    color.enemy_atk,
                )
                actor.fighter.take_damage(self.damage)

        # Remove the corpse from the map
        if self.entity in gamemap.entities:
            gamemap.entities.remove(self.entity)


class HostileEnemy(BaseAI):
    """Standard monster AI that uses pathfinding to chase and attack the player."""

    def __init__(self, entity: Actor):
        super().__init__(entity)
        self.path: List[Tuple[int, int]] = []
        self.last_known_target: Optional[Tuple[int, int]] = None

    def _try_wizard_door(self, dest_x: int, dest_y: int) -> bool:
        """Open a door if this is a Wizard and the destination is a closed door."""
        if (self.entity.name == "Wizard"
                and self.engine.game_map.tiles[dest_x, dest_y] == tile_types.door_closed):
            OpenDoorAction(self.entity, dest_x, dest_y).perform()
            return True
        return False

    def perform(self) -> None:
        # Asleep or blind entities don't act
        if self.entity.is_asleep:
            return

        if self.entity.is_blind:
            # Blind entities wander randomly
            self._wander_randomly()
            return

        target = self.engine.player
        dx = target.x - self.entity.x
        dy = target.y - self.entity.y
        distance = max(abs(dx), abs(dy))  # Chebyshev distance.

        if (
            self.engine.game_map.visible[self.entity.x, self.entity.y]
            and not self.engine.player.is_invisible
            and distance <= self.entity.sight_range
        ):
            # Give actor chance to notice player, if that has not happened yet.
            if not self.entity.noticed_player:
                self.entity.noticed_player = True
                spotted_messages = {
                    "Dragon": ("You have been spotted by a dragon!", color.dragon_roar),
                    "Ender Dragon": (
                        "You have been spotted by an ender dragon!",
                        color.dragon_roar_end,
                    ),
                    "Hydra": ("You have been spotted by a hydra!", color.hydra_roar),
                }
                if self.entity.name in spotted_messages:
                    dragon_message, dragon_message_color = spotted_messages[self.entity.name]
                    self.engine.message_log.add_message(dragon_message, dragon_message_color)

            self.last_known_target = (target.x, target.y)

            if distance <= self.entity.attack_range:
                if self.entity.ranged_attack:
                    RangedAttackAction(self.entity, dx, dy).perform()
                    return
                MeleeAction(self.entity, dx, dy).perform()
                return

            self.path = self.entity.get_path_to(target.x, target.y)

        elif self.last_known_target:
            if (self.entity.x, self.entity.y) == self.last_known_target:
                self.last_known_target = None
                self.path = []
            else:
                self.path = self.entity.get_path_to(*self.last_known_target)

        if self.path:
            dest_x, dest_y = self.path.pop(0)
            if self._try_wizard_door(dest_x, dest_y):
                return
            MovementAction(
                self.entity,
                dest_x - self.entity.x,
                dest_y - self.entity.y,
            ).perform()
            return

        # No path and not aware of player: wander randomly
        self._wander_randomly()


class PatrollingEnemy(BaseAI):
    """AI that patrols between random dungeon locations.

    Picks a random walkable tile, paths to it, wanders for WANDER_TURNS turns,
    then picks a new destination. Attacks the player on sight.
    """

    WANDER_TURNS = 10

    def __init__(self, entity: Actor):
        super().__init__(entity)
        self.path: List[Tuple[int, int]] = []
        self.patrol_target: Optional[Tuple[int, int]] = None
        self.wander_turns: int = 0

    def _pick_patrol_target(self) -> Optional[Tuple[int, int]]:
        """Pick a random walkable tile on the current map."""
        coords = np.argwhere(self.engine.game_map.tiles["walkable"])
        if len(coords) == 0:
            return None
        x, y = coords[random.randrange(len(coords))]
        return int(x), int(y)

    def perform(self) -> None:
        if self.entity.is_asleep:
            return

        if self.entity.is_blind:
            self._wander_randomly()
            return

        target = self.engine.player
        dx = target.x - self.entity.x
        dy = target.y - self.entity.y
        distance = max(abs(dx), abs(dy))

        # Chase and attack if player is visible
        if (
            self.engine.game_map.visible[self.entity.x, self.entity.y]
            and not self.engine.player.is_invisible
            and distance <= self.entity.sight_range
        ):
            if distance <= self.entity.attack_range:
                if self.entity.ranged_attack:
                    RangedAttackAction(self.entity, dx, dy).perform()
                    return
                MeleeAction(self.entity, dx, dy).perform()
                return

            self.path = self.entity.get_path_to(target.x, target.y)
            if self.path:
                dest_x, dest_y = self.path.pop(0)
                MovementAction(
                    self.entity,
                    dest_x - self.entity.x,
                    dest_y - self.entity.y,
                ).perform()
            return

        # Arrived at patrol target: wander for a while
        if self.wander_turns > 0:
            self.wander_turns -= 1
            self._wander_randomly()
            return

        # Pick a new patrol target if we don't have one
        if self.patrol_target is None:
            self.patrol_target = self._pick_patrol_target()
            self.path = []

        if self.patrol_target is not None:
            tx, ty = self.patrol_target
            if (self.entity.x, self.entity.y) == (tx, ty):
                self.patrol_target = None
                self.wander_turns = self.WANDER_TURNS
                self._wander_randomly()
                return

            if not self.path:
                self.path = self.entity.get_path_to(tx, ty)

            if self.path:
                dest_x, dest_y = self.path.pop(0)
                MovementAction(
                    self.entity,
                    dest_x - self.entity.x,
                    dest_y - self.entity.y,
                ).perform()
                return

            # Can't reach target; pick a new one next turn
            self.patrol_target = None

        self._wander_randomly()
