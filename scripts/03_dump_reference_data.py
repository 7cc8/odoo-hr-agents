import os, csv, json, xmlrpc.client
from pathlib import Path

# حمّل .env إن وُجد (بدون مكتبات خارجية)
for p in (Path(".env"), Path(__file__).resolve().parent.parent / ".env"):
    if p.exists():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        break

def env(*names):
    for n in names:
        if os.environ.get(n):
            return os.environ[n]
    raise SystemExit(f"Missing env var, tried: {names}")

URL = env("ODOO_URL").rstrip("/")
DB = env("ODOO_DB")
USER = env("ODOO_USER", "ODOO_USERNAME", "ODOO_LOGIN")
KEY = env("ODOO_API_KEY", "ODOO_PASSWORD", "ODOO_KEY")

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
uid = common.authenticate(DB, USER, KEY, {})
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object", allow_none=True)

def call(model, method, args, kwargs=None):
    return models.execute_kw(DB, uid, KEY, model, method, args, kwargs or {})

def dump(model, wanted, lang=None):
    existing = call(model, "fields_get", [], {"attributes": ["type"]})
    fields = [f for f in wanted if f in existing]
    ctx = {"active_test": False}          # يشمل المؤرشف
    if lang:
        ctx["lang"] = lang
    return call(model, "search_read", [[]], {"fields": fields, "context": ctx, "order": "id"})

def flat(v):
    return v[1] if isinstance(v, list) and len(v) == 2 else v

out = Path("output_catalog/reference")
out.mkdir(parents=True, exist_ok=True)

jobs = [
    ("res.company", ["id", "name", "active"]),
    ("hr.department", ["id", "name", "complete_name", "company_id", "parent_id", "active"]),
    ("hr.job", ["id", "name", "company_id", "department_id", "active"]),
]

for model, wanted in jobs:
    for lang in ("ar_001", "en_US"):
        try:
            rows = dump(model, wanted, lang)
        except Exception as e:
            print(f"[skip] {model} lang={lang}: {str(e)[:120]}")
            continue
        path = out / f"{model.replace('.', '_')}_{lang}.csv"
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else wanted)
            w.writeheader()
            for r in rows:
                w.writerow({k: flat(v) for k, v in r.items()})
        print(f"[ok] {model} lang={lang}: {len(rows)} rows -> {path}")

# فحص سريع: عدد الموظفين نشط/مؤرشف
print(json.dumps({
    "employees_active": call("hr.employee", "search_count", [[]]),
    "employees_all": call("hr.employee", "search_count", [[]], {"context": {"active_test": False}}),
}, ensure_ascii=False))