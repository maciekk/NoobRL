"""Gameplay recording and replay system.

Records the initial engine state and all player keystrokes to a human-readable
file that can be replayed via debug console commands.
"""
import base64
import lzma
import pickle
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

import tcod  # pylint: disable=import-error

# Module-level globals — kept outside Engine to avoid polluting pickle state.
active_recorder: Optional["Recorder"] = None
playback_active: bool = False


def render_overlay(console) -> None:
    """Draw a RECORD or PLAY indicator in the upper-left corner if active."""
    if active_recorder is not None:
        # Red bullet (CP437 pos 0x07 → U+2022) + white "RECORD"
        console.print(x=1, y=0, string="\u25CB", fg=(255, 0, 0))
        console.print(x=3, y=0, string="RECORD", fg=(255, 255, 255))
    elif playback_active:
        # Green right-pointing pointer (CP437 pos 0x10 → U+25BA) + white "PLAY"
        console.print(x=1, y=0, string="\u25BA", fg=(0, 255, 0))
        console.print(x=3, y=0, string="PLAY", fg=(255, 255, 255))


@dataclass
class SyntheticKeyDown:
    """Minimal stand-in for tcod.event.KeyDown used during playback."""
    sym: int
    mod: int


# Modifier flag names used in the recording file format.
_MOD_FLAGS = [
    ("LSHIFT", tcod.event.Modifier.LSHIFT),
    ("RSHIFT", tcod.event.Modifier.RSHIFT),
    ("LCTRL", tcod.event.Modifier.LCTRL),
    ("RCTRL", tcod.event.Modifier.RCTRL),
    ("LALT", tcod.event.Modifier.LALT),
    ("RALT", tcod.event.Modifier.RALT),
]


def _mod_to_names(mod: int) -> List[str]:
    """Convert a modifier bitmask to a list of human-readable flag names."""
    names = []
    for name, flag in _MOD_FLAGS:
        if mod & flag:
            names.append(name)
    return names


def _names_to_mod(names: List[str]) -> int:
    """Convert a list of modifier flag names back to a bitmask."""
    mod = 0
    flag_map = {name: flag for name, flag in _MOD_FLAGS}
    for n in names:
        if n in flag_map:
            mod |= flag_map[n]
    return mod


def _sym_to_name(sym: int) -> str:
    """Convert a KeySym integer to its human-readable name."""
    try:
        return tcod.event.KeySym(sym).name
    except ValueError:
        return str(sym)


def _name_to_sym(name: str) -> int:
    """Convert a KeySym name back to its integer value."""
    try:
        return tcod.event.KeySym[name].value
    except KeyError:
        return int(name)


class Recorder:
    """Captures engine state and keystrokes for later replay."""

    def __init__(self, engine, filename: str):
        self.filename = filename
        self.engine_snapshot: bytes = pickle.dumps(engine)
        self.random_state = random.getstate()
        self.keystrokes: List[Tuple[int, int]] = []
        self._engine = engine  # kept for ASCII map generation at save time

    def record_key(self, sym: int, mod: int) -> None:
        """Append a keystroke to the recording."""
        self.keystrokes.append((sym, mod))

    def generate_ascii_map(self) -> str:
        """Render the current game map as an ASCII string."""
        game_map = self._engine.game_map
        w, h = game_map.width, game_map.height

        # Start with tile characters
        grid = []
        for y in range(h):
            row = []
            for x in range(w):
                ch = int(game_map.tiles[x, y]["light"]["ch"])
                row.append(chr(ch) if ch > 0 else " ")
            grid.append(row)

        # Overlay entities (sorted so higher render_order draws last / on top)
        for entity in sorted(game_map.entities, key=lambda e: e.render_order.value):
            if 0 <= entity.x < w and 0 <= entity.y < h:
                grid[entity.y][entity.x] = entity.char

        return "\n".join("".join(row) for row in grid)

    def save(self, filename: Optional[str] = None) -> None:
        """Write the recording to disk."""
        fname = filename or self.filename

        floor = self._engine.game_world.current_floor
        turn = self._engine.turn

        ascii_map = self.generate_ascii_map()

        random_b64 = base64.b64encode(pickle.dumps(self.random_state)).decode("ascii")
        engine_b64 = base64.b64encode(
            lzma.compress(self.engine_snapshot)
        ).decode("ascii")

        # Format keystrokes
        ks_lines = []
        for sym, mod in self.keystrokes:
            parts = _mod_to_names(mod)
            parts.append(_sym_to_name(sym))
            ks_lines.append("+".join(parts))

        with open(fname, "w") as f:
            f.write("=== NOOBRL RECORDING ===\n")
            f.write(f"Floor: {floor}, Turn: {turn}\n")
            f.write("\n=== MAP ===\n")
            f.write(ascii_map)
            f.write("\n\n=== RANDOM STATE ===\n")
            f.write(random_b64)
            f.write("\n\n=== KEYSTROKES ===\n")
            f.write("\n".join(ks_lines))
            f.write("\n\n=== ENGINE STATE ===\n")
            f.write(engine_b64)
            f.write("\n\n=== END ===\n")


def load_recording(filename: str):
    """Parse a recording file and return (engine, random_state, keystrokes)."""
    with open(filename, "r") as f:
        content = f.read()

    sections = {}
    current_section = None
    current_lines: List[str] = []

    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("=== ") and stripped.endswith(" ==="):
            if current_section is not None:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = stripped[4:-4].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_section is not None:
        sections[current_section] = "\n".join(current_lines).strip()

    # Parse random state
    random_state = pickle.loads(base64.b64decode(sections["RANDOM STATE"]))

    # Parse engine
    engine = pickle.loads(lzma.decompress(base64.b64decode(sections["ENGINE STATE"])))

    # Parse keystrokes
    keystrokes: List[Tuple[int, int]] = []
    ks_text = sections.get("KEYSTROKES", "").strip()
    if ks_text:
        for line in ks_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("+")
            sym_name = parts[-1]
            mod_names = parts[:-1]
            sym = _name_to_sym(sym_name)
            mod = _names_to_mod(mod_names)
            keystrokes.append((sym, mod))

    return engine, random_state, keystrokes
