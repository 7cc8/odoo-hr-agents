import json
from pathlib import Path

cat_path = Path("external/pixel-agents/dist/webview/assets/furniture-catalog.json")
with open(cat_path, "r", encoding="utf-8") as f:
    items = json.load(f)

print(f"Total catalog items: {len(items)}")
print("\n--- default-layout-1.json furniture ---")
print("\n--- default-layout-2.json chairs ---")
with open("external/pixel-agents/webview-ui/public/assets/default-layout-2.json") as f:
    d = json.load(f)
for it in d["furniture"]:
    if "CHAIR" in it["type"] or "BENCH" in it["type"]:
        print(f"{it['uid']:<16} | {it['type']:<22} | col={it['col']}, row={it['row']}")
