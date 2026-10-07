import ast
import csv
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from dry_run_report import (
    build_report_dict,
    write_csv,
    write_json,
    write_xlsx,
    csv_formula_guard,
    REPORT_HEADERS,
)


class DryRunReportTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

        self.parsed_report = {
            "run_id": "run-123",
            "source_hash": "src-456",
            "rows": [
                {"excel_row_number": 2, "parser_flags": ["numeric_cell_in_text_column"]},
                {"excel_row_number": 3, "parser_flags": []},
                {"excel_row_number": 4, "parser_flags": []},
                {"excel_row_number": 5, "parser_flags": []},
                {"excel_row_number": 6, "parser_flags": []},
            ],
        }

        self.repo_info = {
            "odoo_url": "https://odooprosys-hr19.odoo.com/",
            "odoo_db": "odooprosys-hr19-main-37916265",
            "uid": 9,
            "server_version": {"server_version": "19.0"},
        }

        self.snapshot = {
            "companies": [{"id": 1}, {"id": 2}, {"id": 3}],
            "departments": [{"id": 10}] * 6,
            "jobs": [{"id": 20}] * 5,
        }

        self.validated_rows = [
            {
                "excel_row_number": 2,
                "final_status": "accepted",
                "failure_code": None,
                "reasons": ["Row passed validator checks."],
                "resolved_references": {
                    "company": {"id": 15},
                    "department": {"id": 8},
                    "job": {"id": 22},
                },
                "run_id": "run-123",
                "row_hash": "row-2",
                "source_hash": "src-456",
            },
            {
                "excel_row_number": 3,
                "final_status": "needs_review",
                "failure_code": "possible_duplicate",
                "reasons": ["work_email is empty; name + mobile_phone must be reviewed manually."],
                "resolved_references": {
                    "company": {"id": 15},
                },
                "run_id": "run-123",
                "row_hash": "row-3",
                "source_hash": "src-456",
            },
            {
                "excel_row_number": 4,
                "final_status": "rejected",
                "failure_code": "reference_not_found",
                "reasons": ["Department not found for company: قسم غير موجود"],
                "resolved_references": {},
                "run_id": "run-123",
                "row_hash": "row-4",
                "source_hash": "src-456",
            },
            {
                "excel_row_number": 5,
                "final_status": "accepted",
                "failure_code": None,
                "reasons": ["Row passed validator checks."],
                "resolved_references": {
                    "company": {"id": 15},
                },
                "run_id": "run-123",
                "row_hash": "row-5",
                "source_hash": "src-456",
            },
            {
                "excel_row_number": 6,
                "final_status": "needs_review",
                "failure_code": "possible_duplicate",
                "reasons": ["Optional fields missing but report must still render."],
                "resolved_references": None,
                "run_id": "run-123",
                "row_hash": "row-6",
                "source_hash": "src-456",
            },
        ]

    def test_build_report_dict_header_and_summary(self):
        report = build_report_dict(self.parsed_report, self.validated_rows, self.repo_info, self.snapshot)

        self.assertEqual(report["header"]["odoo_url"], self.repo_info["odoo_url"])
        self.assertEqual(report["header"]["odoo_db"], self.repo_info["odoo_db"])
        self.assertEqual(report["header"]["uid"], 9)
        self.assertEqual(
            report["header"]["reference_counts"],
            {"companies": 3, "departments": 6, "jobs": 5},
        )
        self.assertEqual(report["header"]["run_id"], "run-123")
        self.assertEqual(report["header"]["source_hash"], "src-456")
        self.assertEqual(
            report["summary"]["status_counts"],
            {"accepted": 2, "needs_review": 2, "rejected": 1},
        )

    def test_row_contains_status_code_reasons_ids_hash_and_parser_warnings(self):
        report = build_report_dict(self.parsed_report, self.validated_rows, self.repo_info, self.snapshot)
        row = report["rows"][0]

        self.assertEqual(row["final_status"], "accepted")
        self.assertIsNone(row["failure_code"])
        self.assertEqual(row["resolved_ids"]["company_id"], 15)
        self.assertEqual(row["resolved_ids"]["department_id"], 8)
        self.assertEqual(row["resolved_ids"]["job_id"], 22)
        self.assertEqual(row["row_hash"], "row-2")
        self.assertIn("numeric_cell_in_text_column", row["parser_warnings"])

    def test_row_without_optional_values_still_renders(self):
        report = build_report_dict(self.parsed_report, self.validated_rows, self.repo_info, self.snapshot)
        row = next(r for r in report["rows"] if r["excel_row_number"] == 6)

        self.assertEqual(row["final_status"], "needs_review")
        self.assertIsNone(row["resolved_ids"]["company_id"])
        self.assertIsNone(row["resolved_ids"]["department_id"])
        self.assertIsNone(row["resolved_ids"]["job_id"])

    def test_row_with_empty_resolved_references(self):
        report = build_report_dict(self.parsed_report, self.validated_rows, self.repo_info, self.snapshot)
        row = next(r for r in report["rows"] if r["excel_row_number"] == 4)

        self.assertEqual(
            row["resolved_ids"],
            {
                "company_id": None,
                "department_id": None,
                "job_id": None,
                "employee_match_id": None,
            },
        )

    def test_write_csv_and_json(self):
        report = build_report_dict(self.parsed_report, self.validated_rows, self.repo_info, self.snapshot)

        csv_path = self.tmpdir / "dry_run_report.csv"
        json_path = self.tmpdir / "dry_run_report.json"

        write_csv(report, csv_path)
        write_json(report, json_path)

        self.assertTrue(csv_path.exists())
        self.assertTrue(json_path.exists())

        with csv_path.open("r", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["excel_row_number"], "2")

        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["header"]["run_id"], "run-123")

    def test_csv_formula_guard_function_plus_and_equals(self):
        self.assertEqual(csv_formula_guard("+966500000000"), "'+966500000000")
        self.assertEqual(csv_formula_guard("=SUM(A1:A2)"), "'=SUM(A1:A2)")
        self.assertEqual(csv_formula_guard("-100"), "'-100")
        self.assertEqual(csv_formula_guard("@mention"), "'@mention")
        self.assertEqual(csv_formula_guard("normal text"), "normal text")
        self.assertEqual(csv_formula_guard(""), "")

    def test_csv_output_has_leading_apostrophe_for_plus_value(self):
        report = build_report_dict(self.parsed_report, self.validated_rows, self.repo_info, self.snapshot)
        report["rows"][0]["reasons"] = ["+966500000000"]

        csv_path = self.tmpdir / "dry_run_report.csv"
        write_csv(report, csv_path)

        raw_text = csv_path.read_text(encoding="utf-8-sig")
        self.assertIn("'+966500000000", raw_text)

    def test_csv_output_has_leading_apostrophe_for_equals_value(self):
        report = build_report_dict(self.parsed_report, self.validated_rows, self.repo_info, self.snapshot)
        report["rows"][0]["reasons"] = ["=SUM(A1:A2)"]

        csv_path = self.tmpdir / "dry_run_report.csv"
        write_csv(report, csv_path)

        raw_text = csv_path.read_text(encoding="utf-8-sig")
        self.assertIn("'=SUM(A1:A2)", raw_text)

    def test_write_xlsx_plus_number_is_not_formula_and_has_no_apostrophe(self):
        report = build_report_dict(self.parsed_report, self.validated_rows, self.repo_info, self.snapshot)
        report["rows"][0]["reasons"] = ["+966500000000"]

        xlsx_path = self.tmpdir / "dry_run_report.xlsx"
        write_xlsx(report, xlsx_path)

        self.assertTrue(xlsx_path.exists())

        with ZipFile(xlsx_path, "r") as zf:
            sheet_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")

        self.assertIn("+966500000000", sheet_xml)
        self.assertNotIn("'+966500000000", sheet_xml)
        self.assertNotIn("<f>", sheet_xml)

    def test_write_xlsx_equals_value_is_not_formula_and_has_no_apostrophe(self):
        report = build_report_dict(self.parsed_report, self.validated_rows, self.repo_info, self.snapshot)
        report["rows"][0]["reasons"] = ["=SUM(A1:A2)"]

        xlsx_path = self.tmpdir / "dry_run_report.xlsx"
        write_xlsx(report, xlsx_path)

        with ZipFile(xlsx_path, "r") as zf:
            sheet_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")

        self.assertIn("=SUM(A1:A2)", sheet_xml)
        self.assertNotIn("'=SUM(A1:A2)", sheet_xml)
        self.assertNotIn("<f>", sheet_xml)
        self.assertIn('t="inlineStr"', sheet_xml)

    def test_report_headers_are_stable(self):
        self.assertEqual(
            REPORT_HEADERS,
            [
                "excel_row_number",
                "final_status",
                "failure_code",
                "reasons",
                "company_id",
                "department_id",
                "job_id",
                "employee_match_id",
                "row_hash",
                "run_id",
                "source_hash",
                "parser_warnings",
            ],
        )

    def test_no_write_calls_imported_or_used(self):
        source = Path("dry_run_report.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        forbidden_imports = []
        forbidden_calls = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "odoo_writer_repository":
                forbidden_imports.append(node.module)

            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in {"create", "write", "unlink"}:
                    forbidden_calls.append(func.attr)
                elif isinstance(func, ast.Name) and func.id in {"create", "write", "unlink"}:
                    forbidden_calls.append(func.id)

        self.assertEqual(forbidden_imports, [])
        self.assertEqual(forbidden_calls, [])


if __name__ == "__main__":
    unittest.main()