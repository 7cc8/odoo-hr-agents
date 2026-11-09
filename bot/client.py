"""Core Telegram Bot Client, SSL configuration, authorization, and state management."""
from __future__ import annotations

import os
import sys
import json
import time
import ssl
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("telegram_bot")

try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def get_tb_symbol(name: str, fallback: Any = None) -> Any:
    """
    استرجاع الرمز ديناميكياً من موديول telegram_bot لضمان توافقية patch و monkeypatch في الاختبارات.
    """
    tb = sys.modules.get("telegram_bot")
    if tb is not None and hasattr(tb, name):
        return getattr(tb, name)
    return fallback


def _build_ssl_context() -> Optional[ssl.SSLContext]:
    ca_bundle = os.environ.get("TELEGRAM_CA_BUNDLE")
    if ca_bundle:
        if os.path.isfile(ca_bundle):
            try:
                return ssl.create_default_context(cafile=ca_bundle)
            except Exception as exc:
                sys.stderr.write(f"WARNING: Failed to load TELEGRAM_CA_BUNDLE '{ca_bundle}': {exc}\n")
        else:
            sys.stderr.write(f"WARNING: TELEGRAM_CA_BUNDLE '{ca_bundle}' not found\n")
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        try:
            return ssl.create_default_context()
        except Exception:
            return None


def get_ssl_context() -> Optional[ssl.SSLContext]:
    return _build_ssl_context()


_DEFAULT_SSL_CONTEXT = _build_ssl_context()

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = Path("output") / "telegram_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TG_AUDIT_LOG_FILE = LOGS_DIR / "telegram_audit.log"

DEFAULT_COMPANY_ID = 15
DEFAULT_MAX_ROWS = 10
WRITE_API_TOKEN = os.environ.get("WRITE_API_TOKEN", "").strip()
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")

# Pending confirmations waiting for written 'تأكيد' (Section 5.1)
PENDING_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}

# Active Odoo Setup Wizards waiting for user input
ACTIVE_CONFIG_WIZARDS: Dict[str, Dict[str, Any]] = {}

# Active Leave Confirmations and Wizards (Phase 10)
PENDING_LEAVE_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
ACTIVE_LEAVE_WIZARDS: Dict[str, Dict[str, Any]] = {}

# Active Attendance Confirmations and Wizards (Phase 11)
PENDING_ATTENDANCE_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
ACTIVE_ATTENDANCE_WIZARDS: Dict[str, Dict[str, Any]] = {}

# Active Disciplinary Confirmations and Wizards (Phase 12)
PENDING_DISCIPLINARY_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
ACTIVE_DISCIPLINARY_WIZARDS: Dict[str, Dict[str, Any]] = {}

# Active End of Service Confirmations and Wizards (Phase 13)
PENDING_EOS_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
ACTIVE_EOS_WIZARDS: Dict[str, Dict[str, Any]] = {}

# Active Government Relations Confirmations and Wizards (Phase 14)
PENDING_GR_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
ACTIVE_GR_WIZARDS: Dict[str, Dict[str, Any]] = {}

# Active Appraisal Confirmations and Wizards (Phase 15)
PENDING_APPRAISAL_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
ACTIVE_APPRAISAL_WIZARDS: Dict[str, Dict[str, Any]] = {}

# Active Loan Confirmations and Wizards (Phase 16)
PENDING_LOAN_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
ACTIVE_LOAN_WIZARDS: Dict[str, Dict[str, Any]] = {}

# Active Recruitment Confirmations and Wizards (Phase 17)
PENDING_RECRUITMENT_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
ACTIVE_RECRUITMENT_WIZARDS: Dict[str, Dict[str, Any]] = {}

# Active Contract Confirmations and Wizards (Phase 18)
PENDING_CONTRACT_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
ACTIVE_CONTRACT_WIZARDS: Dict[str, Dict[str, Any]] = {}

# Active Payroll Confirmations and Wizards (Phase 19)
PENDING_PAYROLL_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
ACTIVE_PAYROLL_WIZARDS: Dict[str, Dict[str, Any]] = {}

# Active Executive Analytics Wizards (Phase 20)
ACTIVE_ANALYTICS_WIZARDS: Dict[str, Dict[str, Any]] = {}

# Active Letter Confirmations and Wizards (Phase 22)
PENDING_LETTER_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
ACTIVE_LETTER_WIZARDS: Dict[str, Dict[str, Any]] = {}

# Active Warning Confirmations and Wizards (Phase 23)
PENDING_WARNING_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
ACTIVE_WARNING_WIZARDS: Dict[str, Dict[str, Any]] = {}

# Active Expense Confirmations and Wizards (Phase 24)
PENDING_EXPENSE_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}
ACTIVE_EXPENSE_WIZARDS: Dict[str, Dict[str, Any]] = {}

