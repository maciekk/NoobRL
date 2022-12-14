from __future__ import annotations

import random, color
from typing import List, Optional, Tuple, TYPE_CHECKING

import numpy as np  # type: ignore
import tcod

from actions import Action, BumpAction, MeleeAction, MovementAction, WaitAction, RangedAttackAction

if TYPE_CHECKING:
    from entity import Actor


class BaseAI(Action):
    def perform(self) -> None:
        raise NotImplementedError()


class ConfusedEnemy(BaseAI):
    """
    A confused enemy will stumble around aimlessly for a given number of turns, then revert back to its previous AI.
    If an actor occupies a tile it is randomly moving into, it will attack.
    """

    def __init__(
        self, entity: Actor, previous_ai: Optional[BaseAI], turns_remaining: int
    ):
        super().__init__(entity)

        self.previous_ai = previous_ai
        self.turns_remaining = turns_remaining

    def perform(self) -> None:
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
            return BumpAction(self.entity, direction_x, direction_y,).perform()

class HostileEnemy(BaseAI):
    def __init__(self, entity: Actor):
        super().__init__(entity)
        self.path: List[Tuple[int, int]] = []

    def perform(self) -> None:
        target = self.engine.player
        dx = target.x - self.entity.x
        dy = target.y - self.entity.y
        distance = max(abs(dx), abs(dy))  # Chebyshev distance.

        if self.engine.game_map.visible[self.entity.x, self.entity.y]:
            # Give actor chance to notice player, if that has not happened yet.
            if not self.entity.noticed_player:
                self.entity.noticed_player = True
                if self.entity.name == "Dragon":
                    Dragon_message = "You have been spotted by a dragon!"
                    Dragon_message_color = color.dragon_roar
                    self.engine.message_log.add_message(Dragon_message, Dragon_message_color)
                if self.entity.name == "Ender Dragon":
                    Dragon_message = "You have been spotted by an ender dragon!"
                    Dragon_message_color = color.dragon_roar_end
                    self.engine.message_log.add_message(Dragon_message, Dragon_message_color)
                if self.entity.name == "Hydra":
                    Dragon_message = "You have been spotted by a hydra!"
                    Dragon_message_color = color.hydra_roar
                    self.engine.message_log.add_message(Dragon_message, Dragon_message_color)
            if self.entity.name == "Wizard":
                if distance <= 3:
                    return RangedAttackAction(self.entity, dx, dy).perform()
            if self.entity.name == "Crawler":
                if distance <= 2:
                    return MeleeAction(self.entity, dx, dy).perform()

            if distance <= 1:
                return MeleeAction(self.entity, dx, dy).perform()

            self.path = self.entity.get_path_to(target.x, target.y)

        if self.path:
            dest_x, dest_y = self.path.pop(0)
            return MovementAction(
                self.entity, dest_x - self.entity.x, dest_y - self.entity.y,
            ).perform()

        return WaitAction(self.entity).perform()
