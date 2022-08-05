from __future__ import annotations

from typing import List, TYPE_CHECKING

from components.base_component import BaseComponent

if TYPE_CHECKING:
    from entity import Actor, Item


class Effect(BaseComponent):
    parent: Actor

    def __init__(self):
        self.max_turns = 0
        self.turns_left = 0

    def activitate(self) -> None:
        self.turns_left = self.max_turns

    def apply_turn(self):
        """Perform any per-turn effect."""
        self.turns_left -= 1
        if self.turns_left <= 0:
            self.expire()

    def expire(self):
        """Action to perform once effect wears off."""
        pass

class RageEffect(Effect):
    def __init__(self, dmg_mult: float, duration: int):
        super().__init__()
        self.max_turns = duration
        self.dmg_mult = dmg_mult

    def activate(self):
        super().activitate()
        self.parent.fighter.base_power *= self.dmg_mult

    def expire(self):
        super().expire()
        self.parent.fighter.base_power = round(self.parent.fighter.base_power / self.dmg_mult)
        self.parent.effects.remove(self)