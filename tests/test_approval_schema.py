import json
import tempfile
import unittest
from pathlib import Path

from approval_schema import (
    new_approval_timestamps,
    Approval,
    ApprovalSchemaError,
    ApprovalReportMismatchError,
    validate_approval_against_report,
)


class ApprovalSchemaTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.valid_data = {
            "run_id": "ba465f8956d83e02",
            "source_hash": "ba465f8956d83e02ccdcaa1e5f8b3fc93ac0744af605e3aba1d68a5208b42e9d",
            "source_file_name": "test_employees_10.xlsx",
            "approved_by": "khaled",
            **new_approval_timestamps(),
            "approved_row_hashes": ["h1", "h2"],
        }
        self.report = {
            "header": {
                "run_id": "ba465f8956d83e02",
                "source_hash": "ba465f8956d83e02ccdcaa1e5f8b3fc93ac0744af605e3aba1d68a5208b42e9d",
            },
            "rows": [
                {"row_hash": "h1", "final_status": "accepted"},
                {"row_hash": "h2", "final_status": "accepted"},
                {"row_hash": "h3", "final_status": "rejected"},
                {"row_hash": "h4", "final_status": "needs_review"},
            ],
        }

    def test_valid_approval_parses(self):
        approval = Approval.from_dict(self.valid_data)
        self.assertEqual(approval.approved_by, "khaled")
        self.assertEqual(approval.source_file_name, "test_employees_10.xlsx")
        self.assertEqual(approval.approved_row_hashes, ["h1", "h2"])

    def test_missing_field_raises_schema_error(self):
        data = dict(self.valid_data)
        del data["approved_by"]
        with self.assertRaises(ApprovalSchemaError):
            Approval.from_dict(data)

    def test_invalid_approved_at_raises_schema_error(self):
        data = dict(self.valid_data)
        data["approved_at"] = "not-a-date"
        with self.assertRaises(ApprovalSchemaError):
            Approval.from_dict(data)

    def test_empty_approved_by_raises_schema_error(self):
        data = dict(self.valid_data)
        data["approved_by"] = "   "
        with self.assertRaises(ApprovalSchemaError):
            Approval.from_dict(data)

    def test_empty_run_id_raises_schema_error(self):
        data = dict(self.valid_data)
        data["run_id"] = "   "
        with self.assertRaises(ApprovalSchemaError):
            Approval.from_dict(data)

    def test_empty_source_hash_raises_schema_error(self):
        data = dict(self.valid_data)
        data["source_hash"] = "   "
        with self.assertRaises(ApprovalSchemaError):
            Approval.from_dict(data)

    def test_approved_row_hashes_not_list_raises_schema_error(self):
        data = dict(self.valid_data)
        data["approved_row_hashes"] = "h1"
        with self.assertRaises(ApprovalSchemaError):
            Approval.from_dict(data)

    def test_load_from_file(self):
        file_path = self.tmpdir / "approval.json"
        file_path.write_text(json.dumps(self.valid_data), encoding="utf-8")
        approval = Approval.load(file_path)
        self.assertEqual(approval.run_id, self.valid_data["run_id"])

    def test_matching_approval_passes_validation(self):
        approval = Approval.from_dict(self.valid_data)
        validate_approval_against_report(approval, self.report)

    def test_mismatched_run_id_rejected(self):
        data = dict(self.valid_data)
        data["run_id"] = "different_run_id"
        approval = Approval.from_dict(data)
        with self.assertRaises(ApprovalReportMismatchError):
            validate_approval_against_report(approval, self.report)

    def test_mismatched_source_hash_rejected(self):
        data = dict(self.valid_data)
        data["source_hash"] = "a" * 64
        approval = Approval.from_dict(data)
        with self.assertRaises(ApprovalReportMismatchError):
            validate_approval_against_report(approval, self.report)

    def test_unknown_row_hash_rejected_even_when_file_and_run_id_match(self):
        data = dict(self.valid_data)
        data["approved_row_hashes"] = ["h1", "h_not_in_report"]
        approval = Approval.from_dict(data)
        with self.assertRaises(ApprovalReportMismatchError) as ctx:
            validate_approval_against_report(approval, self.report)
        self.assertIn("not present", str(ctx.exception))
        self.assertNotIn("not accepted", str(ctx.exception))

    def test_approval_referencing_rejected_row_is_rejected(self):
        data = dict(self.valid_data)
        data["approved_row_hashes"] = ["h3"]
        approval = Approval.from_dict(data)
        with self.assertRaises(ApprovalReportMismatchError) as ctx:
            validate_approval_against_report(approval, self.report)
        self.assertIn("not accepted", str(ctx.exception))
        self.assertNotIn("not present", str(ctx.exception))

    def test_approval_referencing_needs_review_row_is_rejected(self):
        data = dict(self.valid_data)
        data["approved_row_hashes"] = ["h4"]
        approval = Approval.from_dict(data)
        with self.assertRaises(ApprovalReportMismatchError) as ctx:
            validate_approval_against_report(approval, self.report)
        self.assertIn("not accepted", str(ctx.exception))
        self.assertNotIn("not present", str(ctx.exception))

    def test_approval_with_mixed_accepted_and_rejected_hashes_is_rejected(self):
        data = dict(self.valid_data)
        data["approved_row_hashes"] = ["h1", "h3"]
        approval = Approval.from_dict(data)
        with self.assertRaises(ApprovalReportMismatchError) as ctx:
            validate_approval_against_report(approval, self.report)
        self.assertIn("not accepted", str(ctx.exception))
        self.assertNotIn("not present", str(ctx.exception))

    def test_mixed_unknown_and_not_accepted_hashes_is_rejected_with_distinct_message(self):
        data = dict(self.valid_data)
        data["approved_row_hashes"] = ["h1", "h3", "h_not_in_report"]
        approval = Approval.from_dict(data)
        with self.assertRaises(ApprovalReportMismatchError) as ctx:
            validate_approval_against_report(approval, self.report)
        self.assertIn("mixed invalid selection", str(ctx.exception))
        self.assertIn("not present", str(ctx.exception))
        self.assertIn("not accepted", str(ctx.exception))

    def test_partial_approval_of_subset_of_rows_is_allowed(self):
        data = dict(self.valid_data)
        data["approved_row_hashes"] = ["h1"]
        approval = Approval.from_dict(data)
        validate_approval_against_report(approval, self.report)

    def test_no_write_calls_imported_or_used(self):
        source = Path("approval_schema.py").read_text(encoding="utf-8")

        forbidden_tokens = [
            ".create(",
            ".write(",
            ".unlink(",
            '"create"',
            '"write"',
            '"unlink"',
            "'create'",
            "'write'",
            "'unlink'",
        ]

        for token in forbidden_tokens:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()