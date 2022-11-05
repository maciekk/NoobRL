from typing import TYPE_CHECKING

import random

def parse(dice_str) -> (int, int):
    n, sides = dice_str.split('d')
    return int(n), int(sides)

def roll(dice_str) -> int:
    n, sides = parse(dice_str)
    return sum([random.randint(1, sides) for i in range(n)])

