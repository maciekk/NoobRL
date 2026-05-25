"""Lazy-loaded enchantment data from data/enchantments.json."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

_CACHE: Dict[str, Optional[object]] = {"data": None, "by_id": None}


def _load() -> None:
    path = os.path.join(os.path.dirname(__file__), "data", "enchantments.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _CACHE["data"] = data
    _CACHE["by_id"] = {entry["id"]: entry for entry in data}


def get(enchantment_id: str) -> Optional[Dict]:
    """Return the full enchantment entry for the given id, or None."""
    by_id = _CACHE["by_id"]
    if by_id is None:
        _load()
        by_id = _CACHE["by_id"]
    return by_id.get(enchantment_id)


def get_label(enchantment_id: str) -> str:
    """Return the display label for an enchantment id, falling back to the id itself."""
    entry = get(enchantment_id)
    if entry is None:
        return enchantment_id
    return entry["label"]


def all_entries() -> List[Dict]:
    """Return all enchantment entries."""
    data = _CACHE["data"]
    if data is None:
        _load()
        data = _CACHE["data"]
    return data


def candidates_for(equipment_type_name: str, floor: int) -> List[Tuple[str, float]]:
    """Return list of (id, chance) for enchantments eligible on this equipment type and floor."""
    data = all_entries()
    result = []
    for entry in data:
        slot = entry["applies_to"].get(equipment_type_name)
        if slot is not None and floor >= slot["min_floor"]:
            result.append((entry["id"], slot["chance"]))
    return result
