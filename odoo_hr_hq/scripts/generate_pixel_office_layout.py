"""
Generate default-layout-2.json for external/pixel-agents/webview-ui
Matches the 14-room AI HQ Campus Layout with central boulevard, gardens,
all rooms, furniture, colors, and area definitions.
"""
import json
from pathlib import Path

COLS = 58
ROWS = 56
TOTAL_TILES = COLS * ROWS

# Tile Types
TILE_WALL = 0
TILE_FLOOR_1 = 1   # Plain / colored floor
TILE_FLOOR_7 = 7   # Wood planks
TILE_VOID = 255

tiles = [TILE_VOID] * TOTAL_TILES
tile_colors = [None] * TOTAL_TILES
area_tiles = [None] * TOTAL_TILES
furniture = []

# Color palettes (H, S, B, C)
COLOR_GRASS = {"h": 125, "s": 42, "b": -35, "c": -15}
COLOR_POND = {"h": 205, "s": 75, "b": -20, "c": 0}
COLOR_FOUNTAIN = {"h": 195, "s": 85, "b": 10, "c": 20}
COLOR_ROAD = {"h": 220, "s": 12, "b": -75, "c": -40}
COLOR_ROAD_YELLOW = {"h": 46, "s": 95, "b": 15, "c": 40}
COLOR_SIDEWALK = {"h": 215, "s": 15, "b": -50, "c": -20}
COLOR_WALL = {"h": 218, "s": 25, "b": -65, "c": -45}

COLOR_WOOD_WARM = {"h": 25, "s": 48, "b": -43, "c": -88}
COLOR_WOOD_MAHOGANY = {"h": 18, "s": 52, "b": -55, "c": -88}
COLOR_RUG_BLUE = {"h": 210, "s": 55, "b": -30, "c": -60}
COLOR_RUG_PURPLE = {"h": 272, "s": 45, "b": -40, "c": -60}
COLOR_RUG_TEAL = {"h": 178, "s": 50, "b": -35, "c": -60}
COLOR_RUG_GREEN = {"h": 142, "s": 50, "b": -35, "c": -60}
COLOR_RUG_BROWN = {"h": 32, "s": 45, "b": -50, "c": -60}
COLOR_DARK_SLATE = {"h": 228, "s": 22, "b": -75, "c": -50}
COLOR_RUG_RED = {"h": 355, "s": 55, "b": -35, "c": -55}

def set_tile(col, row, t_type, color=None, area=None):
    if 0 <= col < COLS and 0 <= row < ROWS:
        idx = row * COLS + col
        tiles[idx] = t_type
        tile_colors[idx] = color
        area_tiles[idx] = area

def fill_rect(col_start, col_end, row_start, row_end, t_type, color=None, area=None):
    for r in range(row_start, row_end + 1):
        for c in range(col_start, col_end + 1):
            set_tile(c, r, t_type, color, area)

def build_room(col_start, col_end, row_start, row_end, floor_type, floor_color, area_name, rug_color=None, rug_inset=(2,2,2,2)):
    # Walls
    for c in range(col_start, col_end + 1):
        set_tile(c, row_start, TILE_WALL, COLOR_WALL)
        set_tile(c, row_end, TILE_WALL, COLOR_WALL)
    for r in range(row_start, row_end + 1):
        set_tile(col_start, r, TILE_WALL, COLOR_WALL)
        set_tile(col_end, r, TILE_WALL, COLOR_WALL)
    # Floor inside
    fill_rect(col_start + 1, col_end - 1, row_start + 1, row_end - 1, floor_type, floor_color, area_name)
    # Rug if specified
    if rug_color:
        rx1 = col_start + rug_inset[0]
        rx2 = col_end - rug_inset[1]
        ry1 = row_start + rug_inset[2]
        ry2 = row_end - rug_inset[3]
        if rx1 <= rx2 and ry1 <= ry2:
            fill_rect(rx1, rx2, ry1, ry2, TILE_FLOOR_1, rug_color, area_name)

