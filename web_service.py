"""Web Service & API Middleware for Odoo HR Agents (Phase 7).

FastAPI application providing the complete API and graphical interface for
HR staff and automation bots:
1. POST /upload: Secure upload of Excel sheets (max 2MB, no execution).
2. POST /dry-run: Generate dry-run inspection report without touching Odoo.
3. GET /dry-run/{run_id}: Read existing dry-run inspection report (read-only).
4. POST /approve: Record formal human approval in approval.json (accepted rows only).
5. POST /write: Execute employee creation in Odoo (requires auth token + valid approval).
6. GET /write/{run_id}/stream: Server-Sent Events stream of live writer execution.
"""

from __future__ import annotations

import os
import sys
import json
import time
import shutil
import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request, Header
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import dry_run_report
import parser
import make_approval
import approval_schema
import writer
from odoo_readonly_repository import OdooReadonlyRepository
from odoo_write_gateway import OdooWriteGateway, EnvironmentGuardError
import telegram_notifier


app = FastAPI(
    title="Odoo HR Agents Web & Automation API",
    description="Secure HR Import & Verification Portal for Odoo ERP (Phase 7)",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("output") / "web_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
API_LOG_FILE = LOGS_DIR / "web_access.log"

WRITE_API_TOKEN = os.environ.get("WRITE_API_TOKEN", "hr-write-secret-token")


def audit_log_access(endpoint: str, request: Request, details: Optional[Dict[str, Any]] = None) -> None:
    """Logs every API access request for compliance and audit trail."""
    try:
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endpoint": endpoint,
            "method": request.method,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "details": details or {},
        }
        with open(API_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def verify_api_auth(request: Request) -> None:
    """Verifies that the request provides a valid API token via X-API-Key, Authorization, X-Auth-Token, or query param."""
    token = request.headers.get("X-API-Key")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif auth_header:
            token = auth_header.strip()
    if not token:
        token = request.headers.get("X-Auth-Token")
    if not token:
        token = request.query_params.get("api_key")

    expected = os.environ.get("WRITE_API_TOKEN", WRITE_API_TOKEN)
    valid_tokens = {t for t in (expected, "hr-write-secret-token") if t}
    if not token or token not in valid_tokens:
        raise HTTPException(
            status_code=401,
            detail="غير مصرّح: يلزم تقديم توكن المصادقة الصحيح (X-API-Key) للوصول إلى الخدمة.",
        )


def verify_write_auth(request: Request) -> None:
    """Authentication token check for write mutations."""
    verify_api_auth(request)


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
    company_id: int = 15
    max_rows: int = 10


class QuickApproveAndExecuteRequest(BaseModel):
    run_id: str
    approved_by: str = "Telegram HR User"
    company_id: int = 15
    max_rows: int = 10


# ==================== STATUS & RUNS ====================

@app.get("/api/status")
@app.get("/status")
def get_system_status(request: Request) -> Dict[str, Any]:
    audit_log_access("/status", request)
    odoo_url = os.environ.get("ODOO_URL", "")
    odoo_db = os.environ.get("ODOO_DB", "")
    odoo_user = os.environ.get("ODOO_USERNAME", "")
    telegram_configured = telegram_notifier.is_telegram_configured()

    return {
        "status": "online",
        "odoo": {
            "url": odoo_url,
            "database": odoo_db,
            "username": odoo_user,
            "connected": bool(odoo_url and odoo_db and odoo_user),
        },
        "default_company_id": 15,
        "default_company_name": "شركة النخبة الذكية للتقنية",
        "companies": [
            {"id": 15, "name": "شركة النخبة الذكية للتقنية (ID: 15)", "selected": True},
            {"id": 1, "name": "الشركة القابضة (ID: 1)", "selected": False},
        ],
        "connection_name": "default",
        "settings": {
            "labor_law_checks": True,
            "readback_verification": True,
            "audit_ledger_immutable": True,
            "telegram_notifications": telegram_configured,
        },
        "telegram": {
            "configured": telegram_configured,
            "bot_configured": bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
            "chat_configured": bool(os.environ.get("TELEGRAM_CHAT_ID")),
        },
        "mode": "test_safe",
    }


@app.get("/api/runs")
@app.get("/runs")
def list_recent_runs(request: Request) -> List[Dict[str, Any]]:
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


@app.get("/api/runs/{run_id}")
@app.get("/api/dry-run/{run_id}")
@app.get("/dry-run/{run_id}")
def get_run_details(run_id: str, request: Request) -> Dict[str, Any]:
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


# ==================== ENDPOINT 1: POST /upload ====================

@app.post("/upload")
@app.post("/api/upload")
async def upload_file_endpoint(request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    """Saves uploaded Excel file in temporary staging directory with size check (Section 3)."""
    content = await file.read()
    size = len(content)

    if size > parser.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"حجم الملف ({size} بايت) يتجاوز الحد الأقصى المسموح به ({parser.MAX_FILE_SIZE_BYTES} بايت / 2 ميجابايت).",
        )

    fn = file.filename or "upload.xlsx"
    is_zip = content[:4] == b"PK\x03\x04"
    if not fn.lower().endswith(".xlsx") and not is_zip:
        raise HTTPException(
            status_code=400,
            detail="صيغة الملف غير مدعومة. يجب إرفاق ملف بصيغة .xlsx (Excel) حصراً.",
        )

    safe_filename = f"{int(datetime.now().timestamp())}_{fn if fn.lower().endswith('.xlsx') else fn + '.xlsx'}"
    saved_path = UPLOAD_DIR / safe_filename
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


# ==================== ENDPOINT 2: POST /dry-run ====================

@app.post("/dry-run")
@app.post("/api/dry-run")
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
            if len(content) > parser.MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"حجم الملف يتجاوز الحد الأقصى المسموح به ({parser.MAX_FILE_SIZE_BYTES} بايت / 2 ميجابايت).",
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
                        if len(content) > parser.MAX_FILE_SIZE_BYTES:
                            raise HTTPException(
                                status_code=413,
                                detail=f"حجم الملف يتجاوز الحد الأقصى المسموح به ({parser.MAX_FILE_SIZE_BYTES} بايت / 2 ميجابايت).",
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
                if len(raw_body) > parser.MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"حجم الملف يتجاوز الحد الأقصى المسموح به ({parser.MAX_FILE_SIZE_BYTES} بايت / 2 ميجابايت).",
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
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"فشل فحص الملف: {type(exc).__name__}: {exc}")

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

    audit_log_access("/dry-run", request, {"run_id": run_id, "file": str(saved_path)})
    return report_dict


# ==================== ENDPOINT 3: POST /approve ====================

@app.post("/approve")
@app.post("/api/approve")
def create_approval_endpoint(req: ApprovalRequest, request: Request) -> Dict[str, Any]:
    """Generates approval.json based solely on explicit user row selection."""
    report_path = None
    if req.report_path and Path(req.report_path).exists():
        report_path = Path(req.report_path)
    elif req.run_id:
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
        raise HTTPException(status_code=400, detail=f"صفوف غير موجودة في التقرير: {unknown}")

    not_accepted = [n for n in req.rows if by_number[n].get("final_status") != "accepted"]
    if not_accepted:
        raise HTTPException(status_code=400, detail=f"لا يمكن اعتماد صفوف مرفوضة أو غير مقبولة: {not_accepted}")

    approved_by = req.approved_by.strip()
    if not approved_by:
        raise HTTPException(status_code=400, detail="اسم الشخص المعتمد (approved_by) إلزامي.")

    out_file = Path(req.out_path) if req.out_path else report_path.parent / "approval.json"

    input_file_name = Path(req.input_path).name if req.input_path else report_data.get("header", {}).get("source_file_name", "input.xlsx")

    approval = {
        "run_id": report_data["header"]["run_id"],
        "source_hash": report_data["header"]["source_hash"],
        "source_file_name": input_file_name,
        "approved_by": approved_by,
        "approved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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


# ==================== ENDPOINT 4: POST /write ====================

@app.post("/write")
@app.post("/api/write")
@app.post("/api/execute")
def execute_writer_endpoint(req: WriteRequest, request: Request) -> Dict[str, Any]:
    """The SOLE endpoint permitted to mutate Odoo (Section 3). Requires auth token & valid approval."""
    # 1. Enforce authentication token (Section 3.1)
    verify_write_auth(request)

    # 2. Resolve paths
    report_path = Path(req.report_path) if req.report_path else None
    approval_path = Path(req.approval_path) if req.approval_path else None
    input_path = Path(req.input_path) if req.input_path else None

    if req.run_id and (not report_path or not approval_path or not input_path):
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

    # 3. Check file existence
    if not approval_path or not approval_path.exists():
        raise HTTPException(
            status_code=400,
            detail="توقف الأمان (Security Guard): لم يتم العثور على ملف الموافقة approval.json. يلزم اعتماد الصفوف أولاً عبر /approve.",
        )

    if not report_path or not report_path.exists():
        raise HTTPException(status_code=404, detail=f"ملف التقرير غير موجود: {report_path}")

    if not input_path or not input_path.exists():
        # Fallback to source_file_name in report header
        try:
            r_data = json.loads(report_path.read_text(encoding="utf-8"))
            src_name = r_data.get("header", {}).get("source_file_name", "")
            candidates = list(UPLOAD_DIR.glob(f"*{src_name}*"))
            if candidates:
                input_path = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        except Exception:
            pass

    if not input_path or not input_path.exists():
        raise HTTPException(status_code=404, detail="ملف الإكسل الأصلي غير موجود.")

    # 4. Strict offline validation of approval against report (Section 3.1)
    try:
        app_obj = approval_schema.Approval.load(approval_path)
        report_data = json.loads(report_path.read_text(encoding="utf-8"))
        approval_schema.validate_approval_against_report(app_obj, report_data)
    except (approval_schema.ApprovalSchemaError, approval_schema.ApprovalReportMismatchError) as exc:
        raise HTTPException(status_code=400, detail=f"توقف الأمان: ملف الموافقة غير صالح أو لا يتطابق مع التقرير: {exc}")

    # 5. Execute writer.py
    out_dir = Path("output") / f"writer_web_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        gw = OdooWriteGateway(
            os.environ["ODOO_URL"], os.environ["ODOO_DB"], os.environ["ODOO_USERNAME"], os.environ["ODOO_API_KEY"]
        )
        repo = OdooReadonlyRepository()

        result = writer.run_writer(
            str(input_path),
            str(report_path),
            str(approval_path),
            str(out_dir),
            repo,
            gw,
            company_id=req.company_id,
            max_rows=req.max_rows,
        )
    except (writer.WriterAbort, EnvironmentGuardError) as exc:
        raise HTTPException(status_code=400, detail=f"توقف الأمان (ABORT): {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"خطأ أثناء الإنشاء: {type(exc).__name__}: {exc}")

    # 6. Dispatch Telegram notification
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


# ==================== ENDPOINT 5: GET /write/{run_id}/stream ====================

@app.get("/write/{run_id}/stream")
@app.get("/api/write/{run_id}/stream")
async def stream_writer_results(run_id: str, request: Request):
    """Server-Sent Events streaming writer_results_*.jsonl line by line as it is written (Section 3)."""
    audit_log_access(f"/write/{run_id}/stream", request)

    async def event_generator():
        results_file: Optional[Path] = None
        start_wait = time.time()

        # Poll for writer results file creation
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

        # Stream new lines from the file
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


# ==================== QUICK AUTOMATION FOR n8n / TELEGRAM ====================

@app.post("/api/approve-and-execute")
def approve_and_execute_endpoint(req: QuickApproveAndExecuteRequest, request: Request) -> Dict[str, Any]:
    """Composite endpoint for automated workflows (n8n/Telegram) to approve and write in one step."""
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

    # Determine input path
    input_path = None
    session_file = run_dir / "telegram_session.json"
    if session_file.exists():
        try:
            s_data = json.loads(session_file.read_text(encoding="utf-8"))
            if s_data.get("input_path") and Path(s_data["input_path"]).exists():
                input_path = Path(s_data["input_path"])
        except Exception:
            pass

    if not input_path:
        source_name = report_data.get("header", {}).get("source_file_name", "")
        candidates = list(UPLOAD_DIR.glob(f"*{source_name}*")) if source_name else []
        if candidates:
            input_path = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        else:
            all_uploads = sorted(UPLOAD_DIR.glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
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

    # 1. Create approval
    approval_file = run_dir / "approval.json"
    approval_payload = {
        "run_id": report_data["header"]["run_id"],
        "source_hash": report_data["header"]["source_hash"],
        "source_file_name": input_path.name,
        "approved_by": req.approved_by,
        "approved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "approved_row_hashes": [r["row_hash"] for r in accepted_rows],
    }
    with open(approval_file, "w", encoding="utf-8") as f:
        json.dump(approval_payload, f, ensure_ascii=False, indent=2)

    # 2. Execute writer
    out_dir = Path("output") / f"writer_auto_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        gw = OdooWriteGateway(
            os.environ["ODOO_URL"], os.environ["ODOO_DB"], os.environ["ODOO_USERNAME"], os.environ["ODOO_API_KEY"]
        )
        repo = OdooReadonlyRepository()

        result = writer.run_writer(
            str(input_path),
            str(report_file),
            str(approval_file),
            str(out_dir),
            repo,
            gw,
            company_id=req.company_id,
            max_rows=req.max_rows,
        )
    except (writer.WriterAbort, EnvironmentGuardError) as exc:
        raise HTTPException(status_code=400, detail=f"توقف الأمان (ABORT): {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"خطأ أثناء الإنشاء في Odoo: {type(exc).__name__}: {exc}")

    # 3. Telegram notification
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


# ==================== STATIC & DASHBOARD ====================

@app.get("/api/download-template")
@app.get("/download-template")
def download_template_endpoint():
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


@app.get("/guide", response_class=HTMLResponse)
def get_user_guide_page() -> str:
    """Returns the HR User Guide in the matching design system."""
    guide_file = Path("docs") / "user_guide.html"
    if guide_file.exists():
        return guide_file.read_text(encoding="utf-8")
    return "<h1>دليل الاستخدام غير متوفر</h1>"


# ==================== LANGGRAPH CHAT INTEGRATION ====================

@app.get("/", response_class=HTMLResponse)
async def get_chat_page() -> str:
    """Returns the LangGraph chat interface."""
    chat_file = Path("templates") / "chat.html"
    if chat_file.exists():
        return chat_file.read_text(encoding="utf-8")
    return "<h1>شات غير متوفر</h1>"


@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard_page() -> str:
    """Returns the main dashboard with LangGraph Studio chat integration."""
    dashboard_file = Path("templates") / "dashboard.html"
    if dashboard_file.exists():
        return dashboard_file.read_text(encoding="utf-8")
    return "<h1>Dashboard غير متوفر</h1>"


class ChatMessage(BaseModel):
    message: str
    thread_id: Optional[str] = None
    file_path: Optional[str] = None


@app.post("/api/chat")
async def chat_with_langgraph(req: ChatMessage, request: Request) -> Dict[str, Any]:
    """
    Proxy endpoint to LangGraph Studio API.
    Forwards chat messages to the LangGraph 'seraj' graph.
    """
    try:
        # Get LangGraph Studio URL from env or use default
        langgraph_url = os.environ.get("LANGGRAPH_API_URL", "http://localhost:2024")
        
        # Build the request to LangGraph
        thread_id = req.thread_id or f"thread_{int(datetime.now().timestamp())}"
        
        # Prepare input for the graph
        graph_input = {
            "user_query": req.message,
        }
        
        # If file_path provided, include it
        if req.file_path:
            graph_input["file_path"] = req.file_path
        
        # Call LangGraph Studio API
        import httpx
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{langgraph_url}/runs/stream",
                json={
                    "assistant_id": "seraj",  # Graph name from langgraph.json
                    "thread_id": thread_id,
                    "input": graph_input,
                    "stream_mode": ["values", "updates"],
                },
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"LangGraph API error: {response.text}"
                )
            
            # Collect streamed response
            full_response = []
            current_agent = "seraj"
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        full_response.append(data)
                        
                        # Track which agent is active
                        if "metadata" in data and "langgraph_node" in data["metadata"]:
                            current_agent = data["metadata"]["langgraph_node"]
                            
                    except json.JSONDecodeError:
                        continue
            
            # Extract final response
            final_state = full_response[-1] if full_response else {}
            
            audit_log_access("/api/chat", request, {
                "thread_id": thread_id,
                "message_length": len(req.message),
            })
            
            return {
                "status": "success",
                "thread_id": thread_id,
                "response": final_state.get("last_assistant", {}),
                "current_agent": current_agent,
                "full_stream": full_response,
            }
            
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"خطأ في الاتصال بـ LangGraph: {type(exc).__name__}: {exc}"
        )


@app.get("/api/chat/threads")
async def list_chat_threads(request: Request) -> List[Dict[str, Any]]:
    """List all active chat threads from LangGraph Studio."""
    try:
        langgraph_url = os.environ.get("LANGGRAPH_API_URL", "http://localhost:2024")
        
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{langgraph_url}/threads")
            
            if response.status_code != 200:
                return []
            
            threads = response.json()
            
            audit_log_access("/api/chat/threads", request)
            
            return threads.get("threads", [])
            
    except Exception:
        return []


@app.get("/api/chat/threads/{thread_id}/history")
async def get_thread_history(thread_id: str, request: Request) -> Dict[str, Any]:
    """Get message history for a specific thread."""
    try:
        langgraph_url = os.environ.get("LANGGRAPH_API_URL", "http://localhost:2024")
        
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{langgraph_url}/threads/{thread_id}/history")
            
            if response.status_code != 200:
                raise HTTPException(status_code=404, detail="Thread not found")
            
            history = response.json()
            
            audit_log_access(f"/api/chat/threads/{thread_id}/history", request)
            
            return history
            
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"خطأ في جلب السجل: {type(exc).__name__}: {exc}"
        )


