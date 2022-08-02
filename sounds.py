import numpy as np
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
    ("Player attacks", _read_file("sfx/mixkit-sword-cutting-flesh-2788.wav")),
    ("attacks Player", _read_file("sfx/splattt-6295.wav")),
    ("is dead!", _read_file("sfx/death-rattle-40282.wav")),
    ("consume the Health Potion", _read_file("sfx/mixkit-sip-of-water-1307.wav")),
]


def maybe_play_sfx(log_line, mixer):
    for match_str, (sound, samplerate) in EFFECTS:
        if match_str in log_line:
            mixer.play(mixer.device.convert(sound, samplerate))
            return