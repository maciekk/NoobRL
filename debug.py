from typing import Optional

import tcod

from engine import Engine
from entity import Entity
import entity_factories
from game_map import GameMap
from input_handlers import AskUserEventHandler, MainGameEventHandler

def spawn_entity(name, game_map: GameMap, x: int, y: int):
    if not hasattr(entity_factories, name):
        game_map.engine.message_log.add_message(f"Uknonwn object '{name}' requested.")
        return None
    return entity_factories.__getattribute__(name).spawn(game_map, x, y)

class DebugHandler(AskUserEventHandler):
    """Debug menu."""
    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.buffer = ""

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

        y = 0
        width = 38

        console.draw_frame(
            x=x,
            y=y,
            width=width,
            height=6,
            title="DEBUG MENU",
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )
        console.print(x=x + 1, y=y + 1, string=f"Enter item to spawn: {self.buffer}")

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[MainGameEventHandler]:
        match event:
            case tcod.event.KeyDown(sym=tcod.event.K_RETURN):
                self.engine.message_log.add_message(f"Spawning {self.buffer}.")
                spawn_entity(self.buffer, self.engine.game_map, self.engine.player.x, self.engine.player.y + 1)
                return MainGameEventHandler(self.engine)
            case tcod.event.KeyDown(sym=tcod.event.K_BACKSPACE):
                if len(self.buffer):
                    self.buffer = self.buffer[:-1]
        return None

    def ev_textinput(self, event: tcod.event.TextInput):
        match event:
            case tcod.event.TextInput(text=text):
                self.buffer += text

