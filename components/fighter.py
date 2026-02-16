from __future__ import annotations

from typing import TYPE_CHECKING

import color, random
from components.base_component import BaseComponent
from render_order import RenderOrder

if TYPE_CHECKING:
    from entity import Actor


class Fighter(BaseComponent):
    parent: Actor

    def __init__(self, hp: int, base_defense: int, base_power: int):
        self.max_hp = hp
        self._hp = hp
        self.base_defense = base_defense
        self.base_power = base_power

    @property
    def hp(self) -> int:
        return self._hp

    @hp.setter
    def hp(self, value: int) -> None:
        self._hp = max(0, min(value, self.max_hp))
        if self._hp == 0 and self.parent.ai:
            self.die()

    @property
    def defense(self) -> int:
        return self.base_defense + self.defense_bonus

    @property
    def power(self) -> int:
        return self.base_power + self.power_bonus

    @property
    def defense_bonus(self) -> int:
        if self.parent.equipment:
            return self.parent.equipment.defense_bonus
        else:
            return 0

    @property
    def power_bonus(self) -> int:
        if self.parent.equipment:
            return self.parent.equipment.power_bonus
        else:
            return 0

    def die(self) -> None:
        # If already a corpse (e.g. exploding corpse hit by another explosion),
        # just defuse the AI and stop — no double death messages or XP.
        if self.parent.render_order == RenderOrder.CORPSE:
            self.parent.ai = None
            return

        # Add more to deathmessagelist
        deathmessagelist = [
            "impaled", "blown to smithereens", "sliced down", "beat to death", "butchered"
        ]
        if self.engine.player is self.parent:
            death_message = f"You were {deathmessagelist[random.randint(0, 3)]}. You are dead."
            death_message_color = color.player_die
        else:
            death_message = f"{self.parent.name} was {deathmessagelist[random.randint(0, 3)]}!"
            death_message_color = color.enemy_die
            kills = self.engine.kill_counts
            kills[self.parent.name] = kills.get(self.parent.name, 0) + 1

        original_name = self.parent.name

        self.parent.char = "%"
        self.parent.color = (191, 0, 0)
        self.parent.blocks_movement = False
        self.parent.name = f"remains of {self.parent.name}"
        self.parent.render_order = RenderOrder.CORPSE

        # Check for death explosion (e.g. Puffball)
        from components.ai import ExplodingCorpseAI
        if self.parent.death_explosion and not isinstance(self.parent.ai, ExplodingCorpseAI):
            self.parent.ai = ExplodingCorpseAI(
                self.parent, **self.parent.death_explosion
            )
            self.engine.message_log.add_message(
                f"The {original_name} begins to glow!", color.enemy_atk
            )
        else:
            self.parent.ai = None

        self.engine.message_log.add_message(death_message, death_message_color)

        self.engine.player.level.add_xp(self.parent.level.xp_given)

    def heal(self, amount: int) -> int:
        if self.hp == self.max_hp:
            return 0

        new_hp_value = self.hp + amount

        if new_hp_value > self.max_hp:
            new_hp_value = self.max_hp

        amount_recovered = new_hp_value - self.hp

        self.hp = new_hp_value

        return amount_recovered

    def take_damage(self, amount: int) -> None:
        self.hp -= amount
