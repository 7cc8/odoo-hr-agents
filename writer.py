"""Writer stage: creates approved, re-validated employees in Odoo (test DBs only).

Reads nothing from Odoo except through the injected read-only repository and
never calls any Odoo method except through OdooWriteGateway.create_employee /
read_employee. Every preflight failure aborts before the results file exists
and before any create call.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from approval_schema import (
    Approval,
    ApprovalReportMismatchError,
    ApprovalSchemaError,
    validate_approval_against_report,
)
from odoo_write_gateway import EnvironmentGuardError

DEFAULT_MAX_ROWS = 3
DEFAULT_READ_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 1.0

STATUS_CREATED = "created"
STATUS_FAILED = "failed"
STATUS_UNCERTAIN = "outcome_uncertain"
STATUS_NOT_ATTEMPTED = "not_attempted"

ABORT_APPROVAL_INVALID = "approval_invalid"
ABORT_REPORT_UNREADABLE = "report_unreadable"
ABORT_APPROVAL_REPORT_MISMATCH = "approval_report_mismatch"
ABORT_SOURCE_FILE_NAME_MISMATCH = "source_file_name_mismatch"
ABORT_SOURCE_CHANGED = "source_changed_since_dry_run"
ABORT_ENVIRONMENT_MISMATCH = "environment_mismatch"
ABORT_NO_APPROVED_ROWS = "no_approved_rows"
ABORT_DUPLICATE_APPROVED_HASH = "duplicate_approved_row_hash"
ABORT_TOO_MANY_ROWS = "too_many_approved_rows"
ABORT_RESULTS_FILE_EXISTS = "results_file_exists"
ABORT_SOURCE_UNREADABLE = "source_unreadable"
ABORT_INVALID_COMPANY_ID = "invalid_company_id"

ROW_NOT_FOUND = "approved_row_not_found_in_file"
ROW_HASH_CHANGED = "row_hash_changed"
ROW_HASH_AMBIGUOUS = "approved_row_hash_ambiguous"
ROW_REVALIDATION_ERROR = "revalidation_error"
ROW_REVALIDATION_NOT_ACCEPTED = "revalidation_not_accepted"
ROW_REFERENCE_CHANGED = "reference_changed_since_dry_run"
ROW_COMPANY_ID_MISMATCH = "company_id_mismatch"
ROW_MISSING_WORK_EMAIL = "missing_work_email"
ROW_GUARD_BLOCKED = "environment_guard_blocked"
ROW_OUTCOME_UNCERTAIN = "create_outcome_uncertain"
ROW_STOPPED = "stopped_after_earlier_failure"

READBACK_FIELDS = ["name", "work_email", "company_id", "department_id", "job_id", "hiring_date"]
REFERENCE_KEYS = (("company_id", "company"), ("department_id", "department"), ("job_id", "job"))


class WriterAbort(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def retry_call(
    fn: Callable[[], Any],
    max_attempts: int = DEFAULT_READ_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Any:
    """Executes a read-only callable with exponential backoff on exceptions.

    Retries up to max_attempts. For attempt k (1-indexed):
    if attempt k < max_attempts fails with an Exception, sleeps backoff_base * (2 ** (k - 1))
    and retries. If attempt max_attempts fails, re-raises the exception.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts:
                delay = backoff_base * (2 ** (attempt - 1))
                sleep_fn(delay)
            else:
                raise last_exc


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm_url(url: Any) -> str:
    return str(url or "").rstrip("/")


def _id_of(item: Any) -> Optional[int]:
    if isinstance(item, dict) and isinstance(item.get("id"), int):
        return item["id"]
    return None


def _m2o_id(value: Any) -> Optional[int]:
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], int):
        return value[0]
    return None


def _as_dict(result: Any) -> Dict[str, Any]:
    return result.to_dict() if hasattr(result, "to_dict") else dict(result)


class _ResultsLog:
    """Append-only JSONL file, opened with 'x' so an existing file is never touched."""

    def __init__(self, path: Path):
        self.path = path
        self._fh = open(path, "x", encoding="utf-8")

    def append(self, record: Dict[str, Any]) -> None:
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def close(self) -> None:
        self._fh.close()


def _row_record(number, row_hash, status, code=None, reasons=None, **extra) -> Dict[str, Any]:
    record = {
        "record_type": "row",
        "excel_row_number": number,
        "row_hash": row_hash,
        "status": status,
        "failure_code": code,
        "reasons": list(reasons or []),
        "odoo_employee_id": None,
    }
    record.update(extra)
    return record


