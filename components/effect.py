"""Component for temporary status effects that apply per-turn and expire."""

from __future__ import annotations

from typing import TYPE_CHECKING

from components.base_component import BaseComponent

if TYPE_CHECKING:
    from entity import Actor


class TimedEffect(BaseComponent):
    """Base class for temporary effects that tick down each turn and can expire."""
    parent: Actor

    def __init__(self, engine: Engine):
        self.max_turns = 0
        self.turns_left = 0
        self.name = "<unknown>"

    def activate(self) -> None:
        self.turns_left = self.max_turns

    def apply_turn(self):
        """Decrement duration and expire when time runs out."""
        self.turns_left -= 1
        if self.turns_left <= 0:
            self.expire()

    def expire(self):
        """Called when the effect's duration expires; can be overridden for cleanup."""
        pass


class RageEffect(TimedEffect):
    """Increases damage output for a limited duration."""
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
    """Makes the actor invisible to enemies while active."""

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
    """Doubles the actor's movement and action speed."""

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


class DetectMonsterEffect(TimedEffect):
    """Reveals the location of all monsters on the map."""

    def __init__(self, engine: Engine, duration: int):
        super().__init__(engine)
        self.max_turns = duration
        self.name = "Detect Monster"

    def activate(self):
        super().activate()
        self.parent.is_detecting_monsters = True

    def expire(self):
        super().expire()
        self.parent.is_detecting_monsters = False
        self.parent.effects.remove(self)
        self.engine.message_log.add_message(
            "Your monster sense fades.", (0x80, 0x80, 0x80)
        )


class SleepEffect(TimedEffect):
    """Puts the actor to sleep for a duration; wakes up if attacked."""

    def __init__(self, engine: Engine, duration: int):
        super().__init__(engine)
        self.max_turns = duration
        self.name = "Sleep"

    def activate(self):
        super().activate()
        self.parent.is_asleep = True

    def expire(self):
        super().expire()
        self.parent.is_asleep = False
        self.parent.effects.remove(self)
        if self.parent is self.engine.player:
            self.engine.message_log.add_message(
                "You wake up!", (0xFF, 0xFF, 0xFF)
            )
        else:
            self.engine.message_log.add_message(
                f"The {self.parent.name} wakes up!", (0xFF, 0xFF, 0xFF)
            )
