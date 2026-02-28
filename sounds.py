"""Sound effect playback triggered by message log content."""
import random
import threading
import time

import pygame.mixer  # pylint: disable=import-error

# Stagger delay (seconds) between multiple sounds triggered in quick succession.
_STAGGER_SECS = 0.1
_NEXT_PLAY_TIME = 0.0

_EFFECT_DEFS = [
    (
        "Hello and welcome",
        [
            "sfx/CantinaBand3.wav",
        ],
    ),
    (
        "hit points.",
        [
            "sfx/mixkit-sword-cutting-flesh-2788.wav",
            "sfx/mixkit-metal-hit-woosh-1485.wav",
            #"sfx/sword-whoosh-clang.mp3",
            "sfx/foil-clang.wav",
            #"sfx/sword-clang.wav",
            "sfx/sword-clash-nice.wav",
        ],
    ),
    (
        "hit points [CRIT!]",
        [
            "sfx/mixkit-samurai-sword-impact-2789.wav",
        ],
    ),
    (
        "is dead!",
        [
            "sfx/mixkit-gore-video-game-blood-splash-263.wav",
        ],
    ),
    (
        "consume the Health Potion",
        [
            "sfx/mixkit-sip-of-water-1307.wav",
            "sfx/water_drinkwav-14601.wav",
        ],
    ),
    (
        "You picked up",
        [
            "sfx/mixkit-retro-game-notification-212.wav",
        ],
    ),
    (
        "You are dead",
        [
            "sfx/mixkit-ominous-drums-227.wav",
        ],
    ),
    (
        "A lightning bolt strikes",
        [
            "sfx/zapsplat_science_fiction_laser_hit_thud_zap_delay_001_65399.wav",
            "sfx/bug-zapper-47300.wav",
            "sfx/electrocute-6247.wav",
        ],
    ),
    (
        "Dart hits",
        [
            "sfx/u_xjrmmgxfru-hit-armor-03-266300.mp3",
        ],
    ),
    (
        "clatters to the ground",
        [
            "sfx/dragon-studio-sword-clattering-to-the-ground-393838.mp3",
        ],
    ),
    (
        "for 1 damage!",
        [
            "sfx/floraphonic-metal-hit-96-200425.mp3",
        ],
    ),
    (
        "zapped for",
        [
            "sfx/155790__deleted_user_1941307__shipboard_railgun.mp3",
        ],
    ),
    (
        "sizzles through the air",
        [
            "sfx/155790__deleted_user_1941307__shipboard_railgun.mp3",
        ],
    ),
    (
        "starts to stumble around",
        [
            "sfx/evil-shreik-45560.wav",
        ],
    ),
    (
        "engulfed in a fiery explosion",
        [
            "sfx/mixkit-fuel-explosion-1705.wav",
            "sfx/mixkit-explosion-with-rocks-debris-1703.wav",
        ],
    ),
    (
        "You have been spotted by a dragon!",
        [
            "sfx/mixkit-giant-monster-roar-1972.wav",
        ],
    ),
    (
        "You have been spotted by an ender dragon!",
        [
            "sfx/dragon-roar-high-intensity-36564.wav",
        ],
    ),
    (
        "You have been spotted by a hydra!",
        [
            "sfx/fire-breath-6922.wav",
        ],
    ),
    ("You leveled up!", ["sfx/winharpsichord-39642.wav"]),
    (
        "You blinked.",
        [
            "sfx/teleport-36569.wav",
            "sfx/PM_FN_Spawns_Portals_Teleports_5.wav",
        ],
    ),
    (
        "You teleport.",
        [
            "sfx/teleport-36569.wav",
            "sfx/PM_FN_Spawns_Portals_Teleports_5.wav",
        ],
    ),
    (
        "You are filled in with rage!",
        [
            "sfx/mixkit-angry-dragon-roar-echo-1727.wav",
        ],
    ),
    (
        "but does no damage.",
        [
            "sfx/whoosh.wav",
        ],
    ),
    (
        "Tick...",
        [
            "sfx/clock-tick.wav",
        ],
    ),
    (
        "BOOM!",
        [
            "sfx/explosion1.wav",
        ],
    ),
    (
        "caught in the blast",
        [
            "sfx/explosion2.wav",
        ],
    ),
    (
        "open the chest",
        [
            "sfx/771164__steprock__treasure-chest-open.mp3",
        ],
    ),
    (
        "breaks",
        [
            "sfx/41348__datasoundsample__glass-shatter.wav",
        ],
    ),
]

# Populated by init(); None means audio is unavailable.
_LOADED_EFFECTS = None


def init():
    """Load all sound effects into pygame.mixer.Sound objects.

    Must be called after pygame.mixer.init().
    """
    global _LOADED_EFFECTS  # pylint: disable=global-statement
    _LOADED_EFFECTS = [
        (match_str, [pygame.mixer.Sound(path) for path in paths])
        for match_str, paths in _EFFECT_DEFS
    ]


def maybe_play_sfx(log_line):
    """Play a matching sound effect if audio is available and a trigger matches."""
    global _NEXT_PLAY_TIME  # pylint: disable=global-statement
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
            return


def play(fname):
    """Play a sound file directly, returning the channel or None if audio is off."""
    if not pygame.mixer.get_init():
        return None
    sound = pygame.mixer.Sound(fname)
    return sound.play()
