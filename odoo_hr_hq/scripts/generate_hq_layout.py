import json
import uuid
from pathlib import Path

# 1. البحث عن ملف الخريطة الافتراضي في external/pixel-agents لاستخراج معرفات الأثاث الدقيقة لنسخة v1.3
root = Path(__file__).resolve().parent
pa_dir = root / "external" / "pixel-agents"
default_layouts = list(pa_dir.rglob("*default-layout*.json")) if pa_dir.exists() else []

# قيم افتراضية قياسية لمحرك pixel-agents
WALL = 0
FLOOR_WOOD = 1
FLOOR_DARK = 2
FLOOR_BLUE = 3
FLOOR_CARPET = 4
FLOOR_GRASS = 5
FLOOR_ROAD = 6
FLOOR_BRIDGE = 7
VOID = 8

# استخراج أسماء أنواع الأثاث الفعلية من الخريطة الافتراضية الموجودة على جهازك
types_map = {
    "desk": "desk",
    "chair": "chair",
    "pc": "pc",
    "bookshelf": "bookshelf",
    "plant": "plant",
    "clock": "clock",
    "sofa": "sofa",
    "table": "coffee-table",
    "painting": "painting",
    "cooler": "cooler",
    "bin": "bin",
}

base_version = 1
if default_layouts:
    try:
        raw = json.loads(default_layouts[0].read_text(encoding="utf-8"))
        base_version = raw.get("version", 1)
        existing_types = [item.get("type", "") for item in raw.get("furniture", []) if item.get("type")]
        print(f"📦 تم قراءة الكتالوج الأصلي من: {default_layouts[0].name} ({len(existing_types)} قطعة أثاث)")
        for t in existing_types:
            tl = t.lower()
            if "desk" in tl and "desk" not in types_map.get("_locked", []):
                types_map["desk"] = t
            elif ("chair" in tl or "stool" in tl):
                types_map["chair"] = t
            elif ("pc" in tl or "monitor" in tl or "computer" in tl):
                types_map["pc"] = t
            elif ("book" in tl or "shelf" in tl):
                types_map["bookshelf"] = t
            elif "plant" in tl:
                types_map["plant"] = t
            elif "clock" in tl:
                types_map["clock"] = t
            elif ("sofa" in tl or "couch" in tl):
                types_map["sofa"] = t
            elif "table" in tl:
                types_map["table"] = t
            elif ("paint" in tl or "art" in tl or "frame" in tl):
                types_map["painting"] = t
            elif ("cooler" in tl or "coffee" in tl or "fridge" in tl):
                types_map["cooler"] = t
    except Exception as e:
        print(f"⚠️ تنبيه أثناء قراءة القالب الافتراضي: {e}")

# 2. أبعاد الخريطة الكاملة (64 عمود × 56 صف) لمحاكاة المقر الكامل في الصورة
COLS = 64
ROWS = 56

tiles = [FLOOR_GRASS for _ in range(COLS * ROWS)]
tile_colors = [None for _ in range(COLS * ROWS)]
furniture = []

def color_hsbc(h, s, b, c=0, colorize=True):
    return {"h": h, "s": s, "b": b, "c": c, "colorize": colorize}

# الألوان المطابقة للصورة الأصلية
COLOR_GRASS      = color_hsbc(135, 45, -25, 0, True)   # أخضر الحدائق
COLOR_POND       = color_hsbc(200, 70, -10, 10, True)  # أزرق البركة
COLOR_CORRIDOR   = color_hsbc(220, 35, -55, 10, True)  # كحلي داكن للممرات الأفقية
COLOR_BRIDGE     = color_hsbc(40,  65, -10, 15, True)  # ذهبي خشبي للجسر الوسطي
COLOR_STEP_STONE = color_hsbc(210, 10, -20, 0, True)   # حجري للممرات الفرعية
COLOR_WOOD_WARM  = color_hsbc(25,  60, -20, 10, True)  # خشب بني دافئ للغرف
COLOR_DARK_ROOM  = color_hsbc(225, 40, -45, 10, True)  # أرضية داكنة للاستوديو والبوث
COLOR_BLUE_RUG   = color_hsbc(215, 65, -20, 15, True)  # سجادة زرقاء (جناح المدير والمكتبة)
COLOR_PURPLE_RUG = color_hsbc(275, 55, -30, 15, True)  # سجادة بنفسجية (الاستوديو)
COLOR_GREEN_RUG  = color_hsbc(145, 55, -25, 10, True)  # سجادة خضراء (المستشار والنمو)

def set_tile(c, r, t, col_obj=None):
    if 0 <= c < COLS and 0 <= r < ROWS:
        idx = r * COLS + c
        tiles[idx] = t
        tile_colors[idx] = col_obj

def fill_rect(c1, r1, w, h, t, col_obj=None):
    for rr in range(r1, r1 + h):
        for cc in range(c1, c1 + w):
            set_tile(cc, rr, t, col_obj)