def build_create_values(row: Dict[str, Any], ids: Dict[str, Optional[int]]) -> Dict[str, Any]:
    fields = row["fields"]
    values: Dict[str, Any] = {
        "name": fields["name"]["value"],
        "work_email": fields["work_email"]["value"],
        "company_id": ids["company_id"],
    }
    for key in ("work_phone", "mobile_phone", "job_title"):
        if fields.get(key) and fields[key]["value"]:
            values[key] = fields[key]["value"]
    if fields.get("hiring_date") and fields["hiring_date"]["value"]:
        values["hiring_date"] = fields["hiring_date"]["value"]
    if ids.get("department_id") is not None:
        values["department_id"] = ids["department_id"]
    if ids.get("job_id") is not None:
        values["job_id"] = ids["job_id"]
    return values


def _verify_readback(values: Dict[str, Any], stored: Optional[Dict[str, Any]]) -> List[str]:
    if not stored:
        return ["readback returned no record"]
    problems = []
    if (stored.get("name") or "") != values["name"]:
        problems.append("name differs")
    if (stored.get("work_email") or "").strip().lower() != values["work_email"].strip().lower():
        problems.append("work_email differs")
    for key in ("company_id", "department_id", "job_id"):
        if key in values and _m2o_id(stored.get(key)) != values[key]:
            problems.append(f"{key} differs")
    if "hiring_date" in values and values["hiring_date"]:
        stored_date = stored.get("hiring_date")
        if stored_date != values["hiring_date"]:
            problems.append(f"hiring_date differs: expected {values['hiring_date']!r}, got {stored_date!r}")
    return problems


def _attempt_row(
    row,
    report_row,
    repository,
    gateway,
    validator_factory,
    log,
    target_company_id: int,
    read_retries: int = DEFAULT_READ_RETRIES,
    sleep_fn: Callable[[float], None] = time.sleep,
):
    """Returns (final_record, stop_run)."""
    number, row_hash = row["excel_row_number"], row["row_hash"]

    def rec(status, code=None, reasons=None, **extra):
        return _row_record(number, row_hash, status, code, reasons, **extra)

    try:
        snapshot = retry_call(
            repository.get_live_reference_snapshot,
            max_attempts=read_retries,
            sleep_fn=sleep_fn,
        )
        validation = _as_dict(
            validator_factory(repository).validate_single_row(
                row, snapshot["companies"], snapshot["departments"], snapshot["jobs"]
            )
        )
    except Exception as exc:
        return rec(STATUS_FAILED, ROW_REVALIDATION_ERROR, [f"{type(exc).__name__}: {exc}"]), False

    if validation.get("final_status") != "accepted":
        return rec(
            STATUS_FAILED,
            ROW_REVALIDATION_NOT_ACCEPTED,
            validation.get("reasons"),
            validator_status=validation.get("final_status"),
            validator_failure_code=validation.get("failure_code"),
        ), False

    refs = validation.get("resolved_references") or {}
    current = {ids_key: _id_of(refs.get(ref_key)) for ids_key, ref_key in REFERENCE_KEYS}
    reported = report_row.get("resolved_ids") or {}
    changed = [k for k in current if current[k] != reported.get(k)]
    if changed or current["company_id"] is None:
        return rec(
            STATUS_FAILED,
            ROW_REFERENCE_CHANGED,
            [f"{k}: dry-run={reported.get(k)!r} now={current[k]!r}" for k in changed],
        ), False

    if current["company_id"] != target_company_id:
        return rec(
            STATUS_FAILED,
            ROW_COMPANY_ID_MISMATCH,
            [
                f"Resolved company_id ({current['company_id']}) does not match target company_id ({target_company_id})."
            ],
            resolved_company_id=current["company_id"],
            target_company_id=target_company_id,
        ), False

    values = build_create_values(row, current)
    attempted = {"attempted_name": values["name"], "attempted_work_email": values["work_email"]}
    if not values["work_email"].strip():
        return rec(STATUS_FAILED, ROW_MISSING_WORK_EMAIL, ["work_email is required for creation."], **attempted), False

    log.append({"record_type": "attempt", "excel_row_number": number, "row_hash": row_hash, **attempted})

    context = {"allowed_company_ids": [target_company_id]}
    try:
        new_id = gateway.create_employee(values, context=context)
    except EnvironmentGuardError as exc:
        return rec(STATUS_FAILED, ROW_GUARD_BLOCKED, [str(exc)], **attempted), True
    except Exception as exc:
        return rec(
            STATUS_UNCERTAIN,
            ROW_OUTCOME_UNCERTAIN,
            [f"{type(exc).__name__}: {exc}", "Search Odoo manually for this email/name before any retry."],
            **attempted,
        ), True

    extra: Dict[str, Any] = dict(attempted)
    try:
        stored = retry_call(
            lambda: gateway.read_employee(new_id, READBACK_FIELDS, context=context),
            max_attempts=read_retries,
            sleep_fn=sleep_fn,
        )
        problems = _verify_readback(values, stored)
        extra["verified"] = not problems
        extra["verification_problems"] = problems
    except Exception as exc:
        extra["verified"] = None
        extra["verification_error"] = f"{type(exc).__name__}: {exc}"
    record = rec(STATUS_CREATED, None, ["Created."], **extra)
    record["odoo_employee_id"] = new_id
    return record, False


