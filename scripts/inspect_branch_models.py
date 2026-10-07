import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from odoo_readonly_repository import OdooReadonlyRepository

repo = OdooReadonlyRepository()
repo.connect()

print("--- CHECKING BRANCH & LOCATION IN ODOO ---")
for m in ["hr.work.location", "res.branch"]:
    try:
        f = repo._execute_kw(m, "fields_get", [], {"attributes": ["type", "string"]})
        print(f"Model {m} EXISTS with {len(f)} fields")
    except Exception as e:
        print(f"Model {m} NOT FOUND: {e}")

comp_fields = repo._execute_kw("res.company", "fields_get", [], {"attributes": ["type", "string"]})
for k in sorted(comp_fields):
    if any(w in k.lower() for w in ["branch", "parent", "child"]):
        print(f"res.company field: {k} ({comp_fields[k].get('type')}) -> '{comp_fields[k].get('string')}'")

emp_fields = repo._execute_kw("hr.employee", "fields_get", [], {"attributes": ["type", "string"]})
for k in sorted(emp_fields):
    if any(w in k.lower() for w in ["branch", "location", "work_location"]):
        print(f"hr.employee field: {k} ({emp_fields[k].get('type')}) -> '{emp_fields[k].get('string')}'")

# Check existing companies/branches in database
comps = repo.get_accessible_companies()
print("\n--- ACCESSIBLE COMPANIES / BRANCHES IN DB ---")
for c in comps:
    print(f"ID {c.get('id')}: {c.get('name')}")
