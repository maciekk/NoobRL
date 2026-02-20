"""Core game engine managing game state, turn cycle, and rendering."""
from __future__ import annotations

import copy
import lzma
import pickle
from typing import TYPE_CHECKING

from tcod.console import Console
from tcod.map import compute_fov

import color
from entity import ItemManager, MonsterManager
import exceptions
from message_log import MessageLog
import render_functions

if TYPE_CHECKING:
    from entity import Actor
    from game_map import GameMap, GameWorld


class Engine:
    """Central game state: manages map, player, entities, turns, and rendering."""

    game_map: GameMap
    game_world: GameWorld

    def __init__(self):
        self.message_log = MessageLog()
        self.mouse_location = (0, 0)
        self.item_manager = ItemManager("data/items.json")
        self.monster_manager = MonsterManager("data/monsters.json", self.item_manager)
        self.player = self.monster_manager.clone("player")
        self.turn = 1
        self.kill_counts: dict[str, int] = {}
        self._bonus_actions = 0
        self.scroll_aliases: dict[str, str] = {}
        self.potion_aliases: dict[str, str] = {}
        self.potion_alias_colors: dict[str, tuple] = {}
        self.identified_items: set[str] = set()

    def initialize_scroll_aliases(self) -> None:
        """Assign a random fake name to each scroll type for this game run."""
        import random
        with open("data/scroll_names.txt") as f:
            names = [line.strip() for line in f if line.strip()]
        scroll_ids = [
            item_id for item_id, item in self.item_manager.items.items()
            if item.char == "?"
        ]
        random.shuffle(names)
        for i, item_id in enumerate(scroll_ids):
            self.scroll_aliases[item_id] = names[i % len(names)]

    def initialize_potion_aliases(self) -> None:
        """Assign a random appearance to each potion type for this game run."""
        import random
        with open("data/potion_looks.txt") as f:
            looks = [line.strip() for line in f if line.strip()]
        with open("data/potion_colors.txt") as f:
            color_entries = []
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split(",")]
                name = parts[0]
                rgb = (int(parts[1]), int(parts[2]), int(parts[3]))
                color_entries.append((name, rgb))
        potion_ids = [
            item_id for item_id, item in self.item_manager.items.items()
            if item.char == "!"
        ]
        random.shuffle(looks)
        for i, item_id in enumerate(potion_ids):
            look = looks[i % len(looks)]
            if "$COLOR" in look:
                color_name, color_rgb = random.choice(color_entries)
                look = look.replace("$COLOR", color_name)
                self.potion_alias_colors[item_id] = color_rgb
            self.potion_aliases[item_id] = look

    def handle_enemy_turns(self) -> None:
        """Process AI actions for all non-player actors."""
        for entity in set(self.game_map.actors) - {self.player}:
            if entity.ai:
                entity.energy += entity.speed
                while entity.energy >= 100 and entity.ai:
                    entity.energy -= 100
                    try:
                        entity.ai.perform()
                    except exceptions.Impossible:
                        pass  # Ignore impossible action exceptions from AI.

    def update_fov(self) -> None:
        """Recompute the visible area based on the players point of view."""
        if self.player.is_asleep or self.player.is_blind:
            # Asleep or blind player sees nothing
            self.game_map.visible[:] = False
        else:
            self.game_map.visible[:] = compute_fov(
                self.game_map.tiles["transparent"],
                (self.player.x, self.player.y),
                radius=8,
            )
            # If a tile is "visible" it should be added to "explored".
            self.game_map.explored |= self.game_map.visible

    def render(self, console: Console) -> None:
        """Render the game map, UI bars, and message log to the console."""
        self.game_map.render(console)

        self.message_log.render(console=console, x=21, y=45, width=99, height=5)

        render_functions.render_bar(
            console=console,
            name="HP",
            current_value=self.player.fighter.hp,
            maximum_value=self.player.fighter.max_hp,
            color_fg=color.hp_bar_filled,
            color_bg=color.hp_bar_empty,
            x=0,
            y=45,
            total_width=20,
        )
        render_functions.render_bar(
            console=console,
            name="XP",
            current_value=self.player.level.current_xp,
            maximum_value=self.player.level.experience_to_next_level,
            color_fg=color.xp_bar_filled,
            color_bg=color.xp_bar_empty,
            x=0,
            y=46,
            total_width=20,
        )
        render_functions.render_dungeon_level(
            console=console,
            dungeon_level=self.game_world.current_floor,
            location=(1, 47),
        )
        render_functions.render_names_at_mouse_location(
            console=console, x=21, y=44, engine=self
        )
        y = 48
        console.print(x=1, y=y, string=f"Turn: {self.turn}")
        s = " ".join([f"{e.name}:{e.turns_left}" for e in self.player.effects])
        console.print(x=1, y=y + 1, string=s)

    def save_as(self, filename: str) -> None:
        """Save this Engine instance as a compressed file."""
        save_data = lzma.compress(pickle.dumps(self))
        with open(filename, "wb") as f:
            f.write(save_data)

    def apply_timed_effects(self) -> None:
        """Apply per-turn logic for all active timed effects on actors."""
        for entity in set(self.game_map.actors):
            for eff in entity.effects:
                eff.apply_turn()

    def end_turn(self) -> None:
        """Advance the game state: apply effects, handle AI, update FOV, increment turn."""
        if self._bonus_actions > 0:
            self._bonus_actions -= 1
            self.update_fov()
            return
        self.apply_timed_effects()
        self.handle_enemy_turns()
        self.update_fov()
        self.turn += 1
        self._bonus_actions = (self.player.speed // 100) - 1
