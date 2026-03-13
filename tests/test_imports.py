"""Smoke tests: verify all game modules import without errors.

These catch syntax errors, missing imports, and broken module-level code
across the entire codebase without requiring a live display or engine.
"""


def test_import_location():
    import location  # noqa: F401


def test_import_constants():
    import constants  # noqa: F401


def test_import_color():
    import color  # noqa: F401


def test_import_dice():
    import dice  # noqa: F401


def test_import_exceptions():
    import exceptions  # noqa: F401


def test_import_render_order():
    import render_order  # noqa: F401


def test_import_equipment_types():
    import equipment_types  # noqa: F401


def test_import_options():
    import options  # noqa: F401


def test_import_tile_types():
    import tile_types  # noqa: F401


def test_import_sound_travel():
    import sound_travel  # noqa: F401


def test_import_base_component():
    from components import base_component  # noqa: F401


def test_import_fighter():
    from components import fighter  # noqa: F401


def test_import_level():
    from components import level  # noqa: F401


def test_import_inventory():
    from components import inventory  # noqa: F401


def test_import_equipment():
    from components import equipment  # noqa: F401


def test_import_equippable():
    from components import equippable  # noqa: F401


def test_import_effect():
    from components import effect  # noqa: F401


def test_import_ai():
    from components import ai  # noqa: F401


def test_import_consumable():
    from components import consumable  # noqa: F401


def test_import_entity():
    import entity  # noqa: F401


def test_import_game_map():
    import game_map  # noqa: F401


def test_import_engine():
    import engine  # noqa: F401


def test_import_actions():
    import actions  # noqa: F401


def test_import_procgen():
    import procgen  # noqa: F401


def test_import_managers():
    import managers  # noqa: F401


def test_import_message_log():
    import message_log  # noqa: F401


def test_import_sounds():
    import sounds  # noqa: F401


def test_import_render_functions():
    import render_functions  # noqa: F401
