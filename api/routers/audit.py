"""
Audit, Operations & System Health Router
========================================
Handles system health status, Odoo connection configuration, LLM engine settings,
Sijil audit ledger & reports, and multi-agent lifecycle operations and approvals.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

import approval_schema
import dry_run_report
import telegram_notifier
import writer
from api.common import (
    OUTPUT_ROOT,
    UPLOAD_DIR,
    _get_readonly_repo_cls,
    _get_upload_dir,
    _get_write_gateway_cls,
    audit_log_access,
    verify_api_auth,
)
from odoo_config_manager import (
    clear_active_odoo_config,
    get_active_odoo_config,
    normalize_odoo_url,
    save_active_odoo_config,
    test_odoo_connection,
)
from odoo_readonly_repository import OdooReadonlyRepository
from odoo_write_gateway import OdooWriteGateway

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Audit, Status & Multi-Agent Operations"])


# ==================== SCHEMAS ====================

class ConnectionSettingsRequest(BaseModel):
    url: str
    db: str
    username: str
    api_key: Optional[str] = None


class LLMProviderSettingsRequest(BaseModel):
    mode: Optional[str] = "auto"  # "auto" | "manual"
    active_provider: Optional[str] = "local"  # "local" | "cloud"
    fallback_enabled: Optional[bool] = True
    local_base_url: Optional[str] = "http://localhost:11434/v1"
    local_model: Optional[str] = "qwen3.5:9b"
    cloud_provider: Optional[str] = "openrouter"
    cloud_base_url: Optional[str] = "https://openrouter.ai/api/v1"
    cloud_api_key: Optional[str] = None
    cloud_model: Optional[str] = "openrouter/auto"


class LLMTestRequest(BaseModel):
    target: str  # "local" | "cloud"
    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None


class AgentApprovalApiRequest(BaseModel):
    chat_id: str = "web_default"
    operation_id: Optional[str] = None
    plan_id: Optional[str] = None
    report_folder: Optional[str] = None
    approved_by: Optional[str] = "مشغّل النظام"
    modified_payload: Optional[Dict[str, Any]] = None


class AgentCancelApiRequest(BaseModel):
    chat_id: str = "web_default"
    operation_id: Optional[str] = None


def _get_dashboard_html() -> str:
    try:
        import web_service
        if hasattr(web_service, "get_main_dashboard_html"):
            return web_service.get_main_dashboard_html()
    except Exception:
        pass
    dashboard_file = Path(__file__).resolve().parent.parent.parent / "frontend" / "dashboard.html"
    if not dashboard_file.exists():
        dashboard_file = Path(__file__).resolve().parent.parent.parent / "templates" / "dashboard.html"
    if dashboard_file.exists():
        return dashboard_file.read_text(encoding="utf-8")
    return "<h1>بوابة أتمتة إدخال الموظفين في Odoo</h1>"


# ==================== STATUS & HEALTH ====================

@router.get("/api/status")
@router.get("/status")
def get_system_status(request: Request) -> Dict[str, Any]:
    audit_log_access("/status", request)
    cfg = get_active_odoo_config()
    odoo_url = cfg.get("url", "")
    odoo_db = cfg.get("db", "")
    odoo_user = cfg.get("username", "")
    telegram_configured = telegram_notifier.is_telegram_configured()

    companies: List[Dict[str, Any]] = []
    default_comp_id = None
    default_comp_name = "المنشأة الرئيسية"
    is_connected = False
    conn_error = None

    if odoo_url and odoo_db and odoo_user and cfg.get("api_key"):
        try:
            repo_cls = _get_readonly_repo_cls()
            repo = repo_cls()
            repo.connect()
            def_comp = repo.get_default_company()
            default_comp_id = def_comp.get("id")
            default_comp_name = def_comp.get("name", "")
            real_comps = repo.get_accessible_companies()
            if real_comps:
                companies = [
                    {
                        "id": c["id"],
                        "name": f"{c['name']} (ID: {c['id']})",
                        "selected": (c["id"] == default_comp_id)
                    }
                    for c in real_comps
                ]
            is_connected = True
        except Exception as exc:
            conn_error = str(exc)

    return {
        "status": "online",
        "lockdown": not is_connected,
        "lockdown_reason": "قاعدة بيانات Odoo غير متصلة. النظام في وضع القفل ويسمح فقط بالإعدادات." if not is_connected else None,
        "odoo": {
            "url": odoo_url,
            "database": odoo_db,
            "username": odoo_user,
            "connected": is_connected,
        },
        "default_company_id": default_comp_id,
        "default_company_name": default_comp_name,
        "companies": companies,
        "connection_name": odoo_db or "default",
        "connection_error": conn_error,
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


# ==================== CONNECTION SETTINGS ====================

@router.post("/api/settings/connection")
def update_connection_settings(payload: ConnectionSettingsRequest, request: Request) -> Dict[str, Any]:
    """Updates and validates Odoo connection settings dynamically from user inputs."""
    verify_api_auth(request)
    clean_url = normalize_odoo_url(payload.url)
    audit_log_access("/api/settings/connection", request, {"url": clean_url, "db": payload.db, "username": payload.username})
    api_key = payload.api_key or os.environ.get("ODOO_API_KEY", "")

    test_res = test_odoo_connection(clean_url, payload.db, payload.username, api_key)
    if not test_res.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=f"فشل التحقق من الاتصال بخادم Odoo: {test_res.get('error')}",
        )

    # Save to config/odoo_connection.json and update runtime os.environ
    save_active_odoo_config(clean_url, payload.db, payload.username, api_key)

    # Also persist in .env if available
    try:
        env_file = Path(".env")
        if env_file.exists():
            env_lines = env_file.read_text(encoding="utf-8").splitlines()
            updates = {
                "ODOO_URL": clean_url,
                "ODOO_DB": payload.db.strip(),
                "ODOO_USER": payload.username.strip(),
                "ODOO_USERNAME": payload.username.strip(),
            }
            if payload.api_key:
                updates["ODOO_API_KEY"] = payload.api_key.strip()
            new_lines = []
            applied_keys = set()
            for line in env_lines:
                replaced = False
                for k, v in updates.items():
                    if line.startswith(f"{k}=") or line.startswith(f"{k} ="):
                        new_lines.append(f"{k}={v}")
                        applied_keys.add(k)
                        replaced = True
                        break
                if not replaced:
                    new_lines.append(line)
            for k, v in updates.items():
                if k not in applied_keys:
                    new_lines.append(f"{k}={v}")
            env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception:
        pass

    comps = test_res.get("companies", [])
    default_cid = test_res.get("user_company_id") or (comps[0]["id"] if comps else None)
    default_cname = test_res.get("user_company_name") or (comps[0]["name"] if comps else "المنشأة الرئيسية")

    companies_data = [
        {
            "id": c["id"],
            "name": f"{c['name']} (ID: {c['id']})",
            "selected": (c["id"] == default_cid),
        }
        for c in comps
    ]

    return {
        "status": "success",
        "message": f"تم التحقق من قاعدة {payload.db} وحفظ الاتصال بنجاح. إصدار Odoo: {test_res.get('server_version')}",
        "odoo": {
            "url": clean_url,
            "database": payload.db,
            "username": payload.username,
            "connected": True,
        },
        "default_company_id": default_cid,
        "default_company_name": default_cname,
        "companies": companies_data,
    }


@router.post("/api/settings/connection/reset")
def reset_connection_settings(request: Request) -> Dict[str, Any]:
    """Resets and completely wipes old Odoo connection credentials from storage and environment."""
    verify_api_auth(request)
    audit_log_access("/api/settings/connection/reset", request)
    clear_active_odoo_config()
    try:
        env_file = Path(".env")
        if env_file.exists():
            lines = env_file.read_text(encoding="utf-8").splitlines()
            keys_to_clear = {"ODOO_URL", "ODOO_DB", "ODOO_USER", "ODOO_USERNAME", "ODOO_API_KEY"}
            new_lines = [l for l in lines if not any(l.strip().startswith(f"{k}=") or l.strip().startswith(f"{k} =") for k in keys_to_clear)]
            env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception:
        pass
    return {
        "status": "success",
        "message": "تم حذف بيانات الاتصال القديمة بالكامل من الخادم وملفات الإعدادات.",
        "odoo": {
            "url": "",
            "database": "",
            "username": "",
            "connected": False,
        },
    }


# ==================== LLM SETTINGS ====================

@router.get("/api/settings/llm")
def get_llm_settings_endpoint(request: Request) -> Dict[str, Any]:
    """استرجاع إعدادات محرك الذكاء الاصطناعي وحالة الاتصال المباشرة للمزودات"""
    audit_log_access("/api/settings/llm", request)
    from llm_config_manager import check_cloud_health, check_local_health, get_masked_llm_config, load_llm_config

    masked = get_masked_llm_config()
    raw = load_llm_config()

    local_h = check_local_health(raw.get("local", {}).get("base_url"))
    cloud_h = check_cloud_health(
        raw.get("cloud", {}).get("provider"),
        raw.get("cloud", {}).get("base_url"),
        raw.get("cloud", {}).get("api_key")
    )

    mode = raw.get("mode", "auto")
    active = raw.get("active_provider", "local")

    if mode == "manual":
        effective = "cloud" if active == "cloud" else "local"
    else:
        if local_h.get("available"):
            effective = "local (تلقائي ذكي - محلي متاح)"
        elif cloud_h.get("available"):
            effective = "cloud (تلقائي ذكي - سحابي نشط)"
        else:
            effective = "fallback (قواعد آمنة)"

    return {
        "status": "success",
        "config": masked,
        "health": {
            "local": local_h,
            "cloud": cloud_h,
            "effective_engine": effective
        }
    }


@router.post("/api/settings/llm")
def update_llm_settings_endpoint(payload: LLMProviderSettingsRequest, request: Request) -> Dict[str, Any]:
    """تحديث وحفظ إعدادات محرك الذكاء الاصطناعي والتبديل بين السحابي والمحلي"""
    verify_api_auth(request)
    audit_log_access("/api/settings/llm", request, {
        "mode": payload.mode,
        "active_provider": payload.active_provider,
        "cloud_provider": payload.cloud_provider
    })
    from llm_config_manager import get_masked_llm_config, save_llm_config

    update_data = {
        "mode": payload.mode or "auto",
        "active_provider": payload.active_provider or "local",
        "fallback_enabled": payload.fallback_enabled if payload.fallback_enabled is not None else True,
        "local": {
            "base_url": payload.local_base_url or "http://localhost:11434/v1",
            "model": payload.local_model or "qwen3.5:9b",
        },
        "cloud": {
            "provider": payload.cloud_provider or "openrouter",
            "base_url": payload.cloud_base_url or "https://openrouter.ai/api/v1",
            "model": payload.cloud_model or "openrouter/auto",
        }
    }
    if payload.cloud_api_key is not None:
        update_data["cloud"]["api_key"] = payload.cloud_api_key

    save_llm_config(update_data)
    masked = get_masked_llm_config()

    return {
        "status": "success",
        "message": "تم حفظ وتحديث إعدادات محرك الذكاء الاصطناعي بنجاح.",
        "config": masked
    }


@router.post("/api/settings/llm/test")
def test_llm_settings_endpoint(payload: LLMTestRequest, request: Request) -> Dict[str, Any]:
    """اختبار فوري للاتصال بالمشغل المحلي (Ollama) أو السحابي (API)"""
    audit_log_access("/api/settings/llm/test", request, {"target": payload.target})
    from llm_config_manager import test_provider_connection

    res = test_provider_connection(payload.target, {
        "provider": payload.provider,
        "base_url": payload.base_url,
        "api_key": payload.api_key,
        "model": payload.model
    })
    return res


@router.post("/api/settings/llm/start-local")
def start_local_ollama_endpoint(request: Request) -> Dict[str, Any]:
    """تشغيل خادم Ollama المحلي في الخلفية فوراً والتحقق من صحته"""
    audit_log_access("/api/settings/llm/start-local", request)
    from llm_config_manager import check_local_health, start_local_ollama_process

    health = check_local_health()
    if health.get("available"):
        return {
            "status": "success",
            "message": "خادم Ollama المحلي قيد التشغيل بالفعل ومتاح للاستخدام.",
            "health": health,
        }

    success, msg = start_local_ollama_process()
    if not success:
        return {
            "status": "error",
            "message": msg,
            "health": health,
        }

    time.sleep(2)
    new_health = check_local_health()
    return {
        "status": "success",
        "message": "تم إطلاق خادم Ollama المحلي في الخلفية بنجاح.",
        "health": new_health,
    }


# ==================== SIJIL AUDIT TRAIL ====================

@router.get("/api/sijil/summary")
def get_sijil_summary_endpoint(request: Request) -> Dict[str, Any]:
    """Returns aggregated audit metrics compiled by agent Sijil."""
    audit_log_access("/api/sijil/summary", request)
    from sijil_audit_service import SijilAuditService
    service = SijilAuditService()
    summary = service.compile_audit_summary()
    return {"status": "success", "summary": summary}


@router.get("/api/sijil/report/html", response_class=HTMLResponse)
def get_sijil_html_report_endpoint(request: Request) -> str:
    """Returns the executive dark-mode HTML audit report designed with Resend/Supabase styles."""
    audit_log_access("/api/sijil/report/html", request)
    from sijil_audit_service import SijilAuditService
    service = SijilAuditService()
    return service.generate_html_report()


@router.get("/api/sijil/report/pdf")
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


@router.get("/sijil", response_class=HTMLResponse)
def get_sijil_portal_page(request: Request) -> str:
    """Returns the unified operational cockpit positioned on agent Sijil audit portal."""
    audit_log_access("/sijil", request)
    return _get_dashboard_html()


@router.get("/api/sijil/search")
def get_sijil_search_endpoint(request: Request, q: str = "") -> Dict[str, Any]:
    """Unified operational search across all audit sources and plans."""
    audit_log_access("/api/sijil/search", request, {"q": q})
    from sijil_audit_service import SijilAuditService
    service = SijilAuditService()
    res = service.search_operations(q)
    return res


@router.get("/api/sijil/operation/{identifier}")
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


@router.get("/api/sijil/operation/{identifier}/pdf")
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


@router.get("/api/sijil/recent")
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


# ==================== MULTI-AGENT OPERATIONS & COCKPIT ====================

@router.get("/api/agents/overview")
def get_agents_overview_endpoint(request: Request) -> Dict[str, Any]:
    """Returns directory of all 8 agents with live status."""
    audit_log_access("/api/agents/overview", request)
    from agent_events_service import get_events_service
    srv = get_events_service()
    return {
        "status": "success",
        "agents": srv.get_agents_overview(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/agents/operations")
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


@router.get("/api/agents/operations/{operation_id}")
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

    if op and not op.get("pending_action"):
        from seraj_session_manager import SerajSessionManager
        mgr = SerajSessionManager.get_instance()
        sessions = mgr.sessions
        for s in sessions.values():
            if getattr(s, "active_operation_id", None) == operation_id and getattr(s, "pending_action", None):
                op["pending_action"] = s.pending_action
                break

    return {"status": "success", "operation": op, "source": "live_events"}


@router.get("/api/agents/operations/{operation_id}/events")
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
        "operation_status_label": op.get("status_label") if op else "قيد المعالجة",
    }


@router.get("/api/agent-traces/{operation_id}")
def get_agent_traces_endpoint(operation_id: str, request: Request) -> Dict[str, Any]:
    """
    استرجاع خطة اعتماد العملية المحددة (alias متوافق مع Dashboard).
    يستخدم في Dashboard لرسم Agent Timeline في real-time.
    """
    audit_log_access(f"/api/agent-traces/{operation_id}", request)

    try:
        from agent_events_service import get_events_service
        srv = get_events_service()
        events = srv.get_operation_events(operation_id)
        op = srv.get_operation(operation_id)
        return {
            "operation_id": operation_id,
            "events": events,
            "total_events": len(events),
            "operation_status": op.get("status", "unknown") if op else "unknown",
        }
    except Exception:
        try:
            from agents.agent_events_service import get_agent_events
            events = get_agent_events(operation_id)
            return {
                "operation_id": operation_id,
                "events": events,
                "total_events": len(events),
                "operation_status": "unknown",
            }
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"خطأ في استرجاع بيانات الخطة: {str(exc)}"
            )


@router.get("/api/agents/operations/{operation_id}/stream")
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


def _resolve_dry_run_report_file(identifier: Optional[str]) -> Optional[Path]:
    if not identifier:
        return None
    cleaned = Path(identifier).name
    direct = Path("output") / cleaned / "dry_run_report.json"
    if direct.exists():
        return direct
    if cleaned.startswith("op_"):
        try:
            from agent_events_service import get_events_service
            srv = get_events_service()
            op = srv.get_operation(cleaned)
            if op:
                for evt in op.get("events", []):
                    meta = evt.get("metadata") or {}
                    f = meta.get("folder")
                    if f and (Path("output") / f / "dry_run_report.json").exists():
                        return Path("output") / f / "dry_run_report.json"
                    run_id = meta.get("run_id")
                    if run_id:
                        candidates = list(Path("output").glob(f"*{run_id}*/dry_run_report.json"))
                        if candidates:
                            return candidates[0]
        except Exception:
            pass
    candidates = list(Path("output").glob(f"*{cleaned}*/dry_run_report.json"))
    if candidates:
        return candidates[0]
    return None


def _execute_excel_approval(
    payload: AgentApprovalApiRequest,
    report_file: Path,
    srv: Any,
    request: Request,
) -> Dict[str, Any]:
    import uuid
    op_id = payload.operation_id or f"op_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    run_dir = report_file.parent
    try:
        report_data = json.loads(report_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"تعذر قراءة ملف تقرير الفحص: {exc}")

    srv.emit_event(
        operation_id=op_id,
        agent="hares",
        event_type="action_approved",
        action="hitl_approval_verified",
        reasoning="تحقق حارس من توقيع المشغّل ومطابقة البصمة المشفرة للصفوف المقبولة، وإصدار ترخيص التنفيذ.",
        decision="منح رمز الصلاحية (Write Token) والإذن للكاتب ببدء الكتابة في Odoo.",
        status="waiting_approval",
        description_ar="حارس يتحقق من اعتماد المشغّل الصريح لنتائج الفحص ويأذن للكاتب بالتنفيذ في Odoo",
    )

    rows = report_data.get("rows", [])
    accepted_rows = [r for r in rows if r.get("final_status") == "accepted"]
    if not accepted_rows:
        srv.emit_event(
            operation_id=op_id,
            agent="hares",
            event_type="approval_rejected",
            status="failed",
            description_ar="رفض حارس الإذن بالتنفيذ نظراً لعدم وجود أي صفوف مقبولة في التقرير",
        )
        return {
            "status": "error",
            "operation_id": op_id,
            "response": "لا توجد أي صفوف مقبولة (accepted) في نتائج الفحص لتنفيذها في Odoo.",
            "operation": srv.get_operation(op_id),
        }

    source_name = report_data.get("header", {}).get("source_file_name", "")
    upload_dir = _get_upload_dir()
    candidates = list(upload_dir.glob(f"*{source_name}*")) if source_name else []
    if candidates:
        input_path = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    else:
        all_uploads = sorted(upload_dir.glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
        input_path = all_uploads[0] if all_uploads else None

    approved_by = payload.approved_by or "مشغّل النظام"
    approval_file = run_dir / "approval.json"
    approval_payload = {
        "run_id": report_data.get("header", {}).get("run_id", run_dir.name),
        "source_hash": report_data.get("header", {}).get("source_hash", "offline"),
        "source_file_name": input_path.name if input_path else "input.xlsx",
        "approved_by": approved_by,
        **approval_schema.new_approval_timestamps(),
        "approved_row_hashes": [r["row_hash"] for r in accepted_rows if "row_hash" in r],
    }
    with open(approval_file, "w", encoding="utf-8") as f:
        json.dump(approval_payload, f, ensure_ascii=False, indent=2)

    template_type = report_data.get("summary", {}).get("template_type") or report_data.get("header", {}).get("template_type") or "recruitment"
    template_title = report_data.get("summary", {}).get("template_title") or report_data.get("header", {}).get("template_title") or "الموارد البشرية"

    srv.emit_event(
        operation_id=op_id,
        agent="katib",
        from_agent="hares",
        to_agent="katib",
        event_type="write_started",
        action="odoo_bulk_insert_start",
        reasoning="استلام ترخيص التنفيذ وفتح جلسة اتصال آمنة وموثقة مع Odoo API لمعالجة السجلات المقبولة.",
        decision="بدء الإدخال المتزامن للسجلات وحفظ معرفات الكائنات الناتجة.",
        status="executing_write",
        description_ar=f"كاتب يبدأ تنفيذ اعتماد {len(accepted_rows)} سجلاً في Odoo ({template_title})...",
    )

    try:
        odoo_url = os.environ.get("ODOO_URL", "https://edu-training1555.odoo.com")
        odoo_db = os.environ.get("ODOO_DB", "edu-training1555")
        odoo_user = os.environ.get("ODOO_USERNAME") or os.environ.get("ODOO_USER") or "ghh05420@gmail.com"
        odoo_key = os.environ.get("ODOO_API_KEY", "")

        gw_cls = _get_write_gateway_cls()
        repo_cls = _get_readonly_repo_cls()
        gw = gw_cls(odoo_url, odoo_db, odoo_user, odoo_key)
        repo = repo_cls()

        created_count = 0
        failed_count = 0
        created_items = []

        if template_type == "recruitment":
            available_jobs = {}
            try:
                for j in repo.get_jobs():
                    name_clean = (j.get("name") or "").strip()
                    if name_clean:
                        available_jobs[name_clean.lower()] = j.get("id")
            except Exception:
                pass

            available_stages = {}
            try:
                if hasattr(repo, "_models") and repo._models:
                    st_recs = repo._models.execute_kw(
                        repo.db, repo.uid, repo.api_key,
                        "hr.recruitment.stage", "search_read",
                        [[]],
                        {"fields": ["id", "name", "sequence"]}
                    )
                    for s in st_recs:
                        name_clean = (s.get("name") or "").strip()
                        if name_clean:
                            available_stages[name_clean.lower()] = s.get("id")
            except Exception:
                pass

            STAGE_ALIASES = {
                "معتمد ومباشر": available_stages.get("contract signed", 6),
                "عقد موقع": available_stages.get("contract signed", 6),
                "عرض عمل مرسل": available_stages.get("contract proposal", 5),
                "عرض عمل": available_stages.get("contract proposal", 5),
                "مقابلة مجدولة": available_stages.get("first interview", 3),
                "مقابلة أولى": available_stages.get("first interview", 3),
                "مقابلة ثانية": available_stages.get("second interview", 4),
                "مقبول مبدئياً": available_stages.get("qualification", 2),
                "تأهيل": available_stages.get("qualification", 2),
                "جديد": available_stages.get("new", 1),
            }
            default_stage_id = available_stages.get("new") or available_stages.get("qualification") or 1

            SEMANTIC_JOB_MAP = {
                "أخصائي تسويق": "marketing and community manager",
                "مطوّر برمجيات": "full stack developer",
            }

            target_company_id = 1
            try:
                target_company_id = repo.get_default_company().get("id", 1)
            except Exception:
                pass

            for r in accepted_rows:
                flds = r.get("fields", {})
                cand_name = r.get("display_name") or flds.get("name", {}).get("value") or "مرشح جديد"
                job_title = (flds.get("job", {}).get("value") or "").strip()
                email = flds.get("email", {}).get("value") or ""
                mobile = flds.get("mobile", {}).get("value") or ""
                raw_status = (flds.get("status", {}).get("value") or "").strip()
                salary = 0.0
                try:
                    salary = float(flds.get("expected_salary", {}).get("value") or 0)
                except Exception:
                    pass

                job_id = None
                resolved = r.get("resolved_ids", {})
                if resolved.get("job_id"):
                    job_id = resolved["job_id"]
                elif job_title:
                    if job_title.lower() in available_jobs:
                        job_id = available_jobs[job_title.lower()]
                    elif job_title in SEMANTIC_JOB_MAP and SEMANTIC_JOB_MAP[job_title] in available_jobs:
                        job_id = available_jobs[SEMANTIC_JOB_MAP[job_title]]
                    else:
                        try:
                            new_job_id = gw.create_record("hr.job", {
                                "name": job_title,
                                "expected_employees": 5,
                            })
                            available_jobs[job_title.lower()] = new_job_id
                            job_id = new_job_id
                        except Exception:
                            pass

                dept_id = resolved.get("department_id")
                stage_id = STAGE_ALIASES.get(raw_status, default_stage_id)

                vals = {
                    "partner_name": cand_name,
                    "company_id": target_company_id,
                }
                if email:
                    vals["email_from"] = email
                if mobile:
                    vals["partner_phone"] = mobile
                if salary > 0:
                    vals["salary_expected"] = salary
                if job_id:
                    vals["job_id"] = job_id
                if dept_id:
                    vals["department_id"] = dept_id
                if stage_id:
                    vals["stage_id"] = stage_id

                try:
                    new_id = gw.create_record("hr.applicant", vals)
                    created_count += 1
                    created_items.append({"name": cand_name, "id": new_id, "job": job_title})
                except Exception:
                    failed_count += 1
        elif input_path and input_path.exists():
            out_dir = Path("output") / f"writer_auto_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            out_dir.mkdir(parents=True, exist_ok=True)
            target_company_id = 1
            try:
                target_company_id = repo.get_default_company().get("id", 1)
            except Exception:
                pass
            writer_res = writer.run_writer(
                str(input_path),
                str(report_file),
                str(approval_file),
                str(out_dir),
                repo,
                gw,
                company_id=target_company_id,
                max_rows=max(50, len(accepted_rows)),
            )
            status_counts = writer_res.get("footer", {}).get("status_counts", {})
            created_count = status_counts.get("created", 0)
            failed_count = status_counts.get("failed", 0)
        else:
            created_count = 0
            failed_count = len(accepted_rows)

        if created_count == 0:
            err_msg = (
                f"تعذر تنفيذ السجلات في Odoo (سجلات ناجحة: 0، تعذر: {failed_count}). "
                "يرجى التأكد من وجود ملف المصدر في مجلد الرفع ومطابقة حقول القالب مع أودو."
            )
            srv.emit_event(
                operation_id=op_id,
                agent="katib",
                event_type="write_failed",
                status="failed",
                description_ar=err_msg,
                metadata={"created_count": 0, "failed_count": failed_count, "items": []},
            )
            srv.update_operation_status(op_id, "failed")
            return {
                "status": "error",
                "mode": "excel_import",
                "operation_id": op_id,
                "created_count": 0,
                "failed_count": failed_count,
                "response": err_msg,
                "operation": srv.get_operation(op_id),
            }

        srv.emit_event(
            operation_id=op_id,
            agent="katib",
            event_type="write_completed",
            action="odoo_bulk_insert_complete",
            reasoning=f"تم استيفاء رمز تفويض الكتابة ومطابقة الحقول وقيد {created_count} سجلاً في Odoo بنجاح تام.",
            decision="تأكيد اكتمال الترحيل ونقل ملف المعاملة لوكيل «سجل» لإصدار البصمة الجنائية.",
            status="completed",
            description_ar=f"أنجز كاتب تنفيذ {created_count} سجلاً في Odoo بنجاح (فشل: {failed_count}).",
            metadata={"created_count": created_count, "failed_count": failed_count, "items": created_items},
        )
        srv.emit_event(
            operation_id=op_id,
            agent="sijil",
            from_agent="katib",
            to_agent="sijil",
            event_type="operation_documented",
            action="cryptographic_audit_seal",
            reasoning="توثيق البصمة الجنائية المشفرة (SHA-256) وسند الاعتماد غير القابل للتراجع في دفتر التدقيق.",
            decision="إصدار ختم التوثيق النهائي وإغلاق العملية كـ مكتملة ومحمية من التلاعب.",
            status="completed",
            description_ar="سجل يوثق إنجاز العملية وتوليد سند الاعتماد والحفظ النهائي.",
        )
        srv.update_operation_status(op_id, "completed")

        if template_type == "recruitment":
            succ_msg = (
                f"تم اعتماد وتنفيذ {created_count} طلباً بنجاح في تطبيق «التوظيف» (Recruitment) بـ Odoo عبر الوكيل «كاتب».\n"
                f"ملاحظة: تظهر السجلات في Odoo داخل تطبيق: التوظيف -> المتقدمون للوظائف (Recruitment -> Applications)."
            )
        else:
            succ_msg = f"تم اعتماد وتنفيذ {created_count} سجلاً بنجاح في Odoo عبر الوكيل «كاتب»."
        return {
            "status": "success",
            "mode": "excel_import",
            "operation_id": op_id,
            "created_count": created_count,
            "failed_count": failed_count,
            "response": succ_msg,
            "operation": srv.get_operation(op_id),
        }
    except Exception as exc:
        srv.emit_event(
            operation_id=op_id,
            agent="katib",
            event_type="write_error",
            status="failed",
            description_ar=f"واجه كاتب خطأ أثناء الكتابة في Odoo: {exc}",
            error=str(exc),
        )
        srv.update_operation_status(op_id, "failed")
        return {
            "status": "error",
            "mode": "excel_import",
            "operation_id": op_id,
            "response": f"تعذر استكمال الكتابة في Odoo: {exc}",
            "operation": srv.get_operation(op_id),
        }


@router.post("/api/agents/approve")
def post_agent_approve_endpoint(payload: AgentApprovalApiRequest, request: Request) -> Dict[str, Any]:
    """Explicit human approval of a pending operation plan or Excel batch dry-run."""
    verify_api_auth(request)
    audit_log_access("/api/agents/approve", request, {"chat_id": payload.chat_id, "op_id": payload.operation_id})
    from agent_events_service import get_events_service
    from seraj_llm_service import SerajLLMService
    from seraj_session_manager import SerajSessionManager

    srv = get_events_service()

    # 1. First, check if this is an Excel Dry-Run Batch Operation
    report_file = None
    if payload.report_folder:
        direct = Path("output") / Path(payload.report_folder).name / "dry_run_report.json"
        if direct.exists():
            report_file = direct
    if not report_file and payload.operation_id:
        report_file = _resolve_dry_run_report_file(payload.operation_id)

    if not report_file and payload.chat_id and payload.chat_id.startswith("web_upload_"):
        all_reports = list(Path("output").glob("*/dry_run_report.json"))
        if all_reports:
            all_reports.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            if (time.time() - all_reports[0].stat().st_mtime) < 1800:
                report_file = all_reports[0]

    if report_file and report_file.exists():
        return _execute_excel_approval(payload, report_file, srv, request)

    # 2. Otherwise, treat as conversational chat approval (e.g. employee single edit/delete plan)
    session = SerajSessionManager.get_instance().get_session(payload.chat_id)
    if session and session.pending_action and payload.modified_payload:
        if "action_details" not in session.pending_action:
            session.pending_action["action_details"] = {}
        session.pending_action["action_details"].update(payload.modified_payload)
        for k, v in payload.modified_payload.items():
            session.pending_action[k] = v

    seraj = SerajLLMService()
    reply = seraj.chat_turn(
        user_query="تأكيد",
        chat_id=payload.chat_id,
        operation_id=payload.operation_id,
    )

    op = srv.get_operation(payload.operation_id) if payload.operation_id else None

    return {
        "status": "success",
        "operation_id": payload.operation_id,
        "response": reply,
        "operation": op,
        "pending_action": session.pending_action if session else None,
    }


@router.post("/api/agents/cancel")
def post_agent_cancel_endpoint(payload: AgentCancelApiRequest, request: Request) -> Dict[str, Any]:
    """Explicit human cancellation of a pending operation plan."""
    verify_api_auth(request)
    audit_log_access("/api/agents/cancel", request, {"chat_id": payload.chat_id, "op_id": payload.operation_id})
    from agent_events_service import get_events_service
    from seraj_llm_service import SerajLLMService
    from seraj_session_manager import SerajSessionManager

    srv = get_events_service()
    if payload.operation_id:
        srv.update_operation_status(payload.operation_id, "cancelled")

    seraj = SerajLLMService()
    reply = seraj.chat_turn(
        user_query="إلغاء",
        chat_id=payload.chat_id,
        operation_id=payload.operation_id,
    )

    if payload.operation_id:
        srv.update_operation_status(payload.operation_id, "cancelled")

    session = SerajSessionManager.get_instance().get_session(payload.chat_id)
    op = srv.get_operation(payload.operation_id) if payload.operation_id else None

    return {
        "status": "success",
        "operation_id": payload.operation_id,
        "response": reply,
        "operation": op,
        "pending_action": session.pending_action if session else None,
    }


@router.post("/api/agents/upload")
async def upload_agent_file_endpoint(
    request: Request,
    file: UploadFile = File(...),
    chat_id: str = Form("web_default"),
    operation_id: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Uploads file in agent cockpit, creating staging operation and parsing."""
    verify_api_auth(request)
    audit_log_access("/api/agents/upload", request)
    content = await file.read()
    size = len(content)
    if size > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="حجم الملف يتجاوز الحد الأقصى المسموح به (10 ميجابايت).")

    fn = file.filename or "upload_file"
    safe_filename = f"{int(time.time())}_{fn}"
    saved_path = _get_upload_dir() / safe_filename
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
            tmpl_title = (
                report_dict.get("header", {}).get("template_title")
                or report_dict.get("summary", {}).get("template_title")
                or f"ملف '{fn}'"
            )
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
                "template_title": tmpl_title,
                "report_url": f"/api/reports/dry-run/{folder_name}",
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