# 1. Base Green Ground everywhere
fill_rect(0, COLS - 1, 0, ROWS - 1, TILE_FLOOR_1, COLOR_GRASS)

# 2. Roads
# Central boulevard: cols 26..31 from row 11 to 55
for r in range(11, 55):
    set_tile(26, r, TILE_FLOOR_1, COLOR_SIDEWALK)
    set_tile(27, r, TILE_FLOOR_1, COLOR_ROAD)
    set_tile(28, r, TILE_FLOOR_1, COLOR_ROAD_YELLOW if r % 3 != 0 else COLOR_ROAD)
    set_tile(29, r, TILE_FLOOR_1, COLOR_ROAD_YELLOW if r % 3 != 0 else COLOR_ROAD)
    set_tile(30, r, TILE_FLOOR_1, COLOR_ROAD)
    set_tile(31, r, TILE_FLOOR_1, COLOR_SIDEWALK)

# Horizontal Roads:
# Road 1: row 11..12, cols 2..55
for r in (11, 12):
    for c in range(2, 56):
        set_tile(c, r, TILE_FLOOR_1, COLOR_ROAD)
# Road 2: row 22..23, cols 2..55
for r in (22, 23):
    for c in range(2, 56):
        set_tile(c, r, TILE_FLOOR_1, COLOR_ROAD)
# Road 3: row 33..34, cols 2..55
for r in (33, 34):
    for c in range(2, 56):
        set_tile(c, r, TILE_FLOOR_1, COLOR_ROAD)
# Road 4: row 44..45, cols 2..55
for r in (44, 45):
    for c in range(2, 56):
        set_tile(c, r, TILE_FLOOR_1, COLOR_ROAD)

# 3. Gardens & Ponds
# Top-Left Garden (cols 2..20, rows 2..10)
# Pond at cols 8..11, rows 5..7
fill_rect(8, 11, 5, 7, TILE_FLOOR_1, COLOR_POND)
# Top-Right Garden (cols 37..55, rows 2..10)
# Fountain at cols 45..48, rows 5..7
fill_rect(45, 48, 5, 7, TILE_FLOOR_1, COLOR_FOUNTAIN)
# Bottom-Left Garden (cols 2..25, rows 46..54)
fill_rect(8, 12, 49, 52, TILE_FLOOR_1, COLOR_POND)

TILE_FLOOR_4 = 4   # Threshold plank tile
COLOR_DOOR_THRESHOLD = {"h": 36, "s": 85, "b": 18, "c": 35} # Bright golden amber wood threshold

def make_doorway(col1, row1, col2, row2, area_name):
    set_tile(col1, row1, TILE_FLOOR_4, COLOR_DOOR_THRESHOLD, area_name)
    set_tile(col2, row2, TILE_FLOOR_4, COLOR_DOOR_THRESHOLD, area_name)

# 4. Rooms
# Top Row: CEO SUITE (cols 21..36, rows 2..10)
build_room(21, 36, 2, 10, TILE_FLOOR_7, COLOR_WOOD_WARM, "CEO SUITE", COLOR_RUG_BLUE, (3, 3, 3, 2))
# CEO Suite Door opening at col 28..29, row 10
make_doorway(28, 10, 29, 10, "CEO SUITE")

# Row 1 (rows 13..21):
# Writers' Room: cols 2..13
build_room(2, 13, 13, 21, TILE_FLOOR_7, COLOR_WOOD_WARM, "WRITERS' ROOM", COLOR_RUG_BLUE, (2, 2, 4, 2))
make_doorway(7, 21, 8, 21, "WRITERS' ROOM")

# Montage Studio: cols 14..25
build_room(14, 25, 13, 21, TILE_FLOOR_1, COLOR_DARK_SLATE, "MONTAGE STUDIO", COLOR_RUG_PURPLE, (2, 2, 4, 2))
make_doorway(25, 17, 25, 18, "MONTAGE STUDIO")

