import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from odoo_readonly_repository import OdooReadonlyRepository

repo = OdooReadonlyRepository()
repo.connect()

loan_models = [
    ("employee.loan", "قروض وسلف الموظفين"),
    ("employee.loan.type", "أنواع القروض"),
    ("installment.line", "أقساط القرض"),
    ("dev.skip.installment", "تأجيل الأقساط")
]

for m, ar in loan_models:
    try:
        fields = repo._execute_kw(m, "fields_get", [], {"attributes": ["type", "string", "required", "selection"]})
        print(f"\n==================================================")
        print(f"📦 {m} — {ar} (إجمالي: {len(fields)} حقل)")
        print(f"==================================================")
        for k, v in sorted(fields.items()):
            if v.get("required") or any(w in k.lower() for w in ["name", "loan", "amount", "date", "installment", "employee", "state", "rate", "type", "term"]):
                req = " ⭐ [إلزامي]" if v.get("required") else ""
                print(f"  • {k} ({v.get('type')}): {v.get('string')}{req}")
    except Exception as e:
        print(f"FAIL {m}: {e}")
