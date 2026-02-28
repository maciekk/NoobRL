#!/usr/bin/env python3
# pylint: disable=invalid-name,duplicate-code,cyclic-import
"""Weapon vs armor damage simulation tool."""

import os.path
import sys

# Enable loading modules from parent directory.
sys.path.insert(1, os.path.join(sys.path[0], ".."))

import dice  # pylint: disable=wrong-import-position


def histogram(values):
    """Print an ASCII histogram of value frequencies."""
    bar_char = "="
    d = {}
    for v in values:
        if v in d:
            d[v] += bar_char
        else:
            d[v] = bar_char

    for v in sorted(d.keys()):
        print(f"{v} | {d[v]}")


def stem_and_leaf_plot(values):
    """Print a stem-and-leaf plot of the given values."""
    d = {}
    for v in values:
        stem = v // 10
        if stem in d:
            d[stem] += str(v % 10)
        else:
            d[stem] = str(v % 10)
    for stem in sorted(d.keys()):
        print(f"{stem} | {''.join(sorted(d[stem]))}")


class Match:
    """Simulate rounds of combat between a weapon and armor roll."""

    def __init__(self, hp, armor, weapon):
        """Initialize a match with starting HP, armor dice string, and weapon dice string."""
        self.hp = hp
        self.armor = armor
        self.weapon = weapon
        self.history_dmg = []
        self.history_hp = []

    def round(self):
        """Simulate one round of combat."""
        w = dice.roll(self.weapon)
        a = dice.roll(self.armor)
        dmg = max(w - a, 0)
        self.history_dmg.append(dmg)

        self.hp = max(0, self.hp - dmg)
        self.history_hp.append(self.hp)

        if dmg > 0:
            dmg_str = f"(-{dmg})"
        else:
            dmg_str = "    "
        print(f"HP: {self.hp:2d}  {dmg_str} [{w}->{a}]")

        if self.hp <= 0:
            print("DEATH!!!")

    def until_death(self):
        """Run rounds until hp reaches zero, then print damage histogram."""
        while self.hp > 0:
            self.round()

        # Report some stats
        print()
        print("Damage history: ")
        histogram(self.history_dmg)
        # print("HP history: ")
        # stem_and_leaf_plot(self.history_hp)


def main() -> None:
    """Entry point: run a default simulation."""
    m = Match(hp=100, armor="1d8", weapon="1d7")
    m.until_death()


if __name__ == "__main__":
    main()