def add_item(item_type_key, c, r):
    t_name = types_map.get(item_type_key, item_type_key)
    furniture.append({
        "uid": f"hq-{uuid.uuid4().hex[:8]}",
        "type": t_name,
        "col": c,
        "row": r,
    })

def build_room(c1, r1, w, h, floor_color, door_side="bottom", rug=None):
    # الأرضية
    fill_rect(c1, r1, w, h, FLOOR_WOOD, floor_color)
    # الجدران المحيطة
    for cc in range(c1, c1 + w):
        set_tile(cc, r1, WALL)
        set_tile(cc, r1 + h - 1, WALL)
    for rr in range(r1, r1 + h):
        set_tile(c1, rr, WALL)
        set_tile(c1 + w - 1, rr, WALL)
    # فتحة الباب (بلاطتان)
    mid_c = c1 + w // 2
    if door_side == "bottom":
        set_tile(mid_c - 1, r1 + h - 1, FLOOR_WOOD, floor_color)
        set_tile(mid_c,     r1 + h - 1, FLOOR_WOOD, floor_color)
    elif door_side == "top":
        set_tile(mid_c - 1, r1, FLOOR_WOOD, floor_color)
        set_tile(mid_c,     r1, FLOOR_WOOD, floor_color)
    # السجادة الداخلية إن وجدت
    if rug:
        rc, rr, rw, rh, rcol = rug
        fill_rect(c1 + rc, r1 + rr, rw, rh, FLOOR_CARPET, rcol)

def add_workstation(c, r):
    """إضافة مكتب + شاشة كمبيوتر + كرسي جلوس للوكيل"""
    add_item("desk", c, r)
    add_item("pc", c, r)
    add_item("chair", c, r + 1)

# أ. تلوين أرضية الحديقة الكاملة بالأخضر مع إطار جدار خارجي
fill_rect(0, 0, COLS, ROWS, FLOOR_GRASS, COLOR_GRASS)
for c in range(COLS):
    set_tile(c, 0, WALL)
    set_tile(c, ROWS - 1, WALL)
for r in range(ROWS):
    set_tile(0, r, WALL)
    set_tile(COLS - 1, r, WALL)

# ب. رسم البركة المائية في الحديقة العلوية اليسرى واليمنى
fill_rect(10, 4, 5, 3, FLOOR_BLUE, COLOR_POND)
fill_rect(49, 4, 4, 3, FLOOR_BLUE, COLOR_POND)
fill_rect(12, 48, 4, 3, FLOOR_BLUE, COLOR_POND)

# ج. رسم الـ 4 شوارع الأفقية الداكنة (Corridors)
for corr_r in (11, 23, 35, 46):
    fill_rect(1, corr_r, COLS - 2, 2, FLOOR_ROAD, COLOR_CORRIDOR)

# د. رسم الجسر الخشبي الذهبي الطولي في المنتصف (من جناح المدير حتى الأسفل)
fill_rect(31, 10, 2, ROWS - 11, FLOOR_BRIDGE, COLOR_BRIDGE)

# هـ. بناء الغرف الـ 14 المطابقة للصورة الأصلية:

# 1. جناح المدير التنفيذي (CEO SUITE - سراج) في الأعلى بالمنتصف
build_room(24, 1, 16, 10, COLOR_WOOD_WARM, door_side="bottom", rug=(3, 2, 10, 5, COLOR_BLUE_RUG))
add_item("plant", 25, 2)
add_item("plant", 38, 2)
add_item("painting", 31, 1)
add_workstation(31, 4)   # مكتب سراج (CEO)
add_workstation(27, 7)   # مكتب رئيس الموظفين (Sofia / CoS)

# === الصف الأول من الغرف (Rows 13..22) ===
# 2. WRITERS' ROOM (فاحص وسجل)
build_room(2, 13, 12, 10, COLOR_WOOD_WARM, door_side="bottom", rug=(2, 6, 8, 2, COLOR_BLUE_RUG))
add_item("bookshelf", 4, 13)
add_item("bookshelf", 9, 13)
add_item("plant", 3, 14)
add_workstation(5, 16)
add_workstation(10, 16)

# 3. MONTAGE STUDIO (مصلح)
build_room(17, 13, 13, 10, COLOR_DARK_ROOM, door_side="bottom", rug=(2, 6, 6, 2, COLOR_PURPLE_RUG))
add_item("plant", 18, 14)
add_item("cooler", 20, 14)
add_workstation(26, 16)

# 4. RECORDING BOOTH (الصوتيات)
build_room(34, 13, 13, 10, COLOR_DARK_ROOM, door_side="bottom", rug=(4, 4, 3, 3, COLOR_BLUE_RUG))
add_item("plant", 35, 14)
add_item("plant", 45, 14)
add_workstation(43, 17)

# 5. SHARED MEETING ROOM (غرفة الاجتماعات الكبرى)
build_room(50, 13, 12, 10, COLOR_WOOD_WARM, door_side="bottom", rug=(2, 3, 8, 5, COLOR_BLUE_RUG))
add_item("painting", 55, 13)
add_item("plant", 51, 14)
add_item("plant", 60, 20)
# طاولة الاجتماعات الكبيرة المحاطة بالكراسي
for tc in range(53, 59):
    add_item("desk", tc, 17)
    add_item("chair", tc, 16)
    add_item("chair", tc, 18)

