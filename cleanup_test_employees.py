"""Safely clean employees created by one specific writer results file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from odoo_cleanup_gateway import OdooCleanupGateway
from odoo_readonly_repository import OdooReadonlyRepository


class CleanupInputError(ValueError):
    pass


def load_created_records(results_path: str | Path) -> Dict[int, Dict[str, Any]]:
    """Load only created rows from one writer JSONL results file."""
    records: Dict[int, Dict[str, Any]] = {}
    path = Path(results_path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise CleanupInputError(f"Cannot read results file: {path}") from exc

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CleanupInputError(f"Invalid JSON at line {line_number}.") from exc

        if record.get("record_type") != "row" or record.get("status") != "created":
            continue

        employee_id = record.get("odoo_employee_id")
        email = record.get("attempted_work_email")
        if not isinstance(employee_id, int) or employee_id <= 0:
            raise CleanupInputError(
                f"Created row at line {line_number} has no valid odoo_employee_id."
            )
        if not isinstance(email, str) or not email.strip():
            raise CleanupInputError(
                f"Created row at line {line_number} has no attempted_work_email."
            )
        if employee_id in records:
            raise CleanupInputError(
                f"Results file contains duplicate created employee ID: {employee_id}."
            )
        records[employee_id] = record

    if not records:
        raise CleanupInputError("Results file contains no created rows.")
    return records


def read_current_employee(repository, employee_id: int) -> Optional[Dict[str, Any]]:
    rows = repository._execute_kw(
        "hr.employee",
        "search_read",
        [[["id", "=", employee_id]]],
        {
            "fields": ["id", "name", "work_email", "active"],
            "context": {"active_test": False},
        },
    )
    return rows[0] if rows else None


def emails_match(current: Optional[Dict[str, Any]], expected: str) -> bool:
    return bool(current) and (current.get("work_email") or "").strip().lower() == expected.strip().lower()


def process_cleanup(
    records: Dict[int, Dict[str, Any]],
    repository,
    gateway=None,
    confirm: bool = False,
) -> int:
    failed = False
    for employee_id, record in records.items():
        expected_email = record["attempted_work_email"]
        current = read_current_employee(repository, employee_id)
        if not current:
            print({"employee_id": employee_id, "action": "rejected", "reason": "employee_not_found"})
            failed = True
            continue
        if not emails_match(current, expected_email):
            print({"employee_id": employee_id, "action": "rejected", "reason": "work_email_mismatch"})
            failed = True
            continue

        if not confirm:
            print({"employee_id": employee_id, "action": "would_delete", "work_email_match": True})
            continue

        try:
            deleted = gateway.delete_employee_for_test_cleanup(employee_id)
            print({"employee_id": employee_id, "action": "deleted", "deleted": deleted})
        except Exception as exc:
            print({
                "employee_id": employee_id,
                "action": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            })
            failed = True
            continue

        after = read_current_employee(repository, employee_id)
        exists_after_delete = after is not None
        print({"employee_id": employee_id, "exists_after_delete": exists_after_delete})
        failed = failed or exists_after_delete

    return 1 if failed else 0


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Safely clean only employees recorded as created by one writer JSONL file."
    )
    parser.add_argument("--results", required=True, help="Writer writer_results.jsonl path.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Verify candidates without deleting.")
    mode.add_argument("--confirm", action="store_true", help="Authorize deletion after live email checks.")
    args = parser.parse_args(argv)

    records = load_created_records(args.results)
    repository = OdooReadonlyRepository()
    repository.connect()

    gateway = None
    if args.confirm:
        gateway = OdooCleanupGateway(
            url=repository.url,
            db=repository.db,
            login=repository.username,
            password=repository.api_key,
        )

    print({
        "results": str(args.results),
        "created_rows": len(records),
        "mode": "confirm" if args.confirm else "dry-run",
    })
    return process_cleanup(records, repository, gateway=gateway, confirm=args.confirm)


if __name__ == "__main__":
    raise SystemExit(main())
