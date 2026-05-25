"""Inventory-related handlers split from input_handlers.py."""
# pylint: disable=missing-function-docstring,missing-class-docstring,import-outside-toplevel,unused-argument,attribute-defined-outside-init

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import tcod  # pylint: disable=import-error

import actions
import color
from entity import Actor, Item
from equipment_types import EquipmentType
from handlers.keys import CONFIRM_KEYS, _INVENTORY_KEYS

if TYPE_CHECKING:
    from engine import Engine
    from input_handlers import ActionOrHandler


_SECTION_NAMES = {0: "Weapons", 1: "Armour", 2: "Potions", 3: "Scrolls", 4: "Other"}


def _item_category(item: Item) -> int:
    if item.equippable:
        if item.equippable.equipment_type in (EquipmentType.WEAPON, EquipmentType.THROWN):
            return 0
        if item.equippable.equipment_type == EquipmentType.ARMOR:
            return 1
    if item.char == "*":
        return 0
    if item.char == "!":
        return 2
    if item.char == "?":
        return 3
    return 4


def _item_type_and_stat_lines(item: Item) -> list:
    lines: list = []
    if item.equippable:
        eq_type = item.equippable.equipment_type
        if eq_type == EquipmentType.WEAPON:
            lines.append(("Weapon", color.white))
        elif eq_type == EquipmentType.AMULET:
            lines.append(("Amulet", color.white))
        elif eq_type == EquipmentType.THROWN:
            if item.stackable and item.stack_count > 1:
                lines.append((f"Thrown weapon (x{item.stack_count})", color.white))
            else:
                lines.append(("Thrown weapon", color.white))
        else:
            lines.append(("Armor", color.white))
    elif item.consumable:
        if item.stackable and item.stack_count > 1:
            lines.append((f"Consumable (x{item.stack_count})", color.white))
        else:
            lines.append(("Consumable", color.white))
    else:
        lines.append(("Item", color.white))

    if item.consumable:
        if item.display_name != item.name:
            lines.append(("???", color.white))
        else:
            for desc_line in item.consumable.get_description():
                lines.append((desc_line, color.white))

    if item.equippable:
        eq = item.equippable
        if eq.damage_dice:
            dmg_str = f"Damage: {eq.damage_dice}"
            if eq.enchantment > 0:
                dmg_str += f"+{eq.enchantment}"
            lines.append((dmg_str, color.white))
        elif eq.power_bonus:
            lines.append((f"Attack bonus: +{eq.power_bonus}", color.white))
        total_defense = eq.defense_bonus + eq.enchantment
        if total_defense:
            lines.append((f"Defense bonus: +{total_defense}", color.white))
    return lines


class InventoryEventHandler(__import__("input_handlers").ListSelectionHandler):
    TITLE = "<missing title>"
    use_cursor = True

    def get_items(self) -> list:
        return sorted(self.engine.player.inventory.items, key=_item_category)

    def get_display_string(self, index: int, item) -> str:
        return item.display_name

    def _get_display_suffix(self, item) -> str:
        s = ""
        if item.char == "/":
            s += f" [{item.stack_count}c]"
        elif item.stackable and item.stack_count > 1:
            s += f" [x{item.stack_count}]"
        if self.engine.player.equipment.item_is_equipped(item):
            s += " [E]"
        return s

    def on_render(self, console: tcod.Console) -> None:
        self.engine.render(console)
        items = self.get_items()
        num_items = len(items)
        if self.use_cursor and num_items > 0:
            self.cursor = max(0, min(self.cursor, num_items - 1))

        rows = []
        prev_cat = None
        for idx, item in enumerate(items):
            cat = _item_category(item)
            if cat != prev_cat:
                rows.append(("header", _SECTION_NAMES[cat]))
                prev_cat = cat
            rows.append(("item", idx, item))

        row_data = []
        for row in rows:
            if row[0] == "header":
                row_data.append((f"-- {row[1]} --", ""))
            else:
                _, idx, item = row
                item_key = _INVENTORY_KEYS[idx] if idx < len(_INVENTORY_KEYS) else "?"
                base = f"{item_key}. {self.get_display_string(idx, item)}"
                suffix = self._get_display_suffix(item)
                row_data.append((base, suffix))

        height = max(len(rows) + 2, 3)
        max_str_width = max((len(b) + len(s) for b, s in row_data), default=0)
        width = max(len(self.TITLE) + 4, max_str_width + 2)
        x = self.menu_x

        console.draw_frame(x=x, y=0, width=width, height=height, title=self.TITLE, clear=True, fg=(255, 255, 255), bg=(0, 0, 0))
        if not items:
            console.print(x + 1, 1, self.EMPTY_TEXT)
            return

        cyan = (0, 255, 255)
        for row_y, ((base, suffix), row) in enumerate(zip(row_data, rows), start=1):
            if row[0] == "header":
                console.print(x + 1, row_y, base, fg=color.impossible)
            else:
                _, idx, _ = row
                highlighted = self.use_cursor and idx == self.cursor
                fg_main = color.black if highlighted else color.white
                bg = color.white if highlighted else color.black
                console.print(x + 1, row_y, base, fg=fg_main, bg=bg)
                if suffix:
                    fg_suffix = color.black if highlighted else cyan
                    console.print(x + 1 + len(base), row_y, suffix, fg=fg_suffix, bg=bg)

    def on_selection(self, index: int, item) -> Optional[ActionOrHandler]:
        return self.on_item_selected(item)

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        raise NotImplementedError()


