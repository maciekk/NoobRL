"""Shared key maps and modifier helpers."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import tcod  # pylint: disable=import-error

MOVE_KEYS = {
    tcod.event.KeySym.UP: (0, -1),
    tcod.event.KeySym.DOWN: (0, 1),
    tcod.event.KeySym.LEFT: (-1, 0),
    tcod.event.KeySym.RIGHT: (1, 0),
    tcod.event.KeySym.HOME: (-1, -1),
    tcod.event.KeySym.END: (-1, 1),
    tcod.event.KeySym.PAGEUP: (1, -1),
    tcod.event.KeySym.PAGEDOWN: (1, 1),
    tcod.event.KeySym.KP_1: (-1, 1),
    tcod.event.KeySym.KP_2: (0, 1),
    tcod.event.KeySym.KP_3: (1, 1),
    tcod.event.KeySym.KP_4: (-1, 0),
    tcod.event.KeySym.KP_6: (1, 0),
    tcod.event.KeySym.KP_7: (-1, -1),
    tcod.event.KeySym.KP_8: (0, -1),
    tcod.event.KeySym.KP_9: (1, -1),
    tcod.event.KeySym.h: (-1, 0),
    tcod.event.KeySym.j: (0, 1),
    tcod.event.KeySym.k: (0, -1),
    tcod.event.KeySym.l: (1, 0),
    tcod.event.KeySym.y: (-1, -1),
    tcod.event.KeySym.u: (1, -1),
    tcod.event.KeySym.b: (-1, 1),
    tcod.event.KeySym.n: (1, 1),
}

WAIT_KEYS = {tcod.event.KeySym.PERIOD, tcod.event.KeySym.KP_5, tcod.event.KeySym.CLEAR}
CONFIRM_KEYS = {tcod.event.KeySym.RETURN, tcod.event.KeySym.KP_ENTER}
SCROLL_SPEED = 5


def has_shift(mod: int) -> bool:
    return bool(mod & (tcod.event.Modifier.LSHIFT | tcod.event.Modifier.RSHIFT))


def has_ctrl(mod: int) -> bool:
    return bool(mod & (tcod.event.Modifier.LCTRL | tcod.event.Modifier.RCTRL))


def has_alt(mod: int) -> bool:
    return bool(mod & (tcod.event.Modifier.LALT | tcod.event.Modifier.RALT))


def is_shifted(event: tcod.event.KeyDown, key: tcod.event.KeySym) -> bool:
    return event.sym == key and has_shift(event.mod)


def is_ctrl(event: tcod.event.KeyDown, key: tcod.event.KeySym) -> bool:
    return event.sym == key and has_ctrl(event.mod)


_MOTION_KEYS = frozenset("jk")
_INVENTORY_KEYS = (
    [c for c in "abcdefghijklmnopqrstuvwxyz" if c not in _MOTION_KEYS]
    + [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c.lower() not in _MOTION_KEYS]
)
_INVENTORY_KEY_TO_INDEX = {c: i for i, c in enumerate(_INVENTORY_KEYS)}

INVENTORY_CURSOR_UP_KEYS = {tcod.event.KeySym.UP, tcod.event.KeySym.k, tcod.event.KeySym.KP_8}
INVENTORY_CURSOR_DOWN_KEYS = {tcod.event.KeySym.DOWN, tcod.event.KeySym.j, tcod.event.KeySym.KP_2}
