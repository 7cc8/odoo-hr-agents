"""Schema and validation for the writer's approval file.

This module performs pure, offline validation only. It never imports
odoo_readonly_repository or any writer/create/write/unlink logic, and is
safe to use and test before writer.py exists.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


class ApprovalSchemaError(Exception):
    """The approval file itself is malformed (missing/invalid fields)."""


class ApprovalReportMismatchError(Exception):
    """The approval file is well-formed but does not correspond to the
    specific dry-run report it claims to approve."""


REQUIRED_APPROVAL_FIELDS = (
    "run_id",
    "source_hash",
    "source_file_name",
    "approved_by",
    "approved_at",
    "approved_row_hashes",
    "expires_at",  # P4: تاريخ صلاحية الاعتماد (TTL)
    "is_consumed",  # P4: هل تم استهلاك الاعتماد
)


@dataclass(frozen=True)
class Approval:
    run_id: str
    source_hash: str
    source_file_name: str
    approved_by: str
    approved_at: str  # ISO 8601 string, validated at parse time
    approved_row_hashes: List[str]
    expires_at: str  # P4: ISO 8601 string for TTL expiration
    is_consumed: bool  # P4: single-use flag

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Approval":
        data = dict(data)
        if "expires_at" not in data:
            data["expires_at"] = "2099-12-31T23:59:59Z"
        if "is_consumed" not in data:
            data["is_consumed"] = False

        missing = [f for f in REQUIRED_APPROVAL_FIELDS if f not in data]
        if missing:
            raise ApprovalSchemaError(f"Approval file is missing required fields: {missing}")

        approved_at_raw = data["approved_at"]
        try:
            # Accepts a trailing "Z" by normalizing it to "+00:00".
            datetime.fromisoformat(str(approved_at_raw).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ApprovalSchemaError(
                f"approved_at is not a valid ISO 8601 datetime: {approved_at_raw!r}"
            ) from exc

        # P4: التحقق من صلاحية expires_at
        expires_at_raw = data["expires_at"]
        try:
            expires_dt = datetime.fromisoformat(str(expires_at_raw).replace("Z", "+00:00"))
            # التحقق من أن الاعتماد لم ينته
            now = datetime.now(timezone.utc) if expires_dt.tzinfo is not None else datetime.now()
            if now > expires_dt:
                raise ApprovalSchemaError(
                    f"Approval has expired at {expires_at_raw}. Current time: {now.isoformat()}"
                )
        except ValueError as exc:
            raise ApprovalSchemaError(
                f"expires_at is not a valid ISO 8601 datetime: {expires_at_raw!r}"
            ) from exc

        # P4: التحقق من أن الاعتماد لم يتم استهلاكه
        is_consumed = data.get("is_consumed", False)
        if is_consumed:
            raise ApprovalSchemaError("Approval has already been consumed and cannot be reused.")

        if not isinstance(data["approved_row_hashes"], list) or not all(
            isinstance(h, str) for h in data["approved_row_hashes"]
        ):
            raise ApprovalSchemaError("approved_row_hashes must be a list of strings.")

        run_id = str(data["run_id"]).strip()
        source_hash = str(data["source_hash"]).strip()
        source_file_name = str(data["source_file_name"]).strip()
        approved_by = str(data["approved_by"]).strip()

        if not run_id:
            raise ApprovalSchemaError("run_id must not be empty.")

        if not source_hash:
            raise ApprovalSchemaError("source_hash must not be empty.")

        if not approved_by:
            raise ApprovalSchemaError("approved_by must not be empty.")

        if not source_file_name:
            raise ApprovalSchemaError("source_file_name must not be empty.")

        return Approval(
            run_id=run_id,
            source_hash=source_hash,
            source_file_name=source_file_name,
            approved_by=approved_by,
            approved_at=str(approved_at_raw),
            approved_row_hashes=list(data["approved_row_hashes"]),
            expires_at=str(expires_at_raw),
            is_consumed=is_consumed,
        )

    @staticmethod
    def load(file_path: str | Path) -> "Approval":
        file_path = Path(file_path)
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        return Approval.from_dict(raw)


def validate_approval_against_report(approval: Approval, report: Dict[str, Any]) -> None:
    """Raises ApprovalReportMismatchError unless the approval corresponds
    exactly to the given dry-run report dict (same run_id, same
    source_hash, and every approved_row_hashes entry is present in the
    report's rows AND has final_status == "accepted"). This is the check
    the future writer must call before create()-ing anything — rejecting
    on a missing approval file is not sufficient; a stale, edited, or
    over-broad approval file must be rejected too.
    """

    header = report.get("header", {})

    if approval.run_id != header.get("run_id"):
        raise ApprovalReportMismatchError(
            f"Approval run_id {approval.run_id!r} does not match report run_id {header.get('run_id')!r}."
        )

    if approval.source_hash != header.get("source_hash"):
        raise ApprovalReportMismatchError(
            "Approval source_hash does not match report source_hash. "
            "The source file may have changed since approval was granted."
        )

    report_rows_by_hash = {row["row_hash"]: row for row in report.get("rows", [])}

    unknown_hashes = [h for h in approval.approved_row_hashes if h not in report_rows_by_hash]

    not_accepted = [
        h for h in approval.approved_row_hashes
        if h in report_rows_by_hash and report_rows_by_hash[h].get("final_status") != "accepted"
    ]

    if unknown_hashes and not_accepted:
        raise ApprovalReportMismatchError(
            "Approval contains a mixed invalid selection: "
            f"unknown row_hash value(s) not present in the dry-run report: {unknown_hashes}; "
            f"and row_hash value(s) present in the report but not accepted: {not_accepted}."
        )

    if unknown_hashes:
        raise ApprovalReportMismatchError(
            f"Approval references {len(unknown_hashes)} row_hash value(s) not present "
            f"in this dry-run report: {unknown_hashes}"
        )

    if not_accepted:
        raise ApprovalReportMismatchError(
            f"Approval references {len(not_accepted)} row(s) present in the dry-run report "
            f"but not accepted: {not_accepted}"
        )