import json
import tempfile
import unittest
from pathlib import Path

import writer
from odoo_write_gateway import EnvironmentGuardError

RUN_ID = "run123"
SOURCE_HASH = "b" * 64
IDS = {"company_id": 15, "department_id": 8, "job_id": 22}


def h(ch):
    return ch * 64


def parsed_row(number, row_hash, email="a@example.test", name="Ahmed"):
    def f(v):
        return {"value": v}

    return {
        "excel_row_number": number,
        "row_hash": row_hash,
        "fields": {
            "name": f(name),
            "work_email": f(email),
            "work_phone": f(""),
            "mobile_phone": f(""),
            "job_title": f("Engineer"),
        },
    }


class FakeRepository:
    def __init__(self, fail_snapshot_count=0, exc=None):
        self.fail_snapshot_count = fail_snapshot_count
        self.snapshot_calls = 0
        self.exc = exc or RuntimeError("snapshot network dropped")

    def get_session_info(self):
        return {"odoo_url": "https://example.test", "odoo_db": "test_db"}

    def get_live_reference_snapshot(self):
        self.snapshot_calls += 1
        if self.snapshot_calls <= self.fail_snapshot_count:
            raise self.exc
        return {"companies": [], "departments": [], "jobs": []}


class FakeGateway:
    def __init__(self, fail_on_call=None, exc=None, fail_read_count=0, read_exc=None):
        self.create_calls = []
        self.create_contexts = []
        self.read_calls = []
        self.read_contexts = []
        self.fail_on_call = fail_on_call
        self.exc = exc or RuntimeError("network dropped")
        self.fail_read_count = fail_read_count
        self.read_exc = read_exc or RuntimeError("read network dropped")
        self.read_attempts = 0

    def get_session_info(self):
        return {
            "odoo_url": "https://example.test",
            "odoo_db": "test_db",
            "uid": 1,
            "server_version": "19.0-test",
        }

    def create_employee(self, values, context=None):
        self.create_calls.append(values)
        self.create_contexts = getattr(self, "create_contexts", [])
        self.create_contexts.append(context)
        if self.fail_on_call == len(self.create_calls):
            raise self.exc
        return 900 + len(self.create_calls)

    def read_employee(self, employee_id, fields, context=None):
        self.read_attempts += 1
        if self.read_attempts <= self.fail_read_count:
            raise self.read_exc
        self.read_calls = getattr(self, "read_calls", [])
        self.read_contexts = getattr(self, "read_contexts", [])
        self.read_calls.append((employee_id, fields))
        self.read_contexts.append(context)
        values = self.create_calls[employee_id - 901]
        return {
            "name": values["name"],
            "work_email": values["work_email"],
            "company_id": [values["company_id"], "Company"],
            "department_id": [values["department_id"], "Dept"],
            "job_id": [values["job_id"], "Job"],
            "hiring_date": values.get("hiring_date"),
        }


class FakeValidator:
    def __init__(self, status="accepted", ids=None):
        self.status = status
        self.ids = dict(IDS if ids is None else ids)

    def validate_single_row(self, row, companies, departments, jobs):
        return {
            "final_status": self.status,
            "failure_code": None,
            "reasons": [],
            "resolved_references": {
                "company": {"id": self.ids["company_id"]},
                "department": {"id": self.ids["department_id"]},
                "job": {"id": self.ids["job_id"]},
            },
        }


class WriterTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.output_dir = self.tmpdir / "writer-output"
        self.repository = FakeRepository()
        self.gateway = FakeGateway()
        self.input_path = self.tmpdir / "test_employees_10.xlsx"
        self.input_path.write_bytes(b"placeholder")
        self.report_path = self.tmpdir / "dry_run_report.json"
        self.approval_path = self.tmpdir / "approval.json"

    def prepare(self, report_rows, approved_hashes):
        self.report_path.write_text(
            json.dumps(
                {
                    "header": {"run_id": RUN_ID, "source_hash": SOURCE_HASH},
                    "rows": [
                        {
                            "excel_row_number": number,
                            "row_hash": row_hash,
                            "final_status": "accepted",
                            "resolved_ids": dict(IDS),
                        }
                        for number, row_hash in report_rows
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.approval_path.write_text(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "source_hash": SOURCE_HASH,
                    "source_file_name": self.input_path.name,
                    "approved_by": "test-user",
                    "approved_at": "2026-09-30T00:00:00Z",
                    "approved_row_hashes": list(approved_hashes),
                }
            ),
            encoding="utf-8",
        )

    def run_writer(
        self,
        parsed_rows,
        validator=None,
        parse_fn=None,
        company_id=15,
        read_retries=3,
        sleep_fn=None,
    ):
        validator = validator or FakeValidator()
        if parse_fn is None:
            parse_fn = lambda _path: {
                "run_id": RUN_ID,
                "source_hash": SOURCE_HASH,
                "rows": parsed_rows,
            }
        return writer.run_writer(
            input_xlsx_path=self.input_path,
            report_path=self.report_path,
            approval_path=self.approval_path,
            output_dir=self.output_dir,
            repository=self.repository,
            gateway=self.gateway,
            company_id=company_id,
            parse_fn=parse_fn,
            validator_factory=lambda _repository: validator,
            os_user="tester",
            read_retries=read_retries,
            sleep_fn=sleep_fn or (lambda _s: None),
        )

    def read_log(self, result):
        lines = Path(result["results_path"]).read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines]

    def test_abort_when_parse_fn_raises_source_unreadable(self):
        self.prepare([(2, h("a"))], [h("a")])

        def bad_parse(_path):
            raise RuntimeError("simulated unreadable source")

        with self.assertRaises(writer.WriterAbort) as ctx:
            self.run_writer([], parse_fn=bad_parse)

        self.assertEqual(ctx.exception.code, writer.ABORT_SOURCE_UNREADABLE)
        self.assertEqual(ctx.exception.code, "source_unreadable")
        self.assertEqual(self.gateway.create_calls, [])
        self.assertFalse(self.output_dir.exists())

    def test_happy_path_creates_verifies_and_logs(self):
        self.prepare([(2, h("a"))], [h("a")])
        result = self.run_writer([parsed_row(2, h("a"))])

        self.assertEqual(len(self.gateway.create_calls), 1)
        self.assertEqual(
            self.gateway.create_calls[0],
            {
                "name": "Ahmed",
                "work_email": "a@example.test",
                "company_id": 15,
                "job_title": "Engineer",
                "department_id": 8,
                "job_id": 22,
            },
        )
        row = result["rows"][0]
        self.assertEqual(row["status"], writer.STATUS_CREATED)
        self.assertEqual(row["odoo_employee_id"], 901)
        self.assertIs(row["verified"], True)
        self.assertEqual(result["footer"]["status_counts"], {"created": 1})

        types = [r["record_type"] for r in self.read_log(result)]
        self.assertEqual(types, ["header", "attempt", "row", "footer"])

    def test_uncertain_outcome_stops_run_and_marks_rest_not_attempted(self):
        self.gateway = FakeGateway(fail_on_call=1)
        self.prepare([(2, h("a")), (3, h("b"))], [h("a"), h("b")])
        result = self.run_writer(
            [parsed_row(2, h("a"), "a@example.test"), parsed_row(3, h("b"), "b@example.test", "Sara")]
        )

        self.assertEqual(len(self.gateway.create_calls), 1)
        first, second = result["rows"]
        self.assertEqual(first["status"], writer.STATUS_UNCERTAIN)
        self.assertEqual(first["failure_code"], writer.ROW_OUTCOME_UNCERTAIN)
        self.assertIsNone(first["odoo_employee_id"])
        self.assertEqual(second["status"], writer.STATUS_NOT_ATTEMPTED)
        self.assertEqual(second["failure_code"], writer.ROW_STOPPED)

    def test_environment_guard_block_stops_run_as_failed(self):
        self.gateway = FakeGateway(fail_on_call=1, exc=EnvironmentGuardError("blocked"))
        self.prepare([(2, h("a")), (3, h("b"))], [h("a"), h("b")])
        result = self.run_writer(
            [parsed_row(2, h("a")), parsed_row(3, h("b"), "b@example.test", "Sara")]
        )
        self.assertEqual(result["rows"][0]["failure_code"], writer.ROW_GUARD_BLOCKED)
        self.assertEqual(result["rows"][1]["status"], writer.STATUS_NOT_ATTEMPTED)
        self.assertEqual(len(self.gateway.create_calls), 1)

    def test_reference_changed_since_dry_run_blocks_create(self):
        self.prepare([(2, h("a"))], [h("a")])
        moved = dict(IDS, department_id=9)
        result = self.run_writer([parsed_row(2, h("a"))], validator=FakeValidator(ids=moved))

        row = result["rows"][0]
        self.assertEqual(row["status"], writer.STATUS_FAILED)
        self.assertEqual(row["failure_code"], writer.ROW_REFERENCE_CHANGED)
        self.assertTrue(any("department_id" in r for r in row["reasons"]))
        self.assertEqual(self.gateway.create_calls, [])

    def test_revalidation_not_accepted_blocks_create(self):
        self.prepare([(2, h("a"))], [h("a")])
        result = self.run_writer(
            [parsed_row(2, h("a"))], validator=FakeValidator(status="needs_review")
        )
        self.assertEqual(result["rows"][0]["failure_code"], writer.ROW_REVALIDATION_NOT_ACCEPTED)
        self.assertEqual(self.gateway.create_calls, [])

    def test_empty_work_email_is_blocked_defensively(self):
        self.prepare([(2, h("a"))], [h("a")])
        result = self.run_writer([parsed_row(2, h("a"), email="   ")])

        row = result["rows"][0]
        self.assertEqual(row["status"], writer.STATUS_FAILED)
        self.assertEqual(row["failure_code"], writer.ROW_MISSING_WORK_EMAIL)
        self.assertEqual(self.gateway.create_calls, [])
        types = [r["record_type"] for r in self.read_log(result)]
        self.assertNotIn("attempt", types)

    def test_approved_row_missing_from_file_is_not_created(self):
        self.prepare([(2, h("a")), (3, h("b"))], [h("a"), h("b")])
        result = self.run_writer([parsed_row(2, h("a"))])

        by_hash = {r["row_hash"]: r for r in result["rows"]}
        self.assertEqual(by_hash[h("b")]["failure_code"], writer.ROW_NOT_FOUND)
        self.assertEqual(by_hash[h("a")]["status"], writer.STATUS_CREATED)
        self.assertEqual(len(self.gateway.create_calls), 1)

    def test_row_changed_since_dry_run_is_not_created(self):
        self.prepare([(2, h("a"))], [h("a")])
        result = self.run_writer([parsed_row(2, h("z"), name="Edited")])

        row = result["rows"][0]
        self.assertEqual(row["failure_code"], writer.ROW_HASH_CHANGED)
        self.assertEqual(row["status"], writer.STATUS_FAILED)
        self.assertEqual(self.gateway.create_calls, [])

    def test_too_many_approved_rows_aborts_before_results_file(self):
        hashes = [h(c) for c in "abcd"]
        self.prepare([(i + 2, x) for i, x in enumerate(hashes)], hashes)
        with self.assertRaises(writer.WriterAbort) as ctx:
            self.run_writer([])
        self.assertEqual(ctx.exception.code, writer.ABORT_TOO_MANY_ROWS)
        self.assertEqual(self.gateway.create_calls, [])
        self.assertFalse(self.output_dir.exists())

    def test_rerun_refused_when_results_file_exists(self):
        self.prepare([(2, h("a"))], [h("a")])
        self.run_writer([parsed_row(2, h("a"))])
        with self.assertRaises(writer.WriterAbort) as ctx:
            self.run_writer([parsed_row(2, h("a"))])
        self.assertEqual(ctx.exception.code, writer.ABORT_RESULTS_FILE_EXISTS)
        self.assertEqual(len(self.gateway.create_calls), 1)

    def test_source_file_name_mismatch_aborts(self):
        self.prepare([(2, h("a"))], [h("a")])
        self.input_path = self.tmpdir / "other_file.xlsx"
        self.input_path.write_bytes(b"x")
        with self.assertRaises(writer.WriterAbort) as ctx:
            self.run_writer([parsed_row(2, h("a"))])
        self.assertEqual(ctx.exception.code, writer.ABORT_SOURCE_FILE_NAME_MISMATCH)
        self.assertEqual(self.gateway.create_calls, [])
        self.assertFalse(self.output_dir.exists())

    def test_company_id_mismatch_rejected_locally_before_odoo_create(self):
        diff_ids = dict(IDS, company_id=17)
        self.prepare([(2, h("a"))], [h("a")])
        self.report_path.write_text(
            json.dumps(
                {
                    "header": {"run_id": RUN_ID, "source_hash": SOURCE_HASH},
                    "rows": [
                        {
                            "excel_row_number": 2,
                            "row_hash": h("a"),
                            "final_status": "accepted",
                            "resolved_ids": diff_ids,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = self.run_writer(
            [parsed_row(2, h("a"))],
            validator=FakeValidator(ids=diff_ids),
            company_id=15,
        )

        row = result["rows"][0]
        self.assertEqual(row["status"], writer.STATUS_FAILED)
        self.assertEqual(row["failure_code"], writer.ROW_COMPANY_ID_MISMATCH)
        self.assertEqual(row["resolved_company_id"], 17)
        self.assertEqual(row["target_company_id"], 15)
        self.assertEqual(self.gateway.create_calls, [])
        types = [r["record_type"] for r in self.read_log(result)]
        self.assertNotIn("attempt", types)

    def test_allowed_company_ids_context_passed_to_create_and_read(self):
        self.prepare([(2, h("a"))], [h("a")])
        result = self.run_writer([parsed_row(2, h("a"))], company_id=15)

        self.assertEqual(len(self.gateway.create_calls), 1)
        self.assertEqual(self.gateway.create_contexts, [{"allowed_company_ids": [15]}])
        self.assertEqual(self.gateway.read_contexts, [{"allowed_company_ids": [15]}])
        self.assertEqual(result["header"]["target_company_id"], 15)

    def test_run_writer_requires_valid_positive_company_id(self):
        self.prepare([(2, h("a"))], [h("a")])
        for bad_id in (0, -1, -15, "15", True, False, None):
            with self.assertRaises(writer.WriterAbort) as ctx:
                self.run_writer([parsed_row(2, h("a"))], company_id=bad_id)
            self.assertEqual(ctx.exception.code, writer.ABORT_INVALID_COMPANY_ID)
        self.assertEqual(self.gateway.create_calls, [])

    def test_cli_requires_company_id_flag(self):
        with self.assertRaises(SystemExit) as ctx:
            writer.main([
                "--input", str(self.input_path),
                "--report", str(self.report_path),
                "--approval", str(self.approval_path),
                "--output-dir", str(self.output_dir),
            ])
        self.assertEqual(ctx.exception.code, 2)

    def test_retry_call_recovers_after_transient_failure(self):
        sleeps = []
        attempts = 0

        def flaky():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ConnectionResetError(f"transient error {attempts}")
            return "success"

        res = writer.retry_call(flaky, max_attempts=3, backoff_base=1.0, sleep_fn=sleeps.append)
        self.assertEqual(res, "success")
        self.assertEqual(attempts, 3)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_retry_call_re_raises_after_max_attempts(self):
        sleeps = []
        attempts = 0

        def persistent_fail():
            nonlocal attempts
            attempts += 1
            raise TimeoutError("timeout")

        with self.assertRaises(TimeoutError):
            writer.retry_call(persistent_fail, max_attempts=3, backoff_base=1.0, sleep_fn=sleeps.append)
        self.assertEqual(attempts, 3)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_live_reference_snapshot_transient_failure_recovers_and_creates(self):
        sleeps = []
        self.repository = FakeRepository(fail_snapshot_count=1)
        self.prepare([(2, h("a"))], [h("a")])
        result = self.run_writer([parsed_row(2, h("a"))], sleep_fn=sleeps.append)

        row = result["rows"][0]
        self.assertEqual(row["status"], writer.STATUS_CREATED)
        self.assertEqual(self.repository.snapshot_calls, 2)
        self.assertEqual(sleeps, [1.0])
        self.assertEqual(len(self.gateway.create_calls), 1)

    def test_live_reference_snapshot_persistent_failure_fails_row(self):
        sleeps = []
        self.repository = FakeRepository(fail_snapshot_count=5)
        self.prepare([(2, h("a"))], [h("a")])
        result = self.run_writer([parsed_row(2, h("a"))], sleep_fn=sleeps.append)

        row = result["rows"][0]
        self.assertEqual(row["status"], writer.STATUS_FAILED)
        self.assertEqual(row["failure_code"], writer.ROW_REVALIDATION_ERROR)
        self.assertEqual(self.repository.snapshot_calls, 3)
        self.assertEqual(sleeps, [1.0, 2.0])
        self.assertEqual(len(self.gateway.create_calls), 0)

    def test_read_employee_transient_failure_recovers_and_verifies(self):
        sleeps = []
        self.gateway = FakeGateway(fail_read_count=1)
        self.prepare([(2, h("a"))], [h("a")])
        result = self.run_writer([parsed_row(2, h("a"))], sleep_fn=sleeps.append)

        row = result["rows"][0]
        self.assertEqual(row["status"], writer.STATUS_CREATED)
        self.assertEqual(row["verified"], True)
        self.assertEqual(self.gateway.read_attempts, 2)
        self.assertEqual(sleeps, [1.0])
        self.assertEqual(len(self.gateway.create_calls), 1)

    def test_create_employee_is_never_retried(self):
        sleeps = []
        self.gateway = FakeGateway(fail_on_call=1, exc=RuntimeError("connection dropped on create"))
        self.prepare([(2, h("a"))], [h("a")])
        result = self.run_writer([parsed_row(2, h("a"))], sleep_fn=sleeps.append)

        row = result["rows"][0]
        self.assertEqual(row["status"], writer.STATUS_UNCERTAIN)
        self.assertEqual(row["failure_code"], writer.ROW_OUTCOME_UNCERTAIN)
        # CRITICAL ACCEPTANCE CRITERIA: create_employee called exactly ONCE; no retry under any circumstances!
        self.assertEqual(len(self.gateway.create_calls), 1)
        self.assertEqual(sleeps, [])

    def test_build_create_values_includes_hiring_date_when_present(self):
        row = parsed_row(2, h("a"))
        row["fields"]["hiring_date"] = {"value": "2026-10-06"}
        values = writer.build_create_values(row, IDS)
        self.assertEqual(values.get("hiring_date"), "2026-10-06")

    def test_build_create_values_omits_hiring_date_when_empty_or_absent(self):
        row = parsed_row(2, h("a"))
        row["fields"]["hiring_date"] = {"value": ""}
        values = writer.build_create_values(row, IDS)
        self.assertNotIn("hiring_date", values)

        del row["fields"]["hiring_date"]
        values_no_key = writer.build_create_values(row, IDS)
        self.assertNotIn("hiring_date", values_no_key)

    def test_writer_writes_and_verifies_hiring_date(self):
        self.prepare([(2, h("a"))], [h("a")])
        row_in = parsed_row(2, h("a"))
        row_in["fields"]["hiring_date"] = {"value": "2026-10-06"}
        result = self.run_writer([row_in])

        self.assertEqual(len(self.gateway.create_calls), 1)
        self.assertEqual(self.gateway.create_calls[0].get("hiring_date"), "2026-10-06")
        row = result["rows"][0]
        self.assertEqual(row["status"], writer.STATUS_CREATED)
        self.assertEqual(row["verified"], True)


if __name__ == "__main__":
    unittest.main()
