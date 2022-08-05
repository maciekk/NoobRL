from __future__ import annotations

import lzma
import pickle
from typing import TYPE_CHECKING

from tcod.console import Console
from tcod.map import compute_fov

import color
from entity import ItemManager
import exceptions
from message_log import MessageLog
import render_functions

if TYPE_CHECKING:
    from entity import Actor
    from game_map import GameMap, GameWorld


class Engine:
    game_map: GameMap
    game_world: GameWorld

    def __init__(self, player: Actor, mixer):
        self.message_log = MessageLog(mixer=mixer)
        self.mouse_location = (0, 0)
        self.player = player
        self.item_manager = ItemManager("data/items.json")

    def handle_enemy_turns(self) -> None:
        for entity in set(self.game_map.actors) - {self.player}:
            if entity.ai:
                try:
                    entity.ai.perform()
                except exceptions.Impossible:
                    pass  # Ignore impossible action exceptions from AI.

    def update_fov(self) -> None:
        """Recompute the visible area based on the players point of view."""
        self.game_map.visible[:] = compute_fov(
            self.game_map.tiles["transparent"],
            (self.player.x, self.player.y),
            radius=8,
        )
        # If a tile is "visible" it should be added to "explored".
        self.game_map.explored |= self.game_map.visible

    def render(self, console: Console) -> None:
        self.game_map.render(console)

        self.message_log.render(console=console, x=21, y=45, width=40, height=5)

        render_functions.render_bar(
            console=console,
            name="HP",
            current_value=self.player.fighter.hp,
            maximum_value=self.player.fighter.max_hp,
            color_fg=color.hp_bar_filled,
            color_bg=color.hp_bar_empty,
            x=0, y=45,
            total_width=20,
        )
        render_functions.render_bar(
            console=console,
            name="XP",
            current_value=self.player.level.current_xp,
            maximum_value=self.player.level.experience_to_next_level,
            color_fg=color.xp_bar_filled,
            color_bg=color.xp_bar_empty,
            x=0, y=46,
            total_width=20,
        )

        render_functions.render_dungeon_level(
            console=console,
            dungeon_level=self.game_world.current_floor,
            location=(0, 47),
        )

        render_functions.render_names_at_mouse_location(
            console=console, x=21, y=44, engine=self
        )

    def save_as(self, filename: str) -> None:
        """Save this Engine instance as a compressed file."""
        # First, wipe the mixer, as it is not picklable.
        self.message_log.mixer = None

        save_data = lzma.compress(pickle.dumps(self))
        with open(filename, "wb") as f:
            f.write(save_data)
