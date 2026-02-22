#!/usr/bin/env python3
"""Main entry point for NoobRL roguelike game."""
import traceback

import tcod

import color
import exceptions
import input_handlers
import options
import setup_game
import tilesets


def save_game(handler: input_handlers.BaseEventHandler, filename: str) -> None:
    """If the current event handler has an active Engine then save it."""
    if isinstance(handler, input_handlers.EventHandler):
        handler.engine.save_as(filename)
        print("Game saved.")


def main() -> None:
    """Run the main game loop."""
    n_cols = 120
    n_rows = 50

    # Set to '2' (for small tileset on high-res monitors).
    # TODO: fix; no longer scales
    scale_factor = 1

    tileset, scale_factor, player_char = tilesets.load_sheet(options.tileset)

    handler = setup_game.MainMenu()

    with tcod.context.new(
        columns=round(n_cols * scale_factor),
        rows=round(n_rows * scale_factor),
        tileset=tileset,
        title="NoobRL",
        vsync=True,
    ) as context:
        # order="F" means [x, y] access to NumPy arrays (vs [y, x])
        root_console = tcod.console.Console(n_cols, n_rows, order="F")
        input_handlers._context = context
        input_handlers._root_console = root_console
        try:
            while True:
                root_console.clear()
                handler.on_render(console=root_console)
                context.present(root_console, keep_aspect=True, integer_scaling=False)

                try:
                    for event in tcod.event.wait():
                        # Populates TILE-based coords into the event, based on
                        # extant PIXEL-based ones.
                        context.convert_event(event)
                        handler = handler.handle_events(event)
                except Exception:  # Handle exceptions in game.
                    traceback.print_exc()  # Print error to stderr.
                    # Then print the error to the message log.
                    if isinstance(handler, input_handlers.EventHandler):
                        handler.engine.message_log.add_message(
                            traceback.format_exc(), color.error
                        )
        except exceptions.QuitWithoutSaving:
            raise
        except SystemExit:  # Save and quit.
            save_game(handler, "savegame.sav")
            raise
        except BaseException:  # Save on any other unexpected exception.
            save_game(handler, "savegame.sav")
            raise


if __name__ == "__main__":
    main()