class InventoryActivateHandler(InventoryEventHandler):
    TITLE = "Select an item to use"

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        return ItemDetailHandler(self.engine, item, self.cursor)


class InventoryDropHandler(InventoryEventHandler):
    TITLE = "Select an item to drop"

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        if item.stackable and item.stack_count > 1:
            return DropQuantityHandler(self.engine, item)
        return actions.DropItem(self.engine.player, item)


class QuaffHandler(__import__("input_handlers").ListSelectionHandler):
    TITLE = "Quaff which potion?"
    EMPTY_TEXT = "(No potions)"
    use_cursor = True

    def get_items(self) -> list:
        return [item for item in self.engine.player.inventory.items if item.char == "!"]

    def get_display_string(self, index: int, item) -> str:
        s = item.display_name
        if item.stackable and item.stack_count > 1:
            s += f" [x{item.stack_count}]"
        return s

    def on_selection(self, index: int, item) -> Optional[ActionOrHandler]:
        return item.consumable.get_action(self.engine.player)


class ReadHandler(__import__("input_handlers").ListSelectionHandler):
    TITLE = "Read which scroll?"
    EMPTY_TEXT = "(No scrolls)"
    use_cursor = True

    def get_items(self) -> list:
        return [item for item in self.engine.player.inventory.items if item.char == "?"]

    def get_display_string(self, index: int, item) -> str:
        s = item.display_name
        if item.stackable and item.stack_count > 1:
            s += f" [x{item.stack_count}]"
        return s

    def on_selection(self, index: int, item) -> Optional[ActionOrHandler]:
        return item.consumable.get_action(self.engine.player)


class ItemDetailHandler(__import__("input_handlers").AskUserEventHandler):
    def __init__(self, engine: Engine, item: Item, inventory_cursor: int = 0):
        super().__init__(engine)
        self.item = item
        self.inventory_cursor = inventory_cursor

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)
        item = self.item
        player = self.engine.player
        lines: list[tuple[str, tuple[int, int, int]]] = []
        lines.append((f"{item.char} {item.display_name}", item.display_color))
        lines.extend(_item_type_and_stat_lines(item))

        if item.equippable and item.equippable.equipment_type != EquipmentType.THROWN:
            lines.append(("Currently equipped", color.safe) if player.equipment.item_is_equipped(item) else ("Not equipped", color.white))

        lines.append(("", color.white))
        if item.equippable and item.equippable.equipment_type != EquipmentType.THROWN:
            lines.append(("(e) Unequip" if player.equipment.item_is_equipped(item) else "(e) Equip", color.white))
        if item.consumable:
            lines.append(("(a) Apply", color.white))
        lines.extend([("(t) Throw", color.white), ("(d) Drop", color.white), ("(Esc) Back", color.white)])

        x = self.menu_x
        max_line_width = max(len(text) for text, _ in lines)
        width = max(len(item.display_name) + 6, max_line_width + 2)
        height = len(lines) + 2
        console.draw_frame(x=x, y=0, width=width, height=height, title=item.display_name, clear=True, fg=(255, 255, 255), bg=(0, 0, 0))
        for i, (text, fg) in enumerate(lines):
            console.print(x + 1, 1 + i, text, fg=fg)

    def _get_equip_action(self, player: Actor, item: Item) -> Optional[ActionOrHandler]:
        if item.equippable.equipment_type == EquipmentType.THROWN:
            return None
        return actions.EquipAction(player, item)

    def _get_drop_action(self, player: Actor, item: Item) -> Optional[ActionOrHandler]:
        if item.stackable and item.stack_count > 1:
            return DropQuantityHandler(self.engine, item)
        return actions.DropItem(player, item)

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        key = event.sym
        item = self.item
        player = self.engine.player
        if key == tcod.event.KeySym.e and item.equippable:
            return self._get_equip_action(player, item)
        if key == tcod.event.KeySym.a and item.consumable:
            return item.consumable.get_action(player)
        if key == tcod.event.KeySym.t:
            from handlers.targeting import ThrowTargetHandler

            return ThrowTargetHandler(self.engine, item)
        if key == tcod.event.KeySym.d:
            return self._get_drop_action(player, item)
        if key == tcod.event.KeySym.ESCAPE:
            return InventoryActivateHandler(self.engine, cursor=self.inventory_cursor)
        return None