# Recording Booth: cols 32..43
build_room(32, 43, 13, 21, TILE_FLOOR_1, COLOR_DARK_SLATE, "RECORDING BOOTH", None)
make_doorway(32, 17, 32, 18, "RECORDING BOOTH")

# Shared Meeting Room: cols 44..55
build_room(44, 55, 13, 21, TILE_FLOOR_7, COLOR_WOOD_WARM, "SHARED MEETING ROOM", COLOR_RUG_BLUE, (2, 2, 2, 2))
make_doorway(49, 21, 50, 21, "SHARED MEETING ROOM")

# Row 2 (rows 24..32):
# Web Room: cols 2..13
build_room(2, 13, 24, 32, TILE_FLOOR_1, COLOR_DARK_SLATE, "WEB ROOM", COLOR_RUG_BLUE, (3, 2, 4, 2))
make_doorway(7, 24, 8, 24, "WEB ROOM")

# Academy: cols 14..25
build_room(14, 25, 24, 32, TILE_FLOOR_7, COLOR_WOOD_WARM, "ACADEMY", COLOR_RUG_BROWN, (2, 2, 4, 2))
make_doorway(25, 28, 25, 29, "ACADEMY")

# Github Library: cols 32..43
build_room(32, 43, 24, 32, TILE_FLOOR_7, COLOR_WOOD_MAHOGANY, "GITHUB LIBRARY", COLOR_RUG_PURPLE, (2, 2, 3, 2))
make_doorway(32, 28, 32, 29, "GITHUB LIBRARY")

# Advisor's Library: cols 44..55
build_room(44, 55, 24, 32, TILE_FLOOR_7, COLOR_WOOD_WARM, "ADVISOR'S LIBRARY", COLOR_RUG_TEAL, (2, 2, 4, 2))
make_doorway(49, 24, 50, 24, "ADVISOR'S LIBRARY")

# Row 3 (rows 35..43):
# Publisher Hub: cols 2..13
build_room(2, 13, 35, 43, TILE_FLOOR_7, COLOR_WOOD_WARM, "PUBLISHER HUB", COLOR_RUG_BLUE, (2, 2, 4, 2))
make_doorway(7, 35, 8, 35, "PUBLISHER HUB")

# Mailroom: cols 14..25
build_room(14, 25, 35, 43, TILE_FLOOR_7, COLOR_WOOD_WARM, "MAILROOM", COLOR_RUG_BLUE, (2, 2, 4, 2))
make_doorway(25, 39, 25, 40, "MAILROOM")

# Ads Room: cols 32..43
build_room(32, 43, 35, 43, TILE_FLOOR_7, COLOR_WOOD_WARM, "ADS ROOM", COLOR_RUG_PURPLE, (2, 2, 4, 2))
make_doorway(32, 39, 32, 40, "ADS ROOM")

# Growth Room: cols 44..55
build_room(44, 55, 35, 43, TILE_FLOOR_7, COLOR_WOOD_WARM, "GROWTH ROOM", COLOR_RUG_GREEN, (2, 2, 4, 2))
make_doorway(49, 35, 50, 35, "GROWTH ROOM")

# Bottom Tier (rows 46..54):
# Finance Office: cols 44..55
build_room(44, 55, 46, 54, TILE_FLOOR_7, COLOR_WOOD_MAHOGANY, "FINANCE OFFICE", COLOR_RUG_PURPLE, (2, 2, 4, 2))
make_doorway(49, 46, 50, 46, "FINANCE OFFICE")

# 5. Furniture Placement
uid_counter = 1
def add_furn(f_type, col, row, color=None, custom_uid=None):
    global uid_counter
    item = {
        "uid": custom_uid or f"f-{uid_counter}",
        "type": f_type,
        "col": col,
        "row": row
    }
    if color:
        item["color"] = color
    furniture.append(item)
    uid_counter += 1

