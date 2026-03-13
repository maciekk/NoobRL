#!/usr/bin/env python3
# pylint: disable=invalid-name
"""Balance analysis tool for NoobRL.

Reads spawn tables from procgen.py and data files to detect balance
issues: DPS spikes, weapon tier conflicts, items not in spawn table, etc.

Usage:
    python tools/balance_report.py
    python tools/balance_report.py --max-floor 12
"""

import argparse
import ast
import json
import math
import os

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TOOLS_DIR)

# Mirrors actions.py:343
BIG_MONSTERS = {"Dragon", "Ender Dragon", "Hydra"}
BIG_CRIT = 0.30
DEFAULT_CRIT = 0.05

# Player base stats (from monsters.json player entry)
PLAYER_BASE_DEFENSE = 1
PLAYER_START_WEAPON = 2  # dagger, always equipped at start


def parse_procgen_dicts():
    """Load item and enemy spawn tables from their JSON data files."""
    def load_table(filename):
        path = os.path.join(REPO_ROOT, "data", filename)
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return {int(k): [tuple(entry) for entry in v] for k, v in raw.items()}

    return load_table("loot_table.json"), load_table("enemy_table.json")


def _extract_call_kw_stats(cls_name, call_node, stats):
    """Read power_bonus, defense_bonus, or damage_dice keywords from an ast.Call node."""
    for kw in call_node.keywords:
        if kw.arg in ("power_bonus", "defense_bonus"):
            try:
                stats.setdefault(cls_name, {})[kw.arg] = ast.literal_eval(kw.value)
            except (ValueError, TypeError):
                pass
        elif kw.arg == "damage_dice":
            try:
                dice_str = ast.literal_eval(kw.value)
                n, sides = dice_str.split("d")
                avg = int(n) * (int(sides) + 1) / 2
                stats.setdefault(cls_name, {})["power_bonus"] = avg
            except (ValueError, TypeError, AttributeError):
                pass


