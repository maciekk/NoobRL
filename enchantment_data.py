"""Lazy-loaded enchantment data from data/enchantments.json."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

_data: Optional[List[Dict]] = None
_by_id: Optional[Dict[str, Dict]] = None


def _load() -> None:
    global _data, _by_id
    path = os.path.join(os.path.dirname(__file__), "data", "enchantments.json")
    with open(path, encoding="utf-8") as f:
        _data = json.load(f)
    _by_id = {entry["id"]: entry for entry in _data}


def get(enchantment_id: str) -> Optional[Dict]:
    """Return the full enchantment entry for the given id, or None."""
    if _by_id is None:
        _load()
    return _by_id.get(enchantment_id)


def get_label(enchantment_id: str) -> str:
    """Return the display label for an enchantment id, falling back to the id itself."""
    entry = get(enchantment_id)
    if entry is None:
        return enchantment_id
    return entry["label"]


def candidates_for(equipment_type_name: str, floor: int) -> List[Tuple[str, float]]:
    """Return list of (id, chance) for enchantments eligible on this equipment type and floor."""
    if _data is None:
        _load()
    result = []
    for entry in _data:
        slot = entry["applies_to"].get(equipment_type_name)
        if slot is not None and floor >= slot["min_floor"]:
            result.append((entry["id"], slot["chance"]))
    return result
