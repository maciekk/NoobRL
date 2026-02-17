from __future__ import annotations

from typing import TYPE_CHECKING

from components.base_component import BaseComponent

if TYPE_CHECKING:
    from entity import Actor


class TimedEffect(BaseComponent):
    parent: Actor

    def __init__(self, engine: Engine):
        self.max_turns = 0
        self.turns_left = 0
        self.name = "<unknown>"

    def activate(self) -> None:
        self.turns_left = self.max_turns

    def apply_turn(self):
        """Perform any per-turn effect."""
        self.turns_left -= 1
        if self.turns_left <= 0:
            self.expire()

    def expire(self):
        """Action to perform once effect wears off."""
        pass


class RageEffect(TimedEffect):
    def __init__(self, engine: Engine, dmg_mult: float, duration: int):
        super().__init__(engine)
        self.max_turns = duration
        self.dmg_mult = dmg_mult
        self.name = "Rage"

    def activate(self):
        super().activate()
        self.parent.fighter.base_power *= self.dmg_mult

    def expire(self):
        super().expire()
        self.parent.fighter.base_power = round(
            self.parent.fighter.base_power / self.dmg_mult
        )
        self.parent.effects.remove(self)


class InvisibilityEffect(TimedEffect):
    def __init__(self, engine: Engine, duration: int):
        super().__init__(engine)
        self.max_turns = duration
        self.name = "Invisible"

    def activate(self):
        super().activate()
        self.parent.is_invisible = True

    def expire(self):
        super().expire()
        self.parent.is_invisible = False
        self.parent.effects.remove(self)


class SpeedEffect(TimedEffect):
    def __init__(self, engine: Engine, duration: int):
        super().__init__(engine)
        self.max_turns = duration
        self.name = "Haste"

    def activate(self):
        super().activate()
        self.parent.is_hasted = True

    def expire(self):
        super().expire()
        self.parent.is_hasted = False
        self.parent.effects.remove(self)
        self.engine.message_log.add_message(
            "You feel yourself slowing down.", (0x80, 0x80, 0x80)
        )