def run_writer(
    input_xlsx_path,
    report_path,
    approval_path,
    output_dir,
    repository,
    gateway,
    company_id: int,
    max_rows: int = DEFAULT_MAX_ROWS,
    parse_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    validator_factory: Optional[Callable[[Any], Any]] = None,
    os_user: Optional[str] = None,
    read_retries: int = DEFAULT_READ_RETRIES,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Dict[str, Any]:
    if not isinstance(company_id, int) or isinstance(company_id, bool) or company_id <= 0:
        raise WriterAbort(
            ABORT_INVALID_COMPANY_ID,
            f"company_id must be a positive integer, got: {company_id!r}",
        )
    if parse_fn is None:
        from parser import parse_xlsx as parse_fn
    if validator_factory is None:
        from validator import Validator as validator_factory

    input_path = Path(input_xlsx_path)
    if not input_path.exists():
        samples_cand = Path("samples") / input_path.name
        if samples_cand.exists():
            input_path = samples_cand

    try:
        approval = Approval.load(approval_path)
    except (ApprovalSchemaError, ValueError, OSError) as exc:
        raise WriterAbort(ABORT_APPROVAL_INVALID, str(exc)) from exc
    try:
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise WriterAbort(ABORT_REPORT_UNREADABLE, str(exc)) from exc
    try:
        validate_approval_against_report(approval, report)
    except ApprovalReportMismatchError as exc:
        raise WriterAbort(ABORT_APPROVAL_REPORT_MISMATCH, str(exc)) from exc

    if input_path.name != approval.source_file_name:
        raise WriterAbort(
            ABORT_SOURCE_FILE_NAME_MISMATCH,
            f"input file {input_path.name!r} != approved file {approval.source_file_name!r}",
        )

    hashes = approval.approved_row_hashes
    if not hashes:
        raise WriterAbort(ABORT_NO_APPROVED_ROWS, "approval lists no rows.")
    if len(set(hashes)) != len(hashes):
        raise WriterAbort(ABORT_DUPLICATE_APPROVED_HASH, "approved_row_hashes contains repeated values.")
    if len(hashes) > max_rows:
        raise WriterAbort(ABORT_TOO_MANY_ROWS, f"{len(hashes)} approved rows exceed max_rows={max_rows}.")

    try:
        parsed = parse_fn(str(input_path))
    except Exception as exc:
        raise WriterAbort(
            ABORT_SOURCE_UNREADABLE,
            f"{type(exc).__name__}: {exc}",
        ) from exc
    report_header = report.get("header", {})
    if parsed.get("source_hash") != report_header.get("source_hash") or parsed.get("run_id") != report_header.get("run_id"):
        raise WriterAbort(ABORT_SOURCE_CHANGED, "re-parsed file does not match the dry-run report.")

    repo_info = retry_call(repository.get_session_info, max_attempts=read_retries, sleep_fn=sleep_fn)
    gateway_info = gateway.get_session_info()
    if repo_info.get("odoo_db") != gateway_info.get("odoo_db") or _norm_url(repo_info.get("odoo_url")) != _norm_url(
        gateway_info.get("odoo_url")
    ):
        raise WriterAbort(
            ABORT_ENVIRONMENT_MISMATCH,
            f"repository={repo_info.get('odoo_url')}|{repo_info.get('odoo_db')} "
            f"gateway={gateway_info.get('odoo_url')}|{gateway_info.get('odoo_db')}",
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        log = _ResultsLog(output_dir / f"writer_results_{approval.run_id}.jsonl")
    except FileExistsError as exc:
        raise WriterAbort(ABORT_RESULTS_FILE_EXISTS, f"{exc.filename} already exists; refusing to re-run.") from exc

    parsed_rows = parsed["rows"]
    by_hash: Dict[str, List[Dict[str, Any]]] = {}
    by_number: Dict[int, Dict[str, Any]] = {}
    for prow in parsed_rows:
        by_hash.setdefault(prow["row_hash"], []).append(prow)
        by_number[prow["excel_row_number"]] = prow
    report_by_hash = {r["row_hash"]: r for r in report.get("rows", [])}

    early: List[Dict[str, Any]] = []
    queue: List[Any] = []
    for h in hashes:
        rep = report_by_hash[h]
        number = rep.get("excel_row_number")
        matches = by_hash.get(h, [])
        if len(matches) > 1:
            early.append(_row_record(number, h, STATUS_FAILED, ROW_HASH_AMBIGUOUS,
                                     [f"{len(matches)} rows in the file share this row_hash."]))
        elif len(matches) == 1:
            queue.append((matches[0]["excel_row_number"], h, matches[0], rep))
        elif number in by_number:
            early.append(_row_record(number, h, STATUS_FAILED, ROW_HASH_CHANGED,
                                     [f"Row {number} exists but its content changed since the dry-run."]))
        else:
            early.append(_row_record(number, h, STATUS_FAILED, ROW_NOT_FOUND,
                                     ["Approved row is absent from the re-parsed file."]))
    queue.sort(key=lambda item: item[0])

    approved_set = set(hashes)
    header = {
        "record_type": "header",
        "run_id": approval.run_id,
        "source_hash": approval.source_hash,
        "source_file_name": approval.source_file_name,
        "approved_by": approval.approved_by,
        "approved_at": approval.approved_at,
        "target_company_id": company_id,
        "odoo_url": gateway_info.get("odoo_url"),
        "odoo_db": gateway_info.get("odoo_db"),
        "uid": gateway_info.get("uid"),
        "version": gateway_info.get("server_version"),
        "executed_by_os_user": os_user or _safe_os_user(),
        "executed_at": _utc_now(),
        "max_rows": max_rows,
        "approved_count": len(hashes),
        "not_approved_rows": sum(1 for r in parsed_rows if r["row_hash"] not in approved_set),
    }

    rows_out: List[Dict[str, Any]] = []
    try:
        log.append(header)
        for record in early:
            log.append(record)
            rows_out.append(record)

        stop = False
        for number, h, prow, rep in queue:
            if stop:
                record = _row_record(number, h, STATUS_NOT_ATTEMPTED, ROW_STOPPED,
                                     ["Run stopped after an earlier uncertain or blocked create."])
            else:
                record, stop = _attempt_row(
                    prow,
                    rep,
                    repository,
                    gateway,
                    validator_factory,
                    log,
                    company_id,
                    read_retries=read_retries,
                    sleep_fn=sleep_fn,
                )
            log.append(record)
            rows_out.append(record)

        counts: Dict[str, int] = {}
        for record in rows_out:
            counts[record["status"]] = counts.get(record["status"], 0) + 1
        footer = {"record_type": "footer", "status_counts": counts, "finished_at": _utc_now()}
        log.append(footer)
    finally:
        log.close()

    return {"results_path": str(log.path), "header": header, "rows": rows_out, "footer": footer}


def _safe_os_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def main(argv: Optional[List[str]] = None) -> int:
    parser_ = argparse.ArgumentParser(description="Create approved employees in a test Odoo database.")
    parser_.add_argument("--input", required=True)
    parser_.add_argument("--report", required=True)
    parser_.add_argument("--approval", required=True)
    parser_.add_argument("--output-dir", required=True)
    parser_.add_argument(
        "--company-id",
        type=int,
        required=True,
        help="Target company ID for Odoo context and row validation.",
    )
    parser_.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    args = parser_.parse_args(argv)

    from odoo_readonly_repository import OdooReadonlyRepository
    from odoo_write_gateway import OdooWriteGateway

    try:
        gateway = OdooWriteGateway(
            os.environ["ODOO_URL"], os.environ["ODOO_DB"], os.environ["ODOO_USERNAME"], os.environ["ODOO_API_KEY"]
        )
        result = run_writer(
            args.input, args.report, args.approval, args.output_dir,
            OdooReadonlyRepository(), gateway, company_id=args.company_id, max_rows=args.max_rows,
        )
    except KeyError as exc:
        print(f"ABORT: missing environment variable {exc}", file=sys.stderr)
        return 2
    except (WriterAbort, EnvironmentGuardError) as exc:
        print(f"ABORT: {exc}", file=sys.stderr)
        return 2

    print(f"Results: {result['results_path']}")
    print(f"Status counts: {result['footer']['status_counts']}")
    return 0 if all(r["status"] == STATUS_CREATED for r in result["rows"]) else 1


if __name__ == "__main__":
    sys.exit(main())