# Outdoor Garden decor (Palm trees, benches, plants)
# Top-Left Garden:
add_furn("LARGE_PLANT", 4, 3)
add_furn("LARGE_PLANT", 16, 3)
add_furn("LARGE_PLANT", 4, 9)
add_furn("LARGE_PLANT", 17, 9)
add_furn("WOODEN_BENCH", 6, 8)
add_furn("WOODEN_BENCH", 13, 8)

# Top-Right Garden:
add_furn("LARGE_PLANT", 39, 3)
add_furn("LARGE_PLANT", 52, 3)
add_furn("LARGE_PLANT", 39, 9)
add_furn("LARGE_PLANT", 52, 9)
add_furn("WOODEN_BENCH", 41, 8)
add_furn("WOODEN_BENCH", 48, 8)

# Bottom-Left Garden:
add_furn("LARGE_PLANT", 4, 47)
add_furn("LARGE_PLANT", 18, 47)
add_furn("LARGE_PLANT", 4, 53)
add_furn("LARGE_PLANT", 20, 53)
add_furn("WOODEN_BENCH", 13, 47)

# Bottom-Right Courtyard:
add_furn("LARGE_PLANT", 34, 47)
add_furn("LARGE_PLANT", 41, 47)
add_furn("WOODEN_BENCH", 36, 51)

# ── 1. CEO Suite (cols 21..36, rows 2..10) — Agent 1: Seraj (CEO) ──
add_furn("DOUBLE_BOOKSHELF", 22, 3)
add_furn("DOUBLE_BOOKSHELF", 34, 3)
add_furn("LARGE_PAINTING", 28, 2)
add_furn("PLANT", 22, 9)
add_furn("PLANT", 35, 9)
# Executive Desk: spans cols 27..29, rows 6..7
add_furn("DESK_FRONT", 27, 6)
add_furn("PC_BACK", 28, 6) # Screen faces CEO at row 5, back of monitor faces visitors at row 8
add_furn("CUSHIONED_CHAIR_FRONT", 28, 5, custom_uid="chair-seraj") # CEO sits facing DOWN into the room
# Visitor Chairs in CEO suite
add_furn("CUSHIONED_CHAIR_BACK", 26, 8)
add_furn("CUSHIONED_CHAIR_BACK", 30, 8)
add_furn("SMALL_TABLE_FRONT", 23, 7)
add_furn("COFFEE", 23, 7)
add_furn("SOFA_FRONT", 32, 7)

# ── 2. Writers' Room (cols 2..13, rows 13..21) — Agent 2: Fahas (Query) ──
add_furn("DOUBLE_BOOKSHELF", 3, 14)
add_furn("CLOCK", 7, 13)
add_furn("PLANT", 11, 14)
add_furn("DESK_FRONT", 6, 16) # spans cols 6..8, rows 16..17
add_furn("PC_FRONT_ON_1", 7, 16) # centered on desk
add_furn("CUSHIONED_CHAIR_BACK", 7, 18, custom_uid="chair-fahas") # sits facing UP directly at PC
add_furn("BIN", 11, 20)

# ── 3. Montage Studio (cols 14..25, rows 13..21) — Agent 3: Musleh (Healer) ──
add_furn("DOUBLE_BOOKSHELF", 15, 14)
add_furn("DOUBLE_BOOKSHELF", 23, 14)
add_furn("DESK_FRONT", 18, 16) # spans cols 18..20, rows 16..17
add_furn("PC_FRONT_ON_2", 19, 16) # centered on desk
add_furn("CUSHIONED_CHAIR_BACK", 19, 18, custom_uid="chair-musleh") # sits facing UP directly at PC
add_furn("COFFEE_TABLE", 15, 19)
add_furn("PLANT_2", 23, 20)

# ── 4. Recording Booth (cols 32..43, rows 13..21) — Shared Sound Studio ──
add_furn("DOUBLE_BOOKSHELF", 33, 14)
add_furn("SOFA_FRONT", 37, 18)
add_furn("COFFEE_TABLE", 37, 16)
add_furn("PLANT", 42, 14)

