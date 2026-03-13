"""Tests that JSON data files are well-formed and internally consistent."""
import json
import os

import pytest

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# items.json
# ---------------------------------------------------------------------------

def test_items_json_is_list():
    assert isinstance(load("items.json"), list)


def test_items_all_have_ids():
    for item in load("items.json"):
        assert "id" in item, f"Item missing 'id': {item}"


def test_items_ids_are_unique():
    ids = [item["id"] for item in load("items.json")]
    assert len(ids) == len(set(ids)), "Duplicate item IDs found"


# ---------------------------------------------------------------------------
# monsters.json
# ---------------------------------------------------------------------------

def test_monsters_json_is_list():
    assert isinstance(load("monsters.json"), list)


def test_monsters_all_have_ids():
    for m in load("monsters.json"):
        assert "id" in m, f"Monster missing 'id': {m}"


def test_monsters_ids_are_unique():
    ids = [m["id"] for m in load("monsters.json")]
    assert len(ids) == len(set(ids)), "Duplicate monster IDs found"


# ---------------------------------------------------------------------------
# loot_table.json
# ---------------------------------------------------------------------------

def test_loot_table_is_dict():
    assert isinstance(load("loot_table.json"), dict)


@pytest.mark.parametrize("floor_key,entries", load("loot_table.json").items())
def test_loot_table_floor_keys_are_integers(floor_key, entries):
    assert int(floor_key) >= 0


@pytest.mark.parametrize("floor_key,entries", load("loot_table.json").items())
def test_loot_table_entries_are_pairs(floor_key, entries):
    for entry in entries:
        assert len(entry) == 2, f"Floor {floor_key}: expected [id, weight], got {entry}"
        assert isinstance(entry[0], str)
        assert isinstance(entry[1], int)
        assert entry[1] > 0, f"Floor {floor_key}: weight must be positive"


def test_loot_table_ids_exist_in_items():
    table = load("loot_table.json")
    item_ids = {item["id"] for item in load("items.json")}
    for floor_key, entries in table.items():
        for item_id, _ in entries:
            assert item_id in item_ids, (
                f"loot_table floor {floor_key}: '{item_id}' not found in items.json"
            )


# ---------------------------------------------------------------------------
# enemy_table.json
# ---------------------------------------------------------------------------

def test_enemy_table_is_dict():
    assert isinstance(load("enemy_table.json"), dict)


@pytest.mark.parametrize("floor_key,entries", load("enemy_table.json").items())
def test_enemy_table_floor_keys_are_integers(floor_key, entries):
    assert int(floor_key) >= 0


@pytest.mark.parametrize("floor_key,entries", load("enemy_table.json").items())
def test_enemy_table_entries_are_pairs(floor_key, entries):
    for entry in entries:
        assert len(entry) == 2, f"Floor {floor_key}: expected [id, weight], got {entry}"
        assert isinstance(entry[0], str)
        assert isinstance(entry[1], int)
        assert entry[1] > 0, f"Floor {floor_key}: weight must be positive"


def test_enemy_table_ids_exist_in_monsters():
    table = load("enemy_table.json")
    monster_ids = {m["id"] for m in load("monsters.json")}
    for floor_key, entries in table.items():
        for monster_id, _ in entries:
            assert monster_id in monster_ids, (
                f"enemy_table floor {floor_key}: '{monster_id}' not found in monsters.json"
            )
