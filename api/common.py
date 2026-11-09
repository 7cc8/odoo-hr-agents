"""
API Common Layer - أدوات ومحددات الأمان والمصادقة والمسارات المشتركة
=====================================================================
تجمع هذه الوحدة الثوابت والدوال الأمنية المشتركة لكافة راوترات الـ API:
- التحقق من المصادقة (verify_api_auth, verify_write_auth)
- التحقق من سلامة المسارات ومعرفات العمليات (_safe_artifact_path, _safe_operation_id)
- تسجيل عمليات الوصول والتدقيق الأمني (audit_log_access)
- مسارات التخزين والتحميل المعتمدة
"""

from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request

# مجلدات التخزين والمخرجات
OUTPUT_ROOT = Path("output").resolve()
UPLOAD_DIR = Path("output") / "web_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATE_DIR = Path("output") / "templates"
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
API_LOG_FILE = LOGS_DIR / "web_access.log"

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")

# إعدادات مصادقة الكتابة
WRITE_API_TOKEN = os.environ.get("WRITE_API_TOKEN", "").strip()

def _get_insecure_published_tokens() -> frozenset[str]:
    import sys
    ws = sys.modules.get("web_service")
    if ws is not None and hasattr(ws, "INSECURE_PUBLISHED_WRITE_TOKENS"):
        return getattr(ws, "INSECURE_PUBLISHED_WRITE_TOKENS")
    return frozenset()

INSECURE_PUBLISHED_WRITE_TOKENS: frozenset[str] = frozenset()


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

    expected = os.environ.get("WRITE_API_TOKEN", WRITE_API_TOKEN).strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="خدمة الكتابة معطلة حتى يضبط المشغّل WRITE_API_TOKEN في مخزن الأسرار.",
        )
    insecure_tokens = INSECURE_PUBLISHED_WRITE_TOKENS or _get_insecure_published_tokens()
    if expected in insecure_tokens:
        raise HTTPException(
            status_code=503,
            detail="WRITE_API_TOKEN يساوي قيمة منشورة علناً في المستودع؛ ولّد رمزاً عشوائياً جديداً "
            "(python -c \"import secrets; print(secrets.token_urlsafe(32))\") واضبطه في بيئة الخادم والبوت.",
        )
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=401,
            detail="غير مصرّح: يجب توفير رمز المصادقة للكتابة (X-API-Key) للوصول إلى المورد.",
        )


def verify_write_auth(request: Request) -> None:
    """Authentication token check for write mutations."""
    verify_api_auth(request)


def _safe_artifact_path(value: str, field_name: str) -> Path:
    """Resolve an artifact path without allowing access outside output/."""
    candidate = Path(value).resolve()
    try:
        import web_service
        root = getattr(web_service, "OUTPUT_ROOT", OUTPUT_ROOT)
    except Exception:
        root = OUTPUT_ROOT
    try:
        candidate.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"مسار {field_name} غير مسموح؛ يجب أن يكون ضمن مخزن العملية.")
    return candidate


def _safe_operation_id(value: str) -> str:
    """Sanitize and validate an alphanumeric operation or run ID."""
    if not SAFE_ID_RE.fullmatch(value or ""):
        raise HTTPException(status_code=400, detail="معرّف العملية غير صالح.")
    return value


def _get_upload_dir() -> Path:
    try:
        import web_service
        return getattr(web_service, "UPLOAD_DIR", UPLOAD_DIR)
    except Exception:
        return UPLOAD_DIR


def _get_write_gateway_cls():
    try:
        import web_service
        from odoo_write_gateway import OdooWriteGateway
        return getattr(web_service, "OdooWriteGateway", OdooWriteGateway)
    except Exception:
        try:
            from odoo_write_gateway import OdooWriteGateway
            return OdooWriteGateway
        except Exception:
            return None


def _get_readonly_repo_cls():
    try:
        import web_service
        from odoo_readonly_repository import OdooReadonlyRepository
        return getattr(web_service, "OdooReadonlyRepository", OdooReadonlyRepository)
    except Exception:
        try:
            from odoo_readonly_repository import OdooReadonlyRepository
            return OdooReadonlyRepository
        except Exception:
            return None


def _get_writer_module():
    try:
        import web_service
        import writer
        return getattr(web_service, "writer", writer)
    except Exception:
        try:
            import writer
            return writer
        except Exception:
            return None
