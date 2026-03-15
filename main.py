#!/usr/bin/env python3
"""Main entry point for NoobRL roguelike game."""
import traceback

import tcod  # pylint: disable=import-error

import color
import exceptions
import input_handlers
import recorder as recorder_module
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
    n_cols = options.n_cols
    n_rows = options.n_rows

    tileset, scale_factor, _ = tilesets.load_sheet(options.tileset)

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
        input_handlers.context = context
        input_handlers.root_console = root_console
        try:
            while True:
                # Adjust columns to match window aspect ratio (keeps n_rows fixed).
                try:
                    rec_cols, rec_rows = context.recommended_console_size()
                    if rec_rows > 0:
                        new_cols = max(n_cols, int(rec_cols * n_rows / rec_rows))
                    else:
                        new_cols = n_cols
                    if new_cols != root_console.width:
                        root_console = tcod.console.Console(new_cols, n_rows, order="F")
                        input_handlers.root_console = root_console
                        options.n_cols = new_cols
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

                root_console.clear()
                handler.on_render(console=root_console)
                context.present(root_console, keep_aspect=True, integer_scaling=False)

                try:
                    if recorder_module.playback_active:
                        import time  # pylint: disable=import-outside-toplevel
                        delay = getattr(handler, "playback_delay", 0.1)
                        time.sleep(delay)
                        # Poll for real input (non-blocking) so Escape can abort
                        for event in tcod.event.get():
                            context.convert_event(event)
                            if (
                                isinstance(event, tcod.event.KeyDown)
                                and event.sym == tcod.event.KeySym.ESCAPE
                            ):
                                handler = handler.handle_events(event)
                                break
                        else:
                            handler = handler.handle_events(None)
                    else:
                        for event in tcod.event.wait():
                            # Populates TILE-based coords into the event, based on
                            # extant PIXEL-based ones.
                            context.convert_event(event)
                            handler = handler.handle_events(event)
                except Exception:  # pylint: disable=broad-exception-caught  # Handle exceptions in game.
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
