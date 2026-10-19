"""Regression tests for the Excel import pipeline hardening (phase-1-5).

Covers: Arabic match-key normalization, fail-closed duplicate lookup in the
validator, and two parser bugs (example-row skip, blank header cell).
"""
import os
import tempfile
import unittest

from openpyxl import Workbook

from failure_codes import DUPLICATE_CHECK_UNAVAILABLE, status_for_failure_code
from normalization import name_match_key, reference_match_key
from parser import (
    TEMPLATE_EXAMPLE_ID, TEMPLATE_EXAMPLE_NAME, parse_xlsx,
)
from tests.test_validator import FakeRepository, make_row
from validator import Validator

HEADERS = ["name", "work_email", "work_phone", "mobile_phone", "job_title", "company", "department", "job"]
COMPANY = "شركة النخبة الذكية للتقنية"


class ArabicMatchKeyTests(unittest.TestCase):
    def test_alef_forms_match(self):
        self.assertEqual(name_match_key("أحمد"), name_match_key("احمد"))
        self.assertEqual(name_match_key("إيمان"), name_match_key("ايمان"))
        self.assertEqual(name_match_key("آمنة"), name_match_key("امنه"))

    def test_taa_marbuta_matches_haa(self):
        self.assertEqual(reference_match_key("الموارد البشرية"), reference_match_key("الموارد البشريه"))

    def test_different_names_stay_different(self):
        self.assertNotEqual(name_match_key("محمد"), name_match_key("أحمد"))
        self.assertNotEqual(name_match_key("سارة"), name_match_key("سامي"))

    def test_existing_behaviour_kept(self):
        self.assertEqual(name_match_key("موسى"), name_match_key("موسي"))
        self.assertEqual(name_match_key("مُحَمَّد"), name_match_key("محمد"))
        self.assertEqual(name_match_key("Ahmed"), "ahmed")


class FailureCodeTests(unittest.TestCase):
    def test_duplicate_check_unavailable_is_needs_review(self):
        self.assertEqual(status_for_failure_code(DUPLICATE_CHECK_UNAVAILABLE), "needs_review")


class StrictRepo(FakeRepository):
    """Looks like the real repository (has _execute_kw), so the strict path is used."""

    def __init__(self, *args, rows=None, error=None):
        super().__init__(*args, [])
        self._rows = rows or []
        self._error = error
        self.calls = []

    def get_company_ids(self):
        return [15]

    def _base_context(self):
        return {"active_test": False}

    def _execute_kw(self, model, method, args, kwargs=None):
        self.calls.append((model, method, args, kwargs))
        if self._error:
            raise self._error
        return self._rows


class FailClosedDuplicateCheckTests(unittest.TestCase):
    def setUp(self):
        self.company = {"id": 15, "name": COMPANY, "active": True}
        self.department = {
            "id": 8, "name": "الموارد البشرية", "complete_name": "الإدارة العليا / الموارد البشرية",
            "company_id": [15, COMPANY], "active": True,
        }
        self.job = {"id": 22, "name": "أخصائي موارد بشرية", "company_id": [15, COMPANY],
                    "department_id": False, "active": True}
        self.args = ([self.company], [self.department], [self.job])

    def _validate(self, repo):
        return Validator(repo).validate_rows([make_row()])[0]

    def test_lookup_failure_is_needs_review_not_accepted(self):
        repo = StrictRepo(*self.args, error=RuntimeError("AccessError: hr.employee"))
        result = self._validate(repo)
        self.assertEqual(result["final_status"], "needs_review")
        self.assertEqual(result["failure_code"], DUPLICATE_CHECK_UNAVAILABLE)

    def test_lookup_finds_existing_employee(self):
        repo = StrictRepo(*self.args, rows=[
            {"id": 91, "name": "أحمد محمد", "work_email": "Ahmed@Example.com",
             "company_id": [15, COMPANY], "active": True}])
        result = self._validate(repo)
        self.assertEqual(result["failure_code"], "duplicate_existing_employee")

    def test_lookup_empty_still_accepts(self):
        result = self._validate(StrictRepo(*self.args, rows=[]))
        self.assertEqual(result["final_status"], "accepted")

    def test_strict_query_shape(self):
        repo = StrictRepo(*self.args, rows=[])
        self._validate(repo)
        model, method, args, kwargs = repo.calls[0]
        self.assertEqual((model, method), ("hr.employee", "search_read"))
        self.assertIn(["work_email", "ilike", "ahmed@example.com"], args[0])
        self.assertIn(["company_id", "in", [15]], args[0])
        self.assertEqual(kwargs["context"], {"active_test": False})

    def test_legacy_repository_without_execute_kw_still_works(self):
        repo = FakeRepository(*self.args, [])
        self.assertEqual(self._validate(repo)["final_status"], "accepted")


def _save(wb, name):
    path = os.path.join(tempfile.mkdtemp(), name)
    wb.save(path)
    return path


def _titled_workbook(data_rows, extra_header=None):
    """Title row 1, headers row 2 (the modular template layout), data from row 3."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Employees"
    ws.append(["قالب بيانات الموظفين"])
    ws.append(HEADERS + ([extra_header] if extra_header is not None else []))
    for row in data_rows:
        ws.append(row)
    return wb


def _row(name, email="", mobile="0500000001"):
    return [name, email, "", mobile, "مسؤول", COMPANY, "المالية", "محاسب"]


class ParserFixesTests(unittest.TestCase):
    def test_real_employee_named_abdullah_in_first_row_is_not_skipped(self):
        wb = _titled_workbook([_row("عبدالله العتيبي"), _row("سارة الحربي", mobile="0500000002")])
        report = parse_xlsx(_save(wb, "abdullah.xlsx"))
        self.assertEqual(report["row_count"], 2)
        self.assertEqual(report["rows"][0]["excel_row_number"], 3)
        self.assertNotIn("template_example_row_skipped:3", report["warnings"])

    def test_template_example_row_is_skipped_and_reported(self):
        example = _row(TEMPLATE_EXAMPLE_NAME, email="a.ghamdi@alnokhba.sa")
        example[2] = TEMPLATE_EXAMPLE_ID
        wb = _titled_workbook([example, _row("سارة الحربي", mobile="0500000002")])
        report = parse_xlsx(_save(wb, "example.xlsx"))
        self.assertEqual(report["row_count"], 1)
        self.assertEqual(report["rows"][0]["excel_row_number"], 4)
        self.assertIn("template_example_row_skipped:3", report["warnings"])

    def test_blank_header_cell_is_not_renamed_to_name(self):
        wb = _titled_workbook([_row("سارة الحربي") + ["ملاحظة"]], extra_header=None)
        wb.active.cell(row=2, column=9, value=None)  # blank header cell inside the table range
        report = parse_xlsx(_save(wb, "blank_header.xlsx"))
        self.assertEqual(report["row_count"], 1)
        self.assertEqual(report["rows"][0]["fields"]["name"]["value"], "سارة الحربي")


if __name__ == "__main__":
    unittest.main()
