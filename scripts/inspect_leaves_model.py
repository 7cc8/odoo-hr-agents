import sys
sys.path.insert(0, ".")
from odoo_readonly_repository import OdooReadonlyRepository

repo = OdooReadonlyRepository()
repo.connect()

# 1. Inspect hr.leave.type fields
type_fields = repo._execute_kw('hr.leave.type', 'fields_get', [], {'attributes': ['type', 'string']})
print("Available hr.leave.type fields:")
for f, info in sorted(type_fields.items()):
    if any(term in f for term in ['name', 'valid', 'unit', 'alloc', 'code', 'requir', 'company']):
        print(f"  {f} ({info['type']}): {info['string']}")

# 2. Read all leave types
types = repo._execute_kw(
    'hr.leave.type',
    'search_read',
    [[]],
    {'fields': ['id', 'name', 'request_unit', 'active']}
)
print(f"\nTotal Leave Types: {len(types)}")
for t in types:
    print(f"  ID={t['id']} | Name={t['name']} | Active={t.get('active')} | Unit={t.get('request_unit')}")

# 3. Inspect hr.leave fields
leave_fields = repo._execute_kw('hr.leave', 'fields_get', [], {'attributes': ['type', 'string', 'required']})
print("\nKey hr.leave fields:")
important = ['employee_id', 'holiday_status_id', 'request_date_from', 'request_date_to', 'date_from', 'date_to', 'number_of_days', 'state', 'name', 'department_id', 'company_id']
for k in important:
    if k in leave_fields:
        print(f"  {k} ({leave_fields[k]['type']}): {leave_fields[k]['string']} [Required: {leave_fields[k].get('required')}]")

# 4. Read sample existing leave records
sample_leaves = repo._execute_kw(
    'hr.leave',
    'search_read',
    [[]],
    {'fields': ['id', 'employee_id', 'holiday_status_id', 'request_date_from', 'request_date_to', 'number_of_days', 'state'], 'limit': 5}
)
print(f"\nSample Existing Leaves ({len(sample_leaves)}):")
for l in sample_leaves:
    print(f"  {l}")
