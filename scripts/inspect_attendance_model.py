import sys
sys.path.insert(0, ".")
from odoo_readonly_repository import OdooReadonlyRepository

repo = OdooReadonlyRepository()
repo.connect()

fields = repo._execute_kw('hr.attendance', 'fields_get', [], {'attributes': ['type', 'string', 'required']})
print(f"Total hr.attendance fields: {len(fields)}")
for f, info in sorted(fields.items()):
    req = info.get('required', False)
    t = info['type']
    s = info['string']
    print(f"  {f} ({t}): {s} [Required: {req}]")

sample = repo._execute_kw('hr.attendance', 'search_read', [[]], {'limit': 5})
print(f"\nSample Attendances Count: {len(sample)}")
for s in sample:
    print(f"  {s}")
