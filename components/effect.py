"""Component for temporary status effects that apply per-turn and expire."""

from __future__ import annotations

from typing import TYPE_CHECKING

from components.base_component import BaseComponent

if TYPE_CHECKING:
    from engine import Engine
    from entity import Actor


class TimedEffect(BaseComponent):
    """Base class for temporary effects that tick down each turn and can expire."""
    parent: Actor
    name = "<unknown>"

    def __init__(self, engine: "Engine"):  # pylint: disable=unused-argument
        self.max_turns = 0
        self.turns_left = 0

    def activate(self) -> None:
        """Start the effect by setting the remaining turns to the maximum."""
        self.turns_left = self.max_turns

    def apply_turn(self) -> None:
        """Decrement duration and expire when time runs out."""
        self.turns_left -= 1
        if self.turns_left <= 0:
            self.expire()

    def expire(self) -> None:
        """Remove this effect from the parent. Subclasses should clean up before calling super."""
        self.parent.effects.remove(self)


class FlagEffect(TimedEffect):
    """Timed effect that toggles a boolean flag on the parent actor.

    Subclasses set ``flag_name`` and ``name`` as class attributes.
    Override ``expire()`` to add a message, calling ``super().expire()`` first.
    """
    flag_name: str  # Subclass must set

    def __init__(self, engine: "Engine", duration: int):
        super().__init__(engine)
        self.max_turns = duration

    def activate(self) -> None:
        super().activate()
        setattr(self.parent, self.flag_name, True)

    def expire(self) -> None:
        setattr(self.parent, self.flag_name, False)
        super().expire()


class RageEffect(TimedEffect):
    """Increases damage output for a limited duration."""
    name = "Rage"

    def __init__(self, engine: "Engine", dmg_mult: float, duration: int):
        super().__init__(engine)
        self.max_turns = duration
        self.dmg_mult = dmg_mult

    def activate(self) -> None:
        super().activate()
        self.parent.fighter.base_power *= self.dmg_mult

    def expire(self) -> None:
        self.parent.fighter.base_power = round(
            self.parent.fighter.base_power / self.dmg_mult
        )
        super().expire()


class InvisibilityEffect(FlagEffect):
    """Makes the actor invisible to enemies while active."""
    name = "Invisible"
    flag_name = "is_invisible"


class SpeedEffect(FlagEffect):
    """Doubles the actor's movement and action speed."""
    name = "Haste"
    flag_name = "is_hasted"

    def expire(self) -> None:
        super().expire()
        self.engine.message_log.add_message(
            "You feel yourself slowing down.", (0x80, 0x80, 0x80)
        )


class DetectMonsterEffect(FlagEffect):
    """Reveals the location of all monsters on the map."""
    name = "Detect Monster"
    flag_name = "is_detecting_monsters"

    def expire(self) -> None:
        super().expire()
        self.engine.message_log.add_message(
            "Your monster sense fades.", (0x80, 0x80, 0x80)
        )


class DetectItemEffect(FlagEffect):
    """Reveals the location of all items on the map."""
    name = "Detect Items"
    flag_name = "is_detecting_items"

    def expire(self) -> None:
        super().expire()
        self.engine.message_log.add_message(
            "Your item sense fades.", (0x80, 0x80, 0x80)
        )


class SleepEffect(FlagEffect):
    """Puts the actor to sleep for a duration; wakes up if attacked."""
    name = "Sleep"
    flag_name = "is_asleep"

    def expire(self) -> None:
        super().expire()
        if self.parent is self.engine.player:
            self.engine.message_log.add_message(
                "You wake up!", (0xFF, 0xFF, 0xFF)
            )
        else:
            self.engine.message_log.add_message(
                f"The {self.parent.name} wakes up!", (0xFF, 0xFF, 0xFF)
            )


class BlindnessEffect(FlagEffect):
    """Blinds the actor, preventing them from seeing."""
    name = "Blindness"
    flag_name = "is_blind"

    def expire(self) -> None:
        super().expire()
        if self.parent is self.engine.player:
            self.engine.message_log.add_message(
                "You can see again!", (0xFF, 0xFF, 0xFF)
            )
        else:
            self.engine.message_log.add_message(
                f"The {self.parent.name} can see again!", (0xFF, 0xFF, 0xFF)
            )