# Active Autofix configuration by Chat ID (Phase 26 - Musleh Engine)
AUTOFIX_ENABLED_BY_CHAT: Dict[str, bool] = {}
AUTOFIX_CONFIG_FILE = Path("output") / "autofix_config.json"


def is_autofix_enabled(chat_id: int | str) -> bool:
    """Returns True if auto-repair mode is enabled for this chat, False for review-only mode."""
    chat_key = str(chat_id)
    if chat_key in AUTOFIX_ENABLED_BY_CHAT:
        return AUTOFIX_ENABLED_BY_CHAT[chat_key]
    if AUTOFIX_CONFIG_FILE.exists():
        try:
            data = json.loads(AUTOFIX_CONFIG_FILE.read_text(encoding="utf-8"))
            if chat_key in data:
                AUTOFIX_ENABLED_BY_CHAT[chat_key] = bool(data[chat_key])
                return AUTOFIX_ENABLED_BY_CHAT[chat_key]
        except Exception:
            pass
    # By default, autofix is disabled (review only) to safeguard data
    return False


def set_autofix_enabled(chat_id: int | str, enabled: bool) -> None:
    """Sets and persists the auto-repair setting for this chat."""
    chat_key = str(chat_id)
    AUTOFIX_ENABLED_BY_CHAT[chat_key] = enabled
    try:
        data = {}
        if AUTOFIX_CONFIG_FILE.exists():
            try:
                data = json.loads(AUTOFIX_CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data[chat_key] = enabled
        AUTOFIX_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUTOFIX_CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass





def log_telegram_audit(
    user_id: int | str,
    chat_id: int | str,
    action: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Logs all Telegram interactions for compliance and audit trail (Section 5.2)."""
    try:
        entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "user_id": str(user_id),
            "chat_id": str(chat_id),
            "action": action,
            "details": details or {},
        }
        with open(TG_AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def get_allowed_users() -> Set[str]:
    """Returns the set of authorized Telegram user/chat IDs from environment."""
    raw = os.environ.get("TELEGRAM_ALLOWED_USERS") or os.environ.get("TELEGRAM_CHAT_ID") or ""
    parts = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
    return set(parts)


def is_user_authorized(user_id: int | str, chat_id: int | str) -> bool:
    """Verifies that the sender is explicitly whitelisted."""
    allowed = get_allowed_users()
    if not allowed:
        return False
    return str(user_id) in allowed or str(chat_id) in allowed


class TelegramBotClient:
    """Lightweight Telegram Bot API client using standard urllib."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def is_configured(self) -> bool:
        return bool(self.token)

    def _post(self, method: str, data: Dict[str, Any], timeout: float = 25.0) -> Dict[str, Any]:
        url = f"{self.base_url}/{method}"
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp_ctx = urllib.request.urlopen(req, timeout=timeout, context=_DEFAULT_SSL_CONTEXT)
            with resp_ctx as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="ignore")
            try:
                return json.loads(err_body)
            except Exception:
                return {"ok": False, "description": f"HTTP {exc.code}: {err_body}"}
        except Exception as exc:
            return {"ok": False, "description": f"{type(exc).__name__}: {exc}"}

    def get_updates(self, offset: Optional[int] = None, timeout: int = 15) -> List[Dict[str, Any]]:
        payload: Dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            payload["offset"] = offset
        res = self._post("getUpdates", payload, timeout=timeout + 10.0)
        return res.get("result", []) if res.get("ok") else []

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        reply_to_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        return self._post("sendMessage", payload)

    def edit_message_text(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self._post("editMessageText", payload)

    def answer_callback_query(self, callback_query_id: str, text: str = "", show_alert: bool = False) -> Dict[str, Any]:
        payload = {"callback_query_id": callback_query_id, "text": text, "show_alert": show_alert}
        return self._post("answerCallbackQuery", payload)

    def download_file(self, file_id: str, destination_path: Path) -> bool:
        res = self._post("getFile", {"file_id": file_id})
        if not res.get("ok"):
            return False
        file_path_str = res["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path_str}"
        try:
            resp_ctx = urllib.request.urlopen(download_url, timeout=30.0, context=_DEFAULT_SSL_CONTEXT)
            with resp_ctx as src, open(destination_path, "wb") as dst:
                dst.write(src.read())
            return True
        except Exception:
            return False

    def send_document(
        self,
        chat_id: int | str,
        file_path: Path,
        caption: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sends an Excel or PDF document directly to Telegram chat."""
        try:
            import httpx
            mime_type = "application/pdf" if str(file_path).endswith(".pdf") else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            with open(file_path, "rb") as f:
                resp = httpx.post(
                    f"{self.base_url}/sendDocument",
                    data={"chat_id": str(chat_id), "caption": caption or "", "parse_mode": "HTML"},
                    files={"document": (Path(file_path).name, f, mime_type)},
                    timeout=45.0,
                )
                return resp.json()
        except Exception as exc:
            return {"ok": False, "description": str(exc)}