# ── 5. Shared Meeting Room (cols 44..55, rows 13..21) — Grand Conference ──
add_furn("CLOCK", 49, 13)
add_furn("DOUBLE_BOOKSHELF", 45, 14)
add_furn("DOUBLE_BOOKSHELF", 53, 14)
# Grand Meeting Table (footprint 3x4: cols 48..50, rows 16..19)
add_furn("TABLE_FRONT", 48, 16)
# Conference Chairs around the table:
add_furn("WOODEN_CHAIR_SIDE", 47, 16) # Left side, facing RIGHT
add_furn("WOODEN_CHAIR_SIDE", 47, 17)
add_furn("WOODEN_CHAIR_SIDE", 47, 18)
add_furn("WOODEN_CHAIR_SIDE:left", 51, 16) # Right side, facing LEFT
add_furn("WOODEN_CHAIR_SIDE:left", 51, 17)
add_furn("WOODEN_CHAIR_SIDE:left", 51, 18)
add_furn("CUSHIONED_CHAIR_FRONT", 49, 15) # Top end, facing DOWN
add_furn("CUSHIONED_CHAIR_BACK", 49, 20) # Bottom end, facing UP
add_furn("PLANT", 45, 20)
add_furn("PLANT", 54, 20)

# ── 6. Web Room (cols 2..13, rows 24..32) — Server & Gateway Wing ──
add_furn("DOUBLE_BOOKSHELF", 3, 25)
add_furn("DOUBLE_BOOKSHELF", 3, 27)
add_furn("DOUBLE_BOOKSHELF", 3, 29)
add_furn("PLANT", 11, 25)
add_furn("BIN", 11, 31)

# ── 7. Academy (cols 14..25, rows 24..32) — Agent 4: Mudaqqiq (Law) ──
add_furn("WHITEBOARD", 17, 24)
add_furn("DOUBLE_BOOKSHELF", 23, 25)
add_furn("DESK_FRONT", 18, 27) # spans cols 18..20, rows 27..28
add_furn("PC_FRONT_ON_3", 19, 27) # centered on desk
add_furn("CUSHIONED_CHAIR_BACK", 19, 29, custom_uid="chair-mudaqqiq") # sits facing UP directly at PC
add_furn("PLANT", 24, 31)

# ── 8. Github Library (cols 32..43, rows 24..32) — Knowledge Repository ──
add_furn("DOUBLE_BOOKSHELF", 33, 25)
add_furn("DOUBLE_BOOKSHELF", 35, 25)
add_furn("DOUBLE_BOOKSHELF", 39, 25)
add_furn("DOUBLE_BOOKSHELF", 41, 25)
add_furn("TABLE_FRONT", 35, 27)
add_furn("TABLE_FRONT", 39, 27)
add_furn("PLANT", 33, 31)
add_furn("PLANT", 42, 31)

# ── 9. Advisor's Library (cols 44..55, rows 24..32) — Agent 5: Sijil (Audit) ──
add_furn("DOUBLE_BOOKSHELF", 45, 25)
add_furn("DOUBLE_BOOKSHELF", 52, 25)
add_furn("CLOCK", 49, 24)
add_furn("DESK_FRONT", 48, 27) # spans cols 48..50, rows 27..28
add_furn("PC_FRONT_ON_1", 49, 27) # centered on desk
add_furn("CUSHIONED_CHAIR_BACK", 49, 29, custom_uid="chair-sijil") # sits facing UP directly at PC
add_furn("SOFA_FRONT", 52, 30)
add_furn("PLANT", 54, 31)

# ── 10. Publisher Hub (cols 2..13, rows 35..43) — Agent 6: Katib (Writer) ──
add_furn("DOUBLE_BOOKSHELF", 3, 36)
add_furn("DESK_FRONT", 6, 38) # spans cols 6..8, rows 38..39
add_furn("PC_FRONT_ON_2", 7, 38) # centered on desk
add_furn("CUSHIONED_CHAIR_BACK", 7, 40, custom_uid="chair-katib") # sits facing UP directly at PC
add_furn("PLANT", 11, 36)
add_furn("COFFEE", 4, 40)
add_furn("BIN", 11, 42)

