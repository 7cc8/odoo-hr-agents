"""Telegram notification service for Odoo HR Agents.

Sends alerts and execution summaries to authorized Telegram channels or chats.
Designed to fail safely: errors in Telegram notifications will never fail or
block the primary Odoo writer or dry-run execution.
"""

from __future__ import annotations

import os
import sys
import json
import ssl
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional

def _build_ssl_context() -> ssl.SSLContext:
    """Builds a verified SSL context using custom CA bundle if configured, or certifi/system default.
    Warns if TELEGRAM_CA_BUNDLE or SSL_CERT_FILE is set but the specified file does not exist.
    """
    custom_ca = os.environ.get("TELEGRAM_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if custom_ca:
        ca_path = Path(custom_ca)
        if not ca_path.is_file():
            sys.stderr.write(
                f"WARNING: SSL certificate bundle configured in TELEGRAM_CA_BUNDLE/SSL_CERT_FILE was not found: '{custom_ca}'. Falling back to default CA store.\n"
            )
        else:
            return ssl.create_default_context(cafile=str(ca_path))

    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


_CACHED_SSL_CONTEXT: Optional[ssl.SSLContext] = None


def get_ssl_context() -> ssl.SSLContext:
    """Returns the cached verified SSL context, building it once on first call."""
    global _CACHED_SSL_CONTEXT
    if _CACHED_SSL_CONTEXT is None:
        _CACHED_SSL_CONTEXT = _build_ssl_context()
    return _CACHED_SSL_CONTEXT


_DEFAULT_SSL_CONTEXT = get_ssl_context()


def is_telegram_configured(token: Optional[str] = None, chat_id: Optional[str] = None) -> bool:
    if token is None:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if chat_id is None:
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    return bool(token and chat_id)


def send_telegram_notification(
    text: str,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    timeout: float = 8.0,
) -> Dict[str, Any]:
    """Sends a text message to Telegram via Bot API sendMessage.

    Returns a dict with status: 'sent', 'skipped', or 'error'.
    Never raises an uncaught exception.
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() if token is None else token.strip()
    target_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip() if chat_id is None else chat_id.strip()

    if not bot_token or not target_chat:
        return {
            "sent": False,
            "status": "skipped",
            "reason": "Telegram credentials (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID) are not set.",
        }

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=get_ssl_context()) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            if data.get("ok"):
                return {"sent": True, "status": "ok", "message_id": data.get("result", {}).get("message_id")}
            return {"sent": False, "status": "error", "reason": str(data)}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="ignore")
        return {"sent": False, "status": "error", "reason": f"HTTP {exc.code}: {err_body}"}
    except Exception as exc:
        return {"sent": False, "status": "error", "reason": f"{type(exc).__name__}: {exc}"}


def format_writer_notification(result: Dict[str, Any]) -> str:
    """Formats an execution result from writer.py into an informative Arabic Telegram notification."""
    header = result.get("header") or {}
    footer = result.get("footer") or {}
    rows = result.get("rows") or []

    approved_by = header.get("approved_by", "غير محدد")
    company_id = header.get("target_company_id", "غير محدد")
    company_name = header.get("company_name")
    if not company_name and company_id == 15:
        company_name = "شركة النخبة الذكية للتقنية (15)"
    elif not company_name:
        company_name = f"معرّف {company_id}"
    source_file = header.get("source_file_name", "غير محدد")
    counts = footer.get("status_counts") or {}
    created_count = counts.get("created", 0)
    failed_count = counts.get("failed", 0)
    uncertain_count = counts.get("outcome_uncertain", 0)

    lines = [
        "<b>🔔 إشعار نظام أتمتة الموارد البشرية (Odoo HR)</b>",
        "────────────────────",
        f"📁 <b>الملف:</b> <code>{source_file}</code>",
        f"👤 <b>المعتمد:</b> {approved_by}",
        f"🏢 <b>الشركة:</b> {company_name}",
        f"⏱️ <b>وقت الانتهاء:</b> {footer.get('finished_at', 'الآن')}",
        "────────────────────",
        f"📊 <b>النتائج:</b>",
        f"  • تم الإنشاء بنجاح: <b>{created_count}</b>",
    ]
    if failed_count:
        lines.append(f"  • فشل الإنشاء: <b>{failed_count}</b>")
    if uncertain_count:
        lines.append(f"  • حالة غير مؤكدة (تحتاج تدقيق): <b>{uncertain_count}</b>")

    created_employees = []
    for r in rows:
        if r.get("status") == "created":
            emp_id = r.get("odoo_employee_id")
            name = r.get("attempted_name", "")
            verified_mark = "✅" if r.get("verified") else "⚠️"
            created_employees.append(f"  {verified_mark} <b>{name}</b> (معرّف Odoo: <code>{emp_id}</code>)")

    if created_employees:
        lines.append("\n<b>👥 الموظفون المُنشأون في Odoo:</b>")
        lines.extend(created_employees[:15])
        if len(created_employees) > 15:
            lines.append(f"  <i>... و {len(created_employees) - 15} موظفين إضافيين.</i>")

    lines.append("────────────────────")
    lines.append("🛡️ <i>تم التحقق المباشر وسجل التدقيق محفوظ محلياً.</i>")

    return "\n".join(lines)