# === الصف الثاني من الغرف (Rows 25..34) ===
# 6. WEB ROOM (بوابة أودو)
build_room(2, 25, 12, 10, COLOR_DARK_ROOM, door_side="bottom", rug=(3, 6, 6, 2, COLOR_BLUE_RUG))
add_item("bookshelf", 4, 25)
add_item("plant", 12, 26)
add_workstation(8, 28)

# 7. WEB & ACADEMY (مدقق نظام العمل)
build_room(17, 25, 13, 10, COLOR_WOOD_WARM, door_side="bottom", rug=(3, 6, 7, 2, COLOR_DARK_ROOM))
add_item("bookshelf", 19, 25)
add_item("bookshelf", 25, 25)
add_workstation(20, 28)
add_workstation(26, 28)

# 8. GITHUB LIBRARY (مكتبة المهارات والقوانين)
build_room(34, 25, 13, 10, COLOR_WOOD_WARM, door_side="bottom", rug=(2, 3, 9, 5, COLOR_PURPLE_RUG))
for bc in range(35, 46, 2):
    add_item("bookshelf", bc, 25)
add_workstation(37, 28)
add_workstation(43, 28)
add_workstation(37, 31)
add_workstation(43, 31)

# 9. ADVISOR'S LIBRARY (غرفة المستشار)
build_room(50, 25, 12, 10, COLOR_WOOD_WARM, door_side="bottom", rug=(2, 6, 8, 2, COLOR_GREEN_RUG))
add_item("bookshelf", 52, 25)
add_item("bookshelf", 57, 25)
add_item("sofa", 53, 28)
add_workstation(58, 28)

# === الصف الثالث من الغرف (Rows 37..45) ===
# 10. PUBLISHER HUB (كاتب - منفذ العمليات)
build_room(2, 37, 12, 9, COLOR_WOOD_WARM, door_side="top")
add_item("clock", 7, 37)
add_item("plant", 3, 38)
add_workstation(5, 41)
add_workstation(10, 41)

# 11. MAILROOM (تيليجرام والإشعارات)
build_room(17, 37, 13, 9, COLOR_WOOD_WARM, door_side="top", rug=(3, 6, 7, 2, COLOR_DARK_ROOM))
add_item("cooler", 18, 38)
add_workstation(23, 41)

# 12. ADS & GUARD ROOM (حارس الأمان)
build_room(34, 37, 13, 9, COLOR_WOOD_WARM, door_side="top", rug=(3, 6, 7, 2, COLOR_PURPLE_RUG))
add_item("painting", 38, 37)
add_item("clock", 44, 37)
add_workstation(39, 41)

# 13. GROWTH & MATCH ROOM (موفّق - المطابقة)
build_room(50, 37, 12, 9, COLOR_WOOD_WARM, door_side="top", rug=(2, 6, 8, 2, COLOR_GREEN_RUG))
add_item("plant", 51, 38)
add_item("plant", 60, 38)
add_workstation(55, 41)

# === الصف الرابع السفلي (Rows 48..54) ===
# 14. FINANCE OFFICE (مكتب الرواتب ومكافأة نهاية الخدمة EOSB)
build_room(50, 48, 12, 7, COLOR_WOOD_WARM, door_side="top")
add_item("bookshelf", 52, 48)
add_item("bookshelf", 58, 48)
add_workstation(55, 51)

# و. إضافة الممرات الحجرية الفرعية والأشجار في الحدائق
for r_strip in list(range(13, 23)) + list(range(25, 35)) + list(range(37, 46)):
    set_tile(15, r_strip, FLOOR_WOOD, COLOR_STEP_STONE)
    set_tile(48, r_strip, FLOOR_WOOD, COLOR_STEP_STONE)

garden_plants = [
    (4, 3), (8, 7), (18, 4), (21, 8), (43, 4), (47, 8), (57, 4), (60, 8),
    (5, 50), (10, 52), (20, 49), (26, 52), (38, 50), (45, 52)
]
for gp_c, gp_r in garden_plants:
    add_item("plant", gp_c, gp_r)

layout_data = {
    "version": base_version,
    "cols": COLS,
    "rows": ROWS,
    "tiles": tiles,
    "tileColors": tile_colors,
    "furniture": furniture,
}

# حفظ الملف في جذر المشروع وفي مجلد config
out_main = root / "hq_company_layout.json"
out_main.write_text(json.dumps(layout_data, indent=2), encoding="utf-8")

# تحديث الملف الافتراضي داخل external/pixel-agents إن وجد
for dl in default_layouts:
    try:
        dl.write_text(json.dumps(layout_data, indent=2), encoding="utf-8")
        print(f"✅ تم تحديث الخريطة الافتراضية في: {dl}")
    except Exception:
        pass

print(f"\n🎉 تم توليد خريطة الـ 14 غرفة بنجاح في:\n   {out_main}")