# ── 11. Mailroom (cols 14..25, rows 35..43) — Distribution Center ──
add_furn("DOUBLE_BOOKSHELF", 15, 36)
add_furn("DOUBLE_BOOKSHELF", 18, 36)
add_furn("DOUBLE_BOOKSHELF", 21, 36)
add_furn("SMALL_TABLE_FRONT", 18, 39)
add_furn("PLANT", 24, 42)

# ── 12. Ads Room (cols 32..43, rows 35..43) — Agent 7: Hares (Guard) ──
add_furn("CLOCK", 37, 35)
add_furn("DOUBLE_BOOKSHELF", 41, 36)
add_furn("DESK_FRONT", 36, 38) # spans cols 36..38, rows 38..39
add_furn("PC_FRONT_OFF", 37, 38) # centered on desk
add_furn("CUSHIONED_CHAIR_BACK", 37, 40, custom_uid="chair-hares") # sits facing UP directly at PC
add_furn("PLANT", 33, 42)

# ── 13. Growth Room (cols 44..55, rows 35..43) — Agent 8: Muwaffaq (Match) ──
add_furn("WHITEBOARD", 48, 35)
add_furn("DOUBLE_BOOKSHELF", 45, 36)
add_furn("DOUBLE_BOOKSHELF", 52, 36)
add_furn("DESK_FRONT", 48, 38) # spans cols 48..50, rows 38..39
add_furn("PC_FRONT_ON_3", 49, 38) # centered on desk
add_furn("CUSHIONED_CHAIR_BACK", 49, 40, custom_uid="chair-muwaffaq") # sits facing UP directly at PC
add_furn("PLANT", 54, 42)

# ── 14. Finance Office (cols 44..55, rows 46..54) — Accounting Vault ──
add_furn("DOUBLE_BOOKSHELF", 45, 47)
add_furn("DOUBLE_BOOKSHELF", 52, 47)
add_furn("SMALL_TABLE_FRONT", 48, 49)
add_furn("PLANT", 45, 53)
add_furn("PLANT", 54, 53)

areas = [
    {"label": "CEO SUITE", "color": "#eab308"},
    {"label": "WRITERS' ROOM", "color": "#38bdf8"},
    {"label": "MONTAGE STUDIO", "color": "#818cf8"},
    {"label": "RECORDING BOOTH", "color": "#cbd5e1"},
    {"label": "SHARED MEETING ROOM", "color": "#4ade80"},
    {"label": "WEB ROOM", "color": "#06b6d4"},
    {"label": "ACADEMY", "color": "#f59e0b"},
    {"label": "GITHUB LIBRARY", "color": "#a78bfa"},
    {"label": "ADVISOR'S LIBRARY", "color": "#64748b"},
    {"label": "PUBLISHER HUB", "color": "#d97706"},
    {"label": "MAILROOM", "color": "#38bdf8"},
    {"label": "ADS ROOM", "color": "#ef4444"},
    {"label": "GROWTH ROOM", "color": "#a855f7"},
    {"label": "FINANCE OFFICE", "color": "#eab308"}
]

layout_data = {
    "version": 1,
    "cols": COLS,
    "rows": ROWS,
    "layoutRevision": 2,
    "tiles": tiles,
    "tileColors": tile_colors,
    "furniture": furniture,
    "areas": areas,
    "areaTiles": area_tiles
}

target_path = Path("external/pixel-agents/webview-ui/public/assets/default-layout-2.json")
target_path.parent.mkdir(parents=True, exist_ok=True)
with open(target_path, "w", encoding="utf-8") as f:
    json.dump(layout_data, f, indent=2)

print(f"[OK] Generated {target_path} successfully!")
print(f"   Grid: {COLS}x{ROWS} ({TOTAL_TILES} tiles)")
print(f"   Furniture: {len(furniture)} items placed")
print(f"   Areas: {len(areas)} areas configured")
