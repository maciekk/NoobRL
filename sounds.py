"""Sound effect playback via enum-based Sfx system and log-based triggers."""
import enum
import json
import os
import random
import threading
import time

import pygame.mixer  # pylint: disable=import-error

# Stagger delay (seconds) between multiple sounds triggered in quick succession.
_STAGGER_SECS = 0.1
_NEXT_PLAY_TIME = 0.0

# Set to True whenever a sound is played; checked by movement repeat logic.
sound_heard = False


def consume_sound_heard() -> bool:
    """Return True (and reset) if a sound was heard since last call."""
    global sound_heard  # pylint: disable=global-statement
    result = sound_heard
    sound_heard = False
    return result


# ---------------------------------------------------------------------------
# Enum-based sound effects loaded from data/sfx.json
# ---------------------------------------------------------------------------

_SFX_JSON = os.path.join(os.path.dirname(__file__), "data", "sfx.json")
with open(_SFX_JSON, encoding="utf-8") as _f:
    _SFX_MAP_RAW: dict[str, list[str]] = json.load(_f)

Sfx = enum.Enum("Sfx", {k: k for k in _SFX_MAP_RAW})

_SFX_PATHS: dict[Sfx, list[str]] = {Sfx[k]: v for k, v in _SFX_MAP_RAW.items()}

# Populated by init(); None means audio is unavailable.
_LOADED_SFX: dict[Sfx, list] | None = None


# ---------------------------------------------------------------------------
# Log-based sound triggers (extensibility hook for custom triggers)
# ---------------------------------------------------------------------------

# Log-based sound triggers: add entries here to play sounds when specific
# text appears in the message log. Each entry is (substring, [sound_files]).
# First match wins; put specific triggers before broad ones.
# Example:
#   ("You found a secret door", ["sfx/secret-door.wav"]),
_EFFECT_DEFS = []

# Populated by init(); None means audio is unavailable.
_LOADED_EFFECTS = None


def init():
    """Load all sound effects into pygame.mixer.Sound objects.

    Must be called after pygame.mixer.init().
    """
    global _LOADED_SFX, _LOADED_EFFECTS  # pylint: disable=global-statement

    _LOADED_SFX = {}
    for sfx, paths in _SFX_PATHS.items():
        _LOADED_SFX[sfx] = [pygame.mixer.Sound(path) for path in paths]

    _LOADED_EFFECTS = [
        (match_str, [pygame.mixer.Sound(path) for path in paths])
        for match_str, paths in _EFFECT_DEFS
    ]


def play_sfx(sfx: Sfx):
    """Play a random sound for the given Sfx enum member.

    Returns the pygame Channel or None if audio is unavailable.
    """
    global _NEXT_PLAY_TIME, sound_heard  # pylint: disable=global-statement
    if _LOADED_SFX is None:
        return None
    sounds = _LOADED_SFX.get(sfx)
    if not sounds:
        return None
    sound = random.choice(sounds)
    now = time.monotonic()
    play_at = max(now, _NEXT_PLAY_TIME)
    delay = play_at - now
    if delay <= 0:
        channel = sound.play()
    else:
        channel = None
        threading.Timer(delay, sound.play).start()
    _NEXT_PLAY_TIME = play_at + _STAGGER_SECS
    sound_heard = True
    return channel


def maybe_play_sfx(log_line):
    """Play a matching sound effect if audio is available and a trigger matches."""
    global _NEXT_PLAY_TIME, sound_heard  # pylint: disable=global-statement
    if _LOADED_EFFECTS is None:
        return
    for match_str, sfx_options in _LOADED_EFFECTS:
        if match_str in log_line:
            sound = random.choice(sfx_options)
            now = time.monotonic()
            play_at = max(now, _NEXT_PLAY_TIME)
            delay = play_at - now
            if delay <= 0:
                sound.play()
            else:
                threading.Timer(delay, sound.play).start()
            _NEXT_PLAY_TIME = play_at + _STAGGER_SECS
            sound_heard = True
            return
