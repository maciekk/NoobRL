import tcod

TILESETS = [
    ("dejavu10x10_gs_tc.png", (32, 8, tcod.tileset.CHARMAP_TCOD), 2, "@"),
    ("VGA9x16.png", (16, 16, tcod.tileset.CHARMAP_CP437), 1, "@"),
    ("Curses_800x600_shade.png", (16, 16, tcod.tileset.CHARMAP_CP437), 2, "@"),
    ("eofshaded800x600pb9_f64ded.png", (16, 16, tcod.tileset.CHARMAP_CP437), 2, "@"),
    ("Bedstead-20-df.png", (16, 16, tcod.tileset.CHARMAP_CP437), 1, "\002"),
    ("Shizzle_1280x500.png", (16, 16, tcod.tileset.CHARMAP_CP437), 1, "@"),
    ("TerminusAliased_handedit_gal.png", (16, 16, tcod.tileset.CHARMAP_CP437), 0.75, "@"),
    ("Curses_1920x900.png", (16, 16, tcod.tileset.CHARMAP_CP437), 0.5, "@"),
    ("Curses_24pt_cleartype_ThomModifications.png", (16, 16, tcod.tileset.CHARMAP_CP437), 0.75, "@"),
    ("Cooz_curses_14x16.png", (16, 16, tcod.tileset.CHARMAP_CP437), 1, "@"),
    ("Nice_curses_10x12.png", (16, 16, tcod.tileset.CHARMAP_CP437), 2, "@"),
    ("Yoshis_island.png", (16, 16, tcod.tileset.CHARMAP_CP437), 2, "@"),
]

def load_sheet(name):
    for (fname, (x, y, charmap), sfactor, player_char) in TILESETS:
        if name in fname:
            break

    tileset = tcod.tileset.load_tilesheet("tilesets/" + fname, x, y, charmap)
    return tileset, sfactor, player_char