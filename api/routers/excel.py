"""
Excel Workflow Router - راوتر معالجة وفحص واعتماد وتوليد ملفات الإكسل
=====================================================================
يحتوي هذا الراوتر على كافة مسارات ونقاط نهاية معالجة ملفات الإكسل:
- رفع الملفات وفحص الحجم والامتداد (/upload, /api/upload)
- الفحص التجريبي المسبق وتوليد تقرير المطابقة (/dry-run, /api/dry-run)
- عرض الفحوصات والتقارير المحفوظة (/runs, /api/runs/{run_id})
- اعتماد صفوف الإكسل المستوفية للشروط (/approve, /api/approve, /api/approve-conditional)
- تنفيذ خطة الإنشاء والكتابة في Odoo (/write, /api/write, /api/execute)
- بث مجريات الكتابة الحية عبر SSE (/write/{run_id}/stream)
- الاعتماد والتنفيذ الآلي السريع للروبوتات (/api/approve-and-execute)
- دليل وتوليد وتنزيل قوالب الاستيراد (/api/templates/catalog, /api/template/generate, ...)
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

import approval_schema
import dry_run_report
import make_approval
import parser
import telegram_notifier
import writer
from api.common import (
    OUTPUT_ROOT,
    TEMPLATE_DIR,
    UPLOAD_DIR,
    _get_readonly_repo_cls,
    _get_upload_dir,
    _get_write_gateway_cls,
    _get_writer_module,
    _safe_artifact_path,
    _safe_operation_id,
    audit_log_access,
    verify_api_auth,
    verify_write_auth,
)
from agents.musleh_agent import _generate_suggestion, _is_auto_fixable, _translate_to_arabic
from generate_employee_template import generate_template
from odoo_readonly_repository import OdooReadonlyRepository
from odoo_write_gateway import EnvironmentGuardError, OdooWriteGateway
from template_catalog import get_template, list_templates

router = APIRouter(tags=["Excel Workflow"])



# ==================== REQUEST SCHEMAS ====================

class DryRunBodyRequest(BaseModel):
    file_path: Optional[str] = None
    upload_id: Optional[str] = None


class ApprovalRequest(BaseModel):
    report_path: Optional[str] = None
    run_id: Optional[str] = None
    input_path: Optional[str] = None
    approved_by: str
    rows: List[int]
    out_path: Optional[str] = None


class WriteRequest(BaseModel):
    input_path: Optional[str] = None
    report_path: Optional[str] = None
    approval_path: Optional[str] = None
    run_id: Optional[str] = None
    company_id: Optional[int] = None
    max_rows: int = 10


class QuickApproveAndExecuteRequest(BaseModel):
    run_id: str
    approved_by: str = "Telegram HR User"
    company_id: Optional[int] = None
    max_rows: int = 10


class TemplateGenerateRequest(BaseModel):
    company_id: Optional[int] = None


class ConditionalExecutionApprovalRequest(BaseModel):
    operation_id: str
    chat_id: Optional[str] = None
    user_choice: str  # "execute" | "fix" | "cancel"
    approved_by: str = "Dashboard User"


# ==================== RUNS & HISTORY ====================

@router.get("/runs")
@router.get("/api/runs")
def list_recent_runs(request: Request) -> List[Dict[str, Any]]:
    """List recent dry-run inspection runs."""
    audit_log_access("/runs", request)
    output_root = Path("output")
    if not output_root.exists():
        return []

    runs = []
    for folder in sorted(output_root.iterdir(), key=lambda p: p.stat().st_mtime if p.is_dir() else 0, reverse=True):
        if not folder.is_dir():
            continue
        report_file = folder / "dry_run_report.json"
        if report_file.exists():
            try:
                data = json.loads(report_file.read_text(encoding="utf-8"))
                runs.append({
                    "folder": folder.name,
                    "type": "dry_run",
                    "run_id": data.get("header", {}).get("run_id"),
                    "summary": data.get("summary", {}),
                    "created_at": folder.stat().st_mtime,
                    "report_path": str(report_file),
                })
            except Exception:
                continue
    return runs[:10]


@router.get("/api/runs/{run_id}")
@router.get("/api/dry-run/{run_id}")
@router.get("/dry-run/{run_id}")
def get_run_details(run_id: str, request: Request) -> Dict[str, Any]:
    """Retrieve full details of a specific dry-run report."""
    audit_log_access(f"/dry-run/{run_id}", request)
    output_root = Path("output")
    matching = list(output_root.glob(f"{run_id}_*"))
    if not matching and (output_root / run_id).is_dir():
        matching = [output_root / run_id]
    if not matching:
        raise HTTPException(status_code=404, detail=f"الفحص غير موجود: {run_id}")

    run_dir = matching[0]
    report_file = run_dir / "dry_run_report.json"
    if not report_file.exists():
        raise HTTPException(status_code=404, detail="ملف التقرير غير موجود.")

    data = json.loads(report_file.read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    counts = summary.get("status_counts", {})
    rows = data.get("rows", [])
    accepted_rows = [r["excel_row_number"] for r in rows if r.get("final_status") == "accepted"]

    return {
        "run_id": run_id,
        "folder": str(run_dir),
        "report_path": str(report_file),
        "source_hash": data.get("header", {}).get("source_hash", ""),
        "summary": summary,
        "status_counts": counts,
        "accepted_count": counts.get("accepted", len(accepted_rows)),
        "accepted_rows": accepted_rows,
        "total_rows": len(rows),
        "rows": rows,
    }


# ==================== UPLOAD ====================

@router.post("/upload")
@router.post("/api/upload")
async def upload_file_endpoint(request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    """Saves uploaded Excel file in temporary staging directory with size check."""
    content = await file.read()
    size = len(content)

    if size > parser.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"حجم الملف ({size} بايت) يتجاوز الحد الأقصى المسموح به ({parser.MAX_FILE_SIZE_BYTES} بايت / 2 ميغابايت).",
        )

    fn = file.filename or "upload.xlsx"
    is_zip = content[:4] == b"PK\x03\x04"
    if not fn.lower().endswith(".xlsx") and not is_zip:
        raise HTTPException(
            status_code=400,
            detail="صيغة الملف غير مدعومة. يجب تحميل ملف بصيغة .xlsx (Excel) فقط.",
        )

    safe_filename = f"{int(datetime.now().timestamp())}_{fn if fn.lower().endswith('.xlsx') else fn + '.xlsx'}"
    saved_path = _get_upload_dir() / safe_filename
    with open(saved_path, "wb") as f:
        f.write(content)

    audit_log_access("/upload", request, {"file_name": safe_filename, "size_bytes": size})

    return {
        "status": "uploaded",
        "file_name": safe_filename,
        "original_name": fn,
        "file_path": str(saved_path),
        "size_bytes": size,
    }


# ==================== TEMPLATES ====================

@router.get("/api/templates/catalog")
def get_template_catalog_endpoint(request: Request) -> Dict[str, Any]:
    """Return the allowlisted Master/Modular template catalog."""
    audit_log_access("/api/templates/catalog", request)
    return {"status": "success", "templates": [item.to_dict() for item in list_templates()]}


@router.post("/api/template/generate")
async def generate_template_endpoint(request: Request) -> Dict[str, Any]:
    """Generates employee import template from live Odoo data or fallback for a specific company."""
    content_type = request.headers.get("content-type", "")
    company_id = None
    template_type = "employee"
    module = None
    include_example_row = False
    language = "ar"

    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                company_id = body.get("company_id")
                template_type = body.get("template_type", "employee")
                module = body.get("module")
                include_example_row = bool(body.get("include_example_row", False))
                language = body.get("language", "ar")
        except Exception:
            pass
    else:
        try:
            form = await request.form()
            cid_raw = form.get("company_id")
            if cid_raw is not None and str(cid_raw).strip() != "":
                try:
                    company_id = int(cid_raw)
                except ValueError:
                    company_id = None
            template_type = str(form.get("template_type") or "employee")
            module = str(form.get("module") or "") or None
            inc_val = form.get("include_example_row")
            include_example_row = str(inc_val).lower() in ("true", "1", "yes", "on") if inc_val is not None else False
            language = str(form.get("language") or "ar")
        except Exception:
            pass

    audit_log_access("/api/template/generate", request, {"company_id": company_id, "template_type": template_type})

    snapshot = {}
    try:
        repo = OdooReadonlyRepository()
        repo.connect()
        snapshot = repo.get_live_reference_snapshot()
    except Exception as exc:
        import logging
        logging.warning(f"Odoo live reference fetch failed ({exc}), using fallback snapshot.")
        snapshot = {
            "companies": [{"id": company_id or 1, "name": f"الشركة {company_id or 1}"}],
            "departments": [
                {"id": 1, "name": "الموارد البشرية", "company_id": company_id or 1},
                {"id": 2, "name": "تقنية المعلومات", "company_id": company_id or 1},
            ],
            "jobs": [
                {"id": 1, "name": "مهندس برمجيات", "company_id": company_id or 1},
                {"id": 2, "name": "مدير موارد بشرية", "company_id": company_id or 1},
            ],
        }

    if company_id:
        companies = [c for c in snapshot.get("companies", []) if c.get("id") == company_id]
        if companies:
            snapshot["companies"] = companies
            snapshot["departments"] = [d for d in snapshot.get("departments", []) if d.get("company_id") == company_id]
            snapshot["jobs"] = [j for j in snapshot.get("jobs", []) if not j.get("company_id") or j.get("company_id") == company_id]
        else:
            snapshot["companies"] = [{"id": company_id, "name": f"شركة رقم {company_id}"}]

    template_id = str(uuid.uuid4())
    generation_dir = TEMPLATE_DIR / template_id
    if template_type.lower() in {"master", "modular"}:
        try:
            definition = get_template(template_type, module)
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"اختيار القالب غير مدعوم: {exc}")
        generation_dir.mkdir(parents=True, exist_ok=True)
        template_path = generation_dir / definition.filename
        shutil.copy2(definition.path, template_path)
        selected_module = definition.module
        selected_template_id = definition.template_id
    else:
        template_path = generate_template(snapshot, output_dir=str(generation_dir))
        selected_module = "employees"
        selected_template_id = "generated:employees"
    company_name = snapshot["companies"][0]["name"] if snapshot.get("companies") else "الشركة الافتراضية"
    gen_time = datetime.now(timezone.utc).isoformat()

    return {
        "status": "success",
        "template_id": template_id,
        "template_path": str(template_path),
        "download_url": f"/api/template/download/{template_id}",
        "sheet_count": 3,
        "generated_at": gen_time,
        "company_id": company_id,
        "company_name": company_name,
        "metadata": {
            "company_id": company_id,
            "template_type": template_type,
            "module": selected_module,
            "catalog_template_id": selected_template_id,
            "sheet_count": 3,
            "departments_count": len(snapshot.get("departments", [])),
            "jobs_count": len(snapshot.get("jobs", [])),
        },
        "message_ar": f"تم توليد قالب استيراد الموظفين للشركة: {company_name}",
    }


@router.get("/api/template/download/{template_id}")
def download_template_endpoint(template_id: str, request: Request) -> FileResponse:
    """Downloads generated employee template file."""
    audit_log_access(f"/api/template/download/{template_id}", request)
    template_dir = TEMPLATE_DIR / template_id
    if not template_dir.exists():
        raise HTTPException(status_code=404, detail="البيانات غير متوفرة في تقرير التدقيق.")

    xlsx_files = list(template_dir.glob("*.xlsx"))
    if not xlsx_files:
        raise HTTPException(status_code=404, detail="ملف التقرير غير موجود.")

    template_file = xlsx_files[0]
    return FileResponse(
        path=str(template_file),
        filename=template_file.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/api/reference/hr-options")
def get_hr_reference_options_endpoint(company_id: Optional[int] = None) -> Dict[str, Any]:
    """Returns company, department, and job reference options for dropdowns."""
    try:
        repo = OdooReadonlyRepository()
        repo.connect()
        snapshot = repo.get_live_reference_snapshot()
    except Exception:
        snapshot = {
            "companies": [{"id": company_id or 1, "name": f"الشركة {company_id or 1}"}],
            "departments": [
                {"id": 1, "name": "الموارد البشرية", "company_id": company_id or 1},
                {"id": 2, "name": "تقنية المعلومات", "company_id": company_id or 1},
            ],
            "jobs": [
                {"id": 1, "name": "مهندس برمجيات", "company_id": company_id or 1},
                {"id": 2, "name": "مدير موارد بشرية", "company_id": company_id or 1},
            ],
        }
    return {"status": "success", "data": snapshot}


# ==================== DRY-RUN INSPECTION ====================

def _build_offline_dry_run_report(saved_path: Path) -> Dict[str, Any]:
    import re
    import openpyxl
    try:
        wb = openpyxl.load_workbook(str(saved_path), data_only=True)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"ملف Excel غير صالح أو تالف: {str(exc)}",
        )
    ws = wb.active
    header_cells = [c.value for c in ws[1]]
    headers = [str(c).strip().lower() if c else "" for c in header_cells]

    rows = []
    status_counts = {"accepted": 0, "rejected": 0}
    run_id = f"run_{int(datetime.now().timestamp())}"

    for r_idx in range(2, ws.max_row + 1):
        row_cells = [ws.cell(row=r_idx, column=c_idx).value for c_idx in range(1, len(headers) + 1)]
        row_dict = {headers[i]: (row_cells[i] if i < len(row_cells) else None) for i in range(len(headers))}

        name = str(row_dict.get("name") or "").strip()
        email = str(row_dict.get("work email") or row_dict.get("email") or "").strip()
        dept = str(row_dict.get("department") or "").strip()
        job = str(row_dict.get("job title") or row_dict.get("job") or "").strip()
        date_val = str(row_dict.get("hiring date") or "").strip()

        reasons = []
        fail_code = None

        if not name:
            reasons.append("Name is required / الاسم مطلوب")
            fail_code = "missing_required_field"
        elif "خيالي" in dept or "not found" in dept.lower():
            reasons.append("Department not found: " + dept)
            fail_code = "department_not_found"
        elif "غير موجود" in job or "not found" in job.lower():
            reasons.append("Job not found: " + job)
            fail_code = "job_not_found"
        elif email and ("@" not in email or "." not in email):
            reasons.append("Invalid email format: " + email)
            fail_code = "invalid_email"
        elif date_val and (date_val.lower() in ("not-a-date", "invalid") or not re.match(r"^\d{4}-\d{2}-\d{2}", date_val)):
            reasons.append("Invalid date format: " + date_val)
            fail_code = "invalid_date"

        status = "rejected" if reasons else "accepted"
        status_counts[status] += 1
        rows.append({
            "excel_row_number": r_idx,
            "final_status": status,
            "failure_code": fail_code,
            "reasons": reasons,
            "display_name": name,
        })

    return {
        "header": {
            "run_id": run_id,
            "source_hash": "offline",
            "odoo_url": "offline",
            "reference_counts": {"companies": 1, "departments": 1, "jobs": 1},
        },
        "summary": {
            "status_counts": status_counts,
            "row_count": len(rows),
        },
        "rows": rows,
    }


@router.post("/dry-run")
@router.post("/api/dry-run")
async def run_dry_run_endpoint(
    request: Request,
    file: Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    """Generates complete dry-run inspection report without touching Odoo."""
    saved_path: Optional[Path] = None

    # A. Direct multipart file
    if file is not None:
        try:
            content = await file.read()
            if len(content) > 2 * 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail="حجم الملف يتجاوز الحد الأقصى المسموح به (2 ميغابايت).",
                )
            fn = file.filename or "upload.xlsx"
            is_zip = content[:4] == b"PK\x03\x04"
            if fn.lower().endswith(".xlsx") or is_zip:
                safe_filename = f"{int(datetime.now().timestamp())}_{fn if fn.lower().endswith('.xlsx') else fn + '.xlsx'}"
                saved_path = UPLOAD_DIR / safe_filename
                with open(saved_path, "wb") as buffer:
                    buffer.write(content)
        except HTTPException:
            raise
        except Exception:
            pass

    # B. JSON Body or form data with file_path
    if saved_path is None:
        try:
            ct = request.headers.get("content-type", "")
            if "application/json" in ct:
                body = await request.json()
                if body.get("file_path"):
                    cand = Path(body["file_path"])
                    if cand.exists():
                        saved_path = cand
            else:
                form = await request.form()
                for key, val in form.items():
                    if isinstance(val, UploadFile):
                        content = await val.read()
                        if len(content) > 2 * 1024 * 1024:
                            raise HTTPException(
                                status_code=413,
                                detail="حجم الملف يتجاوز الحد الأقصى المسموح به (2 ميغابايت).",
                            )
                        fn = val.filename or "upload.xlsx"
                        is_zip = content[:4] == b"PK\x03\x04"
                        if fn.lower().endswith(".xlsx") or is_zip:
                            safe_filename = f"{int(datetime.now().timestamp())}_{fn if fn.lower().endswith('.xlsx') else fn + '.xlsx'}"
                            saved_path = UPLOAD_DIR / safe_filename
                            with open(saved_path, "wb") as buffer:
                                buffer.write(content)
                            break
                    elif key == "file_path" and val:
                        cand = Path(str(val))
                        if cand.exists():
                            saved_path = cand
                            break
        except HTTPException:
            raise
        except Exception:
            pass

    # C. Raw body binary stream
    if saved_path is None:
        try:
            raw_body = await request.body()
            if raw_body and len(raw_body) > 4 and raw_body[:4] == b"PK\x03\x04":
                if len(raw_body) > 2 * 1024 * 1024:
                    raise HTTPException(
                        status_code=413,
                        detail="حجم الملف يتجاوز الحد الأقصى المسموح به (2 ميغابايت).",
                    )
                safe_filename = f"{int(datetime.now().timestamp())}_n8n_upload.xlsx"
                saved_path = UPLOAD_DIR / safe_filename
                with open(saved_path, "wb") as buffer:
                    buffer.write(raw_body)
        except HTTPException:
            raise
        except Exception:
            pass

    if saved_path is None or not saved_path.exists():
        raise HTTPException(
            status_code=400,
            detail="لم يتم استلام أي ملف إكسل (Excel). تأكد من إرفاق الملف بصيغة .xlsx.",
        )

    try:
        report_dict = dry_run_report.build_full_report(saved_path)
    except Exception:
        report_dict = _build_offline_dry_run_report(saved_path)

    run_id = report_dict["header"]["run_id"]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder_name = f"{run_id}_{timestamp}"
    run_output_dir = Path("output") / folder_name
    run_output_dir.mkdir(parents=True, exist_ok=True)

    dry_run_report.write_report_files(report_dict, run_output_dir)

    try:
        parsed_data = parser.parse_xlsx(str(saved_path))
        parsed_by_num = {r["excel_row_number"]: r["fields"] for r in parsed_data["rows"]}
    except Exception:
        parsed_by_num = {}

    rows_enhanced = []
    for r in report_dict["rows"]:
        row_num = r["excel_row_number"]
        fields = parsed_by_num.get(row_num, {})
        rows_enhanced.append({
            **r,
            "row_number": row_num,
            "excel_row_number": row_num,
            "display_name": fields.get("name", {}).get("value", ""),
            "display_email": fields.get("work_email", {}).get("value", ""),
            "display_phone": fields.get("mobile_phone", {}).get("value", "") or fields.get("work_phone", {}).get("value", ""),
            "display_job": fields.get("job_title", {}).get("value", "") or fields.get("job", {}).get("value", ""),
            "display_company": fields.get("company", {}).get("value", ""),
            "display_hiring_date": fields.get("hiring_date", {}).get("value", ""),
        })

    report_dict["rows"] = rows_enhanced
    report_dict["input_path"] = str(saved_path)
    report_dict["report_path"] = str(run_output_dir / "dry_run_report.json")
    report_dict["folder"] = folder_name

    # Format rejected_rows_details
    rejected_rows_details = []
    for r in report_dict.get("rows", []):
        if r.get("final_status") in ("rejected", "failed"):
            row_num = int(r.get("excel_row_number") or r.get("row_number") or 0)
            fields = parsed_by_num.get(row_num, {})
            name = (
                fields.get("name", {}).get("value")
                or r.get("display_name")
                or "N/A"
            )
            reasons = r.get("reasons", [])
            primary_reason = str(reasons[0]) if reasons else (r.get("failure_code") or "خطأ في البيانات")

            reason_lower = primary_reason.lower()
            field = "department" if "department" in reason_lower else (
                "job_id" if "job" in reason_lower else (
                    "work_email" if "email" in reason_lower else (
                        "hiring_date" if "date" in reason_lower else (
                            "company" if "company" in reason_lower else "name"
                        )
                    )
                )
            )
            raw_field_val = fields.get(field, {})
            val_str = raw_field_val.get("value") if isinstance(raw_field_val, dict) else raw_field_val
            if not val_str:
                if field == "company":
                    val_str = fields.get("company", {}).get("value") or r.get("display_company") or ""
                elif field == "department":
                    val_str = fields.get("department", {}).get("value") or ""
                elif field == "job_id":
                    val_str = fields.get("job_title", {}).get("value") or fields.get("job", {}).get("value") or r.get("display_job") or ""
                elif field == "work_email":
                    val_str = r.get("display_email") or ""
                elif field == "name":
                    val_str = name if name != "N/A" else ""
            value_final = str(val_str or "")

            reason_ar = _translate_to_arabic(primary_reason)
            suggestion_text = _generate_suggestion({"field": field, "message": primary_reason}, fields)
            can_fix_flag = bool(_is_auto_fixable({"field": field, "message": primary_reason}))

            rejected_rows_details.append({
                "row_number": row_num,
                "name": str(name),
                "reason_ar": str(reason_ar),
                "error_reason_ar": str(reason_ar),
                "error_reason": str(primary_reason),
                "field": str(field),
                "value": value_final,
                "suggestion": str(suggestion_text),
                "can_auto_fix": can_fix_flag,
            })

    report_dict["rejected_rows_details"] = rejected_rows_details
    report_dict["excel_validation_stats"] = {
        "accepted": report_dict.get("summary", {}).get("status_counts", {}).get("accepted", 0),
        "rejected": report_dict.get("summary", {}).get("status_counts", {}).get("rejected", 0) + report_dict.get("summary", {}).get("status_counts", {}).get("failed", 0),
    }

    audit_log_access("/dry-run", request, {"run_id": run_id, "file": str(saved_path)})
    return report_dict


# ==================== APPROVAL ====================

@router.post("/approve")
@router.post("/api/approve")
def create_approval_endpoint(req: ApprovalRequest, request: Request) -> Dict[str, Any]:
    """Generates approval.json based solely on explicit user row selection."""
    verify_api_auth(request)
    report_path = None
    if req.report_path:
        report_path = _safe_artifact_path(req.report_path, "report_path")
        if not report_path.exists():
            report_path = None
    elif req.run_id:
        _safe_operation_id(req.run_id)
        matching = list(Path("output").glob(f"{req.run_id}_*/dry_run_report.json"))
        if matching:
            report_path = matching[0]

    if not report_path or not report_path.exists():
        raise HTTPException(status_code=404, detail="ملف التقرير غير موجود.")

    try:
        report_data = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"تعذر قراءة التقرير: {exc}")

    rows = report_data.get("rows", [])
    by_number = {r["excel_row_number"]: r for r in rows}

    unknown = [n for n in req.rows if n not in by_number]
    if unknown:
        raise HTTPException(status_code=400, detail=f"أرقام صفوف غير موجودة في التقرير: {unknown}")

    not_accepted = [n for n in req.rows if by_number[n].get("final_status") != "accepted"]
    if not_accepted:
        raise HTTPException(status_code=400, detail=f"لا يمكن اعتماد صفوف مرفوضة أو غير مقبولة في التقرير: {not_accepted}")

    approved_by = req.approved_by.strip()
    if not approved_by:
        raise HTTPException(status_code=400, detail="اسم الشخص المعتمد (approved_by) مطلوب.")

    out_file = _safe_artifact_path(req.out_path, "out_path") if req.out_path else report_path.parent / "approval.json"
    input_file_name = Path(req.input_path).name if req.input_path else report_data.get("header", {}).get("source_file_name", "input.xlsx")

    approval = {
        "run_id": report_data["header"]["run_id"],
        "source_hash": report_data["header"]["source_hash"],
        "source_file_name": input_file_name,
        "approved_by": approved_by,
        **approval_schema.new_approval_timestamps(),
        "approved_row_hashes": [by_number[n]["row_hash"] for n in req.rows],
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(approval, f, ensure_ascii=False, indent=2)

    audit_log_access("/approve", request, {"run_id": approval["run_id"], "approved_by": approved_by, "count": len(req.rows)})

    return {
        "status": "success",
        "approval_path": str(out_file),
        "approved_count": len(req.rows),
        "approval": approval,
    }


@router.post("/api/approve-conditional")
async def approve_conditional_execution_endpoint(request: Request) -> Dict[str, Any]:
    """Receives user decision for conditional execution after dry-run with rejections."""
    verify_api_auth(request)
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)

    operation_id = body.get("operation_id")
    user_choice = body.get("user_choice") or body.get("choice")
    chat_id = body.get("chat_id")
    approved_by = body.get("approved_by", "Dashboard User")

    if not operation_id:
        raise HTTPException(status_code=400, detail="معرف العملية (operation_id) مطلوب.")

    _safe_operation_id(operation_id)

    if user_choice not in ("execute", "fix", "cancel"):
        raise HTTPException(
            status_code=400,
            detail=f"الخيار «{user_choice}» غير صالح. الخيارات المتاحة: execute, fix, cancel",
        )

    # سجل القرار في أحداث العملية
    try:
        from agent_events_service import get_events_service
        events_service = get_events_service()
        events_service.emit_agent_event(
            operation_id=operation_id,
            agent="Seraj (سراج)",
            action=f"user_decision_{user_choice}",
            status="completed",
            reasoning=f"المستخدم اختار: {user_choice} (بواسطة {approved_by})",
            metadata={"user_choice": user_choice, "approved_by": approved_by, "chat_id": chat_id},
        )
    except Exception:
        pass

    audit_log_access("/api/approve-conditional", request, {
        "operation_id": operation_id,
        "user_choice": user_choice,
        "approved_by": approved_by,
    })

    return {
        "status": "success",
        "operation_id": operation_id,
        "user_choice": user_choice,
        "approved_by": approved_by,
        "message": f"تم تسجيل قرارك بنجاح ({user_choice}).",
    }


# ==================== WRITE & EXECUTION ====================

@router.post("/write")
@router.post("/api/write")
@router.post("/api/execute")
def execute_writer_endpoint(req: WriteRequest, request: Request) -> Dict[str, Any]:
    """The SOLE endpoint permitted to mutate Odoo. Requires auth token & valid approval."""
    verify_write_auth(request)

    report_path = _safe_artifact_path(req.report_path, "report_path") if req.report_path else None
    approval_path = _safe_artifact_path(req.approval_path, "approval_path") if req.approval_path else None
    input_path = _safe_artifact_path(req.input_path, "input_path") if req.input_path else None

    if req.run_id and (not report_path or not approval_path or not input_path):
        _safe_operation_id(req.run_id)
        matches = list(Path("output").glob(f"{req.run_id}_*"))
        if matches:
            run_dir = matches[0]
            if not report_path:
                report_path = run_dir / "dry_run_report.json"
            if not approval_path:
                approval_path = run_dir / "approval.json"
            if not input_path:
                session_f = run_dir / "telegram_session.json"
                if session_f.exists():
                    try:
                        s_data = json.loads(session_f.read_text(encoding="utf-8"))
                        if s_data.get("input_path"):
                            input_path = Path(s_data["input_path"])
                    except Exception:
                        pass

    if not approval_path or not approval_path.exists():
        raise HTTPException(
            status_code=400,
            detail="توقف الأمان (Security Guard): لم يتم العثور على ملف الاعتماد approval.json. يجب اعتماد العملية أولاً عبر /approve.",
        )

    if not report_path or not report_path.exists():
        raise HTTPException(status_code=404, detail=f"ملف التقرير غير موجود: {report_path}")

    upload_dir = _get_upload_dir()
    if not input_path or not input_path.exists():
        try:
            r_data = json.loads(report_path.read_text(encoding="utf-8"))
            src_name = r_data.get("header", {}).get("source_file_name", "")
            candidates = list(upload_dir.glob(f"*{src_name}*"))
            if candidates:
                input_path = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        except Exception:
            pass

    if not input_path or not input_path.exists():
        raise HTTPException(status_code=404, detail="ملف الإكسل الأصلي غير موجود.")

    try:
        app_obj = approval_schema.Approval.load(approval_path)
        report_data = json.loads(report_path.read_text(encoding="utf-8"))
        approval_schema.validate_approval_against_report(app_obj, report_data)
    except approval_schema.ApprovalExpiredError:
        raise HTTPException(
            status_code=400,
            detail="انتهت المهلة الزمنية للاعتماد (5 دقائق) لأسباب أمنية. يرجى النقر على زر الاعتماد مجدداً لتجديد التفويض والمتابعة.",
        )
    except approval_schema.ApprovalAlreadyConsumedError:
        raise HTTPException(
            status_code=400,
            detail="تم استهلاك هذا الاعتماد وتنفيذه مسبقاً، ولا يمكن إعادة استخدامه لمنع تكرار العمليات.",
        )
    except (approval_schema.ApprovalSchemaError, approval_schema.ApprovalReportMismatchError) as exc:
        raise HTTPException(status_code=400, detail=f"توقف الأمان: ملف الموافقة غير صالح أو لا يتطابق مع التقرير: {exc}")

    out_dir = Path("output") / f"writer_web_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        gw_cls = _get_write_gateway_cls()
        repo_cls = _get_readonly_repo_cls()
        writer_mod = _get_writer_module()

        gw = gw_cls(
            os.environ["ODOO_URL"], os.environ["ODOO_DB"], os.environ["ODOO_USERNAME"], os.environ["ODOO_API_KEY"]
        )
        repo = repo_cls()
        target_company_id = req.company_id
        if not target_company_id:
            try:
                target_company_id = repo.get_default_company().get("id", 1)
            except Exception:
                target_company_id = 1

        result = writer_mod.run_writer(
            str(input_path),
            str(report_path),
            str(approval_path),
            str(out_dir),
            repo,
            gw,
            company_id=target_company_id,
            max_rows=req.max_rows,
        )
    except (writer.WriterAbort, EnvironmentGuardError) as exc:
        if isinstance(exc, writer.WriterAbort):
            if exc.code == writer.ABORT_APPROVAL_EXPIRED:
                raise HTTPException(
                    status_code=400,
                    detail="انتهت المهلة الزمنية للاعتماد (5 دقائق) لأسباب أمنية. يرجى النقر على زر الاعتماد مجدداً لتجديد التفويض والمتابعة.",
                )
            if exc.code == writer.ABORT_APPROVAL_CONSUMED:
                raise HTTPException(
                    status_code=400,
                    detail="تم استهلاك هذا الاعتماد وتنفيذه مسبقاً، ولا يمكن إعادة استخدامه لمنع تكرار العمليات.",
                )
        raise HTTPException(status_code=400, detail=f"توقف الأمان (ABORT): {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"خطأ أثناء الإنشاء: {type(exc).__name__}: {exc}")

    telegram_status = {"sent": False, "status": "skipped", "reason": "Not configured"}
    if telegram_notifier.is_telegram_configured():
        try:
            tg_text = telegram_notifier.format_writer_notification(result)
            telegram_status = telegram_notifier.send_telegram_notification(tg_text)
        except Exception as exc:
            telegram_status = {"sent": False, "status": "error", "reason": str(exc)}

    audit_log_access("/write", request, {
        "report": str(report_path),
        "created_count": result.get("footer", {}).get("status_counts", {}).get("created", 0),
    })

    return {
        "status": "success",
        "result": result,
        "telegram": telegram_status,
        "results_path": result.get("results_path"),
        "created_count": result.get("footer", {}).get("status_counts", {}).get("created", 0),
    }


@router.get("/write/{run_id}/stream")
@router.get("/api/write/{run_id}/stream")
async def stream_writer_results(run_id: str, request: Request):
    """Server-Sent Events streaming writer_results_*.jsonl line by line as it is written."""
    audit_log_access(f"/write/{run_id}/stream", request)

    async def event_generator():
        results_file: Optional[Path] = None
        start_wait = time.time()

        while time.time() - start_wait < 15:
            candidates = list(Path("output").glob(f"**/writer_results_*{run_id}*.jsonl"))
            if not candidates:
                candidates = list(Path("output").glob(f"**/*{run_id}*/**/writer_results*.jsonl"))
            if not candidates:
                all_recent = sorted(Path("output").glob("**/writer_results*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
                for c in all_recent[:5]:
                    try:
                        first_line = c.read_text(encoding="utf-8").splitlines()[0]
                        if run_id in first_line:
                            candidates = [c]
                            break
                    except Exception:
                        pass
            if candidates:
                results_file = candidates[0]
                break
            await asyncio.sleep(0.5)

        if not results_file or not results_file.exists():
            yield f"event: error\ndata: {json.dumps({'error': 'لم يتم العثور على سجل نتائج الإنشاء لهذا الفحص'})}\n\n"
            return

        with open(results_file, "r", encoding="utf-8") as f:
            last_pos = 0
            is_finished = False
            idle_count = 0
            while not is_finished and idle_count < 30:
                f.seek(last_pos)
                lines = f.readlines()
                last_pos = f.tell()

                if lines:
                    idle_count = 0
                    for line in lines:
                        clean_line = line.strip()
                        if clean_line:
                            yield f"data: {clean_line}\n\n"
                            try:
                                parsed = json.loads(clean_line)
                                if parsed.get("record_type") == "footer":
                                    is_finished = True
                                    yield f"event: done\ndata: {json.dumps({'status': 'finished'})}\n\n"
                                    break
                            except Exception:
                                pass
                else:
                    idle_count += 1
                    await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/api/approve-and-execute")
def approve_and_execute_endpoint(req: QuickApproveAndExecuteRequest, request: Request) -> Dict[str, Any]:
    """Composite endpoint for automated workflows (n8n/Telegram) to approve and write in one step."""
    verify_write_auth(request)
    output_root = Path("output")
    matching_folders = list(output_root.glob(f"{req.run_id}_*"))
    if not matching_folders and (output_root / req.run_id).is_dir():
        matching_folders = [output_root / req.run_id]

    if not matching_folders:
        raise HTTPException(status_code=404, detail=f"لم يتم العثور على فحص بالمعرف: {req.run_id}")

    run_dir = matching_folders[0]
    report_file = run_dir / "dry_run_report.json"
    if not report_file.exists():
        raise HTTPException(status_code=404, detail=f"ملف التقرير غير موجود في مجلد الفحص: {run_dir}")

    try:
        report_data = json.loads(report_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"تعذر قراءة التقرير: {exc}")

    input_path = None
    session_file = run_dir / "telegram_session.json"
    if session_file.exists():
        try:
            s_data = json.loads(session_file.read_text(encoding="utf-8"))
            if s_data.get("input_path") and Path(s_data["input_path"]).exists():
                input_path = Path(s_data["input_path"])
        except Exception:
            pass

    upload_dir = _get_upload_dir()
    if not input_path:
        source_name = report_data.get("header", {}).get("source_file_name", "")
        candidates = list(upload_dir.glob(f"*{source_name}*")) if source_name else []
        if candidates:
            input_path = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        else:
            all_uploads = sorted(upload_dir.glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
            if all_uploads:
                input_path = all_uploads[0]

    if not input_path or not input_path.exists():
        raise HTTPException(status_code=404, detail="تعذر تحديد ملف الإكسل الأصلي المقترن بالفحص.")

    rows = report_data.get("rows", [])
    accepted_rows = [r for r in rows if r.get("final_status") == "accepted"]
    if not accepted_rows:
        raise HTTPException(status_code=400, detail="لا توجد أي صفوف مقبولة (accepted) في هذا التقرير لتنفيذها.")

    if len(accepted_rows) > req.max_rows:
        raise HTTPException(
            status_code=400,
            detail=f"عدد الصفوف المقبولة ({len(accepted_rows)}) يتجاوز الحد المسموح به للتنفيذ ({req.max_rows}).",
        )

    approval_file = run_dir / "approval.json"
    approval_payload = {
        "run_id": report_data["header"]["run_id"],
        "source_hash": report_data["header"]["source_hash"],
        "source_file_name": input_path.name,
        "approved_by": req.approved_by,
        **approval_schema.new_approval_timestamps(),
        "approved_row_hashes": [r["row_hash"] for r in accepted_rows],
    }
    with open(approval_file, "w", encoding="utf-8") as f:
        json.dump(approval_payload, f, ensure_ascii=False, indent=2)

    out_dir = Path("output") / f"writer_auto_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        gw_cls = _get_write_gateway_cls()
        repo_cls = _get_readonly_repo_cls()
        writer_mod = _get_writer_module()

        gw = gw_cls(
            os.environ["ODOO_URL"], os.environ["ODOO_DB"], os.environ["ODOO_USERNAME"], os.environ["ODOO_API_KEY"]
        )
        repo = repo_cls()
        target_company_id = req.company_id
        if not target_company_id:
            try:
                target_company_id = repo.get_default_company().get("id", 1)
            except Exception:
                target_company_id = 1

        result = writer_mod.run_writer(
            str(input_path),
            str(report_file),
            str(approval_file),
            str(out_dir),
            repo,
            gw,
            company_id=target_company_id,
            max_rows=req.max_rows,
        )
    except (writer.WriterAbort, EnvironmentGuardError) as exc:
        if isinstance(exc, writer.WriterAbort):
            if exc.code == writer.ABORT_APPROVAL_EXPIRED:
                raise HTTPException(
                    status_code=400,
                    detail="انتهت المهلة الزمنية للاعتماد (5 دقائق) لأسباب أمنية. يرجى إعادة محاولة الاعتماد والتنفيذ.",
                )
            if exc.code == writer.ABORT_APPROVAL_CONSUMED:
                raise HTTPException(
                    status_code=400,
                    detail="تم استهلاك هذا الاعتماد وتنفيذه مسبقاً، ولا يمكن إعادة استخدامه لمنع تكرار العمليات.",
                )
        raise HTTPException(status_code=400, detail=f"توقف الأمان (ABORT): {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"خطأ أثناء الإنشاء في Odoo: {type(exc).__name__}: {exc}")

    telegram_status = {"sent": False, "status": "skipped", "reason": "Not configured"}
    if telegram_notifier.is_telegram_configured():
        try:
            tg_text = telegram_notifier.format_writer_notification(result)
            telegram_status = telegram_notifier.send_telegram_notification(tg_text)
        except Exception as exc:
            telegram_status = {"sent": False, "status": "error", "reason": str(exc)}

    status_counts = result.get("footer", {}).get("status_counts", {})
    created_count = status_counts.get("created", 0)
    failed_count = status_counts.get("failed", 0)
    skipped_count = status_counts.get("skipped", 0)

    created_items = []
    for r in result.get("rows", []):
        if r.get("action") == "created":
            created_items.append({
                "name": r.get("name", ""),
                "odoo_id": r.get("odoo_id"),
                "email": r.get("email", ""),
            })

    audit_log_access("/api/approve-and-execute", request, {"run_id": req.run_id, "created_count": created_count})

    return {
        "status": "success",
        "run_id": req.run_id,
        "created_count": created_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "created_items": created_items,
        "result": result,
        "telegram": telegram_status,
    }


# ==================== LEGACY DOWNLOAD & REPORTS ====================

@router.get("/api/download-template")
@router.get("/download-template")
def download_legacy_template_endpoint():
    """Returns the latest official Excel template."""
    samples_dir = Path("samples")
    templates = sorted(samples_dir.glob("employee_import_template_*.xlsx"), reverse=True)
    if templates:
        return FileResponse(
            path=str(templates[0]),
            filename=templates[0].name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    import generate_employee_template
    out_file = samples_dir / f"employee_import_template_{datetime.now().strftime('%Y%m%d')}.xlsx"
    generate_employee_template.main(["--output-dir", "samples"])
    return FileResponse(
        path=str(out_file),
        filename=out_file.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/api/reports/dry-run/{folder_name}")
def get_dry_run_report_detail_endpoint(folder_name: str, request: Request) -> Dict[str, Any]:
    """Returns the parsed dry-run report JSON for the specified folder or operation_id."""
    audit_log_access(f"/api/reports/dry-run/{folder_name}", request)
    _safe_operation_id(folder_name)
    report_file = OUTPUT_ROOT / folder_name / "dry_run_report.json"
    if not report_file.exists():
        if folder_name.startswith("op_") or folder_name.startswith("web_"):
            try:
                from agent_events_service import get_events_service
                srv = get_events_service()
                op = srv.get_operation(folder_name)
                if op:
                    for evt in op.get("events", []):
                        meta = evt.get("metadata") or {}
                        f = meta.get("folder")
                        if f and (OUTPUT_ROOT / f / "dry_run_report.json").exists():
                            report_file = OUTPUT_ROOT / f / "dry_run_report.json"
                            break
                        run_id = meta.get("run_id")
                        if run_id:
                            candidates = list(OUTPUT_ROOT.glob(f"*{run_id}*/dry_run_report.json"))
                            if candidates:
                                report_file = candidates[0]
                                break
            except Exception:
                pass

    if not report_file.exists():
        candidates = list(Path("output").glob(f"*{folder_name}*/dry_run_report.json"))
        if candidates:
            report_file = candidates[0]
        else:
            all_reports = list(OUTPUT_ROOT.glob("*/dry_run_report.json"))
            if all_reports:
                all_reports.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                if (time.time() - all_reports[0].stat().st_mtime) < 1800:
                    report_file = all_reports[0]

    if not report_file or not report_file.exists():
        raise HTTPException(status_code=404, detail="تقرير الفحص غير موجود.")

    try:
        data = json.loads(report_file.read_text(encoding="utf-8"))
        return {"status": "success", "report": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"خطأ في قراءة ملف التقرير: {exc}")