def parse_equippable_stats():
    """Extract power_bonus / defense_bonus / damage_dice per class from equippable.py via AST."""
    path = os.path.join(REPO_ROOT, "components", "equippable.py")
    with open(path, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    stats: dict = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            cls_name = node.name
            for item in ast.walk(node):
                if isinstance(item, ast.Call):
                    _extract_call_kw_stats(cls_name, item, stats)
    return stats


def load_json(filename):
    """Load a JSON file relative to REPO_ROOT."""
    with open(os.path.join(REPO_ROOT, filename), encoding="utf-8") as f:
        return json.load(f)


def first_floor_in(entity_id, chances_dict):
    """Return the lowest floor key where entity_id first appears, or None."""
    for floor in sorted(chances_dict.keys()):
        for eid, _ in chances_dict[floor]:
            if eid == entity_id:
                return floor
    return None


def all_ids_in(chances_dict):
    """Return the set of all entity IDs mentioned in a chances dict."""
    ids = set()
    for entries in chances_dict.values():
        for eid, _ in entries:
            ids.add(eid)
    return ids


def best_gear_at_floor(floor, item_chances, items_by_id, equip_stats):
    """Return (best_weapon_power, best_armor_defense) from items available up to floor."""
    best_weapon = PLAYER_START_WEAPON  # player always starts with a dagger
    best_armor = 0
    for f in sorted(item_chances.keys()):
        if f > floor:
            break
        for item_id, _ in item_chances[f]:
            item = items_by_id.get(item_id)
            if item is None or "equippable" not in item:
                continue
            cls_name = item["equippable"].get("name", "")
            s = equip_stats.get(cls_name, {})
            best_weapon = max(best_weapon, s.get("power_bonus", 0))
            best_armor = max(best_armor, s.get("defense_bonus", 0))
    return best_weapon, best_armor


def eff_dps(power, player_defense, speed, crit_chance):
    """Compute expected DPS of a monster attack vs. the player's current defense."""
    base = max(power - player_defense, 0)
    crit_dmg = math.ceil(base * 1.5) if base > 0 else 0
    expected = (1 - crit_chance) * base + crit_chance * crit_dmg
    return expected * (speed / 100.0)


def _report_weapons(items_by_id, item_chances, equip_stats, flags):
    """Print weapon progression table and flag same-floor conflicts."""
    print("=== Weapon Progression ===")
    print(f"  {'Class':<20} {'ID':<16} {'Power':>5}  {'Floor':>5}")
    print(f"  {'-'*52}")

    weapon_rows = []
    for item_id, item in items_by_id.items():
        if "equippable" not in item:
            continue
        cls_name = item["equippable"].get("name", "")
        power = equip_stats.get(cls_name, {}).get("power_bonus", 0)
        if power == 0:
            continue
        floor = first_floor_in(item_id, item_chances)
        weapon_rows.append((power, floor if floor is not None else 999, cls_name, item_id))
    weapon_rows.sort()

    floor_to_weapons: dict = {}
    for _, f, _, item_id in weapon_rows:
        if f != 999:
            floor_to_weapons.setdefault(f, []).append(item_id)
    for f, ids in floor_to_weapons.items():
        if len(ids) >= 2:
            flags.append(f"WEAPON CONFLICT: {', '.join(ids)} both first appear at floor {f}")

    for power, f, cls_name, item_id in weapon_rows:
        floor_str = "—" if f == 999 else str(f)
        note = "  ← not in spawn table" if f == 999 else ""
        print(f"  {cls_name:<20} {item_id:<16} {power:>5}  {floor_str:>5}{note}")


def _report_armors(items_by_id, item_chances, equip_stats, flags):
    """Print armor progression table and flag same-floor conflicts."""
    print()
    print("=== Armor Progression ===")
    print(f"  {'Class':<20} {'ID':<16} {'Def':>4}  {'Floor':>5}")
    print(f"  {'-'*52}")

    armor_rows = []
    for item_id, item in items_by_id.items():
        if "equippable" not in item:
            continue
        cls_name = item["equippable"].get("name", "")
        defense = equip_stats.get(cls_name, {}).get("defense_bonus", 0)
        if defense == 0:
            continue
        floor = first_floor_in(item_id, item_chances)
        armor_rows.append((defense, floor if floor is not None else 999, cls_name, item_id))
    armor_rows.sort()

    floor_to_armors: dict = {}
    for _, f, _, item_id in armor_rows:
        if f != 999:
            floor_to_armors.setdefault(f, []).append(item_id)
    for f, ids in floor_to_armors.items():
        if len(ids) >= 2:
            flags.append(f"ARMOR CONFLICT: {', '.join(ids)} both first appear at floor {f}")

    for defense, f, cls_name, item_id in armor_rows:
        floor_str = "—" if f == 999 else str(f)
        note = "  ← not in spawn table" if f == 999 else ""
        print(f"  {cls_name:<20} {item_id:<16} {defense:>4}  {floor_str:>5}{note}")


def _report_missing_equippables(items_by_id, item_chances, flags):
    """Print equippables defined in JSON but absent from the spawn table."""
    print()
    print("=== Equippables in JSON but not in spawn table ===")
    spawnable_ids = all_ids_in(item_chances)
    missing = [
        iid
        for iid, item in items_by_id.items()
        if "equippable" in item and iid not in spawnable_ids
    ]
    if missing:
        for iid in sorted(missing):
            print(f"  [MISSING] {iid}")
            flags.append(f"ITEM NOT SPAWNING: {iid}")
    else:
        print("  (none)")


def _check_debut_balance(new_ids, monsters_by_id, player_defense, floor, flags):
    """Flag when monsters debuting on the same floor have wildly different DPS."""
    new_dpses = []
    for mid in new_ids:
        m = monsters_by_id.get(mid)
        if m is None:
            continue
        fighter = m.get("fighter", {})
        power = fighter.get("base_power", 0)
        speed = m.get("base_speed", 100)
        name = m.get("name", mid)
        crit = BIG_CRIT if name in BIG_MONSTERS else DEFAULT_CRIT
        dps = eff_dps(power, player_defense, speed, crit)
        new_dpses.append((name, dps))
    if new_dpses:
        min_dps = min(d for _, d in new_dpses)
        max_dps_val = max(d for _, d in new_dpses)
        if min_dps > 0 and max_dps_val > min_dps * 1.5:
            flags.append(
                f"IMBALANCED DEBUT on F{floor}:"
                f" max DPS={max_dps_val:.2f} is >1.5× min DPS={min_dps:.2f}"
            )


def _print_floor_monsters(floor, pool, new_ids, monsters_by_id, player_defense,
                           prev_max_dps, flags):
    """Print DPS table for all monsters in the pool at this floor; return floor max DPS."""
    print(f"  {'':5} {'Name':<15} {'PWR':>4} {'DEF':>4} {'SPD':>4}"
          f" {'CRIT':>5} {'DPS':>6}  Notes")
    print(f"  {'-'*62}")
    floor_max_dps = 0.0
    for monster_id in sorted(pool):
        m = monsters_by_id.get(monster_id)
        if m is None:
            continue
        fighter = m.get("fighter", {})
        power = fighter.get("base_power", 0)
        defense = fighter.get("base_defense", 0)
        speed = m.get("base_speed", 100)
        name = m.get("name", monster_id)
        crit = BIG_CRIT if name in BIG_MONSTERS else DEFAULT_CRIT
        dps = eff_dps(power, player_defense, speed, crit)
        floor_max_dps = max(floor_max_dps, dps)
        is_new = monster_id in new_ids
        tag = "[NEW]" if is_new else "     "
        notes = []
        if is_new and prev_max_dps > 0 and dps > prev_max_dps * 1.5:
            notes.append("DPS SPIKE!")
            flags.append(
                f"DPS SPIKE on F{floor}: {name} eff.DPS={dps:.2f}"
                f" vs prev floor max={prev_max_dps:.2f}"
            )
        print(
            f"  {tag} {name:<15} {power:>4} {defense:>4} {speed:>4}"
            f" {crit*100:>4.0f}% {dps:>6.2f}  {', '.join(notes)}"
        )
    return floor_max_dps


def _report_threats(monsters_by_id, enemy_chances, item_chances, equip_stats,
                    items_by_id, flags, max_floor):
    """Print per-floor monster threat analysis and flag DPS spikes."""
    print()
    print("=== Monster Threat by Floor ===")
    pool: set = set()
    prev_max_dps = 0.0
    for floor in sorted(f for f in enemy_chances.keys() if f <= max_floor):
        new_ids = [eid for eid, _ in enemy_chances[floor] if eid not in pool]
        for eid, _ in enemy_chances[floor]:
            pool.add(eid)
        best_weapon, best_armor = best_gear_at_floor(
            floor, item_chances, items_by_id, equip_stats
        )
        player_defense = PLAYER_BASE_DEFENSE + best_armor
        print(
            f"\n  Floor {floor} — weapon+{best_weapon}, armor+{best_armor}"
            f" → player defense={player_defense}"
        )
        floor_max_dps = _print_floor_monsters(
            floor, pool, new_ids, monsters_by_id, player_defense, prev_max_dps, flags
        )
        if len(new_ids) >= 2:
            _check_debut_balance(new_ids, monsters_by_id, player_defense, floor, flags)
        prev_max_dps = max(prev_max_dps, floor_max_dps)


def main():
    """Run the balance report."""
    parser = argparse.ArgumentParser(description="NoobRL balance report")
    parser.add_argument("--max-floor", type=int, default=12)
    args = parser.parse_args()

    item_chances, enemy_chances = parse_procgen_dicts()
    equip_stats = parse_equippable_stats()
    items_by_id = {item["id"]: item for item in load_json("data/items.json")}
    monsters_by_id = {m["id"]: m for m in load_json("data/monsters.json")}

    flags = []  # accumulate all detected issues

    _report_weapons(items_by_id, item_chances, equip_stats, flags)
    _report_armors(items_by_id, item_chances, equip_stats, flags)
    _report_missing_equippables(items_by_id, item_chances, flags)
    _report_threats(
        monsters_by_id, enemy_chances, item_chances, equip_stats,
        items_by_id, flags, args.max_floor
    )

    print()
    print("=== Flagged Issues ===")
    if flags:
        for flag in flags:
            print(f"  [WARN] {flag}")
    else:
        print("  No issues detected.")


if __name__ == "__main__":
    main()
