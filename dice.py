"""Dice rolling utilities using D&D notation (e.g. '2d6')."""
import random


def parse(dice_str) -> (int, int):
    """Parse a dice string like '2d6' into (count, sides)."""
    n, sides = dice_str.split("d")
    return int(n), int(sides)


def roll(dice_str) -> int:
    """Roll dice described by dice_str and return the total."""
    n, sides = parse(dice_str)
    return sum(random.randint(1, sides) for i in range(n))
