# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NoobRL is a traditional turn-based roguelike dungeon crawler written in Python 3 using the **tcod** library (libtcod bindings). It features procedurally generated dungeons, component-based entities, JSON-driven monster/item definitions, and a full game loop with save/load support.

## Running

```bash
SDL_VIDEODRIVER=x11 python main.py
```

Dependencies: `tcod`, `numpy`, `soundfile`. No requirements.txt exists; install manually via pip.

There is no test suite, linter configuration, or formal build system. The Makefile only generates ctags (`make ctags`).

## Architecture

**Entry point**: `main.py` — initializes tcod context (80x50 terminal), runs the main loop dispatching events to the current handler.

**Core state**: `engine.py` — `Engine` holds the game map, player, managers, message log, and turn counter. Manages turn processing: timed effects → enemy turns → FOV update. Save/load uses pickle + lzma.

**Entity system**: `entity.py` — `Entity` base class with `Actor` and `Item` subclasses. Uses composition via components. `ItemManager` and `MonsterManager` load templates from JSON files in `data/` and clone them via deep copy.

**Component architecture** (`components/`):
- `BaseComponent` — parent reference, property access to gamemap/engine
- `Fighter` — HP, power, defense (computed: base + equipment bonuses), crit mechanics, death handling
- `AI` — `HostileEnemy` (pathfinding, range-based behavior per monster type), `ConfusedEnemy` (temporary wrapper)
- `Inventory`, `Equipment`, `Equippable`, `Consumable`, `Level`, `Effect`

**Action system**: `actions.py` — abstract `Action.perform()` returns bool (True = repeat, e.g. held movement). Subclasses: `MovementAction`, `MeleeAction`, `RangedAttackAction`, `ItemAction`, `TakeStairsAction`, etc.

**Input/UI**: `input_handlers.py` (~700 lines, largest file) — handler hierarchy forms a state machine. `BaseEventHandler` → `EventHandler` (has engine) → `MainGameEventHandler` for gameplay, `AskUserEventHandler` subclasses for menus (inventory, level-up, character screen, look, targeting). Handlers return the next handler or an action.

**Procedural generation**: `procgen.py` — `RectangularRoom` with overlap detection, L-shaped tunnels via Bresenham, floor-based difficulty scaling with weighted entity spawn tables.

**Data files**: `data/monsters.json` (player + 7 enemy types with stats), `data/items.json` (consumables + equipment). Managers in `entity.py` dynamically map JSON fields to component classes via `CONSUMABLE_MAP`/`EQUIPPABLE_MAP` dicts.

**Rendering**: `render_functions.py` + `game_map.py`. UI layout: game map fills most of the 80x50 console, stats bar (HP/XP/dungeon level/turn/effects) at bottom-left, message log at bottom-right.

**Other modules**: `color.py` (color constants), `tile_types.py` (NumPy structured arrays for tiles), `sounds.py` (tcod audio mixer), `dice.py` (D&D dice notation parser, e.g. "5d2"), `tilesets.py`, `debug.py` (debug console handler).

## Key Patterns

- **Stats as properties**: `Fighter.power` and `Fighter.defense` are computed from base stat + equipment bonus, not stored directly.
- **Entity spawning**: Templates loaded from JSON, cloned via `deepcopy`, placed on map with `entity.spawn()`.
- **Handler state machine**: Game transitions (gameplay → inventory → targeting → back) are modeled by returning new handler instances from event methods.
- **FOV/exploration**: `GameMap.visible` (current FOV) and `GameMap.explored` (persistent) are NumPy boolean arrays updated via `tcod.map.compute_fov`.
- **Pickle-based saves**: Entire `Engine` is serialized. Non-picklable state (audio mixer) is restored on load.
