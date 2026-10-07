import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import make_approval


class MakeApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.report_path = self.tmpdir / "dry_run_report.json"
        self.input_path = self.tmpdir / "employees.xlsx"
        self.input_path.write_bytes(b"placeholder")
        self.report = {
            "header": {
                "run_id": "run123",
                "source_hash": "source123",
            },
            "rows": [
                {
                    "excel_row_number": 2,
                    "final_status": "accepted",
                    "failure_code": None,
                    "row_hash": "hash2",
                },
                {
                    "excel_row_number": 3,
                    "final_status": "needs_review",
                    "failure_code": "duplicate_existing_employee",
                    "row_hash": "hash3",
                },
            ],
        }
        self.report_path.write_text(json.dumps(self.report), encoding="utf-8")

    def run_main(self, args):
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = make_approval.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_list_prints_report_rows_without_writing_approval(self):
        code, stdout, stderr = self.run_main(["--report", str(self.report_path), "--list"])

        self.assertEqual(code, 0)
        self.assertIn("excel_row", stdout)
        self.assertIn("hash2", stdout)
        self.assertIn("needs_review", stdout)
        self.assertEqual(stderr, "")
        self.assertFalse((self.tmpdir / "approval.json").exists())

    def test_accepted_rows_create_approval_from_row_numbers(self):
        approval_path = self.tmpdir / "approval.json"
        code, stdout, stderr = self.run_main([
            "--report", str(self.report_path),
            "--input", str(self.input_path),
            "--approved-by", "hr-reviewer",
            "--rows", "2",
            "--out", str(approval_path),
        ])

        self.assertEqual(code, 0)
        self.assertIn("Wrote", stdout)
        self.assertEqual(stderr, "")
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        self.assertEqual(approval["run_id"], "run123")
        self.assertEqual(approval["source_hash"], "source123")
        self.assertEqual(approval["source_file_name"], "employees.xlsx")
        self.assertEqual(approval["approved_by"], "hr-reviewer")
        self.assertEqual(approval["approved_row_hashes"], ["hash2"])

    def test_non_accepted_row_is_rejected(self):
        code, stdout, stderr = self.run_main([
            "--report", str(self.report_path),
            "--input", str(self.input_path),
            "--approved-by", "hr-reviewer",
            "--rows", "3",
        ])

        self.assertEqual(code, 2)
        self.assertIn("not_accepted=[3]", stderr)
        self.assertEqual(stdout, "")

    def test_unknown_and_duplicate_rows_are_rejected(self):
        code, stdout, stderr = self.run_main([
            "--report", str(self.report_path),
            "--input", str(self.input_path),
            "--approved-by", "hr-reviewer",
            "--rows", "2", "2", "99",
        ])

        self.assertEqual(code, 2)
        self.assertIn("unknown=[99]", stderr)
        self.assertIn("duplicates=True", stderr)
        self.assertEqual(stdout, "")

    def test_existing_output_is_never_overwritten(self):
        approval_path = self.tmpdir / "approval.json"
        approval_path.write_text("original", encoding="utf-8")

        code, stdout, stderr = self.run_main([
            "--report", str(self.report_path),
            "--input", str(self.input_path),
            "--approved-by", "hr-reviewer",
            "--rows", "2",
            "--out", str(approval_path),
        ])

        self.assertEqual(code, 2)
        self.assertIn("already exists", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(approval_path.read_text(encoding="utf-8"), "original")


if __name__ == "__main__":
    unittest.main()
