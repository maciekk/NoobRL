"""Sound travel distances, loaded from data/sound_travel.json."""
import json
from enum import IntEnum

with open("data/sound_travel.json", encoding="utf-8") as _f:
    _data = json.load(_f)

SoundTravel = IntEnum("SoundTravel", {k.upper(): v for k, v in _data.items()})
