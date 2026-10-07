import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import cleanup_test_employees


class FakeRepository:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def _execute_kw(self, model, method, args, kwargs):
        self.calls.append((model, method, args, kwargs))
        return list(self.rows)


class FakeCleanupGateway:
    def __init__(self, repository=None):
        self.deleted_ids = []
        self.repository = repository

    def delete_employee_for_test_cleanup(self, employee_id):
        self.deleted_ids.append(employee_id)
        if self.repository is not None:
            self.repository.rows = []
        return True


class CleanupScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.results_path = self.tmpdir / "writer_results.jsonl"
        records = [
            {
                "record_type": "header",
                "run_id": "run123",
            },
            {
                "record_type": "row",
                "status": "created",
                "odoo_employee_id": 127,
                "attempted_work_email": "created@example.com",
            },
            {
                "record_type": "row",
                "status": "failed",
                "odoo_employee_id": 128,
                "attempted_work_email": "failed@example.com",
            },
        ]
        self.results_path.write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )

    def test_loader_uses_only_created_rows(self):
        records = cleanup_test_employees.load_created_records(self.results_path)

        self.assertEqual(list(records), [127])
        self.assertEqual(records[127]["attempted_work_email"], "created@example.com")

    def test_loader_rejects_results_without_created_rows(self):
        path = self.tmpdir / "empty_results.jsonl"
        path.write_text(
            json.dumps({"record_type": "row", "status": "failed"}) + "\n",
            encoding="utf-8",
        )

        with self.assertRaises(cleanup_test_employees.CleanupInputError):
            cleanup_test_employees.load_created_records(path)

    def test_dry_run_reads_live_email_without_deleting(self):
        repository = FakeRepository([{"id": 127, "work_email": "created@example.com"}])
        gateway = FakeCleanupGateway()
        output = StringIO()

        with redirect_stdout(output):
            code = cleanup_test_employees.process_cleanup(
                {127: {"attempted_work_email": "created@example.com"}},
                repository,
                gateway=gateway,
                confirm=False,
            )

        self.assertEqual(code, 0)
        self.assertEqual(gateway.deleted_ids, [])
        self.assertIn("would_delete", output.getvalue())

    def test_confirm_deletes_only_after_matching_live_email(self):
        repository = FakeRepository([{"id": 127, "work_email": "created@example.com"}])
        gateway = FakeCleanupGateway(repository)

        code = cleanup_test_employees.process_cleanup(
            {127: {"attempted_work_email": "created@example.com"}},
            repository,
            gateway=gateway,
            confirm=True,
        )

        self.assertEqual(code, 0)
        self.assertEqual(gateway.deleted_ids, [127])
        self.assertEqual(len(repository.calls), 2)

    def test_email_mismatch_rejects_delete(self):
        repository = FakeRepository([{"id": 127, "work_email": "different@example.com"}])
        gateway = FakeCleanupGateway()

        code = cleanup_test_employees.process_cleanup(
            {127: {"attempted_work_email": "created@example.com"}},
            repository,
            gateway=gateway,
            confirm=True,
        )

        self.assertEqual(code, 1)
        self.assertEqual(gateway.deleted_ids, [])
        self.assertEqual(len(repository.calls), 1)

    def test_missing_live_employee_rejects_delete(self):
        repository = FakeRepository([])
        gateway = FakeCleanupGateway()

        code = cleanup_test_employees.process_cleanup(
            {127: {"attempted_work_email": "created@example.com"}},
            repository,
            gateway=gateway,
            confirm=True,
        )

        self.assertEqual(code, 1)
        self.assertEqual(gateway.deleted_ids, [])

    def test_cli_requires_explicit_dry_run_or_confirm(self):
        with self.assertRaises(SystemExit) as context:
            cleanup_test_employees.main(["--results", str(self.results_path)])

        self.assertEqual(context.exception.code, 2)

    def test_cli_does_not_accept_free_employee_ids(self):
        with self.assertRaises(SystemExit) as context:
            cleanup_test_employees.main([
                "--results", str(self.results_path),
                "--dry-run",
                "--employee-ids", "127",
            ])

        self.assertEqual(context.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
