import random

import pygame.mixer


_EFFECT_DEFS = [
    ("Hello and welcome", [
        "sfx/CantinaBand3.wav",
    ]),
    ("hit points.", [
        "sfx/mixkit-sword-cutting-flesh-2788.wav",
        "sfx/mixkit-metal-hit-woosh-1485.wav",
     ]),
    ("hit points [CRIT!]", [
        "sfx/mixkit-samurai-sword-impact-2789.wav",
     ]),
    ("is dead!", [
        "sfx/mixkit-gore-video-game-blood-splash-263.wav",
     ]),
    ("consume the Health Potion", [
        "sfx/mixkit-sip-of-water-1307.wav",
        "sfx/water_drinkwav-14601.wav",
     ]),
    ("You picked up", [
        "sfx/mixkit-retro-game-notification-212.wav",
     ]),
    ("You are dead", [
        "sfx/mixkit-ominous-drums-227.wav",
     ]),
    ("A lightning bolt strikes", [
        "sfx/zapsplat_science_fiction_laser_hit_thud_zap_delay_001_65399.wav",
        "sfx/bug-zapper-47300.wav",
        "sfx/electrocute-6247.wav",
     ]),
    ("starts to stumble around", [
        "sfx/evil-shreik-45560.wav",
    ]),
    ("engulfed in a fiery explosion", [
        "sfx/mixkit-fuel-explosion-1705.wav",
        "sfx/mixkit-explosion-with-rocks-debris-1703.wav",
    ]),
    ("You have been spotted by a dragon!", [
        "sfx/mixkit-giant-monster-roar-1972.wav",
    ]),
    ("You have been spotted by an ender dragon!", [
        "sfx/dragon-roar-high-intensity-36564.wav",
    ]),
    ("You have been spotted by a hydra!", [
        "sfx/fire-breath-6922.wav",
    ]),
    ("You leveled up!", [
        "sfx/winharpsichord-39642.wav"
    ]),
    ("You blinked.", [
        "sfx/teleport-36569.wav",
        "sfx/PM_FN_Spawns_Portals_Teleports_5.wav",
    ]),
    ("You are filled in with rage!", [
        "sfx/mixkit-angry-dragon-roar-echo-1727.wav",
    ]),
    ("but does no damage.", [
        "sfx/whoosh.wav",
    ])
]

# Populated by init(); None means audio is unavailable.
_loaded_effects = None


def init():
    """Load all sound effects into pygame.mixer.Sound objects.

    Must be called after pygame.mixer.init().
    """
    global _loaded_effects
    _loaded_effects = [
        (match_str, [pygame.mixer.Sound(path) for path in paths])
        for match_str, paths in _EFFECT_DEFS
    ]


def maybe_play_sfx(log_line):
    if _loaded_effects is None:
        return
    for match_str, sfx_options in _loaded_effects:
        if match_str in log_line:
            random.choice(sfx_options).play()
            return


def play(fname):
    if not pygame.mixer.get_init():
        return None
    sound = pygame.mixer.Sound(fname)
    return sound.play()
