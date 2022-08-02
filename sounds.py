import numpy as np
import random
import soundfile

def _read_file(fname):
    sound, samplerate = soundfile.read(fname)

    # Soundfile seems to load things into float64 format, which SDL does not support; convert to 16 bit integers.
    # Following stolen from: https://stackoverflow.com/questions/52700279/how-do-you-convert-data-from-float64-to-int16-in-python-3
    max_16bit = 2 ** 15
    sound = sound * max_16bit
    sound = sound.astype(np.int16)

    return (sound,samplerate)


EFFECTS = [
    ("Hello and welcome", [
        _read_file("sfx/CantinaBand3.wav"),
    ]),
    ("Player attacks", [
        _read_file("sfx/mixkit-sword-cutting-flesh-2788.wav"),
     ]),
    ("attacks Player", [
        _read_file("sfx/mixkit-metal-hit-woosh-1485.wav"),
     ]),
    ("is dead!", [
        _read_file("sfx/mixkit-gore-video-game-blood-splash-263.wav"),
     ]),
    ("consume the Health Potion", [
        _read_file("sfx/mixkit-sip-of-water-1307.wav"),
     ]),
    ("You picked up", [
        _read_file("sfx/mixkit-retro-game-notification-212.wav"),
     ]),
    ("You died!", [
        _read_file("sfx/mixkit-ominous-drums-227.wav"),
     ]),
    ("A lightning bolt strikes", [
        _read_file("sfx/zapsplat_science_fiction_laser_hit_thud_zap_delay_001_65399.wav"),
        _read_file("sfx/bug-zapper-47300.wav"),
        _read_file("sfx/electrocute-6247.wav"),
     ]),
    ("starts to stumble around", [
        _read_file("sfx/evil-shreik-45560.wav"),
    ]),
    ("engulfed in a fiery explosion", [
        _read_file("sfx/mixkit-fuel-explosion-1705.wav"),
        _read_file("sfx/mixkit-explosion-with-rocks-debris-1703.wav"),
    ]),
]


def maybe_play_sfx(log_line, mixer):
    for match_str, sfx_options in EFFECTS:
        if match_str in log_line:
            sound, samplerate = random.choice(sfx_options)
            mixer.play(mixer.device.convert(sound, samplerate))
            return