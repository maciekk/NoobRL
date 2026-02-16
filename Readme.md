# NoobRL

A traditional turn-based roguelike dungeon crawler written in Python using the
[tcod](https://python-tcod.readthedocs.io/) library. Features procedurally
generated dungeons, component-based entities, JSON-driven monster and item
definitions, equipment, consumables, a leveling system, and full save/load
support.

![Screenshot](screenshot.png)

## Design Choices

### Item cardinality per floor square

Choices:
- one item per square (a la Nethack)
- multiple items per square (a la CDDA)

Issues:
- if one item, then any event which drops multiple diff items on a square needs them to "spill out", and distribute across surrounding squares (which probably has many corner cases, such as enclosed rooms)
- if multiple items, how best to effectively convey that a floor square has many items?

Current choice (but re-negotiable): multiple items

### Floor permanence

Choices:
- once generated, the floors persist during staircase travel (a la Nethack)
- traveling up/down stairs always regenerates new dungeon, even if that depth previously visited (a la Angband)

Current choice (but re-negotiable): always re-generate

### Health regeneration by default

Should health auto-regenerate over time, even without potions or other effects?

Perhaps this could be like a race trait that player could choose at start.

## Work Items

Ideas & efforts under way.

### FIXES
- [x] wished-for items should appear in player inventory, not on floor `#next`
- [x] for "multiple items" actually use ampersand (roguelikes convention?)
- [x] fix secret door rendering
- [ ] certain "select choice" dialogs should use Nethack directions (e.g., open/close)

### Interesting Mechanics
- [ ] grass patch: acts to stop visibility when outside; when inside, only see 8 squares around; may hide chests; render as green ',' or ';' or ```
- [ ] allow item throwing (e.g., dart, potion) `#next`
    - [ ] thrown potions shatter, convey their benefit to any actor in that square `#next`
- [ ] simulate noise and monster hearing
- [ ] hunger and food items
- [ ] item weights and maximum carry weight
- [ ] track how many of a monster SEEN in a run? (if don't kill everything you see)
- [ ] incremental monster knowledge (scales w/# killed)
- [ ] anonymized consumables: i.e., nature of consumables not immediately known (like Nethack)
- [ ] maybe later add max stack size for consumables
- [ ] wands should have charges, be non-stackable

### Map Generation
- [ ] scrollable map (i.e., map larger than rendered window)
- [ ] improved map generation - make them more interesting, perhaps sometimes variations of rooms
- [ ] consider POI/room set pieces, that are just "pasted" in the worldgen
- [ ] procgen chests with loot
- [ ] locked doors (requiring keys or lockpicking)
- [ ] hidden traps: squeaky board, pit, fall-through to lower level, teleport trap

### Monsters
- [ ] monsters should have different visibility ranges, some shorter than player's
- [ ] some monsters should patrol rooms, even before spotting you
- [ ] allow monsters to be asleep, fall asleep
- [ ] add: Banshee (do not attack, but if seen, will scream and alert within a given radius)
- [ ] add: Kobold (fast, but low HP, minimal damage... although groups dangerous?)
- [ ] enemy special powers (Ex: speed, strength, invisibility, etc...)
- [ ] enemies should sometimes drop loot when killed
- [ ] find something useful to do with monster corpses (food? crafting?)

### Weapons & Armour
- [ ] add darts at level 1, common `#next`
- [ ] add bows & arrows
- [ ] variable damage on weapons (e.g., 1d10)
- [ ] different types of damage: various melee (blunt, pierce, slash), fire, ice, etc.
  - [ ] add monster weaknesses (e.g., damage type)
- [ ] armour and weapon properties that affect crit_chance and crit_mult
- [ ] more types of weapons
- [ ] more types of armour (maybe separate: chest, helmet, gloves, etc)
- [ ] weapon and armor enchantments
- [ ] vampiric weapons, weapon egos in general / rarities
- [ ] armor set powers? P3

### Items (Potions, Scrolls, Powers, etc)
- [ ] add: Potion of Sleep `#next`
- [ ] add: Potion of Blindness `#next`
- [ ] add: Scroll of Identify (blocked: anonymized item names)
- [ ] add: Potion of Berserk - 50% more damage for 10 turns
- [ ] add: Teleport scroll (user-controlled target, must be in explored space)
- [ ] add rings
- [ ] add more wands
- [ ] items react to nearby spells (e.g., fireball makes a potion explode)
- [ ] maybe: magic proficiency skill, which multiplies damage to all magical effects
- [ ] rethink colours and glyphs used for consumables
- [ ] digging tools, wands - modify the dungeon walls, but slow
- [ ] wand of wishing should even be able to spawn monsters
- [ ] have various light sources, with various light radii

### UI
- [ ] tileset should be specified in options.py (currently hard-coded in main.py) `#next`
- [ ] support single turn animations (e.g., wand ray on zap, thrown items flying) `#next`
- [ ] use different, appropriate sfx for wizard attack
- [ ] for variety, each text trigger maps to a SET of sfx, not just one

### Miscellaneous
- [ ] consider additional magic system: mana pool and spells/spellbooks
- [ ] shop keepers
- [ ] JSON-ify: spells?
- [ ] JSON-ify: loot drop tables?
- [ ] JSON-ify: tile_types.py
- [ ] balance game, avoid becoming god too early; levels ups should occur exponentially further