class DropQuantityHandler(__import__("input_handlers").AskUserEventHandler):
    def __init__(self, engine: Engine, item: Item):
        super().__init__(engine)
        self.item = item
        self.text = ""

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)
        x = self.menu_x
        prompt = f"Drop how many {self.item.display_name}? (1-{self.item.stack_count})"
        max_digits = len(str(self.item.stack_count))
        width = len(prompt) + max_digits + 4
        console.draw_frame(x=x, y=0, width=width, height=3, title="Drop", clear=True, fg=(255, 255, 255), bg=(0, 0, 0))
        console.print(x + 1, 1, f"{prompt} {self.text}_")

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        from handlers.gameplay import MainGameEventHandler

        key = event.sym
        if key == tcod.event.KeySym.ESCAPE:
            return MainGameEventHandler(self.engine)
        if key in CONFIRM_KEYS:
            try:
                count = int(self.text)
            except ValueError:
                self.engine.message_log.add_message("Enter a number.", color.invalid)
                return None
            if count < 1 or count > self.item.stack_count:
                self.engine.message_log.add_message(f"Enter a number between 1 and {self.item.stack_count}.", color.invalid)
                return None
            return actions.DropItem(self.engine.player, self.item, count=count)
        if key == tcod.event.KeySym.BACKSPACE:
            self.text = self.text[:-1]
        else:
            try:
                c = chr(key)
                if c.isdigit():
                    self.text += c
            except (ValueError, OverflowError):
                pass
        return None


class WishItemHandler(__import__("input_handlers").ListSelectionHandler):
    TITLE = "Wish for an item"

    def __init__(self, engine: Engine, wand_item: Item):
        super().__init__(engine)
        self.wand_item = wand_item
        self._item_list = sorted([(id_, item.name) for id_, item in engine.item_manager.items.items() if id_ != "wand_wishing"], key=lambda x: x[1])

    def get_items(self) -> list:
        return self._item_list

    def get_display_string(self, index: int, item) -> str:
        return item[1]

    def on_selection(self, index: int, item) -> Optional[ActionOrHandler]:
        item_id, _ = item
        return actions.WishAction(self.engine.player, self.wand_item, item_id)


class IdentifyItemHandler(__import__("input_handlers").ListSelectionHandler):
    TITLE = "Identify which item?"
    use_cursor = True

    def __init__(self, engine: Engine, scroll_item: Item):
        super().__init__(engine)
        self.scroll_item = scroll_item

    def get_items(self) -> list:
        return [item for item in self.engine.player.inventory.items if item.display_name != item.name]

    def get_display_string(self, index: int, item) -> str:
        return item.display_name

    def on_selection(self, index: int, item) -> Optional[ActionOrHandler]:
        return actions.IdentifyAction(self.engine.player, self.scroll_item, item)


class ThrowItemHandler(InventoryEventHandler):
    TITLE = "Throw what?"
    use_cursor = True

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        from handlers.targeting import ThrowTargetHandler

        return ThrowTargetHandler(self.engine, item)
