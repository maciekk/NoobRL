#!/usr/bin/env python3
import copy
import traceback

import tcod

import color
from engine import Engine
import entity_factories
from procgen import generate_dungeon
import tilesets


def main() -> None:
    screen_width = 80
    screen_height = 50

    # Set to '2' (for small tileset on high-res monitors).
    scale_factor = 1

    map_width = 80
    map_height = 43

    room_max_size = 10
    room_min_size = 6
    max_rooms = 30

    max_monsters_per_room = 2
    max_items_per_room = 2

    tileset, scale_factor, player_char = tilesets.load_sheet("Curses_800")

    player = copy.deepcopy(entity_factories.player)

    engine = Engine(player=player)

    engine.game_map = generate_dungeon(
        max_rooms=max_rooms,
        room_min_size=room_min_size,
        room_max_size=room_max_size,
        map_width=map_width,
        map_height=map_height,
        max_monsters_per_room=max_monsters_per_room,
        max_items_per_room=max_items_per_room,
        engine=engine,
    )
    engine.update_fov()

    engine.message_log.add_message(
        "Hello and welcome, adventurer, to yet another dungeon!", color.welcome_text
    )

    with tcod.context.new_terminal(
        round(screen_width * scale_factor),
        round(screen_height * scale_factor),
        tileset=tileset,
        title="Yet Another Roguelike Tutorial",
        vsync=True,
    ) as context:
        root_console = tcod.Console(screen_width, screen_height, order="F")
        while True:
            root_console.clear()
            engine.event_handler.on_render(console=root_console)
            context.present(root_console)

            try:
                for event in tcod.event.wait():
                    context.convert_event(event)
                    engine.event_handler.handle_events(event)
            except Exception:  # Handle exceptions in game.
                traceback.print_exc()  # Print error to stderr.
                # Then print the error to the message log.
                engine.message_log.add_message(traceback.format_exc(), color.error)


if __name__ == "__main__":
    main()