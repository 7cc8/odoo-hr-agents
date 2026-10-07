"""Tests for generate_employee_template.py (fully mocked, no network, no real files)."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import generate_employee_template as gen

# ---------------------------------------------------------------------------
# Shared test fixture snapshot
# ---------------------------------------------------------------------------

SNAPSHOT = {
    "companies": [
        {"id": 15, "name": "شركة النخبة الذكية للتقنية", "active": True},
        {"id": 17, "name": "شركة العقار الموحدة", "active": True},
        {"id": 1, "name": "My Company", "active": False},
    ],
    "departments": [
        {"id": 10, "name": "تقنية المعلومات",
         "complete_name": "شركة النخبة الذكية للتقنية / تقنية المعلومات",
         "company_id": [15, "شركة النخبة الذكية للتقنية"], "active": True},
        {"id": 11, "name": "الموارد البشرية",
         "complete_name": "شركة النخبة الذكية للتقنية / الموارد البشرية",
         "company_id": [15, "شركة النخبة الذكية للتقنية"], "active": True},
        {"id": 20, "name": "الإدارة",
         "complete_name": "شركة العقار الموحدة / الإدارة",
         "company_id": [17, "شركة العقار الموحدة"], "active": False},
    ],
    "jobs": [
        {"id": 5, "name": "مطور برمجيات",
         "company_id": [15, "شركة النخبة الذكية للتقنية"], "active": True},
        {"id": 6, "name": "محاسب",
         "company_id": [15, "شركة النخبة الذكية للتقنية"], "active": True},
    ],
}


# ---------------------------------------------------------------------------
# Helper: generate template to an in-memory bytes buffer
# ---------------------------------------------------------------------------

def _generate_to_bytes(snapshot=None, tmp_path=None) -> bytes:
    """Generate a template and return its raw bytes."""
    import openpyxl
    snapshot = snapshot or SNAPSHOT

    # Patch Path.mkdir and open so we never touch the real filesystem
    dest = tmp_path / "employee_import_template_20260101.xlsx" if tmp_path else None

    actual_dest = gen.generate_template(snapshot, output_dir=str(tmp_path or "/tmp/test"))
    return actual_dest.read_bytes()


# ---------------------------------------------------------------------------
# Tests: sheet structure
# ---------------------------------------------------------------------------

class TestSheetNames:
    def test_three_sheets_in_correct_order(self, tmp_path):
        import openpyxl
        dest = gen.generate_template(SNAPSHOT, output_dir=str(tmp_path))
        wb = openpyxl.load_workbook(dest)
        assert wb.sheetnames == ["Employees", "Reference", "Instructions"]

    def test_active_sheet_is_employees(self, tmp_path):
        import openpyxl
        dest = gen.generate_template(SNAPSHOT, output_dir=str(tmp_path))
        wb = openpyxl.load_workbook(dest)
        assert wb.active.title == "Employees"


class TestEmployeesSheet:
    def _load_ws(self, tmp_path):
        import openpyxl
        dest = gen.generate_template(SNAPSHOT, output_dir=str(tmp_path))
        return openpyxl.load_workbook(dest)["Employees"]

    def test_header_row_contains_all_nine_columns(self, tmp_path):
        ws = self._load_ws(tmp_path)
        headers = [ws.cell(row=1, column=c).value for c in range(1, 10)]
        expected_keys = [col["label"] for col in gen.EMPLOYEE_COLUMNS]
        for key in expected_keys:
            assert any(key in (h or "") for h in headers), f"Missing header: {key}"

    def test_required_columns_marked_with_asterisk(self, tmp_path):
        ws = self._load_ws(tmp_path)
        required_keys = {col["label"] for col in gen.EMPLOYEE_COLUMNS if col["required"]}
        for col_idx in range(1, len(gen.EMPLOYEE_COLUMNS) + 1):
            cell_val = ws.cell(row=1, column=col_idx).value or ""
            label = cell_val.rstrip(" *")
            if label in required_keys:
                assert "*" in cell_val, f"Required column '{label}' missing asterisk in header"

    def test_example_row_exists_at_row_2(self, tmp_path):
        ws = self._load_ws(tmp_path)
        # name column (col 1) should have the example name
        assert ws.cell(row=2, column=1).value == "أحمد محمد العتيبي"

    def test_example_row_company_uses_first_active_company(self, tmp_path):
        ws = self._load_ws(tmp_path)
        # company column index
        company_col = next(
            i + 1 for i, c in enumerate(gen.EMPLOYEE_COLUMNS) if c["key"] == "company"
        )
        assert ws.cell(row=2, column=company_col).value == "شركة النخبة الذكية للتقنية"

    def test_freeze_panes_at_row_3(self, tmp_path):
        ws = self._load_ws(tmp_path)
        assert ws.freeze_panes == "A3"


class TestReferenceSheet:
    def _load_ws(self, tmp_path):
        import openpyxl
        dest = gen.generate_template(SNAPSHOT, output_dir=str(tmp_path))
        return openpyxl.load_workbook(dest, data_only=True)["Reference"]

    def test_generated_at_in_meta_row(self, tmp_path):
        ws = self._load_ws(tmp_path)
        # Row 1 col 1 = "reference_generated_at", col 2 = timestamp
        assert ws.cell(row=1, column=1).value == "reference_generated_at"
        ts = ws.cell(row=1, column=2).value or ""
        assert "UTC" in ts

    def test_all_company_names_present(self, tmp_path):
        ws = self._load_ws(tmp_path)
        all_values = {ws.cell(row=r, column=c).value
                      for r in range(1, ws.max_row + 1)
                      for c in range(1, ws.max_column + 1)}
        for company in SNAPSHOT["companies"]:
            assert company["name"] in all_values, f"Company name missing: {company['name']}"

    def test_all_department_complete_names_present(self, tmp_path):
        ws = self._load_ws(tmp_path)
        all_values = {ws.cell(row=r, column=c).value
                      for r in range(1, ws.max_row + 1)
                      for c in range(1, ws.max_column + 1)}
        for dept in SNAPSHOT["departments"]:
            assert dept["complete_name"] in all_values, \
                f"Department complete_name missing: {dept['complete_name']}"

    def test_all_job_names_present(self, tmp_path):
        ws = self._load_ws(tmp_path)
        all_values = {ws.cell(row=r, column=c).value
                      for r in range(1, ws.max_row + 1)
                      for c in range(1, ws.max_column + 1)}
        for job in SNAPSHOT["jobs"]:
            assert job["name"] in all_values, f"Job name missing: {job['name']}"

    def test_archived_department_marked_correctly(self, tmp_path):
        ws = self._load_ws(tmp_path)
        all_values = {ws.cell(row=r, column=c).value
                      for r in range(1, ws.max_row + 1)
                      for c in range(1, ws.max_column + 1)}
        # The archived dept "الإدارة" should still appear (active_test=False in snapshot)
        assert "شركة العقار الموحدة / الإدارة" in all_values
        assert "مؤرشف" in all_values


class TestInstructionsSheet:
    def _load_ws(self, tmp_path):
        import openpyxl
        dest = gen.generate_template(SNAPSHOT, output_dir=str(tmp_path))
        return openpyxl.load_workbook(dest)["Instructions"]

    def test_sheet_exists_and_is_rtl(self, tmp_path):
        ws = self._load_ws(tmp_path)
        assert ws.sheet_view.rightToLeft is True

    def test_contains_all_four_statuses(self, tmp_path):
        ws = self._load_ws(tmp_path)
        all_text = " ".join(
            str(ws.cell(row=r, column=c).value or "")
            for r in range(1, ws.max_row + 1)
            for c in range(1, 3)
        )
        for status in ["accepted", "needs_review", "rejected", "outcome_uncertain"]:
            assert status in all_text, f"Status '{status}' missing from Instructions"

    def test_contains_column_explanations(self, tmp_path):
        ws = self._load_ws(tmp_path)
        all_text = " ".join(
            str(ws.cell(row=r, column=c).value or "")
            for r in range(1, ws.max_row + 1)
            for c in range(1, 3)
        )
        for col_key in ["name", "work_email", "company", "department", "hiring_date"]:
            assert col_key in all_text, f"Column '{col_key}' missing from Instructions"


# ---------------------------------------------------------------------------
# Tests: output file naming and location
# ---------------------------------------------------------------------------

class TestOutputFile:
    def test_file_name_contains_today_date(self, tmp_path):
        from datetime import date
        today = date.today().strftime("%Y%m%d")
        dest = gen.generate_template(SNAPSHOT, output_dir=str(tmp_path))
        assert today in dest.name

    def test_file_extension_is_xlsx(self, tmp_path):
        dest = gen.generate_template(SNAPSHOT, output_dir=str(tmp_path))
        assert dest.suffix == ".xlsx"

    def test_output_dir_created_if_missing(self, tmp_path):
        new_dir = tmp_path / "subdir" / "nested"
        assert not new_dir.exists()
        gen.generate_template(SNAPSHOT, output_dir=str(new_dir))
        assert new_dir.exists()


# ---------------------------------------------------------------------------
# Tests: helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_first_active_company(self):
        assert gen._first_active_company_name(SNAPSHOT) == "شركة النخبة الذكية للتقنية"

    def test_first_active_company_skips_inactive(self):
        snap = {"companies": [{"id": 1, "name": "أرشيف", "active": False},
                               {"id": 2, "name": "نشط", "active": True}]}
        assert gen._first_active_company_name(snap) == "نشط"

    def test_first_active_dept(self):
        result = gen._first_active_dept_name(SNAPSHOT)
        assert "تقنية المعلومات" in result

    def test_first_active_job(self):
        assert gen._first_active_job_name(SNAPSHOT) == "مطور برمجيات"

    def test_id_of_many2one_list(self):
        assert gen._id_of([15, "شركة النخبة"]) == 15

    def test_id_of_none(self):
        assert gen._id_of(None) is None

    def test_name_of_many2one_list(self):
        assert gen._name_of([15, "شركة النخبة"]) == "شركة النخبة"

    def test_name_of_none(self):
        assert gen._name_of(None) == ""


# ---------------------------------------------------------------------------
# Tests: main() CLI (fully mocked)
# ---------------------------------------------------------------------------

class TestMain:
    def test_main_success(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ODOO_URL", "https://test.odoo.com/")
        monkeypatch.setenv("ODOO_DB", "test-db")
        monkeypatch.setenv("ODOO_USERNAME", "testuser")
        monkeypatch.setenv("ODOO_API_KEY", "testkey123")

        mock_repo = MagicMock()
        mock_repo.get_live_reference_snapshot.return_value = SNAPSHOT

        # OdooReadonlyRepository is imported inside main() from odoo_readonly_repository;
        # patch it in the source module so the local import resolves to the mock.
        with patch("odoo_readonly_repository.OdooReadonlyRepository", return_value=mock_repo):
            rc = gen.main(["--output-dir", str(tmp_path)])
        assert rc == 0

    def test_main_missing_env_returns_2(self, tmp_path, monkeypatch):
        # Remove all required env vars so OdooReadonlyRepository raises on construction.
        for key in ["ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_API_KEY",
                    "ODOO_USER"]:
            monkeypatch.delenv(key, raising=False)

        rc = gen.main(["--output-dir", str(tmp_path)])
        assert rc == 2

    def test_main_snapshot_failure_returns_1(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ODOO_URL", "https://test.odoo.com/")
        monkeypatch.setenv("ODOO_DB", "test-db")
        monkeypatch.setenv("ODOO_USERNAME", "testuser")
        monkeypatch.setenv("ODOO_API_KEY", "testkey123")

        mock_repo = MagicMock()
        mock_repo.get_live_reference_snapshot.side_effect = ConnectionError("timeout")

        with patch("odoo_readonly_repository.OdooReadonlyRepository", return_value=mock_repo):
            rc = gen.main(["--output-dir", str(tmp_path)])
        assert rc == 1
