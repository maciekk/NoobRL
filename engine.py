"""Core game engine managing game state, turn cycle, and rendering."""
from __future__ import annotations

import lzma
import pickle
from collections import deque
from typing import TYPE_CHECKING

from tcod.console import Console  # pylint: disable=import-error
from tcod.map import compute_fov  # pylint: disable=import-error

import color
from constants import ALL_DIRS
from location import Location
from managers import ItemManager, MonsterManager
import exceptions
import options
import recorder as recorder_module
from message_log import MessageLog
import render_functions

if TYPE_CHECKING:
    from entity import Actor, Item
    from game_map import GameMap, GameWorld


class Engine:  # pylint: disable=too-many-instance-attributes
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
        self._pending_sounds: list[tuple[tuple[int, int], int, bool]] = []  # (location, radius, by_player)
        self.camera_x: int = 0
        self.camera_y: int = 0

    def __getattr__(self, name: str):
        if name in ("camera_x", "camera_y"):
            return 0
        raise AttributeError(name)

    @property
    def viewport_width(self) -> int:
        """Width of the visible map area in tiles."""
        return options.n_cols

    @property
    def viewport_height(self) -> int:
        """Height of the visible map area in tiles."""
        return options.n_rows - 7

    def clamp_camera(self) -> None:
        """Clamp camera so at most one SHROUD border tile is visible at each edge."""
        vp_w, vp_h = self.viewport_width, self.viewport_height
        self.camera_x = max(-1, min(self.camera_x, self.game_map.width - vp_w + 1))
        self.camera_y = max(-1, min(self.camera_y, self.game_map.height - vp_h + 1))

    def center_camera_on_player(self) -> None:
        """Reposition camera so the player is centered in the viewport."""
        vp_w, vp_h = self.viewport_width, self.viewport_height
        self.camera_x = self.player.x - vp_w // 2
        self.camera_y = self.player.y - vp_h // 2
        self.clamp_camera()

    def world_to_screen(self, wx: int, wy: int) -> tuple[int, int]:
        """Convert world coordinates to screen (console) coordinates."""
        return wx - self.camera_x, wy - self.camera_y

    def screen_to_world(self, sx: int, sy: int) -> tuple[int, int]:
        """Convert screen (console) coordinates to world coordinates."""
        return sx + self.camera_x, sy + self.camera_y

    def on_screen(self, wx: int, wy: int) -> bool:
        """Return True if world position (wx, wy) is within the current viewport."""
        sx, sy = self.world_to_screen(wx, wy)
        return 0 <= sx < self.viewport_width and 0 <= sy < self.viewport_height

    def print_at_world(self, console: Console, wx: int, wy: int, **kwargs) -> None:
        """Print to console at world coords, converting to screen coords. No-op if off-screen."""
        sx, sy = self.world_to_screen(wx, wy)
        if 0 <= sx < self.viewport_width and 0 <= sy < self.viewport_height:
            console.print(x=sx, y=sy, **kwargs)

    def initialize_scroll_aliases(self) -> None:
        """Assign a random fake name to each scroll type for this game run."""
        import random  # pylint: disable=import-outside-toplevel
        with open("data/scroll_names.txt", encoding="utf-8") as f:
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
        import random  # pylint: disable=import-outside-toplevel
        with open("data/potion_looks.txt", encoding="utf-8") as f:
            looks = [line.strip() for line in f if line.strip()]
        with open("data/potion_colors.txt", encoding="utf-8") as f:
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

    def give_item_to_player(self, item_id: str) -> tuple["Item | None", bool]:
        """Clone item by ID, auto-identify it, and give it to the player.

        Adds to inventory if there is room, otherwise drops at the player's feet.
        Returns (item, True) if added to inventory, (item, False) if dropped on floor,
        or (None, False) if item_id is unknown.
        """
        item = self.item_manager.clone(item_id)
        if item is None:
            return None, False
        self.identified_items.add(item_id)
        item.parent = self.player.inventory
        if self.player.inventory.add(item):
            return item, True
        item.place(self.player.x, self.player.y, self.game_map)
        return item, False

    def handle_enemy_turns(self) -> None:
        """Process AI actions for all non-player actors."""
        for entity in sorted(
            (e for e in self.game_map.actors if e is not self.player),
            key=lambda e: (e.x, e.y, e.name),
        ):
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
                radius=self.player.sight_range,
            )
            # If a tile is "visible" it should be added to "explored".
            self.game_map.explored |= self.game_map.visible

    def render(self, console: Console) -> None:
        """Render the game map, UI bars, and message log to the console."""
        self.game_map.render(console)

        panel_y = self.viewport_height
        self.message_log.render(
            console=console, x=30, y=panel_y + 1, width=console.width - 30, height=5
        )

        render_functions.render_bar(
            console=console,
            name="HP",
            current_value=self.player.fighter.hp,
            maximum_value=self.player.fighter.max_hp,
            color_fg=color.hp_bar_filled,
            color_bg=color.hp_bar_empty,
            x=0,
            y=panel_y + 1,
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
            y=panel_y + 2,
            total_width=20,
        )
        p = self.player
        console.print(
            x=1,
            y=panel_y + 3,
            string=f"DLv:{self.game_world.current_floor} PLv:{p.level.current_level} T:{self.turn}",
        )
        render_functions.render_names_at_mouse_location(
            console=console, x=30, y=panel_y, engine=self
        )
        y = panel_y + 4
        stats = (
            f"P:{p.fighter.power}"
            f" D:{p.fighter.defense}"
            f" S:{p.base_speed}"
        )
        console.print(x=1, y=y, string=stats)
        s = " ".join([f"{e.name}:{e.turns_left}" for e in self.player.effects])
        console.print(x=1, y=y + 1, string=s)
        if options.show_viewport_offset:
            label = f"\u2192{self.camera_x} \u2193{self.camera_y}"
            console.print(x=console.width - len(label), y=0, string=label, fg=(255, 255, 255), bg=(0, 0, 0))
        recorder_module.render_overlay(console)

    def save_as(self, filename: str) -> None:
        """Save this Engine instance as a compressed file."""
        save_data = lzma.compress(pickle.dumps(self))
        with open(filename, "wb") as f:
            f.write(save_data)

    def emit_sound(self, location: Location, radius: int, by_player: bool = False) -> None:
        """Queue a sound event to be processed at the start of the next turn cycle."""
        self._pending_sounds.append((Location(*location), radius, by_player))

    def _bfs_sound(
        self,
        sound_location: Location,
        radius: int,
        combined_by_dist: dict,
        alerted: dict,
    ) -> None:
        """BFS-expand one sound source, accumulating tiles and alerted actors in-place."""
        walkable = self.game_map.tiles["walkable"]
        visited: set[Location] = {sound_location}
        queue: deque[tuple[Location, int]] = deque([(sound_location, 0)])
        while queue:
            pos, dist = queue.popleft()
            if dist >= radius:
                continue
            for ddx, ddy in ALL_DIRS:
                neighbor = Location(pos.x + ddx, pos.y + ddy)
                if neighbor in visited:
                    continue
                if not self.game_map.in_bounds(neighbor.x, neighbor.y):
                    continue
                if not walkable[neighbor.x, neighbor.y]:
                    continue
                visited.add(neighbor)
                combined_by_dist.setdefault(dist + 1, set()).add(neighbor)
                queue.append((neighbor, dist + 1))
                actor = self.game_map.get_actor_at_location(neighbor.x, neighbor.y)
                if actor and actor is not self.player and actor.ai:
                    if hasattr(actor.ai, "on_sound") and actor not in alerted:
                        alerted[actor] = (neighbor, sound_location)

    def _notify_alerted_actors(self, alerted: dict) -> None:
        """Call on_sound for each alerted actor and emit visible wake/investigate messages."""
        for actor, (actor_loc, source_loc) in alerted.items():
            was_asleep = actor.is_asleep
            had_investigate = getattr(actor.ai, "investigate_target", None) is not None
            actor.ai.on_sound(source_loc.x, source_loc.y)
            newly_woken = was_asleep and not actor.is_asleep
            newly_alerted = (
                not had_investigate
                and getattr(actor.ai, "investigate_target", None) is not None
            )
            if (newly_woken or newly_alerted) and self.game_map.is_visible(actor_loc):
                if newly_woken:
                    self.message_log.add_message(f"The {actor.name} stirs awake!")
                else:
                    self.message_log.add_message(f"The {actor.name} perks up.")

    def _process_sounds(self) -> None:
        """BFS-propagate all queued sound events, animate them combined, then alert monsters."""
        if not self._pending_sounds:
            return
        import input_handlers as _ih  # pylint: disable=import-outside-toplevel
        combined_by_dist: dict[int, set[Location]] = {}
        player_by_dist: dict[int, set[Location]] = {}
        monster_by_dist: dict[int, set[Location]] = {}
        monster_burst_locs: list[Location] = []
        # actor → (actor_loc, source_loc) — keep only first source that reaches each actor
        alerted: dict[object, tuple[Location, Location]] = {}
        for location, radius, by_player in self._pending_sounds:
            self._bfs_sound(location, radius, combined_by_dist, alerted)
            if by_player:
                self._bfs_sound(location, radius, player_by_dist, {})
            else:
                if self.game_map.visible[location.x, location.y]:
                    self._bfs_sound(location, radius, monster_by_dist, {})
                else:
                    from sound_travel import SOUND_ANIM_MAX_DIST  # pylint: disable=import-outside-toplevel
                    if abs(location.x - self.player.x) + abs(location.y - self.player.y) <= SOUND_ANIM_MAX_DIST:
                        monster_burst_locs.append(location)
        can_animate = _ih.context is not None and _ih.root_console is not None and options.show_sound
        if can_animate and (player_by_dist or monster_by_dist or monster_burst_locs):
            from render_functions import animate_sound_wave  # pylint: disable=import-outside-toplevel
            animate_sound_wave(self, player_by_dist, monster_by_dist, monster_burst_locs, _ih.root_console, _ih.context)
        self._notify_alerted_actors(alerted)
        self._pending_sounds.clear()

    def apply_timed_effects(self) -> None:
        """Apply per-turn logic for all active timed effects on actors."""
        for entity in sorted(self.game_map.actors, key=lambda e: (e.x, e.y, e.name)):
            for eff in entity.effects:
                eff.apply_turn()

    def end_turn(self) -> None:
        """Advance the game state: apply effects, handle AI, update FOV, increment turn."""
        if self._bonus_actions > 0:
            self._bonus_actions -= 1
            self.update_fov()
            self.center_camera_on_player()
            return
        self.apply_timed_effects()
        self.handle_enemy_turns()
        self._process_sounds()
        self.update_fov()
        self.turn += 1
        self._bonus_actions = (self.player.speed // 100) - 1
        self.center_camera_on_player()
