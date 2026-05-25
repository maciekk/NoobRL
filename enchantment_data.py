"""Lazy-loaded enchantment data from data/enchantments.json."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple

_DATA: List[Dict] = []
_BY_ID: Dict[str, Dict] = {}
_LOADED = False


def _load() -> None:
    global _LOADED
    if _LOADED:
        return
    path = os.path.join(os.path.dirname(__file__), "data", "enchantments.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _DATA.clear()
    _DATA.extend(data)
    _BY_ID.clear()
    _BY_ID.update({entry["id"]: entry for entry in _DATA})
    _LOADED = True


def get(enchantment_id: str) -> Dict | None:
    """Return the full enchantment entry for the given id, or None."""
    _load()
    return _BY_ID.get(enchantment_id)


def get_label(enchantment_id: str) -> str:
    """Return the display label for an enchantment id, falling back to the id itself."""
    entry = get(enchantment_id)
    if entry is None:
        return enchantment_id
    return entry["label"]


def all_entries() -> List[Dict]:
    """Return all enchantment entries."""
    _load()
    return _DATA


def candidates_for(equipment_type_name: str, floor: int) -> List[Tuple[str, float]]:
    """Return list of (id, chance) for enchantments eligible on this equipment type and floor."""
    result = []
    for entry in all_entries():
        slot = entry["applies_to"].get(equipment_type_name)
        if slot is not None and floor >= slot["min_floor"]:
            result.append((entry["id"], slot["chance"]))
    return result