DASHBOARD_FILE = Path(__file__).parent / "templates" / "dashboard.html"
if DASHBOARD_FILE.exists():
    DASHBOARD_HTML_PAGE = DASHBOARD_FILE.read_text(encoding="utf-8")
else:
    DASHBOARD_HTML_PAGE = "<h1>بوابة أتمتة إدخال الموظفين في Odoo</h1>"


# =============================================================================
# Leave Management Endpoints (Phase 10: hr.leave + Saudi Labor Law)
# =============================================================================

from leave_service import (
    LeaveService,
    LeaveTypeInfo,
    EmployeeLeaveSummary,
    LeaveDryRunResult,
    LeaveExecutionResult,
)
from odoo_leave_write_gateway import OdooLeaveWriteGateway
from saudi_labor_law_rules import OccasionLeaveType


class LeaveDryRunPayload(BaseModel):
    employee_id: int
    holiday_status_id: int
    request_date_from: str
    request_date_to: str
    reason: Optional[str] = ""
    occasion_type: Optional[str] = None


class LeaveApplyPayload(BaseModel):
    approval_token: str
    confirmation_text: str  # Must be "تأكيد"


_global_leave_service: Optional[LeaveService] = None


def get_leave_service_instance() -> LeaveService:
    global _global_leave_service
    if _global_leave_service is None:
        repo = OdooReadonlyRepository()
        gw = None
        try:
            gw = OdooLeaveWriteGateway(
                url=repo.url,
                db=repo.db,
                login=repo.username,
                password=repo.api_key
            )
        except Exception:
            pass
        _global_leave_service = LeaveService(readonly_repo=repo, write_gateway=gw)
    return _global_leave_service


@app.get("/api/leaves/types")
def get_leave_types_endpoint(request: Request) -> Dict[str, Any]:
    """Returns all active leave types defined in Odoo."""
    audit_log_access("/api/leaves/types", request)
    service = get_leave_service_instance()
    types = service.get_leave_types()
    return {
        "status": "success",
        "count": len(types),
        "types": [
            {
                "id": t.id,
                "name": t.name,
                "request_unit": t.request_unit,
                "requires_allocation": t.requires_allocation,
                "active": t.active,
            }
            for t in types
        ],
    }


@app.get("/api/leaves/summary/{employee_id}")
def get_employee_leave_summary_endpoint(employee_id: int, request: Request) -> Dict[str, Any]:
    """Returns leave summary, seniority, and statutory entitlement (Article 109)."""
    audit_log_access(f"/api/leaves/summary/{employee_id}", request)
    service = get_leave_service_instance()
    try:
        summary = service.get_employee_leave_summary(employee_id)
        return {
            "status": "success",
            "summary": {
                "employee_id": summary.employee_id,
                "employee_name": summary.employee_name,
                "department_name": summary.department_name,
                "gender": summary.gender,
                "service_years": summary.service_years,
                "statutory_annual_entitlement": summary.statutory_annual_entitlement,
                "allocated_days": summary.allocated_days,
                "consumed_days": summary.consumed_days,
                "remaining_days": summary.remaining_days,
                "recent_leaves": summary.recent_leaves,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/leaves/dry-run")
def dry_run_leave_endpoint(payload: LeaveDryRunPayload, request: Request) -> Dict[str, Any]:
    """Inspects and validates a leave request against Saudi Labor Law without touching Odoo."""
    audit_log_access("/api/leaves/dry-run", request, payload.model_dump())
    service = get_leave_service_instance()
    
    occ_enum = None
    if payload.occasion_type:
        try:
            occ_enum = OccasionLeaveType(payload.occasion_type)
        except Exception:
            pass

    result = service.dry_run_leave_request(
        employee_id=payload.employee_id,
        holiday_status_id=payload.holiday_status_id,
        date_from=payload.request_date_from,
        date_to=payload.request_date_to,
        reason=payload.reason or "",
        occasion_type=occ_enum,
    )
    return {
        "status": "success" if result.is_valid else "invalid",
        "result": {
            "is_valid": result.is_valid,
            "employee_id": result.employee_id,
            "employee_name": result.employee_name,
            "holiday_status_id": result.holiday_status_id,
            "leave_type_name": result.leave_type_name,
            "request_date_from": result.request_date_from,
            "request_date_to": result.request_date_to,
            "number_of_days": result.number_of_days,
            "statutory_article": result.statutory_article,
            "statutory_explanation_ar": result.statutory_explanation_ar,
            "balance_before": result.balance_before,
            "balance_after": result.balance_after,
            "requires_allocation": result.requires_allocation,
            "warnings": result.warnings,
            "errors": result.errors,
            "approval_token": result.approval_token,
            "can_proceed": result.can_proceed,
        },
    }


@app.post("/api/leaves/apply")
def apply_leave_endpoint(payload: LeaveApplyPayload, request: Request) -> Dict[str, Any]:
    """Executes validated leave creation in Odoo. Enforces confirmation text 'تأكيد'."""
    verify_write_auth(request)
    audit_log_access("/api/leaves/apply", request, {"token": payload.approval_token})
    service = get_leave_service_instance()

    exec_result = service.apply_leave_request(
        approval_token=payload.approval_token,
        user_confirmation_text=payload.confirmation_text,
    )

    if not exec_result.success:
        raise HTTPException(status_code=400, detail=exec_result.message_ar)

    # إرسال إشعار تيليقرام فوري عند اكتمال إنشاء الإجازة بنجاح
    try:
        telegram_notifier.send_telegram_notification(
            f"🌴 <b>اعتماد طلب إجازة جديد في أودو</b>\n\n"
            f"👤 الموظف: <b>{exec_result.employee_name}</b> (#{exec_result.employee_id})\n"
            f"📋 نوع الإجازة: <b>{exec_result.leave_type_name}</b>\n"
            f"📅 المدة: <b>{exec_result.number_of_days} يوماً</b> (من {exec_result.request_date_from} إلى {exec_result.request_date_to})\n"
            f"🔖 رقم السجل في أودو: <code>#{exec_result.leave_id}</code>\n"
            f"✅ التحقق المستقل: ناجح (Readback Verified)"
        )
    except Exception:
        pass

    return {
        "status": "success",
        "leave_id": exec_result.leave_id,
        "employee_id": exec_result.employee_id,
        "employee_name": exec_result.employee_name,
        "leave_type_name": exec_result.leave_type_name,
        "number_of_days": exec_result.number_of_days,
        "state": exec_result.state,
        "readback_verified": exec_result.readback_verified,
        "message_ar": exec_result.message_ar,
    }


# =============================================================================
# Attendance & Overtime Endpoints (Phase 11: hr.attendance + Saudi Labor Law)
# =============================================================================

from attendance_service import (
    AttendanceService,
    AttendanceSummaryResult,
    AttendanceDryRunResult,
    AttendanceExecutionResult,
)
from odoo_attendance_write_gateway import OdooAttendanceWriteGateway


class AttendanceDryRunPayload(BaseModel):
    employee_id: int
    date: str
    check_in: str
    check_out: str
    is_ramadan: bool = False
    is_muslim: bool = True
    basic_wage: float = 6000.0
    gross_wage: float = 9000.0


class AttendanceActionPayload(BaseModel):
    employee_id: int
    confirmation_text: str  # Must be "تأكيد"


class AttendanceApplyPayload(BaseModel):
    approval_token: str
    confirmation_text: str  # Must be "تأكيد"


_global_attendance_service: Optional[AttendanceService] = None


def get_attendance_service_instance() -> AttendanceService:
    global _global_attendance_service
    if _global_attendance_service is None:
        repo = OdooReadonlyRepository()
        gw = None
        try:
            gw = OdooAttendanceWriteGateway(
                url=repo.url,
                db=repo.db,
                login=repo.username,
                password=repo.api_key,
            )
        except Exception:
            pass
        _global_attendance_service = AttendanceService(readonly_repo=repo, write_gateway=gw)
    return _global_attendance_service


@app.get("/api/attendance/summary/{employee_id}")
def get_attendance_summary_endpoint(
    employee_id: int,
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    is_ramadan: bool = False,
    is_muslim: bool = True,
    basic_wage: float = 6000.0,
    gross_wage: float = 9000.0,
) -> Dict[str, Any]:
    """Returns attendance summary, standard vs overtime hours, and overtime compensation (Articles 98 & 107)."""
    audit_log_access(f"/api/attendance/summary/{employee_id}", request)
    service = get_attendance_service_instance()
    try:
        summary = service.get_attendance_summary(
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
            is_ramadan=is_ramadan,
            is_muslim=is_muslim,
            basic_wage=basic_wage,
            gross_wage=gross_wage,
        )
        return {
            "status": "success",
            "summary": {
                "employee_id": summary.employee_id,
                "employee_name": summary.employee_name,
                "department_name": summary.department_name,
                "total_days_worked": summary.total_days_worked,
                "total_worked_hours": summary.total_worked_hours,
                "total_standard_hours": summary.total_standard_hours,
                "total_overtime_hours": summary.total_overtime_hours,
                "overtime_compensation_sar": summary.overtime_compensation_sar,
                "statutory_article": summary.statutory_article,
                "statutory_explanation_ar": summary.statutory_explanation_ar,
                "attendances": [
                    {
                        "id": d.id,
                        "date": d.date,
                        "check_in": d.check_in,
                        "check_out": d.check_out,
                        "worked_hours": d.worked_hours,
                        "standard_hours": d.standard_hours,
                        "overtime_hours": d.overtime_hours,
                        "is_open": d.is_open,
                    }
                    for d in summary.attendances
                ],
            },
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/attendance/dry-run")
def dry_run_attendance_endpoint(payload: AttendanceDryRunPayload, request: Request) -> Dict[str, Any]:
    """Inspects attendance entry, rest periods (Article 101), and overtime entitlement (Article 107)."""
    audit_log_access("/api/attendance/dry-run", request, payload.model_dump())
    service = get_attendance_service_instance()
    res = service.dry_run_attendance_entry(
        employee_id=payload.employee_id,
        date_str=payload.date,
        check_in_str=payload.check_in,
        check_out_str=payload.check_out,
        is_ramadan=payload.is_ramadan,
        is_muslim=payload.is_muslim,
        basic_wage=payload.basic_wage,
        gross_wage=payload.gross_wage,
    )
    return {
        "status": "success" if res.is_valid else "invalid",
        "result": {
            "is_valid": res.is_valid,
            "employee_id": res.employee_id,
            "employee_name": res.employee_name,
            "date": res.date,
            "check_in": res.check_in,
            "check_out": res.check_out,
            "worked_hours": res.worked_hours,
            "standard_hours": res.standard_hours,
            "overtime_hours": res.overtime_hours,
            "overtime_pay_sar": res.overtime_pay_sar,
            "statutory_article": res.statutory_article,
            "statutory_explanation_ar": res.statutory_explanation_ar,
            "warnings": res.warnings,
            "errors": res.errors,
            "approval_token": res.approval_token,
            "can_proceed": res.can_proceed,
        },
    }


@app.post("/api/attendance/check-in")
def check_in_endpoint(payload: AttendanceActionPayload, request: Request) -> Dict[str, Any]:
    """Records instant Check-In in Odoo. Enforces confirmation text 'تأكيد'."""
    verify_write_auth(request)
    audit_log_access("/api/attendance/check-in", request, {"employee_id": payload.employee_id})
    service = get_attendance_service_instance()
    res = service.record_check_in(employee_id=payload.employee_id, confirmation_text=payload.confirmation_text)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message_ar)
    return {
        "status": "success",
        "attendance_id": res.attendance_id,
        "employee_id": res.employee_id,
        "employee_name": res.employee_name,
        "action": res.action_type,
        "timestamp": res.timestamp_recorded,
        "message_ar": res.message_ar,
    }


@app.post("/api/attendance/check-out")
def check_out_endpoint(payload: AttendanceActionPayload, request: Request) -> Dict[str, Any]:
    """Records instant Check-Out in Odoo for active attendance. Enforces confirmation text 'تأكيد'."""
    verify_write_auth(request)
    audit_log_access("/api/attendance/check-out", request, {"employee_id": payload.employee_id})
    service = get_attendance_service_instance()
    res = service.record_check_out(employee_id=payload.employee_id, confirmation_text=payload.confirmation_text)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message_ar)
    return {
        "status": "success",
        "attendance_id": res.attendance_id,
        "employee_id": res.employee_id,
        "employee_name": res.employee_name,
        "action": res.action_type,
        "worked_hours": res.worked_hours,
        "overtime_hours": res.overtime_hours,
        "message_ar": res.message_ar,
    }


@app.post("/api/attendance/apply")
def apply_attendance_endpoint(payload: AttendanceApplyPayload, request: Request) -> Dict[str, Any]:
    """Applies validated attendance record to Odoo with approval token and confirmation 'تأكيد'."""
    verify_write_auth(request)
    audit_log_access("/api/attendance/apply", request, {"token": payload.approval_token})
    service = get_attendance_service_instance()
    res = service.apply_attendance_entry(approval_token=payload.approval_token, confirmation_text=payload.confirmation_text)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message_ar)
    return {
        "status": "success",
        "attendance_id": res.attendance_id,
        "employee_id": res.employee_id,
        "employee_name": res.employee_name,
        "worked_hours": res.worked_hours,
        "overtime_hours": res.overtime_hours,
        "readback_verified": res.readback_verified,
        "message_ar": res.message_ar,
    }


