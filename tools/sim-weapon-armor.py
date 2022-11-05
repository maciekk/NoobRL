#!/usr/bin/env python3

import os.path
import sys

# Enable loading modules from parent directory.
sys.path.insert(1, os.path.join(sys.path[0], '..'))

import dice


def histogram(values):
    BAR_CHAR = '='
    d = {}
    for v in values:
        if v in d:
            d[v] += BAR_CHAR
        else:
            d[v] = BAR_CHAR

    for v in sorted(d.keys()):
        print("%s | %s" % (v, d[v]))


def stem_and_leaf_plot(values):
    d = {}
    for v in values:
        stem = v//10
        if stem in d:
            d[stem] += str(v % 10)
        else:
            d[stem] = str(v % 10)
    for stem in sorted(d.keys()):
        print("%s | %s" % (stem, ''.join(sorted(d[stem]))))


class Match:
    def __init__(self, hp, armor, weapon):
        self.hp = hp
        self.armor = armor
        self.weapon = weapon
        self.history_dmg = []
        self.history_hp = []

    def round(self):
        w = dice.roll(self.weapon)
        a = dice.roll(self.armor)
        dmg = max(w - a, 0)
        self.history_dmg.append(dmg)

        self.hp = max(0, self.hp - dmg)
        self.history_hp.append(self.hp)

        if dmg > 0:
            dmg_str = "(-%d)" % (dmg,)
        else:
            dmg_str = '    '
        print("HP: %2d  %s [%d->%d]" % (self.hp, dmg_str, w, a))

        if self.hp <= 0:
            print("DEATH!!!")

    def until_death(self):
        while self.hp > 0:
            self.round()

        # Report some stats
        print()
        print("Damage history: ")
        histogram(self.history_dmg)
        #print("HP history: ")
        #stem_and_leaf_plot(self.history_hp)


def main() -> None:
    m = Match(hp=100, armor='1d8', weapon='1d7')
    m.until_death()


if __name__ == "__main__":
    main()
