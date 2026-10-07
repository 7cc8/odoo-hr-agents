# scripts/05_live_repository_check.py
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # عدّل لمكان الملفات
from odoo_readonly_repository import OdooReadonlyRepository
from parser import parse_xlsx
from validator import Validator

repo = OdooReadonlyRepository()
repo.connect()
print(json.dumps({"url": repo.url, "db": repo.db, "uid": repo.uid,
                  "version": repo.version().get("server_version")}, ensure_ascii=False))

snap = repo.get_live_reference_snapshot()
print("counts:", {k: len(v) for k, v in snap.items()},
      "| expected: companies 3, departments 6, jobs 5")

emps = repo._execute_kw("hr.employee", "search_read", [[]],
    {"fields": ["id", "name", "work_email"], "context": {"active_test": False}})
print("employees:", len(emps))
for e in emps:
    print(" ", e["id"], e["name"], "|", e["work_email"])

if len(sys.argv) > 1:   # python scripts/05_live_repository_check.py test10.xlsx
    parsed = parse_xlsx(sys.argv[1])
    for r in Validator(repo).validate_rows(parsed["rows"]):
        print(r["excel_row_number"], r["final_status"], r["failure_code"])

for r in parsed["rows"]:
    print(r["excel_row_number"], "mobile value/match:",
          r["fields"]["mobile_phone"]["value"], "|",
          r["fields"]["mobile_phone"]["match_key"])