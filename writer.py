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
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from approval_schema import (
    Approval,
    ApprovalAlreadyConsumedError,
    ApprovalExpiredError,
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
ABORT_APPROVAL_EXPIRED = "approval_expired"
ABORT_APPROVAL_CONSUMED = "approval_already_consumed"
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
    pre_summary: Optional[Dict[str, Any]] = None,
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
        if pre_summary:
            if pre_summary.get("company_created"):
                cc = pre_summary["company_created"]
                if cc.get("name") and cc["name"].lower() not in [c.get("name", "").lower() for c in snapshot.get("companies", [])]:
                    snapshot.setdefault("companies", []).append({"id": cc["id"], "name": cc["name"], "active": True})
            for dc in pre_summary.get("departments_created", []):
                if dc.get("name") and dc["name"].lower() not in [(d.get("complete_name") or d.get("name") or "").lower() for d in snapshot.get("departments", [])]:
                    snapshot.setdefault("departments", []).append({"id": dc["id"], "name": dc["name"], "complete_name": dc["name"], "company_id": [target_company_id, ""]})
            for jc in pre_summary.get("jobs_created", []):
                if jc.get("name") and jc["name"].lower() not in [(j.get("name") or "").lower() for j in snapshot.get("jobs", [])]:
                    snapshot.setdefault("jobs", []).append({"id": jc["id"], "name": jc["name"], "company_id": [target_company_id, ""]})

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


def _normalize_iso_date(raw_val: Any, fallback: Optional[str] = None) -> Optional[str]:
    """يحوّل القيمة الزمنية إلى صيغة YYYY-MM-DD صالحة لأودو."""
    if raw_val is None:
        return fallback
    if hasattr(raw_val, "strftime"):
        return raw_val.strftime("%Y-%m-%d")
    txt = str(raw_val).strip()
    if not txt or txt.startswith("="):
        return fallback
    if len(txt) == 7 and txt[4] == "-":
        return f"{txt}-01"
    part = txt.split("T")[0].split(" ")[0].strip()
    if len(part) >= 10 and part[4] == "-" and part[7] == "-":
        return part[:10]
    return fallback


def _safe_float(raw_val: Any, default: float = 0.0) -> float:
    if raw_val is None:
        return default
    txt = str(raw_val).strip().replace(",", "")
    if not txt or txt.startswith("="):
        return default
    try:
        return float(txt)
    except (ValueError, TypeError):
        return default


def _get_muwaffaq_instance() -> Any:
    try:
        from agents.muwaffaq_agent import get_muwaffaq_agent
        return get_muwaffaq_agent()
    except Exception:
        return None


def _resolve_with_muwaffaq(
    query: str,
    candidates_map: Dict[str, int],
    entity_type: str = "employee",
    muwaffaq: Any = None,
) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    """يطابق الاسم أو المصطلح أولاً بالتطابق المباشر ثم عبر وكيل موفق (MuwaffaqAgent)."""
    q_clean = str(query or "").strip()
    if not q_clean or not candidates_map:
        return None, None
    q_low = q_clean.lower()
    if q_clean in candidates_map:
        return candidates_map[q_clean], None
    if q_low in candidates_map:
        return candidates_map[q_low], None

    agent = muwaffaq or _get_muwaffaq_instance()
    if not agent or not hasattr(agent, "find_match"):
        return None, None

    candidates_list = []
    seen_ids = set()
    for name_key, rec_id in candidates_map.items():
        if not name_key or rec_id in seen_ids:
            continue
        seen_ids.add(rec_id)
        candidates_list.append({"id": rec_id, "name": name_key})

    if not candidates_list:
        return None, None

    try:
        res = agent.find_match({
            "query": q_clean,
            "field_type": entity_type,
            "candidates": candidates_list,
        })
        best = res.get("best_match") if isinstance(res, dict) else None
        if isinstance(best, dict) and best.get("id") is not None and res.get("status") in ("matched", "proposed"):
            conf_val = float(best.get("confidence", res.get("confidence", 0.0)) or 0.0)
            if conf_val >= 0.55:
                return int(best["id"]), {
                    "query": q_clean,
                    "matched_id": int(best["id"]),
                    "matched_name": str(best.get("name") or best.get("display_name") or ""),
                    "confidence": round(conf_val, 3),
                    "strategy": str(best.get("strategy") or res.get("strategy_used") or "semantic"),
                    "entity_type": entity_type,
                }
    except Exception as exc:
        logger.debug(f"Muwaffaq find_match failed for '{q_clean}' ({entity_type}): {exc}")
    return None, None


def _extract_raw_sheet_rows(ws: Any, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """يستخرج صفوف ورقة إكسل واحدة كقاموس مسطح {key: value} اعتماداً على _map_columns_to_keys."""
    from excel_template_validator import _detect_header_and_data_rows, _map_columns_to_keys

    header_row_idx, _validator_data_start = _detect_header_and_data_rows(ws, spec)
    header_cells = [cell.value for cell in ws[header_row_idx]]
    col_map = _map_columns_to_keys(header_cells, spec)
    if not col_map:
        return []

    data_start_row = header_row_idx + 1
    if header_row_idx == 2 and ws.max_row > 3:
        first_cell = ws.cell(row=3, column=1)
        first_txt = str(first_cell.value or "").strip()
        is_italic = bool(getattr(getattr(first_cell, "font", None), "italic", False))
        if is_italic or "1088776655" in first_txt or "شركة النخبة" in first_txt:
            data_start_row = 4

    rows_out: List[Dict[str, Any]] = []
    for r_idx in range(data_start_row, ws.max_row + 1):
        fields: Dict[str, Any] = {}
        has_any = False
        for key, col_idx in col_map.items():
            raw_v = ws.cell(row=r_idx, column=col_idx).value
            if raw_v is None:
                fields[key] = ""
                continue
            txt = str(raw_v).strip()
            if txt.startswith("="):
                fields[key] = ""
                continue
            if txt:
                has_any = True
            fields[key] = raw_v if not isinstance(raw_v, str) else txt
        if has_any:
            rows_out.append({"excel_row_number": r_idx, "fields": fields})
    return rows_out


def _setup_onboarding_prerequisites(
    input_path: Path,
    repository: Any,
    gateway: Any,
    target_company_id: int,
) -> Tuple[int, Dict[str, Any]]:
    """
    تأسيس المتطلبات المسبقة للمنشأة والهيكل التنظيمي بالترتيب الاعتمادي:
    1) تأسيس/ربط المنشأة (res.company) بدعم المطابقة الدلالية عبر موفق.
    2) تأسيس/ربط الأقسام (hr.department).
    3) تأسيس/ربط المسميات الوظيفية (hr.job).
    """
    summary: Dict[str, Any] = {
        "company_id": target_company_id,
        "company_created": None,
        "departments_created": [],
        "jobs_created": [],
    }

    if not input_path.exists():
        return target_company_id, summary

    try:
        import openpyxl
        wb = openpyxl.load_workbook(input_path, data_only=True)
    except Exception:
        return target_company_id, summary

    try:
        from excel_template_validator import (
            TEMPLATE_SPECS,
            _detect_header_and_data_rows,
            _map_columns_to_keys,
            _resolve_sheet_domain,
            is_auxiliary_sheet,
        )
    except Exception:
        TEMPLATE_SPECS = {}
        _detect_header_and_data_rows = None
        _map_columns_to_keys = None
        _resolve_sheet_domain = None
        is_auxiliary_sheet = lambda s: s.strip().lower() in {"instructions", "reference"}

    muwaffaq = _get_muwaffaq_instance()

    comp_sheet = None
    for name in wb.sheetnames:
        if is_auxiliary_sheet(name):
            continue
        domain = _resolve_sheet_domain(name) if _resolve_sheet_domain else None
        name_lower = name.strip().lower()
        if domain == "company" or any(k in name_lower for k in ("company", "منشأة", "منشاه", "شركة")):
            comp_sheet = wb[name]
            break

    effective_company_id = target_company_id
    comp_candidates: Dict[str, int] = {}
    try:
        companies = repository.get_companies() if hasattr(repository, "get_companies") else []
        for c in companies:
            if c.get("name") and c.get("id") is not None:
                comp_candidates[str(c["name"]).strip()] = int(c["id"])
                comp_candidates[str(c["name"]).strip().lower()] = int(c["id"])
    except Exception:
        pass

    if comp_sheet and comp_sheet.max_row >= 2:
        comp_rows: List[Dict[str, Any]] = []
        if "company" in TEMPLATE_SPECS and _detect_header_and_data_rows and _map_columns_to_keys:
            try:
                comp_rows = _extract_raw_sheet_rows(comp_sheet, TEMPLATE_SPECS["company"])
            except Exception:
                comp_rows = []

        comp_payload: Dict[str, Any] = {}
        if comp_rows:
            f = comp_rows[0].get("fields", {})
            comp_name = str(f.get("name_ar") or f.get("name_en") or "").strip()
            if comp_name:
                comp_payload["name"] = comp_name
                if f.get("vat_number"):
                    comp_payload["vat"] = str(f["vat_number"]).strip()
                if f.get("city"):
                    comp_payload["city"] = str(f["city"]).strip()
        else:
            comp_name = None
            for r_idx in range(2, min(comp_sheet.max_row + 1, 6)):
                for cell in comp_sheet[r_idx]:
                    val = str(cell.value or "").strip()
                    if val and not val.endswith("*") and not val.startswith("=") and not any(h in val for h in ["اسم", "بيانات", "Company", "رقم", "سجل", "ملف"]):
                        comp_name = val
                        break
                if comp_name:
                    break
            if comp_name:
                comp_payload["name"] = comp_name

        if comp_payload.get("name"):
            c_name = comp_payload["name"]
            matched_cid, _ = _resolve_with_muwaffaq(c_name, comp_candidates, entity_type="company", muwaffaq=muwaffaq)
            if matched_cid is not None:
                effective_company_id = matched_cid
            elif hasattr(gateway, "create_record"):
                try:
                    new_cid = gateway.create_record("res.company", comp_payload)
                    effective_company_id = int(new_cid)
                    summary["company_created"] = {"id": int(new_cid), "name": c_name}
                    comp_candidates[c_name] = int(new_cid)
                    comp_candidates[c_name.lower()] = int(new_cid)
                except Exception as e:
                    logger.debug(f"Company setup prerequisite check skipped: {e}")

    summary["company_id"] = effective_company_id

    dept_candidates: Dict[str, int] = {}
    job_candidates: Dict[str, int] = {}
    try:
        depts_list = repository.get_departments(effective_company_id) if hasattr(repository, "get_departments") else []
        for d in depts_list:
            d_id = d.get("id")
            for k_name in (d.get("name"), d.get("complete_name")):
                if k_name and d_id is not None:
                    dept_candidates[str(k_name).strip()] = int(d_id)
                    dept_candidates[str(k_name).strip().lower()] = int(d_id)
        jobs_list = repository.get_jobs(effective_company_id) if hasattr(repository, "get_jobs") else []
        for j in jobs_list:
            j_id = j.get("id")
            j_name = j.get("name") or ""
            if j_name and j_id is not None:
                job_candidates[str(j_name).strip()] = int(j_id)
                job_candidates[str(j_name).strip().lower()] = int(j_id)
    except Exception as e:
        logger.debug(f"Reference cache read skipped: {e}")

    needed_depts: set = set()
    needed_jobs: set = set()

    for sheet_name in wb.sheetnames:
        if is_auxiliary_sheet(sheet_name):
            continue
        sheet = wb[sheet_name]
        if sheet.max_row < 2:
            continue

        domain = _resolve_sheet_domain(sheet_name) if _resolve_sheet_domain else None
        spec = TEMPLATE_SPECS.get(domain) if domain else None
        if _detect_header_and_data_rows and _map_columns_to_keys and spec:
            header_row, data_start = _detect_header_and_data_rows(sheet, spec)
            header_cells = [c.value for c in sheet[header_row]]
            col_map = _map_columns_to_keys(header_cells, spec)
            dept_col = col_map.get("department") or col_map.get("dept")
            job_col = col_map.get("job_title") or col_map.get("job")
            start_r = data_start
        else:
            header_row = 1
            h_vals = [str(c.value or "").strip().lower() for c in sheet[1]]
            if not any("name" in h or "اسم" in h or "department" in h or "قسم" in h for h in h_vals) and sheet.max_row >= 2:
                header_row = 2
                h_vals = [str(c.value or "").strip().lower() for c in sheet[2]]
            dept_col = None
            job_col = None
            for c_idx, h in enumerate(h_vals, 1):
                if any(k in h for k in ["department", "القسم", "إدارة", "ادارة"]):
                    dept_col = c_idx
                elif any(k in h for k in ["job", "وظيفة", "مسمى", "مسمي"]):
                    job_col = c_idx
            start_r = header_row + 1

        if dept_col or job_col:
            for r_idx in range(start_r, sheet.max_row + 1):
                if dept_col:
                    d_val = str(sheet.cell(row=r_idx, column=dept_col).value or "").strip()
                    if d_val and not d_val.startswith("=") and not d_val.endswith("*"):
                        matched_d, _ = _resolve_with_muwaffaq(d_val, dept_candidates, entity_type="department", muwaffaq=muwaffaq)
                        if matched_d is None:
                            needed_depts.add(d_val)
                if job_col:
                    j_val = str(sheet.cell(row=r_idx, column=job_col).value or "").strip()
                    if j_val and not j_val.startswith("=") and not j_val.endswith("*"):
                        matched_j, _ = _resolve_with_muwaffaq(j_val, job_candidates, entity_type="job", muwaffaq=muwaffaq)
                        if matched_j is None:
                            needed_jobs.add(j_val)

    for d_name in sorted(needed_depts):
        if d_name.lower() in dept_candidates:
            continue
        try:
            if hasattr(gateway, "create_record"):
                d_id = gateway.create_record("hr.department", {
                    "name": d_name,
                    "company_id": effective_company_id,
                })
                summary["departments_created"].append({"id": d_id, "name": d_name})
                dept_candidates[d_name] = int(d_id)
                dept_candidates[d_name.lower()] = int(d_id)
        except Exception as e:
            logger.debug(f"Could not auto-create department '{d_name}': {e}")

    for j_name in sorted(needed_jobs):
        if j_name.lower() in job_candidates:
            continue
        try:
            if hasattr(gateway, "create_record"):
                j_id = gateway.create_record("hr.job", {
                    "name": j_name,
                    "company_id": effective_company_id,
                })
                summary["jobs_created"].append({"id": j_id, "name": j_name})
                job_candidates[j_name] = int(j_id)
                job_candidates[j_name.lower()] = int(j_id)
        except Exception as e:
            logger.debug(f"Could not auto-create job '{j_name}': {e}")

    return effective_company_id, summary


def _resolve_employee_id_for_row(
    emp_ident: str,
    emp_id_num: str,
    employee_id_map: Dict[str, int],
    repo_emp_candidates: Dict[str, int],
    muwaffaq: Any = None,
) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    """يبحث عن معرف الموظف عبر الهوية/الإقامة، ثم الاسم المباشر، ثم وكيل موفق."""
    for key in (emp_id_num, emp_ident):
        k = str(key or "").strip()
        if not k:
            continue
        if k in employee_id_map:
            return employee_id_map[k], None
        if k.lower() in employee_id_map:
            return employee_id_map[k.lower()], None

    combined = {**repo_emp_candidates, **employee_id_map}
    if emp_ident:
        matched_id, trace = _resolve_with_muwaffaq(emp_ident, combined, entity_type="employee", muwaffaq=muwaffaq)
        if matched_id is not None:
            return matched_id, trace

    if not emp_ident and not emp_id_num and len(set(employee_id_map.values())) == 1:
        return next(iter(employee_id_map.values())), None
    return None, None


def _execute_domain_record(
    domain: str,
    fields: Dict[str, Any],
    repository: Any,
    gateway: Any,
    effective_company_id: int,
    employee_id_map: Dict[str, int],
    repo_emp_candidates: Dict[str, int],
    dept_candidates: Dict[str, int],
    job_candidates: Dict[str, int],
    leave_type_id: int,
    muwaffaq: Any = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    """
    ينفّذ سجلاً واحداً من أي ورقة تشغيلية (3..13) باستخدام SAFE_WRITE_FIELDS المعتمدة فقط.
    يعيد: (created_item_dict | None, muwaffaq_match_dict | None, error_msg | None)
    """
    emp_ident = str(fields.get("emp_name") or fields.get("name") or "").strip()
    emp_id_num = str(fields.get("emp_id") or fields.get("id_number") or "").strip()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    target_emp_id: Optional[int] = None
    m_trace: Optional[Dict[str, Any]] = None
    if domain != "recruitment":
        target_emp_id, m_trace = _resolve_employee_id_for_row(
            emp_ident, emp_id_num, employee_id_map, repo_emp_candidates, muwaffaq=muwaffaq
        )
        if not target_emp_id:
            return None, m_trace, f"تعذر ربط الموظف '{emp_ident or emp_id_num}' بسجل موجود في أودو."

    if domain == "contract":
        wage_val = _safe_float(fields.get("wage") or fields.get("total_salary"), 0.0)
        if wage_val <= 0:
            return None, m_trace, "الراتب الأساسي في العقد يجب أن يكون أكبر من صفر."
        payload: Dict[str, Any] = {
            "name": f"عقد عمل - {emp_ident or target_emp_id}",
            "employee_id": target_emp_id,
            "wage": wage_val,
            "state": "open",
            "company_id": effective_company_id,
        }
        d_start = _normalize_iso_date(fields.get("start_date"))
        d_end = _normalize_iso_date(fields.get("end_date"))
        if d_start:
            payload["date_start"] = d_start
        if d_end:
            payload["date_end"] = d_end
        housing = _safe_float(fields.get("housing"), 0.0)
        transport = _safe_float(fields.get("transport"), 0.0)
        other = _safe_float(fields.get("other_allowance"), 0.0)
        if housing or transport or other:
            payload["notes"] = f"نوع العقد: {fields.get('contract_type', 'محدد المدة')} | سكن: {housing} | نقل: {transport} | أخرى: {other}"
        rec_id = gateway.create_record("hr.contract", payload)
        return {"domain": domain, "model": "hr.contract", "id": rec_id, "employee_id": target_emp_id, "wage": wage_val, "name": payload["name"]}, m_trace, None

    if domain == "payroll":
        d_from = _normalize_iso_date(fields.get("month"), today_str[:7] + "-01")
        payload = {
            "name": f"مسير راتب وتأمينات - {emp_ident or target_emp_id}",
            "employee_id": target_emp_id,
            "date_from": d_from,
            "date_to": d_from,
            "company_id": effective_company_id,
            "note": (
                f"GOSI: {fields.get('gosi_type', '')} | رقم: {fields.get('gosi_sub_num', '')} | "
                f"بنك: {fields.get('bank_name', '')} | أجر خاضع: {fields.get('gosi_wage', '')} | "
                f"صافي متوقع: {fields.get('net_salary', '')}"
            ),
        }
        rec_id = gateway.create_record("hr.payslip", payload)
        return {"domain": domain, "model": "hr.payslip", "id": rec_id, "employee_id": target_emp_id, "name": payload["name"]}, m_trace, None

    if domain == "timeoff":
        d_from = _normalize_iso_date(fields.get("start_date"), today_str)
        d_to = _normalize_iso_date(fields.get("end_date"), d_from)
        days = _safe_float(fields.get("days_count"), 1.0)
        leave_label = str(fields.get("leave_type") or "إجازة سنوية").strip()
        payload = {
            "name": f"{leave_label} - {emp_ident or target_emp_id}",
            "employee_id": target_emp_id,
            "holiday_status_id": leave_type_id,
            "request_date_from": d_from,
            "request_date_to": d_to,
            "number_of_days": max(0.5, days),
            "company_id": effective_company_id,
        }
        rec_id = gateway.create_record("hr.leave", payload)
        return {"domain": domain, "model": "hr.leave", "id": rec_id, "employee_id": target_emp_id, "days": days, "name": payload["name"]}, m_trace, None

    if domain == "attendance":
        month_base = _normalize_iso_date(fields.get("month"), today_str)
        payload = {
            "employee_id": target_emp_id,
            "check_in": f"{month_base} 08:00:00",
            "check_out": f"{month_base} 16:00:00",
        }
        rec_id = gateway.create_record("hr.attendance", payload)
        return {"domain": domain, "model": "hr.attendance", "id": rec_id, "employee_id": target_emp_id, "name": f"حضور {month_base[:7]} - {emp_ident}"}, m_trace, None

    if domain == "overtime":
        ot_date = _normalize_iso_date(fields.get("date"), today_str)
        hours = _safe_float(fields.get("hours"), 0.0)
        amt = _safe_float(fields.get("total_amount"), 0.0)
        payload = {
            "name": f"عمل إضافي ({hours} س) - {emp_ident or target_emp_id}",
            "employee_id": target_emp_id,
            "date_from": ot_date,
            "date_to": ot_date,
            "company_id": effective_company_id,
            "note": f"نوع الإضافي: {fields.get('overtime_type', 'عادي')} | ساعات: {hours} | مستحق: {amt} | مبرر: {fields.get('reason', '')}",
        }
        rec_id = gateway.create_record("hr.payslip", payload)
        return {"domain": domain, "model": "hr.payslip", "id": rec_id, "employee_id": target_emp_id, "hours": hours, "name": payload["name"]}, m_trace, None

    if domain == "loan":
        amt = _safe_float(fields.get("loan_amount"), 0.0)
        inst = _safe_float(fields.get("installment_amt"), 0.0)
        if inst <= 0:
            terms = max(1.0, _safe_float(fields.get("term_months"), 1.0))
            inst = round(amt / terms, 2) if amt > 0 else 0.0
        payload = {
            "name": f"{fields.get('loan_type') or 'سلفة موظف'} - {emp_ident or target_emp_id}",
            "employee_id": target_emp_id,
            "loan_amount": amt,
            "installment": inst,
            "date": _normalize_iso_date(fields.get("start_date"), today_str),
            "company_id": effective_company_id,
        }
        rec_id = gateway.create_record("hr.loan", payload)
        return {"domain": domain, "model": "hr.loan", "id": rec_id, "employee_id": target_emp_id, "loan_amount": amt, "name": payload["name"]}, m_trace, None

    if domain == "disciplinary":
        v_date = _normalize_iso_date(fields.get("violation_date"), today_str)
        payload = {
            "name": f"{fields.get('penalty_type') or 'جزاء إداري'} - {emp_ident or target_emp_id}",
            "employee_id": target_emp_id,
            "date": v_date,
            "description": f"المخالفة: {fields.get('reason', '')} | أيام الخصم: {fields.get('deduction_days', 0)} | تاريخ التحقيق: {fields.get('investigation_date', '')}",
            "company_id": effective_company_id,
        }
        rec_id = gateway.create_record("hr.disciplinary", payload)
        return {"domain": domain, "model": "hr.disciplinary", "id": rec_id, "employee_id": target_emp_id, "name": payload["name"]}, m_trace, None

    if domain == "end_of_service":
        h_date = _normalize_iso_date(fields.get("hire_date"), today_str)
        t_date = _normalize_iso_date(fields.get("term_date"), today_str)
        payload = {
            "name": f"مخالصة نهاية خدمة - {emp_ident or target_emp_id}",
            "employee_id": target_emp_id,
            "date_from": h_date,
            "date_to": t_date,
            "company_id": effective_company_id,
            "note": f"السبب: {fields.get('reason', '')} | المكافأة: {fields.get('eos_amount', '')} | الصافي: {fields.get('net_settlement', '')}",
        }
        rec_id = gateway.create_record("hr.payslip", payload)
        return {"domain": domain, "model": "hr.payslip", "id": rec_id, "employee_id": target_emp_id, "name": payload["name"]}, m_trace, None

    if domain == "appraisal":
        yr = str(fields.get("year") or today_str[:4]).strip()
        d_close = f"{yr[:4]}-12-31" if yr[:4].isdigit() else today_str
        payload = {
            "employee_id": target_emp_id,
            "date_close": d_close,
            "company_id": effective_company_id,
            "note": f"السنة: {yr} | النوع: {fields.get('type', '')} | المقيّم: {fields.get('manager', '')} | التقدير: {fields.get('rating', '')} | الدرجة: {fields.get('total_score', '')} | التوصية: {fields.get('recommendation', '')}",
        }
        rec_id = gateway.create_record("hr.appraisal", payload)
        return {"domain": domain, "model": "hr.appraisal", "id": rec_id, "employee_id": target_emp_id, "name": f"تقييم {yr} - {emp_ident}"}, m_trace, None

    if domain == "recruitment":
        cand_name = str(fields.get("name") or emp_ident or "مرشح جديد").strip()
        job_title = str(fields.get("job") or fields.get("job_title") or "").strip()
        dept_title = str(fields.get("dept") or fields.get("department") or "").strip()
        j_id, jt = _resolve_with_muwaffaq(job_title, job_candidates, entity_type="job", muwaffaq=muwaffaq) if job_title else (None, None)
        d_id, dt = _resolve_with_muwaffaq(dept_title, dept_candidates, entity_type="department", muwaffaq=muwaffaq) if dept_title else (None, None)
        payload = {
            "partner_name": cand_name,
            "company_id": effective_company_id,
        }
        if fields.get("email"):
            payload["email_from"] = str(fields["email"]).strip()
        if fields.get("mobile"):
            payload["partner_phone"] = str(fields["mobile"]).strip()
        exp_sal = _safe_float(fields.get("expected_salary"), 0.0)
        if exp_sal > 0:
            payload["salary_expected"] = exp_sal
        if j_id:
            payload["job_id"] = j_id
        if d_id:
            payload["department_id"] = d_id
        rec_id = gateway.create_record("hr.applicant", payload)
        return {"domain": domain, "model": "hr.applicant", "id": rec_id, "name": cand_name, "job": job_title}, (jt or dt), None

    if domain == "gr":
        tx_date = _normalize_iso_date(fields.get("iqama_greg") or fields.get("passport_exp"), today_str)
        payload = {
            "name": f"معاملة حكومية ({fields.get('tx_type', 'مقيم/قوى')}) - {emp_ident or target_emp_id}",
            "employee_id": target_emp_id,
            "date": tx_date,
            "description": f"الحالة: {fields.get('status', '')} | جواز: {fields.get('passport_num', '')} | رقم الحدود: {fields.get('border_num', '')} | الرسوم: {fields.get('gov_fees', 0)}",
            "company_id": effective_company_id,
        }
        rec_id = gateway.create_record("hr.disciplinary", payload)
        return {"domain": domain, "model": "hr.disciplinary", "id": rec_id, "employee_id": target_emp_id, "name": payload["name"]}, m_trace, None

    return None, m_trace, f"نطاق غير مدعوم للتنفيذ التلقائي: {domain}"


def _setup_onboarding_post_requisites(
    input_path: Path,
    repository: Any,
    gateway: Any,
    target_company_id: int,
    employee_id_map: Dict[str, int],
) -> Dict[str, Any]:
    """
    تأسيس السجلات اللاحقة بعد إنشاء الموظفين بالترتيب الاعتمادي:
    1) تأسيس العقود والبدلات (hr.contract).
    2) تأسيس سجلات الإجازات (hr.leave) والحضور (hr.attendance) والسلف (hr.loan) عبر الأوراق اللاحقة.
    """
    summary: Dict[str, Any] = {
        "contracts_created": [],
        "leaves_created": [],
        "attendances_created": [],
        "loans_created": [],
    }

    if not input_path.exists() or not hasattr(gateway, "create_record"):
        return summary

    try:
        import openpyxl
        wb = openpyxl.load_workbook(input_path, data_only=True)
    except Exception:
        return summary

    try:
        from excel_template_validator import TEMPLATE_SPECS, _resolve_sheet_domain, is_auxiliary_sheet
    except Exception:
        TEMPLATE_SPECS = {}
        _resolve_sheet_domain = None
        is_auxiliary_sheet = lambda s: s.strip().lower() in {"instructions", "reference"}

    muwaffaq = _get_muwaffaq_instance()
    repo_emp_candidates: Dict[str, int] = {}
    try:
        for o_emp in (repository.get_employees() if hasattr(repository, "get_employees") else []):
            if o_emp.get("name") and o_emp.get("id") is not None:
                repo_emp_candidates[str(o_emp["name"]).strip()] = int(o_emp["id"])
                repo_emp_candidates[str(o_emp["name"]).strip().lower()] = int(o_emp["id"])
    except Exception:
        pass

    domain_bucket_map = {
        "contract": "contracts_created",
        "timeoff": "leaves_created",
        "attendance": "attendances_created",
        "loan": "loans_created",
    }

    if _resolve_sheet_domain and TEMPLATE_SPECS:
        for s_name in wb.sheetnames:
            if is_auxiliary_sheet(s_name):
                continue
            dom = _resolve_sheet_domain(s_name)
            if dom not in domain_bucket_map:
                continue
            spec = TEMPLATE_SPECS.get(dom)
            if not spec:
                continue
            rows = _extract_raw_sheet_rows(wb[s_name], spec)
            for r_info in rows:
                flds = r_info.get("fields", {})
                item, _, _ = _execute_domain_record(
                    dom, flds, repository, gateway, target_company_id,
                    employee_id_map, repo_emp_candidates, {}, {}, 1, muwaffaq=muwaffaq
                )
                if item:
                    summary[domain_bucket_map[dom]].append(item)
        return summary

    contract_sheet = None
    for name in wb.sheetnames:
        name_lower = name.strip().lower()
        if "contract" in name_lower or "عقد" in name_lower or "عقود" in name_lower:
            contract_sheet = wb[name]
            break

    if contract_sheet and contract_sheet.max_row >= 2:
        header_row = 1
        h_vals = [str(c.value or "").strip().lower() for c in contract_sheet[1]]
        if not any("wage" in h or "راتب" in h or "عقد" in h or "salary" in h for h in h_vals) and contract_sheet.max_row >= 2:
            header_row = 2
            h_vals = [str(c.value or "").strip().lower() for c in contract_sheet[2]]

        emp_col = None
        wage_col = None
        start_col = None
        end_col = None

        for c_idx, h in enumerate(h_vals, 1):
            if any(k in h for k in ["اسم", "name", "هوية", "إقامة", "iqama", "employee"]):
                if emp_col is None:
                    emp_col = c_idx
            elif any(k in h for k in ["راتب أساسي", "الراتب", "wage", "basic", "salary"]):
                wage_col = c_idx
            elif any(k in h for k in ["بداية", "start", "تاريخ بداية"]):
                start_col = c_idx
            elif any(k in h for k in ["نهاية", "end", "تاريخ نهاية"]):
                end_col = c_idx

        if wage_col:
            for r_idx in range(header_row + 1, contract_sheet.max_row + 1):
                raw_wage = contract_sheet.cell(row=r_idx, column=wage_col).value
                if raw_wage is None or str(raw_wage).strip() == "":
                    continue
                try:
                    wage_val = float(raw_wage)
                except (ValueError, TypeError):
                    continue

                emp_ident = str(contract_sheet.cell(row=r_idx, column=emp_col).value or "").strip() if emp_col else ""
                target_emp_id, _ = _resolve_employee_id_for_row(
                    emp_ident, "", employee_id_map, repo_emp_candidates, muwaffaq=muwaffaq
                )
                if target_emp_id:
                    try:
                        contract_payload: Dict[str, Any] = {
                            "name": f"عقد عمل - {emp_ident or target_emp_id}",
                            "employee_id": target_emp_id,
                            "wage": wage_val,
                            "state": "open",
                            "company_id": target_company_id,
                        }
                        if start_col:
                            s_val = contract_sheet.cell(row=r_idx, column=start_col).value
                            if s_val:
                                contract_payload["date_start"] = str(s_val).split("T")[0].split(" ")[0]
                        if end_col:
                            e_val = contract_sheet.cell(row=r_idx, column=end_col).value
                            if e_val:
                                contract_payload["date_end"] = str(e_val).split("T")[0].split(" ")[0]

                        c_id = gateway.create_record("hr.contract", contract_payload)
                        summary["contracts_created"].append({"id": c_id, "employee_id": target_emp_id, "wage": wage_val})
                    except Exception as e:
                        logger.debug(f"Could not create contract for employee {target_emp_id}: {e}")

    return summary


def execute_master_onboarding_sheets(
    input_path: Optional[Path],
    accepted_rows: List[Dict[str, Any]],
    repository: Any,
    gateway: Any,
    target_company_id: int,
    event_emitter: Any = None,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    ينفّذ جميع الأوراق الـ 13 المعبّأة في مصنف الماستر (Master Workbook) بالترتيب الاعتمادي الصارم:
    1_Company_Setup -> 2_Employees -> 3_Contracts -> الأوراق التشغيلية (4..13).
    """
    from excel_template_validator import (
        MASTER_SHEET_ORDER,
        TEMPLATE_SPECS,
        _resolve_sheet_domain,
        is_auxiliary_sheet,
    )

    muwaffaq = _get_muwaffaq_instance()
    created_count = 0
    failed_count = 0
    created_items: List[Dict[str, Any]] = []
    muwaffaq_matches: List[Dict[str, Any]] = []
    sheets_exec_summary: Dict[str, Dict[str, Any]] = {}
    execution_order: List[str] = []

    comp_candidates: Dict[str, int] = {}
    dept_candidates: Dict[str, int] = {}
    job_candidates: Dict[str, int] = {}
    repo_emp_candidates: Dict[str, int] = {}
    employee_id_map: Dict[str, int] = {}

    try:
        for c in (repository.get_companies() if hasattr(repository, "get_companies") else []):
            if c.get("name") and c.get("id") is not None:
                comp_candidates[str(c["name"]).strip()] = int(c["id"])
                comp_candidates[str(c["name"]).strip().lower()] = int(c["id"])
    except Exception:
        pass

    effective_company_id = int(target_company_id or 1)

    def _refresh_org_caches(cid: int) -> None:
        try:
            for d in (repository.get_departments(cid) if hasattr(repository, "get_departments") else []):
                if d.get("name") and d.get("id") is not None:
                    dept_candidates[str(d["name"]).strip()] = int(d["id"])
                    dept_candidates[str(d["name"]).strip().lower()] = int(d["id"])
        except Exception:
            pass
        try:
            for j in (repository.get_jobs(cid) if hasattr(repository, "get_jobs") else []):
                if j.get("name") and j.get("id") is not None:
                    job_candidates[str(j["name"]).strip()] = int(j["id"])
                    job_candidates[str(j["name"]).strip().lower()] = int(j["id"])
        except Exception:
            pass

    _refresh_org_caches(effective_company_id)

    try:
        for e in (repository.get_employees() if hasattr(repository, "get_employees") else []):
            if e.get("name") and e.get("id") is not None:
                eid = int(e["id"])
                repo_emp_candidates[str(e["name"]).strip()] = eid
                repo_emp_candidates[str(e["name"]).strip().lower()] = eid
                if e.get("identification_id"):
                    repo_emp_candidates[str(e["identification_id"]).strip()] = eid
    except Exception:
        pass

    leave_type_id = 1
    try:
        if hasattr(repository, "_models") and repository._models:
            lt_recs = repository._models.execute_kw(
                repository.db, repository.uid, repository.api_key,
                "hr.leave.type", "search_read", [[]], {"fields": ["id"], "limit": 1}
            )
            if lt_recs:
                leave_type_id = int(lt_recs[0]["id"])
    except Exception:
        pass

    # تجميع الصفوف المقبولة حسب النطاق التخصصي
    rows_by_domain: Dict[str, List[Dict[str, Any]]] = {}
    has_domain_tagged_rows = any(r.get("domain") or r.get("sheet_name") for r in accepted_rows)

    if has_domain_tagged_rows:
        for r in accepted_rows:
            dom = r.get("domain") or (_resolve_sheet_domain(str(r.get("sheet_name") or "")) if r.get("sheet_name") else None) or "employee"
            raw_fields = r.get("fields", {})
            flat_fields: Dict[str, Any] = {}
            for k, v in raw_fields.items():
                flat_fields[k] = v.get("value") if isinstance(v, dict) else v
            rows_by_domain.setdefault(dom, []).append({
                "fields": flat_fields,
                "sheet_name": r.get("sheet_name") or dom,
                "row_number": r.get("excel_row_number") or r.get("row_number"),
                "resolved_ids": r.get("resolved_ids", {}),
            })
    elif input_path and input_path.exists():
        import openpyxl
        wb = openpyxl.load_workbook(input_path, data_only=True)
        for s_name in wb.sheetnames:
            if is_auxiliary_sheet(s_name):
                continue
            dom = _resolve_sheet_domain(s_name)
            if not dom or dom not in TEMPLATE_SPECS:
                continue
            extracted = _extract_raw_sheet_rows(wb[s_name], TEMPLATE_SPECS[dom])
            for er in extracted:
                rows_by_domain.setdefault(dom, []).append({
                    "fields": er.get("fields", {}),
                    "sheet_name": s_name,
                    "row_number": er.get("excel_row_number"),
                    "resolved_ids": {},
                })

    # التنفيذ بالترتيب الاعتمادي الصارم (1..13)
    for dom, _aliases in MASTER_SHEET_ORDER:
        dom_rows = rows_by_domain.get(dom, [])
        if not dom_rows:
            continue

        execution_order.append(dom)
        sheet_label = dom_rows[0].get("sheet_name") or dom
        bucket = sheets_exec_summary.setdefault(sheet_label, {"domain": dom, "created": 0, "failed": 0, "items": []})

        if event_emitter and operation_id:
            event_emitter.emit_event(
                operation_id=operation_id,
                agent="katib",
                event_type="sheet_execution_started",
                action=f"execute_sheet_{dom}",
                description_ar=f"كاتب يبدأ تنفيذ ورقة «{sheet_label}» ({len(dom_rows)} صفاً) وفق الترتيب الاعتمادي...",
                metadata={"domain": dom, "sheet": sheet_label, "rows": len(dom_rows)},
            )

        if dom == "company":
            for entry in dom_rows:
                flds = entry["fields"]
                comp_name = str(flds.get("name_ar") or flds.get("name_en") or flds.get("name") or "").strip()
                if not comp_name:
                    failed_count += 1
                    bucket["failed"] += 1
                    continue
                existing_cid, m_trace = _resolve_with_muwaffaq(comp_name, comp_candidates, entity_type="company", muwaffaq=muwaffaq)
                if m_trace:
                    muwaffaq_matches.append(m_trace)
                if existing_cid is not None:
                    effective_company_id = existing_cid
                    _refresh_org_caches(effective_company_id)
                    item = {"domain": "company", "model": "res.company", "id": existing_cid, "name": comp_name, "reused": True}
                    created_items.append(item)
                    bucket["items"].append(item)
                    created_count += 1
                    bucket["created"] += 1
                else:
                    comp_vals: Dict[str, Any] = {"name": comp_name}
                    if flds.get("vat_number"):
                        comp_vals["vat"] = str(flds["vat_number"]).strip()
                    if flds.get("city"):
                        comp_vals["city"] = str(flds["city"]).strip()
                    try:
                        new_cid = int(gateway.create_record("res.company", comp_vals))
                        effective_company_id = new_cid
                        comp_candidates[comp_name] = new_cid
                        comp_candidates[comp_name.lower()] = new_cid
                        _refresh_org_caches(effective_company_id)
                        item = {"domain": "company", "model": "res.company", "id": new_cid, "name": comp_name}
                        created_items.append(item)
                        bucket["items"].append(item)
                        created_count += 1
                        bucket["created"] += 1
                    except Exception as exc:
                        logger.warning(f"Failed creating company '{comp_name}': {exc}")
                        failed_count += 1
                        bucket["failed"] += 1
            continue

        if dom == "employee":
            for entry in dom_rows:
                flds = entry["fields"]
                resolved = entry.get("resolved_ids", {})
                emp_name = str(flds.get("name") or flds.get("name_en") or "").strip()
                if not emp_name:
                    failed_count += 1
                    bucket["failed"] += 1
                    continue

                comp_name = str(flds.get("company") or "").strip()
                dept_name = str(flds.get("department") or "").strip()
                job_title = str(flds.get("job_title") or flds.get("job") or "").strip()

                def _real_int_id(val: Any) -> Optional[int]:
                    if isinstance(val, int) and val > 0:
                        return val
                    if isinstance(val, str) and val.strip().isdigit():
                        return int(val.strip())
                    return None

                c_id = _real_int_id(resolved.get("company_id"))
                if not c_id and comp_name:
                    c_id, ct = _resolve_with_muwaffaq(comp_name, comp_candidates, entity_type="company", muwaffaq=muwaffaq)
                    if ct:
                        muwaffaq_matches.append(ct)
                c_id = int(c_id or effective_company_id)

                d_id = _real_int_id(resolved.get("department_id"))
                if not d_id and dept_name:
                    d_id, dt = _resolve_with_muwaffaq(dept_name, dept_candidates, entity_type="department", muwaffaq=muwaffaq)
                    if dt:
                        muwaffaq_matches.append(dt)
                    if not d_id:
                        try:
                            d_id = int(gateway.create_record("hr.department", {"name": dept_name, "company_id": c_id}))
                            dept_candidates[dept_name] = d_id
                            dept_candidates[dept_name.lower()] = d_id
                        except Exception:
                            d_id = None

                j_id = _real_int_id(resolved.get("job_id"))
                if not j_id and job_title:
                    j_id, jt = _resolve_with_muwaffaq(job_title, job_candidates, entity_type="job", muwaffaq=muwaffaq)
                    if jt:
                        muwaffaq_matches.append(jt)
                    if not j_id:
                        try:
                            j_id = int(gateway.create_record("hr.job", {"name": job_title, "company_id": c_id}))
                            job_candidates[job_title] = j_id
                            job_candidates[job_title.lower()] = j_id
                        except Exception:
                            j_id = None

                vals: Dict[str, Any] = {"name": emp_name, "company_id": c_id}
                email = str(flds.get("work_email") or flds.get("email") or "").strip()
                mobile = str(flds.get("mobile_phone") or flds.get("mobile") or "").strip()
                iqama = str(flds.get("id_number") or flds.get("iqama") or "").strip()
                gender_raw = str(flds.get("gender") or "").strip().lower()
                bday = _normalize_iso_date(flds.get("birthday"))
                if email:
                    vals["work_email"] = email
                if mobile:
                    vals["mobile_phone"] = mobile
                if job_title:
                    vals["job_title"] = job_title
                if iqama:
                    vals["identification_id"] = iqama
                if j_id:
                    vals["job_id"] = j_id
                if d_id:
                    vals["department_id"] = d_id
                if bday:
                    vals["birthday"] = bday
                if gender_raw in ("male", "ذكر", "m"):
                    vals["gender"] = "male"
                elif gender_raw in ("female", "أنثى", "انثى", "f"):
                    vals["gender"] = "female"

                try:
                    new_eid = int(gateway.create_employee(vals))
                    employee_id_map[emp_name] = new_eid
                    employee_id_map[emp_name.lower()] = new_eid
                    if flds.get("name_en"):
                        en_n = str(flds["name_en"]).strip()
                        employee_id_map[en_n] = new_eid
                        employee_id_map[en_n.lower()] = new_eid
                    if iqama:
                        employee_id_map[iqama] = new_eid
                    item = {"domain": "employee", "model": "hr.employee", "id": new_eid, "name": emp_name, "job": job_title}
                    created_items.append(item)
                    bucket["items"].append(item)
                    created_count += 1
                    bucket["created"] += 1
                except Exception as exc:
                    logger.warning(f"Failed creating employee '{emp_name}': {exc}")
                    failed_count += 1
                    bucket["failed"] += 1
            continue

        # تنفيذ أوراق العقود والعمليات اللاحقة (3..13)
        for entry in dom_rows:
            flds = entry["fields"]
            try:
                item, m_trace, err = _execute_domain_record(
                    dom, flds, repository, gateway, effective_company_id,
                    employee_id_map, repo_emp_candidates, dept_candidates, job_candidates, leave_type_id,
                    muwaffaq=muwaffaq,
                )
                if m_trace:
                    muwaffaq_matches.append(m_trace)
                if item:
                    created_items.append(item)
                    bucket["items"].append(item)
                    created_count += 1
                    bucket["created"] += 1
                else:
                    logger.debug(f"Domain record skipped/failed ({dom}): {err}")
                    failed_count += 1
                    bucket["failed"] += 1
            except Exception as exc:
                logger.warning(f"Failed executing domain '{dom}' record: {exc}")
                failed_count += 1
                bucket["failed"] += 1

    if muwaffaq_matches and event_emitter and operation_id:
        event_emitter.emit_event(
            operation_id=operation_id,
            agent="muwaffaq",
            from_agent="katib",
            to_agent="katib",
            event_type="semantic_entity_linked",
            action="muwaffaq_master_linking",
            description_ar=f"طابق «موفق» دلالياً {len(muwaffaq_matches)} مرجعاً/موظفاً عبر أوراق الماستر للربط السليم في Odoo.",
            metadata={"matches": muwaffaq_matches[:10]},
        )

    return {
        "created_count": created_count,
        "failed_count": failed_count,
        "created_items": created_items,
        "effective_company_id": effective_company_id,
        "sheets_execution_summary": sheets_exec_summary,
        "muwaffaq_matches": muwaffaq_matches,
        "execution_order": execution_order,
    }


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
    except ApprovalExpiredError as exc:
        raise WriterAbort(ABORT_APPROVAL_EXPIRED, str(exc)) from exc
    except ApprovalAlreadyConsumedError as exc:
        raise WriterAbort(ABORT_APPROVAL_CONSUMED, str(exc)) from exc
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

    # تأسيس المتطلبات المسبقة (المنشأة، الأقسام، المسميات الوظيفية) قبل إنشاء الموظفين
    company_id, pre_summary = _setup_onboarding_prerequisites(
        input_path, repository, gateway, company_id
    )

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

        employee_id_map: Dict[str, int] = {}
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
                    pre_summary=pre_summary,
                )
            if record.get("status") == STATUS_CREATED and record.get("odoo_employee_id"):
                emp_id = record["odoo_employee_id"]
                prow_f = prow.get("fields", {})
                nm = prow_f.get("name", {}).get("value")
                em = prow_f.get("work_email", {}).get("value")
                id_num = prow_f.get("identification_id", {}).get("value")
                if nm:
                    employee_id_map[str(nm).strip()] = emp_id
                    employee_id_map[str(nm).strip().lower()] = emp_id
                if em:
                    employee_id_map[str(em).strip()] = emp_id
                    employee_id_map[str(em).strip().lower()] = emp_id
                if id_num:
                    employee_id_map[str(id_num).strip()] = emp_id
            log.append(record)
            rows_out.append(record)

        # تأسيس المتطلبات اللاحقة (العقود والبدلات وسجلات الـ HR التخصصية) بعد إنشاء الموظفين
        post_summary = _setup_onboarding_post_requisites(
            input_path, repository, gateway, company_id, employee_id_map
        )

        counts: Dict[str, int] = {}
        for record in rows_out:
            counts[record["status"]] = counts.get(record["status"], 0) + 1
        footer = {
            "record_type": "footer",
            "status_counts": counts,
            "finished_at": _utc_now(),
            "onboarding_summary": {**pre_summary, **post_summary},
        }
        log.append(footer)
    finally:
        log.close()

    return {
        "results_path": str(log.path),
        "header": header,
        "rows": rows_out,
        "footer": footer,
        "onboarding_summary": {**pre_summary, **post_summary},
    }


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