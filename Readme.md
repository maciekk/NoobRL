# NoobRL

A traditional turn-based roguelike dungeon crawler written in Python using the [tcod](https://python-tcod.readthedocs.io/) library. Features procedurally generated dungeons, component-based entities, JSON-driven monster and item definitions, equipment, consumables, a leveling system, and full save/load support.

![Screenshot](screenshot.png)

## Ideas

This file is for storing ideas that may be added to the project only.

### IMPORTANT / FIXES / WIP
- [ ] fix "view" command... shift-V doesn't work
- [ ] stack items (e.g., all potions of healing should take one inventory slot)
  - [ ] maybe later add max stack size
- [ ] fix Shift-motion, such that player DOES enter open room
- [ ] maybe: ensure only one item spawned on dungeon ground (avoid hiding items)? design choice
- [ ] review clairvoyance... only want room outlines, and fix stairs shown in upper left?
- [ ] add debug ability to spawn named item (e.g., "potion of clairvoyance")
- [ ] balance game, avoid becoming god too early; levels ups should occur exponentially further
- [ ] use different, appropriate sfx for wizard attack
- [ ] for variety, each text trigger maps to a SET of sfx, not just one

### General
- [ ] JSON-ify all the tables (monsters, items, spells, loot drops)
- [ ] perhaps ability to see monster weaknesses, attack power, def, etc... depends on # vanquished
- [ ] Item weights and maximum carry weight
- [ ] hunger and food items
- [ ] Simulate noise and monster hearing
- [ ] Hidden traps: squeaky board, pit, fall-through to lower level, teleport trap
- [ ] add debugging console: spawn item, spawn monster, etc.
- [ ] procgen chests with loot

### Map gen
- [ ] Improved map generation
- [ ] scrollable map (i.e., map larger than rendered window)
- [ ] have upwards stairwells, but then regen levels (like in Angband)

### Weapons/armor
- [ ] variable damage on weapons (e.g., 1d10)
- [ ] different types of damage: various melee (blunt, pierce, slash), fire, ice, etc.
  - [ ] add monster weaknesses (e.g., damage type)
- [ ] armour and weapon propreties that affect crit_chance and crit_mult
- [ ] More types of weapons
- [ ] More types of armour (maybe separate: chest, helmet, gloves, etc)
- [ ] Weapon and armor enchantments
- [ ] vampiric weapons, weapon egos in general / rarities
- [ ] armor set powers? P3

### Items (Potions, Scrolls, Powers, etc)
- [ ] add potion: Berserk - 50% more damage for 10 turns
- [ ] add scroll: Teleport (user-controlled target, must be in explored space)
- [ ] items react to nearby spells (e.g., fireball makes a potion explode)
- [ ] maybe: magic proficiency skill, which multiplies damage to all magical effects
- [ ] scrolls & potions should initially have generic descriptions (e.g., red potion),
      and player has to figure out item type based on effects.]
- [ ] rethink colours and glyphs used for consumables
- [ ] perhaps anonymize consumables; i.e., nature of consumables not immediately known (like Nethack)
  - [ ] Scrolls of Identify

### Enemies
- [ ] Banshee:(Do not attack, but if seen, will scream and alert within a given radius)
- [ ] Enemy special powers (Ex: speed, strength, invisibility, etc...)
- [ ] Enemies should sometimes drop loot when killed
- [ ] Find something useful to do with monster corpses (food? crafting?)

### UI
- [ ] command which lists items and monsters that player can see from current > [!CAUTION]
- [ ] have function to examine item in inventory

### Open Questions
- [ ] should we regen health very slowly over time? perhaps a character trait?

### Miscellaneous
- [ ] consider additional magic system: mana pool and spells/spellbooks
- [ ] shop keepers
- [ ] add ability to go back in levels (e.g., when left stash upstairs)

### DONE
- [x] add potion: Clairvoyance
- [x] Wizards
- [x] fully heal on level up!
- [x] expand Look function (around level) to provide more info (incl. HP left on monster, maybe attack power, def)
- [x] add scroll: Blink (and/or general Teleport)
- [x] N/A name:(Fast enemy(2 studs), but is weak and not very strong.)
- [x] add sfx for crit hits
- [x] Higher crit chance for dragon enemy or overall powerful mobs
- [x] help button that tells all the keybinds

