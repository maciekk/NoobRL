# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NoobRL is a traditional turn-based roguelike dungeon crawler written in Python 3 using the **tcod** library (libtcod bindings). It features procedurally generated dungeons, component-based entities, JSON-driven monster/item definitions, and a full game loop with save/load support.

## Running

```bash
SDL_VIDEODRIVER=x11 python main.py
```

Dependencies: `tcod`, `numpy`, `pygame`. No requirements.txt exists; install manually via pip.

There is no test suite, linter configuration, or formal build system. The Makefile only generates ctags (`make ctags`).

## Architecture Overview

The game loop flows like this:

```
main.py loop
  │
  ▼
Handler (state machine)  ──  decides what to do
  │ returns Action or new Handler
  ▼
Action.perform()  ──  mutates entities/components/map
  │
  ▼
Engine.end_turn()  ──  ticks effects, runs AI, updates FOV
  │
  ▼
Engine.render() → GameMap + UI → tcod console → screen
```

The **handler** decides *what* to do, the **action** does it, the **engine** advances the world, and **components** define entity behavior. Data flows up through the parent-reference chain (`component → entity → gamemap → engine`), and templates flow from JSON through managers into cloned entities on the map.

### Main Loop (`main.py`)

Creates a tcod context (120x50 terminal) and runs a **render-event loop**: clear console → ask handler to render → present to screen → wait for input → dispatch to handler. The handler returns either a new handler (state transition) or an action to execute.

### Input Handlers (`input_handlers.py`) — State Machine

The UI is modeled as a **handler state machine**. Each screen is a handler class; transitions happen by returning a different handler instance.

- **`MainGameEventHandler`** — normal gameplay. Maps keypresses to Actions (movement, bump, pickup, stairs, wait). Opens menu handlers for inventory, character screen, etc.
- **`AskUserEventHandler`** subclasses — modal menus (inventory, level-up, targeting, look mode, item detail, drop quantity). They render an overlay and return an Action or another Handler when the player makes a choice.
- **`GameOverEventHandler`** — death screen.
- **`MainMenu`** (in `setup_game.py`) — title screen, new game / load game.

Key flow: `ev_keydown` → returns `Action` or `Handler` → if Action, `handle_action()` calls `action.perform()` in a loop (for repeated movement), then `engine.end_turn()`.

### Actions (`actions.py`) — Commands

Every game-state mutation is an **Action** subclass with a `perform()` method. This decouples "what the player chose" from "how it affects the world." The same action classes are used by both player input and monster AI. `perform()` returns `True` to repeat (for held-key movement) or `False`/`None` to stop.

- **`BumpAction`** — decides between `MeleeAction` and `MovementAction`
- **`MovementAction`** — basic movement; subclasses add auto-run: `MovementRepeatedAction` (Ctrl+dir, run until wall/monster) and `CarefulMovementAction` (Shift+dir, corridor-smart running that stops at rooms, junctions, stairs, items)
- **`TargetMovementAction`** — A* pathfinding to a clicked tile
- **`MeleeAction`** / **`RangedAttackAction`** — combat with damage/crit calculation
- **`ItemAction`** — delegates to the item's `Consumable.activate()`
- `PickupAction`, `DropItem`, `EquipAction`, `TakeStairsAction`, `WaitAction`

Both corridor-following actions use `_find_corridor_turn()` which excludes the backward direction and returns the unique continuation if exactly one exists. A "near open area" guard prevents turn-following in room corners: if any walkable cardinal neighbor has >= 3 walkable cardinal neighbors, it's near a room, not a true corridor.

### Engine (`engine.py`) — Central Game State

The **Engine** is the root object that owns everything: the game map, the player, message log, item/monster managers, turn counter, and kill counts. It orchestrates the **turn cycle**:

```
end_turn():
  if bonus_actions remaining → just update FOV (haste mechanic)
  else →
    1. apply_timed_effects()   (tick durations on all actors)
    2. handle_enemy_turns()    (energy-based: each monster gains speed energy, acts per 100 spent)
    3. update_fov()            (recompute tcod FOV)
    4. turn += 1
    5. compute bonus_actions = (player.speed // 100) - 1
```

Engine is also the unit of **save/load** — the entire instance is pickled + lzma-compressed.

### Entities (`entity.py`) — Things in the World

```
Entity (x, y, char, color, name)
├── Actor — living beings (player, monsters)
│     has: Fighter, AI, Inventory, Equipment, Level, effects[]
│     has: base_speed, energy (speed system), is_invisible, is_hasted
└── Item — objects
      has: Consumable OR Equippable, stack_count
```

**Spawning**: `ItemManager` and `MonsterManager` load templates from JSON files (`data/monsters.json`, `data/items.json`) and clone them via `deepcopy`. The managers map JSON fields to component classes using lookup dictionaries (`CONSUMABLE_MAP`, `EQUIPPABLE_MAP`, `AI_MAP`). Item display symbols follow roguelike conventions: `?` scrolls, `!` potions, `)` weapons, `[` armor, `/` wands.

### Components (`components/`) — Behavior via Composition

All components inherit **`BaseComponent`**, which provides a `parent` reference and property access up the chain: `component.parent` → `Entity` → `entity.gamemap` → `gamemap.engine`.

