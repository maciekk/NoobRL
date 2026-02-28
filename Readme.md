# NoobRL

A traditional turn-based roguelike dungeon crawler written in Python using the
[tcod](https://python-tcod.readthedocs.io/) library. Features procedurally
generated dungeons, component-based entities, JSON-driven monster and item
definitions, equipment, consumables, a leveling system, and full save/load
support.

![Screenshot](pics/screenshot2.png)

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
- [ ] bombs should also be listed in WEAPONS section of Inventory, not Other
- [ ] scrolls should have no colours, or randomly selected (not from data/items.json) `#next`
- [ ] when you read unidentified Scroll of Identify, there should be no going back (can't cancel out), the scroll is consumed regardless, and gets immediately identified itself

### Interesting Mechanics
- [ ] auto-pickup items
- [ ] simulate noise and monster hearing
- [ ] hunger and food items
- [ ] item weights and maximum carry weight
- [ ] track how many of a monster SEEN in a run? (if don't kill everything you see)
- [ ] incremental monster knowledge (scales w/# killed)
- [ ] maybe later add max stack size for consumables
- [ ] hidden traps: squeaky board, pit, fall-through to lower level, teleport trap
- [ ] need 'kick' ability: damages/breaks doors, but can also hurt monster, and maybe shove them 1sq away

### Dungeon
- [ ] locked doors (requiring keys or lockpicking)
- [ ] scrollable map (i.e., map larger than rendered window)
- [ ] improved map generation - make them more interesting, perhaps sometimes variations of rooms
- [ ] consider POI/room set pieces, that are just "pasted" in the worldgen

### Monsters
- [ ] add: Popper - like Puffball, but smaller, low HP, low damage, small explosion (3 turns?)... spawn in packs `#next`
- [ ] add: Banshee (do not attack, but if seen, will scream and alert within a given radius)
- [ ] enemy special powers (Ex: speed, strength, invisibility, etc...)
- [ ] enemies should sometimes drop loot when killed (is corpse part of drop?)
- [ ] find something useful to do with monster corpses (food? crafting?)

### Weapons & Armour
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
- [ ] add: Potion of Berserk - 50% more damage for 10 turns
- [ ] add: Wand of Digging `#next`
- [ ] add rings
- [ ] add more wands
- [ ] items react to nearby spells (e.g., fireball makes a potion explode)
- [ ] maybe: magic proficiency skill, which multiplies damage to all magical effects
- [ ] digging tools, wands - modify the dungeon walls, but slow
- [ ] LoS will need to be independent from player sight distance (b/c some monsters will have better eyesight)
- [ ] have various light sources, with various light radii; thus visibility of X is compound of 3 factors: LoS map + min(player sight_distance, light source range)

### UI
- [ ] use different, appropriate sfx for wizard attack

### Miscellaneous
- [ ] consider additional magic system: mana pool and spells/spellbooks
- [ ] shop keepers
- [ ] JSON-ify: spells?
- [ ] JSON-ify: loot drop tables?
- [ ] JSON-ify: tile_types.py
- [ ] balance game, avoid becoming god too early; levels ups should occur exponentially further

