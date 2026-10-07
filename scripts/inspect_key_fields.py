import json
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("output_catalog/odoo_models_catalog.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for model, info in data.items():
    print(f"\n==================================================")
    print(f"📦 {model} — {info.get('name_ar')} (إجمالي: {info.get('total_fields')} حقل)")
    print(f"==================================================")
    fields = info.get("fields", {})
    # print required and most important business fields
    for fname, fmeta in sorted(fields.items()):
        if fmeta.get("required") or any(k in fname for k in ["name", "code", "date", "type", "state", "employee", "amount", "wage", "vat", "cr", "bank", "iban", "score", "result", "action", "reason", "benefit"]):
            req_mark = " ⭐ [إلزامي]" if fmeta.get("required") else ""
            print(f"  • {fname} ({fmeta.get('type')}): {fmeta.get('string')}{req_mark}")
