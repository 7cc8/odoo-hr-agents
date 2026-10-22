"""failure_codes.py is the single source of truth: every code the validator emits must map to
the final_status the validator actually returns for it (VALIDATION_ERROR used to say "failed"
while the validator returned "rejected")."""
import os
import re

import pytest

import failure_codes
from failure_codes import status_for_failure_code
from tests.test_excel_pipeline_hardening import StrictRepo
from tests.test_validator import FakeRepository, make_row
from validator import Validator

COMPANY = "شركة النخبة الذكية للتقنية"
COMPANY_REF = [15, COMPANY]


def _refs(company_active=True, extra_company=False):
    company = {"id": 15, "name": COMPANY, "active": company_active}
    companies = [company] + ([{"id": 16, "name": COMPANY, "active": True}] if extra_company else [])
    department = {"id": 8, "name": "الموارد البشرية", "complete_name": "الإدارة العليا / الموارد البشرية",
                  "company_id": COMPANY_REF, "active": True}
    job = {"id": 22, "name": "أخصائي موارد بشرية", "company_id": COMPANY_REF, "department_id": False, "active": True}
    return companies, [department], [job]


def _existing(i):
    return {"id": 90 + i, "name": "أحمد", "work_email": "ahmed@example.com", "company_id": COMPANY_REF, "active": True}


def _run(row, repo=None, **ref_kw):
    companies, departments, jobs = _refs(**ref_kw)
    repo = repo or FakeRepository(companies, departments, jobs, [])
    return Validator(repo).validate_rows([row])[0]


def _cases():
    c, d, j = _refs()
    yield "accepted", _run(make_row())
    yield "empty name", _run(make_row(name_value="", name_match=""))
    yield "invalid email", _run(make_row(work_email_value="not-an-email", work_email_match="not-an-email"))
    yield "company missing", _run(make_row(company_value="شركة غير موجودة"))
    yield "company ambiguous", _run(make_row(), extra_company=True)
    yield "company archived", _run(make_row(), company_active=False)
    yield "department missing", _run(make_row(department_value="قسم غير موجود"))
    yield "job missing", _run(make_row(job_value="وظيفة غير موجودة"))
    yield "duplicate in file", _run(make_row(parser_flags=["duplicate_in_file"]))
    yield "possible duplicate in file", _run(make_row(parser_flags=["possible_duplicate_in_file"]))
    yield "existing employee", _run(make_row(), FakeRepository(c, d, j, [_existing(1)]))
    yield "ambiguous duplicate", _run(make_row(), FakeRepository(c, d, j, [_existing(1), _existing(2)]))
    yield "no email no mobile", _run(make_row(work_email_value="", work_email_match=None, mobile_value="", mobile_match=None))
    yield "no email with mobile", _run(make_row(work_email_value="", work_email_match=None))
    yield "duplicate check unavailable", _run(make_row(), StrictRepo(c, d, j, error=RuntimeError("odoo down")))


CASES = list(_cases())


@pytest.mark.parametrize("label,result", CASES, ids=[c[0] for c in CASES])
def test_validator_status_matches_failure_codes(label, result):
    code = result["failure_code"]
    if code is None:
        assert result["final_status"] == "accepted"
    else:
        assert status_for_failure_code(code) == result["final_status"], (label, code)


def test_every_code_the_validator_can_emit_is_exercised():
    """Adding a new code to validator.py without a case above fails here."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "validator.py"), encoding="utf-8") as fh:
        source = fh.read()
    emitted = {getattr(failure_codes, name)
               for name in re.findall(r"result\(\s*FINAL_[A-Z_]+,\s*([A-Z_]+)\b", source)}
    exercised = {r["failure_code"] for _, r in CASES if r["failure_code"]}
    assert emitted == exercised, (sorted(emitted - exercised), sorted(exercised - emitted))