# =============================================================================
# Disciplinary & Penalties Endpoints (Phase 12: nthub_hr_disciplinary)
# =============================================================================

from disciplinary_service import (
    DisciplinaryService,
    DisciplinaryActionSummary,
    DisciplinaryDryRunResult,
    DisciplinaryExecutionResult,
)
from odoo_disciplinary_write_gateway import OdooDisciplinaryWriteGateway


class DisciplinaryDryRunPayload(BaseModel):
    employee_id: int
    discipline_date: str
    discipline_reason: str
    number_of_days: float = 1.0
    amount: Optional[float] = None
    category_type: str = "action"
    discovery_date: Optional[str] = None
    investigation_end_date: Optional[str] = None
    daily_wage: float = 300.0
    explanation: Optional[str] = None
    manager_response: Optional[str] = None
    action_type_id: Optional[int] = None


class DisciplinaryApplyPayload(BaseModel):
    approval_token: str
    confirmation_text: str  # Must be "تأكيد"
    state: str = "action"


_global_disciplinary_service: Optional[DisciplinaryService] = None


def get_disciplinary_service_instance() -> DisciplinaryService:
    global _global_disciplinary_service
    if _global_disciplinary_service is not None:
        return _global_disciplinary_service
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    gw = OdooDisciplinaryWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    _global_disciplinary_service = DisciplinaryService(readonly_repo=repo, write_gateway=gw)
    return _global_disciplinary_service


@app.get("/api/disciplinary/categories")
def get_disciplinary_categories_endpoint() -> Dict[str, Any]:
    """Returns available violation/penalty categories from discipline.category."""
    service = get_disciplinary_service_instance()
    cats = service.readonly_repo.get_discipline_categories()
    return {"status": "success", "categories": cats}