| Component | Role |
|---|---|
| **Fighter** | HP, base power/defense (computed properties add equipment bonuses), crit mechanics, death handling |
| **AI** | `HostileEnemy` (pathfinding, range-based melee/ranged), `ConfusedEnemy` (temporary random walk wrapper) |
| **Inventory** | Item list, stack merging, capacity limit |
| **Equipment** | Weapon/armor/amulet slots, computed power/defense bonuses from all equipped items |
| **Equippable** | Per-item stats (power_bonus, defense_bonus), `on_equip()` hooks |
| **Consumable** | `get_action()` (may return a targeting handler), `activate()` (apply the effect), `consume()` (decrement stack). Subclasses: healing, fireball, confusion, lightning, rage, invisibility, speed, wishing |
| **Level** | XP tracking, level-up thresholds, stat increase methods |
| **TimedEffect** | Duration-based buffs: `activate()` → `apply_turn()` each turn → `expire()`. Subclasses toggle Actor flags (`is_invisible`, `is_hasted`) |

### Game Map & World (`game_map.py`)

**GameMap** holds the tile grid (NumPy structured arrays), entity set, and three boolean arrays: `visible` (current FOV), `explored` (permanent), `revealed` (clairvoyance). It provides spatial queries (`get_actor_at_location`, `get_blocking_entity_at_location`) and renders tiles + entities to the console.

**GameWorld** manages multi-floor dungeon generation, holding generation parameters and a floor counter.

### Procedural Generation (`procgen.py`)

Generates dungeons with random non-overlapping rectangular rooms connected by L-shaped Bresenham tunnels. A wide-corridor check prevents 2x2 walkable blocks. Entity spawning uses weighted tables that scale with floor depth.

### Rendering (`render_functions.py`, `game_map.py`)

Rendering flows: `Engine.render()` → `GameMap.render()` (tiles via `np.select`, entities sorted by render order) → UI overlays (HP bar, XP bar, dungeon level, turn counter, active effects, message log, entity names under cursor).

### Other Modules

`color.py` (color constants), `tile_types.py` (NumPy structured arrays for tiles), `sounds.py` (pygame.mixer audio), `dice.py` (D&D dice notation parser, e.g. "5d2"), `tilesets.py`, `debug.py` (debug console handler).

## Key Patterns

- **Stats as properties**: `Fighter.power` and `Fighter.defense` are computed from base stat + equipment bonus, not stored directly.
- **Entity spawning**: Templates loaded from JSON, cloned via `deepcopy`, placed on map with `entity.spawn()`.
- **Handler state machine**: Game transitions (gameplay → inventory → targeting → back) are modeled by returning new handler instances from event methods.
- **FOV/exploration**: `GameMap.visible` (current FOV) and `GameMap.explored` (persistent) are NumPy boolean arrays updated via `tcod.map.compute_fov`.
- **Pickle-based saves**: Entire `Engine` is serialized. Audio uses global `pygame.mixer`, not stored in Engine.
- **Corridor detection**: A tile with >= 3 walkable cardinal neighbors is "open area" (room). For corridor turn-following, a stricter two-level check is used: the tile AND all its walkable neighbors must have < 3 walkable cardinal neighbors. This distinguishes narrow corridors from room corners, which locally look identical (both have 2 walkable cardinal neighbors).
- **Adding items to inventory programmatically**: When cloning items and adding to inventory outside of `PickupAction`, you must set `item.parent = actor.inventory` before use. The `inventory.add()` method does not set the parent. Without this, `BaseComponent.engine` fails because `gamemap` is None.
- **Never use `ev_textinput`**: SDL3 does not generate TextInput events in this setup. All key handling must go through `ev_keydown`. For shifted keys, check modifiers explicitly (e.g., `key == tcod.event.KeySym.N1 and modifier & LSHIFT|RSHIFT`). For text input (like the debug console), convert keysyms to characters via `chr(key)` in `ev_keydown`.
- **Debug shortcuts**: `@` (Shift+2) opens debug console for spawning entities by ID. `!` (Shift+1) grants a Wand of Wishing.
- **Consumable with custom handler**: To create a consumable that opens a selection menu (like `WishingWandConsumable`), override `get_action()` to return an `AskUserEventHandler` subclass. The handler's `ev_keydown()` returns the final action (e.g., `WishAction`). No `activate()` override needed — the action handles everything directly.
- **Item stack_count in JSON**: Set `stack_count` in `data/items.json` to control initial charges for consumables (e.g., Wand of Wishing has 3). Defaults to 1 if omitted.
- **Energy-based speed system**: Each `Actor` has `base_speed` (default 100), `energy` accumulator, and `speed` property. Each turn, monsters gain `speed` energy; they act once per 100 energy spent. Crawler has speed 200 (2 actions/turn), troll/dragon/ender_dragon have speed 50 (1 action every 2 turns). Player bonus actions are computed as `(speed // 100) - 1` after each full turn.
- **Actor boolean flags**: `is_invisible` and `is_hasted` are simple bools on `Actor`, toggled by their respective `TimedEffect` subclasses (`InvisibilityEffect`, `SpeedEffect`). The `speed` property uses `is_hasted` to double `base_speed`. To add a new flag-based buff: add the bool to `Actor.__init__`, create a `TimedEffect` subclass that sets/clears it, and a `Consumable` subclass that creates and activates the effect.
