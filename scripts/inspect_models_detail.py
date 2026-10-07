import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from odoo_readonly_repository import OdooReadonlyRepository

repo = OdooReadonlyRepository()
repo.connect()

models_to_check = [
    ("res.company", "الشركة"),
    ("hr.version", "العقود والبدلات"),
    ("hr.leave", "الإجازات"),
    ("attendance.sheet", "سجل الحضور"),
    ("overtime.request", "العمل الإضافي"),
    ("disciplinary.action", "الجزاءات والانضباط"),
    ("warning.letter", "خطابات الإنذار"),
    ("hr.end.service.benefit", "مكافأة نهاية الخدمة"),
    ("gr.transaction", "المعاملات الحكومية"),
    ("approval.request", "الموافقات العامة"),
    ("appraisal.request", "تقييمات الموظفين"),
    ("annual.evaluation", "التقييم السنوي"),
    ("hr.applicant", "التوظيف"),
    ("new.hiring.request", "طلبات التوظيف الجديد")
]

results = {}
for m, ar_name in models_to_check:
    try:
        fields = repo._execute_kw(m, "fields_get", [], {"attributes": ["type", "string", "required", "selection"]})
        results[m] = {
            "name_ar": ar_name,
            "total_fields": len(fields),
            "fields": {
                k: {
                    "type": v.get("type"),
                    "string": v.get("string"),
                    "required": bool(v.get("required")),
                    "selection": v.get("selection") if v.get("type") == "selection" else None
                } for k, v in fields.items()
            }
        }
        print(f"OK: {m} ({ar_name}) -> {len(fields)} fields")
    except Exception as e:
        print(f"FAIL: {m} -> {e}")

with open("output_catalog/odoo_models_catalog.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\nSaved full schema to output_catalog/odoo_models_catalog.json")