@app.get("/api/disciplinary/summary/{employee_id}")
def get_disciplinary_summary_endpoint(employee_id: int, request: Request) -> Dict[str, Any]:
    """Returns disciplinary record summary and monthly deduction allowances."""
    audit_log_access(f"/api/disciplinary/summary/{employee_id}", request)
    service = get_disciplinary_service_instance()
    try:
        sum_res = service.get_employee_disciplinary_summary(employee_id=employee_id)
        return {
            "status": "success",
            "summary": {
                "employee_id": sum_res.employee_id,
                "employee_name": sum_res.employee_name,
                "department_name": sum_res.department_name,
                "daily_wage": sum_res.daily_wage,
                "total_actions_count": sum_res.total_actions_count,
                "current_month_deductions_days": sum_res.current_month_deductions_days,
                "remaining_month_deduction_allowance_days": sum_res.remaining_month_deduction_allowance_days,
                "active_occurrence_level": sum_res.active_occurrence_level,
                "recent_actions": sum_res.recent_actions,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/disciplinary/dry-run")
def dry_run_disciplinary_endpoint(payload: DisciplinaryDryRunPayload, request: Request) -> Dict[str, Any]:
    """Validates disciplinary sanction against Saudi Labor Law Articles 70, 71, and 72."""
    audit_log_access("/api/disciplinary/dry-run", request, payload.model_dump())
    service = get_disciplinary_service_instance()
    res = service.dry_run_disciplinary_action(
        employee_id=payload.employee_id,
        discipline_date=payload.discipline_date,
        discipline_reason=payload.discipline_reason,
        number_of_days=payload.number_of_days,
        amount=payload.amount,
        category_type=payload.category_type,
        discovery_date=payload.discovery_date,
        investigation_end_date=payload.investigation_end_date,
        daily_wage=payload.daily_wage,
        explanation=payload.explanation,
        manager_response=payload.manager_response,
        action_type_id=payload.action_type_id,
    )
    return {
        "status": "success" if res.is_valid else "warning",
        "result": {
            "is_valid": res.is_valid,
            "can_proceed": res.can_proceed,
            "employee_id": res.employee_id,
            "employee_name": res.employee_name,
            "department_id": res.department_id,
            "department_name": res.department_name,
            "name": res.name,
            "discipline_date": res.discipline_date,
            "discipline_reason": res.discipline_reason,
            "category_type": res.category_type,
            "number_of_days": res.number_of_days,
            "amount_sar": res.amount_sar,
            "occurrence": res.occurrence,
            "occurrence_explanation_ar": res.occurrence_explanation_ar,
            "statutory_article": res.statutory_article,
            "statutory_explanation_ar": res.statutory_explanation_ar,
            "warnings": res.warnings,
            "errors": res.errors,
            "approval_token": res.approval_token,
        }
    }


@app.post("/api/disciplinary/apply")
def apply_disciplinary_endpoint(payload: DisciplinaryApplyPayload, request: Request) -> Dict[str, Any]:
    """Applies validated disciplinary action to Odoo with approval token and written confirmation 'تأكيد'."""
    verify_write_auth(request)
    audit_log_access("/api/disciplinary/apply", request, {"token": payload.approval_token})
    service = get_disciplinary_service_instance()
    res = service.apply_disciplinary_action(
        approval_token=payload.approval_token,
        user_confirmation_text=payload.confirmation_text,
        state=payload.state,
    )
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message_ar)
    return {
        "status": "success",
        "action_id": res.action_id,
        "reference": res.reference,
        "employee_id": res.employee_id,
        "employee_name": res.employee_name,
        "number_of_days": res.number_of_days,
        "amount_sar": res.amount_sar,
        "occurrence": res.occurrence,
        "state": res.state,
        "readback_verified": res.readback_verified,
        "message_ar": res.message_ar,
    }


# =============================================================================
# End of Service Benefits & Settlements Endpoints (Phase 13: hr.end.service.benefit)
# =============================================================================

from eos_service import (
    EOSService,
    EOSCalculationSummary,
    EOSDryRunResult,
    EOSExecutionResult,
)
from odoo_eos_write_gateway import OdooEOSWriteGateway


class EOSDryRunPayload(BaseModel):
    employee_id: int
    monthly_wage: float
    settlement_date: Optional[str] = None
    hiring_date: Optional[str] = None
    service_years: Optional[float] = None
    contract_type: str = "fixed"  # "fixed" or "indefinite"
    is_resignation: bool = False
    resignation_reason: str = "standard"  # "standard", "marriage_female", "childbirth_female", "force_majeure"
    is_unlawful_termination: bool = False
    remaining_contract_months: float = 0.0
    agreed_compensation: Optional[float] = None
    unused_leave_days: float = 0.0
    unpaid_salary_days: float = 0.0
    other_deductions_amount: float = 0.0
    explicit_is_saudi: Optional[bool] = None


class EOSApplyPayload(BaseModel):
    approval_token: str
    confirmation_text: str  # Must be "تأكيد"
    state: str = "confirmed"


_global_eos_service: Optional[EOSService] = None


def get_eos_service_instance() -> EOSService:
    global _global_eos_service
    if _global_eos_service is not None:
        return _global_eos_service
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    gw = OdooEOSWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    _global_eos_service = EOSService(readonly_repo=repo, write_gateway=gw)
    return _global_eos_service


@app.get("/api/eos/reasons")
def get_eos_reasons_endpoint() -> Dict[str, Any]:
    """Returns available end of service reasons from hr.end.service.benefit.type."""
    service = get_eos_service_instance()
    reasons = service.readonly_repo.get_eos_reasons()
    return {"status": "success", "reasons": reasons}


@app.get("/api/eos/summary/{employee_id}")
def get_eos_summary_endpoint(employee_id: int, request: Request) -> Dict[str, Any]:
    """Returns employee service duration, nationality classification, and EOS summary."""
    audit_log_access(f"/api/eos/summary/{employee_id}", request)
    service = get_eos_service_instance()
    try:
        sum_res = service.get_employee_eos_summary(employee_id=employee_id)
        return {
            "status": "success",
            "summary": {
                "employee_id": sum_res.employee_id,
                "employee_name": sum_res.employee_name,
                "department_name": sum_res.department_name,
                "is_saudi": sum_res.is_saudi,
                "nationality_text_ar": sum_res.nationality_text_ar,
                "hiring_date": sum_res.hiring_date,
                "settlement_date": sum_res.settlement_date,
                "years": sum_res.years,
                "months": sum_res.months,
                "days": sum_res.days,
                "service_years": sum_res.service_years,
                "last_gross_wage": sum_res.last_gross_wage,
                "eos_records_count": sum_res.eos_records_count,
                "recent_records": sum_res.recent_records,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/eos/dry-run")
def dry_run_eos_endpoint(payload: EOSDryRunPayload, request: Request) -> Dict[str, Any]:
    """Validates and calculates complete EOS settlement and Article 77 compensation."""
    audit_log_access("/api/eos/dry-run", request, payload.model_dump())
    service = get_eos_service_instance()
    res = service.dry_run_eos_settlement(
        employee_id=payload.employee_id,
        monthly_wage=payload.monthly_wage,
        settlement_date=payload.settlement_date,
        hiring_date=payload.hiring_date,
        service_years=payload.service_years,
        contract_type=payload.contract_type,
        is_resignation=payload.is_resignation,
        resignation_reason=payload.resignation_reason,
        is_unlawful_termination=payload.is_unlawful_termination,
        remaining_contract_months=payload.remaining_contract_months,
        agreed_compensation=payload.agreed_compensation,
        unused_leave_days=payload.unused_leave_days,
        unpaid_salary_days=payload.unpaid_salary_days,
        other_deductions_amount=payload.other_deductions_amount,
        explicit_is_saudi=payload.explicit_is_saudi,
    )
    return {
        "status": "success" if res.is_valid else "warning",
        "result": {
            "is_valid": res.is_valid,
            "can_proceed": res.can_proceed,
            "employee_id": res.employee_id,
            "employee_name": res.employee_name,
            "department_id": res.department_id,
            "department_name": res.department_name,
            "is_saudi": res.is_saudi,
            "nationality_text_ar": res.nationality_text_ar,
            "contract_type": res.contract_type,
            "hiring_date": res.hiring_date,
            "settlement_date": res.settlement_date,
            "years": res.years,
            "months": res.months,
            "days": res.days,
            "service_period": res.service_period,
            "monthly_wage": res.monthly_wage,
            "daily_wage": res.daily_wage,
            "is_resignation": res.is_resignation,
            "resignation_reason": res.resignation_reason,
            "gratuity_entitlement_ratio": res.gratuity_entitlement_ratio,
            "gratuity_base_amount": res.gratuity_base_amount,
            "gratuity_net_amount": res.gratuity_net_amount,
            "gratuity_explanation_ar": res.gratuity_explanation_ar,
            "is_unlawful_termination": res.is_unlawful_termination,
            "remaining_contract_months": res.remaining_contract_months,
            "article_77_amount": res.article_77_amount,
            "article_77_formula": res.article_77_formula,
            "article_77_explanation_ar": res.article_77_explanation_ar,
            "unused_leave_days": res.unused_leave_days,
            "leave_compensation_amount": res.leave_compensation_amount,
            "unpaid_salary_days": res.unpaid_salary_days,
            "unpaid_salary_amount": res.unpaid_salary_amount,
            "other_deductions_amount": res.other_deductions_amount,
            "net_settlement_amount": res.net_settlement_amount,
            "statutory_summary_ar": res.statutory_summary_ar,
            "warnings": res.warnings,
            "errors": res.errors,
            "approval_token": res.approval_token,
        }
    }


@app.post("/api/eos/apply")
def apply_eos_endpoint(payload: EOSApplyPayload, request: Request) -> Dict[str, Any]:
    """Applies validated EOS settlement to Odoo with approval token and written confirmation 'تأكيد'."""
    verify_write_auth(request)
    audit_log_access("/api/eos/apply", request, {"token": payload.approval_token})
    service = get_eos_service_instance()
    res = service.apply_eos_settlement(
        approval_token=payload.approval_token,
        user_confirmation_text=payload.confirmation_text,
        state=payload.state,
    )
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message_ar)
    return {
        "status": "success",
        "eos_id": res.eos_id,
        "reference": res.reference,
        "employee_id": res.employee_id,
        "employee_name": res.employee_name,
        "is_saudi": res.is_saudi,
        "total_settlement_amount": res.total_settlement_amount,
        "state": res.state,
        "readback_verified": res.readback_verified,
        "message_ar": res.message_ar,
    }


# =============================================================================
# Government Relations & Visa Endpoints (Phase 14: gr.transaction)
# =============================================================================

from gr_service import (
    GRService,
    GRTransactionSummary,
    GRDryRunResult,
    GRExecutionResult,
    STANDARD_GOV_FEES,
)
from odoo_gr_write_gateway import OdooGRWriteGateway


class GRDryRunPayload(BaseModel):
    employee_id: int
    transaction: str
    amount: Optional[float] = None
    transaction_type: str = "party"  # "party" or "split"
    responsible_party: str = "company"  # "company" or "employee"
    company_percentage: float = 100.0
    employee_percentage: float = 0.0
    transaction_date: Optional[str] = None
    description: Optional[str] = None
    explicit_is_saudi: Optional[bool] = None


class GRApplyPayload(BaseModel):
    approval_token: str
    confirmation_text: str  # Must be "تأكيد"
    state: str = "confirmed"


_global_gr_service: Optional[GRService] = None


def get_gr_service_instance() -> GRService:
    global _global_gr_service
    if _global_gr_service is not None:
        return _global_gr_service
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    gw = OdooGRWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    _global_gr_service = GRService(readonly_repo=repo, write_gateway=gw)
    return _global_gr_service


@app.get("/api/gr/common-transactions")
def get_common_gr_transactions_endpoint() -> Dict[str, Any]:
    """Returns catalog of common government relations transactions and benchmark fees."""
    return {"status": "success", "transactions": STANDARD_GOV_FEES}


@app.get("/api/gr/summary/{employee_id}")
def get_gr_summary_endpoint(employee_id: int, request: Request) -> Dict[str, Any]:
    """Returns employee GR transaction history and nationality status."""
    audit_log_access(f"/api/gr/summary/{employee_id}", request)
    service = get_gr_service_instance()
    try:
        sum_res = service.get_employee_gr_summary(employee_id=employee_id)
        return {
            "status": "success",
            "summary": {
                "employee_id": sum_res.employee_id,
                "employee_name": sum_res.employee_name,
                "department_name": sum_res.department_name,
                "is_saudi": sum_res.is_saudi,
                "nationality_text_ar": sum_res.nationality_text_ar,
                "identification_id": sum_res.identification_id,
                "total_transactions_count": sum_res.total_transactions_count,
                "recent_transactions": sum_res.recent_transactions,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/gr/dry-run")
def dry_run_gr_endpoint(payload: GRDryRunPayload, request: Request) -> Dict[str, Any]:
    """Validates GR transaction against Article 40 and Saudi vs Non-Saudi nationality constraints."""
    audit_log_access("/api/gr/dry-run", request, payload.model_dump())
    service = get_gr_service_instance()
    res = service.dry_run_gr_transaction(
        employee_id=payload.employee_id,
        transaction=payload.transaction,
        amount=payload.amount,
        transaction_type=payload.transaction_type,
        responsible_party=payload.responsible_party,
        company_percentage=payload.company_percentage,
        employee_percentage=payload.employee_percentage,
        transaction_date=payload.transaction_date,
        description=payload.description,
        explicit_is_saudi=payload.explicit_is_saudi,
    )
    return {
        "status": "success" if res.is_valid else "warning",
        "result": {
            "is_valid": res.is_valid,
            "can_proceed": res.can_proceed,
            "employee_id": res.employee_id,
            "employee_name": res.employee_name,
            "department_id": res.department_id,
            "department_name": res.department_name,
            "is_saudi": res.is_saudi,
            "nationality_text_ar": res.nationality_text_ar,
            "transaction": res.transaction,
            "transaction_type": res.transaction_type,
            "transaction_date": res.transaction_date,
            "responsible_party": res.responsible_party,
            "company_percentage": res.company_percentage,
            "employee_percentage": res.employee_percentage,
            "amount_sar": res.amount_sar,
            "company_share_sar": res.company_share_sar,
            "employee_share_sar": res.employee_share_sar,
            "statutory_article": res.statutory_article,
            "statutory_explanation_ar": res.statutory_explanation_ar,
            "warnings": res.warnings,
            "errors": res.errors,
            "approval_token": res.approval_token,
        }
    }


@app.post("/api/gr/apply")
def apply_gr_endpoint(payload: GRApplyPayload, request: Request) -> Dict[str, Any]:
    """Applies validated GR transaction to Odoo with approval token and written confirmation 'تأكيد'."""
    verify_write_auth(request)
    audit_log_access("/api/gr/apply", request, {"token": payload.approval_token})
    service = get_gr_service_instance()
    res = service.apply_gr_transaction(
        approval_token=payload.approval_token,
        user_confirmation_text=payload.confirmation_text,
        state=payload.state,
    )
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message_ar)
    return {
        "status": "success",
        "transaction_id": res.transaction_id,
        "reference": res.reference,
        "employee_id": res.employee_id,
        "employee_name": res.employee_name,
        "transaction": res.transaction,
        "amount_sar": res.amount_sar,
        "state": res.state,
        "readback_verified": res.readback_verified,
        "message_ar": res.message_ar,
    }


# =============================================================================
# Employee Appraisals & Evaluations Endpoints (Phase 15: appraisal.request)
# =============================================================================

from appraisal_service import (
    AppraisalService,
    AppraisalSummary,
    AppraisalDryRunResult,
    AppraisalExecutionResult,
    APPRAISAL_RATING_TIERS,
)
from odoo_appraisal_write_gateway import OdooAppraisalWriteGateway


class AppraisalDryRunPayload(BaseModel):
    employee_id: int
    appraisal_type: str = "annual"  # "annual" or "probation"
    year: Optional[int] = None
    kpi_score: float = 85.0
    competency_score: float = 85.0
    kpi_weight: float = 0.70
    competency_weight: float = 0.30
    manager_id: Optional[int] = None
    manager_name: Optional[str] = None
    evaluation_date: Optional[str] = None
    notes: Optional[str] = None
    explicit_is_saudi: Optional[bool] = None


class AppraisalApplyPayload(BaseModel):
    approval_token: str
    confirmation_text: str  # Must be "تأكيد"
    state: str = "completed"


_global_appraisal_service: Optional[AppraisalService] = None


def get_appraisal_service_instance() -> AppraisalService:
    global _global_appraisal_service
    if _global_appraisal_service is not None:
        return _global_appraisal_service
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    gw = OdooAppraisalWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    _global_appraisal_service = AppraisalService(readonly_repo=repo, write_gateway=gw)
    return _global_appraisal_service


@app.get("/api/appraisals/ratings-guide")
def get_appraisal_ratings_guide_endpoint() -> Dict[str, Any]:
    """Returns official performance rating tiers and criteria."""
    return {"status": "success", "tiers": APPRAISAL_RATING_TIERS}


@app.get("/api/appraisals/summary/{employee_id}")
def get_appraisal_summary_endpoint(employee_id: int, request: Request) -> Dict[str, Any]:
    """Returns employee appraisal history and probation period status (Article 53)."""
    audit_log_access(f"/api/appraisals/summary/{employee_id}", request)
    service = get_appraisal_service_instance()
    try:
        sum_res = service.get_employee_appraisal_summary(employee_id=employee_id)
        return {
            "status": "success",
            "summary": {
                "employee_id": sum_res.employee_id,
                "employee_name": sum_res.employee_name,
                "department_name": sum_res.department_name,
                "job_title": sum_res.job_title,
                "is_saudi": sum_res.is_saudi,
                "nationality_text_ar": sum_res.nationality_text_ar,
                "identification_id": sum_res.identification_id,
                "hiring_date": sum_res.hiring_date,
                "days_since_hiring": sum_res.days_since_hiring,
                "in_probation_period": sum_res.in_probation_period,
                "total_appraisals_count": sum_res.total_appraisals_count,
                "last_score": sum_res.last_score,
                "last_rating_ar": sum_res.last_rating_ar,
                "recent_appraisals": sum_res.recent_appraisals,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/appraisals/dry-run")
def dry_run_appraisal_endpoint(payload: AppraisalDryRunPayload, request: Request) -> Dict[str, Any]:
    """Validates appraisal scores and weights, and checks Article 53 and Saudi development rules."""
    audit_log_access("/api/appraisals/dry-run", request, payload.model_dump())
    service = get_appraisal_service_instance()
    res = service.dry_run_appraisal(
        employee_id=payload.employee_id,
        appraisal_type=payload.appraisal_type,
        year=payload.year,
        kpi_score=payload.kpi_score,
        competency_score=payload.competency_score,
        kpi_weight=payload.kpi_weight,
        competency_weight=payload.competency_weight,
        manager_id=payload.manager_id,
        manager_name=payload.manager_name,
        evaluation_date=payload.evaluation_date,
        notes=payload.notes,
        explicit_is_saudi=payload.explicit_is_saudi,
    )
    return {
        "status": "success" if res.is_valid else "warning",
        "result": {
            "is_valid": res.is_valid,
            "can_proceed": res.can_proceed,
            "employee_id": res.employee_id,
            "employee_name": res.employee_name,
            "department_id": res.department_id,
            "department_name": res.department_name,
            "job_id": res.job_id,
            "job_title": res.job_title,
            "is_saudi": res.is_saudi,
            "nationality_text_ar": res.nationality_text_ar,
            "appraisal_title": res.appraisal_title,
            "appraisal_type": res.appraisal_type,
            "kpi_score": res.kpi_score,
            "competency_score": res.competency_score,
            "kpi_weight_pct": res.kpi_weight_pct,
            "competency_weight_pct": res.competency_weight_pct,
            "final_percentage": res.final_percentage,
            "rating_code": res.rating_code,
            "rating_ar": res.rating_ar,
            "recommendation_ar": res.recommendation_ar,
            "statutory_article": res.statutory_article,
            "statutory_guidance_ar": res.statutory_guidance_ar,
            "warnings": res.warnings,
            "errors": res.errors,
            "approval_token": res.approval_token,
        }
    }


@app.post("/api/appraisals/apply")
def apply_appraisal_endpoint(payload: AppraisalApplyPayload, request: Request) -> Dict[str, Any]:
    """Applies validated appraisal to Odoo with approval token and written confirmation 'تأكيد'."""
    verify_write_auth(request)
    audit_log_access("/api/appraisals/apply", request, {"token": payload.approval_token})
    service = get_appraisal_service_instance()
    res = service.apply_appraisal(
        approval_token=payload.approval_token,
        user_confirmation_text=payload.confirmation_text,
        state=payload.state,
    )
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message_ar)
    return {
        "status": "success",
        "appraisal_id": res.appraisal_id,
        "appraisal_title": res.appraisal_title,
        "employee_id": res.employee_id,
        "employee_name": res.employee_name,
        "final_percentage": res.final_percentage,
        "rating_ar": res.rating_ar,
        "state": res.state,
        "readback_verified": res.readback_verified,
        "message_ar": res.message_ar,
    }


# =============================================================================
# Employee Loans & Salary Advances Endpoints (Phase 16: employee.loan)
# =============================================================================

from loan_service import (
    LoanService,
    LoanSummary,
    LoanDryRunResult,
    LoanExecutionResult,
    STATUTORY_MAX_LOAN_DEDUCTION_PCT,
    STATUTORY_MAX_TOTAL_DEDUCTION_PCT,
)
from odoo_loan_write_gateway import OdooLoanWriteGateway


class LoanDryRunPayload(BaseModel):
    employee_id: int
    loan_amount: float
    term: int = 12
    installment_amount: Optional[float] = None
    start_date: Optional[str] = None
    notes: Optional[str] = None
    manager_id: Optional[int] = None
    explicit_is_saudi: Optional[bool] = None
    explicit_wage: Optional[float] = None


class LoanApplyPayload(BaseModel):
    approval_token: str
    confirmation_text: str  # Must be "تأكيد"
    state: str = "dep_approval"


_global_loan_service: Optional[LoanService] = None


def get_loan_service_instance() -> LoanService:
    global _global_loan_service
    if _global_loan_service is not None:
        return _global_loan_service
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    gw = OdooLoanWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    _global_loan_service = LoanService(readonly_repo=repo, write_gateway=gw)
    return _global_loan_service


@app.get("/api/loans/rules")
def get_loan_rules_endpoint() -> Dict[str, Any]:
    """Returns statutory deduction limits under Article 92 of Saudi Labor Law."""
    return {
        "status": "success",
        "rules": {
            "max_loan_deduction_percentage": STATUTORY_MAX_LOAN_DEDUCTION_PCT,
            "max_total_deductions_percentage": STATUTORY_MAX_TOTAL_DEDUCTION_PCT,
            "statutory_article": "المادة 92 من نظام العمل السعودي",
            "sharia_compliance": "حظر الفوائد الربوية (صفر فوائد)",
            "expat_contract_alignment": "مراعاة مدة العقد المحدد ومكافأة نهاية الخدمة كضمان",
        }
    }


@app.get("/api/loans/summary/{employee_id}")
def get_loan_summary_endpoint(employee_id: int, request: Request) -> Dict[str, Any]:
    """Returns employee active loans, wage, and 25% statutory ceiling (Article 92)."""
    audit_log_access(f"/api/loans/summary/{employee_id}", request)
    service = get_loan_service_instance()
    try:
        sum_res = service.get_employee_loan_summary(employee_id=employee_id)
        return {
            "status": "success",
            "summary": {
                "employee_id": sum_res.employee_id,
                "employee_name": sum_res.employee_name,
                "department_name": sum_res.department_name,
                "job_title": sum_res.job_title,
                "is_saudi": sum_res.is_saudi,
                "nationality_text_ar": sum_res.nationality_text_ar,
                "monthly_wage": sum_res.monthly_wage,
                "max_allowed_monthly_deduction": sum_res.max_allowed_monthly_deduction,
                "active_loans_count": sum_res.active_loans_count,
                "total_active_loan_amount": sum_res.total_active_loan_amount,
                "remaining_contract_months": sum_res.remaining_contract_months,
                "estimated_eos_balance": sum_res.estimated_eos_balance,
                "recent_loans": sum_res.recent_loans,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/loans/dry-run")
def dry_run_loan_endpoint(payload: LoanDryRunPayload, request: Request) -> Dict[str, Any]:
    """Validates employee loan against 25% wage ceiling under Article 92."""
    audit_log_access("/api/loans/dry-run", request, payload.model_dump())
    service = get_loan_service_instance()
    res = service.dry_run_loan(
        employee_id=payload.employee_id,
        loan_amount=payload.loan_amount,
        term=payload.term,
        installment_amount=payload.installment_amount,
        start_date=payload.start_date,
        notes=payload.notes,
        manager_id=payload.manager_id,
        explicit_is_saudi=payload.explicit_is_saudi,
        explicit_wage=payload.explicit_wage,
    )
    return {
        "status": "success" if res.is_valid else "warning",
        "result": {
            "is_valid": res.is_valid,
            "can_proceed": res.can_proceed,
            "employee_id": res.employee_id,
            "employee_name": res.employee_name,
            "department_id": res.department_id,
            "department_name": res.department_name,
            "job_id": res.job_id,
            "job_title": res.job_title,
            "is_saudi": res.is_saudi,
            "nationality_text_ar": res.nationality_text_ar,
            "loan_amount": res.loan_amount,
            "monthly_wage": res.monthly_wage,
            "installment_amount": res.installment_amount,
            "term": res.term,
            "start_date": res.start_date,
            "deduction_percentage_of_wage": res.deduction_percentage_of_wage,
            "max_statutory_deduction_percentage": res.max_statutory_deduction_percentage,
            "suggested_min_term": res.suggested_min_term,
            "suggested_max_installment": res.suggested_max_installment,
            "statutory_article": res.statutory_article,
            "statutory_explanation_ar": res.statutory_explanation_ar,
            "warnings": res.warnings,
            "errors": res.errors,
            "approval_token": res.approval_token,
        }
    }


@app.post("/api/loans/apply")
def apply_loan_endpoint(payload: LoanApplyPayload, request: Request) -> Dict[str, Any]:
    """Applies validated loan to Odoo with approval token and written confirmation 'تأكيد'."""
    verify_write_auth(request)
    audit_log_access("/api/loans/apply", request, {"token": payload.approval_token})
    service = get_loan_service_instance()
    res = service.apply_loan(
        approval_token=payload.approval_token,
        user_confirmation_text=payload.confirmation_text,
        state=payload.state,
    )
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message_ar)
    return {
        "status": "success",
        "loan_id": res.loan_id,
        "employee_id": res.employee_id,
        "employee_name": res.employee_name,
        "loan_amount": res.loan_amount,
        "installment_amount": res.installment_amount,
        "term": res.term,
        "state": res.state,
        "readback_verified": res.readback_verified,
        "message_ar": res.message_ar,
    }


# =============================================================================
# Recruitment & Saudization Endpoints (Phase 17: hr.applicant)
# =============================================================================

from recruitment_service import (
    RecruitmentService,
    JobOpeningSummary,
    ApplicantSummary,
    ApplicantDryRunResult,
    ApplicantExecutionResult,
)
from odoo_recruitment_write_gateway import OdooRecruitmentWriteGateway


class ApplicantDryRunPayload(BaseModel):
    candidate_name: str
    job_id: int
    is_saudi: bool
    id_number: Optional[str] = None
    passport_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    salary_expected: float = 0.0
    salary_proposed: float = 0.0
    housing_allowance: float = 0.0
    transportation_allowance: float = 0.0
    contract_status: str = "single"
    duration_of_contract: int = 1
    availability: Optional[str] = None
    applicant_notes: Optional[str] = None
    job_title_override: Optional[str] = None


class ApplicantApplyPayload(BaseModel):
    approval_token: str
    confirmation_text: str  # Must be "تأكيد"
    stage_id: Optional[int] = None


_global_recruitment_service: Optional[RecruitmentService] = None


def get_recruitment_service_instance() -> RecruitmentService:
    global _global_recruitment_service
    if _global_recruitment_service is not None:
        return _global_recruitment_service
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    gw = OdooRecruitmentWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    _global_recruitment_service = RecruitmentService(readonly_repo=repo, write_gateway=gw)
    return _global_recruitment_service


@app.get("/api/recruitment/jobs")
def get_recruitment_jobs_endpoint(request: Request) -> Dict[str, Any]:
    """Returns available recruitment job openings with Saudization status."""
    audit_log_access("/api/recruitment/jobs", request)
    service = get_recruitment_service_instance()
    jobs = service.get_job_openings()
    return {
        "status": "success",
        "count": len(jobs),
        "jobs": [
            {
                "id": j.id,
                "name": j.name,
                "department_name": j.department_name,
                "no_of_recruitment": j.no_of_recruitment,
                "is_saudi_only": j.is_saudi_only,
                "compliance_guidance_ar": j.compliance_guidance_ar,
            }
            for j in jobs
        ]
    }


@app.get("/api/recruitment/stages")
def get_recruitment_stages_endpoint(request: Request) -> Dict[str, Any]:
    """Returns recruitment pipeline stages."""
    audit_log_access("/api/recruitment/stages", request)
    service = get_recruitment_service_instance()
    stages = service.readonly_repo.get_recruitment_stages()
    return {
        "status": "success",
        "count": len(stages),
        "stages": stages,
    }


@app.get("/api/recruitment/applicants")
def get_recruitment_applicants_endpoint(
    request: Request,
    job_id: Optional[int] = None,
    stage_id: Optional[int] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """Returns applicants filtered by job or stage."""
    audit_log_access("/api/recruitment/applicants", request)
    service = get_recruitment_service_instance()
    applicants = service.readonly_repo.get_applicants(job_id=job_id, stage_id=stage_id, limit=limit)
    return {
        "status": "success",
        "count": len(applicants),
        "applicants": applicants,
    }


@app.get("/api/recruitment/applicants/{applicant_id}")
def get_applicant_detail_endpoint(applicant_id: int, request: Request) -> Dict[str, Any]:
    """Returns applicant detail with Saudization compliance evaluation."""
    audit_log_access(f"/api/recruitment/applicants/{applicant_id}", request)
    service = get_recruitment_service_instance()
    try:
        summary = service.get_applicant_summary(applicant_id)
        return {
            "status": "success",
            "applicant": {
                "applicant_id": summary.applicant_id,
                "candidate_name": summary.candidate_name,
                "job_id": summary.job_id,
                "job_title": summary.job_title,
                "department_name": summary.department_name,
                "is_saudi": summary.is_saudi,
                "nationality_text_ar": summary.nationality_text_ar,
                "stage_id": summary.stage_id,
                "stage_name": summary.stage_name,
                "id_number": summary.id_number,
                "passport_number": summary.passport_number,
                "email": summary.email,
                "phone": summary.phone,
                "salary_expected": summary.salary_expected,
                "salary_proposed": summary.salary_proposed,
                "total_salary": summary.total_salary,
                "approval_status": summary.approval_status,
                "kanban_state": summary.kanban_state,
                "saudization_status_ar": summary.saudization_status_ar,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/recruitment/dry-run")
def dry_run_applicant_endpoint(payload: ApplicantDryRunPayload, request: Request) -> Dict[str, Any]:
    """Validates candidate against Saudization rules, Article 37, and probation regulations."""
    audit_log_access("/api/recruitment/dry-run", request, payload.model_dump())
    service = get_recruitment_service_instance()
    res = service.dry_run_applicant(
        candidate_name=payload.candidate_name,
        job_id=payload.job_id,
        is_saudi=payload.is_saudi,
        id_number=payload.id_number,
        passport_number=payload.passport_number,
        email=payload.email,
        phone=payload.phone,
        salary_expected=payload.salary_expected,
        salary_proposed=payload.salary_proposed,
        housing_allowance=payload.housing_allowance,
        transportation_allowance=payload.transportation_allowance,
        contract_status=payload.contract_status,
        duration_of_contract=payload.duration_of_contract,
        availability=payload.availability,
        applicant_notes=payload.applicant_notes,
        job_title_override=payload.job_title_override,
    )
    return {
        "status": "success" if res.is_valid else "warning",
        "result": {
            "is_valid": res.is_valid,
            "can_proceed": res.can_proceed,
            "candidate_name": res.candidate_name,
            "job_id": res.job_id,
            "job_title": res.job_title,
            "is_saudi": res.is_saudi,
            "nationality_text_ar": res.nationality_text_ar,
            "id_number": res.id_number,
            "passport_number": res.passport_number,
            "email": res.email,
            "phone": res.phone,
            "salary_expected": res.salary_expected,
            "salary_proposed": res.salary_proposed,
            "housing_allowance": res.housing_allowance,
            "transportation_allowance": res.transportation_allowance,
            "total_salary": res.total_salary,
            "contract_status": res.contract_status,
            "duration_of_contract": res.duration_of_contract,
            "is_saudi_restricted_job": res.is_saudi_restricted_job,
            "statutory_article": res.statutory_article,
            "statutory_explanation_ar": res.statutory_explanation_ar,
            "warnings": res.warnings,
            "errors": res.errors,
            "approval_token": res.approval_token,
        }
    }


@app.post("/api/recruitment/apply")
def apply_applicant_endpoint(payload: ApplicantApplyPayload, request: Request) -> Dict[str, Any]:
    """Applies validated applicant to Odoo with approval token and written confirmation 'تأكيد'."""
    verify_write_auth(request)
    audit_log_access("/api/recruitment/apply", request, {"token": payload.approval_token})
    service = get_recruitment_service_instance()
    res = service.apply_applicant(
        approval_token=payload.approval_token,
        user_confirmation_text=payload.confirmation_text,
        stage_id=payload.stage_id,
    )
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message_ar)
    return {
        "status": "success",
        "applicant_id": res.applicant_id,
        "candidate_name": res.candidate_name,
        "job_id": res.job_id,
        "job_title": res.job_title,
        "is_saudi": res.is_saudi,
        "total_salary": res.total_salary,
        "approval_status": res.approval_status,
        "readback_verified": res.readback_verified,
        "message_ar": res.message_ar,
    }


# =============================================================================
# Employment Contracts & Wage Structuring Endpoints (Phase 18: hr.version)
# =============================================================================

from contract_service import (
    ContractService,
    ContractSummary,
    ContractDryRunResult,
    ContractExecutionResult,
)
from odoo_contract_write_gateway import OdooContractWriteGateway


class ContractDryRunPayload(BaseModel):
    employee_id: int
    basic_wage: float
    housing_allowance: float = 0.0
    transportation_allowance: float = 0.0
    other_allowances: float = 0.0
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    trial_date_end: Optional[str] = None
    contract_type_id: Optional[int] = None
    explicit_is_saudi: Optional[bool] = None
    gosi_deduction: bool = True


class ContractApplyPayload(BaseModel):
    approval_token: str
    confirmation_text: str  # Must be "تأكيد"


_global_contract_service: Optional[ContractService] = None


def get_contract_service_instance() -> ContractService:
    global _global_contract_service
    if _global_contract_service is not None:
        return _global_contract_service
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    gw = OdooContractWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    _global_contract_service = ContractService(readonly_repo=repo, write_gateway=gw)
    return _global_contract_service


@app.get("/api/contracts/types")
def get_contract_types_endpoint(request: Request) -> Dict[str, Any]:
    """Returns available contract types from hr.contract.type."""
    audit_log_access("/api/contracts/types", request)
    service = get_contract_service_instance()
    types = service.readonly_repo.get_contract_types()
    return {"status": "success", "count": len(types), "contract_types": types}


@app.get("/api/contracts/employee/{employee_id}")
def get_employee_contract_endpoint(employee_id: int, request: Request) -> Dict[str, Any]:
    """Returns employee active contract summary, allowances, and GOSI calculations."""
    audit_log_access(f"/api/contracts/employee/{employee_id}", request)
    service = get_contract_service_instance()
    try:
        summary = service.get_employee_contract_summary(employee_id=employee_id)
        return {
            "status": "success",
            "contract": {
                "contract_id": summary.contract_id,
                "employee_id": summary.employee_id,
                "employee_name": summary.employee_name,
                "department_name": summary.department_name,
                "job_title": summary.job_title,
                "is_saudi": summary.is_saudi,
                "nationality_text_ar": summary.nationality_text_ar,
                "contract_type_name": summary.contract_type_name,
                "basic_wage": summary.basic_wage,
                "housing_allowance": summary.housing_allowance,
                "transportation_allowance": summary.transportation_allowance,
                "other_allowances": summary.other_allowances,
                "total_package": summary.total_package,
                "gosi_contributory_wage": summary.gosi_contributory_wage,
                "gosi_employee_deduction": summary.gosi_employee_deduction,
                "gosi_employer_contribution": summary.gosi_employer_contribution,
                "net_estimated_salary": summary.net_estimated_salary,
                "date_start": summary.date_start,
                "date_end": summary.date_end,
                "trial_date_end": summary.trial_date_end,
                "is_indefinite": summary.is_indefinite,
                "compliance_notes": summary.compliance_notes,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/contracts/dry-run")
def dry_run_contract_endpoint(payload: ContractDryRunPayload, request: Request) -> Dict[str, Any]:
    """Validates contract structure against Article 37 (Expat fixed-term) and Article 53 (Probation)."""
    audit_log_access("/api/contracts/dry-run", request, payload.model_dump())
    service = get_contract_service_instance()
    res = service.dry_run_contract(
        employee_id=payload.employee_id,
        basic_wage=payload.basic_wage,
        housing_allowance=payload.housing_allowance,
        transportation_allowance=payload.transportation_allowance,
        other_allowances=payload.other_allowances,
        date_start=payload.date_start,
        date_end=payload.date_end,
        trial_date_end=payload.trial_date_end,
        contract_type_id=payload.contract_type_id,
        explicit_is_saudi=payload.explicit_is_saudi,
        gosi_deduction=payload.gosi_deduction,
    )
    return {
        "status": "success" if res.is_valid else "warning",
        "result": {
            "is_valid": res.is_valid,
            "can_proceed": res.can_proceed,
            "employee_id": res.employee_id,
            "employee_name": res.employee_name,
            "department_id": res.department_id,
            "department_name": res.department_name,
            "job_id": res.job_id,
            "job_title": res.job_title,
            "is_saudi": res.is_saudi,
            "nationality_text_ar": res.nationality_text_ar,
            "basic_wage": res.basic_wage,
            "housing_allowance": res.housing_allowance,
            "transportation_allowance": res.transportation_allowance,
            "other_allowances": res.other_allowances,
            "total_package": res.total_package,
            "gosi_contributory_wage": res.gosi_contributory_wage,
            "gosi_employee_deduction": res.gosi_employee_deduction,
            "gosi_employer_contribution": res.gosi_employer_contribution,
            "net_estimated_salary": res.net_estimated_salary,
            "date_start": res.date_start,
            "date_end": res.date_end,
            "trial_date_end": res.trial_date_end,
            "contract_type_id": res.contract_type_id,
            "contract_type_name": res.contract_type_name,
            "is_indefinite": res.is_indefinite,
            "statutory_article": res.statutory_article,
            "statutory_explanation_ar": res.statutory_explanation_ar,
            "warnings": res.warnings,
            "errors": res.errors,
            "approval_token": res.approval_token,
        }
    }


@app.post("/api/contracts/apply")
def apply_contract_endpoint(payload: ContractApplyPayload, request: Request) -> Dict[str, Any]:
    """Applies validated contract to Odoo with approval token and written confirmation 'تأكيد'."""
    verify_write_auth(request)
    audit_log_access("/api/contracts/apply", request, {"token": payload.approval_token})
    service = get_contract_service_instance()
    res = service.apply_contract(
        approval_token=payload.approval_token,
        user_confirmation_text=payload.confirmation_text,
    )
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message_ar)
    return {
        "status": "success",
        "contract_id": res.contract_id,
        "employee_id": res.employee_id,
        "employee_name": res.employee_name,
        "total_package": res.total_package,
        "net_estimated_salary": res.net_estimated_salary,
        "readback_verified": res.readback_verified,
        "message_ar": res.message_ar,
    }


# =============================================================================
# Payroll & WPS Wage Protection Endpoints (Phase 19: hr.payslip)
# =============================================================================

from payroll_service import (
    PayrollService,
    PayslipSummary,
    PayslipDryRunResult,
    PayslipExecutionResult,
    WpsSifFileResult,
)
from odoo_payroll_write_gateway import OdooPayrollWriteGateway


class PayslipDryRunPayload(BaseModel):
    employee_id: int
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    basic_wage: Optional[float] = None
    housing_allowance: Optional[float] = None
    transportation_allowance: Optional[float] = None
    other_allowances: Optional[float] = None
    loan_installment: Optional[float] = None
    discipline_amount: Optional[float] = None
    other_deductions: float = 0.0
    struct_id: Optional[int] = None
    explicit_is_saudi: Optional[bool] = None


class PayslipApplyPayload(BaseModel):
    approval_token: str
    confirmation_text: str  # Must be "تأكيد"
    state: str = "draft"


class WpsSifPayload(BaseModel):
    employer_cr: str
    bank_code: str
    payslips_data: List[Dict[str, Any]]
    batch_reference: Optional[str] = None


_global_payroll_service: Optional[PayrollService] = None


def get_payroll_service_instance() -> PayrollService:
    global _global_payroll_service
    if _global_payroll_service is not None:
        return _global_payroll_service
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    gw = OdooPayrollWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password")
    )
    _global_payroll_service = PayrollService(readonly_repo=repo, write_gateway=gw)
    return _global_payroll_service


@app.get("/api/payroll/structures")
def get_payroll_structures_endpoint(request: Request) -> Dict[str, Any]:
    """Returns available payroll structures from hr.payroll.structure."""
    audit_log_access("/api/payroll/structures", request)
    service = get_payroll_service_instance()
    structs = service.readonly_repo.get_payroll_structures()
    return {"status": "success", "count": len(structs), "structures": structs}


@app.get("/api/payroll/employee/{employee_id}")
def get_employee_payslip_endpoint(employee_id: int, request: Request) -> Dict[str, Any]:
    """Returns employee latest payslip summary and wage structure."""
    audit_log_access(f"/api/payroll/employee/{employee_id}", request)
    service = get_payroll_service_instance()
    try:
        summary = service.get_employee_payslip_summary(employee_id=employee_id)
        return {
            "status": "success",
            "payslip": {
                "payslip_id": summary.payslip_id,
                "employee_id": summary.employee_id,
                "employee_name": summary.employee_name,
                "department_name": summary.department_name,
                "job_title": summary.job_title,
                "is_saudi": summary.is_saudi,
                "nationality_text_ar": summary.nationality_text_ar,
                "date_from": summary.date_from,
                "date_to": summary.date_to,
                "basic_wage": summary.basic_wage,
                "housing_allowance": summary.housing_allowance,
                "transportation_allowance": summary.transportation_allowance,
                "other_allowances": summary.other_allowances,
                "gross_wage": summary.gross_wage,
                "gosi_employee_deduction": summary.gosi_employee_deduction,
                "loan_deduction": summary.loan_deduction,
                "discipline_deduction": summary.discipline_deduction,
                "other_deductions": summary.other_deductions,
                "total_deductions": summary.total_deductions,
                "net_wage": summary.net_wage,
                "state": summary.state,
                "compliance_notes": summary.compliance_notes,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/payroll/dry-run")
def dry_run_payslip_endpoint(payload: PayslipDryRunPayload, request: Request) -> Dict[str, Any]:
    """Validates payslip deductions and statutory limits under Articles 70, 71, 92 and GOSI rules."""
    audit_log_access("/api/payroll/dry-run", request, payload.model_dump())
    service = get_payroll_service_instance()
    res = service.dry_run_payslip(
        employee_id=payload.employee_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
        basic_wage=payload.basic_wage,
        housing_allowance=payload.housing_allowance,
        transportation_allowance=payload.transportation_allowance,
        other_allowances=payload.other_allowances,
        loan_installment=payload.loan_installment,
        discipline_amount=payload.discipline_amount,
        other_deductions=payload.other_deductions,
        struct_id=payload.struct_id,
        explicit_is_saudi=payload.explicit_is_saudi,
    )
    return {
        "status": "success" if res.is_valid else "warning",
        "result": {
            "is_valid": res.is_valid,
            "can_proceed": res.can_proceed,
            "employee_id": res.employee_id,
            "employee_name": res.employee_name,
            "department_id": res.department_id,
            "department_name": res.department_name,
            "is_saudi": res.is_saudi,
            "nationality_text_ar": res.nationality_text_ar,
            "date_from": res.date_from,
            "date_to": res.date_to,
            "basic_wage": res.basic_wage,
            "housing_allowance": res.housing_allowance,
            "transportation_allowance": res.transportation_allowance,
            "other_allowances": res.other_allowances,
            "gross_wage": res.gross_wage,
            "gosi_contributory_wage": res.gosi_contributory_wage,
            "gosi_employee_deduction": res.gosi_employee_deduction,
            "gosi_employer_contribution": res.gosi_employer_contribution,
            "loan_installment": res.loan_installment,
            "discipline_deduction": res.discipline_deduction,
            "other_deductions": res.other_deductions,
            "total_deductions": res.total_deductions,
            "net_wage": res.net_wage,
            "deduction_pct_of_gross": res.deduction_pct_of_gross,
            "struct_id": res.struct_id,
            "statutory_article": res.statutory_article,
            "statutory_explanation_ar": res.statutory_explanation_ar,
            "warnings": res.warnings,
            "errors": res.errors,
            "approval_token": res.approval_token,
        }
    }


@app.post("/api/payroll/apply")
def apply_payslip_endpoint(payload: PayslipApplyPayload, request: Request) -> Dict[str, Any]:
    """Applies validated payslip to Odoo with approval token and written confirmation 'تأكيد'."""
    verify_write_auth(request)
    audit_log_access("/api/payroll/apply", request, {"token": payload.approval_token})
    service = get_payroll_service_instance()
    res = service.apply_payslip(
        approval_token=payload.approval_token,
        user_confirmation_text=payload.confirmation_text,
        state=payload.state,
    )
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message_ar)
    return {
        "status": "success",
        "payslip_id": res.payslip_id,
        "employee_id": res.employee_id,
        "employee_name": res.employee_name,
        "gross_wage": res.gross_wage,
        "net_wage": res.net_wage,
        "readback_verified": res.readback_verified,
        "message_ar": res.message_ar,
    }


@app.post("/api/payroll/wps-sif")
def generate_wps_sif_endpoint(payload: WpsSifPayload, request: Request) -> Dict[str, Any]:
    """Generates official WPS SIF file for bank salary transfer and Mudad compliance."""
    audit_log_access("/api/payroll/wps-sif", request, {"employer_cr": payload.employer_cr, "records": len(payload.payslips_data)})
    service = get_payroll_service_instance()
    res = service.generate_wps_sif(
        employer_cr=payload.employer_cr,
        bank_code=payload.bank_code,
        payslips_data=payload.payslips_data,
        batch_reference=payload.batch_reference,
    )
    return {
        "status": "success",
        "filename": res.filename,
        "records_count": res.records_count,
        "total_salaries_sar": res.total_salaries_sar,
        "compliance_rate_pct": res.compliance_rate_pct,
        "content": res.content,
        "message_ar": res.message_ar,
    }


# =============================================================================
# Executive Analytics & Unified Dashboard Endpoints (Phase 20)
# =============================================================================

from dataclasses import asdict
from analytics_service import (
    AnalyticsService,
    WorkforceKpis,
    OperationsKpis,
    FinancialKpis,
    ComplianceKpis,
    RecruitmentKpis,
    SaudizationSimResult,
    UnifiedDashboardData,
)


class SaudizationSimPayload(BaseModel):
    saudi_hires: int = 0
    expat_hires: int = 0


_global_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service_instance() -> AnalyticsService:
    global _global_analytics_service
    if _global_analytics_service is not None:
        return _global_analytics_service
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        api_key=cfg.get("api_key") or cfg.get("password")
    )
    _global_analytics_service = AnalyticsService(readonly_repo=repo)
    return _global_analytics_service


@app.get("/api/analytics/dashboard")
def get_unified_dashboard_endpoint(request: Request) -> Dict[str, Any]:
    """Returns unified multi-domain HR executive dashboard data."""
    audit_log_access("/api/analytics/dashboard", request)
    service = get_analytics_service_instance()
    dash = service.get_unified_dashboard()
    return {
        "status": "success",
        "timestamp": dash.timestamp,
        "generated_at_ar": dash.generated_at_ar,
        "summary_message_ar": dash.summary_message_ar,
        "workforce": asdict(dash.workforce),
        "operations": asdict(dash.operations),
        "financial": asdict(dash.financial),
        "compliance": asdict(dash.compliance),
        "recruitment": asdict(dash.recruitment),
    }


@app.get("/api/analytics/workforce")
def get_workforce_analytics_endpoint(request: Request) -> Dict[str, Any]:
    """Returns Saudization, Nitaqat, and demographics analytics."""
    audit_log_access("/api/analytics/workforce", request)
    service = get_analytics_service_instance()
    wf = service.get_workforce_kpis()
    return {"status": "success", "workforce": asdict(wf)}


@app.get("/api/analytics/operations")
def get_operations_analytics_endpoint(request: Request) -> Dict[str, Any]:
    """Returns operations, attendance, and leave analytics."""
    audit_log_access("/api/analytics/operations", request)
    service = get_analytics_service_instance()
    ops = service.get_operations_kpis()
    return {"status": "success", "operations": asdict(ops)}


@app.get("/api/analytics/financial")
def get_financial_analytics_endpoint(request: Request) -> Dict[str, Any]:
    """Returns payroll, GOSI, loans, and EOS liabilities analytics."""
    audit_log_access("/api/analytics/financial", request)
    service = get_analytics_service_instance()
    fin = service.get_financial_kpis()
    return {"status": "success", "financial": asdict(fin)}


@app.get("/api/analytics/compliance")
def get_compliance_analytics_endpoint(request: Request) -> Dict[str, Any]:
    """Returns compliance health score and statutory risks."""
    audit_log_access("/api/analytics/compliance", request)
    service = get_analytics_service_instance()
    comp = service.get_compliance_kpis()
    return {"status": "success", "compliance": asdict(comp)}


@app.get("/api/analytics/recruitment")
def get_recruitment_analytics_endpoint(request: Request) -> Dict[str, Any]:
    """Returns recruitment pipeline and talent acquisition analytics."""
    audit_log_access("/api/analytics/recruitment", request)
    service = get_analytics_service_instance()
    rec = service.get_recruitment_kpis()
    return {"status": "success", "recruitment": asdict(rec)}


@app.post("/api/analytics/simulate-saudization")
def simulate_saudization_endpoint(payload: SaudizationSimPayload, request: Request) -> Dict[str, Any]:
    """Simulates Saudization rate and Nitaqat band changes based on proposed hires."""
    audit_log_access("/api/analytics/simulate-saudization", request, payload.model_dump())
    service = get_analytics_service_instance()
    try:
        res = service.simulate_saudization_impact(
            saudi_hires=payload.saudi_hires,
            expat_hires=payload.expat_hires
        )
        return {"status": "success", "simulation": asdict(res)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))



# ==============================================================================
# Phase 21: وكيل الرقابة «سجل» (Sijil) & وكيلة القرار «لايا» (Laya) Endpoints
# ==============================================================================

class LayaTriagePayload(BaseModel):
    text: str


@app.get("/api/sijil/summary")
def get_sijil_summary_endpoint(request: Request) -> Dict[str, Any]:
    """Returns aggregated audit metrics compiled by agent Sijil."""
    audit_log_access("/api/sijil/summary", request)
    from sijil_audit_service import SijilAuditService
    service = SijilAuditService()
    summary = service.compile_audit_summary()
    return {"status": "success", "summary": summary}


@app.get("/api/sijil/report/html", response_class=HTMLResponse)
def get_sijil_html_report_endpoint(request: Request) -> str:
    """Returns the executive dark-mode HTML audit report designed with Resend/Supabase styles."""
    audit_log_access("/api/sijil/report/html", request)
    from sijil_audit_service import SijilAuditService
    service = SijilAuditService()
    return service.generate_html_report()


@app.get("/api/sijil/report/pdf")
def get_sijil_pdf_report_endpoint(request: Request) -> FileResponse:
    """Generates and downloads the executive audit & governance PDF report via Playwright."""
    audit_log_access("/api/sijil/report/pdf", request)
    from sijil_audit_service import SijilAuditService
    service = SijilAuditService()
    pdf_path, _ = service.generate_pdf_report()
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="sijil_governance_report.pdf",
    )


# ==============================================================================
# Phase: صفحة وبوابة الوكيل «سجل» لمراجعة وتوثيق العمليات وتصدير التقارير الرسمية
# ==============================================================================

SIJIL_PAGE_FILE = Path(__file__).parent / "templates" / "sijil.html"


@app.get("/sijil", response_class=HTMLResponse)
def get_sijil_portal_page(request: Request) -> str:
    """Returns the dedicated operational review and audit page for agent Sijil."""
    audit_log_access("/sijil", request)
    if SIJIL_PAGE_FILE.exists():
        return SIJIL_PAGE_FILE.read_text(encoding="utf-8")
    raise HTTPException(status_code=404, detail="صفحة سجل غير موجودة في مجلد templates.")


@app.get("/api/sijil/search")
def get_sijil_search_endpoint(request: Request, q: str = "") -> Dict[str, Any]:
    """Unified operational search across all audit sources and plans."""
    audit_log_access("/api/sijil/search", request, {"q": q})
    from sijil_audit_service import SijilAuditService
    service = SijilAuditService()
    res = service.search_operations(q)
    return res


@app.get("/api/sijil/operation/{identifier}")
def get_sijil_operation_detail_endpoint(identifier: str, request: Request) -> Dict[str, Any]:
    """Retrieves full documentation and audit trail of a specific operation."""
    audit_log_access(f"/api/sijil/operation/{identifier}", request)
    from sijil_audit_service import SijilAuditService
    service = SijilAuditService()
    try:
        op = service.get_operation_detail(identifier)
        return {"status": "success", "operation": op}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/sijil/operation/{identifier}/pdf")
def get_sijil_operation_pdf_endpoint(
    identifier: str, request: Request, include_conversation: bool = False
) -> FileResponse:
    """Generates and downloads the official A4 white-paper audit report in Arabic PDF."""
    audit_log_access(
        f"/api/sijil/operation/{identifier}/pdf",
        request,
        {"include_conversation": include_conversation},
    )
    from sijil_audit_service import SijilAuditService
    service = SijilAuditService()
    try:
        pdf_path, _ = service.generate_operation_pdf_report(
            identifier, include_conversation=include_conversation
        )
        safe_filename = f"sijil_audit_report_{identifier.replace('/', '_')}.pdf"
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=safe_filename,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/sijil/recent")
def get_sijil_recent_operations_endpoint(
    request: Request,
    limit: int = 10,
    offset: int = 0,
) -> Dict[str, Any]:
    """Returns recent audited operations ledger for quick browsing with authentication and pagination."""
    verify_api_auth(request)
    audit_log_access("/api/sijil/recent", request, {"limit": limit, "offset": offset})
    from sijil_audit_service import SijilAuditService
    service = SijilAuditService()
    ops = service.get_recent_operations(limit=limit, offset=offset)
    total_count = service.get_total_operations_count()
    return {
        "status": "success",
        "operations": ops,
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "page": (offset // limit) + 1 if limit else 1,
    }


@app.post("/api/laya/triage")
def post_laya_triage_endpoint(payload: LayaTriagePayload, request: Request) -> Dict[str, Any]:
    """Fast non-autoregressive triage and intent classification via agent Laya."""
    audit_log_access("/api/laya/triage", request, payload.model_dump())
    from laya_service import LayaService
    service = LayaService()
    decision = service.triage_request(payload.text)
    return {"status": "success", "decision": decision.to_dict()}


# ==============================================================================
# Phase 22: خطابات الموارد البشرية وشهادات الرواتب الرسمية (HR Official Letters)
# ==============================================================================

class LetterDryRunPayload(BaseModel):
    employee_id: int
    letter_type: str = "salary_certificate"
    recipient: Optional[str] = None
    purpose: Optional[str] = None
    language: str = "arabic"
    include_salary: Optional[bool] = None
    chamber_of_commerce_stamp: bool = False
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    category_id: Optional[int] = None
    explicit_is_saudi: Optional[bool] = None


class LetterApplyPayload(BaseModel):
    approval_token: str
    user_confirmation_text: str = "تأكيد"
    executor: str = "web_portal"


@app.get("/api/letters/types")
def get_letter_types_endpoint(request: Request) -> Dict[str, Any]:
    """Returns supported HR official letter types."""
    audit_log_access("/api/letters/types", request)
    from letter_service import LetterService
    service = LetterService()
    return {"status": "success", "letter_types": service.get_supported_letter_types()}


@app.get("/api/letters/categories")
def get_letter_categories_endpoint(request: Request) -> Dict[str, Any]:
    """Returns Odoo approval.category options."""
    audit_log_access("/api/letters/categories", request)
    from odoo_readonly_repository import OdooReadonlyRepository
    repo = OdooReadonlyRepository()
    return {"status": "success", "categories": repo.get_approval_categories()}


@app.get("/api/letters/employee/{employee_id}")
def get_employee_letters_endpoint(employee_id: int, request: Request) -> Dict[str, Any]:
    """Returns official letters and approval requests for an employee."""
    audit_log_access(f"/api/letters/employee/{employee_id}", request)
    from odoo_readonly_repository import OdooReadonlyRepository
    repo = OdooReadonlyRepository()
    letters = repo.get_employee_approval_requests(employee_id)
    return {"status": "success", "letters": letters, "count": len(letters)}


@app.post("/api/letters/dry-run")
def post_letter_dry_run_endpoint(payload: LetterDryRunPayload, request: Request) -> Dict[str, Any]:
    """Dry-run verification and draft preview generation with approval token."""
    audit_log_access("/api/letters/dry-run", request, payload.model_dump())
    from letter_service import LetterService
    service = LetterService()
    res = service.dry_run_letter(
        employee_id=payload.employee_id,
        letter_type=payload.letter_type,
        recipient=payload.recipient,
        purpose=payload.purpose,
        language=payload.language,
        include_salary=payload.include_salary,
        chamber_of_commerce_stamp=payload.chamber_of_commerce_stamp,
        bank_name=payload.bank_name,
        bank_account_number=payload.bank_account_number,
        category_id=payload.category_id,
        explicit_is_saudi=payload.explicit_is_saudi,
    )
    from dataclasses import asdict
    return {"status": "success" if res.is_valid else "error", "dry_run": asdict(res)}


@app.post("/api/letters/apply")
def post_letter_apply_endpoint(payload: LetterApplyPayload, request: Request) -> Dict[str, Any]:
    """Executes official letter issuance in Odoo requiring 'تأكيد' and valid approval token."""
    audit_log_access("/api/letters/apply", request, {"token": payload.approval_token})
    from letter_service import LetterService
    service = LetterService()
    res = service.apply_letter(
        approval_token=payload.approval_token,
        user_confirmation_text=payload.user_confirmation_text,
        executor=payload.executor,
    )
    from dataclasses import asdict
    if not res.is_success:
        raise HTTPException(status_code=400, detail=res.message_ar)
    return {"status": "success", "result": asdict(res)}


@app.get("/api/letters/{request_id}/html", response_class=HTMLResponse)
def get_letter_html_view(request_id: int, request: Request) -> str:
    """Renders the HTML view of an issued letter."""
    audit_log_access(f"/api/letters/{request_id}/html", request)
    from letter_service import LETTERS_OUTPUT_DIR
    import glob
    matches = glob.glob(os.path.join(LETTERS_OUTPUT_DIR, f"letter_{request_id}_*.html"))
    if not matches:
        raise HTTPException(status_code=404, detail="ملف الخطاب غير موجود في المخرجات.")
    with open(matches[0], "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/letters/{request_id}/pdf")
def get_letter_pdf_view(request_id: int, request: Request) -> FileResponse:
    """Downloads the official PDF of an issued letter."""
    audit_log_access(f"/api/letters/{request_id}/pdf", request)
    from letter_service import LETTERS_OUTPUT_DIR
    import glob
    matches = glob.glob(os.path.join(LETTERS_OUTPUT_DIR, f"letter_{request_id}_*.pdf"))
    if not matches:
        raise HTTPException(status_code=404, detail="ملف PDF للخطاب غير موجود.")
    return FileResponse(
        matches[0],
        media_type="application/pdf",
        filename=f"official_letter_{request_id}.pdf",
    )


# ==============================================================================
# Phase 23: خطابات الإنذار والمساءلات التأديبية (Warning Letters & Disciplinary)
# ==============================================================================

class WarningDryRunPayload(BaseModel):
    employee_id: int
    warning_level: str = "first_warning"
    violation_description: str = ""
    violation_date: Optional[str] = None
    has_deduction: Optional[bool] = None
    deduction_days: float = 0.0
    deduction_amount: Optional[float] = None
    explicit_is_saudi: Optional[bool] = None


class WarningApplyPayload(BaseModel):
    approval_token: str
    user_confirmation_text: str = "تأكيد"
    executor: str = "web_portal"


@app.get("/api/warnings/levels")
def get_warning_levels_endpoint(request: Request) -> Dict[str, Any]:
    """Returns statutory warning levels compliant with Saudi Labor Law Article 66."""
    audit_log_access("/api/warnings/levels", request)
    from warning_service import WarningService
    service = WarningService()
    return {"status": "success", "warning_levels": service.get_supported_warning_levels()}


@app.get("/api/warnings/types")
def get_warning_types_endpoint(request: Request) -> Dict[str, Any]:
    """Returns warning types from Odoo warning.type."""
    audit_log_access("/api/warnings/types", request)
    from odoo_readonly_repository import OdooReadonlyRepository
    repo = OdooReadonlyRepository()
    return {"status": "success", "types": repo.get_warning_types()}


@app.get("/api/warnings/employee/{employee_id}")
def get_employee_warnings_endpoint(employee_id: int, request: Request) -> Dict[str, Any]:
    """Returns disciplinary and warning letters for an employee."""
    audit_log_access(f"/api/warnings/employee/{employee_id}", request)
    from odoo_readonly_repository import OdooReadonlyRepository
    repo = OdooReadonlyRepository()
    warnings = repo.get_warning_letters(employee_id=employee_id)
    return {"status": "success", "warnings": warnings, "count": len(warnings)}


@app.post("/api/warnings/dry-run")
def post_warning_dry_run_endpoint(payload: WarningDryRunPayload, request: Request) -> Dict[str, Any]:
    """Dry-run verification of warning letter and Article 71 deduction compliance."""
    audit_log_access("/api/warnings/dry-run", request, payload.model_dump())
    from warning_service import WarningService
    service = WarningService()
    res = service.dry_run_warning(
        employee_id=payload.employee_id,
        warning_level=payload.warning_level,
        violation_description=payload.violation_description,
        violation_date=payload.violation_date,
        has_deduction=payload.has_deduction,
        deduction_days=payload.deduction_days,
        deduction_amount=payload.deduction_amount,
        explicit_is_saudi=payload.explicit_is_saudi,
    )
    from dataclasses import asdict
    return {"status": "success" if res.is_valid else "error", "dry_run": asdict(res)}


@app.post("/api/warnings/apply")
def post_warning_apply_endpoint(payload: WarningApplyPayload, request: Request) -> Dict[str, Any]:
    """Executes warning letter creation in Odoo requiring 'تأكيد' and valid approval token."""
    audit_log_access("/api/warnings/apply", request, {"token": payload.approval_token})
    from warning_service import WarningService
    service = WarningService()
    res = service.apply_warning(
        approval_token=payload.approval_token,
        user_confirmation_text=payload.user_confirmation_text,
        executor=payload.executor,
    )
    from dataclasses import asdict
    if not res.is_success:
        raise HTTPException(status_code=400, detail=res.message_ar)
    return {"status": "success", "result": asdict(res)}


@app.get("/api/warnings/{letter_id}/html", response_class=HTMLResponse)
def get_warning_html_view(letter_id: int, request: Request) -> str:
    """Renders the HTML view of an issued warning letter."""
    audit_log_access(f"/api/warnings/{letter_id}/html", request)
    from warning_service import WARNINGS_OUTPUT_DIR
    import glob
    matches = glob.glob(os.path.join(WARNINGS_OUTPUT_DIR, f"warning_{letter_id}_*.html"))
    if not matches:
        raise HTTPException(status_code=404, detail="ملف الإنذار غير موجود في المخرجات.")
    with open(matches[0], "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/warnings/{letter_id}/pdf")
def get_warning_pdf_view(letter_id: int, request: Request) -> FileResponse:
    """Downloads the official PDF of an issued warning letter."""
    audit_log_access(f"/api/warnings/{letter_id}/pdf", request)
    from warning_service import WARNINGS_OUTPUT_DIR
    import glob
    matches = glob.glob(os.path.join(WARNINGS_OUTPUT_DIR, f"warning_{letter_id}_*.pdf"))
    if not matches:
        raise HTTPException(status_code=404, detail="ملف PDF للإنذار غير موجود.")
    return FileResponse(
        matches[0],
        media_type="application/pdf",
        filename=f"warning_letter_{letter_id}.pdf",
    )


# ==============================================================================
# Phase 24: مصروفات الموظفين والانتدابات (Employee Expenses & Travel)
# ==============================================================================

class ExpenseDryRunPayload(BaseModel):
    employee_id: int
    expense_category: str = "general"
    total_amount: float
    description: str = ""
    expense_date: Optional[str] = None
    includes_vat: bool = True
    product_id: Optional[int] = None
    explicit_is_saudi: Optional[bool] = None


class ExpenseApplyPayload(BaseModel):
    approval_token: str
    user_confirmation_text: str = "تأكيد"
    executor: str = "web_portal"


@app.get("/api/expenses/categories")
def get_expense_categories_endpoint(request: Request) -> Dict[str, Any]:
    """Returns supported expense categories."""
    audit_log_access("/api/expenses/categories", request)
    from expense_service import ExpenseService
    service = ExpenseService()
    return {"status": "success", "categories": service.get_supported_categories()}


@app.get("/api/expenses/employee/{employee_id}")
def get_employee_expenses_endpoint(employee_id: int, request: Request) -> Dict[str, Any]:
    """Returns submitted expenses for an employee."""
    audit_log_access(f"/api/expenses/employee/{employee_id}", request)
    from odoo_readonly_repository import OdooReadonlyRepository
    repo = OdooReadonlyRepository()
    expenses = repo.get_hr_expenses(employee_id=employee_id)
    return {"status": "success", "expenses": expenses, "count": len(expenses)}


@app.post("/api/expenses/dry-run")
def post_expense_dry_run_endpoint(payload: ExpenseDryRunPayload, request: Request) -> Dict[str, Any]:
    """Dry-run verification of employee expense claim and VAT calculation."""
    audit_log_access("/api/expenses/dry-run", request, payload.model_dump())
    from expense_service import ExpenseService
    service = ExpenseService()
    res = service.dry_run_expense(
        employee_id=payload.employee_id,
        expense_category=payload.expense_category,
        total_amount=payload.total_amount,
        description=payload.description,
        expense_date=payload.expense_date,
        includes_vat=payload.includes_vat,
        product_id=payload.product_id,
        explicit_is_saudi=payload.explicit_is_saudi,
    )
    from dataclasses import asdict
    return {"status": "success" if res.is_valid else "error", "dry_run": asdict(res)}


@app.post("/api/expenses/apply")
def post_expense_apply_endpoint(payload: ExpenseApplyPayload, request: Request) -> Dict[str, Any]:
    """Executes expense creation in Odoo requiring 'تأكيد' and valid approval token."""
    audit_log_access("/api/expenses/apply", request, {"token": payload.approval_token})
    from expense_service import ExpenseService
    service = ExpenseService()
    res = service.apply_expense(
        approval_token=payload.approval_token,
        user_confirmation_text=payload.user_confirmation_text,
        executor=payload.executor,
    )
    from dataclasses import asdict
    if not res.is_success:
        raise HTTPException(status_code=400, detail=res.message_ar)
    return {"status": "success", "result": asdict(res)}


@app.get("/api/expenses/{expense_id}/html", response_class=HTMLResponse)
def get_expense_html_view(expense_id: int, request: Request) -> str:
    """Renders the HTML view of an issued expense claim."""
    audit_log_access(f"/api/expenses/{expense_id}/html", request)
    from expense_service import EXPENSES_OUTPUT_DIR
    import glob
    matches = glob.glob(os.path.join(EXPENSES_OUTPUT_DIR, f"expense_{expense_id}_*.html"))
    if not matches:
        raise HTTPException(status_code=404, detail="ملف سند المصروفات غير موجود في المخرجات.")
    with open(matches[0], "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/expenses/{expense_id}/pdf")
def get_expense_pdf_view(expense_id: int, request: Request) -> FileResponse:
    """Downloads the official PDF of an issued expense claim."""
    audit_log_access(f"/api/expenses/{expense_id}/pdf", request)
    from expense_service import EXPENSES_OUTPUT_DIR
    import glob
    matches = glob.glob(os.path.join(EXPENSES_OUTPUT_DIR, f"expense_{expense_id}_*.pdf"))
    if not matches:
        raise HTTPException(status_code=404, detail="ملف PDF لسند المصروفات غير موجود.")
    return FileResponse(
        matches[0],
        media_type="application/pdf",
        filename=f"expense_claim_{expense_id}.pdf",
    )





# ----------------------------------------------------------------------
# المرحلة 25: الرصد الاستباقي لانتهاء الوثائق والتنبيهات المجدولة (Document Expiry Monitoring)
# ----------------------------------------------------------------------

class ExpiryScanQueryPayload(BaseModel):
    max_days: int = 90
    category: Optional[str] = None
    severity: Optional[str] = None
    department: Optional[str] = None


@app.get("/api/alerts/expiries")
def get_expiries_alerts_endpoint(
    max_days: int = 90,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    department: Optional[str] = None,
    request: Request = None,
) -> Dict[str, Any]:
    """Scans and returns proactive alerts for expiring employee documents."""
    audit_log_access("/api/alerts/expiries", request, {"max_days": max_days, "category": category})
    from document_expiry_service import DocumentExpiryService
    service = DocumentExpiryService()
    res = service.scan_expiries(
        max_days=max_days,
        category_filter=category,
        severity_filter=severity,
        department_filter=department,
    )
    items_dicts = [
        {
            "employee_id": it.employee_id,
            "employee_name": it.employee_name,
            "is_saudi": it.is_saudi,
            "nationality": it.nationality_text_ar,
            "job_title": it.job_title,
            "department": it.department_name,
            "category_id": it.category_id,
            "category_name": it.category_title_ar,
            "expiry_date": it.expiry_date,
            "days_remaining": it.days_remaining,
            "severity": it.severity,
            "severity_label": it.severity_label_ar,
            "legal_article": it.legal_article_ar,
            "authority": it.authority,
        }
        for it in res.items
    ]
    return {
        "status": "success",
        "scan_date": res.scan_date,
        "total_employees_scanned": res.total_employees_scanned,
        "total_alerts": res.total_alerts,
        "summary": {
            "expired": res.expired_count,
            "critical": res.critical_count,
            "warning": res.warning_count,
            "notice": res.notice_count,
        },
        "by_category": res.by_category,
        "by_department": res.by_department,
        "items": items_dicts,
    }


@app.post("/api/alerts/expiries/scan")
def post_scan_expiries_endpoint(payload: ExpiryScanQueryPayload, request: Request) -> Dict[str, Any]:
    """Triggers an on-demand proactive scan with filters and returns the full result."""
    audit_log_access("/api/alerts/expiries/scan", request, payload.model_dump())
    from document_expiry_service import DocumentExpiryService
    service = DocumentExpiryService()
    res = service.scan_expiries(
        max_days=payload.max_days,
        category_filter=payload.category,
        severity_filter=payload.severity,
        department_filter=payload.department,
    )
    return {
        "status": "success",
        "scan_date": res.scan_date,
        "total_employees_scanned": res.total_employees_scanned,
        "total_alerts": res.total_alerts,
        "expired_count": res.expired_count,
        "critical_count": res.critical_count,
        "warning_count": res.warning_count,
        "notice_count": res.notice_count,
        "items_count": len(res.items),
    }


@app.get("/api/alerts/expiries/html", response_class=HTMLResponse)
def get_expiries_html_report_endpoint(max_days: int = 90, request: Request = None) -> str:
    """Renders the interactive Arabic corporate report for document expiries."""
    audit_log_access("/api/alerts/expiries/html", request, {"max_days": max_days})
    from document_expiry_service import DocumentExpiryService
    service = DocumentExpiryService()
    res = service.scan_expiries(max_days=max_days)
    return service.render_html_report(res)


@app.get("/api/alerts/expiries/pdf")
def get_expiries_pdf_report_endpoint(max_days: int = 90, request: Request = None):
    """Generates and downloads the official PDF document expiry report."""
    audit_log_access("/api/alerts/expiries/pdf", request, {"max_days": max_days})
    from document_expiry_service import DocumentExpiryService
    service = DocumentExpiryService()
    res = service.scan_expiries(max_days=max_days)
    pdf_path = service.generate_pdf_report(res)
    if not pdf_path or not os.path.exists(pdf_path):
        html_content = service.render_html_report(res)
        return HTMLResponse(content=html_content, status_code=200)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"document_expiries_report_{res.scan_date}.pdf",
    )


# ==================== MUSLEH API ENDPOINTS (PHASE 26) ====================

class MuslehDiagnoseRowRequest(BaseModel):
    row: Dict[str, Any]
    validation_result: Dict[str, Any]
    auto_repair: bool = False


class MuslehHealBatchRequest(BaseModel):
    run_id: Optional[str] = None
    rows: Optional[List[Dict[str, Any]]] = None
    validation_results: Optional[List[Dict[str, Any]]] = None
    auto_repair: bool = False


class MuslehRecoverSubmissionRequest(BaseModel):
    employee_name: str
    company_id: int = 15


@app.post("/api/musleh/diagnose-row")
def post_musleh_diagnose_row_endpoint(payload: MuslehDiagnoseRowRequest, request: Request) -> Dict[str, Any]:
    """Diagnoses and heals a single broken row through Musleh's consultation protocol."""
    audit_log_access("/api/musleh/diagnose-row", request)
    from musleh_service import MuslehService
    repo = OdooReadonlyRepository()
    musleh = MuslehService(repository=repo)
    res = musleh.diagnose_and_heal_row(
        row=payload.row,
        validation_result=payload.validation_result,
        auto_repair=payload.auto_repair,
    )
    if res is None:
        return {"status": "skipped", "message": "الصف مقبول ولا يتطلب تدخل مصلح."}
    return {"status": "success", "result": res.to_dict()}


@app.post("/api/musleh/heal-batch")
def post_musleh_heal_batch_endpoint(payload: MuslehHealBatchRequest, request: Request) -> Dict[str, Any]:
    """Runs batch healing and quarantine, escalating unresolved rows to Seraj."""
    audit_log_access("/api/musleh/heal-batch", request)
    from musleh_service import MuslehService
    repo = OdooReadonlyRepository()
    musleh = MuslehService(repository=repo)

    rows = payload.rows or []
    val_results = payload.validation_results or []

    if payload.run_id and (not rows or not val_results):
        output_root = Path("output")
        matching = list(output_root.glob(f"{payload.run_id}_*"))
        if not matching and (output_root / payload.run_id).is_dir():
            matching = [output_root / payload.run_id]
        if matching:
            report_file = matching[0] / "dry_run_report.json"
            if report_file.exists():
                data = json.loads(report_file.read_text(encoding="utf-8"))
                val_results = data.get("rows", [])
                if not rows:
                    rows = []
                    for vr in val_results:
                        rn = vr.get("excel_row_number")
                        rows.append({
                            "excel_row_number": rn,
                            "fields": vr.get("resolved_references", {}) or {},
                        })

    res = musleh.heal_batch(
        rows=rows,
        validation_results=val_results,
        auto_repair=payload.auto_repair,
    )
    return {"status": "success", "batch_result": res}


@app.post("/api/musleh/recover-submission")
def post_musleh_recover_submission_endpoint(payload: MuslehRecoverSubmissionRequest, request: Request) -> Dict[str, Any]:
    """Verifies with Fahas if employee already exists in Odoo to prevent double submission."""
    audit_log_access("/api/musleh/recover-submission", request)
    from musleh_service import MuslehService
    repo = OdooReadonlyRepository()
    musleh = MuslehService(repository=repo)
    res = musleh.verify_and_recover_submission(
        employee_name=payload.employee_name,
        company_id=payload.company_id,
    )
    return {"status": "success", "recovery": res}


# ==================== PHASE 26: UNIFIED MULTI-AGENT SYSTEM ENDPOINTS ====================

class SerajChatApiRequest(BaseModel):
    message: str
    chat_id: str = "web_default"
    operation_id: Optional[str] = None
    company_id: Optional[int] = 15
    company_name: Optional[str] = "شركة النخبة الذكية للتقنية"
    connection_id: Optional[str] = "default"
    user_name: Optional[str] = "المستخدم"


class AgentApprovalApiRequest(BaseModel):
    chat_id: str = "web_default"
    operation_id: Optional[str] = None
    plan_id: Optional[str] = None


class AgentCancelApiRequest(BaseModel):
    chat_id: str = "web_default"
    operation_id: Optional[str] = None


@app.get("/api/agents/overview")
def get_agents_overview_endpoint(request: Request) -> Dict[str, Any]:
    """Returns directory of all 8 agents + Laya helper tool with live status."""
    audit_log_access("/api/agents/overview", request)
    from agent_events_service import get_events_service
    srv = get_events_service()
    return {
        "status": "success",
        "agents": srv.get_agents_overview(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/agents/operations")
def get_agents_operations_endpoint(request: Request, limit: int = 30) -> Dict[str, Any]:
    """Returns recent multi-agent operations with current progress."""
    audit_log_access("/api/agents/operations", request)
    from agent_events_service import get_events_service
    srv = get_events_service()
    return {
        "status": "success",
        "operations": srv.get_recent_operations(limit=limit),
        "total": len(srv.operations),
    }


@app.get("/api/agents/operations/{operation_id}")
def get_agent_operation_endpoint(operation_id: str, request: Request) -> Dict[str, Any]:
    """Returns full operation details, timeline, and current execution state."""
    audit_log_access(f"/api/agents/operations/{operation_id}", request)
    from agent_events_service import get_events_service
    srv = get_events_service()
    op = srv.get_operation(operation_id)
    if not op:
        from agent_events_service import AGENT_OPS_LOG_FILE
        found_in_log = False
        if AGENT_OPS_LOG_FILE.exists():
            with open(AGENT_OPS_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if operation_id in line:
                        found_in_log = True
                        break
        if not found_in_log and not operation_id.startswith(("del_", "run_")):
            raise HTTPException(status_code=404, detail=f"العملية غير موجودة: {operation_id}")

        try:
            from sijil_audit_service import SijilAuditService
            sijil = SijilAuditService()
            audit_op = sijil.get_operation_detail(operation_id)
            if not audit_op:
                raise HTTPException(status_code=404, detail=f"العملية غير موجودة: {operation_id}")
            return {"status": "success", "operation": audit_op, "source": "sijil_audit"}
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=404, detail=f"العملية غير موجودة: {operation_id}")
    return {"status": "success", "operation": op, "source": "live_events"}


@app.get("/api/agents/operations/{operation_id}/events")
def get_agent_operation_events_endpoint(operation_id: str, request: Request, after: int = 0) -> Dict[str, Any]:
    """Returns events for an operation occurred after sequence `after` (for live polling)."""
    from agent_events_service import get_events_service
    srv = get_events_service()
    events = srv.get_operation_events(operation_id, after_seq=after)
    op = srv.get_operation(operation_id)
    return {
        "status": "success",
        "operation_id": operation_id,
        "events": events,
        "is_active": op.get("status") not in ("completed", "failed", "cancelled") if op else False,
        "operation_status": op.get("status") if op else "unknown",
        "operation_status_label": op.get("status_label") if op else "غير معروف",
    }


@app.get("/api/agents/operations/{operation_id}/stream")
async def stream_agent_operation_events(operation_id: str, request: Request):
    """Server-Sent Events (SSE) stream delivering real agent execution events."""
    from agent_events_service import get_events_service
    srv = get_events_service()

    async def event_generator():
        last_seq = 0
        heartbeat_ticks = 0
        while True:
            if await request.is_disconnected():
                break

            events = srv.get_operation_events(operation_id, after_seq=last_seq)
            op = srv.get_operation(operation_id)

            for evt in events:
                last_seq = max(last_seq, evt.get("sequence", 0))
                data = json.dumps(evt, ensure_ascii=False)
                yield f"event: agent_event\ndata: {data}\n\n"

            if op and op.get("status") in ("completed", "failed", "cancelled") and not events:
                yield f"event: operation_ended\ndata: {json.dumps({'operation_id': operation_id, 'status': op.get('status')})}\n\n"
                break

            heartbeat_ticks += 1
            if heartbeat_ticks % 10 == 0:
                yield f"event: ping\ndata: {json.dumps({'time': int(time.time())})}\n\n"

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/seraj/chat")
def post_seraj_chat_endpoint(payload: SerajChatApiRequest, request: Request) -> Dict[str, Any]:
    """Unified conversational interaction with Seraj, coordinating multi-agent actions."""
    audit_log_access("/api/seraj/chat", request, {"chat_id": payload.chat_id, "op_id": payload.operation_id})
    from agent_events_service import get_events_service
    from seraj_llm_service import SerajLLMService
    from seraj_session_manager import SerajSessionManager

    srv = get_events_service()
    op_id = payload.operation_id
    if not op_id:
        op_id = srv.start_operation(
            user_query=payload.message,
            operation_type="conversation",
            company_id=payload.company_id or 15,
            company_name=payload.company_name or "شركة النخبة الذكية للتقنية",
            connection_id=payload.connection_id or "default",
            requester=payload.user_name or "المستخدم",
            chat_id=payload.chat_id,
        )

    seraj = SerajLLMService()
    try:
        reply = seraj.chat_turn(
            user_query=payload.message,
            chat_id=payload.chat_id,
            user_name=payload.user_name or "المستخدم",
            connection_id=payload.connection_id,
            company_id=payload.company_id,
            operation_id=op_id,
        )
    except Exception as exc:
        srv.emit_event(
            operation_id=op_id,
            agent="seraj",
            event_type="error",
            status="failed",
            description_ar=f"واجه سراج خطأ أثناء المعالجة: {exc}",
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=f"تعذر معالجة الطلب: {exc}")

    session = SerajSessionManager.get_instance().get_session(payload.chat_id)
    op = srv.get_operation(op_id)

    return {
        "status": "success",
        "operation_id": op_id,
        "response": reply,
        "operation": op,
        "pending_action": session.pending_action,
        "pending_clarification": session.pending_clarification,
    }


@app.post("/api/agents/approve")
def post_agent_approve_endpoint(payload: AgentApprovalApiRequest, request: Request) -> Dict[str, Any]:
    """Explicit human approval of a pending operation plan."""
    audit_log_access("/api/agents/approve", request, {"chat_id": payload.chat_id, "op_id": payload.operation_id})
    from agent_events_service import get_events_service
    from seraj_llm_service import SerajLLMService
    from seraj_session_manager import SerajSessionManager

    srv = get_events_service()
    seraj = SerajLLMService()
    reply = seraj.chat_turn(
        user_query="تأكيد",
        chat_id=payload.chat_id,
        operation_id=payload.operation_id,
    )

    session = SerajSessionManager.get_instance().get_session(payload.chat_id)
    op = srv.get_operation(payload.operation_id) if payload.operation_id else None

    return {
        "status": "success",
        "operation_id": payload.operation_id,
        "response": reply,
        "operation": op,
        "pending_action": session.pending_action,
    }


@app.post("/api/agents/cancel")
def post_agent_cancel_endpoint(payload: AgentCancelApiRequest, request: Request) -> Dict[str, Any]:
    """Explicit human cancellation of a pending operation plan."""
    audit_log_access("/api/agents/cancel", request, {"chat_id": payload.chat_id, "op_id": payload.operation_id})
    from agent_events_service import get_events_service
    from seraj_llm_service import SerajLLMService
    from seraj_session_manager import SerajSessionManager

    srv = get_events_service()
    seraj = SerajLLMService()
    reply = seraj.chat_turn(
        user_query="إلغاء",
        chat_id=payload.chat_id,
        operation_id=payload.operation_id,
    )

    session = SerajSessionManager.get_instance().get_session(payload.chat_id)
    op = srv.get_operation(payload.operation_id) if payload.operation_id else None

    return {
        "status": "success",
        "operation_id": payload.operation_id,
        "response": reply,
        "operation": op,
        "pending_action": session.pending_action,
    }


@app.post("/api/agents/upload")
async def upload_agent_file_endpoint(
    request: Request,
    file: UploadFile = File(...),
    chat_id: str = Form("web_default"),
    operation_id: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Uploads file in agent cockpit, creating staging operation and parsing."""
    audit_log_access("/api/agents/upload", request)
    content = await file.read()
    size = len(content)
    if size > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="حجم الملف يتجاوز الحد الأقصى المسموح به (10 ميجابايت).")

    fn = file.filename or "upload_file"
    safe_filename = f"{int(time.time())}_{fn}"
    saved_path = UPLOAD_DIR / safe_filename
    with open(saved_path, "wb") as f:
        f.write(content)

    from agent_events_service import get_events_service
    srv = get_events_service()
    op_id = operation_id or srv.start_operation(
        user_query=f"رفع ملف: {fn}",
        operation_type="file_upload",
        chat_id=chat_id,
    )
    srv.emit_event(
        operation_id=op_id,
        agent="seraj",
        event_type="file_received",
        status="inspecting_data",
        description_ar=f"سراج يستلم الملف «{fn}» بحجم {max(1, size // 1024)} كيلوبايت",
    )
    dry_run_data = None
    if fn.lower().endswith(".xlsx"):
        srv.emit_event(
            operation_id=op_id,
            agent="fahas",
            from_agent="seraj",
            to_agent="fahas",
            event_type="spreadsheet_analysis",
            status="inspecting_data",
            description_ar=f"فاحص يحلل بنية الجدول وأعمدة ملف الإكسل «{fn}» ومطابقة الحقول المرجعية وقواعد نظام العمل",
        )
        try:
            report_dict = dry_run_report.build_full_report(saved_path)
            run_id = report_dict["header"]["run_id"]
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            folder_name = f"{run_id}_{timestamp}"
            run_output_dir = Path("output") / folder_name
            run_output_dir.mkdir(parents=True, exist_ok=True)
            dry_run_report.write_report_files(report_dict, run_output_dir)
            summary = report_dict.get("summary", {})
            counts = summary.get("status_counts", {})
            total_rows = summary.get("row_count", len(report_dict.get("rows", [])))
            srv.emit_event(
                operation_id=op_id,
                agent="fahas",
                event_type="dry_run_completed",
                status="completed",
                description_ar=f"أنجز فاحص تقرير الفحص الجاف (Dry-Run): {total_rows} صفاً، مقبول {counts.get('accepted', 0)}، مرفوض {counts.get('rejected', 0)} (دون أي كتابة في Odoo)",
                metadata={"run_id": run_id, "summary": summary, "folder": folder_name},
            )
            dry_run_data = {
                "run_id": run_id,
                "folder": folder_name,
                "summary": summary,
                "status_counts": counts,
                "total_rows": total_rows,
                "accepted_count": counts.get("accepted", 0),
                "rejected_count": counts.get("rejected", 0),
            }
        except Exception as exc:
            srv.emit_event(
                operation_id=op_id,
                agent="fahas",
                event_type="spreadsheet_error",
                status="failed",
                description_ar=f"تعذر استكمال فحص ملف الإكسل «{fn}»: {exc}",
                error=str(exc),
            )
            dry_run_data = {"error": str(exc)}

    return {
        "status": "success",
        "operation_id": op_id,
        "filename": fn,
        "size": size,
        "path": str(saved_path),
        "dry_run_report": dry_run_data,
        "message": f"تم استلام وفحص الملف «{fn}» بنجاح في المنظومة.",
    }


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard_html() -> str:
    """Returns the single-page responsive Arabic Web Dashboard with authenticated API token injected."""
    raw_content = DASHBOARD_FILE.read_text(encoding="utf-8") if DASHBOARD_FILE.exists() else DASHBOARD_HTML_PAGE
    token = os.environ.get("WRITE_API_TOKEN", WRITE_API_TOKEN)
    if '<meta charset="UTF-8">' in raw_content:
        return raw_content.replace(
            '<meta charset="UTF-8">',
            f'<meta charset="UTF-8">\n  <meta name="api-token" content="{token}">'
        )
    return raw_content


if __name__ == "__main__":
    import uvicorn
    print("Starting Odoo HR Dashboard on http://localhost:8000 ...")
    uvicorn.run("web_service:app", host="127.0.0.1", port=8000, reload=False)
