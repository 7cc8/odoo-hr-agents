import json
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("output_catalog/odoo_models_catalog.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for model, info in data.items():
    fields = info.get("fields", {})
    req_fields = [k for k, v in fields.items() if v.get("required")]
    print(f"• {model} ({info.get('name_ar')}): {len(fields)} fields | Required: {len(req_fields)}")
