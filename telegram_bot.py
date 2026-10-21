"""Interactive Telegram Bot for Odoo HR Agents (Phase 7).

Allows authorized HR personnel to:
1. Send an Excel template directly in Telegram chat from desktop or mobile.
2. Execute dry-run automatically without modifying parser or validator logic.
3. Receive formatted inspection summary and interactive Inline Keyboard buttons.
4. Authorize creation with written confirmation ("تأكيد") to prevent accidental triggers (Section 5.1).
5. Calls the centralized Backend API (/write) rather than running writer directly (Section 5.2).
6. Strictly enforces silent rejection on unauthorized chat IDs (Section 5.2).
7. Maintains a dedicated interaction audit log in logs/telegram_audit.log.
"""

from __future__ import annotations

import os
import sys
import json
import time
import ssl
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


try:
    import certifi
    _DEFAULT_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    try:
        _DEFAULT_SSL_CONTEXT = ssl.create_default_context()
    except Exception:
        _DEFAULT_SSL_CONTEXT = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import dry_run_report
import writer
from odoo_readonly_repository import OdooReadonlyRepository
from odoo_write_gateway import OdooWriteGateway, EnvironmentGuardError
from odoo_leave_write_gateway import OdooLeaveWriteGateway
from odoo_attendance_write_gateway import OdooAttendanceWriteGateway
from leave_service import (
    LeaveService,
    EmployeeLeaveSummary,
    LeaveDryRunResult,
    LeaveExecutionResult,
)
from attendance_service import (
    AttendanceService,
    AttendanceSummaryResult,
    AttendanceDryRunResult,
    AttendanceExecutionResult,
)
from odoo_disciplinary_write_gateway import OdooDisciplinaryWriteGateway
from disciplinary_service import (
    DisciplinaryService,
    DisciplinaryActionSummary,
    DisciplinaryDryRunResult,
    DisciplinaryExecutionResult,
)
from odoo_eos_write_gateway import OdooEOSWriteGateway
from eos_service import (
    EOSService,
    EOSCalculationSummary,
    EOSDryRunResult,
    EOSExecutionResult,
)
from odoo_gr_write_gateway import OdooGRWriteGateway
from gr_service import (
    GRService,
    GRTransactionSummary,
    GRDryRunResult,
    GRExecutionResult,
    STANDARD_GOV_FEES,
)
from odoo_appraisal_write_gateway import OdooAppraisalWriteGateway
from appraisal_service import (
    AppraisalService,
    AppraisalSummary,
    AppraisalDryRunResult,
    AppraisalExecutionResult,
    APPRAISAL_RATING_TIERS,
)
from odoo_loan_write_gateway import OdooLoanWriteGateway
from loan_service import (
    LoanService,
    LoanSummary,
    LoanDryRunResult,
    LoanExecutionResult,
    STATUTORY_MAX_LOAN_DEDUCTION_PCT,
    STATUTORY_MAX_TOTAL_DEDUCTION_PCT,
)
from odoo_recruitment_write_gateway import OdooRecruitmentWriteGateway
from recruitment_service import (
    RecruitmentService,
    JobOpeningSummary,
    ApplicantSummary,
    ApplicantDryRunResult,
    ApplicantExecutionResult,
)
from odoo_contract_write_gateway import OdooContractWriteGateway
from contract_service import (
    ContractService,
    ContractSummary,
    ContractDryRunResult,
    ContractExecutionResult,
)
from odoo_payroll_write_gateway import OdooPayrollWriteGateway
from payroll_service import (
    PayrollService,
    PayslipSummary,
    PayslipDryRunResult,
    PayslipExecutionResult,
    WpsSifFileResult,
)
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
from saudi_labor_law_rules import OccasionLeaveType
from odoo_letter_write_gateway import OdooLetterWriteGateway
from letter_service import (
    LetterService,
    SUPPORTED_LETTER_TYPES,
    LetterDryRunResult,
    LetterApplyResult,
)
from odoo_warning_write_gateway import OdooWarningWriteGateway
from warning_service import (
    WarningService,
    WARNING_LEVELS,
    WarningDryRunResult,
    WarningApplyResult,
)
from odoo_expense_write_gateway import OdooExpenseWriteGateway
from expense_service import (
    ExpenseService,
    SUPPORTED_EXPENSE_CATEGORIES,
    ExpenseDryRunResult,
    ExpenseApplyResult,
)
from document_expiry_service import (
    DocumentExpiryService,
    DocumentExpiryScanResult,
    DOCUMENT_CATEGORIES,
)
from odoo_config_manager import (
    get_active_odoo_config,
    save_active_odoo_config,
    test_odoo_connection,
)




ROOT_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path("output") / "telegram_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TG_AUDIT_LOG_FILE = LOGS_DIR / "telegram_audit.log"

DEFAULT_COMPANY_ID = 15
DEFAULT_MAX_ROWS = 10
WRITE_API_TOKEN = os.environ.get("WRITE_API_TOKEN", "hr-write-secret-token")
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
            try:
                resp_ctx = urllib.request.urlopen(req, timeout=timeout, context=_DEFAULT_SSL_CONTEXT)
            except urllib.error.URLError as ssl_err:
                if "CERTIFICATE_VERIFY_FAILED" in str(ssl_err):
                    resp_ctx = urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())
                else:
                    raise ssl_err
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
            try:
                resp_ctx = urllib.request.urlopen(download_url, timeout=30.0, context=_DEFAULT_SSL_CONTEXT)
            except urllib.error.URLError as ssl_err:
                if "CERTIFICATE_VERIFY_FAILED" in str(ssl_err):
                    resp_ctx = urllib.request.urlopen(download_url, timeout=30.0, context=ssl._create_unverified_context())
                else:
                    raise ssl_err
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



def handle_excel_document(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    doc: Dict[str, Any],
    message_id: int,
) -> None:
    """Processes an uploaded Excel document: runs dry-run and replies with summary and approval button."""
    file_name = doc.get("file_name", "unnamed.xlsx")
    if not file_name.lower().endswith(".xlsx"):
        bot.send_message(
            chat_id,
            "⚠️ <b>تنبيه:</b> يجب أن يكون الملف بصيغة Excel (<code>.xlsx</code>) حصراً.",
            reply_to_message_id=message_id,
        )
        return

    bot.send_message(chat_id, f"⏳ جارِ استلام وفحص ملف <code>{file_name}</code> استباقياً واعتماده...", reply_to_message_id=message_id)

    safe_dest = UPLOAD_DIR / f"{int(time.time())}_{file_name}"
    success = bot.download_file(doc["file_id"], safe_dest)
    if not success:
        bot.send_message(chat_id, "❌ فشل تحميل الملف من خوادم تيليقرام. يرجى إعادة المحاولة.")
        return

    try:
        report_dict = dry_run_report.build_full_report(safe_dest)
    except Exception as exc:
        bot.send_message(chat_id, f"❌ <b>خطأ أثناء فحص الملف:</b>\n<code>{type(exc).__name__}: {exc}</code>")
        return

    run_id = report_dict["header"]["run_id"]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_output_dir = Path("output") / f"{run_id}_{timestamp}"
    run_output_dir.mkdir(parents=True, exist_ok=True)
    dry_run_report.write_report_files(report_dict, run_output_dir)

    summary = report_dict["summary"]
    counts = summary.get("status_counts", {})
    accepted = counts.get("accepted", 0)
    review = counts.get("needs_review", 0)
    rejected = counts.get("rejected", 0)
    total = summary.get("row_count", 0)

    report_path_str = str(run_output_dir / "dry_run_report.json")
    input_path_str = str(safe_dest)

    # Save session context for callback execution
    session_file = run_output_dir / "telegram_session.json"
    session_data = {
        "run_id": run_id,
        "input_path": input_path_str,
        "report_path": report_path_str,
        "folder": str(run_output_dir),
        "source_file_name": file_name,
        "accepted_rows": [r["excel_row_number"] for r in report_dict["rows"] if r["final_status"] == "accepted"],
        "user_id": str(user_id),
        "user_name": user_name,
    }
    session_file.write_text(json.dumps(session_data, ensure_ascii=False, indent=2), encoding="utf-8")

    text = (
        f"📊 <b>نتائج الفحص والتدقيق الاستباقي (Pre-Audit)</b>\n"
        f"────────────────────\n"
        f"📁 <b>الملف:</b> <code>{file_name}</code>\n"
        f"🆔 <b>معرّف الفحص:</b> <code>{run_id}</code>\n"
        f"📈 <b>إجمالي الصفوف:</b> <b>{total}</b>\n\n"
        f"  • جاهز للاعتماد (accepted): <b>{accepted}</b> ✅\n"
        f"  • يحتاج مراجعة (needs_review): <b>{review}</b> ⚠️\n"
        f"  • مرفوض (rejected): <b>{rejected}</b> ❌\n"
        f"────────────────────\n"
    )

    if accepted == 0 and review == 0 and rejected == 0:
        text += "⚠️ <i>لا توجد صفوف قابلة للمعالجة في هذا الملف.</i>"
        bot.send_message(chat_id, text)
        log_telegram_audit(user_id, chat_id, "dry_run_zero_rows", {"run_id": run_id, "file_name": file_name})
        return

    text += (
        f"👤 <b>المعتمد:</b> {user_name}\n"
        f"🏢 <b>المنشأة:</b> شركة النخبة الذكية للتقنية (15)\n\n"
        f"اختر الإجراء المناسب للمتابعة:"
    )

    keyboard_rows = []
    if accepted > 0:
        keyboard_rows.append([
            {"text": f"🚀 اعتمد وأنشئ ({accepted}) في Odoo", "callback_data": f"approve:{run_id}"},
            {"text": "❌ تراجع عن العملية", "callback_data": f"cancel:{run_id}"},
        ])

    if review > 0 or rejected > 0:
        keyboard_rows.append([
            {"text": f"🛠️ استشر «مصلح» لعلاج ({review + rejected}) صفوف معطوبة", "callback_data": f"musleh:heal:{run_id}"}
        ])

    inline_keyboard = {"inline_keyboard": keyboard_rows}
    bot.send_message(chat_id, text, reply_markup=inline_keyboard)
    log_telegram_audit(user_id, chat_id, "dry_run_ready", {"run_id": run_id, "accepted": accepted, "review": review, "rejected": rejected})


def handle_voice_message(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    voice_obj: Dict[str, Any],
    message_id: int,
) -> Optional[str]:
    """Downloads and transcribes a Telegram voice note or audio file via Whisper STT."""
    file_id = voice_obj.get("file_id")
    if not file_id:
        return None

    duration = voice_obj.get("duration", 0)
    dur_str = f" ({duration} ثانية)" if duration else ""
    bot.send_message(
        chat_id,
        f"🎙️ <b>استلمتُ تسجيلك الصوتي{dur_str}...</b>\nجارِ الاستماع والتحويل لنص عبر Whisper ⏳",
        reply_to_message_id=message_id,
    )

    safe_dest = UPLOAD_DIR / f"voice_{int(time.time())}_{file_id[:8]}.ogg"
    success = bot.download_file(file_id, safe_dest)
    if not success:
        bot.send_message(
            chat_id,
            "❌ <b>تعذر تحميل التسجيل الصوتي من تيليجرام.</b> يرجى إعادة المحاولة.",
            reply_to_message_id=message_id,
        )
        return None

    try:
        from whisper_service import WhisperSTTService
        whisper_engine = WhisperSTTService()
        trans_res = whisper_engine.transcribe(safe_dest, language="ar", delete_after=True)
    except Exception as exc:
        bot.send_message(
            chat_id,
            f"❌ <b>حدث خطأ أثناء معالجة الصوت:</b> <code>{type(exc).__name__}: {exc}</code>",
            reply_to_message_id=message_id,
        )
        return None

    if not trans_res.is_success or not trans_res.text.strip():
        bot.send_message(
            chat_id,
            "⚠️ <b>لم أتمكن من تمييز كلمات واضحة في التسجيل الصوتي.</b>\nيرجى التحدث بوضوح وإعادة المحاولة، أو كتابة طلبك نصياً.",
            reply_to_message_id=message_id,
        )
        return None

    transcribed_text = trans_res.text.strip()
    log_telegram_audit(
        user_id,
        chat_id,
        "voice_note_transcribed",
        {
            "duration": duration,
            "text": transcribed_text,
            "backend": trans_res.backend,
        },
    )

    bot.send_message(
        chat_id,
        f"🎙️ <b>النص المستخلص من التسجيل الصوتي:</b>\n"
        f"«<i>{transcribed_text}</i>»\n\n"
        f"⚡ <b>جارِ معالجة طلبك عبر «سراج»...</b>",
        reply_to_message_id=message_id,
    )

    return transcribed_text


def handle_approval_callback(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    message_id: int,
    callback_query_id: str,
    data: str,
) -> None:
    """Handles button clicks and requires written confirmation before execution (Section 5.1)."""
    action, run_id = data.split(":", 1)

    if action == "cancel":
        PENDING_CONFIRMATIONS.pop(str(chat_id), None)
        bot.answer_callback_query(callback_query_id, "تراجعتَ عن العملية.")
        bot.edit_message_text(chat_id, message_id, f"🚫 <b>تراجعتَ عن اعتماد العملية:</b> <code>{run_id}</code>")
        log_telegram_audit(user_id, chat_id, "cancel_clicked", {"run_id": run_id})
        return

    # Section 5.1: "يتطلب كلمة تأكيد مكتوبة (تأكيد) قبل التنفيذ، لا ضغطة زر واحدة فقط"
    PENDING_CONFIRMATIONS[str(chat_id)] = {
        "run_id": run_id,
        "user_id": str(user_id),
        "user_name": user_name,
        "timestamp": time.time(),
    }

    bot.answer_callback_query(callback_query_id, "يلزم تأكيد كتابي للمتابعة")
    confirm_prompt = (
        f"⚠️ <b>تأكيد أمان إلزامي</b>\n"
        f"أنت على وشك إضافة بيانات الفحص <code>{run_id}</code> فعلياً إلى خادم Odoo.\n\n"
        f"لحماية بيانات المنشأة من أي ضغطة غير مقصودة، اكتب كلمة <b>«تأكيد»</b> في المحادثة للمتابعة."
    )
    bot.edit_message_text(chat_id, message_id, confirm_prompt)
    log_telegram_audit(user_id, chat_id, "written_confirm_requested", {"run_id": run_id})


def handle_musleh_heal_callback(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    message_id: int,
    callback_query_id: str,
    run_id: str,
) -> None:
    """Executes Musleh consultation and healing on broken rows in dry-run report."""
    bot.answer_callback_query(callback_query_id, "جارِ تشخيص المشاكل وتشغيل مصلح...")

    output_root = Path("output")
    matching = list(output_root.glob(f"{run_id}_*"))
    if not matching and (output_root / run_id).is_dir():
        matching = [output_root / run_id]
    if not matching:
        bot.send_message(chat_id, f"❌ تعذر العثور على بيانات الفحص: <code>{run_id}</code>")
        return

    run_dir = matching[0]
    report_file = run_dir / "dry_run_report.json"
    if not report_file.exists():
        bot.send_message(chat_id, "❌ ملف تقرير الفحص غير موجود.")
        return

    try:
        report_data = json.loads(report_file.read_text(encoding="utf-8"))
        val_rows = report_data.get("rows", [])
        val_map = {r.get("excel_row_number"): r for r in val_rows}

        session_file = run_dir / "telegram_session.json"
        raw_rows = []
        parsed_row_map = {}
        if session_file.exists():
            s_data = json.loads(session_file.read_text(encoding="utf-8"))
            input_path = s_data.get("input_path")
            if input_path and Path(input_path).exists():
                from parser import parse_xlsx
                try:
                    p_res = parse_xlsx(Path(input_path))
                    parsed_row_map = {r["excel_row_number"]: r for r in p_res.get("rows", [])}
                except Exception as ex:
                    logger.warning("Could not re-parse excel for musleh: %s", ex)

        for vr in val_rows:
            rn = vr.get("excel_row_number")
            p_row = parsed_row_map.get(rn)
            if p_row:
                raw_rows.append(p_row)
            else:
                raw_rows.append({
                    "excel_row_number": rn,
                    "fields": vr.get("resolved_references", {}) or {},
                })

        from musleh_service import MuslehService
        repo = OdooReadonlyRepository()
        musleh = MuslehService(repository=repo)
        auto_repair = is_autofix_enabled(chat_id)
        heal_res = musleh.heal_batch(rows=raw_rows, validation_results=val_rows, auto_repair=auto_repair)

        ready_count = heal_res.get("ready_to_create_count", 0)
        quarantine_count = heal_res.get("quarantined_count", 0)
        accepted_rows_list = heal_res.get("accepted_rows", [])
        quarantined_rows_list = heal_res.get("quarantined_rows", [])

        if session_file.exists():
            s_data = json.loads(session_file.read_text(encoding="utf-8"))
            s_data["accepted_rows"] = [r["excel_row_number"] for r in accepted_rows_list]
            session_file.write_text(json.dumps(s_data, ensure_ascii=False, indent=2), encoding="utf-8")

        mode_badge = "🟢 تلقائي نشط (/autofix on)" if auto_repair else "⏸️ مراجعة فقط (/autofix off)"

        heal_msg = (
            f"🛠️ <b>تقرير وكيل الإصلاح «مصلح» للفحص</b> <code>{run_id}</code>:\n"
            f"• <b>نمط المعالجة:</b> {mode_badge}\n"
            f"────────────────────\n"
            f"✅ <b>الصفوف الجاهزة للإنشاء الآن:</b> <b>{ready_count}</b> صفاً\n"
            f"📦 <b>الصفوف المعزولة (Quarantined):</b> <b>{quarantine_count}</b> صفاً\n"
        )

        field_labels_ar = {
            "name": "الاسم",
            "mobile_phone": "الجوال",
            "work_phone": "الهاتف",
            "work_email": "البريد الإلكتروني",
            "department": "القسم",
            "job": "المسمى الوظيفي",
            "hiring_date": "تاريخ التعيين",
            "company": "الشركة",
        }

        # 1. عرض التعديلات المنفذة تلقائياً (قبل وبعد) عند تفعيل autofix
        if auto_repair and ready_count > 0:
            healed_diffs = []
            for acc in accepted_rows_list:
                rn = acc.get("excel_row_number")
                orig = parsed_row_map.get(rn)
                if not orig:
                    continue
                ename = acc.get("fields", {}).get("name", {}).get("value") or orig.get("fields", {}).get("name", {}).get("value") or f"صف {rn}"
                diffs = []
                for fn, fv in acc.get("fields", {}).items():
                    or_val = orig.get("fields", {}).get(fn, {}).get("raw", "")
                    nw_val = fv.get("value", "") if isinstance(fv, dict) else str(fv)
                    if or_val and nw_val and str(or_val).strip() != str(nw_val).strip():
                        lbl = field_labels_ar.get(fn, fn)
                        diffs.append(f"  • {lbl}: <s>{or_val}</s> (قبل) ➔ <b>{nw_val}</b> (بعد المصححة)")
                if diffs:
                    healed_diffs.append((rn, ename, diffs))

            if healed_diffs:
                heal_msg += "\n✨ <b>الصفوف المصححة تلقائياً «قبل وبعد»:</b>\n"
                for rn, ename, diffs in healed_diffs[:4]:
                    heal_msg += f"• صف {rn} (<b>{ename}</b>):\n" + "\n".join(diffs) + "\n"

        # 2. عرض الصفوف المعزولة والمقترحات التشخيصية «قبل وبعد»
        if quarantined_rows_list:
            heal_msg += "\n🚨 <b>تفاصيل الصفوف المعزولة والمقترحات «قبل وبعد»:</b>\n"
            for q in quarantined_rows_list[:4]:
                dec = q.get("decision", {})
                rn = dec.get("excel_row_number") or q.get("row", {}).get("excel_row_number")
                orig = parsed_row_map.get(rn, {})
                ename = orig.get("fields", {}).get("name", {}).get("value") or f"صف {rn}"
                pf = dec.get("patched_fields", {})
                vr = val_map.get(rn, {})
                reasons = vr.get("reasons", [])

                heal_msg += f"• صف {rn} (<b>{ename}</b>):\n"
                has_prop = False
                if pf:
                    for k, v in pf.items():
                        if k in ("missing_entity", "entity_type"):
                            continue
                        or_val = orig.get("fields", {}).get(k, {}).get("raw", "")
                        conf = int(dec.get("confidence", 1) * 100)
                        lbl = field_labels_ar.get(k, k)
                        heal_msg += f"  • {lbl}: <s>{or_val}</s> (قبل) ➔ <b>{v}</b> (بعد المقترح - مطابقة {conf}%)\n"
                        has_prop = True
                if not has_prop:
                    reason_clean = reasons[0] if reasons else dec.get("verdict_ar", "")
                    if "Existing employee found by work_email" in reason_clean:
                        email_part = reason_clean.split(":")[-1].strip()
                        reason_clean = f"البريد ({email_part}) مسجل مسبقاً في Odoo لموظف قائم"
                    elif "Department not found" in reason_clean:
                        dept_part = reason_clean.split(":")[-1].strip()
                        reason_clean = f"القسم ({dept_part}) غير مسجل في Odoo لهذه الشركة"
                    elif "Company not found" in reason_clean:
                        comp_part = reason_clean.split(":")[-1].strip()
                        reason_clean = f"الشركة ({comp_part}) غير مسجلة في Odoo"
                    elif "Duplicate row detected" in reason_clean:
                        reason_clean = "الصف مكرر بالكامل داخل نفس الملف"
                    heal_msg += f"  • ❌ تعذر التصحيح: {reason_clean} (الهويات والكيانات غير المعرفة لا تُعدل آلياً)\n"

        root_causes = heal_res.get("batch_root_causes", [])
        if root_causes:
            heal_msg += "\n💡 <b>توصيات مصلح الذكية للدفعة:</b>\n"
            for rc in root_causes:
                heal_msg += f"• {rc.get('recommendation_ar')}\n"

        if not auto_repair and quarantine_count > 0:
            heal_msg += "\n💡 <i>ملاحظة: وضع التصحيح التلقائي معطّل حالياً. لتفعيل المعالجة الفورية أرسل <code>/autofix on</code> أو اضغط الزر أدناه.</i>\n"

        heal_kb_rows = []
        if not auto_repair and quarantine_count > 0:
            heal_kb_rows.append([
                {"text": "⚡ تفعيل التصحيح التلقائي وإعادة الفحص", "callback_data": f"musleh:heal_auto:{run_id}"}
            ])
        if ready_count > 0:
            heal_kb_rows.append([
                {"text": f"🚀 اعتمد وأنشئ ({ready_count}) في Odoo الآن", "callback_data": f"approve:{run_id}"},
                {"text": "❌ تراجع", "callback_data": f"cancel:{run_id}"},
            ])
        heal_kb_rows.append([
            {"text": "⚙️ إعدادات /autofix", "callback_data": "autofix:status"},
            {"text": "🔙 القائمة الرئيسية", "callback_data": "menu:main"},
        ])

        bot.send_message(chat_id, heal_msg, reply_markup={"inline_keyboard": heal_kb_rows})
        log_telegram_audit(user_id, chat_id, "musleh_batch_healed", {"run_id": run_id, "ready_count": ready_count, "auto_repair": auto_repair})
    except Exception as exc:
        bot.send_message(chat_id, f"❌ حدث خطأ أثناء تشغيل مصلح: <code>{exc}</code>")


def execute_via_backend_api(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    run_id: str,
    reply_to_msg_id: int,
) -> None:
    """Executes creation by calling the centralized Backend API (/write) rather than direct writer (Section 5.2)."""
    bot.send_message(
        chat_id,
        f"⏳ <b>جارِ استدعاء الـ API الخلفي للاعتماد والإنشاء في Odoo...</b>\nمعرّف الفحص: <code>{run_id}</code>",
        reply_to_message_id=reply_to_msg_id,
    )
    log_telegram_audit(user_id, chat_id, "api_write_dispatched", {"run_id": run_id})

    api_url = f"{API_BASE_URL.rstrip('/')}/api/approve-and-execute"
    payload = {
        "run_id": run_id,
        "approved_by": f"{user_name} (Telegram ID: {user_id})",
        "company_id": DEFAULT_COMPANY_ID,
        "max_rows": DEFAULT_MAX_ROWS,
    }

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": WRITE_API_TOKEN,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))

            if data.get("status") == "success":
                created = data.get("created_count", 0)
                items = data.get("created_items", [])
                lines = [
                    f"🎉 <b>اكتمل الإنشاء الحي في Odoo بنجاح!</b>",
                    f"────────────────────",
                    f"🏢 <b>الشركة:</b> شركة النخبة الذكية للتقنية (15)",
                    f"🆔 <b>معرّف الفحص:</b> <code>{run_id}</code>",
                    f"👤 <b>المعتمد:</b> {user_name} (ID: <code>{user_id}</code>)",
                    f"📊 <b>العدد المُنشأ:</b> <b>{created} موظف(ين)</b>",
                    f"────────────────────",
                    f"<b>👥 سجل الموظفين الجدد:</b>",
                ]
                for it in items:
                    lines.append(f"  ✅ <b>{it.get('name')}</b> — معرّف Odoo: <code>#{it.get('odoo_id')}</code>")
                lines.append("────────────────────")
                lines.append(f"✨ تم توثيق الاعتماد وتحديث قاعدة البيانات بأمان تام.")
                bot.send_message(chat_id, "\n".join(lines), reply_to_message_id=reply_to_msg_id)
                log_telegram_audit(user_id, chat_id, "api_write_success", {"run_id": run_id, "created": created})
            else:
                bot.send_message(
                    chat_id,
                    f"❌ <b>فشل الإنشاء:</b> <code>{data.get('detail')}</code>",
                    reply_to_message_id=reply_to_msg_id,
                )
                log_telegram_audit(user_id, chat_id, "api_write_failed", {"run_id": run_id, "error": data.get("detail")})
    except urllib.error.HTTPError as exc:
        err_msg = exc.read().decode("utf-8", errors="ignore")
        bot.send_message(
            chat_id,
            f"❌ <b>خطأ من خادم الـ API:</b> HTTP {exc.code}\n<code>{err_msg}</code>",
            reply_to_message_id=reply_to_msg_id,
        )
        log_telegram_audit(user_id, chat_id, "api_write_http_error", {"code": exc.code, "error": err_msg})
    except Exception as exc:
        bot.send_message(
            chat_id,
            f"❌ <b>تعذر استدعاء الـ API الخلفي:</b>\n<code>{type(exc).__name__}: {exc}</code>",
            reply_to_message_id=reply_to_msg_id,
        )
        log_telegram_audit(user_id, chat_id, "api_write_exception", {"error": str(exc)})


# ---------------------------------------------------------------------------
# Templates & Multi-Database Management
# ---------------------------------------------------------------------------

TEMPLATES_CATALOG: Dict[str, Dict[str, Any]] = {
    "master": {
        "title": "🏢 1. القالب الشامل لتأسيس المنشأة (Master)",
        "file": Path("templates") / "master" / "Master_Client_Onboarding_Template.xlsx",
        "caption": "🏢 <b>القالب الشامل لتأسيس المنشأة الجديدة في Odoo HR</b>\nيحتوي على كافة التبويبات لتأسيس الشركة، الفروع، الأقسام، الموظفين، العقود، الرواتب، والإجازات.",
    },
    "emp": {
        "title": "👥 2. قالب الموظفين ومواقع العمل",
        "file": Path("templates") / "modular" / "template_employees.xlsx",
        "caption": "👥 <b>قالب استيراد الموظفين ومواقع العمل</b>\nلتسجيل بيانات الموظفين، الهويات، الجنسيات، والأقسام والفروع.",
    },
    "contract": {
        "title": "📜 3. قالب العقود والبدلات (hr.version)",
        "file": Path("templates") / "modular" / "template_contracts_allowances.xlsx",
        "caption": "📜 <b>قالب عقود العمل والبدلات</b>\nلتوثيق العقود، الراتب الأساسي، بدل السكن، النقل، وفترة التجربة (مادة 53).",
    },
    "payroll": {
        "title": "💰 4. قالب الرواتب وتأمينات GOSI",
        "file": Path("templates") / "modular" / "template_payroll_gosi.xlsx",
        "caption": "💰 <b>قالب الرواتب والتأمينات الاجتماعية (GOSI)</b>\nلحسابات نسب التأمينات والآيبان البنكي لنظام حماية الأجور WPS.",
    },
    "timeoff": {
        "title": "🏖️ 5. قالب الإجازات والأرصدة",
        "file": Path("templates") / "modular" / "template_timeoff.xlsx",
        "caption": "🏖️ <b>قالب الإجازات والأرصدة الافتتاحية</b>\nلتسجيل الإجازات السنوية وإجازات المناسبات نظاماً (زواج، وفاة، مولود).",
    },
    "attend": {
        "title": "⏰ 6. قالب ساعات الحضور والدوام",
        "file": Path("templates") / "modular" / "template_attendance.xlsx",
        "caption": "⏰ <b>قالب كشف الحضور وساعات العمل</b>\nلتسجيل ساعات الدوام الفعلية، والتأخير والغياب الشهري.",
    },
    "overtime": {
        "title": "⏱️ 7. قالب العمل الإضافي (مادة 107)",
        "file": Path("templates") / "modular" / "template_overtime.xlsx",
        "caption": "⏱️ <b>قالب العمل الإضافي (الأوفرتايم)</b>\nلحساب ساعات الإضافي بمعامل 1.5x الأجر المعتاد بموجب المادة 107.",
    },
    "loan": {
        "title": "💳 8. قالب القروض وسلف الموظفين",
        "file": Path("templates") / "modular" / "template_loans_installments.xlsx",
        "caption": "💳 <b>قالب سلف وقروض الموظفين (مادة 92)</b>\nلجدولة الأقساط الشهرية مع ضمان عدم تجاوز 25% من الراتب.",
    },
    "disc": {
        "title": "⚖️ 9. قالب الجزاءات والإنذارات",
        "file": Path("templates") / "modular" / "template_disciplinary.xlsx",
        "caption": "⚖️ <b>قالب الجزاءات والإنذارات التأديبية</b>\nلتوثيق محاضر التحقيق وقرارات الخصم المعتمدة.",
    },
    "eos": {
        "title": "📑 10. قالب مكافأة نهاية الخدمة",
        "file": Path("templates") / "modular" / "template_end_of_service.xlsx",
        "caption": "📑 <b>قالب مكافأة نهاية الخدمة والتسويات</b>\nلحساب مستحقات انتهاء العقد والاستقالة والفصل وفق مواد نظام العمل.",
    },
    "appraisal": {
        "title": "🌟 11. قالب تقييمات الأداء",
        "file": Path("templates") / "modular" / "template_appraisals.xlsx",
        "caption": "🌟 <b>قالب تقييمات أداء الموظفين</b>\nلتقييم الأداء السنوي وفترة التجربة ومعدلات الأهداف والكفاءات.",
    },
    "recruit": {
        "title": "🎯 12. قالب شواغر التوظيف والمتقدمين",
        "file": Path("templates") / "modular" / "template_recruitment.xlsx",
        "caption": "🎯 <b>قالب شواغر التوظيف والمرشحين</b>\nلتسجيل المتقدمين ونتائج المقابلات وعروض العمل.",
    },
    "gr": {
        "title": "🏛️ 13. قالب المعاملات الحكومية والجوازات",
        "file": Path("templates") / "modular" / "template_gr_transactions.xlsx",
        "caption": "🏛️ <b>قالب المعاملات الحكومية والتأشيرات</b>\nلتجديد الإقامات والجوازات ورخص العمل عبر مقيم وقوى.",
    },
    "company": {
        "title": "🏢 14. قالب بيانات تأسيس الشركة",
        "file": Path("templates") / "modular" / "template_company_setup.xlsx",
        "caption": "🏢 <b>قالب تأسيس المنشأة والحسابات البنكية</b>\nللسجل التجاري والرقم الضريبي والآيبان والعنوان الوطني.",
    },
}


def get_main_menu_keyboard() -> Dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "📥 استلم قوالب الإكسل (14 قالباً)", "callback_data": "menu:templates"},
                {"text": "🌴 طلب واستعلام الإجازات", "callback_data": "menu:leaves"},
            ],
            [
                {"text": "⏰ الحضور والعمل الإضافي", "callback_data": "menu:attendance"},
                {"text": "⚖️ الجزاءات والانضباط", "callback_data": "menu:disciplinary"},
            ],
            [
                {"text": "💼 نهاية الخدمة والتسويات", "callback_data": "menu:eos"},
                {"text": "🏛️ المعاملات ومقيم وقوى", "callback_data": "menu:gr"},
            ],
            [
                {"text": "🌟 تقييمات الأداء والموظفين", "callback_data": "menu:appraisal"},
                {"text": "💳 السلف وقروض الموظفين", "callback_data": "menu:loan"},
            ],
            [
                {"text": "🎯 شواغر التوظيف والمرشحين", "callback_data": "menu:recruitment"},
                {"text": "📜 عقود العمل وهيكلة الأجور", "callback_data": "menu:contract"},
            ],
            [
                {"text": "📊 المؤشرات والتحليلات الشاملة", "callback_data": "menu:analytics"},
                {"text": "💵 مسير الرواتب وحماية الأجور (WPS)", "callback_data": "menu:payroll"},
            ],
            [
                {"text": "🔗 اربط خادم Odoo جديداً", "callback_data": "odoo:edit_wizard"},
                {"text": "⚙️ راجع بيانات الاتصال الحالية", "callback_data": "menu:odoo_settings"},
            ],
            [
                {"text": "🏢 تصفح الشركات والفروع", "callback_data": "menu:show_companies"},
                {"text": "📈 تابع جاهزية الوكلاء", "callback_data": "menu:system_status"},
            ],
            [
                {"text": "📜 الخطابات وشهادات التعريف", "callback_data": "menu:letters"},
                {"text": "🧾 المصروفات والانتدابات", "callback_data": "menu:expenses"},
            ],
            [
                {"text": "🔔 تنبيهات وصلاحيات الوثائق", "callback_data": "menu:expiries"},
                {"text": "🛡️ تقرير التدقيق الرقابي PDF (سجل)", "callback_data": "audit:pdf"},
            ],
            [
                {"text": "🛠️ وكيل الإصلاح الذاتي (مصلح)", "callback_data": "musleh:info"},
            ],
            [
                {"text": "🔗 إعدادات وربط خادم Odoo", "callback_data": "menu:odoo_settings"},
            ]
        ]
    }


def get_templates_menu_keyboard() -> Dict[str, Any]:
    buttons = [
        [{"text": "🏢 1. حمّل القالب الشامل لتأسيس المنشأة (Master)", "callback_data": "get_tpl:master"}],
        [
            {"text": "👥 2. الموظفون", "callback_data": "get_tpl:emp"},
            {"text": "📜 3. العقود والبدلات", "callback_data": "get_tpl:contract"},
        ],
        [
            {"text": "💰 4. الرواتب والتأمينات", "callback_data": "get_tpl:payroll"},
            {"text": "🏖️ 5. الإجازات", "callback_data": "get_tpl:timeoff"},
        ],
        [
            {"text": "⏰ 6. الحضور والدوام", "callback_data": "get_tpl:attend"},
            {"text": "⏱️ 7. ساعات العمل الإضافية", "callback_data": "get_tpl:overtime"},
        ],
        [
            {"text": "💳 8. السلف والأقساط", "callback_data": "get_tpl:loan"},
            {"text": "⚖️ 9. الجزاءات والإنذارات", "callback_data": "get_tpl:disc"},
        ],
        [
            {"text": "📑 10. مكافأة نهاية الخدمة", "callback_data": "get_tpl:eos"},
            {"text": "🌟 11. تقييمات الأداء", "callback_data": "get_tpl:appraisal"},
        ],
        [
            {"text": "🎯 12. التوظيف والمرشحين", "callback_data": "get_tpl:recruit"},
            {"text": "🏛️ 13. المعاملات والجوازات", "callback_data": "get_tpl:gr"},
        ],
        [
            {"text": "🏢 14. بيانات المنشأة البنكية", "callback_data": "get_tpl:company"},
        ],
        [
            {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
        ]
    ]
    return {"inline_keyboard": buttons}


# =============================================================================
# وظائف إدارة الإجازات ونظام العمل السعودي (Phase 10: Leaves Management)
# =============================================================================

_BOT_LEAVE_SERVICE: Optional[LeaveService] = None

def get_leave_service_for_bot(force_refresh: bool = False) -> LeaveService:
    global _BOT_LEAVE_SERVICE
    if _BOT_LEAVE_SERVICE is not None and not force_refresh:
        return _BOT_LEAVE_SERVICE
    repo = OdooReadonlyRepository()
    gw = None
    try:
        gw = OdooLeaveWriteGateway(
            url=repo.url,
            db=repo.db,
            login=repo.username,
            password=repo.api_key,
        )
    except Exception:
        pass
    _BOT_LEAVE_SERVICE = LeaveService(readonly_repo=repo, write_gateway=gw)
    return _BOT_LEAVE_SERVICE


def show_leaves_menu(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "🌴 <b>إدارة الإجازات ونظام العمل السعودي (1446هـ)</b> 🏢\n"
        "────────────────────\n"
        "أهلاً بك! يمكنك عبر هذا القسم استعلام وتدقيق إجازات الموظفين وفق الأنظمة الرسمية:\n\n"
        "• <b>الرصيد والاستحقاق:</b> فحص رصيد الموظف واستحقاقه السنوي (المادة 109: 21 أو 30 يوماً).\n"
        "• <b>طلب إجازة جديدة:</b> تدقيق حتمي استباقي معتمد ومطابقة الأنظمة قبل Odoo.\n"
        "• <b>دليل الأنظمة:</b> استعراض ضوابط إجازات المناسبات والوضع وتعديلات 1446هـ."
    )
    kb = {
        "inline_keyboard": [
            [
                {"text": "📊 رصيد واستحقاق الموظف", "callback_data": "leave:balance_prompt"},
                {"text": "📝 طلب إجازة جديدة", "callback_data": "leave:request_wizard"},
            ],
            [
                {"text": "⚖️ دليل إجازات نظام العمل (1446هـ)", "callback_data": "leave:law_guide"},
            ],
            [
                {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_leaves_law_guide(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "⚖️ <b>دليل إجازات نظام العمل السعودي وتعديلات 1446هـ (م/44):</b>\n"
        "────────────────────\n"
        "🌴 <b>1. الإجازة السنوية (المادة 109):</b>\n"
        "  • <b>21 يوماً</b> بأجر كامل لمن أمضى خدمة أقل من 5 سنوات.\n"
        "  • <b>30 يوماً</b> بأجر كامل لمن أمضى 5 سنوات خدمة متصلة فأكثر.\n\n"
        "🎉 <b>2. إجازات المناسبات مدفوعة الأجر (المادة 113):</b>\n"
        "  • زواج العامل: <b>5 أيام</b>.\n"
        "  • وفاة الزوج أو أحد الأصول أو الفروع: <b>5 أيام</b>.\n"
        "  • وفاة الأخ أو الأخت (تعديل 1446هـ): <b>3 أيام</b>.\n"
        "  • ولادة مولود للموظف (أبوة - تعديل 1446هـ): <b>3 أيام</b>.\n\n"
        "🤱 <b>3. إجازة الوضع للمرأة العاملة (المادة 116):</b>\n"
        "  • <b>12 أسبوعاً بأجر كامل</b> (تعديل 1446هـ)، منها 6 أسابيع إلزامية بعد الوضع.\n\n"
        "🩺 <b>4. الإجازة المرضية (المادة 117):</b>\n"
        "  • أول 30 يوماً: بأجر كامل (100%).\n"
        "  • الـ 60 يوماً التالية: بثلاثة أرباع الأجر (75%).\n"
        "  • الـ 30 يوماً التالية: بدون أجر خلال السنة الواحدة."
    )
    kb = {
        "inline_keyboard": [
            [{"text": "📝 تقديم إجازة الآن", "callback_data": "leave:request_wizard"}],
            [{"text": "🔙 عُد لقائمة الإجازات", "callback_data": "menu:leaves"}],
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_employee_leaves_balance(bot: TelegramBotClient, chat_id: int | str, employee_id: int, message_id: Optional[int] = None) -> None:
    service = get_leave_service_for_bot()
    try:
        summary = service.get_employee_leave_summary(employee_id)
        text = (
            f"📊 <b>بطاقة رصيد واستحقاق الإجازات</b> 🌴\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {summary.employee_name} (معرّف #{summary.employee_id})\n"
            f"🏢 <b>القسم:</b> {summary.department_name}\n"
            f"⏳ <b>سنوات الخدمة:</b> <b>{summary.service_years} سنة</b>\n"
            f"────────────────────\n"
            f"⚖️ <b>الاستحقاق السنوي النظامي (م/109):</b> <b>{summary.statutory_annual_entitlement} يوماً</b>\n"
            f"📦 <b>إجمالي الأيام المخصصة في Odoo:</b> {summary.allocated_days:,.1f} يوماً\n"
            f"📉 <b>الأيام المستهلكة المعتمدة:</b> {summary.consumed_days:,.1f} يوماً\n"
            f"✨ <b>الرصيد المتاح للاستخدام:</b> <b>{summary.remaining_days:,.1f} يوماً</b>\n"
            f"────────────────────\n"
        )
        if summary.recent_leaves:
            text += "🗓️ <b>آخر الإجازات المسجلة:</b>\n"
            for lv in summary.recent_leaves[:3]:
                d_from = lv.get("request_date_from", "")
                days = lv.get("number_of_days", 0)
                st = lv.get("state", "")
                text += f"  • {d_from} ({days} يوماً) - حالة: <code>{st}</code>\n"
        else:
            text += "<i>لا توجد إجازات سابقة مسجلة لهذا الموظف.</i>\n"

        kb = {
            "inline_keyboard": [
                [{"text": "📝 تقديم إجازة لهذا الموظف", "callback_data": f"leave:req_for:{employee_id}"}],
                [{"text": "🔙 عُد لقائمة الإجازات", "callback_data": "menu:leaves"}],
            ]
        }
        if message_id:
            bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
        else:
            bot.send_message(chat_id, text, reply_markup=kb)
    except Exception as exc:
        err_text = f"❌ <b>خطأ:</b> تعذر جلب رصيد الموظف #{employee_id}: <code>{exc}</code>"
        kb = {"inline_keyboard": [[{"text": "🔙 عُد لقائمة الإجازات", "callback_data": "menu:leaves"}]]}
        if message_id:
            bot.edit_message_text(chat_id, message_id, err_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, err_text, reply_markup=kb)


def prompt_leave_type_selection(bot: TelegramBotClient, chat_id: int | str, employee_id: int, message_id: Optional[int] = None) -> None:
    service = get_leave_service_for_bot()
    types = service.get_leave_types()
    buttons = []
    row = []
    for t in types:
        row.append({"text": t.name, "callback_data": f"leave_type:{t.id}"})
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([{"text": "❌ تراجع", "callback_data": "leave:cancel"}])

    text = (
        f"📋 <b>اختر نوع الإجازة المطلوبة للموظف #{employee_id}:</b>\n"
        "────────────────────\n"
        "حدد نوع الإجازة من القائمة المتاحة في نظام Odoo:"
    )
    kb = {"inline_keyboard": buttons}
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def resolve_employee_input_for_wizard(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_input: str,
    wiz_type: str,
    cancel_callback: str,
    message_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Resolves employee from numeric ID, name, email, or national ID.
    - If 1 employee found: returns employee dict immediately.
    - If multiple found: sends an interactive Inline Keyboard button list for disambiguation and returns None.
    - If 0 found: sends a polite guidance message with ID example and returns None.
    """
    clean_text = user_input.strip()
    # تجنب البحث في أسماء الموظفين عن أسئلة أو استفسارات عامة
    if any(q in clean_text for q in ("؟", "?", "كم", "عدد", "ما هي", "ماهي", "ما هو", "ماهو", "هل", "أين", "كيف", "احسب")):
        return None

    repo = OdooReadonlyRepository()
    cands = repo.search_employee_candidates(clean_text, limit=8)

    if not cands:
        if clean_text.isdigit():
            return {"id": int(clean_text), "name": f"موظف #{clean_text}"}

        bot.send_message(
            chat_id,
            f"⚠️ لم يتم العثور على موظف يطابق «<b>{clean_text}</b>» في Odoo.\n\n"
            f"💡 <i>يرجى كتابة جزء آخر من الاسم، أو رقم الهوية/الإقامة، أو رقم المعرّف ID مباشرة (مثال: <code>147</code>):</i>",
            reply_markup={"inline_keyboard": [[{"text": "❌ إلغاء العملية", "callback_data": cancel_callback}]]},
            reply_to_message_id=message_id,
        )
        return None

    if len(cands) == 1:
        return cands[0]

    # Multiple matching employees found! Show interactive selection buttons
    keyboard_rows = []
    for c in cands:
        eid = c.get("id")
        name = c.get("name", "موظف")
        job = c.get("job_id")
        job_title = f" ({job[1]})" if isinstance(job, (list, tuple)) and len(job) > 1 else ""
        btn_text = f"👤 {name} (ID: #{eid}){job_title}"
        keyboard_rows.append([
            {"text": btn_text, "callback_data": f"wiz_emp:{wiz_type}:{eid}"}
        ])
    keyboard_rows.append([
        {"text": "❌ إلغاء العملية", "callback_data": cancel_callback}
    ])

    bot.send_message(
        chat_id,
        f"🔍 <b>وجدنا ({len(cands)}) موظفين يطابقون «{clean_text}»:</b>\n"
        f"────────────────────\n"
        f"يرجى النقر على الموظف المطلوب للمتابعة خطوة بخطوة:",
        reply_markup={"inline_keyboard": keyboard_rows},
        reply_to_message_id=message_id,
    )
    return None


def handle_leave_wizard_step(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    text: str,
    msg_id: Optional[int] = None,
) -> bool:
    wiz = ACTIVE_LEAVE_WIZARDS.get(str(chat_id))
    if not wiz:
        return False

    clean_text = text.strip()
    mode = wiz.get("mode")

    if clean_text in ("إلغاء", "تراجع", "خروج", "cancel"):
        ACTIVE_LEAVE_WIZARDS.pop(str(chat_id), None)
        show_leaves_menu(bot, chat_id)
        return True

    if mode == "balance":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "leave_bal", "menu:leaves", msg_id)
        if not emp:
            return True
        ACTIVE_LEAVE_WIZARDS.pop(str(chat_id), None)
        show_employee_leaves_balance(bot, chat_id, emp["id"])
        return True

    if mode == "request":
        step = wiz.get("step")
        if step == "emp":
            emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "leave_req", "leave:cancel", msg_id)
            if not emp:
                return True
            wiz["employee_id"] = emp["id"]
            wiz["step"] = "type"
            prompt_leave_type_selection(bot, chat_id, emp["id"])
            return True

        elif step == "dates":
            parts = clean_text.split()
            date_from = parts[0]
            date_to = parts[1] if len(parts) > 1 else date_from

            emp_id = wiz["employee_id"]
            type_id = wiz.get("holiday_status_id", 1)

            service = get_leave_service_for_bot()
            dry_res = service.dry_run_leave_request(
                employee_id=emp_id,
                holiday_status_id=type_id,
                date_from=date_from,
                date_to=date_to,
                reason="طلب عبر تيليقرام سراج"
            )

            if not dry_res.is_valid:
                err_msg = "❌ <b>تعذر قبول تواريخ الإجازة للأسباب التالية:</b>\n"
                for e in dry_res.errors:
                    err_msg += f"  • {e}\n"
                err_msg += "\nيرجى إعادة إرسال التواريخ بصيغة صحيحة (YYYY-MM-DD):"
                bot.send_message(chat_id, err_msg, reply_to_message_id=msg_id)
                return True

            ACTIVE_LEAVE_WIZARDS.pop(str(chat_id), None)
            token = dry_res.approval_token

            summary_text = (
                f"📊 <b>نتائج الفحص والتدقيق الاستباقي لطلب الإجازة:</b>\n"
                f"────────────────────\n"
                f"👤 <b>الموظف:</b> {dry_res.employee_name} (#{dry_res.employee_id})\n"
                f"🌴 <b>النوع:</b> {dry_res.leave_type_name}\n"
                f"📅 <b>الفترة:</b> من <code>{dry_res.request_date_from}</code> إلى <code>{dry_res.request_date_to}</code>\n"
                f"⏱️ <b>الأيام المطلوبة:</b> <b>{dry_res.number_of_days} يوماً</b>\n"
                f"⚖️ <b>المرجع النظامي:</b> {dry_res.statutory_article}\n"
                f"💡 <b>التفسير:</b> {dry_res.statutory_explanation_ar}\n"
                f"📉 <b>الرصيد المتاح:</b> {dry_res.balance_before:,.1f} ➔ <b>{dry_res.balance_after:,.1f} يوماً</b>\n"
                f"────────────────────\n"
            )
            if dry_res.warnings:
                summary_text += "⚠️ <b>ملاحظات:</b>\n"
                for w in dry_res.warnings:
                    summary_text += f"  • {w}\n"
                summary_text += "────────────────────\n"

            summary_text += (
                f"🆔 <b>رمز الاعتماد:</b> <code>{token}</code>\n"
                f"اضغط الزر أدناه ثم اكتب «تأكيد» للاعتماد النهائي في Odoo:"
            )

            kb = {
                "inline_keyboard": [
                    [
                        {"text": "🚀 اعتماد وتسجيل الإجازة في Odoo", "callback_data": f"leave_approve:{token}"},
                        {"text": "❌ تراجع", "callback_data": "leave:cancel"},
                    ]
                ]
            }
            bot.send_message(chat_id, summary_text, reply_markup=kb, reply_to_message_id=msg_id)
            return True

    return False


def execute_leave_via_service(
    bot: TelegramBotClient,
    chat_id: int | str,
    token: str,
    msg_id: Optional[int] = None,
) -> None:
    service = get_leave_service_for_bot()
    bot.send_message(chat_id, "⏳ جارِ تسجيل الإجازة في Odoo والتحقق المستقل منها...", reply_to_message_id=msg_id)
    try:
        res = service.apply_leave_request(approval_token=token, user_confirmation_text="تأكيد")
        if res.success:
            succ_text = (
                f"🎉 <b>تم اعتماد وتسجيل الإجازة بنجاح في Odoo!</b>\n"
                f"────────────────────\n"
                f"👤 <b>الموظف:</b> {res.employee_name} (#{res.employee_id})\n"
                f"📋 <b>نوع الإجازة:</b> {res.leave_type_name}\n"
                f"📅 <b>المدة:</b> <b>{res.number_of_days} يوماً</b> ({res.request_date_from} إلى {res.request_date_to})\n"
                f"🔖 <b>رقم السجل في Odoo:</b> <code>#{res.leave_id}</code>\n"
                f"✅ <b>التحقق المستقل:</b> ناجح ومطابق (Readback Verified)\n"
                f"────────────────────\n"
                f"تم حفظ العملية في سجل التدقيق المركزي بنجاح."
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "🌴 العودة لقائمة الإجازات", "callback_data": "menu:leaves"}],
                    [{"text": "🔙 القائمة الرئيسية", "callback_data": "menu:main"}],
                ]
            }
            bot.send_message(chat_id, succ_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, f"❌ <b>فشل تسجيل الإجازة:</b> {res.message_ar}")
    except Exception as exc:
        bot.send_message(chat_id, f"❌ <b>خطأ أثناء التنفيذ:</b> <code>{exc}</code>")


# وظائف إدارة الحضور والعمل الإضافي ونظام العمل السعودي (Phase 11: Attendance & Overtime)

_BOT_ATTENDANCE_SERVICE: Optional[AttendanceService] = None

def get_attendance_service_for_bot(force_refresh: bool = False) -> AttendanceService:
    global _BOT_ATTENDANCE_SERVICE
    if _BOT_ATTENDANCE_SERVICE is not None and not force_refresh:
        return _BOT_ATTENDANCE_SERVICE
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password"),
    )
    gw = OdooAttendanceWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password"),
    )
    _BOT_ATTENDANCE_SERVICE = AttendanceService(readonly_repo=repo, write_gateway=gw)
    return _BOT_ATTENDANCE_SERVICE


def show_attendance_menu(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "⏰ <b>إدارة الحضور والعمل الإضافي ونظام العمل السعودي (1446هـ)</b> 🏢\n"
        "────────────────────\n"
        "مرحباً بك! يتيح لك هذا القسم متابعة وتسجيل دوام الموظفين وحساب الساعات الإضافية بدقة وفق المواد 98 و 101 و 107:\n\n"
        "• <b>ملخص وساعات الموظف:</b> عرض ساعات العمل الفعلية والمعيارية وحصيلة العمل الإضافي.\n"
        "• <b>تسجيل حضور فوري (Check-In):</b> تسجيل حركة دخول الموظف فورياً مع منع التكرار.\n"
        "• <b>تسجيل انصراف فوري (Check-Out):</b> إغلاق الدوام المفتوح وتوثيق ساعات العمل المنجزة.\n"
        "• <b>حاسبة وتدقيق العمل الإضافي (Dry-Run):</b> احتساب الأوفرتايم بنسبة 1.5x تلقائياً مع فحص فترات الراحة (المادة 101).\n"
        "• <b>دليل الدوام والراحة:</b> استعراض معايير الدوام الاعتيادي ورمضان وضوابط الراحة."
    )
    kb = {
        "inline_keyboard": [
            [
                {"text": "📊 ملخص الدوام والأوفرتايم", "callback_data": "attend:summary_prompt"},
                {"text": "⏱️ احتساب عمل إضافي (Dry-Run)", "callback_data": "attend:overtime_prompt"},
            ],
            [
                {"text": "🟢 تسجيل حضور فوري", "callback_data": "attend:checkin_prompt"},
                {"text": "🔴 تسجيل انصراف فوري", "callback_data": "attend:checkout_prompt"},
            ],
            [
                {"text": "⚖️ دليل الدوام والراحة (المواد 98 و 101 و 107)", "callback_data": "attend:law_guide"},
            ],
            [
                {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_attendance_law_guide(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "⚖️ <b>دليل ساعات العمل والراحة والعمل الإضافي في نظام العمل السعودي:</b>\n"
        "────────────────────\n"
        "⏱️ <b>1. ساعات العمل المعيارية (المادة 98):</b>\n"
        "  • <b>8 ساعات يومياً</b> أو <b>48 ساعة أسبوعياً</b> كحد أقصى للدوام الاعتيادي.\n"
        "  • <b>في شهر رمضان:</b> تُخفض ساعات العمل للمسلمين إلى <b>6 ساعات يومياً</b> أو <b>36 ساعة أسبوعياً</b>.\n\n"
        "☕ <b>2. فترات الراحة الإلزامية (المادة 101):</b>\n"
        "  • حظر تشغيل العامل أكثر من <b>5 ساعات متصلة</b> دون فترة راحة وصلاة وطعام لا تقل عن <b>نصف ساعة</b>.\n"
        "  • لا يجوز أن يبقى العامل في مقر العمل أكثر من <b>12 ساعة يومياً</b>.\n\n"
        "💰 <b>3. أجر العمل الإضافي (المادة 107):</b>\n"
        "  • كل ساعة تزيد عن الساعات المعيارية تُعد عملاً إضافياً.\n"
        "  • يُدفع للعامل: <b>أجر الساعة الفعلي (الأجر الإجمالي / 240) + 50% من أجره الأساسي (الأساسي / 240)</b>، أي ما يعادل 1.5x تقريباً.\n"
        "  • جميع ساعات العمل في أيام الأعياد والعطل الأسبوعية الرسمية تُحسب ساعات إضافية."
    )
    kb = {
        "inline_keyboard": [
            [{"text": "⏱️ احتساب عمل إضافي الآن", "callback_data": "attend:overtime_prompt"}],
            [{"text": "🔙 عُد لقائمة الحضور والدوام", "callback_data": "menu:attendance"}],
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_employee_attendance_card(
    bot: TelegramBotClient,
    chat_id: int | str,
    employee_id: int,
    message_id: Optional[int] = None
) -> None:
    service = get_attendance_service_for_bot()
    try:
        summary = service.get_attendance_summary(employee_id=employee_id, limit=5)
        text = (
            f"📊 <b>بطاقة حضور وساعات دوام الموظف</b> ⏰\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {summary.employee_name} (معرّف #{summary.employee_id})\n"
            f"🏢 <b>القسم:</b> {summary.department_name}\n"
            f"📅 <b>أيام العمل المسجلة:</b> <b>{summary.total_days_worked} يوم</b>\n"
            f"⏱️ <b>إجمالي ساعات العمل:</b> <b>{summary.total_worked_hours:,.2f} ساعة</b>\n"
            f"🏛️ <b>الساعات المعيارية:</b> {summary.total_standard_hours:,.2f} ساعة\n"
            f"⚡ <b>ساعات العمل الإضافي (م/107):</b> <b>{summary.total_overtime_hours:,.2f} ساعة</b>\n"
            f"💵 <b>مستحق العمل الإضافي التقديري:</b> <b>{summary.overtime_compensation_sar:,.2f} ر.س</b>\n"
            f"────────────────────\n"
        )
        if summary.attendances:
            text += "🗓️ <b>آخر حركات الحضور المسجلة:</b>\n"
            for att in summary.attendances[:3]:
                cin = att.check_in.split(" ")[-1] if " " in att.check_in else att.check_in
                cout = (att.check_out.split(" ")[-1] if " " in att.check_out else att.check_out) if att.check_out else "<i>مفتوح</i>"
                st = "🟢" if not att.is_open else "⏳"
                text += f"  {st} {att.date}: {cin} ➔ {cout} ({att.worked_hours:,.1f}س | إضافي: {att.overtime_hours:,.1f}س)\n"
        else:
            text += "<i>لا توجد حركات حضور مسجلة مؤخراً لهذا الموظف.</i>\n"

        kb = {
            "inline_keyboard": [
                [
                    {"text": "🟢 تسجيل حضور (Check-In)", "callback_data": f"attend_act:cin:{employee_id}"},
                    {"text": "🔴 تسجيل انصراف (Check-Out)", "callback_data": f"attend_act:cout:{employee_id}"},
                ],
                [
                    {"text": "⏱️ فحص ساعات إضافية لهذا الموظف", "callback_data": f"attend:ot_for:{employee_id}"},
                ],
                [
                    {"text": "🔙 عُد لقائمة الحضور", "callback_data": "menu:attendance"}],
            ]
        }
        if message_id:
            bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
        else:
            bot.send_message(chat_id, text, reply_markup=kb)
    except Exception as exc:
        err_text = f"❌ <b>خطأ:</b> تعذر جلب سجلات حضور الموظف #{employee_id}: <code>{exc}</code>"
        kb = {"inline_keyboard": [[{"text": "🔙 عُد لقائمة الحضور", "callback_data": "menu:attendance"}]]}
        if message_id:
            bot.edit_message_text(chat_id, message_id, err_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, err_text, reply_markup=kb)


def handle_attendance_wizard_step(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    text: str,
    msg_id: Optional[int] = None,
) -> bool:
    wiz = ACTIVE_ATTENDANCE_WIZARDS.get(str(chat_id))
    if not wiz:
        return False

    clean_text = text.strip()
    mode = wiz.get("mode")

    if clean_text in ("إلغاء", "تراجع", "خروج", "cancel"):
        ACTIVE_ATTENDANCE_WIZARDS.pop(str(chat_id), None)
        show_attendance_menu(bot, chat_id)
        return True

    if mode == "summary":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "attend_sum", "menu:attendance", msg_id)
        if not emp:
            return True
        ACTIVE_ATTENDANCE_WIZARDS.pop(str(chat_id), None)
        show_employee_attendance_card(bot, chat_id, emp["id"])
        return True

    if mode == "checkin_input":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "attend_in", "menu:attendance", msg_id)
        if not emp:
            return True
        emp_id = emp["id"]
        ACTIVE_ATTENDANCE_WIZARDS.pop(str(chat_id), None)

        PENDING_ATTENDANCE_CONFIRMATIONS[str(chat_id)] = {
            "action": "check_in",
            "employee_id": emp_id,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        confirm_text = (
            f"⚠️ <b>تأكيد تسجيل حضور فوري (Check-In)</b> 🟢\n"
            f"────────────────────\n"
            f"أنت على وشك تسجيل حضور للموظف معرّف #{emp_id} في Odoo.\n\n"
            f"وفق مبدأ التحقق المزدوج (Four-Eyes Principle)، اكتب كلمة <b>«تأكيد»</b> لتسجيل الحضور."
        )
        kb = {"inline_keyboard": [[{"text": "❌ تراجع", "callback_data": "attend:cancel"}]]}
        bot.send_message(chat_id, confirm_text, reply_markup=kb, reply_to_message_id=msg_id)
        log_telegram_audit(user_id, chat_id, "attendance_checkin_confirm_requested", {"employee_id": emp_id})
        return True

    if mode == "checkout_input":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "attend_out", "menu:attendance", msg_id)
        if not emp:
            return True
        emp_id = emp["id"]
        ACTIVE_ATTENDANCE_WIZARDS.pop(str(chat_id), None)

        PENDING_ATTENDANCE_CONFIRMATIONS[str(chat_id)] = {
            "action": "check_out",
            "employee_id": emp_id,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        confirm_text = (
            f"⚠️ <b>تأكيد تسجيل انصراف فوري (Check-Out)</b> 🔴\n"
            f"────────────────────\n"
            f"أنت على وشك إغلاق دوام وتسجيل انصراف للموظف معرّف #{emp_id} في Odoo.\n\n"
            f"وفق مبدأ التحقق المزدوج (Four-Eyes Principle)، اكتب كلمة <b>«تأكيد»</b> لتسجيل الانصراف."
        )
        kb = {"inline_keyboard": [[{"text": "❌ تراجع", "callback_data": "attend:cancel"}]]}
        bot.send_message(chat_id, confirm_text, reply_markup=kb, reply_to_message_id=msg_id)
        log_telegram_audit(user_id, chat_id, "attendance_checkout_confirm_requested", {"employee_id": emp_id})
        return True

    if mode == "overtime":
        step = wiz.get("step")
        if step == "emp":
            emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "attend_overtime", "menu:attendance", msg_id)
            if not emp:
                return True
            emp_id = emp["id"]
            wiz["employee_id"] = emp_id
            wiz["step"] = "times"
            prompt_text = (
                f"⏱️ <b>تحديد تاريخ وساعات الدوام للموظف #{emp_id}:</b>\n"
                f"────────────────────\n"
                f"أرسل تاريخ وساعات الحضور والانصراف بصيغة:\n"
                f"<code>YYYY-MM-DD HH:MM HH:MM</code>\n\n"
                f"مثال (دوام من 8:00 ص إلى 6:30 م):\n"
                f"<code>2026-10-06 08:00 18:30</code>"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "attend:cancel"}]]}
            bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb, reply_to_message_id=msg_id)
            return True

        elif step == "times":
            parts = clean_text.split()
            if len(parts) < 3:
                bot.send_message(
                    chat_id,
                    "⚠️ صيغة غير مكتملة. يرجى إرسال: <code>YYYY-MM-DD HH:MM HH:MM</code>\n(مثال: <code>2026-10-06 08:00 18:30</code>):",
                    reply_to_message_id=msg_id,
                )
                return True

            d_str = parts[0]
            cin_str = f"{d_str} {parts[1]}" if len(parts[1]) <= 5 else parts[1]
            cout_str = f"{d_str} {parts[2]}" if len(parts[2]) <= 5 else parts[2]
            emp_id = wiz["employee_id"]

            service = get_attendance_service_for_bot()
            dry_res = service.dry_run_attendance_record(
                employee_id=emp_id,
                date_str=d_str,
                check_in_str=cin_str,
                check_out_str=cout_str,
            )

            if not dry_res.is_valid:
                err_msg = "❌ <b>تعذر تدقيق ساعات الدوام للأسباب التالية:</b>\n"
                for e in dry_res.errors:
                    err_msg += f"  • {e}\n"
                err_msg += "\nيرجى إعادة إرسال التوقيت بصيغة صحيحة:"
                bot.send_message(chat_id, err_msg, reply_to_message_id=msg_id)
                return True

            ACTIVE_ATTENDANCE_WIZARDS.pop(str(chat_id), None)
            token = dry_res.approval_token

            summary_text = (
                f"📊 <b>نتائج الفحص والتدقيق الاستباقي للدوام والعمل الإضافي:</b>\n"
                f"────────────────────\n"
                f"👤 <b>الموظف:</b> {dry_res.employee_name} (#{dry_res.employee_id})\n"
                f"📅 <b>التاريخ:</b> <code>{dry_res.date}</code>\n"
                f"⏰ <b>الفترة:</b> من <code>{dry_res.check_in}</code> إلى <code>{dry_res.check_out}</code>\n"
                f"⏱️ <b>ساعات العمل الفعلية:</b> <b>{dry_res.worked_hours:,.2f} ساعة</b>\n"
                f"🏛️ <b>ساعات العمل المعيارية (م/98):</b> {dry_res.standard_hours:,.2f} ساعة\n"
                f"⚡ <b>ساعات العمل الإضافي (م/107):</b> <b>{dry_res.overtime_hours:,.2f} ساعة</b>\n"
                f"💵 <b>مستحق العمل الإضافي (1.5x):</b> <b>{dry_res.overtime_pay_sar:,.2f} ر.س</b>\n"
                f"⚖️ <b>المرجع النظامي:</b> {dry_res.statutory_article}\n"
                f"💡 <b>التفسير:</b> {dry_res.statutory_explanation_ar}\n"
                f"────────────────────\n"
            )
            if dry_res.warnings:
                summary_text += "⚠️ <b>ملاحظات وفحص الراحة:</b>\n"
                for w in dry_res.warnings:
                    summary_text += f"  • {w}\n"
                summary_text += "────────────────────\n"

            summary_text += (
                f"🆔 <b>رمز الاعتماد:</b> <code>{token}</code>\n"
                f"اضغط الزر أدناه ثم اكتب «تأكيد» للاعتماد النهائي في Odoo:"
            )

            kb = {
                "inline_keyboard": [
                    [
                        {"text": "🚀 اعتماد وتسجيل الدوام في Odoo", "callback_data": f"attend_approve:{token}"},
                        {"text": "❌ تراجع", "callback_data": "attend:cancel"},
                    ]
                ]
            }
            bot.send_message(chat_id, summary_text, reply_markup=kb, reply_to_message_id=msg_id)
            return True

    return False


def execute_attendance_action_via_service(
    bot: TelegramBotClient,
    chat_id: int | str,
    action_info: Dict[str, Any],
    msg_id: Optional[int] = None,
) -> None:
    service = get_attendance_service_for_bot()
    action = action_info.get("action")
    bot.send_message(chat_id, "⏳ جارِ تنفيذ حركة الحضور في Odoo والتحقق المستقل منها...", reply_to_message_id=msg_id)
    try:
        if action == "check_in":
            emp_id = action_info["employee_id"]
            res = service.record_check_in(employee_id=emp_id, confirmation_text="تأكيد")
        elif action == "check_out":
            emp_id = action_info["employee_id"]
            res = service.record_check_out(employee_id=emp_id, confirmation_text="تأكيد")
        elif action == "apply_token":
            token = action_info["token"]
            res = service.apply_attendance_entry(approval_token=token, confirmation_text="تأكيد")
        else:
            bot.send_message(chat_id, f"❌ نوع الإجراء غير معروف: {action}")
            return

        if res.success:
            succ_text = (
                f"🎉 <b>تم تنفيذ حركة الحضور بنجاح في Odoo!</b>\n"
                f"────────────────────\n"
                f"👤 <b>الموظف:</b> {res.employee_name} (#{res.employee_id})\n"
                f"⚙️ <b>نوع الإجراء:</b> <b>{res.action_type}</b>\n"
                f"⏰ <b>التوقيت المسجل:</b> <code>{res.timestamp_recorded}</code>\n"
                f"🔖 <b>رقم السجل في Odoo:</b> <code>#{res.attendance_id}</code>\n"
            )
            if res.action_type in ("CHECK_OUT", "CREATE_RECORD"):
                succ_text += (
                    f"⏱️ <b>ساعات العمل:</b> {res.worked_hours:,.2f} ساعة\n"
                    f"⚡ <b>الساعات الإضافية:</b> {res.overtime_hours:,.2f} ساعة\n"
                )
            succ_text += (
                f"✅ <b>التحقق المستقل:</b> ناجح ومطابق (Readback Verified)\n"
                f"────────────────────\n"
                f"تم حفظ العملية في سجل التدقيق المركزي بنجاح."
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "⏰ العودة لقائمة الحضور والدوام", "callback_data": "menu:attendance"}],
                    [{"text": "🔙 القائمة الرئيسية", "callback_data": "menu:main"}],
                ]
            }
            bot.send_message(chat_id, succ_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, f"❌ <b>فشل تنفيذ الحركة:</b> {res.message_ar}")
    except Exception as exc:
        bot.send_message(chat_id, f"❌ <b>خطأ أثناء التنفيذ:</b> <code>{exc}</code>")


# وظائف إدارة الجزاءات والانضباط ونظام العمل السعودي (Phase 12: nthub_hr_disciplinary)

_BOT_DISCIPLINARY_SERVICE: Optional[DisciplinaryService] = None

def get_disciplinary_service_for_bot(force_refresh: bool = False) -> DisciplinaryService:
    global _BOT_DISCIPLINARY_SERVICE
    if _BOT_DISCIPLINARY_SERVICE is not None and not force_refresh:
        return _BOT_DISCIPLINARY_SERVICE
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password"),
    )
    gw = OdooDisciplinaryWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password"),
    )
    _BOT_DISCIPLINARY_SERVICE = DisciplinaryService(readonly_repo=repo, write_gateway=gw)
    return _BOT_DISCIPLINARY_SERVICE


def show_disciplinary_menu(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "⚖️ <b>إدارة الجزاءات والانضباط ونظام العمل السعودي</b> 🏢\n"
        "────────────────────\n"
        "أهلاً بك! يتيح لك هذا القسم إدارة الجزاءات التأديبية وتدقيقها وفق المواد 70 و 71 و 72 و 80:\n\n"
        "• <b>سجل مخالفات الموظف:</b> عرض السوابق، رصيد الخصم الشهري المتاح، ودرجة التكرار.\n"
        "• <b>تدقيق وتسجيل جزاء (Dry-Run):</b> فحص سقوف الخصم (حد أقصى 5 أيام) وتقادم الدعوى (30 يوماً).\n"
        "• <b>دليل الأنظمة والضوابط:</b> استعراض قيود المادة 70 وسقوط التكرار وضوابط فسخ العقد بموجب المادة 80."
    )
    kb = {
        "inline_keyboard": [
            [
                {"text": "📊 سجل مخالفات الموظف", "callback_data": "disc:summary_prompt"},
                {"text": "📝 تدقيق وتسجيل جزاء (Dry-Run)", "callback_data": "disc:action_prompt"},
            ],
            [
                {"text": "📜 إصدار خطاب إنذار رسمي (warning.letter)", "callback_data": "warning:levels_prompt"},
            ],
            [
                {"text": "⚖️ دليل الجزاءات (المواد 70 و 71 و 80)", "callback_data": "disc:law_guide"},
            ],

            [
                {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_disciplinary_law_guide(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "⚖️ <b>دليل لائحة الجزاءات ونظام العمل السعودي:</b>\n"
        "────────────────────\n"
        "📌 <b>1. سقوف الخصومات التأديبية (المادة 70):</b>\n"
        "  • حظر اقتطاع أكثر من <b>أجر 5 أيام</b> عن المخالفة الواحدة.\n"
        "  • حظر اقتطاع أكثر من <b>أجر 5 أيام في الشهر الواحد</b> وفاءً للجزاءات.\n"
        "  • حظر زيادة مدة الإيقاف عن العمل دون أجر على <b>5 أيام في الشهر</b>.\n\n"
        "⏳ <b>2. سقوط أثر تكرار المخالفة (المادة 71):</b>\n"
        "  • يسقط أثر التكرار وتعود المخالفة كأنها للمرة الأولى إذا انقضى <b>180 يوماً</b> على إبلاغ العامل بالجزاء السابق دون مخالفة جديدة.\n\n"
        "🛡️ <b>3. مواعيد سقوط الحق التأديبي (المادة 72):</b>\n"
        "  • لا يجوز اتهام العامل بعد مضي <b>30 يوماً</b> على كشف المخالفة.\n"
        "  • لا يجوز توقيع الجزاء بعد مضي <b>30 يوماً</b> على تاريخ انتهاء التحقيق وثبوت المخالفة.\n\n"
        "🚫 <b>4. الفسخ التأديبي الصارم (المادة 80):</b>\n"
        "  • يشترط حتماً إتاحة الفرصة للعامل لإبداء أسباب معارضته وسماع دفاعه كتابياً.\n"
        "  • الغياب بدون عذر: يشترط إنذار كتابي بعد 10 أيام في المتصل (15 يوماً للفسخ) وبعد 20 يوماً في المتقطع (30 يوماً للفسخ)."
    )
    kb = {
        "inline_keyboard": [
            [{"text": "📝 تدقيق جزاء تأديبي الآن", "callback_data": "disc:action_prompt"}],
            [{"text": "🔙 عُد لقائمة الجزاءات", "callback_data": "menu:disciplinary"}],
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_employee_disciplinary_card(
    bot: TelegramBotClient,
    chat_id: int | str,
    employee_id: int,
    message_id: Optional[int] = None
) -> None:
    service = get_disciplinary_service_for_bot()
    try:
        summary = service.get_employee_disciplinary_summary(employee_id=employee_id)
        text = (
            f"📊 <b>بطاقة سجل الجزاءات والانضباط</b> ⚖️\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {summary.employee_name} (معرّف #{summary.employee_id})\n"
            f"🏢 <b>القسم:</b> {summary.department_name}\n"
            f"💰 <b>أجر اليوم التقديري:</b> {summary.daily_wage:,.2f} ر.س\n"
            f"📁 <b>إجمالي المخالفات المسجلة:</b> <b>{summary.total_actions_count} مخالفة</b>\n"
            f"📉 <b>خصومات الشهر الحالي (م/70):</b> <b>{summary.current_month_deductions_days:,.1f} من 5 أيام</b>\n"
            f"🛡️ <b>المتبقي المسموح نظاماً هذا الشهر:</b> <b>{summary.remaining_month_deduction_allowance_days:,.1f} أيام</b>\n"
            f"🔄 <b>درجة التكرار النشطة (م/71):</b> <code>{summary.active_occurrence_level}</code>\n"
            f"────────────────────\n"
        )
        if summary.recent_actions:
            text += "🗓️ <b>آخر الجزاءات المسجلة:</b>\n"
            for a in summary.recent_actions[:3]:
                d_date = a.get("discipline_date", "")
                days = a.get("number_of_days", 0.0)
                reason = a.get("discipline_reason", "")[:30]
                text += f"  • {d_date}: خصم {days:,.1f} يوم ({reason}) - حالة: <code>{a.get('state')}</code>\n"
        else:
            text += "<i>السجل نظيف! لا توجد مخالفات مسجلة على هذا الموظف.</i>\n"

        kb = {
            "inline_keyboard": [
                [{"text": "📝 تسجيل جزاء لهذا الموظف", "callback_data": f"disc:act_for:{employee_id}"}],
                [{"text": "🔙 عُد لقائمة الجزاءات", "callback_data": "menu:disciplinary"}],
            ]
        }
        if message_id:
            bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
        else:
            bot.send_message(chat_id, text, reply_markup=kb)
    except Exception as exc:
        err_text = f"❌ <b>خطأ:</b> تعذر جلب سجل مخالفات الموظف #{employee_id}: <code>{exc}</code>"
        kb = {"inline_keyboard": [[{"text": "🔙 عُد للجزاءات", "callback_data": "menu:disciplinary"}]]}
        if message_id:
            bot.edit_message_text(chat_id, message_id, err_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, err_text, reply_markup=kb)


def handle_disciplinary_wizard_step(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    text: str,
    msg_id: Optional[int] = None,
) -> bool:
    wiz = ACTIVE_DISCIPLINARY_WIZARDS.get(str(chat_id))
    if not wiz:
        return False

    clean_text = text.strip()
    mode = wiz.get("mode")

    if clean_text in ("إلغاء", "تراجع", "خروج", "cancel"):
        ACTIVE_DISCIPLINARY_WIZARDS.pop(str(chat_id), None)
        show_disciplinary_menu(bot, chat_id)
        return True

    if mode == "summary":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "disc_sum", "menu:disciplinary", msg_id)
        if not emp:
            return True
        ACTIVE_DISCIPLINARY_WIZARDS.pop(str(chat_id), None)
        show_employee_disciplinary_card(bot, chat_id, emp["id"])
        return True

    if mode == "action":
        step = wiz.get("step")
        if step == "emp":
            emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "disc_act", "menu:disciplinary", msg_id)
            if not emp:
                return True
            emp_id = emp["id"]
            wiz["employee_id"] = emp_id
            wiz["step"] = "details"
            prompt_text = (
                f"📝 <b>بيانات الجزاء التأديبي للموظف #{emp_id}:</b>\n"
                f"────────────────────\n"
                f"أرسل تاريخ المخالفة وعدد أيام الخصم ووصف المخالفة مفصولة بمسافات:\n\n"
                f"الصيغة: <code>YYYY-MM-DD [عدد الأيام] [السبب]</code>\n\n"
                f"مثال:\n"
                f"<code>2026-10-06 1 تأخر متكرر عن موعد الدوام الرسمي</code>"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "disc:cancel"}]]}
            bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb, reply_to_message_id=msg_id)
            return True

        elif step == "details":
            parts = clean_text.split(None, 2)
            if len(parts) < 3:
                bot.send_message(
                    chat_id,
                    "⚠️ صيغة غير مكتملة. يرجى إرسال: <code>YYYY-MM-DD [أيام الخصم] [السبب]</code>\n"
                    "مثال: <code>2026-10-06 1 تأخر غير مبرر</code>",
                    reply_to_message_id=msg_id,
                )
                return True

            d_date = parts[0]
            try:
                days = float(parts[1])
            except ValueError:
                bot.send_message(chat_id, "⚠️ عدد أيام الخصم يجب أن يكون رقماً (مثال: 1 أو 2):", reply_to_message_id=msg_id)
                return True

            reason = parts[2]
            emp_id = wiz["employee_id"]

            service = get_disciplinary_service_for_bot()
            dry_res = service.dry_run_disciplinary_action(
                employee_id=emp_id,
                discipline_date=d_date,
                discipline_reason=reason,
                number_of_days=days,
            )

            if not dry_res.is_valid:
                err_msg = "❌ <b>تعذر اعتماد الجزاء التأديبي لمخالفة نظام العمل السعودي:</b>\n"
                for e in dry_res.errors:
                    err_msg += f"  • {e}\n"
                err_msg += "\nيرجى تعديل البيانات وفق النظام لإعادة الفحص:"
                bot.send_message(chat_id, err_msg, reply_to_message_id=msg_id)
                return True

            ACTIVE_DISCIPLINARY_WIZARDS.pop(str(chat_id), None)
            token = dry_res.approval_token

            summary_text = (
                f"📊 <b>نتائج الفحص والتدقيق الاستباقي للجزاء التأديبي:</b>\n"
                f"────────────────────\n"
                f"👤 <b>الموظف:</b> {dry_res.employee_name} (#{dry_res.employee_id})\n"
                f"🏢 <b>القسم:</b> {dry_res.department_name}\n"
                f"📅 <b>تاريخ المخالفة:</b> <code>{dry_res.discipline_date}</code>\n"
                f"📝 <b>المخالفة:</b> {dry_res.discipline_reason}\n"
                f"📉 <b>الجزاء المقترح:</b> <b>خصم {dry_res.number_of_days} يوم ({dry_res.amount_sar:,.2f} ر.س)</b>\n"
                f"🔄 <b>درجة التكرار (م/71):</b> {dry_res.occurrence_explanation_ar}\n"
                f"⚖️ <b>المرجع النظامي:</b> {dry_res.statutory_article}\n"
                f"💡 <b>التفسير:</b> {dry_res.statutory_explanation_ar}\n"
                f"────────────────────\n"
            )
            if dry_res.warnings:
                summary_text += "⚠️ <b>ملاحظات وضمانات:</b>\n"
                for w in dry_res.warnings:
                    summary_text += f"  • {w}\n"
                summary_text += "────────────────────\n"

            summary_text += (
                f"🆔 <b>رمز الاعتماد:</b> <code>{token}</code>\n"
                f"اضغط الزر أدناه ثم اكتب «تأكيد» للاعتماد النهائي في Odoo:"
            )

            kb = {
                "inline_keyboard": [
                    [
                        {"text": "🚀 اعتماد الجزاء التأديبي في Odoo", "callback_data": f"disc_approve:{token}"},
                        {"text": "❌ تراجع", "callback_data": "disc:cancel"},
                    ]
                ]
            }
            bot.send_message(chat_id, summary_text, reply_markup=kb, reply_to_message_id=msg_id)
            return True

    return False


def execute_disciplinary_action_via_service(
    bot: TelegramBotClient,
    chat_id: int | str,
    token: str,
    msg_id: Optional[int] = None,
) -> None:
    service = get_disciplinary_service_for_bot()
    bot.send_message(chat_id, "⏳ جارِ تسجيل الجزاء التأديبي في Odoo والتحقق المستقل منه...", reply_to_message_id=msg_id)
    try:
        res = service.apply_disciplinary_action(approval_token=token, user_confirmation_text="تأكيد")
        if res.success:
            succ_text = (
                f"🎉 <b>تم تسجيل الجزاء التأديبي بنجاح في Odoo!</b>\n"
                f"────────────────────\n"
                f"👤 <b>الموظف:</b> {res.employee_name} (#{res.employee_id})\n"
                f"🔖 <b>الرقم المرجعي:</b> <code>{res.reference}</code>\n"
                f"📉 <b>الجزاء الموقع:</b> <b>خصم {res.number_of_days} يوم ({res.amount_sar:,.2f} ر.س)</b>\n"
                f"🔢 <b>رقم السجل في Odoo:</b> <code>#{res.action_id}</code>\n"
                f"✅ <b>التحقق المستقل:</b> ناجح ومطابق (Readback Verified)\n"
                f"────────────────────\n"
                f"تم توثيق العملية في سجل التدقيق الخاص بالجزاءات (المادة 73)."
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "⚖️ العودة لقائمة الجزاءات", "callback_data": "menu:disciplinary"}],
                    [{"text": "🔙 القائمة الرئيسية", "callback_data": "menu:main"}],
                ]
            }
            bot.send_message(chat_id, succ_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, f"❌ <b>فشل تسجيل الجزاء:</b> {res.message_ar}")
    except Exception as exc:
        bot.send_message(chat_id, f"❌ <b>خطأ أثناء التنفيذ:</b> <code>{exc}</code>")


_BOT_EOS_SERVICE: Optional[EOSService] = None

def get_eos_service_for_bot(force_refresh: bool = False) -> EOSService:
    global _BOT_EOS_SERVICE
    if _BOT_EOS_SERVICE is not None and not force_refresh:
        return _BOT_EOS_SERVICE
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password"),
    )
    gw = OdooEOSWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password"),
    )
    _BOT_EOS_SERVICE = EOSService(readonly_repo=repo, write_gateway=gw)
    return _BOT_EOS_SERVICE


def show_eos_menu(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "💼 <b>تسويات مكافأة نهاية الخدمة ونظام العمل السعودي</b> ⚖️\n"
        "────────────────────\n"
        "أهلاً بك! يتيح لك هذا القسم إدارة وتسوية مستحقات نهاية الخدمة بدقة تامة:\n\n"
        "• <b>التفريق الصارم بين السعودي وغير السعودي:</b> تطبيق المادة 37 وحظر العقود غير محددة المدة للوافد.\n"
        "• <b>مكافأة نهاية الخدمة (م/84 و 85):</b> نصف شهر لأول 5 سنوات وشهر لما بعدها، وتدرج الاستقالة.\n"
        "• <b>استثناءات الاستحقاق الكامل (م/87):</b> زواج أو وضع العاملة، وحالات القوة القاهرة.\n"
        "• <b>تعويض الإنهاء غير المشروع (م/77):</b> أجر المدة الباقية أو 15 يوماً/سنة بحد أدنى شهرين.\n"
        "• <b>رصيد الإجازات والأجور (م/111):</b> صرف البدل النقدي للأيام غير المستنفدة."
    )
    kb = {
        "inline_keyboard": [
            [
                {"text": "📊 استعلام وتصفية مستحقات موظف", "callback_data": "eos:calc_prompt"},
            ],
            [
                {"text": "📜 دليل مواد التسويات (77، 84، 85، 87، 111)", "callback_data": "eos:laws_guide"},
            ],
            [
                {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_eos_laws_guide(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "📜 <b>دليل تسويات نهاية الخدمة ونظام العمل السعودي:</b>\n"
        "────────────────────\n"
        "📌 <b>1. مكافأة نهاية الخدمة (المادة 84):</b>\n"
        "  • أجر نصف شهر عن كل سنة من السنوات الخمس الأولى.\n"
        "  • أجر شهر كامل عن كل سنة تالية، وتحسب أجزاء السنة بنسبتها.\n\n"
        "📉 <b>2. تدرج الاستقالة (المادة 85):</b>\n"
        "  • أقل من سنتين: <b>لا يستحق مكافأة (0%)</b>.\n"
        "  • من سنتين إلى أقل من 5 سنوات: <b>ثلث المكافأة (1/3)</b>.\n"
        "  • من 5 سنوات إلى أقل من 10 سنوات: <b>ثلثي المكافأة (2/3)</b>.\n"
        "  • 10 سنوات فأكثر: <b>المكافأة كاملة (100%)</b>.\n\n"
        "🌟 <b>3. استثناءات الاستحقاق الكامل عند الاستقالة (المادة 87):</b>\n"
        "  • استقالة العاملة خلال <b>6 أشهر من عقد قرانها</b>.\n"
        "  • استقالة العاملة خلال <b>3 أشهر من وضعها لمولودها</b>.\n"
        "  • ترك العمل بسبب <b>قوة قاهرة خارجة عن إرادة العامل</b>.\n\n"
        "⚖️ <b>4. تعويض الإنهاء غير المشروع (المادة 77):</b>\n"
        "  • <b>عقد غير محدد المدة (للسعودي فقط - م/37):</b> أجر 15 يوماً عن كل سنة خدمة.\n"
        "  • <b>عقد محدد المدة (للسعودي أو غير السعودي):</b> أجر المدة المتبقية من العقد.\n"
        "  • <b>الحد الأدنى الإلزامي:</b> أجر <b>شهرين على الأقل</b> في جميع الحالات.\n\n"
        "🏖️ <b>5. بدل رصيد الإجازات السنوية (المادة 111):</b>\n"
        "  • يستحق العامل أجراً نقدياً عن أيام الإجازات السنوية المستحقة التي لم يستنفدها."
    )
    kb = {
        "inline_keyboard": [
            [{"text": "💼 احتساب تسوية موظف الآن", "callback_data": "eos:calc_prompt"}],
            [{"text": "🔙 عُد لقائمة نهاية الخدمة", "callback_data": "menu:eos"}],
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_employee_eos_card(
    bot: TelegramBotClient,
    chat_id: int | str,
    employee_id: int,
    message_id: Optional[int] = None
) -> None:
    service = get_eos_service_for_bot()
    try:
        summary = service.get_employee_eos_summary(employee_id=employee_id)
        text = (
            f"📊 <b>بطاقة مدة الخدمة وسجل التسويات</b> 💼\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {summary.employee_name} (#{summary.employee_id})\n"
            f"🏢 <b>القسم:</b> {summary.department_name}\n"
            f"🇸🇦 <b>الجنسية والتصنيف:</b> <b>{summary.nationality_text_ar}</b>\n"
            f"📅 <b>تاريخ المباشرة:</b> <code>{summary.hiring_date}</code>\n"
            f"⏳ <b>مدة الخدمة المحسوبة:</b> <b>{summary.years} سنة و {summary.months} شهر و {summary.days} يوم</b> ({summary.service_years:.2f} سنة)\n"
            f"💰 <b>الأجر الشهري التقديري:</b> {summary.last_gross_wage:,.2f} ر.س\n"
            f"📁 <b>سجلات التسوية السابقة في Odoo:</b> <b>{summary.eos_records_count} سجل</b>\n"
            f"────────────────────\n"
        )
        if summary.recent_records:
            text += "🗓️ <b>آخر التسويات المسجلة:</b>\n"
            for r in summary.recent_records[:2]:
                r_date = r.get("date", "")
                r_rew = r.get("total_reward", 0.0)
                text += f"  • {r_date}: مبلغ {r_rew:,.2f} ر.س - حالة: <code>{r.get('state')}</code>\n"
        else:
            text += "<i>لا توجد تسويات سابقة مسجلة لهذا الموظف.</i>\n"

        kb = {
            "inline_keyboard": [
                [{"text": "💼 احتساب تسوية نهاية الخدمة", "callback_data": f"eos:calc_for:{employee_id}"}],
                [{"text": "🔙 عُد لقائمة نهاية الخدمة", "callback_data": "menu:eos"}],
            ]
        }
        if message_id:
            bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
        else:
            bot.send_message(chat_id, text, reply_markup=kb)
    except Exception as exc:
        err_text = f"❌ <b>خطأ:</b> تعذر جلب بيانات نهاية الخدمة للموظف #{employee_id}: <code>{exc}</code>"
        kb = {"inline_keyboard": [[{"text": "🔙 عُد لنهاية الخدمة", "callback_data": "menu:eos"}]]}
        if message_id:
            bot.edit_message_text(chat_id, message_id, err_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, err_text, reply_markup=kb)


def handle_eos_wizard_step(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    text: str,
    msg_id: Optional[int] = None,
) -> bool:
    wiz = ACTIVE_EOS_WIZARDS.get(str(chat_id))
    if not wiz:
        return False

    clean_text = text.strip()
    mode = wiz.get("mode")

    if clean_text in ("إلغاء", "تراجع", "خروج", "cancel"):
        ACTIVE_EOS_WIZARDS.pop(str(chat_id), None)
        show_eos_menu(bot, chat_id)
        return True

    if mode == "calc_emp":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "eos_calc", "eos:cancel", msg_id)
        if not emp:
            return True
        emp_id = emp["id"]
        wiz["employee_id"] = emp_id
        wiz["mode"] = "calc_details"
        prompt_text = (
            f"💼 <b>بيانات تسوية نهاية الخدمة للموظف #{emp_id}:</b>\n"
            f"────────────────────\n"
            f"أرسل الأجر الشهري وسبب انتهاء العلاقة ورصيد الإجازات مفصولة بمسافات:\n\n"
            f"الصيغة: <code>[الأجر الشهري] [السبب] [رصيد الإجازات المتبقية] [شهور العقد المتبقية إن وجد]</code>\n\n"
            f"خيارات السبب:\n"
            f"• <code>إنهاء</code> أو <code>فصل</code> (إنهاء من المنشأة - م/84)\n"
            f"• <code>استقالة</code> (استقالة عادية - م/85)\n"
            f"• <code>زواج</code> (استقالة زواج عاملة خلال 6 أشهر - م/87)\n"
            f"• <code>وضع</code> (استقالة وضع عاملة خلال 3 أشهر - م/87)\n"
            f"• <code>قوة_قاهرة</code> (استقالة لقوة قاهرة - م/87)\n\n"
            f"أمثلة شائعة:\n"
            f"• <code>8500 إنهاء 10</code> (راتب 8,500، إنهاء من المنشأة، 10 أيام إجازة)\n"
            f"• <code>6000 استقالة 0</code> (راتب 6,000، استقالة عادية)\n"
            f"• <code>10000 فصل 12 4</code> (فصل تعسفي م/77 مع بقاء 4 أشهر في العقد)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "eos:cancel"}]]}
        bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb, reply_to_message_id=msg_id)
        return True

    elif mode == "calc_details":
        parts = clean_text.split()
        if len(parts) < 2:
            bot.send_message(
                chat_id,
                "⚠️ صيغة غير مكتملة. يرجى إرسال: <code>[الأجر] [السبب] [أيام الإجازات]</code> (مثال: <code>7500 إنهاء 5</code>)",
                reply_to_message_id=msg_id,
            )
            return True

        try:
            wage = float(parts[0])
        except ValueError:
            bot.send_message(chat_id, "⚠️ الأجر الشهري يجب أن يكون رقماً صحيحاً (مثال: 8000):", reply_to_message_id=msg_id)
            return True

        reason_raw = parts[1].lower()
        is_resignation = False
        res_reason = "standard"
        is_unlawful = False

        if "استقال" in reason_raw:
            is_resignation = True
            res_reason = "standard"
        elif "زواج" in reason_raw:
            is_resignation = True
            res_reason = "marriage_female"
        elif "وضع" in reason_raw:
            is_resignation = True
            res_reason = "childbirth_female"
        elif "قوة" in reason_raw or "قاهره" in reason_raw:
            is_resignation = True
            res_reason = "force_majeure"
        elif "فصل" in reason_raw or "تعسف" in reason_raw:
            is_resignation = False
            is_unlawful = True
        else:
            is_resignation = False

        unused_leaves = 0.0
        if len(parts) >= 3:
            try:
                unused_leaves = float(parts[2])
            except ValueError:
                unused_leaves = 0.0

        remaining_months = 0.0
        if len(parts) >= 4:
            try:
                remaining_months = float(parts[3])
                if remaining_months > 0:
                    is_unlawful = True
            except ValueError:
                remaining_months = 0.0

        emp_id = wiz["employee_id"]
        service = get_eos_service_for_bot()
        dry_res = service.dry_run_eos_settlement(
            employee_id=emp_id,
            monthly_wage=wage,
            is_resignation=is_resignation,
            resignation_reason=res_reason,
            is_unlawful_termination=is_unlawful,
            remaining_contract_months=remaining_months,
            unused_leave_days=unused_leaves,
        )

        if not dry_res.is_valid:
            err_msg = "❌ <b>تعذر احتساب تسوية نهاية الخدمة:</b>\n"
            for e in dry_res.errors:
                err_msg += f"  • {e}\n"
            bot.send_message(chat_id, err_msg, reply_to_message_id=msg_id)
            return True

        ACTIVE_EOS_WIZARDS.pop(str(chat_id), None)
        token = dry_res.approval_token

        summary_text = (
            f"📊 <b>نتائج الفحص والاحتساب الاستباقي لنهاية الخدمة:</b>\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {dry_res.employee_name} (#{dry_res.employee_id})\n"
            f"🇸🇦 <b>التصنيف:</b> <b>{dry_res.nationality_text_ar}</b>\n"
            f"📜 <b>نوع العقد المعتمد:</b> <code>{dry_res.contract_type}</code>\n"
            f"⏳ <b>مدة الخدمة:</b> {dry_res.years} سنة و {dry_res.months} شهر و {dry_res.days} يوم ({dry_res.service_period:.2f} سنة)\n"
            f"💰 <b>الأجر الشهري:</b> {dry_res.monthly_wage:,.2f} ر.س | <b>أجر اليوم:</b> {dry_res.daily_wage:,.2f} ر.س\n"
            f"────────────────────\n"
            f"💼 <b>مكافأة نهاية الخدمة (م/84، 85، 87):</b> <b>{dry_res.gratuity_net_amount:,.2f} ر.س</b> (نسبة {dry_res.gratuity_entitlement_ratio * 100:.1f}%)\n"
            f"💡 <i>{dry_res.gratuity_explanation_ar}</i>\n"
        )
        if dry_res.article_77_amount > 0:
            summary_text += (
                f"⚖️ <b>تعويض الإنهاء غير المشروع (م/77):</b> <b>{dry_res.article_77_amount:,.2f} ر.س</b>\n"
                f"💡 <i>{dry_res.article_77_explanation_ar}</i>\n"
            )
        if dry_res.leave_compensation_amount > 0:
            summary_text += f"🏖️ <b>بدل رصيد الإجازات ({dry_res.unused_leave_days} يوم - م/111):</b> <b>{dry_res.leave_compensation_amount:,.2f} ر.س</b>\n"

        summary_text += (
            f"────────────────────\n"
            f"💵 <b>صافي المستحق النهائي للصرف:</b> <b>{dry_res.net_settlement_amount:,.2f} ر.س</b>\n"
            f"────────────────────\n"
        )
        if dry_res.warnings:
            summary_text += "⚠️ <b>ملاحظات نظامية:</b>\n"
            for w in dry_res.warnings:
                summary_text += f"  • {w}\n"
            summary_text += "────────────────────\n"

        summary_text += (
            f"🆔 <b>رمز الموافقة:</b> <code>{token}</code>\n"
            f"اضغط الزر أدناه ثم اكتب «تأكيد» للاعتماد النهائي في Odoo:"
        )

        kb = {
            "inline_keyboard": [
                [
                    {"text": "🚀 اعتماد تسوية نهاية الخدمة في Odoo", "callback_data": f"eos_approve:{token}"},
                    {"text": "❌ تراجع", "callback_data": "eos:cancel"},
                ]
            ]
        }
        bot.send_message(chat_id, summary_text, reply_markup=kb, reply_to_message_id=msg_id)
        return True

    return False


def execute_eos_settlement_via_service(
    bot: TelegramBotClient,
    chat_id: int | str,
    token: str,
    msg_id: Optional[int] = None,
) -> None:
    service = get_eos_service_for_bot()
    bot.send_message(chat_id, "⏳ جارِ تسجيل واعتماد تسوية نهاية الخدمة في Odoo والتحقق المستقل...", reply_to_message_id=msg_id)
    try:
        res = service.apply_eos_settlement(approval_token=token, user_confirmation_text="تأكيد")
        if res.success:
            succ_text = (
                f"🎉 <b>تم تسجيل واعتماد تسوية نهاية الخدمة بنجاح في Odoo!</b>\n"
                f"────────────────────\n"
                f"👤 <b>الموظف:</b> {res.employee_name} (#{res.employee_id})\n"
                f"🔖 <b>الرقم المرجعي:</b> <code>{res.reference}</code>\n"
                f"💵 <b>إجمالي التسوية المعتمد:</b> <b>{res.total_settlement_amount:,.2f} ر.س</b>\n"
                f"🔢 <b>رقم السجل في Odoo:</b> <code>#{res.eos_id}</code>\n"
                f"✅ <b>التحقق المستقل:</b> ناجح ومطابق (Readback Verified)\n"
                f"────────────────────\n"
                f"تم توثيق العملية بالكامل في سجل تدقيق التسويات (logs/eos_audit_log.jsonl)."
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "💼 العودة لقائمة نهاية الخدمة", "callback_data": "menu:eos"}],
                    [{"text": "🔙 القائمة الرئيسية", "callback_data": "menu:main"}],
                ]
            }
            bot.send_message(chat_id, succ_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, f"❌ <b>فشل تسجيل التسوية:</b> {res.message_ar}")
    except Exception as exc:
        bot.send_message(chat_id, f"❌ <b>خطأ أثناء التنفيذ:</b> <code>{exc}</code>")


_BOT_GR_SERVICE: Optional[GRService] = None

def get_gr_service_for_bot(force_refresh: bool = False) -> GRService:
    global _BOT_GR_SERVICE
    if _BOT_GR_SERVICE is not None and not force_refresh:
        return _BOT_GR_SERVICE
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password"),
    )
    gw = OdooGRWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password"),
    )
    _BOT_GR_SERVICE = GRService(readonly_repo=repo, write_gateway=gw)
    return _BOT_GR_SERVICE


def show_gr_menu(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "🏛️ <b>إدارة المعاملات الحكومية والجوازات (مقيم، قوى، أبشر)</b> 🏢\n"
        "────────────────────\n"
        "أهلاً بك! يتيح لك هذا القسم إدارة وتوثيق العمليات الحكومية وتدقيق المادة 40 من نظام العمل:\n\n"
        "• <b>التفريق الحتمي بين السعودي والوافد:</b> منع تسجيل معاملات الإقامة والتأشيرات للمواطنين.\n"
        "• <b>التزامات المنشأة (المادة 40):</b> تحمل رسوم رخص العمل وتجديد الإقامة وتأشيرات الاستقدام.\n"
        "• <b>إدارة الرسوم والمشاركة:</b> توثيق تحمل المنشأة أو العامل أو المشاركة بنسبة مئوية.\n"
        "• <b>التكامل المباشر:</b> تسجيل المعاملة في Odoo والتحقق المستقل منها فوراً."
    )
    kb = {
        "inline_keyboard": [
            [
                {"text": "📋 استعلام ومعاملة جديدة للموظف", "callback_data": "gr:prompt"},
            ],
            [
                {"text": "📜 دليل الرسوم والتزامات المادة 40", "callback_data": "gr:laws_guide"},
            ],
            [
                {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_gr_laws_guide(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "📜 <b>دليل المعاملات الحكومية ونظام العمل السعودي (المادة 40):</b>\n"
        "────────────────────\n"
        "📌 <b>1. التزامات صاحب العمل (المادة 40 فقرة 1):</b>\n"
        "  • رسوم استقدام العامل غير السعودي ورسوم الإقامة ورخصة العمل وتجديدهما.\n"
        "  • غرامات التأخير الناتجة عن التقصير في التجديد في المواعيد النظامية.\n"
        "  • رسوم تغيير المهنة إذا كان التغيير لمصلحة العمل.\n"
        "  • تذكرة عودة العامل إلى موطنه بعد انتهاء العلاقة التعاقدية.\n\n"
        "👤 <b>2. التزامات العامل (المادة 40 فقرة 2):</b>\n"
        "  • نفقات العودة إذا كان غير صالح للعمل أو رغب في العودة دون سبب مشروع.\n\n"
        "🔄 <b>3. نقل الخدمات (المادة 40 فقرة 3):</b>\n"
        "  • يتحمل صاحب العمل الجديد رسوم نقل خدمات العامل إليه.\n\n"
        "🇸🇦 <b>4. خصوصية المواطن السعودي:</b>\n"
        "  • لا يخضع لمعاملات الجوازات والتأشيرات الخاصة بالوافدين (إقامة، خروج وعودة، خروج نهائي).\n"
        "  • معاملاته محصورة في: توثيق قوى، التأمينات GOSI، والتراخيص المهنية.\n\n"
        "💵 <b>5. الرسوم المعيارية في المنصات الحكومية (مقيم وقوى):</b>\n"
        "  • تجديد إقامة: <b>650 ر.س</b> سنوياً\n"
        "  • تأشيرة خروج وعودة مفردة: <b>200 ر.س</b> (شهران)\n"
        "  • تأشيرة خروج وعودة متعددة: <b>500 ر.س</b> (3 أشهر)\n"
        "  • تأشيرة خروج نهائي: <b>مجاناً (0 ر.س)</b>\n"
        "  • تعديل مهنة: <b>1,000 ر.س</b>\n"
        "  • نقل كفالة: <b>2,000 ر.س</b> (المرة الأولى) / <b>4,000 ر.س</b> (الثانية)"
    )
    kb = {
        "inline_keyboard": [
            [{"text": "📋 تسجيل معاملة حكومية الآن", "callback_data": "gr:prompt"}],
            [{"text": "🔙 عُد لقائمة المعاملات", "callback_data": "menu:gr"}],
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_employee_gr_card(
    bot: TelegramBotClient,
    chat_id: int | str,
    employee_id: int,
    message_id: Optional[int] = None
) -> None:
    service = get_gr_service_for_bot()
    try:
        summary = service.get_employee_gr_summary(employee_id=employee_id)
        text = (
            f"📊 <b>بطاقة المعاملات الحكومية والجوازات</b> 🏛️\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {summary.employee_name} (#{summary.employee_id})\n"
            f"🏢 <b>القسم:</b> {summary.department_name}\n"
            f"🇸🇦 <b>التصنيف والجنسية:</b> <b>{summary.nationality_text_ar}</b>\n"
            f"🆔 <b>رقم الهوية / الإقامة:</b> <code>{summary.identification_id}</code>\n"
            f"📁 <b>إجمالي المعاملات المسجلة في Odoo:</b> <b>{summary.total_transactions_count} معاملة</b>\n"
            f"────────────────────\n"
        )
        if summary.recent_transactions:
            text += "🗓️ <b>آخر المعاملات المسجلة:</b>\n"
            for t in summary.recent_transactions[:3]:
                t_date = t.get("transaction_date", "")
                t_name = t.get("transaction", "")
                t_amt = t.get("amount", 0.0)
                t_state = t.get("state", "draft")
                text += f"  • {t_date}: {t_name} ({t_amt:,.2f} ر.س) - حالة: <code>{t_state}</code>\n"
        else:
            text += "<i>لا توجد معاملات حكومية سابقة مسجلة لهذا الموظف.</i>\n"

        kb = {
            "inline_keyboard": [
                [{"text": "📋 تسجيل معاملة لهذا الموظف", "callback_data": f"gr:tx_for:{employee_id}"}],
                [{"text": "🔙 عُد لقائمة المعاملات", "callback_data": "menu:gr"}],
            ]
        }
        if message_id:
            bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
        else:
            bot.send_message(chat_id, text, reply_markup=kb)
    except Exception as exc:
        err_text = f"❌ <b>خطأ:</b> تعذر جلب معاملات الموظف #{employee_id}: <code>{exc}</code>"
        kb = {"inline_keyboard": [[{"text": "🔙 عُد للمعاملات", "callback_data": "menu:gr"}]]}
        if message_id:
            bot.edit_message_text(chat_id, message_id, err_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, err_text, reply_markup=kb)


def handle_gr_wizard_step(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    text: str,
    msg_id: Optional[int] = None,
) -> bool:
    wiz = ACTIVE_GR_WIZARDS.get(str(chat_id))
    if not wiz:
        return False

    clean_text = text.strip()
    mode = wiz.get("mode")

    if clean_text in ("إلغاء", "تراجع", "خروج", "cancel"):
        ACTIVE_GR_WIZARDS.pop(str(chat_id), None)
        show_gr_menu(bot, chat_id)
        return True

    if mode == "gr_emp":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "gr_act", "gr:cancel", msg_id)
        if not emp:
            return True
        emp_id = emp["id"]
        wiz["employee_id"] = emp_id
        wiz["mode"] = "gr_details"
        prompt_text = (
            f"🏛️ <b>بيانات المعاملة الحكومية للموظف #{emp_id}:</b>\n"
            f"────────────────────\n"
            f"أرسل نوع المعاملة والرسوم والطرف المسؤول مفصولة بمسافات:\n\n"
            f"الصيغة: <code>[نوع المعاملة] [الرسوم اختياري] [الطرف المسؤول: company أو employee أو split]</code>\n\n"
            f"أمثلة شائعة:\n"
            f"• <code>تجديد إقامة</code> (يتم اعتماد 650 ر.س على المنشأة)\n"
            f"• <code>إصدار تأشيرة خروج وعودة</code> (200 ر.س على المنشأة)\n"
            f"• <code>تأشيرة خروج وعودة 200 employee</code> (200 ر.س على الموظف)\n"
            f"• <code>نقل كفالة 2000 company</code> (2000 ر.س على المنشأة)\n"
            f"• <code>توثيق عقد عمل في قوى</code> (0 ر.س للمواطن أو المقيم)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "gr:cancel"}]]}
        bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb, reply_to_message_id=msg_id)
        return True

    elif mode == "gr_details":
        parts = clean_text.split()
        if not parts:
            bot.send_message(chat_id, "⚠️ يرجى كتابة نوع المعاملة الحكومية (مثال: تجديد إقامة):", reply_to_message_id=msg_id)
            return True

        tx_parts = []
        amount_val = None
        resp_party = "company"
        tx_type = "party"

        for p in parts:
            p_lower = p.lower()
            if p_lower in ("company", "منشأة", "المنشأة", "الشركة"):
                resp_party = "company"
                tx_type = "party"
            elif p_lower in ("employee", "موظف", "الموظف", "عامل", "العامل"):
                resp_party = "employee"
                tx_type = "party"
            elif p_lower in ("split", "مناصفة", "مشاركة"):
                tx_type = "split"
            else:
                try:
                    num = float(p)
                    amount_val = num
                except ValueError:
                    tx_parts.append(p)

        tx_name = " ".join(tx_parts).strip()
        if not tx_name:
            tx_name = "معاملة حكومية عامة"

        emp_id = wiz["employee_id"]
        service = get_gr_service_for_bot()
        dry_res = service.dry_run_gr_transaction(
            employee_id=emp_id,
            transaction=tx_name,
            amount=amount_val,
            transaction_type=tx_type,
            responsible_party=resp_party,
        )

        if not dry_res.is_valid:
            err_msg = "❌ <b>تعذر تدقيق المعاملة الحكومية:</b>\n"
            for e in dry_res.errors:
                err_msg += f"  • {e}\n"
            bot.send_message(chat_id, err_msg, reply_to_message_id=msg_id)
            return True

        ACTIVE_GR_WIZARDS.pop(str(chat_id), None)
        token = dry_res.approval_token

        summary_text = (
            f"📊 <b>نتائج الفحص والتدقيق الاستباقي للمعاملة الحكومية:</b>\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {dry_res.employee_name} (#{dry_res.employee_id})\n"
            f"🇸🇦 <b>التصنيف:</b> <b>{dry_res.nationality_text_ar}</b>\n"
            f"🏛️ <b>نوع المعاملة:</b> <b>{dry_res.transaction}</b>\n"
            f"💵 <b>الرسوم الإجمالية:</b> <b>{dry_res.amount_sar:,.2f} ر.س</b>\n"
            f"🏢 <b>حصة المنشأة:</b> {dry_res.company_share_sar:,.2f} ر.س ({dry_res.company_percentage}%)\n"
            f"👤 <b>حصة الموظف:</b> {dry_res.employee_share_sar:,.2f} ر.س ({dry_res.employee_percentage}%)\n"
            f"⚖️ <b>المرجع النظامي:</b> {dry_res.statutory_article}\n"
            f"────────────────────\n"
        )
        if dry_res.warnings:
            summary_text += "⚠️ <b>تنبيهات المادة 40:</b>\n"
            for w in dry_res.warnings:
                summary_text += f"  • {w}\n"
            summary_text += "────────────────────\n"

        summary_text += (
            f"🆔 <b>رمز الموافقة:</b> <code>{token}</code>\n"
            f"اضغط الزر أدناه ثم اكتب «تأكيد» للاعتماد النهائي في Odoo:"
        )

        kb = {
            "inline_keyboard": [
                [
                    {"text": "🚀 اعتماد المعاملة في Odoo", "callback_data": f"gr_approve:{token}"},
                    {"text": "❌ تراجع", "callback_data": "gr:cancel"},
                ]
            ]
        }
        bot.send_message(chat_id, summary_text, reply_markup=kb, reply_to_message_id=msg_id)
        return True

    return False


def execute_gr_transaction_via_service(
    bot: TelegramBotClient,
    chat_id: int | str,
    token: str,
    msg_id: Optional[int] = None,
) -> None:
    service = get_gr_service_for_bot()
    bot.send_message(chat_id, "⏳ جارِ تسجيل المعاملة الحكومية في Odoo والتحقق المستقل...", reply_to_message_id=msg_id)
    try:
        res = service.apply_gr_transaction(approval_token=token, user_confirmation_text="تأكيد")
        if res.success:
            succ_text = (
                f"🎉 <b>تم تسجيل المعاملة الحكومية بنجاح في Odoo!</b>\n"
                f"────────────────────\n"
                f"👤 <b>الموظف:</b> {res.employee_name} (#{res.employee_id})\n"
                f"🔖 <b>الرقم المرجعي:</b> <code>{res.reference}</code>\n"
                f"🏛️ <b>المعاملة:</b> {res.transaction}\n"
                f"💵 <b>الرسوم المعتمدة:</b> <b>{res.amount_sar:,.2f} ر.س</b>\n"
                f"🔢 <b>رقم السجل في Odoo:</b> <code>#{res.transaction_id}</code>\n"
                f"✅ <b>التحقق المستقل:</b> ناجح ومطابق (Readback Verified)\n"
                f"────────────────────\n"
                f"تم توثيق العملية بالكامل في سجل تدقيق المعاملات الحكومية (logs/gr_audit_log.jsonl)."
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "🏛️ العودة لقائمة المعاملات", "callback_data": "menu:gr"}],
                    [{"text": "🔙 القائمة الرئيسية", "callback_data": "menu:main"}],
                ]
            }
            bot.send_message(chat_id, succ_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, f"❌ <b>فشل تسجيل المعاملة:</b> {res.message_ar}")
    except Exception as exc:
        bot.send_message(chat_id, f"❌ <b>خطأ أثناء التنفيذ:</b> <code>{exc}</code>")


_BOT_APPRAISAL_SERVICE: Optional[AppraisalService] = None

def get_appraisal_service_for_bot(force_refresh: bool = False) -> AppraisalService:
    global _BOT_APPRAISAL_SERVICE
    if _BOT_APPRAISAL_SERVICE is not None and not force_refresh:
        return _BOT_APPRAISAL_SERVICE
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password"),
    )
    gw = OdooAppraisalWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password"),
    )
    _BOT_APPRAISAL_SERVICE = AppraisalService(readonly_repo=repo, write_gateway=gw)
    return _BOT_APPRAISAL_SERVICE


def show_appraisal_menu(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "🌟 <b>إدارة تقييمات الأداء والموظفين (Appraisals & Performance)</b> 🏢\n"
        "────────────────────\n"
        "أهلاً بك! يتيح لك هذا القسم إدارة وتدقيق تقييمات الأداء الدورية وفترة التجربة نظامياً:\n\n"
        "• <b>تقييم فترة التجربة (المادة 53):</b> فحص المدة (90/180 يوماً) وتقرير التثبيت أو إنهاء العقد.\n"
        "• <b>التقييم السنوي الموزون:</b> 70% مؤشرات أداء (KPIs) + 30% كفاءات وسلوكيات.\n"
        "• <b>التفريق الحتمي بين السعودي والوافد:</b>\n"
        "  - المواطن: أولوية الترقية، والتطوير القيادي والإحلال، وخطة تحسين الأداء (PIP) الإلزامية.\n"
        "  - المقيم: ربط التقييم بتجديد العقد المحدد المدة (المادة 37) ورخصة العمل في قوى.\n"
        "• <b>التكامل المباشر مع Odoo:</b> إنشاء واعتماد السجل فوراً مع التحقق المستقل."
    )
    kb = {
        "inline_keyboard": [
            [
                {"text": "📋 استعلام وتقييم جديد للموظف", "callback_data": "appraisal:prompt"},
            ],
            [
                {"text": "📜 دليل التقديرات وضوابط المادة 53", "callback_data": "appraisal:laws_guide"},
            ],
            [
                {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_appraisal_laws_guide(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "📜 <b>دليل تقييم الأداء ونظام العمل السعودي (المادة 53 ولائحة العمل):</b>\n"
        "────────────────────\n"
        "📌 <b>1. ضوابط فترة التجربة (المادة 53):</b>\n"
        "  • المدة الأساسية: بحد أقصى <b>90 يوماً</b> من مباشرة العمل.\n"
        "  • التمديد: يجوز حتى <b>180 يوماً</b> باتفاق كتابي صريح بين الطرفين أثناء سريان العقد.\n"
        "  • لا تحسب إجازتا العيدين والإجازات المرضية ضمن مدة التجربة.\n"
        "  • إنهاء العقد خلال التجربة لا يترتب عليه مكافأة نهاية خدمة أو تعويض م/77.\n\n"
        "📊 <b>2. سلم التقديرات المعتمد (الدرجات والمعدلات):</b>\n"
        "  • 🟢 <b>ممتاز (90 - 100%):</b> ترقية استحقاق، علاوة تميز، إدراج بخطة الإحلال.\n"
        "  • 🔵 <b>جيد جداً (80 - 89.9%):</b> تثبيت مسار التميز، علاوة دورية.\n"
        "  • 🟡 <b>جيد (70 - 79.9%):</b> أداء مرضي، برامج تدريب وتطوير سنوية.\n"
        "  • 🟠 <b>مقبول (60 - 69.9%):</b> خطة تحسين أداء (PIP) لمدة 90 يوماً.\n"
        "  • 🔴 <b>غير مرضٍ (< 60%):</b> إنذار أداء، خطة تصحيحية مشددة للمواطن، أو عدم تجديد عقد الوافد (م/37).\n\n"
        "⚖️ <b>3. الأوزان والمعادلة:</b>\n"
        "  <code>المعدل العام = (درجة الأهداف × 70%) + (درجة الكفاءات × 30%)</code>"
    )
    kb = {
        "inline_keyboard": [
            [{"text": "📋 تسجيل وتدقيق تقييم الآن", "callback_data": "appraisal:prompt"}],
            [{"text": "🔙 عُد لقائمة التقييمات", "callback_data": "menu:appraisal"}],
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_employee_appraisal_card(
    bot: TelegramBotClient,
    chat_id: int | str,
    employee_id: int,
    message_id: Optional[int] = None
) -> None:
    service = get_appraisal_service_for_bot()
    try:
        summary = service.get_employee_appraisal_summary(employee_id=employee_id)
        prob_tag = "⚠️ داخل فترة التجربة (مادة 53)" if summary.in_probation_period else "✅ اجتاز فترة التجربة"
        text = (
            f"📊 <b>بطاقة تقييم الأداء والموظف</b> 🌟\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {summary.employee_name} (#{summary.employee_id})\n"
            f"🏢 <b>القسم:</b> {summary.department_name} | <b>المسمى:</b> {summary.job_title}\n"
            f"🇸🇦 <b>التصنيف:</b> <b>{summary.nationality_text_ar}</b>\n"
            f"📅 <b>تاريخ المباشرة:</b> {summary.hiring_date} ({summary.days_since_hiring} يوماً)\n"
            f"⏱️ <b>حالة التجربة:</b> <b>{prob_tag}</b>\n"
            f"📁 <b>إجمالي التقييمات المسجلة:</b> <b>{summary.total_appraisals_count}</b>\n"
            f"────────────────────\n"
        )
        if summary.last_score is not None:
            text += f"🎖️ <b>آخر تقييم معتمد:</b> {summary.last_score}% ({summary.last_rating_ar})\n"
        else:
            text += "<i>لا توجد تقييمات سابقة مسجلة لهذا الموظف في Odoo.</i>\n"

        kb = {
            "inline_keyboard": [
                [{"text": "📋 تقييم جديد لهذا الموظف", "callback_data": f"appraisal:eval_for:{employee_id}"}],
                [{"text": "🔙 عُد لقائمة التقييمات", "callback_data": "menu:appraisal"}],
            ]
        }
        if message_id:
            bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
        else:
            bot.send_message(chat_id, text, reply_markup=kb)
    except Exception as exc:
        err_text = f"❌ <b>خطأ:</b> تعذر جلب بطاقة تقييم الموظف #{employee_id}: <code>{exc}</code>"
        kb = {"inline_keyboard": [[{"text": "🔙 عُد للتقييمات", "callback_data": "menu:appraisal"}]]}
        if message_id:
            bot.edit_message_text(chat_id, message_id, err_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, err_text, reply_markup=kb)


def handle_appraisal_wizard_step(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    text: str,
    msg_id: Optional[int] = None,
) -> bool:
    wiz = ACTIVE_APPRAISAL_WIZARDS.get(str(chat_id))
    if not wiz:
        return False

    clean_text = text.strip()
    mode = wiz.get("mode")

    if clean_text in ("إلغاء", "تراجع", "خروج", "cancel"):
        ACTIVE_APPRAISAL_WIZARDS.pop(str(chat_id), None)
        show_appraisal_menu(bot, chat_id)
        return True

    if mode == "appraisal_emp":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "appraisal_act", "appraisal:cancel", msg_id)
        if not emp:
            return True
        emp_id = emp["id"]
        wiz["employee_id"] = emp_id
        wiz["mode"] = "appraisal_details"
        prompt_text = (
            f"🌟 <b>بيانات تقييم الموظف #{emp_id}:</b>\n"
            f"────────────────────\n"
            f"أرسل درجات التقييم ونوعه مفصولة بمسافات:\n\n"
            f"الصيغة: <code>[درجة الأهداف KPIs من 100] [درجة الكفاءات من 100] [النوع: annual أو probation]</code>\n\n"
            f"أمثلة شائعة:\n"
            f"• <code>90 85 annual</code> (تقييم سنوي: 90 أهداف، 85 كفاءات)\n"
            f"• <code>95 90</code> (تقييم سنوي افتراضي)\n"
            f"• <code>75 70 probation</code> (تقييم فترة التجربة م/53)\n"
            f"• <code>55 50 annual</code> (تقييم ضعيف لفحص خطة PIP)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "appraisal:cancel"}]]}
        bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb, reply_to_message_id=msg_id)
        return True

    elif mode == "appraisal_details":
        parts = clean_text.split()
        if not parts:
            bot.send_message(chat_id, "⚠️ يرجى إدخال درجات التقييم (مثال: 90 85 annual):", reply_to_message_id=msg_id)
            return True

        kpi_val = 80.0
        comp_val = 80.0
        app_type = "annual"
        nums = []

        for p in parts:
            p_lower = p.lower()
            if p_lower in ("probation", "تجربة", "تجربه"):
                app_type = "probation"
            elif p_lower in ("annual", "سنوي", "سنويه"):
                app_type = "annual"
            else:
                try:
                    num = float(p)
                    nums.append(num)
                except ValueError:
                    pass

        if len(nums) >= 2:
            kpi_val, comp_val = nums[0], nums[1]
        elif len(nums) == 1:
            kpi_val = comp_val = nums[0]

        emp_id = wiz["employee_id"]
        service = get_appraisal_service_for_bot()
        dry_res = service.dry_run_appraisal(
            employee_id=emp_id,
            appraisal_type=app_type,
            kpi_score=kpi_val,
            competency_score=comp_val,
        )

        if not dry_res.is_valid:
            err_msg = "❌ <b>تعذر تدقيق تقييم الأداء:</b>\n"
            for e in dry_res.errors:
                err_msg += f"  • {e}\n"
            bot.send_message(chat_id, err_msg, reply_to_message_id=msg_id)
            return True

        ACTIVE_APPRAISAL_WIZARDS.pop(str(chat_id), None)
        token = dry_res.approval_token

        summary_text = (
            f"📊 <b>نتائج التدقيق الاستباقي المعتمد لتقييم الأداء:</b>\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {dry_res.employee_name} (#{dry_res.employee_id})\n"
            f"🇸🇦 <b>التصنيف:</b> <b>{dry_res.nationality_text_ar}</b>\n"
            f"📝 <b>عنوان التقييم:</b> {dry_res.appraisal_title}\n"
            f"🎯 <b>درجة الأهداف (70%):</b> {dry_res.kpi_score} / 100\n"
            f"🤝 <b>درجة الكفاءات (30%):</b> {dry_res.competency_score} / 100\n"
            f"🏆 <b>المعدل النهائي:</b> <b>{dry_res.final_percentage}%</b> — تقدير: <b>({dry_res.rating_ar})</b>\n"
            f"💡 <b>التوصية المعتمدة:</b> {dry_res.recommendation_ar}\n"
            f"⚖️ <b>المرجع النظامي:</b> {dry_res.statutory_article}\n"
            f"────────────────────\n"
        )
        if dry_res.warnings:
            summary_text += "⚠️ <b>تنبيهات الموارد البشرية:</b>\n"
            for w in dry_res.warnings:
                summary_text += f"  • {w}\n"
            summary_text += "────────────────────\n"

        summary_text += (
            f"🆔 <b>رمز الموافقة:</b> <code>{token}</code>\n"
            f"اضغط الزر أدناه ثم اكتب «تأكيد» للاعتماد النهائي في Odoo:"
        )

        kb = {
            "inline_keyboard": [
                [
                    {"text": "🚀 اعتماد التقييم في Odoo", "callback_data": f"appraisal_approve:{token}"},
                    {"text": "❌ تراجع", "callback_data": "appraisal:cancel"},
                ]
            ]
        }
        bot.send_message(chat_id, summary_text, reply_markup=kb, reply_to_message_id=msg_id)
        return True

    return False


def execute_appraisal_via_service(
    bot: TelegramBotClient,
    chat_id: int | str,
    token: str,
    msg_id: Optional[int] = None,
) -> None:
    service = get_appraisal_service_for_bot()
    bot.send_message(chat_id, "⏳ جارِ تسجيل واعتماد تقييم الأداء في Odoo والتحقق المستقل...", reply_to_message_id=msg_id)
    try:
        res = service.apply_appraisal(approval_token=token, user_confirmation_text="تأكيد")
        if res.success:
            succ_text = (
                f"🎉 <b>تم تسجيل واعتماد تقييم الأداء بنجاح في Odoo!</b>\n"
                f"────────────────────\n"
                f"👤 <b>الموظف:</b> {res.employee_name} (#{res.employee_id})\n"
                f"📝 <b>العنوان:</b> {res.appraisal_title}\n"
                f"🏆 <b>النسبة النهائية:</b> <b>{res.final_percentage}%</b> ({res.rating_ar})\n"
                f"🔢 <b>رقم السجل في Odoo:</b> <code>#{res.appraisal_id}</code>\n"
                f"✅ <b>التحقق المستقل:</b> ناجح ومطابق (Readback Verified)\n"
                f"────────────────────\n"
                f"تم توثيق العملية بالكامل في سجل تدقيق التقييمات (logs/appraisal_audit_log.jsonl)."
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "🌟 العودة لقائمة التقييمات", "callback_data": "menu:appraisal"}],
                    [{"text": "🔙 القائمة الرئيسية", "callback_data": "menu:main"}],
                ]
            }
            bot.send_message(chat_id, succ_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, f"❌ <b>فشل تسجيل التقييم:</b> {res.message_ar}")
    except Exception as exc:
        bot.send_message(chat_id, f"❌ <b>خطأ أثناء التنفيذ:</b> <code>{exc}</code>")


_BOT_LOAN_SERVICE: Optional[LoanService] = None

def get_loan_service_for_bot(force_refresh: bool = False) -> LoanService:
    global _BOT_LOAN_SERVICE
    if _BOT_LOAN_SERVICE is not None and not force_refresh:
        return _BOT_LOAN_SERVICE
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password"),
    )
    gw = OdooLoanWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("password"),
    )
    _BOT_LOAN_SERVICE = LoanService(readonly_repo=repo, write_gateway=gw)
    return _BOT_LOAN_SERVICE


def show_loan_menu(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "💳 <b>إدارة سلف وقروض الموظفين (Employee Loans & Advances)</b> 🏢\n"
        "────────────────────\n"
        "أهلاً بك! يتيح لك هذا القسم جدولة وتدقيق سلف وقروض الموظفين وضمان توافقها التام مع المادة 92 من نظام العمل:\n\n"
        "• <b>سقف الاستقطاع الشهري (المادة 92 فقرة 1):</b> حظر تجاوز القسط 25% من راتب الموظف شهرياً.\n"
        "• <b>السقف الإجمالي للاستقطاعات:</b> ألا تتجاوز إجمالي الحسومات 50% من الأجر المستحق.\n"
        "• <b>حظر الفوائد الربوية:</b> قروض وسلف ميسرة بصفر فوائد (0% Interest).\n"
        "• <b>التفريق الحتمي بين السعودي والوافد:</b>\n"
        "  - الوافد: مواءمة الأقساط مع مدة العقد المحدد (المادة 37) وضمانها برصيد نهاية الخدمة.\n"
        "  - المواطن: مرونة سداد أطول مع مراعاة حسم التأمينات الاجتماعية GOSI.\n"
        "• <b>التكامل المباشر مع Odoo:</b> إنشاء السلفة مع خطة استقطاع المسيرات (By Payslip)."
    )
    kb = {
        "inline_keyboard": [
            [
                {"text": "📋 استعلام وسلفة جديدة للموظف", "callback_data": "loan:prompt"},
            ],
            [
                {"text": "📜 دليل ضوابط المادة 92 وسقف الاستقطاع", "callback_data": "loan:laws_guide"},
            ],
            [
                {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_loan_laws_guide(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "📜 <b>دليل سلف الموظفين ونظام العمل السعودي (المادة 92):</b>\n"
        "────────────────────\n"
        "📌 <b>1. سقف استرداد قروض صاحب العمل (المادة 92 فقرة 1):</b>\n"
        "  • لا يجوز حسم أكثر من <b>25% من أجر العامل شهرياً</b> لاسترداد قروض المنشأة.\n"
        "  • إذا كان القسط المطلوب أعلى من 25%، يلزم نظاماً تمديد عدد الأشهر (Term).\n\n"
        "📊 <b>2. السقف الإجمالي للحسومات (المادة 92 الفقرة الأخيرة):</b>\n"
        "  • لا يجوز في جميع الأحوال أن تزيد نسبة المبالغ المحسومة على <b>نصف أجر العامل (50%)</b>.\n"
        "  • يشمل ذلك: أقساط السلف + اشتراك التأمينات GOSI + أي جزاءات أو ديون قضائية.\n\n"
        "⚖️ <b>3. التوافق الشرعي والنظامي:</b>\n"
        "  • السلف تقدم بدون أي فوائد إضافية (نسبة الفائدة = 0%).\n\n"
        "🇸🇦 <b>4. الوافد مقابل المواطن:</b>\n"
        "  • الوافد المقيم: يُشترط ألا تتجاوز فترة السداد تاريخ نهاية العقد المحدد المدة (المادة 37) إلا بوجود رصيد كافٍ من مكافأة نهاية الخدمة."
    )
    kb = {
        "inline_keyboard": [
            [{"text": "📋 تسجيل وتدقيق سلفة الآن", "callback_data": "loan:prompt"}],
            [{"text": "🔙 عُد لقائمة السلف", "callback_data": "menu:loan"}],
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_employee_loan_card(
    bot: TelegramBotClient,
    chat_id: int | str,
    employee_id: int,
    message_id: Optional[int] = None
) -> None:
    service = get_loan_service_for_bot()
    try:
        summary = service.get_employee_loan_summary(employee_id=employee_id)
        text = (
            f"📊 <b>بطاقة سلف وقروض الموظف</b> 💳\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {summary.employee_name} (#{summary.employee_id})\n"
            f"🏢 <b>القسم:</b> {summary.department_name} | <b>المسمى:</b> {summary.job_title}\n"
            f"🇸🇦 <b>التصنيف:</b> <b>{summary.nationality_text_ar}</b>\n"
            f"💰 <b>الراتب الشهري الأساسي والبدلات:</b> <b>{summary.monthly_wage:,.2f} ر.س</b>\n"
            f"⚖️ <b>الحد الأقصى للقسط الشهري نظاماً (25%):</b> <b>{summary.max_allowed_monthly_deduction:,.2f} ر.س</b>\n"
            f"📁 <b>السلف النشطة:</b> <b>{summary.active_loans_count}</b> (إجمالي: {summary.total_active_loan_amount:,.2f} ر.س)\n"
            f"────────────────────\n"
        )
        if not summary.is_saudi:
            rem_m = f"{summary.remaining_contract_months} شهراً" if summary.remaining_contract_months is not None else "غير محدد"
            text += f"📅 <b>المدة المتبقية بالعقد (م/37):</b> {rem_m}\n"
            text += f"🛡️ <b>رصيد نهاية الخدمة التقديري (ضمان):</b> {summary.estimated_eos_balance:,.2f} ر.س\n"

        if summary.recent_loans:
            text += "\n📋 <b>آخر السلف المسجلة:</b>\n"
            for l in summary.recent_loans[:3]:
                l_amt = float(l.get("loan_amount") or 0.0)
                l_inst = float(l.get("installment_amount") or 0.0)
                l_st = l.get("state", "draft")
                text += f"  • سلفة {l_amt:,.2f} ر.س (قسط {l_inst:,.2f} ر.س) - حالة: <code>{l_st}</code>\n"

        kb = {
            "inline_keyboard": [
                [{"text": "📋 تسجيل سلفة لهذا الموظف", "callback_data": f"loan:req_for:{employee_id}"}],
                [{"text": "🔙 عُد لقائمة السلف", "callback_data": "menu:loan"}],
            ]
        }
        if message_id:
            bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
        else:
            bot.send_message(chat_id, text, reply_markup=kb)
    except Exception as exc:
        err_text = f"❌ <b>خطأ:</b> تعذر جلب بطاقة سلف الموظف #{employee_id}: <code>{exc}</code>"
        kb = {"inline_keyboard": [[{"text": "🔙 عُد للسلف", "callback_data": "menu:loan"}]]}
        if message_id:
            bot.edit_message_text(chat_id, message_id, err_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, err_text, reply_markup=kb)


def handle_loan_wizard_step(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    text: str,
    msg_id: Optional[int] = None,
) -> bool:
    wiz = ACTIVE_LOAN_WIZARDS.get(str(chat_id))
    if not wiz:
        return False

    clean_text = text.strip()
    mode = wiz.get("mode")

    if clean_text in ("إلغاء", "تراجع", "خروج", "cancel"):
        ACTIVE_LOAN_WIZARDS.pop(str(chat_id), None)
        show_loan_menu(bot, chat_id)
        return True

    if mode == "loan_emp":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "loan_act", "loan:cancel", msg_id)
        if not emp:
            return True
        emp_id = emp["id"]
        wiz["employee_id"] = emp_id
        wiz["mode"] = "loan_details"
        prompt_text = (
            f"💳 <b>بيانات طلب السلفة للموظف #{emp_id}:</b>\n"
            f"────────────────────\n"
            f"أرسل مبلغ السلفة ومدة السداد بالأشهر والقسط مفصولة بمسافات:\n\n"
            f"الصيغة: <code>[مبلغ السلفة] [مدة السداد بالأشهر] [القسط اختياري]</code>\n\n"
            f"أمثلة شائعة:\n"
            f"• <code>6000 6</code> (سلفة 6000 ر.س على 6 أشهر، قسط 1000 ر.س)\n"
            f"• <code>10000 10 1000</code> (سلفة 10000 ر.س على 10 أشهر بقسط محدد)\n"
            f"• <code>15000 12</code> (يتم التحقق تلقائياً من سقف الـ 25% بموجب م/92)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "loan:cancel"}]]}
        bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb, reply_to_message_id=msg_id)
        return True

    elif mode == "loan_details":
        parts = clean_text.split()
        if not parts:
            bot.send_message(chat_id, "⚠️ يرجى إدخال مبلغ السلفة والمدة (مثال: 6000 6):", reply_to_message_id=msg_id)
            return True

        nums = []
        for p in parts:
            try:
                nums.append(float(p))
            except ValueError:
                pass

        if not nums:
            bot.send_message(chat_id, "⚠️ لم يتم التعرف على أرقام. يرجى إدخال المبلغ والمدة (مثال: 6000 6):", reply_to_message_id=msg_id)
            return True

        amount_val = nums[0]
        term_val = int(nums[1]) if len(nums) >= 2 else 12
        inst_val = nums[2] if len(nums) >= 3 else None

        emp_id = wiz["employee_id"]
        service = get_loan_service_for_bot()
        dry_res = service.dry_run_loan(
            employee_id=emp_id,
            loan_amount=amount_val,
            term=term_val,
            installment_amount=inst_val,
        )

        if not dry_res.is_valid:
            err_msg = "❌ <b>تعذر اعتماد طلب السلفة لمخالفة المادة 92:</b>\n"
            for e in dry_res.errors:
                err_msg += f"  • {e}\n"
            bot.send_message(chat_id, err_msg, reply_to_message_id=msg_id)
            return True

        ACTIVE_LOAN_WIZARDS.pop(str(chat_id), None)
        token = dry_res.approval_token

        summary_text = (
            f"📊 <b>نتائج التدقيق الاستباقي المعتمد لسلفة الموظف:</b>\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {dry_res.employee_name} (#{dry_res.employee_id})\n"
            f"🇸🇦 <b>التصنيف:</b> <b>{dry_res.nationality_text_ar}</b>\n"
            f"💰 <b>مبلغ السلفة الإجمالي:</b> <b>{dry_res.loan_amount:,.2f} ر.س</b>\n"
            f"📅 <b>مدة السداد بالأشهر:</b> <b>{dry_res.term} شهراً</b>\n"
            f"💵 <b>القسط الشهري:</b> <b>{dry_res.installment_amount:,.2f} ر.س</b>\n"
            f"📊 <b>نسبة الاستقطاع من الراتب:</b> <b>{dry_res.deduction_percentage_of_wage}%</b> (الحد الأقصى: 25%)\n"
            f"⚖️ <b>المرجع النظامي:</b> {dry_res.statutory_article}\n"
            f"────────────────────\n"
        )
        if dry_res.warnings:
            summary_text += "⚠️ <b>تنبيهات الموارد البشرية:</b>\n"
            for w in dry_res.warnings:
                summary_text += f"  • {w}\n"
            summary_text += "────────────────────\n"

        summary_text += (
            f"🆔 <b>رمز الموافقة:</b> <code>{token}</code>\n"
            f"اضغط الزر أدناه ثم اكتب «تأكيد» للاعتماد النهائي في Odoo:"
        )

        kb = {
            "inline_keyboard": [
                [
                    {"text": "🚀 اعتماد السلفة في Odoo", "callback_data": f"loan_approve:{token}"},
                    {"text": "❌ تراجع", "callback_data": "loan:cancel"},
                ]
            ]
        }
        bot.send_message(chat_id, summary_text, reply_markup=kb, reply_to_message_id=msg_id)
        return True

    return False


def execute_loan_via_service(
    bot: TelegramBotClient,
    chat_id: int | str,
    token: str,
    msg_id: Optional[int] = None,
) -> None:
    service = get_loan_service_for_bot()
    bot.send_message(chat_id, "⏳ جارِ تسجيل واعتماد السلفة في Odoo والتحقق المستقل...", reply_to_message_id=msg_id)
    try:
        res = service.apply_loan(approval_token=token, user_confirmation_text="تأكيد")
        if res.success:
            succ_text = (
                f"🎉 <b>تم تسجيل واعتماد سلفة الموظف بنجاح في Odoo!</b>\n"
                f"────────────────────\n"
                f"👤 <b>الموظف:</b> {res.employee_name} (#{res.employee_id})\n"
                f"💰 <b>إجمالي السلفة:</b> <b>{res.loan_amount:,.2f} ر.س</b>\n"
                f"💵 <b>القسط الشهري:</b> <b>{res.installment_amount:,.2f} ر.س</b> لمدة <b>{res.term} شهراً</b>\n"
                f"🔢 <b>رقم السجل في Odoo:</b> <code>#{res.loan_id}</code>\n"
                f"✅ <b>التحقق المستقل:</b> ناجح ومطابق (Readback Verified)\n"
                f"────────────────────\n"
                f"تم توثيق العملية بالكامل في سجل تدقيق السلف (logs/loan_audit_log.jsonl)."
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "💳 العودة لقائمة السلف", "callback_data": "menu:loan"}],
                    [{"text": "🔙 القائمة الرئيسية", "callback_data": "menu:main"}],
                ]
            }
            bot.send_message(chat_id, succ_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, f"❌ <b>فشل تسجيل السلفة:</b> {res.message_ar}")
    except Exception as exc:
        bot.send_message(chat_id, f"❌ <b>خطأ أثناء التنفيذ:</b> <code>{exc}</code>")


# =============================================================================
# وظائف إدارة التوظيف والتوطين السعودي (Phase 17: Recruitment & Saudization)
# =============================================================================

_BOT_RECRUITMENT_SERVICE: Optional[RecruitmentService] = None

def get_recruitment_service_for_bot(force_refresh: bool = False) -> RecruitmentService:
    global _BOT_RECRUITMENT_SERVICE
    if _BOT_RECRUITMENT_SERVICE is not None and not force_refresh:
        return _BOT_RECRUITMENT_SERVICE
    repo = OdooReadonlyRepository()
    gw = None
    try:
        gw = OdooRecruitmentWriteGateway(
            url=repo.url,
            db=repo.db,
            username=repo.username,
            password=repo.api_key,
        )
    except Exception:
        pass
    _BOT_RECRUITMENT_SERVICE = RecruitmentService(readonly_repo=repo, write_gateway=gw)
    return _BOT_RECRUITMENT_SERVICE


def show_recruitment_menu(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "🎯 <b>إدارة التوظيف وشواغر العمل والتوطين (Recruitment & Saudization)</b> 🏢\n"
        "────────────────────\n"
        "أهلاً بك! يتيح لك هذا القسم إدارة واستقبال طلبات التوظيف وضمان توافقها الكامل مع قرارات التوطين الرسمية:\n\n"
        "• <b>المهن المقصورة 100% على المواطنين:</b> حظر قطعي لتعيين غير السعوديين في وظائف الموارد البشرية، شؤون الموظفين، الاستقبال، والعلاقات الحكومية.\n"
        "• <b>التراخيص والاعتمادات المهنية:</b> التنبيه بمتطلبات الهيئة السعودية للمحاسبين (SOCPA) والهيئة السعودية للمهندسين (SCE).\n"
        "• <b>ضوابط التعاقد وفترة التجربة:</b>\n"
        "  - المواطن: فترة تجربة 90 يوماً تمدد لـ 180 يوماً كتابة (م/53)، واستيفاء دعم هدف/جدارات.\n"
        "  - الوافد: إلزامية العقد محدد المدة (م/37) ونقل الخدمات عبر منصة قوى.\n"
        "• <b>التكامل المباشر مع Odoo:</b> إنشاء ملف المرشح في (hr.applicant) مع حقول التوطين والأجور."
    )
    kb = {
        "inline_keyboard": [
            [
                {"text": "📋 استعراض الشواغر الوظيفية", "callback_data": "recruit:jobs_list"},
                {"text": "➕ تسجيل مرشح جديد", "callback_data": "recruit:prompt"},
            ],
            [
                {"text": "📜 دليل التوطين والمهن المقصورة (HRSD)", "callback_data": "recruit:laws_guide"},
            ],
            [
                {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_saudization_laws_guide(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "📜 <b>دليل التوطين وقواعد وزارة الموارد البشرية (HRSD):</b>\n"
        "────────────────────\n"
        "🚫 <b>1. مهن مقصورة 100% على السعوديين:</b>\n"
        "  • مدير / أخصائي / موظف موارد بشرية.\n"
        "  • مدير / أخصائي شؤون موظفين.\n"
        "  • مسؤول / أخصائي توظيف.\n"
        "  • موظف / كاتب استقبال.\n"
        "  • مسؤول علاقات حكومية (معقب).\n"
        "  • أمين صندوق (كاشير) / حارس أمن.\n\n"
        "🎓 <b>2. الاعتماد المهني الإلزامي:</b>\n"
        "  • المهن المحاسبية: التسجيل في SOCPA واحتساب نسب التوطين المحاسبي.\n"
        "  • المهن الهندسية: التسجيل في الهيئة السعودية للمهندسين (SCE).\n\n"
        "🇸🇦 <b>3. التمييز بين المواطن والمقيم:</b>\n"
        "  • المواطن: هوية تبدأ بـ (1)، دعم هدف، تسجيل فوري في التأمينات GOSI.\n"
        "  • المقيم: إقامة تبدأ بـ (2) أو جواز سفر، عقد محدد المدة نظاماً (المادة 37).\n\n"
        "⏳ <b>4. فترة التجربة (المادة 53):</b>\n"
        "  • بحد أقصى 90 يوماً، ولا تزيد على 180 يوماً باتفاق مكتوب صريح."
    )
    kb = {
        "inline_keyboard": [
            [{"text": "📋 الشواغر الوظيفية", "callback_data": "recruit:jobs_list"}],
            [{"text": "🔙 عُد لقائمة التوظيف", "callback_data": "menu:recruitment"}],
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_recruitment_jobs_list(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    service = get_recruitment_service_for_bot()
    try:
        jobs = service.get_job_openings()
        if not jobs:
            text = "ℹ️ لا توجد شواغر وظيفية مسجلة حالياً في قاعدة بيانات Odoo."
            kb = {"inline_keyboard": [[{"text": "🔙 عُد لقائمة التوظيف", "callback_data": "menu:recruitment"}]]}
            if message_id:
                bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
            else:
                bot.send_message(chat_id, text, reply_markup=kb)
            return

        text = (
            "🏢 <b>شواغر التوظيف المتاحة في المنشأة:</b>\n"
            "────────────────────\n"
        )
        buttons = []
        for j in jobs[:6]:
            icon = "🇸🇦 [سعودة 100%]" if j.is_saudi_only else "🌐 [متاح للجميع]"
            text += f"• <b>{j.name}</b> (#{j.id})\n  └ القسم: {j.department_name} | {icon}\n"
            buttons.append([{"text": f"➕ ترشيح لوظيفة: {j.name}", "callback_data": f"recruit:for_job:{j.id}"}])

        buttons.append([{"text": "🔙 عُد لقائمة التوظيف", "callback_data": "menu:recruitment"}])
        kb = {"inline_keyboard": buttons}

        if message_id:
            bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
        else:
            bot.send_message(chat_id, text, reply_markup=kb)
    except Exception as exc:
        err_text = f"❌ تعذر جلب شواغر التوظيف: <code>{exc}</code>"
        kb = {"inline_keyboard": [[{"text": "🔙 عُد لقائمة التوظيف", "callback_data": "menu:recruitment"}]]}
        if message_id:
            bot.edit_message_text(chat_id, message_id, err_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, err_text, reply_markup=kb)


def show_applicant_card(
    bot: TelegramBotClient,
    chat_id: int | str,
    applicant_id: int,
    message_id: Optional[int] = None
) -> None:
    service = get_recruitment_service_for_bot()
    try:
        summary = service.get_applicant_summary(applicant_id)
        text = (
            f"👤 <b>بطاقة المرشح / طلب التوظيف</b> 🎯\n"
            f"────────────────────\n"
            f"📝 <b>الاسم:</b> {summary.candidate_name} (#{summary.applicant_id})\n"
            f"💼 <b>الوظيفة:</b> {summary.job_title} | <b>القسم:</b> {summary.department_name}\n"
            f"🇸🇦 <b>التصنيف:</b> <b>{summary.nationality_text_ar}</b>\n"
            f"📊 <b>مرحلة التوظيف:</b> <code>{summary.stage_name}</code>\n"
            f"💰 <b>الراتب المعروض:</b> <b>{summary.salary_proposed:,.2f} ر.س</b> (المتوقع: {summary.salary_expected:,.2f} ر.س)\n"
            f"⚖️ <b>حالة التوطين:</b> {summary.saudization_status_ar}\n"
            f"────────────────────\n"
        )
        if summary.id_number:
            text += f"🆔 <b>رقم الهوية/الإقامة:</b> <code>{summary.id_number}</code>\n"
        if summary.phone:
            text += f"📞 <b>الهاتف:</b> {summary.phone}\n"

        kb = {
            "inline_keyboard": [
                [{"text": "📋 الشواغر الوظيفية", "callback_data": "recruit:jobs_list"}],
                [{"text": "🔙 عُد لقائمة التوظيف", "callback_data": "menu:recruitment"}],
            ]
        }
        if message_id:
            bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
        else:
            bot.send_message(chat_id, text, reply_markup=kb)
    except Exception as exc:
        err_text = f"❌ <b>خطأ:</b> تعذر جلب بطاقة المرشح #{applicant_id}: <code>{exc}</code>"
        kb = {"inline_keyboard": [[{"text": "🔙 عُد لقائمة التوظيف", "callback_data": "menu:recruitment"}]]}
        if message_id:
            bot.edit_message_text(chat_id, message_id, err_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, err_text, reply_markup=kb)


def handle_recruitment_wizard_step(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    text: str,
    msg_id: Optional[int] = None,
) -> bool:
    wiz = ACTIVE_RECRUITMENT_WIZARDS.get(str(chat_id))
    if not wiz:
        return False

    clean_text = text.strip()
    mode = wiz.get("mode")

    if clean_text in ("إلغاء", "تراجع", "خروج", "cancel"):
        ACTIVE_RECRUITMENT_WIZARDS.pop(str(chat_id), None)
        show_recruitment_menu(bot, chat_id)
        return True

    if mode == "recruit_job":
        try:
            job_id = int(clean_text)
        except ValueError:
            repo = OdooReadonlyRepository()
            jobs = repo.get_recruitment_jobs()
            match = next((j for j in jobs if clean_text in str(j.get("name") or "")), None)
            if match:
                job_id = int(match["id"])
            else:
                bot.send_message(
                    chat_id,
                    f"⚠️ تعذر العثور على الوظيفة '{clean_text}'. يرجى كتابة رقم معرّف الوظيفة ID مباشرة (أو اضغط الشواغر من القائمة):",
                    reply_to_message_id=msg_id,
                )
                return True

        wiz["job_id"] = job_id
        wiz["mode"] = "recruit_details"
        prompt_text = (
            f"👤 <b>بيانات المرشح للوظيفة #{job_id}:</b>\n"
            f"────────────────────\n"
            f"أرسل اسم المرشح، وجنسيته (سعودي أو وافد)، والراتب المعروض مفصولة بمسافات:\n\n"
            f"الصيغة: <code>[اسم المرشح] [الجنسية: saudi/non_saudi] [الراتب المعروض] [رقم الهوية/الإقامة اختياري]</code>\n\n"
            f"أمثلة:\n"
            f"• <code>فيصل_العتيبي saudi 8000 1012345678</code>\n"
            f"• <code>أحمد_المصري non_saudi 7000 2456789012</code>\n"
            f"• <code>سارة_الغامدي saudi 9500</code>"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "recruit:cancel"}]]}
        bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb, reply_to_message_id=msg_id)
        return True

    elif mode == "recruit_details":
        parts = clean_text.split()
        if not parts:
            bot.send_message(chat_id, "⚠️ يرجى إدخال بيانات المرشح (مثال: فيصل_العتيبي saudi 8000):", reply_to_message_id=msg_id)
            return True

        cand_name = parts[0].replace("_", " ")
        is_saudi = True
        sal_val = 0.0
        id_num = None

        if len(parts) >= 2:
            p1 = parts[1].lower()
            if p1 in ("non_saudi", "expat", "وافد", "مقيم", "اجنبي", "أجنبي"):
                is_saudi = False
            elif p1 in ("saudi", "سعودي", "مواطن"):
                is_saudi = True

        if len(parts) >= 3:
            try:
                sal_val = float(parts[2])
            except ValueError:
                sal_val = 0.0

        if len(parts) >= 4:
            id_num = parts[3]

        job_id = wiz["job_id"]
        service = get_recruitment_service_for_bot()
        dry_res = service.dry_run_applicant(
            candidate_name=cand_name,
            job_id=job_id,
            is_saudi=is_saudi,
            salary_proposed=sal_val,
            id_number=id_num,
        )

        if not dry_res.is_valid:
            err_msg = "❌ <b>تعذر اعتماد طلب التوظيف لمخالفة ضوابط التوطين:</b>\n"
            for e in dry_res.errors:
                err_msg += f"  • {e}\n"
            bot.send_message(chat_id, err_msg, reply_to_message_id=msg_id)
            return True

        ACTIVE_RECRUITMENT_WIZARDS.pop(str(chat_id), None)
        token = dry_res.approval_token

        summary_text = (
            f"📊 <b>نتائج التدقيق الاستباقي المعتمد لطلب التوظيف:</b>\n"
            f"────────────────────\n"
            f"👤 <b>المرشح:</b> {dry_res.candidate_name}\n"
            f"💼 <b>الوظيفة:</b> {dry_res.job_title} (#{dry_res.job_id})\n"
            f"🇸🇦 <b>التصنيف:</b> <b>{dry_res.nationality_text_ar}</b>\n"
            f"💰 <b>الراتب المعروض:</b> <b>{dry_res.total_salary:,.2f} ر.س</b>\n"
            f"⚖️ <b>المرجع النظامي:</b> {dry_res.statutory_article}\n"
            f"────────────────────\n"
        )
        if dry_res.warnings:
            summary_text += "⚠️ <b>تنبيهات وملاحظات الموارد البشرية:</b>\n"
            for w in dry_res.warnings:
                summary_text += f"  • {w}\n"
            summary_text += "────────────────────\n"

        summary_text += (
            f"🆔 <b>رمز الموافقة:</b> <code>{token}</code>\n"
            f"اضغط الزر أدناه ثم اكتب «تأكيد» للاعتماد النهائي في Odoo:"
        )

        kb = {
            "inline_keyboard": [
                [
                    {"text": "🚀 تسجيل المرشح في Odoo", "callback_data": f"recruit_approve:{token}"},
                    {"text": "❌ تراجع", "callback_data": "recruit:cancel"},
                ]
            ]
        }
        bot.send_message(chat_id, summary_text, reply_markup=kb, reply_to_message_id=msg_id)
        return True

    return False


def execute_applicant_via_service(
    bot: TelegramBotClient,
    chat_id: int | str,
    token: str,
    msg_id: Optional[int] = None,
) -> None:
    service = get_recruitment_service_for_bot()
    bot.send_message(chat_id, "⏳ جارِ تسجيل المرشح في Odoo والتحقق المستقل...", reply_to_message_id=msg_id)
    try:
        res = service.apply_applicant(approval_token=token, user_confirmation_text="تأكيد")
        if res.success:
            succ_text = (
                f"🎉 <b>تم تسجيل طلب التوظيف والمرشح بنجاح في Odoo!</b>\n"
                f"────────────────────\n"
                f"👤 <b>المرشح:</b> {res.candidate_name}\n"
                f"💼 <b>الوظيفة:</b> {res.job_title} (#{res.job_id})\n"
                f"🇸🇦 <b>التصنيف:</b> {'مواطن سعودي' if res.is_saudi else 'وافد غير سعودي (مقيم)'}\n"
                f"💰 <b>الراتب الإجمالي:</b> <b>{res.total_salary:,.2f} ر.س</b>\n"
                f"🔢 <b>رقم السجل في Odoo:</b> <code>#{res.applicant_id}</code>\n"
                f"✅ <b>التحقق المستقل:</b> ناجح ومطابق (Readback Verified)\n"
                f"────────────────────\n"
                f"تم توثيق العملية بالكامل في سجل تدقيق التوظيف (logs/recruitment_audit_log.jsonl)."
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "🎯 العودة لقائمة التوظيف", "callback_data": "menu:recruitment"}],
                    [{"text": "🔙 القائمة الرئيسية", "callback_data": "menu:main"}],
                ]
            }
            bot.send_message(chat_id, succ_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, f"❌ <b>فشل تسجيل المرشح:</b> {res.message_ar}")
    except Exception as exc:
        bot.send_message(chat_id, f"❌ <b>خطأ أثناء التنفيذ:</b> <code>{exc}</code>")


# =============================================================================
# وظائف إدارة وتدقيق عقود العمل وهيكلة الأجور (Phase 18: Employment Contracts & Wage Structuring)
# =============================================================================

_BOT_CONTRACT_SERVICE: Optional[ContractService] = None

def get_contract_service_for_bot(force_refresh: bool = False) -> ContractService:
    global _BOT_CONTRACT_SERVICE
    if _BOT_CONTRACT_SERVICE is not None and not force_refresh:
        return _BOT_CONTRACT_SERVICE
    repo = OdooReadonlyRepository()
    gw = None
    try:
        gw = OdooContractWriteGateway(
            url=repo.url,
            db=repo.db,
            username=repo.username,
            password=repo.api_key,
        )
    except Exception:
        pass
    _BOT_CONTRACT_SERVICE = ContractService(readonly_repo=repo, write_gateway=gw)
    return _BOT_CONTRACT_SERVICE


def show_contract_menu(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "📜 <b>إدارة عقود العمل وهيكلة الأجور والبدلات (Employment Contracts)</b> 🏢\n"
        "────────────────────\n"
        "أهلاً بك! يتيح لك هذا القسم إدارة وتوثيق عقود العمل وهياكل الأجور والبدلات في Odoo مع الامتثال التام لنظام العمل والتأمينات:\n\n"
        "• <b>التفريق الحتمي بين المواطن والمقيم:</b>\n"
        "  - المقيم (الوافد): إلزامية العقد محدد المدة وتاريخ النهاية (المادة 37)، واشتراك GOSI للأخطار 2% فقط.\n"
        "  - المواطن: إمكانية العقد محدد أو غير محدد المدة، واحتساب استقطاع GOSI بنسبة 9.75%، وحد نطاقات (4,000 ر.س).\n"
        "• <b>هيكلة الأجر والبدلات:</b>\n"
        "  - الأساسي + بدل سكن (25%) + بدل نقل (10%) + البدلات الأخرى = إجمالي الراتب.\n"
        "• <b>فترة التجربة (المادة 53):</b> 90 يوماً تمدد لـ 180 يوماً كتابة، وحظر تجاوز 180 يوماً.\n"
        "• <b>التحقق المزدوج:</b> إلزامية كلمة «تأكيد» والتحقق المستقل بعد الكتابة (Readback)."
    )
    kb = {
        "inline_keyboard": [
            [
                {"text": "➕ تحديث / إنشاء عقد عمل", "callback_data": "contract:prompt"},
                {"text": "📜 دليل عقود العمل ونظام التأمينات", "callback_data": "contract:laws_guide"},
            ],
            [
                {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_contract_laws_guide(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "📜 <b>الدليل النظامي لعقود العمل والأجور والتأمينات الاجتماعية (GOSI):</b>\n"
        "────────────────────\n"
        "⚖️ <b>1. ضوابط جنسية العامل (المادة 37):</b>\n"
        "  • <b>غير السعودي (الوافد):</b> يجب أن يكون عقد عمله محدد المدة، وإذا خلا من تحديد المدة تعد رخصة العمل هي مدة العقد.\n"
        "  • <b>المواطن السعودي:</b> يجوز أن يكون محدد المدة أو غير محدد المدة (عقد مفتوح).\n\n"
        "💰 <b>2. هيكلة الأجر واشتراكات التأمينات الاجتماعية (GOSI):</b>\n"
        "  • وعاء الاشتراك = الأجر الأساسي + بدل السكن النقدي (أو بدل السكن العيني المقدر بمرتب شهرين).\n"
        "  • سقف وعاء الاشتراك: 45,000 ر.س، والحد الأدنى: 1,500 ر.س.\n"
        "  • <b>استقطاع الموظف السعودي:</b> 9.75% (9% معاشات + 0.75% ساند).\n"
        "  • <b>مساهمة صاحب العمل للمواطن:</b> 11.75% (9% معاشات + 0.75% ساند + 2% أخطار).\n"
        "  • <b>غير السعودي:</b> 0% على الموظف، و 2% أخطار مهنية على صاحب العمل.\n\n"
        "⏳ <b>3. فترة التجربة (المادة 53):</b>\n"
        "  • الأصل ألا تزيد على 90 يوماً، وتمديدها حتى 180 يوماً مشروط بموافقة كتابية.\n\n"
        "📢 <b>4. مهلة الإشعار (المادة 75):</b>\n"
        "  • 60 يوماً على الأقل للعقد غير المحدد، و 30 يوماً للعقد المحدد."
    )
    kb = {
        "inline_keyboard": [
            [{"text": "➕ تحديث / إنشاء عقد", "callback_data": "contract:prompt"}],
            [{"text": "🔙 عُد لقائمة العقود", "callback_data": "menu:contract"}],
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_employee_contract_card(
    bot: TelegramBotClient,
    chat_id: int | str,
    employee_id: int,
    message_id: Optional[int] = None
) -> None:
    service = get_contract_service_for_bot()
    try:
        summary = service.get_employee_contract_summary(employee_id)
        text = (
            f"📜 <b>بطاقة عقد العمل وهيكل الراتب</b> 🏢\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {summary.employee_name} (#{summary.employee_id})\n"
            f"💼 <b>الوظيفة:</b> {summary.job_title} | <b>القسم:</b> {summary.department_name}\n"
            f"🇸🇦 <b>التصنيف:</b> <b>{summary.nationality_text_ar}</b>\n"
            f"📑 <b>نوع العقد:</b> <code>{summary.contract_type_name}</code>\n"
            f"📅 <b>تاريخ البداية:</b> <code>{summary.date_start}</code>\n"
        )
        if summary.date_end:
            text += f"📅 <b>تاريخ النهاية:</b> <code>{summary.date_end}</code>\n"
        else:
            text += f"📅 <b>مدة العقد:</b> عقد غير محدد المدة (مفتوح)\n"

        text += (
            f"────────────────────\n"
            f"💵 <b>الأجر الأساسي:</b> {summary.basic_wage:,.2f} ر.س\n"
            f"🏠 <b>بدل السكن:</b> {summary.housing_allowance:,.2f} ر.س\n"
            f"🚗 <b>بدل النقل:</b> {summary.transportation_allowance:,.2f} ر.س\n"
        )
        if summary.other_allowances > 0:
            text += f"➕ <b>بدلات أخرى:</b> {summary.other_allowances:,.2f} ر.س\n"

        text += (
            f"💰 <b>إجمالي الباقة (Total):</b> <b>{summary.total_package:,.2f} ر.س</b>\n"
            f"🏛️ <b>وعاء التأمينات (GOSI):</b> {summary.gosi_contributory_wage:,.2f} ر.س\n"
            f"📉 <b>استقطاع الموظف GOSI:</b> {summary.gosi_employee_deduction:,.2f} ر.س\n"
            f"💵 <b>الصافي التقديري:</b> <b>{summary.net_estimated_salary:,.2f} ر.س</b>\n"
            f"────────────────────\n"
        )
        if summary.compliance_notes:
            text += "⚠️ <b>ملاحظات الامتثال:</b>\n"
            for note in summary.compliance_notes:
                text += f"  • {note}\n"
            text += "────────────────────\n"

        kb = {
            "inline_keyboard": [
                [{"text": "✏️ تعديل هيكل العقد", "callback_data": f"contract:for_emp:{summary.employee_id}"}],
                [{"text": "🔙 عُد لقائمة العقود", "callback_data": "menu:contract"}],
            ]
        }
        if message_id:
            bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
        else:
            bot.send_message(chat_id, text, reply_markup=kb)
    except Exception as exc:
        err_text = f"❌ <b>خطأ:</b> تعذر جلب بطاقة عقد الموظف #{employee_id}: <code>{exc}</code>"
        kb = {"inline_keyboard": [[{"text": "🔙 عُد لقائمة العقود", "callback_data": "menu:contract"}]]}
        if message_id:
            bot.edit_message_text(chat_id, message_id, err_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, err_text, reply_markup=kb)


def handle_contract_wizard_step(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    text: str,
    msg_id: Optional[int] = None,
) -> bool:
    wiz = ACTIVE_CONTRACT_WIZARDS.get(str(chat_id))
    if not wiz:
        return False

    clean_text = text.strip()
    mode = wiz.get("mode")

    if clean_text in ("إلغاء", "تراجع", "خروج", "cancel"):
        ACTIVE_CONTRACT_WIZARDS.pop(str(chat_id), None)
        show_contract_menu(bot, chat_id)
        return True

    if mode == "contract_emp":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "contract_act", "contract:cancel", msg_id)
        if not emp:
            return True
        emp_id = emp["id"]
        wiz["employee_id"] = emp_id
        wiz["mode"] = "contract_details"

        prompt_text = (
            f"👤 <b>هيكلة أجر وعقد الموظف #{emp_id}:</b>\n"
            f"────────────────────\n"
            f"أرسل الأجر الأساسي وبدل السكن وبدل النقل وتاريخ النهاية (لغير السعودي):\n\n"
            f"الصيغة: <code>[الأساسي] [بدل السكن] [بدل النقل] [تاريخ النهاية YYYY-MM-DD للوافد]</code>\n\n"
            f"أمثلة:\n"
            f"• <code>8000 2000 800</code> (للمواطن السعودي - عقد غير محدد)\n"
            f"• <code>6000 1500 600 2027-10-01</code> (للمقيم الوافد - محدد المدة م/37)\n"
            f"• <code>10000</code> (سيتم احتساب 25% سكن و 10% نقل تلقائياً)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "contract:cancel"}]]}
        bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb, reply_to_message_id=msg_id)
        return True

    elif mode == "contract_details":
        parts = clean_text.split()
        if not parts:
            bot.send_message(chat_id, "⚠️ يرجى إدخال الراتب الأساسي (مثال: 8000 2000 800):", reply_to_message_id=msg_id)
            return True

        try:
            basic_wage = float(parts[0])
        except ValueError:
            bot.send_message(chat_id, "⚠️ الراتب الأساسي يجب أن يكون رقماً صحيحاً (مثال: 8000):", reply_to_message_id=msg_id)
            return True

        housing = round(basic_wage * 0.25, 2)
        transport = round(basic_wage * 0.10, 2)
        date_end = None

        if len(parts) >= 2:
            try:
                housing = float(parts[1])
            except ValueError:
                date_end = parts[1]

        if len(parts) >= 3 and not date_end:
            try:
                transport = float(parts[2])
            except ValueError:
                date_end = parts[2]

        if len(parts) >= 4 and not date_end:
            date_end = parts[3]

        emp_id = wiz["employee_id"]
        service = get_contract_service_for_bot()
        dry_res = service.dry_run_contract(
            employee_id=emp_id,
            basic_wage=basic_wage,
            housing_allowance=housing,
            transportation_allowance=transport,
            date_end=date_end,
        )

        if not dry_res.is_valid:
            err_msg = "❌ <b>تعذر اعتماد هيكل العقد لمخالفة نظام العمل السعودي:</b>\n"
            for e in dry_res.errors:
                err_msg += f"  • {e}\n"
            bot.send_message(chat_id, err_msg, reply_to_message_id=msg_id)
            return True

        ACTIVE_CONTRACT_WIZARDS.pop(str(chat_id), None)
        token = dry_res.approval_token

        summary_text = (
            f"📊 <b>نتائج التدقيق الاستباقي المعتمد لعقد العمل:</b>\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {dry_res.employee_name} (#{dry_res.employee_id})\n"
            f"🇸🇦 <b>التصنيف:</b> <b>{dry_res.nationality_text_ar}</b>\n"
            f"📑 <b>نوع العقد:</b> {dry_res.contract_type_name}\n"
            f"💵 <b>الأساسي:</b> {dry_res.basic_wage:,.2f} ر.س | <b>السكن:</b> {dry_res.housing_allowance:,.2f} ر.س | <b>النقل:</b> {dry_res.transportation_allowance:,.2f} ر.س\n"
            f"💰 <b>إجمالي الباقة:</b> <b>{dry_res.total_package:,.2f} ر.س</b>\n"
            f"🏛️ <b>وعاء التأمينات (GOSI):</b> {dry_res.gosi_contributory_wage:,.2f} ر.س\n"
            f"📉 <b>استقطاع الموظف التأمينات:</b> {dry_res.gosi_employee_deduction:,.2f} ر.س\n"
            f"💵 <b>الصافي التقديري:</b> <b>{dry_res.net_estimated_salary:,.2f} ر.س</b>\n"
            f"⚖️ <b>المرجع النظامي:</b> {dry_res.statutory_article}\n"
            f"────────────────────\n"
        )
        if dry_res.warnings:
            summary_text += "⚠️ <b>تنبيهات الموارد البشرية ونطاقات:</b>\n"
            for w in dry_res.warnings:
                summary_text += f"  • {w}\n"
            summary_text += "────────────────────\n"

        summary_text += (
            f"🆔 <b>رمز الموافقة:</b> <code>{token}</code>\n"
            f"اضغط الزر أدناه ثم اكتب «تأكيد» للاعتماد النهائي في Odoo:"
        )

        kb = {
            "inline_keyboard": [
                [
                    {"text": "🚀 اعتماد وتحديث العقد في Odoo", "callback_data": f"contract_approve:{token}"},
                    {"text": "❌ تراجع", "callback_data": "contract:cancel"},
                ]
            ]
        }
        bot.send_message(chat_id, summary_text, reply_markup=kb, reply_to_message_id=msg_id)
        return True

    return False


def execute_contract_via_service(
    bot: TelegramBotClient,
    chat_id: int | str,
    token: str,
    msg_id: Optional[int] = None,
) -> None:
    service = get_contract_service_for_bot()
    bot.send_message(chat_id, "⏳ جارِ تحديث واعتماد عقد العمل في Odoo والتحقق المستقل...", reply_to_message_id=msg_id)
    try:
        res = service.apply_contract(approval_token=token, user_confirmation_text="تأكيد")
        if res.success:
            succ_text = (
                f"🎉 <b>تم اعتماد وتحديث عقد العمل بنجاح في Odoo!</b>\n"
                f"────────────────────\n"
                f"👤 <b>الموظف:</b> {res.employee_name} (#{res.employee_id})\n"
                f"💰 <b>إجمالي الباقة (Total):</b> <b>{res.total_package:,.2f} ر.س</b>\n"
                f"💵 <b>الصافي التقديري:</b> <b>{res.net_estimated_salary:,.2f} ر.س</b>\n"
                f"🔢 <b>رقم السجل في Odoo:</b> <code>#{res.contract_id}</code>\n"
                f"✅ <b>التحقق المستقل:</b> ناجح ومطابق (Readback Verified)\n"
                f"────────────────────\n"
                f"تم توثيق العملية بالكامل في سجل تدقيق العقود (logs/contract_audit_log.jsonl)."
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "📜 العودة لقائمة العقود", "callback_data": "menu:contract"}],
                    [{"text": "🔙 القائمة الرئيسية", "callback_data": "menu:main"}],
                ]
            }
            bot.send_message(chat_id, succ_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, f"❌ <b>فشل اعتماد العقد:</b> {res.message_ar}")
    except Exception as exc:
        bot.send_message(chat_id, f"❌ <b>خطأ أثناء التنفيذ:</b> <code>{exc}</code>")


# =============================================================================
# وظائف إدارة مسيرات الرواتب وحماية الأجور (Phase 19: Payroll & WPS)
# =============================================================================

_BOT_PAYROLL_SERVICE: Optional[PayrollService] = None

def get_payroll_service_for_bot(force_refresh: bool = False) -> PayrollService:
    global _BOT_PAYROLL_SERVICE
    if _BOT_PAYROLL_SERVICE is not None and not force_refresh:
        return _BOT_PAYROLL_SERVICE
    repo = OdooReadonlyRepository()
    gw = None
    try:
        gw = OdooPayrollWriteGateway(
            url=repo.url,
            db=repo.db,
            username=repo.username,
            password=repo.api_key,
        )
    except Exception:
        pass
    _BOT_PAYROLL_SERVICE = PayrollService(readonly_repo=repo, write_gateway=gw)
    return _BOT_PAYROLL_SERVICE


def show_payroll_menu(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "💵 <b>مسيرات الرواتب ونظام حماية الأجور (Payroll & WPS)</b> 🏢\n"
        "────────────────────\n"
        "أهلاً بك! يتيح لك هذا القسم تدقيق واحتساب مسيرات الرواتب (hr.payslip) والتأكد من مطابقتها لنظام العمل ونظام حماية الأجور:\n\n"
        "• <b>التأمينات الاجتماعية GOSI:</b>\n"
        "  - المواطن: استقطاع 9.75% من وعاء الراتب (الأساسي + السكن).\n"
        "  - المقيم: 0% استقطاع على الموظف (2% أخطار على صاحب العمل).\n"
        "• <b>سقف الاستقطاعات القانوني:</b>\n"
        "  - سلف الموظفين: سقف 25% شهرياً (المادة 92).\n"
        "  - الخصومات والجزاءات: سقف 5 أيام شهرياً (المادة 71).\n"
        "  - السقف التراكمي: حظر تجاوز الاستقطاعات لسقف 50% من إجمالي الراتب.\n"
        "• <b>ملف حماية الأجور (WPS SIF):</b> جاهزية توليد الملف البنكي لمنصة مدد وبوابات الصرف.\n"
        "• <b>التحقق المزدوج:</b> اشتراط كلمة «تأكيد» والتحقق المستقل بعد الإنشاء."
    )
    kb = {
        "inline_keyboard": [
            [
                {"text": "➕ تدقيق وإنشاء قسيمة راتب", "callback_data": "payroll:prompt"},
                {"text": "📜 دليل حماية الأجور والاستقطاعات", "callback_data": "payroll:laws_guide"},
            ],
            [
                {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_payroll_laws_guide(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "📜 <b>الدليل النظامي لمسيرات الرواتب وحماية الأجور (WPS & SAMA):</b>\n"
        "────────────────────\n"
        "💰 <b>1. التزامات نظام حماية الأجور (WPS):</b>\n"
        "  • إلزامية تحويل الأجور عبر الحسابات البنكية أو المحافظ الرقمية المعتمدة.\n"
        "  • صرف الراتب في موعد الاستحقاق خلال مهلة لا تتجاوز 10 أيام من نهايته.\n"
        "  • نسبة التزام المنشأة يجب ألا تقل عن 80% لتفادي إيقاف الخدمات.\n\n"
        "⚖️ <b>2. ضوابط الاستقطاع من أجر العامل (المادة 92):</b>\n"
        "  • لا يجوز حسم أكثر من 25% من أجر العامل وفاءً لسلف أو قروض صاحب العمل.\n"
        "  • لا يجوز في جميع الأحوال أن تزيد نسبة المبالغ المحسومة على نصف أجر العامل (50%) إلا بقرار قضائي.\n\n"
        "🛡️ <b>3. الجزاءات التأديبية (المادتان 70 و 71):</b>\n"
        "  • أقصى غرامة على المخالفة الواحدة أجر 5 أيام.\n"
        "  • أقصى اقتطاع للجزاءات في الشهر الواحد أجر 5 أيام.\n\n"
        "🏛️ <b>4. اشتراكات التأمينات الاجتماعية (GOSI):</b>\n"
        "  • 9.75% للموظف السعودي من وعاء (الأساسي + بدل السكن) بسقف 45,000 ر.س.\n"
        "  • 0% استقطاع على الموظف غير السعودي."
    )
    kb = {
        "inline_keyboard": [
            [{"text": "➕ تدقيق قسيمة راتب", "callback_data": "payroll:prompt"}],
            [{"text": "🔙 عُد لقائمة الرواتب", "callback_data": "menu:payroll"}],
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_employee_payslip_card(
    bot: TelegramBotClient,
    chat_id: int | str,
    employee_id: int,
    message_id: Optional[int] = None
) -> None:
    service = get_payroll_service_for_bot()
    try:
        summary = service.get_employee_payslip_summary(employee_id)
        text = (
            f"💵 <b>بطاقة مسير الراتب والاستقطاعات</b> 🏢\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {summary.employee_name} (#{summary.employee_id})\n"
            f"💼 <b>الوظيفة:</b> {summary.job_title} | <b>القسم:</b> {summary.department_name}\n"
            f"🇸🇦 <b>التصنيف:</b> <b>{summary.nationality_text_ar}</b>\n"
            f"📅 <b>الفترة:</b> <code>{summary.date_from}</code> إلى <code>{summary.date_to}</code>\n"
            f"────────────────────\n"
            f"💵 <b>الأجر الأساسي:</b> {summary.basic_wage:,.2f} ر.س\n"
            f"🏠 <b>بدل السكن:</b> {summary.housing_allowance:,.2f} ر.س\n"
            f"🚗 <b>بدل النقل:</b> {summary.transportation_allowance:,.2f} ر.س\n"
            f"💰 <b>إجمالي الراتب (Gross):</b> <b>{summary.gross_wage:,.2f} ر.س</b>\n"
            f"────────────────────\n"
            f"📉 <b>استقطاع التأمينات (GOSI):</b> {summary.gosi_employee_deduction:,.2f} ر.س\n"
        )
        if summary.loan_deduction > 0:
            text += f"💳 <b>قسط سلفة الموظف:</b> {summary.loan_deduction:,.2f} ر.س\n"
        if summary.discipline_deduction > 0:
            text += f"⚖️ <b>خصومات انضباطية:</b> {summary.discipline_deduction:,.2f} ر.س\n"

        text += (
            f"📊 <b>إجمالي الاستقطاعات:</b> {summary.total_deductions:,.2f} ر.س\n"
            f"💵 <b>صافي الراتب المستحق:</b> <b>{summary.net_wage:,.2f} ر.س</b>\n"
            f"────────────────────\n"
        )
        if summary.compliance_notes:
            text += "⚠️ <b>ملاحظات الامتثال:</b>\n"
            for note in summary.compliance_notes:
                text += f"  • {note}\n"
            text += "────────────────────\n"

        kb = {
            "inline_keyboard": [
                [{"text": "➕ تدقيق قسيمة جديدة", "callback_data": f"payroll:for_emp:{summary.employee_id}"}],
                [{"text": "🔙 عُد لقائمة الرواتب", "callback_data": "menu:payroll"}],
            ]
        }
        if message_id:
            bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
        else:
            bot.send_message(chat_id, text, reply_markup=kb)
    except Exception as exc:
        err_text = f"❌ <b>خطأ:</b> تعذر جلب قسيمة راتب الموظف #{employee_id}: <code>{exc}</code>"
        kb = {"inline_keyboard": [[{"text": "🔙 عُد لقائمة الرواتب", "callback_data": "menu:payroll"}]]}
        if message_id:
            bot.edit_message_text(chat_id, message_id, err_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, err_text, reply_markup=kb)


def handle_payroll_wizard_step(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    text: str,
    msg_id: Optional[int] = None,
) -> bool:
    wiz = ACTIVE_PAYROLL_WIZARDS.get(str(chat_id))
    if not wiz:
        return False

    clean_text = text.strip()
    mode = wiz.get("mode")

    if clean_text in ("إلغاء", "تراجع", "خروج", "cancel"):
        ACTIVE_PAYROLL_WIZARDS.pop(str(chat_id), None)
        show_payroll_menu(bot, chat_id)
        return True

    if mode == "payroll_emp":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "payroll_act", "payroll:cancel", msg_id)
        if not emp:
            return True
        emp_id = emp["id"]
        wiz["employee_id"] = emp_id
        wiz["mode"] = "payroll_details"

        prompt_text = (
            f"👤 <b>احتساب مسير راتب الموظف #{emp_id}:</b>\n"
            f"────────────────────\n"
            f"أرسل قسط السلفة (إن وجد) وقيمة الخصم التأديبي (إن وجد) مفصولة بمسافة:\n\n"
            f"الصيغة: <code>[قسط السلفة] [الخصم التأديبي]</code>\n\n"
            f"أمثلة:\n"
            f"• <code>0 0</code> (الراتب المعتاد بدون استقطاعات)\n"
            f"• <code>1000 0</code> (خصم قسط سلفة 1000 ر.س)\n"
            f"• <code>500 200</code> (قسط سلفة 500 وخصم تأديبي 200)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "payroll:cancel"}]]}
        bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb, reply_to_message_id=msg_id)
        return True

    elif mode == "payroll_details":
        parts = clean_text.split()
        loan_val = 0.0
        disc_val = 0.0

        if len(parts) >= 1:
            try:
                loan_val = float(parts[0])
            except ValueError:
                loan_val = 0.0

        if len(parts) >= 2:
            try:
                disc_val = float(parts[1])
            except ValueError:
                disc_val = 0.0

        emp_id = wiz["employee_id"]
        service = get_payroll_service_for_bot()
        dry_res = service.dry_run_payslip(
            employee_id=emp_id,
            loan_installment=loan_val,
            discipline_amount=disc_val,
        )

        if not dry_res.is_valid:
            err_msg = "❌ <b>تعذر اعتماد قسيمة الراتب لمخالفة سقف الاستقطاعات:</b>\n"
            for e in dry_res.errors:
                err_msg += f"  • {e}\n"
            bot.send_message(chat_id, err_msg, reply_to_message_id=msg_id)
            return True

        ACTIVE_PAYROLL_WIZARDS.pop(str(chat_id), None)
        token = dry_res.approval_token

        summary_text = (
            f"📊 <b>نتائج التدقيق الاستباقي المعتمد لمسير الراتب:</b>\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {dry_res.employee_name} (#{dry_res.employee_id})\n"
            f"🇸🇦 <b>التصنيف:</b> <b>{dry_res.nationality_text_ar}</b>\n"
            f"💰 <b>إجمالي الراتب (Gross):</b> <b>{dry_res.gross_wage:,.2f} ر.س</b>\n"
            f"🏛️ <b>وعاء التأمينات (GOSI):</b> {dry_res.gosi_contributory_wage:,.2f} ر.س\n"
            f"📉 <b>استقطاع التأمينات:</b> {dry_res.gosi_employee_deduction:,.2f} ر.س\n"
            f"💳 <b>قسط السلفة:</b> {dry_res.loan_installment:,.2f} ر.س\n"
            f"⚖️ <b>الجزاءات:</b> {dry_res.discipline_deduction:,.2f} ر.س\n"
            f"📊 <b>إجمالي الاستقطاعات:</b> {dry_res.total_deductions:,.2f} ر.س ({dry_res.deduction_pct_of_gross}%)\n"
            f"💵 <b>صافي الراتب المستحق:</b> <b>{dry_res.net_wage:,.2f} ر.س</b>\n"
            f"⚖️ <b>المرجع النظامي:</b> {dry_res.statutory_article}\n"
            f"────────────────────\n"
        )
        if dry_res.warnings:
            summary_text += "⚠️ <b>تنبيهات وملاحظات الرواتب:</b>\n"
            for w in dry_res.warnings:
                summary_text += f"  • {w}\n"
            summary_text += "────────────────────\n"

        summary_text += (
            f"🆔 <b>رمز الموافقة:</b> <code>{token}</code>\n"
            f"اضغط الزر أدناه ثم اكتب «تأكيد» للاعتماد النهائي في Odoo:"
        )

        kb = {
            "inline_keyboard": [
                [
                    {"text": "🚀 إنشاء واعتماد قسيمة الراتب في Odoo", "callback_data": f"payroll_approve:{token}"},
                    {"text": "❌ تراجع", "callback_data": "payroll:cancel"},
                ]
            ]
        }
        bot.send_message(chat_id, summary_text, reply_markup=kb, reply_to_message_id=msg_id)
        return True

    return False


def execute_payslip_via_service(
    bot: TelegramBotClient,
    chat_id: int | str,
    token: str,
    msg_id: Optional[int] = None,
) -> None:
    service = get_payroll_service_for_bot()
    bot.send_message(chat_id, "⏳ جارِ إنشاء واعتماد قسيمة الراتب في Odoo والتحقق المستقل...", reply_to_message_id=msg_id)
    try:
        res = service.apply_payslip(approval_token=token, user_confirmation_text="تأكيد")
        if res.success:
            succ_text = (
                f"🎉 <b>تم إنشاء واعتماد قسيمة الراتب بنجاح في Odoo!</b>\n"
                f"────────────────────\n"
                f"👤 <b>الموظف:</b> {res.employee_name} (#{res.employee_id})\n"
                f"💰 <b>إجمالي الراتب (Gross):</b> <b>{res.gross_wage:,.2f} ر.س</b>\n"
                f"💵 <b>صافي الراتب المستحق:</b> <b>{res.net_wage:,.2f} ر.س</b>\n"
                f"🔢 <b>رقم السجل في Odoo:</b> <code>#{res.payslip_id}</code>\n"
                f"✅ <b>التحقق المستقل:</b> ناجح ومطابق (Readback Verified)\n"
                f"────────────────────\n"
                f"تم توثيق العملية بالكامل في سجل تدقيق الرواتب (logs/payroll_audit_log.jsonl)."
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "💵 العودة لقائمة الرواتب", "callback_data": "menu:payroll"}],
                    [{"text": "🔙 القائمة الرئيسية", "callback_data": "menu:main"}],
                ]
            }
            bot.send_message(chat_id, succ_text, reply_markup=kb)
        else:
            bot.send_message(chat_id, f"❌ <b>فشل إنشاء قسيمة الراتب:</b> {res.message_ar}")
    except Exception as exc:
        bot.send_message(chat_id, f"❌ <b>خطأ أثناء التنفيذ:</b> <code>{exc}</code>")


# =============================================================================
# وظائف التحليلات والمؤشرات التنفيذية (Phase 20: Analytics & Executive Dashboard)
# =============================================================================

_BOT_ANALYTICS_SERVICE: Optional[AnalyticsService] = None

def get_analytics_service_for_bot(force_refresh: bool = False) -> AnalyticsService:
    global _BOT_ANALYTICS_SERVICE
    if _BOT_ANALYTICS_SERVICE is not None and not force_refresh:
        return _BOT_ANALYTICS_SERVICE
    repo = OdooReadonlyRepository()
    _BOT_ANALYTICS_SERVICE = AnalyticsService(readonly_repo=repo)
    return _BOT_ANALYTICS_SERVICE


def show_analytics_menu(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    service = get_analytics_service_for_bot()
    try:
        dash = service.get_unified_dashboard()
        wf = dash.workforce
        comp = dash.compliance
        text = (
            "📊 <b>لوحة المؤشرات والتحليلات التنفيذية الشاملة</b> 🏢\n"
            "────────────────────\n"
            f"👤 <b>إجمالي القوى العاملة:</b> {wf.total_employees} موظفاً\n"
            f"🇸🇦 <b>المواطنون:</b> {wf.saudi_count} | 🌍 <b>المقيمون:</b> {wf.non_saudi_count}\n"
            f"📈 <b>نسبة التوطين الحالية:</b> <b>{wf.saudization_rate_pct}%</b>\n"
            f"🏷️ <b>نطاق المنشأة:</b> <b>{wf.nitaqat_band_name}</b>\n"
            f"🛡️ <b>مؤشر الامتثال النظامي:</b> <b>{comp.health_score}/100</b> ({comp.rating_label_ar})\n"
            "────────────────────\n"
            "اختر التقرير التفصيلي أو استخدم محاكي التوطين الذكي:"
        )
    except Exception as exc:
        text = (
            "📊 <b>لوحة المؤشرات والتحليلات التنفيذية</b> 🏢\n"
            "────────────────────\n"
            f"⚠️ تعذر جلب البيانات الحية من Odoo: <code>{exc}</code>\n"
            "اختر القسم المطلوب للاستعلام المباشر:"
        )

    kb = {
        "inline_keyboard": [
            [
                {"text": "📊 نظرة عامة شاملة", "callback_data": "analytics:overview"},
                {"text": "🇸🇦 التوطين ونطاقات", "callback_data": "analytics:saudization"},
            ],
            [
                {"text": "💰 الالتزامات والرواتب", "callback_data": "analytics:financial"},
                {"text": "🛡️ مؤشر الامتثال والمخاطر", "callback_data": "analytics:compliance"},
            ],
            [
                {"text": "🎯 محاكي التوطين ونطاقات", "callback_data": "analytics:simulator_prompt"},
            ],
            [
                {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_analytics_overview_card(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    service = get_analytics_service_for_bot()
    try:
        dash = service.get_unified_dashboard()
        wf = dash.workforce
        ops = dash.operations
        fin = dash.financial
        comp = dash.compliance
        rec = dash.recruitment

        text = (
            "📊 <b>التقرير التنفيذي الشامل (Executive Summary)</b> 🏢\n"
            "────────────────────\n"
            f"👥 <b>القوى العاملة والتوطين:</b>\n"
            f"  • الإجمالي: {wf.total_employees} موظفاً (🇸🇦 {wf.saudi_count} مواطناً / 🌍 {wf.non_saudi_count} مقيماً)\n"
            f"  • نسبة التوطين: <b>{wf.saudization_rate_pct}%</b> | {wf.nitaqat_band_name}\n\n"
            f"⚙️ <b>العمليات التشغيلية والدوام:</b>\n"
            f"  • إجازات معلقة: {ops.pending_leaves_count} | معتمدة: {ops.approved_leaves_count}\n"
            f"  • حضور اليوم: {ops.today_checkins_count} | متواجدون الآن: {ops.currently_active_checkins_count}\n"
            f"  • ساعات العمل الإضافي: {ops.total_monthly_overtime_hours:,.1f} ساعة\n\n"
            f"💰 <b>المالية ومسيرات الرواتب:</b>\n"
            f"  • إجمالي المسير التقديري: {fin.estimated_monthly_gross_payroll:,.2f} ر.س\n"
            f"  • رصيد السلف النشطة: {fin.total_active_loans_balance:,.2f} ر.س ({fin.active_loans_count} سلفة)\n"
            f"  • اشتراكات التأمينات (GOSI): صاحب العمل {fin.estimated_monthly_gosi_employer_cost:,.2f} ر.س\n\n"
            f"🛡️ <b>الامتثال والمخاطر:</b> {comp.health_score}/100 ({comp.rating_label_ar})\n"
            f"  • إقامات تنتهي خلال شهر: {comp.expiring_iqamas_30d}\n"
            f"  • تحقيقات معلقة (م/72): {comp.pending_disciplinary_count}\n"
            f"  • فترات تجربة سارية (م/53): {comp.active_probation_count}\n\n"
            f"🎯 <b>التوظيف:</b> {rec.open_jobs_count} شواغر | {rec.total_applicants_count} متقدماً\n"
            "────────────────────\n"
            f"<i>تم التحديث: {dash.generated_at_ar}</i>"
        )
    except Exception as exc:
        text = f"❌ <b>خطأ أثناء استخراج التقرير الشامل:</b> <code>{exc}</code>"

    kb = {
        "inline_keyboard": [
            [{"text": "🎯 محاكي التوطين", "callback_data": "analytics:simulator_prompt"}],
            [{"text": "🔙 عُد لقائمة التحليلات", "callback_data": "menu:analytics"}],
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_analytics_saudization_card(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    service = get_analytics_service_for_bot()
    try:
        wf = service.get_workforce_kpis()
        text = (
            "🇸🇦 <b>تقرير التوطين ونطاقات الدقيق</b> 🏢\n"
            "────────────────────\n"
            f"👥 <b>إجمالي العاملين:</b> {wf.total_employees} موظفاً\n"
            f"🇸🇦 <b>المواطنون السعوديون:</b> {wf.saudi_count} موظفاً\n"
            f"🌍 <b>المقيمون الأجانب:</b> {wf.non_saudi_count} موظفاً\n"
            f"📊 <b>نسبة التوطين الحالية:</b> <b>{wf.saudization_rate_pct}%</b>\n\n"
            f"🏷️ <b>نطاق المنشأة في الوزارة:</b>\n"
            f"  <b>{wf.nitaqat_band_name}</b>\n"
            f"  <i>{wf.nitaqat_status_ar}</i>\n\n"
            f"⚧️ <b>التوزيع حسب الجنس:</b>\n"
            f"  • ذكور: {wf.male_count} | إناث: {wf.female_count}\n"
            "────────────────────\n"
            "🏢 <b>أكبر الأقسام عدداً:</b>\n"
        )
        for dept in wf.top_departments:
            text += f"  • {dept['department']}: {dept['count']} موظفاً\n"
    except Exception as exc:
        text = f"❌ <b>خطأ أثناء استخراج بيانات التوطين:</b> <code>{exc}</code>"

    kb = {
        "inline_keyboard": [
            [{"text": "🎯 جرب محاكي التوطين", "callback_data": "analytics:simulator_prompt"}],
            [{"text": "🔙 عُد لقائمة التحليلات", "callback_data": "menu:analytics"}],
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_analytics_financial_card(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    service = get_analytics_service_for_bot()
    try:
        fin = service.get_financial_kpis()
        text = (
            "💰 <b>تقرير الالتزامات المالية ومسيرات الرواتب</b> 🏢\n"
            "────────────────────\n"
            f"💵 <b>المسير الشهري الإجمالي التقديري:</b>\n"
            f"  <b>{fin.estimated_monthly_gross_payroll:,.2f} ر.س</b>\n\n"
            f"🏛️ <b>اشتراكات التأمينات الاجتماعية (GOSI):</b>\n"
            f"  • التزام المنشأة (صاحب العمل): {fin.estimated_monthly_gosi_employer_cost:,.2f} ر.س\n"
            f"  • استقطاع الموظفين السعوديين (9.75%): {fin.estimated_monthly_gosi_employee_deductions:,.2f} ر.س\n\n"
            f"💳 <b>محفظة سلف وقروض الموظفين:</b>\n"
            f"  • إجمالي الرصيد القائم: {fin.total_active_loans_balance:,.2f} ر.س\n"
            f"  • عدد السلف النشطة: {fin.active_loans_count}\n"
            f"  • قسط الاسترداد الشهري: {fin.monthly_loan_recovery_run:,.2f} ر.س\n\n"
            f"💼 <b>مخصصات ومكافآت نهاية الخدمة (EOSB):</b>\n"
            f"  • إجمالي التسويات المعتمدة والمدفوعة: {fin.total_eosb_settled_amount:,.2f} ر.س\n"
            "────────────────────\n"
            "✅ متوافق مع نظام حماية الأجور ومحددات المادة 92."
        )
    except Exception as exc:
        text = f"❌ <b>خطأ أثناء استخراج البيانات المالية:</b> <code>{exc}</code>"

    kb = {
        "inline_keyboard": [
            [{"text": "💵 مسير الرواتب و WPS", "callback_data": "menu:payroll"}],
            [{"text": "🔙 عُد لقائمة التحليلات", "callback_data": "menu:analytics"}],
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_analytics_compliance_card(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    service = get_analytics_service_for_bot()
    try:
        comp = service.get_compliance_kpis()
        text = (
            f"🛡️ <b>مؤشر الامتثال النظامي ومخاطر العمل:</b> <b>{comp.health_score}/100</b>\n"
            f"<b>التقييم:</b> {comp.rating_label_ar}\n"
            "────────────────────\n"
            f"⏰ <b>الإقامات ورخص العمل والتأشيرات:</b>\n"
            f"  • تنتهي خلال 30 يوماً: <b>{comp.expiring_iqamas_30d}</b>\n"
            f"  • تنتهي خلال 60 يوماً: {comp.expiring_iqamas_60d}\n"
            f"  • تنتهي خلال 90 يوماً: {comp.expiring_iqamas_90d}\n\n"
            f"⚖️ <b>التحقيقات والجزاءات العالقة (المادة 72):</b> {comp.pending_disciplinary_count}\n"
            f"⏳ <b>فترات التجربة السارية (المادة 53):</b> {comp.active_probation_count}\n"
            "────────────────────\n"
            "⚠️ <b>التنبيهات والملاحظات النظامية:</b>\n"
        )
        for a in comp.compliance_alerts:
            text += f"  • {a}\n"

        text += "\n💡 <b>التوصيات المباشرة:</b>\n"
        for r in comp.actionable_recommendations_ar:
            text += f"  • {r}\n"
    except Exception as exc:
        text = f"❌ <b>خطأ أثناء استخراج مؤشرات الامتثال:</b> <code>{exc}</code>"

    kb = {
        "inline_keyboard": [
            [{"text": "🏛️ إدارة المعاملات الحكومية", "callback_data": "menu:gr"}],
            [{"text": "🔙 عُد لقائمة التحليلات", "callback_data": "menu:analytics"}],
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def handle_analytics_wizard_step(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    text: str,
    msg_id: Optional[int] = None,
) -> bool:
    wiz = ACTIVE_ANALYTICS_WIZARDS.get(str(chat_id))
    if not wiz:
        return False

    clean_text = text.strip()
    if clean_text in ("إلغاء", "تراجع", "خروج", "cancel"):
        ACTIVE_ANALYTICS_WIZARDS.pop(str(chat_id), None)
        show_analytics_menu(bot, chat_id)
        return True

    # Expect: [saudi_hires] [expat_hires]
    parts = clean_text.split()
    if len(parts) >= 2:
        try:
            s_hires = int(parts[0])
            e_hires = int(parts[1])
        except ValueError:
            bot.send_message(
                chat_id,
                "⚠️ يرجى إدخال أرقام صحيحة لعدد التعيينات: <code>[سعودي] [أجنبي]</code> (مثال: <code>2 1</code>)",
                reply_to_message_id=msg_id,
            )
            return True

        ACTIVE_ANALYTICS_WIZARDS.pop(str(chat_id), None)
        service = get_analytics_service_for_bot()
        try:
            res = service.simulate_saudization_impact(saudi_hires=s_hires, expat_hires=e_hires)
            res_text = (
                "🎯 <b>نتائج محاكي التوطين وبرنامج نطاقات</b> 🏢\n"
                "────────────────────\n"
                f"📥 <b>التعيينات المقترحة:</b> {s_hires} سعودي | {e_hires} وافد\n"
                "────────────────────\n"
                f"👥 <b>الوضع الحالي:</b>\n"
                f"  • القوى العاملة: {res.current_employees} موظفاً (🇸🇦 {res.current_saudi})\n"
                f"  • نسبة التوطين: <b>{res.current_rate_pct}%</b>\n"
                f"  • النطاق: <b>{res.current_band}</b>\n\n"
                f"🚀 <b>الوضع التقديري بعد التعيين:</b>\n"
                f"  • القوى العاملة: {res.simulated_employees} موظفاً (🇸🇦 {res.simulated_saudi})\n"
                f"  • نسبة التوطين المتوقعة: <b>{res.simulated_rate_pct}%</b>\n"
                f"  • النطاق المتوقع: <b>{res.simulated_band}</b>\n\n"
                f"📊 <b>الأثر النظامي:</b>\n"
                f"  {res.status_change_ar}\n\n"
                f"💡 <b>التوجيه القانوني:</b>\n"
                f"  {res.legal_advice_ar}\n"
                "────────────────────\n"
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "🔄 محاكاة أخرى", "callback_data": "analytics:simulator_prompt"}],
                    [{"text": "🔙 عُد لقائمة التحليلات", "callback_data": "menu:analytics"}],
                ]
            }
            bot.send_message(chat_id, res_text, reply_markup=kb, reply_to_message_id=msg_id)
            return True
        except Exception as exc:
            bot.send_message(chat_id, f"❌ خطأ أثناء المحاكاة: <code>{exc}</code>", reply_to_message_id=msg_id)
            return True

    bot.send_message(
        chat_id,
        "⚠️ يرجى إدخال عدد التعيينات مفصولة بمسافة: <code>[عدد السعوديين] [عدد غير السعوديين]</code> (مثال: <code>3 1</code>)",
        reply_to_message_id=msg_id,
    )
    return True


def send_sijil_audit_pdf(bot: TelegramBotClient, chat_id: int | str, msg_id: Optional[int] = None) -> None:
    """Generates and delivers the executive audit PDF report compiled by agent Sijil."""
    bot.send_message(
        chat_id,
        "⏳ <b>جارِ استخراج سجلات الحوكمة وتوليد تقرير التدقيق الرقابي بصيغة PDF عبر الوكيل «سجل»...</b>",
        reply_to_message_id=msg_id,
    )
    try:
        from sijil_audit_service import SijilAuditService
        service = SijilAuditService()
        pdf_path_str, pdf_bytes = service.generate_pdf_report()
        summary = service.compile_audit_summary()

        caption = (
            f"🛡️ <b>تقرير الرقابة والتدقيق وسجل العمليات — الوكيل «سجل»</b>\n"
            f"────────────────────\n"
            f"• <b>معدل التحقق بعد القراءة:</b> <code>{summary['readback_rate']}%</code> (مطابقة تامة)\n"
            f"• <b>اعتمادات التحقق المزدوج:</b> <code>{summary['four_eyes_tokens_count']}</code> اعتماد\n"
            f"• <b>إجمالي العمليات الموثقة:</b> <code>{summary['total_events']}</code> عملية\n"
            f"• <b>العمليات المحظورة أمنياً:</b> <code>{summary['blocked_actions']}</code> عملية\n"
            f"• <b>بصمة التقرير:</b> <code>{summary['report_digest']}</code>\n\n"
            f"<i>تم التصميم بالمعايير التنفيذية (Resend Black Velvet & Supabase Midnight).</i>"
        )
        bot.send_document(chat_id, Path(pdf_path_str), caption=caption)
    except Exception as exc:
        bot.send_message(
            chat_id,
            f"❌ <b>فشل توليد تقرير PDF:</b> <code>{exc}</code>",
            reply_to_message_id=msg_id,
        )


_BOT_LETTER_SERVICE: Optional[LetterService] = None

def get_letter_service_for_bot(force_refresh: bool = False) -> LetterService:
    global _BOT_LETTER_SERVICE
    if _BOT_LETTER_SERVICE is not None and not force_refresh:
        return _BOT_LETTER_SERVICE
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        api_key=cfg.get("api_key") or cfg.get("password"),
    )
    gw = OdooLetterWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("api_key") or cfg.get("password"),
    )
    _BOT_LETTER_SERVICE = LetterService(repo=repo, gateway=gw)
    return _BOT_LETTER_SERVICE


def show_letter_menu(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "📜 <b>إصدار الخطابات الرسمية وشهادات الرواتب (Official Letters)</b> 🏢\n"
        "────────────────────\n"
        "أهلاً بك! يتيح لك هذا القسم إعداد وإصدار الخطابات الإدارية وشهادات التعريف المعتمدة:\n\n"
        "• <b>شهادة تعريف بالراتب:</b> تفصيل الأجر الأساسي وبدل السكن وبدل النقل والبدلات الأخرى.\n"
        "• <b>شهادة إثبات عمل:</b> تأكيد الاستمرار على رأس العمل دون الإفصاح عن الراتب.\n"
        "• <b>خطاب مصرفي:</b> موجه للبنوك لفتح الحسابات أو طلبات التمويل والقروض.\n"
        "• <b>خطاب للسفارات والقنصليات:</b> لاستخراج تأشيرات السفر والسياحة.\n"
        "• <b>خطاب للغرفة التجارية:</b> جاهز للتصديق الإلكتروني الرسمي.\n"
        "• <b>التكامل المباشر:</b> حفظ الطلب في Odoo (approval.request) مع التحقق المستقل.\n"
        "• <b>مستند PDF رسمي:</b> يتضمن رمز التحقق الرقمي والختم المؤسسي المعتمد."
    )
    kb = {
        "inline_keyboard": [
            [
                {"text": "💵 شهادة تعريف بالراتب والبدلات", "callback_data": "letter:type:salary_certificate"},
            ],
            [
                {"text": "📋 شهادة إثبات عمل (بدون راتب)", "callback_data": "letter:type:employment_certificate"},
            ],
            [
                {"text": "🏦 خطاب موجه للمصرف / البنك", "callback_data": "letter:type:bank_letter"},
                {"text": "✈️ خطاب موجه للسفارة / تأشيرة", "callback_data": "letter:type:embassy_letter"},
            ],
            [
                {"text": "🏛️ خطاب مصدق للغرفة التجارية", "callback_data": "letter:type:chamber_certified"},
            ],
            [
                {"text": "🔍 استعلام خطابات موظف سابقاً", "callback_data": "letter:query_prompt"},
            ],
            [
                {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def start_letter_wizard(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    letter_type: str,
    message_id: Optional[int] = None,
) -> None:
    meta = SUPPORTED_LETTER_TYPES.get(letter_type, {})
    title = meta.get("title_ar", "خطاب رسمي")
    ACTIVE_LETTER_WIZARDS[str(chat_id)] = {
        "step": "emp_id",
        "letter_type": letter_type,
        "user_id": str(user_id),
    }
    prompt = (
        f"📝 <b>إعداد {title}</b>\n"
        f"────────────────────\n"
        f"<b>الخطوة 1 من 2:</b> أرسل <b>رقم معرّف الموظف (ID)</b> في Odoo:\n"
        f"(مثال: <code>100</code> أو <code>15</code>)"
    )
    cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "letter:cancel"}]]}
    if message_id:
        bot.edit_message_text(chat_id, message_id, prompt, reply_markup=cancel_kb)
    else:
        bot.send_message(chat_id, prompt, reply_markup=cancel_kb)


def handle_letter_wizard_step(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    text: str,
    msg_id: Optional[int] = None,
) -> bool:
    wiz = ACTIVE_LETTER_WIZARDS.get(str(chat_id))
    if not wiz:
        return False

    step = wiz.get("step")
    clean_text = text.strip()

    if clean_text in ("/cancel", "الغاء", "إلغاء", "تراجع"):
        ACTIVE_LETTER_WIZARDS.pop(str(chat_id), None)
        bot.send_message(chat_id, "❌ تم إلغاء معالج الخطابات.", reply_to_message_id=msg_id)
        show_letter_menu(bot, chat_id)
        return True

    if step == "query_emp_id":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "letter_query", "menu:letters", msg_id)
        if not emp:
            return True
        emp_id = emp["id"]
        ACTIVE_LETTER_WIZARDS.pop(str(chat_id), None)

        cfg = get_active_odoo_config()
        repo = OdooReadonlyRepository(
            url=cfg.get("url"), db=cfg.get("db"), username=cfg.get("username"), api_key=cfg.get("api_key") or cfg.get("password")
        )
        letters = repo.get_employee_approval_requests(emp_id)
        if not letters:
            bot.send_message(chat_id, f"ℹ️ لا توجد خطابات أو طلبات موافقة مسجلة للموظف #{emp_id}.", reply_to_message_id=msg_id)
            return True

        res_text = f"📋 <b>سجل الخطابات والموافقات الصادرة للموظف #{emp_id}:</b>\n────────────────────\n"
        for idx, l in enumerate(letters[:10], 1):
            st = l.get("request_status") or "غير محدد"
            res_text += f"{idx}. <b>{l.get('name') or 'طلب'}</b>\n   • الحالة: <code>{st}</code> | الجهة: <code>{l.get('to') or '—'}</code>\n   • التاريخ: <code>{str(l.get('create_date') or l.get('date'))[:10]}</code>\n\n"
        bot.send_message(chat_id, res_text, reply_to_message_id=msg_id)
        return True

    if step == "emp_id":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "letter_issue", "letter:cancel", msg_id)
        if not emp:
            return True
        emp_id = emp["id"]
        wiz["employee_id"] = emp_id
        wiz["step"] = "recipient"
        meta = SUPPORTED_LETTER_TYPES.get(wiz["letter_type"], {})
        default_to = meta.get("default_to", "إلى من يهمه الأمر")
        prompt = (
            f"🎯 <b>الخطوة 2 من 2: تحديد الجهة الموجه إليها الخطاب</b>\n"
            f"────────────────────\n"
            f"أرسل اسم الجهة أو البنك أو السفارة الموجه لها الخطاب:\n"
            f"(أو أرسل <b>.</b> لاستخدام الافتراضي: <code>{default_to}</code>)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "letter:cancel"}]]}
        bot.send_message(chat_id, prompt, reply_markup=cancel_kb, reply_to_message_id=msg_id)
        return True

    if step == "recipient":
        meta = SUPPORTED_LETTER_TYPES.get(wiz["letter_type"], {})
        recipient = meta.get("default_to", "إلى من يهمه الأمر") if clean_text == "." else clean_text
        wiz["recipient"] = recipient

        ACTIVE_LETTER_WIZARDS.pop(str(chat_id), None)
        bot.send_message(chat_id, "⏳ <b>جارِ فحص بيانات الموظف والعقد وتجهيز المسودة للمعاينة (Dry-Run)...</b>", reply_to_message_id=msg_id)

        service = get_letter_service_for_bot()
        dry_run = service.dry_run_letter(
            employee_id=wiz["employee_id"],
            letter_type=wiz["letter_type"],
            recipient=recipient,
            chamber_of_commerce_stamp=(wiz["letter_type"] == "chamber_certified"),
        )

        if not dry_run.is_valid:
            bot.send_message(
                chat_id,
                f"❌ <b>تعذر إنشاء الخطاب:</b>\n" + "\n".join(f"• {e}" for e in dry_run.errors),
                reply_to_message_id=msg_id,
            )
            return True

        summary_text = (
            f"📄 <b>معاينة الخطاب الرسمي قبل الاعتماد (Dry-Run Preview)</b> ⚖️\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {dry_run.employee_name} (#{dry_run.employee_id})\n"
            f"🇸🇦 <b>الجنسية:</b> {dry_run.nationality_text_ar}\n"
            f"🆔 <b>الهوية/الإقامة:</b> <code>{dry_run.identification_id or '—'}</code>\n"
            f"💼 <b>المسمى الوظيفي:</b> {dry_run.job_title}\n"
            f"🏢 <b>القسم:</b> {dry_run.department_name}\n"
            f"🏛️ <b>الجهة الموجه إليها:</b> {dry_run.recipient}\n"
        )
        if dry_run.include_salary:
            summary_text += (
                f"────────────────────\n"
                f"💵 <b>تفاصيل الأجر الشهري المعتمد:</b>\n"
                f"• الأساسي: {dry_run.salary_details.basic_wage:,.2f} ر.س\n"
                f"• السكن: {dry_run.salary_details.housing_allowance:,.2f} ر.س\n"
                f"• النقل: {dry_run.salary_details.transportation_allowance:,.2f} ر.س\n"
                f"• <b>الإجمالي: {dry_run.salary_details.total_package:,.2f} ر.س</b>\n"
            )

        if dry_run.chamber_of_commerce_stamp:
            summary_text += "🏛️ <b>مطلوب تصديق الغرفة التجارية:</b> نعم ✅\n"

        summary_text += (
            f"────────────────────\n"
            f"🔐 <b>رمز الموافقة المؤقت:</b> <code>{dry_run.approval_token}</code>\n"
            f"⚠️ <b>حماية التحقق المزدوج:</b> يلزم النقر على زر الاعتماد ثم كتابة «تأكيد»."
        )

        token = dry_run.approval_token
        kb = {
            "inline_keyboard": [
                [
                    {"text": "🚀 اعتماد وإصدار الخطاب في Odoo", "callback_data": f"letter_approve:{token}"},
                    {"text": "❌ تراجع", "callback_data": "letter:cancel"},
                ]
            ]
        }
        bot.send_message(chat_id, summary_text, reply_markup=kb, reply_to_message_id=msg_id)
        return True

    return False


def execute_letter_via_service(
    bot: TelegramBotClient,
    chat_id: int | str,
    token: str,
    msg_id: Optional[int] = None,
) -> None:
    service = get_letter_service_for_bot()
    bot.send_message(chat_id, "⏳ جارِ إصدار الخطاب في Odoo وتوليد الوثيقة الرسمية والتحقق المستقل...", reply_to_message_id=msg_id)
    try:
        res = service.apply_letter(approval_token=token, user_confirmation_text="تأكيد")
        if res.is_success:
            succ_text = (
                f"🎉 <b>تم إصدار وتوثيق الخطاب الرسمي بنجاح في Odoo!</b>\n"
                f"────────────────────\n"
                f"👤 <b>الموظف:</b> {res.employee_name} (#{res.employee_id})\n"
                f"🔢 <b>رقم الطلب في Odoo:</b> <code>#{res.approval_request_id}</code>\n"
                f"🔐 <b>رمز التحقق الرقمي:</b> <code>{res.verification_code}</code>\n"
                f"📊 <b>حالة الطلب:</b> {res.request_status}\n"
                f"✅ <b>التحقق المستقل:</b> مطابق ومثبت (Readback Verified)\n"
                f"────────────────────\n"
                f"📄 <i>يتم الآن إرسال نسخة الوثيقة الرسمية للمحادثة...</i>"
            )
            bot.send_message(chat_id, succ_text)
            if res.pdf_path and os.path.exists(res.pdf_path):
                caption = f"📄 خطاب رسمي معتمد: {res.employee_name} ({res.verification_code})"
                bot.send_document(chat_id, Path(res.pdf_path), caption=caption)
            elif res.html_path and os.path.exists(res.html_path):
                caption = f"📄 نسخة الخطاب الرسمية: {res.employee_name} ({res.verification_code})"
                bot.send_document(chat_id, Path(res.html_path), caption=caption)
        else:
            bot.send_message(chat_id, f"❌ <b>فشل إصدار الخطاب:</b> {res.message_ar}")
    except Exception as exc:
        bot.send_message(chat_id, f"❌ <b>خطأ أثناء إصدار الخطاب:</b> <code>{exc}</code>")


_BOT_WARNING_SERVICE: Optional[WarningService] = None

def get_warning_service_for_bot(force_refresh: bool = False) -> WarningService:
    global _BOT_WARNING_SERVICE
    if _BOT_WARNING_SERVICE is not None and not force_refresh:
        return _BOT_WARNING_SERVICE
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        api_key=cfg.get("api_key") or cfg.get("password"),
    )
    gw = OdooWarningWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("api_key") or cfg.get("password"),
    )
    _BOT_WARNING_SERVICE = WarningService(repo=repo, gateway=gw)
    return _BOT_WARNING_SERVICE


def show_warning_levels_menu(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "📜 <b>إصدار خطابات الإنذار والمساءلات التأديبية (Warning Letters)</b> 🏢\n"
        "────────────────────\n"
        "أهلاً بك! يتيح لك هذا القسم توجيه وتوثيق خطابات الإنذار والجزاءات طبقاً للمواد 66 و 71 من نظام العمل:\n\n"
        "• <b>لفت نظر كتابي:</b> تنبيه مبدئي للمخالفات الخفيفة دون حسم.\n"
        "• <b>إنذار كتابي أول:</b> إنذار رسمي كتابي مودع بملف الموظف.\n"
        "• <b>إنذار كتابي ثانٍ مع خصم:</b> إنذار مشفوع بخصم (سقف 5 أيام كحد أقصى بموجب م/71).\n"
        "• <b>إنذار نهائي بالفصل:</b> إشعار نهائي قبل الفسخ بموجب المادة 80.\n"
        "• <b>التكامل المباشر:</b> تسجيل السجل في Odoo (warning.letter) وتوليد PDF فوري."
    )
    kb = {
        "inline_keyboard": [
            [
                {"text": "🟡 لفت نظر كتابي", "callback_data": "warning:level:notice"},
                {"text": "🟠 إنذار كتابي أول", "callback_data": "warning:level:first_warning"},
            ],
            [
                {"text": "🔴 إنذار ثانٍ مع خصم (م/71)", "callback_data": "warning:level:second_warning"},
                {"text": "⛔ إنذار نهائي بالفصل (م/80)", "callback_data": "warning:level:final_warning"},
            ],
            [
                {"text": "⚖️ دليل المواد 66 و 70 و 71 و 72", "callback_data": "disc:law_guide"},
            ],
            [
                {"text": "🔙 عُد لقائمة الجزاءات", "callback_data": "menu:disciplinary"},
                {"text": "🏠 القائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def start_warning_wizard(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    warning_level: str,
    message_id: Optional[int] = None,
) -> None:
    meta = WARNING_LEVELS.get(warning_level, {})
    title = meta.get("title_ar", "إنذار")
    ACTIVE_WARNING_WIZARDS[str(chat_id)] = {
        "step": "emp_id",
        "warning_level": warning_level,
        "user_id": str(user_id),
    }
    prompt = (
        f"📝 <b>إعداد {title}</b>\n"
        f"────────────────────\n"
        f"<b>الخطوة 1 من 3:</b> أرسل <b>رقم معرّف الموظف (ID)</b> في Odoo:\n"
        f"(مثال: <code>100</code> أو <code>25</code>)"
    )
    cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "warning:cancel"}]]}
    if message_id:
        bot.edit_message_text(chat_id, message_id, prompt, reply_markup=cancel_kb)
    else:
        bot.send_message(chat_id, prompt, reply_markup=cancel_kb)


def handle_warning_wizard_step(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    text: str,
    msg_id: Optional[int] = None,
) -> bool:
    wiz = ACTIVE_WARNING_WIZARDS.get(str(chat_id))
    if not wiz:
        return False

    step = wiz.get("step")
    clean_text = text.strip()

    if clean_text in ("/cancel", "الغاء", "إلغاء", "تراجع"):
        ACTIVE_WARNING_WIZARDS.pop(str(chat_id), None)
        bot.send_message(chat_id, "❌ تم إلغاء معالج الإنذارات.", reply_to_message_id=msg_id)
        show_warning_levels_menu(bot, chat_id)
        return True

    if step == "emp_id":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "warning_act", "warning:cancel", msg_id)
        if not emp:
            return True
        emp_id = emp["id"]
        wiz["employee_id"] = emp_id
        wiz["step"] = "violation"
        prompt = (
            "📋 <b>الخطوة 2 من 3: وصف واقعة المخالفة</b>\n"
            "────────────────────\n"
            "اكتب تفاصيل المخالفة المرتكبة باختصار ووضوح:\n"
            "(مثال: <code>التأخر عن العمل 45 دقيقة للمرة الثالثة بدون مبرر</code>)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "warning:cancel"}]]}
        bot.send_message(chat_id, prompt, reply_markup=cancel_kb, reply_to_message_id=msg_id)
        return True

    if step == "violation":
        wiz["violation_description"] = clean_text
        meta = WARNING_LEVELS.get(wiz["warning_level"], {})
        if meta.get("has_deduction_default"):
            wiz["step"] = "deduction_days"
            prompt = (
                "💵 <b>الخطوة 3 من 3: تحديد أيام الخصم (المادة 71)</b>\n"
                "────────────────────\n"
                "أدخل عدد أيام الخصم (الحد الأقصى النظامي: <b>5 أيام</b>):\n"
                "(مثال: <code>1</code> أو <code>2.5</code> أو <code>0</code> بدون خصم)"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "warning:cancel"}]]}
            bot.send_message(chat_id, prompt, reply_markup=cancel_kb, reply_to_message_id=msg_id)
            return True
        else:
            wiz["deduction_days"] = 0.0
            return _finish_warning_dry_run(bot, chat_id, wiz, msg_id)

    if step == "deduction_days":
        try:
            days = float(clean_text)
            if days < 0 or days > 5.0:
                bot.send_message(chat_id, "⚠️ المادة 71 تحظر تجاوز 5 أيام للمخالفة الواحدة. يرجى إدخال قيمة بين 0 و 5:", reply_to_message_id=msg_id)
                return True
            wiz["deduction_days"] = days
        except ValueError:
            bot.send_message(chat_id, "⚠️ يرجى إدخال رقم صالح لعدد أيام الخصم:", reply_to_message_id=msg_id)
            return True

        return _finish_warning_dry_run(bot, chat_id, wiz, msg_id)

    return False


def _finish_warning_dry_run(
    bot: TelegramBotClient,
    chat_id: int | str,
    wiz: Dict[str, Any],
    msg_id: Optional[int] = None,
) -> bool:
    ACTIVE_WARNING_WIZARDS.pop(str(chat_id), None)
    bot.send_message(chat_id, "⏳ <b>جارِ تدقيق الإنذار وحساب الراتب والسند النظامي (Dry-Run)...</b>", reply_to_message_id=msg_id)

    service = get_warning_service_for_bot()
    dry_run = service.dry_run_warning(
        employee_id=wiz["employee_id"],
        warning_level=wiz["warning_level"],
        violation_description=wiz["violation_description"],
        has_deduction=(wiz.get("deduction_days", 0) > 0),
        deduction_days=wiz.get("deduction_days", 0.0),
    )

    if not dry_run.is_valid:
        bot.send_message(
            chat_id,
            f"❌ <b>مخالفة نظامية - تعذر إصدار الإنذار:</b>\n" + "\n".join(f"• {e}" for e in dry_run.errors),
            reply_to_message_id=msg_id,
        )
        return True

    summary_text = (
        f"📄 <b>معاينة خطاب الإنذار والجزاء التأديبي (Dry-Run)</b> ⚖️\n"
        f"────────────────────\n"
        f"👤 <b>الموظف:</b> {dry_run.employee_name} (#{dry_run.employee_id})\n"
        f"🇸🇦 <b>الجنسية:</b> {dry_run.nationality_text_ar}\n"
        f"💼 <b>المسمى الوظيفي:</b> {dry_run.job_title} | {dry_run.department_name}\n"
        f"🏷️ <b>مستوى الإنذار:</b> <b>{dry_run.warning_title_ar}</b>\n"
        f"📜 <b>السند النظامي:</b> {dry_run.labor_law_article}\n"
        f"📋 <b>المخالفة:</b> {dry_run.violation_description}\n"
    )

    if dry_run.has_deduction and dry_run.deduction_amount > 0:
        summary_text += (
            f"────────────────────\n"
            f"💵 <b>تفاصيل الخصم (المادة 71):</b>\n"
            f"• الأجر اليومي: {dry_run.daily_wage:,.2f} ر.س\n"
            f"• عدد الأيام: <b>{dry_run.deduction_days} أيام</b>\n"
            f"• مبلغ الخصم: <b>{dry_run.deduction_amount:,.2f} ر.س</b>\n"
        )

    summary_text += (
        f"────────────────────\n"
        f"🔖 <b>الرقم المرجعي:</b> <code>{dry_run.reference_code}</code>\n"
        f"🔐 <b>رمز الموافقة المؤقت:</b> <code>{dry_run.approval_token}</code>\n"
        f"⚠️ <b>حماية التحقق المزدوج:</b> اضغط زر الاعتماد ثم اكتب كلمة «تأكيد» في المحادثة."
    )

    token = dry_run.approval_token
    kb = {
        "inline_keyboard": [
            [
                {"text": "🚀 اعتماد وحفظ الإنذار في Odoo", "callback_data": f"warning_approve:{token}"},
                {"text": "❌ تراجع", "callback_data": "warning:cancel"},
            ]
        ]
    }
    bot.send_message(chat_id, summary_text, reply_markup=kb, reply_to_message_id=msg_id)
    return True


def execute_warning_via_service(
    bot: TelegramBotClient,
    chat_id: int | str,
    token: str,
    msg_id: Optional[int] = None,
) -> None:
    service = get_warning_service_for_bot()
    bot.send_message(chat_id, "⏳ جارِ تسجيل خطاب الإنذار في Odoo وتوليد الوثيقة الرسمية والتحقق المستقل...", reply_to_message_id=msg_id)
    try:
        res = service.apply_warning(approval_token=token, user_confirmation_text="تأكيد")
        if res.is_success:
            succ_text = (
                f"🎉 <b>تم إصدار وتوثيق خطاب الإنذار بنجاح في Odoo!</b>\n"
                f"────────────────────\n"
                f"👤 <b>الموظف:</b> {res.employee_name} (#{res.employee_id})\n"
                f"🔢 <b>رقم السجل في Odoo:</b> <code>#{res.warning_letter_id}</code>\n"
                f"🔖 <b>الرقم المرجعي:</b> <code>{res.reference_code}</code>\n"
                f"🏷️ <b>المستوى:</b> {res.warning_level}\n"
                f"📊 <b>الحالة:</b> <code>{res.state}</code>\n"
                f"✅ <b>التحقق المستقل:</b> مطابق وموثق (Readback Verified)\n"
                f"────────────────────\n"
                f"📄 <i>يتم الآن إرسال نسخة وثيقة الإنذار الرسمية للمحادثة...</i>"
            )
            bot.send_message(chat_id, succ_text)
            if res.pdf_path and os.path.exists(res.pdf_path):
                caption = f"📄 خطاب إنذار رسمي: {res.employee_name} ({res.reference_code})"
                bot.send_document(chat_id, Path(res.pdf_path), caption=caption)
            elif res.html_path and os.path.exists(res.html_path):
                caption = f"📄 خطاب إنذار رسمي: {res.employee_name} ({res.reference_code})"
                bot.send_document(chat_id, Path(res.html_path), caption=caption)
        else:
            bot.send_message(chat_id, f"❌ <b>فشل إصدار الإنذار:</b> {res.message_ar}")
    except Exception as exc:
        bot.send_message(chat_id, f"❌ <b>خطأ أثناء إصدار الإنذار:</b> <code>{exc}</code>")


# ----------------------------------------------------------------------
# دوال معالجة مصروفات الموظفين والانتدابات (Phase 24 - Expenses)
# ----------------------------------------------------------------------

_BOT_EXPENSE_SERVICE: Optional[ExpenseService] = None

def get_expense_service_for_bot(force_refresh: bool = False) -> ExpenseService:
    global _BOT_EXPENSE_SERVICE
    if _BOT_EXPENSE_SERVICE is not None and not force_refresh:
        return _BOT_EXPENSE_SERVICE
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        api_key=cfg.get("api_key") or cfg.get("password"),
    )
    gw = OdooExpenseWriteGateway(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        password=cfg.get("api_key") or cfg.get("password"),
    )
    _BOT_EXPENSE_SERVICE = ExpenseService(repo=repo, gateway=gw)
    return _BOT_EXPENSE_SERVICE


def show_expense_menu(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    text = (
        "🧾 <b>إدارة مصروفات الموظفين وانتدابات العمل (Employee Expenses)</b> ✈️\n"
        "────────────────────\n"
        "أهلاً بك! يتيح لك هذا القسم تقديم وتدقيق واعتماد مطالبات المصروفات والانتدابات في Odoo:\n\n"
        "• <b>تذاكر السفر:</b> رحلات العمل والانتقالات الرسمية.\n"
        "• <b>الإقامة الفندقية:</b> السكن خلال فترات الانتداب والمهمات الخارجية.\n"
        "• <b>الإعاشة والوجبات:</b> وجبات العمل والبدلات اليومية.\n"
        "• <b>المواصلات والمحروقات:</b> النقل الميداني والتنقلات الداخلية.\n"
        "• <b>الاتصالات والإنترنت:</b> رسوم الاتصالات وخدمات الشبكة للعمل.\n"
        "• <b>مصروفات إدارية ونثرية:</b> المشتريات العاجلة والنثريات التشغيلية.\n"
        "• <b>الضريبة التلقائية:</b> فصل ضريبة القيمة المضافة (15% ZATCA) آلياً.\n"
        "• <b>التكامل المباشر:</b> إنشاء السجل في Odoo (hr.expense) مع التحقق المستقل وإصدار سند صرف PDF."
    )
    kb = {
        "inline_keyboard": [
            [
                {"text": "✈️ تذاكر سفر وانتقالات رسمية", "callback_data": "expense:cat:travel"},
                {"text": "🏨 إقامة فندقية وسكن انتداب", "callback_data": "expense:cat:hotel"},
            ],
            [
                {"text": "🍽️ إعاشة ووجبات عمل رسمية", "callback_data": "expense:cat:meals"},
                {"text": "🚗 مواصلات داخلية ومحروقات", "callback_data": "expense:cat:mileage"},
            ],
            [
                {"text": "📱 اتصالات وإنترنت ورسوم تقنية", "callback_data": "expense:cat:communication"},
                {"text": "💼 مصروفات إدارية ونثرية عامة", "callback_data": "expense:cat:general"},
            ],
            [
                {"text": "🔍 استعلام مصروفات موظف سابقاً", "callback_data": "expense:query_prompt"},
            ],
            [
                {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def start_expense_wizard(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    category: str,
    message_id: Optional[int] = None,
) -> None:
    meta = SUPPORTED_EXPENSE_CATEGORIES.get(category, {})
    title = meta.get("name_ar", "مطالبة مصروف")
    ACTIVE_EXPENSE_WIZARDS[str(chat_id)] = {
        "step": "emp_id",
        "category": category,
        "user_id": str(user_id),
    }
    prompt = (
        f"📝 <b>تسجيل {title}</b>\n"
        f"────────────────────\n"
        f"<b>الخطوة 1 من 3:</b> أرسل <b>رقم معرّف الموظف (ID)</b> في Odoo:\n"
        f"(مثال: <code>100</code> أو <code>15</code>)"
    )
    cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "expense:cancel"}]]}
    if message_id:
        bot.edit_message_text(chat_id, message_id, prompt, reply_markup=cancel_kb)
    else:
        bot.send_message(chat_id, prompt, reply_markup=cancel_kb)


def handle_expense_wizard_step(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    text: str,
    msg_id: Optional[int] = None,
) -> bool:
    wiz = ACTIVE_EXPENSE_WIZARDS.get(str(chat_id))
    if not wiz:
        return False

    step = wiz.get("step")
    clean_text = text.strip()

    if clean_text in ("/cancel", "الغاء", "إلغاء", "تراجع"):
        ACTIVE_EXPENSE_WIZARDS.pop(str(chat_id), None)
        bot.send_message(chat_id, "❌ تم إلغاء معالج المصروفات.", reply_to_message_id=msg_id)
        show_expense_menu(bot, chat_id)
        return True

    if step == "query_emp_id":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "expense_query", "menu:expenses", msg_id)
        if not emp:
            return True
        emp_id = emp["id"]
        ACTIVE_EXPENSE_WIZARDS.pop(str(chat_id), None)

        cfg = get_active_odoo_config()
        repo = OdooReadonlyRepository(
            url=cfg.get("url"), db=cfg.get("db"), username=cfg.get("username"), api_key=cfg.get("api_key") or cfg.get("password")
        )
        expenses = repo.get_hr_expenses(employee_id=emp_id)
        if not expenses:
            bot.send_message(chat_id, f"ℹ️ لا توجد مصروفات أو عهد مسجلة للموظف #{emp_id}.", reply_to_message_id=msg_id)
            return True

        res_text = f"📋 <b>سجل المصروفات المسجلة للموظف #{emp_id}:</b>\n────────────────────\n"
        for idx, exp in enumerate(expenses[:10], 1):
            st = exp.get("state") or "draft"
            total = exp.get("total_amount") or 0.0
            res_text += f"{idx}. <b>{exp.get('name') or 'مصروف'}</b>\n   • المبلغ: <code>{total:,.2f} ر.س</code> | الحالة: <code>{st}</code>\n   • التاريخ: <code>{str(exp.get('date'))[:10]}</code>\n\n"
        bot.send_message(chat_id, res_text, reply_to_message_id=msg_id)
        return True

    if step == "emp_id":
        emp = resolve_employee_input_for_wizard(bot, chat_id, clean_text, "expense_act", "expense:cancel", msg_id)
        if not emp:
            return True
        emp_id = emp["id"]
        wiz["employee_id"] = emp_id
        wiz["step"] = "amount"
        prompt = (
            "💵 <b>الخطوة 2 من 3: إجمالي المبلغ شاملاً الضريبة (SAR)</b>\n"
            "────────────────────\n"
            "أرسل إجمالي قيمة الفاتورة أو المصروف (شامل 15% ضريبة إن وجدت):\n"
            "(مثال: <code>450.00</code> أو <code>1850</code>)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "expense:cancel"}]]}
        bot.send_message(chat_id, prompt, reply_markup=cancel_kb, reply_to_message_id=msg_id)
        return True

    if step == "amount":
        try:
            amount = float(clean_text)
            if amount <= 0:
                bot.send_message(chat_id, "⚠️ يجب أن يكون المبلغ أكبر من الصفر:", reply_to_message_id=msg_id)
                return True
            wiz["total_amount"] = amount
        except ValueError:
            bot.send_message(chat_id, "⚠️ يرجى إدخال رقم صحيح للمبلغ (مثال: 350.50):", reply_to_message_id=msg_id)
            return True

        wiz["step"] = "description"
        meta = SUPPORTED_EXPENSE_CATEGORIES.get(wiz["category"], {})
        prompt = (
            "📝 <b>الخطوة 3 من 3: بيان وتفاصيل المصروف</b>\n"
            "────────────────────\n"
            "اكتب وصفاً مختصراً للمصروف أو رقم الفاتورة أو الغرض:\n"
            f"(أو أرسل <b>.</b> للاعتماد التلقائي: <code>{meta.get('name_ar')}</code>)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "expense:cancel"}]]}
        bot.send_message(chat_id, prompt, reply_markup=cancel_kb, reply_to_message_id=msg_id)
        return True

    if step == "description":
        meta = SUPPORTED_EXPENSE_CATEGORIES.get(wiz["category"], {})
        description = meta.get("name_ar", "مصروف عمل") if clean_text == "." else clean_text
        wiz["description"] = description

        ACTIVE_EXPENSE_WIZARDS.pop(str(chat_id), None)
        bot.send_message(chat_id, "⏳ <b>جارِ فحص وتدقيق بيانات المصروف واحتساب الضريبة (Dry-Run)...</b>", reply_to_message_id=msg_id)

        service = get_expense_service_for_bot()
        dry_run = service.dry_run_expense(
            employee_id=wiz["employee_id"],
            expense_category=wiz["category"],
            total_amount=wiz["total_amount"],
            description=description,
            includes_vat=True,
        )

        if not dry_run.is_valid:
            bot.send_message(
                chat_id,
                f"❌ <b>تعذر تسجيل المصروف:</b>\n" + "\n".join(f"• {e}" for e in dry_run.errors),
                reply_to_message_id=msg_id,
            )
            return True

        summary_text = (
            f"📄 <b>معاينة مطالبة المصروف قبل الحفظ (Dry-Run)</b> 🧾\n"
            f"────────────────────\n"
            f"👤 <b>الموظف:</b> {dry_run.employee_name} (#{dry_run.employee_id})\n"
            f"🇸🇦 <b>الجنسية:</b> {dry_run.nationality_text_ar}\n"
            f"💼 <b>المسمى الوظيفي:</b> {dry_run.job_title} | {dry_run.department_name}\n"
            f"🏷️ <b>التصنيف:</b> {dry_run.category_title_ar}\n"
            f"📝 <b>البيان:</b> {dry_run.description}\n"
            f"────────────────────\n"
            f"💵 <b>تفاصيل المبالغ والضريبة (15% ZATCA):</b>\n"
            f"• المبلغ الأساسي: {dry_run.untaxed_amount:,.2f} ر.س\n"
            f"• ضريبة القيمة المضافة (15%): {dry_run.tax_amount:,.2f} ر.س\n"
            f"• <b>الإجمالي الكلي: {dry_run.total_amount:,.2f} ر.س</b>\n"
            f"────────────────────\n"
            f"🔖 <b>الرقم المرجعي:</b> <code>{dry_run.reference_code}</code>\n"
            f"🔐 <b>رمز الموافقة المؤقت:</b> <code>{dry_run.approval_token}</code>\n"
            f"⚠️ <b>حماية التحقق المزدوج:</b> اضغط زر الاعتماد ثم اكتب كلمة «تأكيد» في المحادثة."
        )

        token = dry_run.approval_token
        kb = {
            "inline_keyboard": [
                [
                    {"text": "🚀 اعتماد وقيد المصروف في Odoo", "callback_data": f"expense_approve:{token}"},
                    {"text": "❌ تراجع", "callback_data": "expense:cancel"},
                ]
            ]
        }
        bot.send_message(chat_id, summary_text, reply_markup=kb, reply_to_message_id=msg_id)
        return True

    return False


def execute_expense_via_service(
    bot: TelegramBotClient,
    chat_id: int | str,
    token: str,
    msg_id: Optional[int] = None,
) -> None:
    service = get_expense_service_for_bot()
    bot.send_message(chat_id, "⏳ جارِ تسجيل المصروف في Odoo وتوليد سند الصرف والتحقق المستقل...", reply_to_message_id=msg_id)
    try:
        res = service.apply_expense(approval_token=token, user_confirmation_text="تأكيد")
        if res.is_success:
            succ_text = (
                f"🎉 <b>تم تسجيل وقيد المصروف بنجاح في Odoo!</b>\n"
                f"────────────────────\n"
                f"👤 <b>الموظف:</b> {res.employee_name} (#{res.employee_id})\n"
                f"🔢 <b>رقم السجل في Odoo:</b> <code>#{res.expense_id}</code>\n"
                f"🔖 <b>الرقم المرجعي:</b> <code>{res.reference_code}</code>\n"
                f"💵 <b>المبلغ الإجمالي:</b> <b>{res.total_amount:,.2f} ر.س</b>\n"
                f"📊 <b>الحالة:</b> <code>{res.state}</code>\n"
                f"✅ <b>التحقق المستقل:</b> مطابق ومثبت (Readback Verified)\n"
                f"────────────────────\n"
                f"📄 <i>يتم الآن إرسال سند الصرف الرسمي للمحادثة...</i>"
            )
            bot.send_message(chat_id, succ_text)
            if res.pdf_path and os.path.exists(res.pdf_path):
                caption = f"📄 سند صرف ومطالبة مصروفات: {res.employee_name} ({res.reference_code})"
                bot.send_document(chat_id, Path(res.pdf_path), caption=caption)
            elif res.html_path and os.path.exists(res.html_path):
                caption = f"📄 سند صرف ومطالبة مصروفات: {res.employee_name} ({res.reference_code})"
                bot.send_document(chat_id, Path(res.html_path), caption=caption)
        else:
            bot.send_message(chat_id, f"❌ <b>فشل تسجيل المصروف:</b> {res.message_ar}")
    except Exception as exc:
        bot.send_message(chat_id, f"❌ <b>خطأ أثناء تسجيل المصروف:</b> <code>{exc}</code>")


# ----------------------------------------------------------------------
# دوال معالجة صلاحيات الوثائق والتنبيهات المجدولة (Phase 25 - Expiries)
# ----------------------------------------------------------------------

_BOT_EXPIRY_SERVICE: Optional[DocumentExpiryService] = None

def get_expiry_service_for_bot(force_refresh: bool = False) -> DocumentExpiryService:
    global _BOT_EXPIRY_SERVICE
    if _BOT_EXPIRY_SERVICE is not None and not force_refresh:
        return _BOT_EXPIRY_SERVICE
    cfg = get_active_odoo_config()
    repo = OdooReadonlyRepository(
        url=cfg.get("url"),
        db=cfg.get("db"),
        username=cfg.get("username"),
        api_key=cfg.get("api_key") or cfg.get("password"),
    )
    _BOT_EXPIRY_SERVICE = DocumentExpiryService(repo=repo)
    return _BOT_EXPIRY_SERVICE


def show_expiry_menu_card(
    bot: TelegramBotClient,
    chat_id: int | str,
    message_id: Optional[int] = None,
    max_days: int = 90,
) -> None:
    service = get_expiry_service_for_bot()
    scan_res = service.scan_expiries(max_days=max_days)
    text = service.format_telegram_summary_message(scan_res, top_n=8)

    kb = {
        "inline_keyboard": [
            [
                {"text": "🔴 منتهية الصلاحية فقط", "callback_data": "expiries:filter:0"},
                {"text": "🚨 حرجة (خلال 7 أيام)", "callback_data": "expiries:filter:7"},
            ],
            [
                {"text": "⚠️ تحذيرية (خلال 30 يوماً)", "callback_data": "expiries:filter:30"},
                {"text": "ℹ️ نافذة 90 يوماً كاملة", "callback_data": "expiries:filter:90"},
            ],
            [
                {"text": "📄 استخراج تقرير PDF رسمي", "callback_data": "expiries:pdf"},
            ],
            [
                {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def send_expiry_pdf_report(
    bot: TelegramBotClient,
    chat_id: int | str,
    msg_id: Optional[int] = None,
) -> None:
    bot.send_message(chat_id, "⏳ جارِ فحص وثائق كافة الموظفين وتوليد تقرير الرصد الرسمي...", reply_to_message_id=msg_id)
    service = get_expiry_service_for_bot()
    scan_res = service.scan_expiries(max_days=90)
    pdf_path = service.generate_pdf_report(scan_res)

    caption = f"📋 تقرير رصد صلاحيات الوثائق والهويات الرسمي ({scan_res.scan_date}) - {scan_res.total_alerts} تنبيهاً"
    if pdf_path and os.path.exists(pdf_path):
        bot.send_document(chat_id, Path(pdf_path), caption=caption)
    else:
        html_fname = f"expiry_report_{scan_res.scan_date.replace('-', '')}.html"
        html_path = os.path.join(EXPIRY_OUTPUT_DIR, html_fname)
        if os.path.exists(html_path):
            bot.send_document(chat_id, Path(html_path), caption=caption)
        else:
            bot.send_message(chat_id, f"✅ تم فحص الوثائق ({scan_res.total_alerts} تنبيهاً مسجلاً).")


def show_musleh_info_card(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    """Displays Musleh self-healing engine details, consultation workflow, and auto-repair status."""
    is_on = is_autofix_enabled(chat_id)
    status_str = "🟢 مفعّل (Auto-Fix Active)" if is_on else "⏸️ معطّل - مراجعة فقط (Review Only)"
    text = (
        "🛠️ <b>وكيل الإصلاح الذاتي والتعافي: «مصلح» (Musleh Engine)</b>\n"
        "────────────────────\n"
        f"• <b>نمط الإصلاح التلقائي الحالي:</b> {status_str} (التحكم: <code>/autofix on|off</code>)\n"
        "• <b>الدور الوظيفي:</b> مهندس التحقيق وعلاج الأخطاء والتعافي بعد الأعطال.\n"
        "• <b>نطاق العمل:</b> يتدخل حصراً في الصفوف المعطوبة (<code>needs_review</code> و <code>rejected</code>).\n"
        "• <b>سلسلة المشاورة التشخيصية:</b>\n"
        "  1️⃣ <b>فاحص:</b> استعلام مراجع Odoo الحية والمؤرشفة.\n"
        "  2️⃣ <b>موفق:</b> المطابقة الضبابية الذكية (Fuzzy Matching) واقتراح البدائل.\n"
        "  3️⃣ <b>مدقق:</b> الامتثال لمواد نظام العمل السعودي والتأمينات.\n"
        "\n"
        "⚖️ <b>القرارات التنفيذية الصادرة:</b>\n"
        "  • <b>الإصلاح الفوري (APPLY_AUTO_PATCH):</b> عند الثقة ≥ 90% وخيار الإصلاح التلقائي.\n"
        "  • <b>العزل والمتابعة (QUARANTINE_AND_PROCEED):</b> عزل المعطوب لإنشاء باقي الدفعة.\n"
        "  • <b>تأسيس كيان مفقود (PROPOSE_MISSING_ENTITY):</b> اقتراح إنشاء القسم/المسمى أولاً.\n"
        "  • <b>الإحالة للمسؤول (ESCALATE_TO_HUMAN):</b> ترفع وترجع لسراج مع خيارات بنقرة زر.\n\n"
        "🔒 <b>صمام الأمان:</b> أرقام الهويات الوطنية والإقامات خط أحمر لا تُعدل تلقائياً."
    )
    back_kb = {
        "inline_keyboard": [
            [
                {"text": "⚙️ تبديل وضع الإصلاح التلقائي (/autofix)", "callback_data": "autofix:status"}
            ],
            [
                {"text": "🔙 العودة للقائمة الرئيسية", "callback_data": "menu:main"}
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=back_kb)
    else:
        bot.send_message(chat_id, text, reply_markup=back_kb)


def show_autofix_status_card(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    """Displays current Autofix mode (ON/OFF) with interactive toggle buttons."""
    is_on = is_autofix_enabled(chat_id)
    status_icon = "🟢" if is_on else "⏸️"
    status_text = "<b>مفعّل (Auto-Fix Active)</b>" if is_on else "<b>معطّل - وضع المراجعة فقط (Review Only)</b>"

    text = (
        f"⚙️ <b>إعدادات الإصلاح التلقائي: «مصلح» (Auto-Fix Settings)</b>\n"
        f"────────────────────\n"
        f"• <b>الحالة الحالية:</b> {status_icon} {status_text}\n\n"
        f"📋 <b>كيف يعمل هذا الخيار؟</b>\n"
        f"• <b>عند التفعيل (<code>/autofix on</code>):</b>\n"
        f"  يعالج «مصلح» التواريخ وأرقام الهواتف ومطابقات المسميات والأقسام الموثوقة (ثقة ≥ 90%) فورياً ويجهز الصفوف للإنشاء دون توقف عند كل حقل.\n\n"
        f"• <b>عند التعطيل (<code>/autofix off</code>):</b>\n"
        f"  يقدم «مصلح» تشخيصاً مفصلاً ويعزل الصفوف المعطوبة، ويحيل الخيارات لسراج للاعتماد اليدوي دون تعديل آلي.\n\n"
        f"🔒 <b>صمام الأمان الدائم:</b> أرقام الهويات الوطنية والإقامات محظورة تماماً من التعديل التلقائي."
    )

    kb = {
        "inline_keyboard": [
            [
                {"text": "🟢 تفعيل الإصلاح التلقائي (/autofix on)", "callback_data": "autofix:enable"},
                {"text": "⏸️ تعطيل (مراجعة فقط)", "callback_data": "autofix:disable"},
            ],
            [
                {"text": "🛠️ بطاقة معلومات «مصلح»", "callback_data": "musleh:info"},
                {"text": "🔙 القائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_main_menu(bot: TelegramBotClient, chat_id: int | str, user_name: str, message_id: Optional[int] = None) -> None:
    text = (
        f"أهلاً بك <b>{user_name}</b>، معك <b>سراج</b> لإدارة وتدقيق عمليات Odoo للموارد البشرية 🏢\n\n"
        f"اختر ما تريد إنجازه وسأنفذه معك خطوة بخطوة:\n\n"
        f"• <b>التسجيلات الصوتية:</b> أرسل رسالة صوتية (Voice Note) وسأفهم طلبك وأوجهه فورياً عبر Whisper 🎙️\n"
        f"• <b>قوالب الإكسل:</b> استلم أي قالب من قوالب العمليات الـ 14 المعتمدة سعودياً.\n"
        f"• <b>ربط خادم Odoo:</b> وجّهني لقاعدة بياناتك أو قاعدة عميلك الجديد برابط ومفتاح API.\n"
        f"• <b>فحص ملف فوري:</b> أرسل ملف الإكسل (<code>.xlsx</code>) مباشرة هنا وسأفحصه وأدققه لك استباقياً.\n"
        f"• <b>استعراض الهيكل:</b> تصفح فروع الشركة وأقسامها المكتشفة في Odoo."
    )
    kb = get_main_menu_keyboard()
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_odoo_settings_card(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    cfg = get_active_odoo_config()
    test_res = test_odoo_connection(cfg["url"], cfg["db"], cfg["username"], cfg["api_key"])

    raw_key = cfg.get("api_key", "")
    masked_key = (raw_key[:4] + "••••" + raw_key[-4:]) if len(raw_key) >= 8 else "••••••••"
    status_emoji = "✅ متصل وجاهز" if test_res.get("ok") else "⚠️ غير متصل"

    text = (
        f"⚙️ <b>بيانات الاتصال الحالية بخادم Odoo:</b>\n"
        f"────────────────────\n"
        f"🌐 <b>الرابط:</b> <code>{cfg.get('url') or 'غير محدد'}</code>\n"
        f"🗄️ <b>قاعدة البيانات:</b> <code>{cfg.get('db') or 'غير محدد'}</code>\n"
        f"👤 <b>اسم المستخدم:</b> <code>{cfg.get('username') or 'غير محدد'}</code>\n"
        f"🔑 <b>مفتاح الـ API:</b> <code>{masked_key}</code>\n"
        f"────────────────────\n"
        f"📡 <b>الحالة:</b> <b>{status_emoji}</b>\n"
    )
    if test_res.get("ok"):
        text += f"• معرّف الدخول (UID): <code>{test_res.get('uid')}</code>\n"
        text += f"• الشركات والفروع: <b>{test_res.get('company_count')}</b>\n"
        text += f"• الموظفون المسجلون: <b>{test_res.get('employee_count', 0)}</b>\n"
        text += f"• الأقسام النشطة: <b>{test_res.get('department_count', 0)}</b>\n"
    else:
        text += f"💡 <b>التفاصيل:</b> <code>{test_res.get('error')}</code>\n"

    text += "\nاختر الإجراء المطلوب:"

    kb = {
        "inline_keyboard": [
            [
                {"text": "🔗 اربط خادماً جديداً", "callback_data": "odoo:edit_wizard"},
                {"text": "🔄 افحص الاتصال الآن", "callback_data": "odoo:test"},
            ],
            [
                {"text": "🏢 تصفح الشركات والفروع", "callback_data": "menu:show_companies"},
                {"text": "🔄 ولّد قوالب لهذه القاعدة", "callback_data": "odoo:regen_templates"},
            ],
            [
                {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_companies_branches(bot: TelegramBotClient, chat_id: int | str, message_id: Optional[int] = None) -> None:
    try:
        from odoo_readonly_repository import OdooReadonlyRepository
        repo = OdooReadonlyRepository()
        comps = repo.get_accessible_companies()
        depts = repo.get_departments()

        lines = [
            "🔍 <b>تقرير وكيل الاستعلام والفحص «فاحص» (بيانات Odoo الحية):</b>",
            "────────────────────",
            "🏢 <b>المنشآت والفروع المسجلة:</b>\n",
        ]
        if comps:
            for c in comps:
                cid = c.get("id")
                cname = c.get("name")
                c_depts = [d for d in depts if (d.get("company_id") == cid or (isinstance(d.get("company_id"), (list, tuple)) and d.get("company_id")[0] == cid))]
                lines.append(f"• <b>{cname}</b> (معرّف ID: <code>#{cid}</code>)")
                if c_depts:
                    dept_names = [d.get("name") for d in c_depts]
                    lines.append(f"  └ <i>الأقسام ({len(c_depts)}):</i> {', '.join(dept_names)}")
                lines.append("")
        else:
            lines.append("<i>لم يتم العثور على منشآت مسجلة أو لا تملك الصلاحيات الكافية.</i>")

        lines.append("────────────────────")
        lines.append("💡 <i>ملاحظة: يمكنك الاستعلام عن أي موظف بالاسم أو المعرّف ID وسيفحصه لك «فاحص» فوراً.</i>")
        text = "\n".join(lines)
    except Exception as exc:
        text = f"❌ <b>تعذر جلب المنشآت من Odoo عبر فاحص:</b>\n<code>{type(exc).__name__}: {exc}</code>"

    kb = {
        "inline_keyboard": [
            [
                {"text": "🔗 إعدادات الاتصال بـ Odoo", "callback_data": "menu:odoo_settings"},
                {"text": "📥 تحميل القوالب", "callback_data": "menu:templates"},
            ],
            [
                {"text": "🔙 العودة للقائمة الرئيسية", "callback_data": "menu:main"},
            ]
        ]
    }
    if message_id:
        bot.edit_message_text(chat_id, message_id, text, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


def handle_template_request(bot: TelegramBotClient, chat_id: int | str, tpl_key: str, message_id: Optional[int] = None) -> None:
    tpl = TEMPLATES_CATALOG.get(tpl_key)
    if not tpl:
        bot.send_message(chat_id, "⚠️ القالب المطلوب غير مسجل.")
        return

    file_path = ROOT_DIR / tpl["file"]
    alt_file = file_path.parent / f"{file_path.stem}_updated{file_path.suffix}"
    if alt_file.exists() and (not file_path.exists() or alt_file.stat().st_mtime > file_path.stat().st_mtime):
        file_path = alt_file

    if not file_path.exists():
        bot.send_message(chat_id, f"⏳ جارِ توليد ملف <b>{tpl['title']}</b> للمرة الأولى...")
        try:
            import subprocess
            subprocess.run([sys.executable, "scripts/generate_all_hr_templates.py"], check=True, timeout=60)
            if alt_file.exists() and (not file_path.exists() or alt_file.stat().st_mtime > file_path.stat().st_mtime):
                file_path = alt_file
        except Exception as exc:
            bot.send_message(chat_id, f"❌ تعذر توليد القالب: <code>{exc}</code>")
            return

    bot.send_message(chat_id, f"📤 جارِ إرسال <b>{tpl['title']}</b>...")
    res = bot.send_document(chat_id, file_path, caption=tpl["caption"])
    if not res.get("ok"):
        bot.send_message(chat_id, f"❌ فشل إرسال الملف عبر تيليجرام: <code>{res.get('description')}</code>")
    else:
        log_telegram_audit(chat_id, chat_id, "template_sent", {"template": tpl_key})


def handle_config_wizard_step(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    text: str,
    msg_id: int,
) -> bool:
    wiz = ACTIVE_CONFIG_WIZARDS.get(str(chat_id))
    if not wiz:
        return False

    clean_text = text.strip()
    step = wiz.get("step")

    if clean_text in ("إلغاء", "الغاء", "cancel", "/cancel"):
        ACTIVE_CONFIG_WIZARDS.pop(str(chat_id), None)
        bot.send_message(chat_id, "🚫 تم إلغاء معالج إعداد ربط Odoo.", reply_to_message_id=msg_id)
        show_main_menu(bot, chat_id, user_name)
        return True

    cancel_kb = {"inline_keyboard": [[{"text": "❌ تراجع عن الإعداد", "callback_data": "wizard:cancel"}]]}

    if step == "url":
        if not (clean_text.startswith("http://") or clean_text.startswith("https://")):
            bot.send_message(
                chat_id,
                "تأكد أن الرابط يبدأ بـ <code>https://</code> أو <code>http://</code> للاتصال بخادمك بأمان.\n"
                "مثال: <code>https://mycompany.odoo.com</code>",
                reply_to_message_id=msg_id,
                reply_markup=cancel_kb,
            )
            return True
        wiz["url"] = clean_text.rstrip("/")
        wiz["step"] = "db"
        bot.send_message(
            chat_id,
            f"حفظتُ الرابط: <code>{wiz['url']}</code> ✅\n\n"
            f"🗄️ <b>الخطوة 2 من 4:</b>\n"
            f"ما اسم قاعدة البيانات (Database Name) في Odoo؟",
            reply_to_message_id=msg_id,
            reply_markup=cancel_kb,
        )
        return True

    elif step == "db":
        wiz["db"] = clean_text
        wiz["step"] = "user"
        bot.send_message(
            chat_id,
            f"سجّلتُ اسم القاعدة: <code>{wiz['db']}</code> ✅\n\n"
            f"👤 <b>الخطوة 3 من 4:</b>\n"
            f"أرسل بريدك الإلكتروني أو اسم المستخدم المسجل في Odoo:",
            reply_to_message_id=msg_id,
            reply_markup=cancel_kb,
        )
        return True

    elif step == "user":
        wiz["user"] = clean_text
        wiz["step"] = "key"
        bot.send_message(
            chat_id,
            f"سجّلتُ المستخدم: <code>{wiz['user']}</code> ✅\n\n"
            f"🔑 <b>الخطوة 4 من 4 (الأخيرة):</b>\n"
            f"أرسل الآن مفتاح الـ API الخاص بحسابك لتأكيد الاتصال فوراً:\n"
            f"💡 <i>(تستخرجه من: تفضيلاتك في Odoo ➔ أمان الحساب ➔ مفاتيح المطورين)</i>",
            reply_to_message_id=msg_id,
            reply_markup=cancel_kb,
        )
        return True

    elif step == "key":
        wiz["key"] = clean_text
        ACTIVE_CONFIG_WIZARDS.pop(str(chat_id), None)

        bot.send_message(
            chat_id,
            "⏳ <b>أتصل الآن بخادمك وأتحقق من بيانات الدخول...</b>",
            reply_to_message_id=msg_id,
        )

        test_res = test_odoo_connection(wiz["url"], wiz["db"], wiz["user"], wiz["key"])
        if test_res.get("ok"):
            save_active_odoo_config(wiz["url"], wiz["db"], wiz["user"], wiz["key"])
            log_telegram_audit(user_id, chat_id, "odoo_config_updated", {"url": wiz["url"], "db": wiz["db"]})

            success_text = (
                f"🎉 <b>رائع! اتصلتُ بنجاح وتعرّفتُ على قاعدة بياناتك:</b>\n"
                f"────────────────────\n"
                f"• خادم Odoo: <code>{wiz['url']}</code>\n"
                f"• قاعدة البيانات: <code>{wiz['db']}</code>\n"
                f"• المستخدم: <code>{wiz['user']}</code> (معرّف UID: <code>{test_res.get('uid')}</code>)\n"
                f"• الشركات والفروع: <b>{test_res.get('company_count')}</b>\n"
                f"• الموظفون المسجلون: <b>{test_res.get('employee_count', 0)}</b>\n"
                f"• الأقسام النشطة: <b>{test_res.get('department_count', 0)}</b>\n"
                f"────────────────────\n"
                f"✨ حفظتُ هذه الإعدادات بنجاح. أصبحت جميع أدوات الفحص وتوليد القوالب متصلة بقاعدتك مباشرة!\n\n"
                f"ماذا تحب أن نفعل الآن؟"
            )
            kb = {
                "inline_keyboard": [
                    [
                        {"text": "🔄 ولّد قوالب مخصصة لشركتك", "callback_data": "odoo:regen_templates"},
                    ],
                    [
                        {"text": "📥 استلم القوالب الجاهزة", "callback_data": "menu:templates"},
                        {"text": "🏢 تصفح هيكل الفروع", "callback_data": "menu:show_companies"},
                    ],
                    [
                        {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
                    ]
                ]
            }
            bot.send_message(chat_id, success_text, reply_markup=kb)
        else:
            fail_text = (
                f"تعذر الاتصال بخادم Odoo للسبب التالي:\n"
                f"<code>{test_res.get('error')}</code>\n\n"
                f"تأكد من صحة الرابط واسم القاعدة وبيانات الدخول ثم أعد المحاولة."
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "✏️ أعد المحاولة", "callback_data": "odoo:edit_wizard"}],
                    [{"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"}],
                ]
            }
            bot.send_message(chat_id, fail_text, reply_markup=kb)
        return True

    return False


def handle_wizard_employee_selection(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    msg_id: int,
    wiz_type: str,
    emp_id: int,
) -> None:
    """Dispatches interactive employee selection from disambiguation button click."""
    if wiz_type == "leave_bal":
        ACTIVE_LEAVE_WIZARDS.pop(str(chat_id), None)
        show_employee_leaves_balance(bot, chat_id, emp_id)

    elif wiz_type == "leave_req":
        ACTIVE_LEAVE_WIZARDS[str(chat_id)] = {
            "mode": "request",
            "step": "type",
            "employee_id": emp_id,
            "user_id": str(user_id),
        }
        prompt_leave_type_selection(bot, chat_id, emp_id)

    elif wiz_type == "attend_sum":
        ACTIVE_ATTENDANCE_WIZARDS.pop(str(chat_id), None)
        show_employee_attendance_card(bot, chat_id, emp_id)

    elif wiz_type == "attend_in":
        ACTIVE_ATTENDANCE_WIZARDS.pop(str(chat_id), None)
        PENDING_ATTENDANCE_CONFIRMATIONS[str(chat_id)] = {
            "action": "check_in",
            "employee_id": emp_id,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        confirm_text = (
            f"⚠️ <b>تأكيد تسجيل حضور فوري (Check-In)</b> 🟢\n"
            f"────────────────────\n"
            f"أنت على وشك تسجيل حضور للموظف معرّف #{emp_id} في Odoo.\n\n"
            f"وفق مبدأ التحقق المزدوج (Four-Eyes Principle)، اكتب كلمة <b>«تأكيد»</b> لتسجيل الحضور."
        )
        kb = {"inline_keyboard": [[{"text": "❌ تراجع", "callback_data": "attend:cancel"}]]}
        bot.send_message(chat_id, confirm_text, reply_markup=kb)
        log_telegram_audit(user_id, chat_id, "attendance_checkin_confirm_requested", {"employee_id": emp_id})

    elif wiz_type == "attend_out":
        ACTIVE_ATTENDANCE_WIZARDS.pop(str(chat_id), None)
        PENDING_ATTENDANCE_CONFIRMATIONS[str(chat_id)] = {
            "action": "check_out",
            "employee_id": emp_id,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        confirm_text = (
            f"⚠️ <b>تأكيد تسجيل انصراف فوري (Check-Out)</b> 🔴\n"
            f"────────────────────\n"
            f"أنت على وشك إغلاق دوام وتسجيل انصراف للموظف معرّف #{emp_id} في Odoo.\n\n"
            f"وفق مبدأ التحقق المزدوج (Four-Eyes Principle)، اكتب كلمة <b>«تأكيد»</b> لتسجيل الانصراف."
        )
        kb = {"inline_keyboard": [[{"text": "❌ تراجع", "callback_data": "attend:cancel"}]]}
        bot.send_message(chat_id, confirm_text, reply_markup=kb)
        log_telegram_audit(user_id, chat_id, "attendance_checkout_confirm_requested", {"employee_id": emp_id})

    elif wiz_type == "attend_overtime":
        ACTIVE_ATTENDANCE_WIZARDS[str(chat_id)] = {
            "mode": "overtime",
            "step": "times",
            "employee_id": emp_id,
            "user_id": str(user_id),
        }
        prompt_text = (
            f"⏱️ <b>تحديد تاريخ وساعات الدوام للموظف #{emp_id}:</b>\n"
            f"────────────────────\n"
            f"أرسل تاريخ وساعات الحضور والانصراف بصيغة:\n"
            f"<code>YYYY-MM-DD HH:MM HH:MM</code>\n\n"
            f"مثال: <code>2026-10-07 08:00 18:30</code>"
        )
        bot.send_message(chat_id, prompt_text)

    elif wiz_type == "disc_sum":
        ACTIVE_DISCIPLINARY_WIZARDS.pop(str(chat_id), None)
        show_employee_disciplinary_card(bot, chat_id, emp_id)

    elif wiz_type == "disc_act":
        ACTIVE_DISCIPLINARY_WIZARDS[str(chat_id)] = {
            "mode": "action",
            "step": "details",
            "employee_id": emp_id,
            "user_id": str(user_id),
        }
        prompt_text = (
            f"📝 <b>بيانات الجزاء التأديبي للموظف #{emp_id}:</b>\n"
            f"────────────────────\n"
            f"أرسل تفاصيل المخالفة والنوع والخصم مفصولة بمسافات:\n\n"
            f"الصيغة: <code>[نوع الجزاء] [سبب المخالفة] [أيام الخصم أو النسبة]</code>\n\n"
            f"خيارات نوع الجزاء المعتمدة بنظام العمل:\n"
            f"• <code>إنذار</code> أو <code>تنبيه</code> (إنذار كتابي)\n"
            f"• <code>خصم 1</code> (خصم يوم عمل من الأجر م/66)\n"
            f"• <code>إيقاف 2</code> (إيقاف عن العمل بدون أجر يومين م/66)\n"
            f"• <code>حرمان</code> (حرمان من العلاوة أو تأجيل الترقية)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "disciplinary:cancel"}]]}
        bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb)

    elif wiz_type == "eos_calc":
        ACTIVE_EOS_WIZARDS[str(chat_id)] = {
            "mode": "calc_details",
            "employee_id": emp_id,
            "user_id": str(user_id),
        }
        prompt_text = (
            f"💼 <b>بيانات تسوية نهاية الخدمة للموظف #{emp_id}:</b>\n"
            f"────────────────────\n"
            f"أرسل الأجر الشهري وسبب انتهاء العلاقة ورصيد الإجازات مفصولة بمسافات:\n\n"
            f"الصيغة: <code>[الأجر الشهري] [السبب] [رصيد الإجازات المتبقية] [شهور العقد المتبقية إن وجد]</code>\n\n"
            f"خيارات السبب:\n"
            f"• <code>إنهاء</code> أو <code>فصل</code> (إنهاء من المنشأة - م/84)\n"
            f"• <code>استقالة</code> (استقالة عادية - م/85)\n"
            f"• <code>اتفاق</code> (إنهاء بالتراضي - م/74)\n"
            f"• <code>قوة_قاهرة</code> (م/87 - استحقاق كامل)\n"
            f"• <code>مادة_80</code> (فصل تأديبي بدون مكافأة)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "eos:cancel"}]]}
        bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb)

    elif wiz_type == "gr_act":
        ACTIVE_GR_WIZARDS[str(chat_id)] = {
            "mode": "gr_details",
            "employee_id": emp_id,
            "user_id": str(user_id),
        }
        prompt_text = (
            f"🏛️ <b>بيانات المعاملة الحكومية للموظف #{emp_id}:</b>\n"
            f"────────────────────\n"
            f"أرسل نوع المعاملة والرسوم والطرف المسؤول مفصولة بمسافات:\n\n"
            f"الصيغة: <code>[نوع المعاملة] [الرسوم اختياري] [الطرف المسؤول: company أو employee أو split]</code>"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "gr:cancel"}]]}
        bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb)

    elif wiz_type == "appraisal_act":
        ACTIVE_APPRAISAL_WIZARDS[str(chat_id)] = {
            "mode": "appraisal_details",
            "employee_id": emp_id,
            "user_id": str(user_id),
        }
        prompt_text = (
            f"🌟 <b>بيانات تقييم الموظف #{emp_id}:</b>\n"
            f"────────────────────\n"
            f"أرسل درجات التقييم ونوعه مفصولة بمسافات:\n\n"
            f"الصيغة: <code>[درجة الأهداف KPIs من 100] [درجة الكفاءات من 100] [النوع: annual أو probation]</code>"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "appraisal:cancel"}]]}
        bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb)

    elif wiz_type == "loan_act":
        ACTIVE_LOAN_WIZARDS[str(chat_id)] = {
            "mode": "loan_details",
            "employee_id": emp_id,
            "user_id": str(user_id),
        }
        prompt_text = (
            f"💳 <b>بيانات طلب السلفة للموظف #{emp_id}:</b>\n"
            f"────────────────────\n"
            f"أرسل مبلغ السلفة ومدة السداد بالأشهر والقسط مفصولة بمسافات:\n\n"
            f"الصيغة: <code>[مبلغ السلفة] [مدة السداد بالأشهر] [القسط اختياري]</code>"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "loan:cancel"}]]}
        bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb)

    elif wiz_type == "contract_act":
        ACTIVE_CONTRACT_WIZARDS[str(chat_id)] = {
            "mode": "contract_details",
            "employee_id": emp_id,
            "user_id": str(user_id),
        }
        prompt_text = (
            f"📄 <b>بيانات العقد الجديد للموظف #{emp_id}:</b>\n"
            f"────────────────────\n"
            f"أرسل تفاصيل الراتب والبدلات مفصولة بمسافات:\n\n"
            f"الصيغة: <code>[الراتب الأساسي] [بدل السكن] [بدل النقل] [بدلات أخرى إن وجدت]</code>\n\n"
            f"مثال: <code>6000 1500 500</code> (إجمالي 8000 ر.س)\n\n"
            f"💡 سيتم احتساب اشتراك التأمينات (GOSI) تلقائياً بموجب نظام التأمينات السعودي."
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "contract:cancel"}]]}
        bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb)

    elif wiz_type == "payroll_act":
        ACTIVE_PAYROLL_WIZARDS[str(chat_id)] = {
            "mode": "payroll_details",
            "employee_id": emp_id,
            "user_id": str(user_id),
        }
        prompt_text = (
            f"💰 <b>بيانات مسير الرواتب للموظف #{emp_id}:</b>\n"
            f"────────────────────\n"
            f"أرسل شهر المسير وساعات العمل الإضافي وأيام الغياب مفصولة بمسافات:\n\n"
            f"الصيغة: <code>[الشهر YYYY-MM] [ساعات إضافي إن وجدت] [أيام غياب إن وجدت]</code>\n\n"
            f"مثال: <code>2026-10 10 0</code> (مسير شهر 10 مع 10 ساعات إضافي م/107 وبدون غياب)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "payroll:cancel"}]]}
        bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb)

    elif wiz_type == "letter_query":
        ACTIVE_LETTER_WIZARDS.pop(str(chat_id), None)
        cfg = get_active_odoo_config()
        repo = OdooReadonlyRepository(
            url=cfg.get("url"), db=cfg.get("db"), username=cfg.get("username"), api_key=cfg.get("api_key") or cfg.get("password")
        )
        letters = repo.get_employee_approval_requests(emp_id)
        if not letters:
            bot.send_message(chat_id, f"ℹ️ لا توجد خطابات أو طلبات موافقة مسجلة للموظف #{emp_id}.")
        else:
            res_text = f"📋 <b>سجل الخطابات والموافقات الصادرة للموظف #{emp_id}:</b>\n────────────────────\n"
            for idx, l in enumerate(letters[:10], 1):
                st = l.get("request_status") or "غير محدد"
                res_text += f"{idx}. <b>{l.get('name') or 'طلب'}</b>\n   • الحالة: <code>{st}</code> | الجهة: <code>{l.get('to') or '—'}</code>\n   • التاريخ: <code>{str(l.get('create_date') or l.get('date'))[:10]}</code>\n\n"
            bot.send_message(chat_id, res_text)

    elif wiz_type == "letter_issue":
        wiz = ACTIVE_LETTER_WIZARDS.get(str(chat_id), {})
        wiz["employee_id"] = emp_id
        wiz["step"] = "recipient"
        ACTIVE_LETTER_WIZARDS[str(chat_id)] = wiz
        meta = SUPPORTED_LETTER_TYPES.get(wiz.get("letter_type", ""), {})
        default_to = meta.get("default_to", "إلى من يهمه الأمر")
        prompt = (
            f"🎯 <b>الخطوة 2 من 2: تحديد الجهة الموجه إليها الخطاب للموظف #{emp_id}</b>\n"
            f"────────────────────\n"
            f"أرسل اسم الجهة أو البنك أو السفارة الموجه لها الخطاب:\n"
            f"(أو أرسل <b>.</b> لاستخدام الافتراضي: <code>{default_to}</code>)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "letter:cancel"}]]}
        bot.send_message(chat_id, prompt, reply_markup=cancel_kb)

    elif wiz_type == "warning_act":
        wiz = ACTIVE_WARNING_WIZARDS.get(str(chat_id), {})
        wiz["employee_id"] = emp_id
        wiz["step"] = "violation"
        ACTIVE_WARNING_WIZARDS[str(chat_id)] = wiz
        prompt = (
            f"📋 <b>الخطوة 2 من 3: وصف واقعة المخالفة للموظف #{emp_id}</b>\n"
            f"────────────────────\n"
            f"اكتب تفاصيل المخالفة المرتكبة باختصار ووضوح:\n"
            f"(مثال: <code>التأخر عن العمل 45 دقيقة للمرة الثالثة بدون مبرر</code>)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "warning:cancel"}]]}
        bot.send_message(chat_id, prompt, reply_markup=cancel_kb)

    elif wiz_type == "expense_query":
        ACTIVE_EXPENSE_WIZARDS.pop(str(chat_id), None)
        cfg = get_active_odoo_config()
        repo = OdooReadonlyRepository(
            url=cfg.get("url"), db=cfg.get("db"), username=cfg.get("username"), api_key=cfg.get("api_key") or cfg.get("password")
        )
        expenses = repo.get_hr_expenses(employee_id=emp_id)
        if not expenses:
            bot.send_message(chat_id, f"ℹ️ لا توجد مصروفات أو عهد مسجلة للموظف #{emp_id}.")
        else:
            res_text = f"📋 <b>سجل المصروفات المسجلة للموظف #{emp_id}:</b>\n────────────────────\n"
            for idx, exp in enumerate(expenses[:10], 1):
                st = exp.get("state") or "draft"
                total = exp.get("total_amount") or 0.0
                res_text += f"{idx}. <b>{exp.get('name') or 'مصروف'}</b>\n   • المبلغ: <code>{total:,.2f} ر.س</code> | الحالة: <code>{st}</code>\n   • التاريخ: <code>{str(exp.get('date'))[:10]}</code>\n\n"
            bot.send_message(chat_id, res_text)

    elif wiz_type == "expense_act":
        wiz = ACTIVE_EXPENSE_WIZARDS.get(str(chat_id), {})
        wiz["employee_id"] = emp_id
        wiz["step"] = "amount"
        ACTIVE_EXPENSE_WIZARDS[str(chat_id)] = wiz
        prompt = (
            f"💵 <b>الخطوة 2 من 3: إجمالي المبلغ للموظف #{emp_id} شاملاً الضريبة (SAR)</b>\n"
            f"────────────────────\n"
            f"أرسل إجمالي قيمة الفاتورة أو المصروف (شامل 15% ضريبة إن وجدت):\n"
            f"(مثال: <code>450.00</code> أو <code>1850</code>)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "expense:cancel"}]]}
        bot.send_message(chat_id, prompt, reply_markup=cancel_kb)


def handle_callback_dispatch(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    msg_id: int,
    cq_id: str,
    data: str,
) -> None:
    """Central router for all callback queries."""
    if data.startswith("approve:") or data.startswith("cancel:"):
        handle_approval_callback(bot, chat_id, user_id, user_name, msg_id, cq_id, data)
        return

    if data.startswith("musleh:heal:"):
        run_id = data.split(":", 2)[2]
        handle_musleh_heal_callback(bot, chat_id, user_id, user_name, msg_id, cq_id, run_id)
        return

    if data.startswith("musleh:heal_auto:"):
        run_id = data.split(":", 2)[2]
        set_autofix_enabled(chat_id, True)
        handle_musleh_heal_callback(bot, chat_id, user_id, user_name, msg_id, cq_id, run_id)
        return

    bot.answer_callback_query(cq_id)

    if data.startswith("wiz_emp:"):
        parts = data.split(":", 2)
        if len(parts) == 3:
            _, wiz_type, emp_id_str = parts
            try:
                emp_id = int(emp_id_str)
                handle_wizard_employee_selection(bot, chat_id, user_id, user_name, msg_id, wiz_type, emp_id)
            except Exception as e:
                logger.error(f"Error handling wiz_emp callback {data}: {e}")
        return

    if data == "menu:main":
        show_main_menu(bot, chat_id, user_name, message_id=msg_id)
    elif data == "menu:templates":
        bot.edit_message_text(
            chat_id, msg_id,
            "📥 <b>مستودع قوالب الموارد البشرية (Odoo HR Templates):</b>\n"
            "────────────────────\n"
            "اختر القالب الذي تحتاجه وسأرسل لك ملف الإكسل (<code>.xlsx</code>) فوراً في المحادثة:\n\n"
            "• <b>القالب الشامل:</b> لتأسيس منشأة جديدة من الصفر مع كل الهياكل.\n"
            "• <b>القوالب المنفصلة:</b> للعمليات اليومية والشهرية للعملاء القائمين.",
            reply_markup=get_templates_menu_keyboard(),
        )
    elif data.startswith("get_tpl:"):
        tpl_key = data.split(":", 1)[1]
        handle_template_request(bot, chat_id, tpl_key, message_id=msg_id)
    elif data == "menu:odoo_settings":
        show_odoo_settings_card(bot, chat_id, message_id=msg_id)
    elif data == "menu:show_companies":
        show_companies_branches(bot, chat_id, message_id=msg_id)
    elif data == "menu:system_status":
        cfg = get_active_odoo_config()
        status_text = (
            f"📊 <b>جاهزية منظومة وكلاء سراج:</b>\n"
            f"────────────────────\n"
            f"🤖 <b>سراج (الموجّه التفاعلي):</b> نشط ومستعد ✅\n"
            f"🔍 <b>فاحص (مستودع القراءة):</b> متصل بقاعدة (<code>{cfg.get('db') or 'غير محدد'}</code>) ✅\n"
            f"⚖️ <b>مدقق (محرك القوانين):</b> مطابق لنظام العمل والتأمينات السعودي ✅\n"
            f"🛡️ <b>حارس (سياسة البيئات):</b> بيئة العمل مؤمنة ومحمية ✅\n"
            f"✍️ <b>كاتب (بوابة الاعتماد):</b> جاهز للإنشاء عبر الـ API ✅\n"
            f"📁 <b>سجل (سجل العمليات):</b> موثق في <code>logs/telegram_audit.log</code> ✅\n"
            f"────────────────────\n"
            f"✨ جميع الوكلاء يعملون بتناغم تام وجاهزون لاستقبال ملفاتك وأوامرك."
        )
        kb = {"inline_keyboard": [[{"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"}]]}
        bot.edit_message_text(chat_id, msg_id, status_text, reply_markup=kb)
    elif data == "odoo:test":
        show_odoo_settings_card(bot, chat_id, message_id=msg_id)
    elif data == "odoo:edit_wizard":
        ACTIVE_CONFIG_WIZARDS[str(chat_id)] = {"step": "url", "user_id": str(user_id)}
        prompt_text = (
            "🔗 <b>معالج ربط خادم Odoo</b> 🏢\n"
            "────────────────────\n"
            "أهلاً بك! لكي أتعرف على قاعدة بياناتك وأفهم فروعها وموظفيها، أحتاج منك 4 بيانات بسيطة خطوة بخطوة:\n\n"
            "1️⃣ <b>رابط الخادم (URL)</b>\n"
            "2️⃣ <b>اسم قاعدة البيانات (Database Name)</b>\n"
            "3️⃣ <b>اسم المستخدم أو البريد (Username / Email)</b>\n"
            "4️⃣ <b>مفتاح API (Developer API Key)</b>\n\n"
            "💡 <i>أين تجد مفتاح API في Odoo؟</i>\n"
            "من حسابك في Odoo: اضغط على صورتك ➔ تفضيلات ➔ أمان الحساب ➔ مفاتيح المطورين ➔ أنشئ مفتاحاً جديداً.\n"
            "────────────────────\n"
            "🌐 <b>الخطوة 1 من 4:</b>\n"
            "أرسل رابط خادم Odoo الآن:\n"
            "(مثال: <code>https://my-company.odoo.com</code>)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ تراجع عن الإعداد", "callback_data": "wizard:cancel"}]]}
        bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data == "odoo:regen_templates":
        bot.edit_message_text(chat_id, msg_id, "⏳ جارِ توليد وتحديث القوالب لبيانات القاعدة النشطة الآن...")
        try:
            import subprocess
            proc = subprocess.run(
                [sys.executable, "scripts/generate_all_hr_templates.py"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=90
            )
            if proc.returncode != 0:
                err_text = (proc.stderr or proc.stdout or "").strip()
                if "PermissionError" in err_text or "Permission denied" in err_text:
                    bot.edit_message_text(
                        chat_id, msg_id,
                        "⚠️ <b>تعذر استبدال ملف القالب الموحد:</b>\n"
                        "ملف القالب مفتوح حالياً في برنامج <b>Microsoft Excel</b> على جهازك.\n\n"
                        "💡 <b>الحل السريع:</b> يرجى إغلاق ملف الإكسل المفتوح على جهازك، ثم الضغط على زر التحديث مجدداً.",
                        reply_markup={"inline_keyboard": [
                            [{"text": "🔄 إعادة محاولة التحديث", "callback_data": "odoo:regen_templates"}],
                            [{"text": "🔙 القائمة الرئيسية", "callback_data": "menu:main"}],
                        ]}
                    )
                else:
                    short_err = err_text[-250:] if len(err_text) > 250 else err_text
                    bot.edit_message_text(
                        chat_id, msg_id,
                        f"❌ تعذر تحديث القوالب:\n<code>{short_err}</code>",
                        reply_markup={"inline_keyboard": [
                            [{"text": "🔄 إعادة المحاولة", "callback_data": "odoo:regen_templates"}],
                            [{"text": "🔙 القائمة الرئيسية", "callback_data": "menu:main"}],
                        ]}
                    )
                return

            bot.edit_message_text(
                chat_id, msg_id,
                "🎉 <b>تم تحديث وتوليد جميع القوالب الـ 14 بنجاح!</b>\nأصبحت جميع القوائم المنسدلة والمراجع مطابقة لقاعدتك الجديدة.",
                reply_markup={"inline_keyboard": [
                    [{"text": "📥 تحميل القوالب الآن", "callback_data": "menu:templates"}],
                    [{"text": "🔙 القائمة الرئيسية", "callback_data": "menu:main"}],
                ]}
            )
        except Exception as exc:
            bot.edit_message_text(chat_id, msg_id, f"❌ تعذر تحديث القوالب: <code>{exc}</code>")
    elif data == "wizard:cancel":
        ACTIVE_CONFIG_WIZARDS.pop(str(chat_id), None)
        show_main_menu(bot, chat_id, user_name, message_id=msg_id)
    elif data == "menu:leaves":
        show_leaves_menu(bot, chat_id, message_id=msg_id)
    elif data == "leave:law_guide":
        show_leaves_law_guide(bot, chat_id, message_id=msg_id)
    elif data == "leave:balance_prompt":
        ACTIVE_LEAVE_WIZARDS[str(chat_id)] = {"mode": "balance", "user_id": str(user_id)}
        prompt_text = (
            "📊 <b>استعلام رصيد واستحقاق الموظف</b>\n"
            "────────────────────\n"
            "أرسل <b>رقم معرّف الموظف (ID)</b> أو جزءاً من اسمه/بريده في Odoo:\n"
            "(مثال: <code>100</code> أو <code>أحمد</code>)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "leave:cancel"}]]}
        bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data == "leave:request_wizard" or data.startswith("leave:req_for:"):
        emp_id = None
        if data.startswith("leave:req_for:"):
            try:
                emp_id = int(data.split(":", 2)[2])
            except Exception:
                emp_id = None
        if emp_id:
            ACTIVE_LEAVE_WIZARDS[str(chat_id)] = {"mode": "request", "step": "type", "employee_id": emp_id, "user_id": str(user_id)}
            prompt_leave_type_selection(bot, chat_id, emp_id, message_id=msg_id)
        else:
            ACTIVE_LEAVE_WIZARDS[str(chat_id)] = {"mode": "request", "step": "emp", "user_id": str(user_id)}
            prompt_text = (
                "📝 <b>تقديم طلب إجازة جديد</b> 🌴\n"
                "────────────────────\n"
                "أرسل <b>رقم معرّف الموظف (ID)</b> أو جزءاً من اسمه/بريده للمتابعة:"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "leave:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data.startswith("leave_type:"):
        lt_id = int(data.split(":", 1)[1])
        wiz = ACTIVE_LEAVE_WIZARDS.get(str(chat_id))
        if wiz and wiz.get("mode") == "request":
            wiz["holiday_status_id"] = lt_id
            wiz["step"] = "dates"
            prompt_text = (
                "📅 <b>تحديد فترة الإجازة</b>\n"
                "────────────────────\n"
                "أرسل تاريخ البداية والنهاية بصيغة (YYYY-MM-DD):\n"
                "(مثال: <code>2026-10-15 2026-10-20</code>)\n"
                "أو أرسل تاريخ البداية فقط إذا كانت يوماً واحداً."
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "leave:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data.startswith("leave_approve:"):
        token = data.split(":", 1)[1]
        PENDING_LEAVE_CONFIRMATIONS[str(chat_id)] = {
            "token": token,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        bot.answer_callback_query(cq_id, "يلزم تأكيد كتابي للمتابعة")
        confirm_prompt = (
            f"⚠️ <b>تأكيد أمان إلزامي (مبدأ العينين الأربع)</b>\n"
            f"────────────────────\n"
            f"أنت على وشك تسجيل طلب الإجازة رمز <code>{token}</code> فعلياً في قاعدة بيانات Odoo.\n\n"
            f"لحماية العمليات وسجلات المنشأة، اكتب كلمة <b>«تأكيد»</b> في المحادثة للاعتماد والتنفيذ."
        )
        bot.edit_message_text(chat_id, msg_id, confirm_prompt)
        log_telegram_audit(user_id, chat_id, "leave_written_confirm_requested", {"token": token})
    elif data == "leave:cancel":
        ACTIVE_LEAVE_WIZARDS.pop(str(chat_id), None)
        PENDING_LEAVE_CONFIRMATIONS.pop(str(chat_id), None)
        show_leaves_menu(bot, chat_id, message_id=msg_id)
    elif data == "menu:attendance":
        show_attendance_menu(bot, chat_id, message_id=msg_id)
    elif data == "attend:law_guide":
        show_attendance_law_guide(bot, chat_id, message_id=msg_id)
    elif data == "attend:summary_prompt":
        ACTIVE_ATTENDANCE_WIZARDS[str(chat_id)] = {"mode": "summary", "user_id": str(user_id)}
        prompt_text = (
            "📊 <b>استعلام ملخص وساعات دوام الموظف</b> ⏰\n"
            "────────────────────\n"
            "أرسل <b>رقم معرّف الموظف (ID)</b> أو جزءاً من اسمه/بريده في Odoo:\n"
            "(مثال: <code>100</code> أو <code>خالد</code>)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "attend:cancel"}]]}
        bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data == "attend:checkin_prompt":
        ACTIVE_ATTENDANCE_WIZARDS[str(chat_id)] = {"mode": "checkin_input", "user_id": str(user_id)}
        prompt_text = (
            "🟢 <b>تسجيل حضور فوري (Check-In)</b>\n"
            "────────────────────\n"
            "أرسل <b>رقم معرّف الموظف (ID)</b> لتسجيل حضوره الآن:"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "attend:cancel"}]]}
        bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data == "attend:checkout_prompt":
        ACTIVE_ATTENDANCE_WIZARDS[str(chat_id)] = {"mode": "checkout_input", "user_id": str(user_id)}
        prompt_text = (
            "🔴 <b>تسجيل انصراف فوري (Check-Out)</b>\n"
            "────────────────────\n"
            "أرسل <b>رقم معرّف الموظف (ID)</b> لإغلاق دوامه وتسجيل الانصراف:"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "attend:cancel"}]]}
        bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data == "attend:overtime_prompt" or data.startswith("attend:ot_for:"):
        emp_id = None
        if data.startswith("attend:ot_for:"):
            try:
                emp_id = int(data.split(":", 2)[2])
            except Exception:
                emp_id = None
        if emp_id:
            ACTIVE_ATTENDANCE_WIZARDS[str(chat_id)] = {"mode": "overtime", "step": "times", "employee_id": emp_id, "user_id": str(user_id)}
            prompt_text = (
                f"⏱️ <b>تحديد تاريخ وساعات الدوام للموظف #{emp_id}:</b>\n"
                f"────────────────────\n"
                f"أرسل تاريخ وساعات الحضور والانصراف بصيغة:\n"
                f"<code>YYYY-MM-DD HH:MM HH:MM</code>\n\n"
                f"مثال:\n"
                f"<code>2026-10-06 08:00 18:30</code>"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "attend:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
        else:
            ACTIVE_ATTENDANCE_WIZARDS[str(chat_id)] = {"mode": "overtime", "step": "emp", "user_id": str(user_id)}
            prompt_text = (
                "⏱️ <b>احتساب وتدقيق العمل الإضافي (Dry-Run)</b>\n"
                "────────────────────\n"
                "أرسل <b>رقم معرّف الموظف (ID)</b> أو جزءاً من اسمه/بريده للمتابعة:"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "attend:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data.startswith("attend_act:cin:"):
        emp_id = int(data.split(":", 2)[2])
        PENDING_ATTENDANCE_CONFIRMATIONS[str(chat_id)] = {
            "action": "check_in",
            "employee_id": emp_id,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        bot.answer_callback_query(cq_id, "يلزم تأكيد كتابي للمتابعة")
        confirm_prompt = (
            f"⚠️ <b>تأكيد تسجيل حضور فوري (Check-In)</b> 🟢\n"
            f"────────────────────\n"
            f"أنت على وشك تسجيل حضور للموظف معرّف #{emp_id} في Odoo.\n\n"
            f"وفق مبدأ التحقق المزدوج (Four-Eyes Principle)، اكتب كلمة <b>«تأكيد»</b> لتسجيل الحضور."
        )
        bot.edit_message_text(chat_id, msg_id, confirm_prompt)
        log_telegram_audit(user_id, chat_id, "attendance_checkin_confirm_requested", {"employee_id": emp_id})
    elif data.startswith("attend_act:cout:"):
        emp_id = int(data.split(":", 2)[2])
        PENDING_ATTENDANCE_CONFIRMATIONS[str(chat_id)] = {
            "action": "check_out",
            "employee_id": emp_id,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        bot.answer_callback_query(cq_id, "يلزم تأكيد كتابي للمتابعة")
        confirm_prompt = (
            f"⚠️ <b>تأكيد تسجيل انصراف فوري (Check-Out)</b> 🔴\n"
            f"────────────────────\n"
            f"أنت على وشك إغلاق دوام وتسجيل انصراف للموظف معرّف #{emp_id} في Odoo.\n\n"
            f"وفق مبدأ التحقق المزدوج (Four-Eyes Principle)، اكتب كلمة <b>«تأكيد»</b> لتسجيل الانصراف."
        )
        bot.edit_message_text(chat_id, msg_id, confirm_prompt)
        log_telegram_audit(user_id, chat_id, "attendance_checkout_confirm_requested", {"employee_id": emp_id})
    elif data.startswith("attend_approve:"):
        token = data.split(":", 1)[1]
        PENDING_ATTENDANCE_CONFIRMATIONS[str(chat_id)] = {
            "action": "apply_token",
            "token": token,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        bot.answer_callback_query(cq_id, "يلزم تأكيد كتابي للمتابعة")
        confirm_prompt = (
            f"⚠️ <b>تأكيد أمان إلزامي (مبدأ العينين الأربع)</b>\n"
            f"────────────────────\n"
            f"أنت على وشك تسجيل حركة الدوام والعمل الإضافي رمز <code>{token}</code> فعلياً في Odoo.\n\n"
            f"لحماية العمليات وسجلات المنشأة، اكتب كلمة <b>«تأكيد»</b> في المحادثة للاعتماد والتنفيذ."
        )
        bot.edit_message_text(chat_id, msg_id, confirm_prompt)
        log_telegram_audit(user_id, chat_id, "attendance_written_confirm_requested", {"token": token})
    elif data == "attend:cancel":
        ACTIVE_ATTENDANCE_WIZARDS.pop(str(chat_id), None)
        PENDING_ATTENDANCE_CONFIRMATIONS.pop(str(chat_id), None)
        show_attendance_menu(bot, chat_id, message_id=msg_id)
    elif data == "menu:disciplinary":
        show_disciplinary_menu(bot, chat_id, message_id=msg_id)
    elif data == "disc:law_guide":
        show_disciplinary_law_guide(bot, chat_id, message_id=msg_id)
    elif data == "disc:summary_prompt":
        ACTIVE_DISCIPLINARY_WIZARDS[str(chat_id)] = {"mode": "summary", "user_id": str(user_id)}
        prompt_text = (
            "📊 <b>استعلام سجل مخالفات وجزاءات الموظف</b> ⚖️\n"
            "────────────────────\n"
            "أرسل <b>رقم معرّف الموظف (ID)</b> أو جزءاً من اسمه/بريده في Odoo:\n"
            "(مثال: <code>100</code> أو <code>خالد</code>)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "disc:cancel"}]]}
        bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data == "disc:action_prompt" or data.startswith("disc:act_for:"):
        emp_id = None
        if data.startswith("disc:act_for:"):
            try:
                emp_id = int(data.split(":", 2)[2])
            except Exception:
                emp_id = None
        if emp_id:
            ACTIVE_DISCIPLINARY_WIZARDS[str(chat_id)] = {"mode": "action", "step": "details", "employee_id": emp_id, "user_id": str(user_id)}
            prompt_text = (
                f"📝 <b>بيانات الجزاء التأديبي للموظف #{emp_id}:</b>\n"
                f"────────────────────\n"
                f"أرسل تاريخ المخالفة وعدد أيام الخصم ووصف المخالفة مفصولة بمسافات:\n\n"
                f"الصيغة: <code>YYYY-MM-DD [عدد الأيام] [السبب]</code>\n\n"
                f"مثال:\n"
                f"<code>2026-10-06 1 تأخر متكرر عن موعد الدوام الرسمي</code>"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "disc:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
        else:
            ACTIVE_DISCIPLINARY_WIZARDS[str(chat_id)] = {"mode": "action", "step": "emp", "user_id": str(user_id)}
            prompt_text = (
                "📝 <b>تسجيل وتدقيق جزاء تأديبي جديد (Dry-Run)</b> ⚖️\n"
                "────────────────────\n"
                "أرسل <b>رقم معرّف الموظف (ID)</b> أو جزءاً من اسمه/بريده للمتابعة:"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "disc:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data.startswith("disc_approve:"):
        token = data.split(":", 1)[1]
        PENDING_DISCIPLINARY_CONFIRMATIONS[str(chat_id)] = {
            "token": token,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        bot.answer_callback_query(cq_id, "يلزم تأكيد كتابي للمتابعة")
        confirm_prompt = (
            f"⚠️ <b>تأكيد أمان إلزامي (مبدأ العينين الأربع)</b>\n"
            f"────────────────────\n"
            f"أنت على وشك تسجيل الجزاء التأديبي رمز <code>{token}</code> فعلياً في Odoo.\n\n"
            f"لحماية العمليات وسجلات المنشأة، اكتب كلمة <b>«تأكيد»</b> في المحادثة للاعتماد والتنفيذ."
        )
        bot.edit_message_text(chat_id, msg_id, confirm_prompt)
        log_telegram_audit(user_id, chat_id, "disciplinary_written_confirm_requested", {"token": token})
    elif data == "disc:cancel":
        ACTIVE_DISCIPLINARY_WIZARDS.pop(str(chat_id), None)
        PENDING_DISCIPLINARY_CONFIRMATIONS.pop(str(chat_id), None)
        show_disciplinary_menu(bot, chat_id, message_id=msg_id)
    elif data == "menu:eos":
        show_eos_menu(bot, chat_id, message_id=msg_id)
    elif data == "eos:laws_guide":
        show_eos_laws_guide(bot, chat_id, message_id=msg_id)
    elif data == "eos:calc_prompt" or data.startswith("eos:calc_for:"):
        emp_id = None
        if data.startswith("eos:calc_for:"):
            try:
                emp_id = int(data.split(":", 2)[2])
            except Exception:
                emp_id = None
        if emp_id:
            ACTIVE_EOS_WIZARDS[str(chat_id)] = {"mode": "calc_details", "employee_id": emp_id, "user_id": str(user_id)}
            prompt_text = (
                f"💼 <b>بيانات تسوية نهاية الخدمة للموظف #{emp_id}:</b>\n"
                f"────────────────────\n"
                f"أرسل الأجر الشهري وسبب انتهاء العلاقة ورصيد الإجازات مفصولة بمسافات:\n\n"
                f"الصيغة: <code>[الأجر الشهري] [السبب] [رصيد الإجازات] [المدة المتبقية بالعقد]</code>\n\n"
                f"مثال:\n"
                f"<code>9000 إنهاء 10</code> أو <code>7000 استقالة 0</code>"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "eos:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
        else:
            ACTIVE_EOS_WIZARDS[str(chat_id)] = {"mode": "calc_emp", "user_id": str(user_id)}
            prompt_text = (
                "💼 <b>تسوية مكافأة نهاية الخدمة (Dry-Run)</b> ⚖️\n"
                "────────────────────\n"
                "أرسل <b>رقم معرّف الموظف (ID)</b> أو جزءاً من اسمه/بريده الإلكتروني للمتابعة:"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "eos:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data.startswith("eos_approve:"):
        token = data.split(":", 1)[1]
        PENDING_EOS_CONFIRMATIONS[str(chat_id)] = {
            "token": token,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        bot.answer_callback_query(cq_id, "يلزم تأكيد كتابي للمتابعة")
        confirm_prompt = (
            f"⚠️ <b>تأكيد أمان إلزامي (مبدأ العينين الأربع)</b>\n"
            f"────────────────────\n"
            f"أنت على وشك اعتماد وتسجيل تسوية نهاية الخدمة رمز <code>{token}</code> فعلياً في Odoo.\n\n"
            f"لحماية العمليات وسجلات المنشأة، اكتب كلمة <b>«تأكيد»</b> في المحادثة للاعتماد والتنفيذ."
        )
        bot.edit_message_text(chat_id, msg_id, confirm_prompt)
        log_telegram_audit(user_id, chat_id, "eos_written_confirm_requested", {"token": token})
    elif data == "eos:cancel":
        ACTIVE_EOS_WIZARDS.pop(str(chat_id), None)
        PENDING_EOS_CONFIRMATIONS.pop(str(chat_id), None)
        show_eos_menu(bot, chat_id, message_id=msg_id)
    elif data == "menu:gr":
        show_gr_menu(bot, chat_id, message_id=msg_id)
    elif data == "gr:laws_guide":
        show_gr_laws_guide(bot, chat_id, message_id=msg_id)
    elif data == "gr:prompt" or data.startswith("gr:tx_for:"):
        emp_id = None
        if data.startswith("gr:tx_for:"):
            try:
                emp_id = int(data.split(":", 2)[2])
            except Exception:
                emp_id = None
        if emp_id:
            ACTIVE_GR_WIZARDS[str(chat_id)] = {"mode": "gr_details", "employee_id": emp_id, "user_id": str(user_id)}
            prompt_text = (
                f"🏛️ <b>بيانات المعاملة الحكومية للموظف #{emp_id}:</b>\n"
                f"────────────────────\n"
                f"أرسل نوع المعاملة والرسوم والطرف المسؤول مفصولة بمسافات:\n\n"
                f"الصيغة: <code>[نوع المعاملة] [الرسوم إن اختلفت] [الطرف: company/employee/split]</code>\n\n"
                f"أمثلة:\n"
                f"• <code>تجديد إقامة</code>\n"
                f"• <code>إصدار تأشيرة خروج وعودة</code>\n"
                f"• <code>تأشيرة خروج وعودة 200 employee</code>\n"
                f"• <code>نقل كفالة 2000 company</code>"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "gr:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
        else:
            ACTIVE_GR_WIZARDS[str(chat_id)] = {"mode": "gr_emp", "user_id": str(user_id)}
            prompt_text = (
                "🏛️ <b>تسجيل وتدقيق معاملة حكومية جديدة (Dry-Run)</b> 🏢\n"
                "────────────────────\n"
                "أرسل <b>رقم معرّف الموظف (ID)</b> أو جزءاً من اسمه/بريده الإلكتروني للمتابعة:"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "gr:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data.startswith("gr_approve:"):
        token = data.split(":", 1)[1]
        PENDING_GR_CONFIRMATIONS[str(chat_id)] = {
            "token": token,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        bot.answer_callback_query(cq_id, "يلزم تأكيد كتابي للمتابعة")
        confirm_prompt = (
            f"⚠️ <b>تأكيد أمان إلزامي (مبدأ العينين الأربع)</b>\n"
            f"────────────────────\n"
            f"أنت على وشك اعتماد وتسجيل المعاملة الحكومية رمز <code>{token}</code> فعلياً في Odoo.\n\n"
            f"لحماية العمليات وسجلات المنشأة، اكتب كلمة <b>«تأكيد»</b> في المحادثة للاعتماد والتنفيذ."
        )
        bot.edit_message_text(chat_id, msg_id, confirm_prompt)
        log_telegram_audit(user_id, chat_id, "gr_written_confirm_requested", {"token": token})
    elif data == "gr:cancel":
        ACTIVE_GR_WIZARDS.pop(str(chat_id), None)
        PENDING_GR_CONFIRMATIONS.pop(str(chat_id), None)
        show_gr_menu(bot, chat_id, message_id=msg_id)
    elif data == "menu:appraisal":
        show_appraisal_menu(bot, chat_id, message_id=msg_id)
    elif data == "appraisal:laws_guide":
        show_appraisal_laws_guide(bot, chat_id, message_id=msg_id)
    elif data == "appraisal:prompt" or data.startswith("appraisal:eval_for:"):
        emp_id = None
        if data.startswith("appraisal:eval_for:"):
            try:
                emp_id = int(data.split(":", 2)[2])
            except Exception:
                emp_id = None
        if emp_id:
            ACTIVE_APPRAISAL_WIZARDS[str(chat_id)] = {"mode": "appraisal_details", "employee_id": emp_id, "user_id": str(user_id)}
            prompt_text = (
                f"🌟 <b>بيانات تقييم الموظف #{emp_id}:</b>\n"
                f"────────────────────\n"
                f"أرسل درجات التقييم ونوعه مفصولة بمسافات:\n\n"
                f"الصيغة: <code>[درجة الأهداف من 100] [درجة الكفاءات من 100] [النوع: annual أو probation]</code>\n\n"
                f"أمثلة:\n"
                f"• <code>90 85 annual</code> (سنوي: 90 أهداف، 85 كفاءات)\n"
                f"• <code>75 70 probation</code> (فترة التجربة م/53)\n"
                f"• <code>95 90</code> (سنوي افتراضي)"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "appraisal:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
        else:
            ACTIVE_APPRAISAL_WIZARDS[str(chat_id)] = {"mode": "appraisal_emp", "user_id": str(user_id)}
            prompt_text = (
                "🌟 <b>تسجيل وتدقيق تقييم أداء جديد (Dry-Run)</b> 🏢\n"
                "────────────────────\n"
                "أرسل <b>رقم معرّف الموظف (ID)</b> أو جزءاً من اسمه/بريده الإلكتروني للمتابعة:"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "appraisal:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data.startswith("appraisal_approve:"):
        token = data.split(":", 1)[1]
        PENDING_APPRAISAL_CONFIRMATIONS[str(chat_id)] = {
            "token": token,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        bot.answer_callback_query(cq_id, "يلزم تأكيد كتابي للمتابعة")
        confirm_prompt = (
            f"⚠️ <b>تأكيد أمان إلزامي (مبدأ العينين الأربع)</b>\n"
            f"────────────────────\n"
            f"أنت على وشك اعتماد وتسجيل تقييم الأداء رمز <code>{token}</code> فعلياً في Odoo.\n\n"
            f"لحماية العمليات وسجلات المنشأة، اكتب كلمة <b>«تأكيد»</b> في المحادثة للاعتماد والتنفيذ."
        )
        bot.edit_message_text(chat_id, msg_id, confirm_prompt)
        log_telegram_audit(user_id, chat_id, "appraisal_written_confirm_requested", {"token": token})
    elif data == "appraisal:cancel":
        ACTIVE_APPRAISAL_WIZARDS.pop(str(chat_id), None)
        PENDING_APPRAISAL_CONFIRMATIONS.pop(str(chat_id), None)
        show_appraisal_menu(bot, chat_id, message_id=msg_id)
    elif data == "menu:loan":
        show_loan_menu(bot, chat_id, message_id=msg_id)
    elif data == "loan:laws_guide":
        show_loan_laws_guide(bot, chat_id, message_id=msg_id)
    elif data == "loan:prompt" or data.startswith("loan:req_for:"):
        emp_id = None
        if data.startswith("loan:req_for:"):
            try:
                emp_id = int(data.split(":", 2)[2])
            except Exception:
                emp_id = None
        if emp_id:
            ACTIVE_LOAN_WIZARDS[str(chat_id)] = {"mode": "loan_details", "employee_id": emp_id, "user_id": str(user_id)}
            prompt_text = (
                f"💳 <b>بيانات طلب السلفة للموظف #{emp_id}:</b>\n"
                f"────────────────────\n"
                f"أرسل مبلغ السلفة ومدة السداد بالأشهر والقسط مفصولة بمسافات:\n\n"
                f"الصيغة: <code>[مبلغ السلفة] [مدة السداد بالأشهر] [القسط اختياري]</code>\n\n"
                f"أمثلة شائعة:\n"
                f"• <code>6000 6</code> (سلفة 6000 ر.س على 6 أشهر، قسط 1000 ر.س)\n"
                f"• <code>10000 10 1000</code> (سلفة 10000 ر.س على 10 أشهر بقسط محدد)\n"
                f"• <code>15000 12</code> (يتم التحقق تلقائياً من سقف الـ 25% بموجب م/92)"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "loan:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
        else:
            ACTIVE_LOAN_WIZARDS[str(chat_id)] = {"mode": "loan_emp", "user_id": str(user_id)}
            prompt_text = (
                "💳 <b>تسجيل وتدقيق سلفة موظف جديدة (Dry-Run)</b> 🏢\n"
                "────────────────────\n"
                "أرسل <b>رقم معرّف الموظف (ID)</b> أو جزءاً من اسمه/بريده الإلكتروني للمتابعة:"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "loan:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data.startswith("loan_approve:"):
        token = data.split(":", 1)[1]
        PENDING_LOAN_CONFIRMATIONS[str(chat_id)] = {
            "token": token,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        bot.answer_callback_query(cq_id, "يلزم تأكيد كتابي للمتابعة")
        confirm_prompt = (
            f"⚠️ <b>تأكيد أمان إلزامي (مبدأ العينين الأربع)</b>\n"
            f"────────────────────\n"
            f"أنت على وشك اعتماد وتسجيل سلفة الموظف رمز <code>{token}</code> فعلياً في Odoo.\n\n"
            f"لحماية العمليات وسجلات المنشأة، اكتب كلمة <b>«تأكيد»</b> في المحادثة للاعتماد والتنفيذ."
        )
        bot.edit_message_text(chat_id, msg_id, confirm_prompt)
        log_telegram_audit(user_id, chat_id, "loan_written_confirm_requested", {"token": token})
    elif data == "loan:cancel":
        ACTIVE_LOAN_WIZARDS.pop(str(chat_id), None)
        PENDING_LOAN_CONFIRMATIONS.pop(str(chat_id), None)
        show_loan_menu(bot, chat_id, message_id=msg_id)
    elif data == "menu:recruitment":
        show_recruitment_menu(bot, chat_id, message_id=msg_id)
    elif data == "recruit:laws_guide":
        show_saudization_laws_guide(bot, chat_id, message_id=msg_id)
    elif data == "recruit:jobs_list":
        show_recruitment_jobs_list(bot, chat_id, message_id=msg_id)
    elif data == "recruit:prompt" or data.startswith("recruit:for_job:"):
        job_id = None
        if data.startswith("recruit:for_job:"):
            try:
                job_id = int(data.split(":", 2)[2])
            except Exception:
                job_id = None
        if job_id:
            ACTIVE_RECRUITMENT_WIZARDS[str(chat_id)] = {"mode": "recruit_details", "job_id": job_id, "user_id": str(user_id)}
            prompt_text = (
                f"👤 <b>بيانات المرشح للوظيفة #{job_id}:</b>\n"
                f"────────────────────\n"
                f"أرسل اسم المرشح، وجنسيته (سعودي أو وافد)، والراتب المعروض مفصولة بمسافات:\n\n"
                f"الصيغة: <code>[اسم المرشح] [الجنسية: saudi/non_saudi] [الراتب المعروض] [رقم الهوية/الإقامة اختياري]</code>\n\n"
                f"أمثلة:\n"
                f"• <code>فيصل_العتيبي saudi 8000 1012345678</code>\n"
                f"• <code>أحمد_المصري non_saudi 7000 2456789012</code>\n"
                f"• <code>سارة_الغامدي saudi 9500</code>"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "recruit:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
        else:
            ACTIVE_RECRUITMENT_WIZARDS[str(chat_id)] = {"mode": "recruit_job", "user_id": str(user_id)}
            prompt_text = (
                "🎯 <b>تسجيل وتدقيق طلب توظيف جديد (Dry-Run)</b> 🏢\n"
                "────────────────────\n"
                "أرسل <b>رقم معرّف الوظيفة الشاغرة (Job ID)</b> أو جزءاً من اسمها:\n"
                "(مثال: <code>23</code> أو <code>مطوّر برمجيات</code>)"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "recruit:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data.startswith("recruit_approve:"):
        token = data.split(":", 1)[1]
        PENDING_RECRUITMENT_CONFIRMATIONS[str(chat_id)] = {
            "token": token,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        bot.answer_callback_query(cq_id, "يلزم تأكيد كتابي للمتابعة")
        confirm_prompt = (
            f"⚠️ <b>تأكيد أمان إلزامي (مبدأ العينين الأربع)</b>\n"
            f"────────────────────\n"
            f"أنت على وشك اعتماد وتسجيل طلب التوظيف رمز <code>{token}</code> فعلياً في Odoo.\n\n"
            f"لحماية العمليات وسجلات المنشأة، اكتب كلمة <b>«تأكيد»</b> في المحادثة للاعتماد والتنفيذ."
        )
        bot.edit_message_text(chat_id, msg_id, confirm_prompt)
        log_telegram_audit(user_id, chat_id, "recruitment_written_confirm_requested", {"token": token})
    elif data == "recruit:cancel":
        ACTIVE_RECRUITMENT_WIZARDS.pop(str(chat_id), None)
        PENDING_RECRUITMENT_CONFIRMATIONS.pop(str(chat_id), None)
        show_recruitment_menu(bot, chat_id, message_id=msg_id)
    elif data == "menu:contract":
        show_contract_menu(bot, chat_id, message_id=msg_id)
    elif data == "contract:laws_guide":
        show_contract_laws_guide(bot, chat_id, message_id=msg_id)
    elif data == "contract:prompt" or data.startswith("contract:for_emp:"):
        emp_id = None
        if data.startswith("contract:for_emp:"):
            try:
                emp_id = int(data.split(":", 2)[2])
            except Exception:
                emp_id = None
        if emp_id:
            ACTIVE_CONTRACT_WIZARDS[str(chat_id)] = {"mode": "contract_details", "employee_id": emp_id, "user_id": str(user_id)}
            prompt_text = (
                f"👤 <b>هيكلة أجر وعقد الموظف #{emp_id}:</b>\n"
                f"────────────────────\n"
                f"أرسل الأجر الأساسي وبدل السكن وبدل النقل وتاريخ النهاية (لغير السعودي):\n\n"
                f"الصيغة: <code>[الأساسي] [بدل السكن] [بدل النقل] [تاريخ النهاية YYYY-MM-DD للوافد]</code>\n\n"
                f"أمثلة:\n"
                f"• <code>8000 2000 800</code> (للمواطن السعودي - عقد غير محدد)\n"
                f"• <code>6000 1500 600 2027-10-01</code> (للمقيم الوافد - محدد المدة م/37)\n"
                f"• <code>10000</code> (سيتم احتساب 25% سكن و 10% نقل تلقائياً)"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "contract:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
        else:
            ACTIVE_CONTRACT_WIZARDS[str(chat_id)] = {"mode": "contract_emp", "user_id": str(user_id)}
            prompt_text = (
                "📜 <b>تحديث وهيكلة عقد عمل موظف (Dry-Run)</b> 🏢\n"
                "────────────────────\n"
                "أرسل <b>رقم معرّف الموظف (ID)</b> أو جزءاً من اسمه في Odoo:\n"
                "(مثال: <code>100</code> أو <code>عبدالله</code>)"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "contract:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data.startswith("contract_approve:"):
        token = data.split(":", 1)[1]
        PENDING_CONTRACT_CONFIRMATIONS[str(chat_id)] = {
            "token": token,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        bot.answer_callback_query(cq_id, "يلزم تأكيد كتابي للمتابعة")
        confirm_prompt = (
            f"⚠️ <b>تأكيد أمان إلزامي (مبدأ العينين الأربع)</b>\n"
            f"────────────────────\n"
            f"أنت على وشك اعتماد وتحديث عقد العمل رمز <code>{token}</code> فعلياً في Odoo.\n\n"
            f"لحماية العمليات وسجلات المنشأة، اكتب كلمة <b>«تأكيد»</b> في المحادثة للاعتماد والتنفيذ."
        )
        bot.edit_message_text(chat_id, msg_id, confirm_prompt)
        log_telegram_audit(user_id, chat_id, "contract_written_confirm_requested", {"token": token})
    elif data == "contract:cancel":
        ACTIVE_CONTRACT_WIZARDS.pop(str(chat_id), None)
        PENDING_CONTRACT_CONFIRMATIONS.pop(str(chat_id), None)
        show_contract_menu(bot, chat_id, message_id=msg_id)
    elif data == "menu:payroll":
        show_payroll_menu(bot, chat_id, message_id=msg_id)
    elif data == "payroll:laws_guide":
        show_payroll_laws_guide(bot, chat_id, message_id=msg_id)
    elif data == "payroll:prompt" or data.startswith("payroll:for_emp:"):
        emp_id = None
        if data.startswith("payroll:for_emp:"):
            try:
                emp_id = int(data.split(":", 2)[2])
            except Exception:
                emp_id = None
        if emp_id:
            ACTIVE_PAYROLL_WIZARDS[str(chat_id)] = {"mode": "payroll_details", "employee_id": emp_id, "user_id": str(user_id)}
            prompt_text = (
                f"👤 <b>احتساب مسير راتب الموظف #{emp_id}:</b>\n"
                f"────────────────────\n"
                f"أرسل قسط السلفة (إن وجد) وقيمة الخصم التأديبي (إن وجد) مفصولة بمسافة:\n\n"
                f"الصيغة: <code>[قسط السلفة] [الخصم التأديبي]</code>\n\n"
                f"أمثلة:\n"
                f"• <code>0 0</code> (الراتب المعتاد بدون استقطاعات)\n"
                f"• <code>1000 0</code> (خصم قسط سلفة 1000 ر.س)\n"
                f"• <code>500 200</code> (قسط سلفة 500 وخصم تأديبي 200)"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "payroll:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
        else:
            ACTIVE_PAYROLL_WIZARDS[str(chat_id)] = {"mode": "payroll_emp", "user_id": str(user_id)}
            prompt_text = (
                "💵 <b>تدقيق واحتساب مسير راتب موظف (Dry-Run)</b> 🏢\n"
                "────────────────────\n"
                "أرسل <b>رقم معرّف الموظف (ID)</b> أو جزءاً من اسمه في Odoo:\n"
                "(مثال: <code>100</code> أو <code>سعود</code>)"
            )
            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "payroll:cancel"}]]}
            bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data.startswith("payroll_approve:"):
        token = data.split(":", 1)[1]
        PENDING_PAYROLL_CONFIRMATIONS[str(chat_id)] = {
            "token": token,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        bot.answer_callback_query(cq_id, "يلزم تأكيد كتابي للمتابعة")
        confirm_prompt = (
            f"⚠️ <b>تأكيد أمان إلزامي (مبدأ العينين الأربع)</b>\n"
            f"────────────────────\n"
            f"أنت على وشك إنشاء واعتماد قسيمة الراتب رمز <code>{token}</code> فعلياً في Odoo.\n\n"
            f"لحماية العمليات والمسيرات المالية، اكتب كلمة <b>«تأكيد»</b> في المحادثة للاعتماد والتنفيذ."
        )
        bot.edit_message_text(chat_id, msg_id, confirm_prompt)
        log_telegram_audit(user_id, chat_id, "payroll_written_confirm_requested", {"token": token})
    elif data == "payroll:cancel":
        ACTIVE_PAYROLL_WIZARDS.pop(str(chat_id), None)
        PENDING_PAYROLL_CONFIRMATIONS.pop(str(chat_id), None)
        show_payroll_menu(bot, chat_id, message_id=msg_id)
    elif data == "menu:analytics":
        show_analytics_menu(bot, chat_id, message_id=msg_id)
    elif data == "analytics:overview":
        show_analytics_overview_card(bot, chat_id, message_id=msg_id)
    elif data == "analytics:saudization":
        show_analytics_saudization_card(bot, chat_id, message_id=msg_id)
    elif data == "analytics:financial":
        show_analytics_financial_card(bot, chat_id, message_id=msg_id)
    elif data == "analytics:compliance":
        show_analytics_compliance_card(bot, chat_id, message_id=msg_id)
    elif data == "analytics:simulator_prompt":
        ACTIVE_ANALYTICS_WIZARDS[str(chat_id)] = {"mode": "simulate", "user_id": str(user_id)}
        prompt_text = (
            "🎯 <b>محاكي أثر التعيينات على التوطين وبرنامج نطاقات:</b>\n"
            "────────────────────\n"
            "أدخل عدد التعيينات المقترحة: <b>[عدد السعوديين] [عدد غير السعوديين]</b>\n\n"
            "أمثلة:\n"
            "• <code>2 0</code> (تعيين موظفين اثنين سعوديين فقط)\n"
            "• <code>1 3</code> (تعيين سعودي واحد و 3 وافدين)\n"
            "• <code>5 2</code> (تعيين 5 سعوديين واثنين وافدين)"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "analytics:cancel"}]]}
        bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data == "analytics:cancel":
        ACTIVE_ANALYTICS_WIZARDS.pop(str(chat_id), None)
        show_analytics_menu(bot, chat_id, message_id=msg_id)
    elif data == "audit:pdf":
        send_sijil_audit_pdf(bot, chat_id, msg_id)
    elif data == "musleh:info":
        show_musleh_info_card(bot, chat_id, message_id=msg_id)
    elif data == "autofix:status":
        show_autofix_status_card(bot, chat_id, message_id=msg_id)
    elif data == "autofix:enable":
        set_autofix_enabled(chat_id, True)
        bot.answer_callback_query(cq_id, "تم تفعيل الإصلاح التلقائي 🟢")
        show_autofix_status_card(bot, chat_id, message_id=msg_id)
    elif data == "autofix:disable":
        set_autofix_enabled(chat_id, False)
        bot.answer_callback_query(cq_id, "تم تعطيل الإصلاح التلقائي ⏸️")
        show_autofix_status_card(bot, chat_id, message_id=msg_id)
    elif data == "menu:letters":
        show_letter_menu(bot, chat_id, message_id=msg_id)
    elif data.startswith("letter:type:"):
        l_type = data.split(":", 2)[2]
        start_letter_wizard(bot, chat_id, user_id, l_type, message_id=msg_id)
    elif data == "letter:query_prompt":
        ACTIVE_LETTER_WIZARDS[str(chat_id)] = {"step": "query_emp_id", "user_id": str(user_id)}
        prompt_text = (
            "🔍 <b>استعلام الخطابات الصادرة للموظف</b>\n"
            "────────────────────\n"
            "أرسل رقم معرّف الموظف (ID) في Odoo لعرض الخطابات والموافقات السابقة:"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "letter:cancel"}]]}
        bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data.startswith("letter_approve:"):
        token = data.split(":", 1)[1]
        PENDING_LETTER_CONFIRMATIONS[str(chat_id)] = {
            "token": token,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        bot.answer_callback_query(cq_id, "يلزم تأكيد كتابي للمتابعة")
        confirm_prompt = (
            f"⚠️ <b>تأكيد أمان إلزامي (مبدأ العينين الأربع)</b>\n"
            f"────────────────────\n"
            f"أنت على وشك اعتماد وإصدار الخطاب الرسمي رمز <code>{token}</code> فعلياً في Odoo.\n\n"
            f"لحماية العمليات والوثائق الرسمية، اكتب كلمة <b>«تأكيد»</b> في المحادثة للاعتماد والتنفيذ."
        )
        bot.edit_message_text(chat_id, msg_id, confirm_prompt)
        log_telegram_audit(user_id, chat_id, "letter_written_confirm_requested", {"token": token})
    elif data == "letter:cancel":
        ACTIVE_LETTER_WIZARDS.pop(str(chat_id), None)
        PENDING_LETTER_CONFIRMATIONS.pop(str(chat_id), None)
        show_letter_menu(bot, chat_id, message_id=msg_id)
    elif data == "warning:levels_prompt":
        show_warning_levels_menu(bot, chat_id, message_id=msg_id)
    elif data.startswith("warning:level:"):
        w_lvl = data.split(":", 2)[2]
        start_warning_wizard(bot, chat_id, user_id, w_lvl, message_id=msg_id)
    elif data.startswith("warning_approve:"):
        token = data.split(":", 1)[1]
        PENDING_WARNING_CONFIRMATIONS[str(chat_id)] = {
            "token": token,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        bot.answer_callback_query(cq_id, "يلزم تأكيد كتابي للمتابعة")
        confirm_prompt = (
            f"⚠️ <b>تأكيد أمان إلزامي (مبدأ العينين الأربع)</b>\n"
            f"────────────────────\n"
            f"أنت على وشك اعتماد وحفظ خطاب الإنذار رمز <code>{token}</code> فعلياً في Odoo.\n\n"
            f"لحماية العمليات والقرارات التأديبية، اكتب كلمة <b>«تأكيد»</b> في المحادثة للاعتماد والتنفيذ."
        )
        bot.edit_message_text(chat_id, msg_id, confirm_prompt)
        log_telegram_audit(user_id, chat_id, "warning_written_confirm_requested", {"token": token})
    elif data == "warning:cancel":
        ACTIVE_WARNING_WIZARDS.pop(str(chat_id), None)
        PENDING_WARNING_CONFIRMATIONS.pop(str(chat_id), None)
        show_warning_levels_menu(bot, chat_id, message_id=msg_id)
    # Phase 24: Expenses Callbacks
    elif data == "menu:expenses":
        show_expense_menu(bot, chat_id, message_id=msg_id)
    elif data.startswith("expense:cat:"):
        cat = data.split(":", 2)[2]
        start_expense_wizard(bot, chat_id, user_id, cat, message_id=msg_id)
    elif data == "expense:query_prompt":
        ACTIVE_EXPENSE_WIZARDS[str(chat_id)] = {"step": "query_emp_id", "user_id": str(user_id)}
        prompt_text = (
            "🔍 <b>استعلام مصروفات الموظف</b>\n"
            "────────────────────\n"
            "أرسل رقم معرّف الموظف (ID) في Odoo لعرض المصروفات والعهد السابقة:"
        )
        cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": "expense:cancel"}]]}
        bot.edit_message_text(chat_id, msg_id, prompt_text, reply_markup=cancel_kb)
    elif data.startswith("expense_approve:"):
        token = data.split(":", 1)[1]
        PENDING_EXPENSE_CONFIRMATIONS[str(chat_id)] = {
            "token": token,
            "user_id": str(user_id),
            "user_name": user_name,
            "timestamp": time.time(),
        }
        bot.answer_callback_query(cq_id, "يلزم تأكيد كتابي للمتابعة")
        confirm_prompt = (
            f"⚠️ <b>تأكيد أمان إلزامي (مبدأ العينين الأربع)</b>\n"
            f"────────────────────\n"
            f"أنت على وشك اعتماد وقيد مطالبة المصروفات رمز <code>{token}</code> فعلياً في Odoo.\n\n"
            f"لحماية العمليات والمالية، اكتب كلمة <b>«تأكيد»</b> في المحادثة للاعتماد والتنفيذ."
        )
        bot.edit_message_text(chat_id, msg_id, confirm_prompt)
        log_telegram_audit(user_id, chat_id, "expense_written_confirm_requested", {"token": token})
    elif data == "expense:cancel":
        ACTIVE_EXPENSE_WIZARDS.pop(str(chat_id), None)
        PENDING_EXPENSE_CONFIRMATIONS.pop(str(chat_id), None)
        show_expense_menu(bot, chat_id, message_id=msg_id)

    # Phase 25: Expiries Callbacks
    elif data == "menu:expiries":
        show_expiry_menu_card(bot, chat_id, message_id=msg_id, max_days=90)
    elif data.startswith("expiries:filter:"):
        days_str = data.split(":", 2)[2]
        try:
            days = int(days_str)
        except ValueError:
            days = 90
        show_expiry_menu_card(bot, chat_id, message_id=msg_id, max_days=days)
    elif data == "expiries:pdf":
        send_expiry_pdf_report(bot, chat_id, msg_id=msg_id)






def run_telegram_bot_polling(poll_interval: float = 1.5) -> None:
    """Runs the Telegram Bot long-polling service with silent drop for unauthorized users (Section 5.2)."""
    bot = TelegramBotClient()
    if not bot.is_configured():
        print("ERROR: TELEGRAM_BOT_TOKEN is not set in environment or .env file.", file=sys.stderr)
        return

    allowed = get_allowed_users()
    print("=" * 60)
    print("🤖 Odoo HR Interactive Telegram Bot (Phase 7 - Enhanced Seraj)")
    print(f"Token: configured ({bot.token[:8]}...)")
    print(f"Whitelisted Users/Chats: {list(allowed) if allowed else 'WARNING: NONE'}")
    print("Bot is listening for messages, commands, and Excel files ... (Press Ctrl+C to stop)")
    print("=" * 60)

    offset = None
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=10)
            for u in updates:
                offset = u["update_id"] + 1

                # Handle callback queries (Inline Button clicks)
                if "callback_query" in u:
                    cq = u["callback_query"]
                    sender = cq.get("from", {})
                    user_id = sender.get("id")
                    user_name = sender.get("first_name", "") or sender.get("username", "مستخدم")
                    msg = cq.get("message", {})
                    chat_id = msg.get("chat", {}).get("id")
                    msg_id = msg.get("message_id")
                    cq_id = cq.get("id")
                    data = cq.get("data", "")

                    if not is_user_authorized(user_id, chat_id):
                        log_telegram_audit(user_id, chat_id, "silent_drop_unauthorized_callback")
                        continue

                    handle_callback_dispatch(bot, chat_id, user_id, user_name, msg_id, cq_id, data)
                    continue

                # Handle standard messages
                if "message" in u:
                    m = u["message"]
                    sender = m.get("from", {})
                    user_id = sender.get("id")
                    user_name = sender.get("first_name", "") or sender.get("username", "مستخدم")
                    chat = m.get("chat", {})
                    chat_id = chat.get("id")
                    msg_id = m.get("message_id")
                    text = m.get("text", "")

                    if not is_user_authorized(user_id, chat_id):
                        log_telegram_audit(user_id, chat_id, "silent_drop_unauthorized_message", {"text": text})
                        continue

                    # 0. Check for Excel Document Upload (.xlsx)
                    if "document" in m:
                        doc = m["document"]
                        handle_excel_document(bot, chat_id, user_id, user_name, doc, msg_id)
                        continue

                    # 0.0 Voice Notes & Audio processing (Phase 27 - Whisper STT)
                    if "voice" in m or "audio" in m:
                        voice_obj = m.get("voice") or m.get("audio")
                        transcribed = handle_voice_message(bot, chat_id, user_id, user_name, voice_obj, msg_id)
                        if not transcribed:
                            continue
                        text = transcribed

                    if not text:
                        continue

                    clean_text = text.strip().lower()

                    # 0. Handle written confirmation 'تأكيد' (Section 5.1 & Phases 10-24)
                    if clean_text in ("تأكيد", "تاكيد", "confirm") or clean_text.startswith("تأكيد ") or clean_text.startswith("تاكيد "):
                        parts = text.strip().split()
                        explicit_token = parts[1].strip() if len(parts) > 1 else ""

                        if explicit_token:
                            if explicit_token.startswith("LEAVE-"):
                                execute_leave_via_service(bot, chat_id, explicit_token, msg_id)
                                continue
                            elif explicit_token.startswith("ATTEND-"):
                                execute_attendance_action_via_service(bot, chat_id, {"token": explicit_token, "employee_id": 0, "action_type": "CREATE_RECORD"}, msg_id)
                                continue
                            elif explicit_token.startswith("DISC-"):
                                execute_disciplinary_action_via_service(bot, chat_id, explicit_token, msg_id)
                                continue
                            elif explicit_token.startswith("EOS-"):
                                execute_eos_settlement_via_service(bot, chat_id, explicit_token, msg_id)
                                continue
                            elif explicit_token.startswith("APR-"):
                                execute_appraisal_via_service(bot, chat_id, explicit_token, msg_id)
                                continue
                            elif explicit_token.startswith("LOAN-"):
                                execute_loan_via_service(bot, chat_id, explicit_token, msg_id)
                                continue
                            elif explicit_token.startswith("APP-"):
                                execute_applicant_via_service(bot, chat_id, explicit_token, msg_id)
                                continue
                            elif explicit_token.startswith("CTR-"):
                                execute_contract_via_service(bot, chat_id, explicit_token, msg_id)
                                continue
                            elif explicit_token.startswith("PAY-"):
                                execute_payslip_via_service(bot, chat_id, explicit_token, msg_id)
                                continue
                            elif explicit_token.startswith("EXP-"):
                                execute_expense_via_service(bot, chat_id, explicit_token, msg_id)
                                continue
                            elif explicit_token.startswith("WARN-"):
                                execute_warning_via_service(bot, chat_id, explicit_token, msg_id)
                                continue

                        pending_expense = PENDING_EXPENSE_CONFIRMATIONS.pop(str(chat_id), None)
                        if pending_expense:
                            execute_expense_via_service(bot, chat_id, pending_expense["token"], msg_id)
                            continue

                        pending_warning = PENDING_WARNING_CONFIRMATIONS.pop(str(chat_id), None)
                        if pending_warning:
                            execute_warning_via_service(bot, chat_id, pending_warning["token"], msg_id)
                            continue

                        pending_letter = PENDING_LETTER_CONFIRMATIONS.pop(str(chat_id), None)
                        if pending_letter:
                            execute_letter_via_service(bot, chat_id, pending_letter["token"], msg_id)
                            continue

                        pending_payroll = PENDING_PAYROLL_CONFIRMATIONS.pop(str(chat_id), None)
                        if pending_payroll:
                            execute_payslip_via_service(bot, chat_id, pending_payroll["token"], msg_id)
                            continue

                        pending_contract = PENDING_CONTRACT_CONFIRMATIONS.pop(str(chat_id), None)
                        if pending_contract:
                            execute_contract_via_service(bot, chat_id, pending_contract["token"], msg_id)
                            continue

                        pending_recruit = PENDING_RECRUITMENT_CONFIRMATIONS.pop(str(chat_id), None)
                        if pending_recruit:
                            execute_applicant_via_service(bot, chat_id, pending_recruit["token"], msg_id)
                            continue

                        pending_loan = PENDING_LOAN_CONFIRMATIONS.pop(str(chat_id), None)
                        if pending_loan:
                            execute_loan_via_service(bot, chat_id, pending_loan["token"], msg_id)
                            continue

                        pending_app = PENDING_APPRAISAL_CONFIRMATIONS.pop(str(chat_id), None)
                        if pending_app:
                            execute_appraisal_via_service(bot, chat_id, pending_app["token"], msg_id)
                            continue

                        pending_gr = PENDING_GR_CONFIRMATIONS.pop(str(chat_id), None)
                        if pending_gr:
                            execute_gr_transaction_via_service(bot, chat_id, pending_gr["token"], msg_id)
                            continue

                        pending_eos = PENDING_EOS_CONFIRMATIONS.pop(str(chat_id), None)
                        if pending_eos:
                            execute_eos_settlement_via_service(bot, chat_id, pending_eos["token"], msg_id)
                            continue

                        pending_disc = PENDING_DISCIPLINARY_CONFIRMATIONS.pop(str(chat_id), None)
                        if pending_disc:
                            execute_disciplinary_action_via_service(bot, chat_id, pending_disc["token"], msg_id)
                            continue

                        pending_att = PENDING_ATTENDANCE_CONFIRMATIONS.pop(str(chat_id), None)
                        if pending_att:
                            execute_attendance_action_via_service(bot, chat_id, pending_att, msg_id)
                            continue

                        pending_leave = PENDING_LEAVE_CONFIRMATIONS.pop(str(chat_id), None)
                        if pending_leave:
                            execute_leave_via_service(bot, chat_id, pending_leave["token"], msg_id)
                            continue

                        pending = PENDING_CONFIRMATIONS.pop(str(chat_id), None)
                        if pending:
                            execute_via_backend_api(
                                bot,
                                chat_id,
                                pending["user_id"],
                                pending["user_name"],
                                pending["run_id"],
                                msg_id,
                            )
                            continue

                        # Check if Seraj has an approved pending action (e.g. deletion plan or write action)
                        try:
                            from seraj_session_manager import SerajSessionManager
                            active_seraj_session = SerajSessionManager.get_instance().get_session(chat_id)
                            if active_seraj_session.pending_action:
                                from seraj_llm_service import SerajLLMService
                                seraj_llm = SerajLLMService()
                                if seraj_llm.is_configured():
                                    ai_answer = seraj_llm.chat_turn(
                                        user_query=text,
                                        chat_id=str(chat_id),
                                        user_name=user_name,
                                    )
                                    if ai_answer:
                                        bot.send_message(
                                            chat_id,
                                            f"🤖 <b>سراج (المساعد الذكي):</b>\n────────────────────\n{ai_answer}\n\n💡 <i>(للوصول السريع للقوائم كأزرار تفاعلية، أرسل «أزرار»)</i>",
                                            reply_to_message_id=msg_id,
                                        )
                                        continue
                        except Exception as e_seraj_act:
                            logger.warning(f"Error executing pending Seraj action: {e_seraj_act}")

                        if clean_text in ("تأكيد", "تاكيد", "confirm"):
                            bot.send_message(
                                chat_id,
                                "ℹ️ لا توجد عملية معلقة بانتظار التأكيد حالياً.",
                                reply_to_message_id=msg_id,
                            )
                            continue

                    # Global Cancel / Reset Interceptor
                    clean_text = text.strip()
                    if clean_text in ("/cancel", "/start", "الغاء", "إلغاء", "تراجع", "خروج", "cancel", "reset"):
                        for wiz_dict in (
                            ACTIVE_CONFIG_WIZARDS, ACTIVE_LEAVE_WIZARDS, ACTIVE_ATTENDANCE_WIZARDS,
                            ACTIVE_DISCIPLINARY_WIZARDS, ACTIVE_EOS_WIZARDS, ACTIVE_GR_WIZARDS,
                            ACTIVE_APPRAISAL_WIZARDS, ACTIVE_LOAN_WIZARDS, ACTIVE_RECRUITMENT_WIZARDS,
                            ACTIVE_CONTRACT_WIZARDS, ACTIVE_PAYROLL_WIZARDS, ACTIVE_ANALYTICS_WIZARDS,
                            ACTIVE_LETTER_WIZARDS, ACTIVE_WARNING_WIZARDS, ACTIVE_EXPENSE_WIZARDS
                        ):
                            wiz_dict.pop(str(chat_id), None)

                        # Handle Seraj pending action cancellation
                        try:
                            from seraj_session_manager import SerajSessionManager
                            s_sess = SerajSessionManager.get_instance().get_session(chat_id)
                            if s_sess.pending_action:
                                from seraj_llm_service import SerajLLMService
                                seraj_llm = SerajLLMService()
                                if seraj_llm.is_configured() and clean_text in ("الغاء", "إلغاء", "تراجع", "cancel"):
                                    ai_answer = seraj_llm.chat_turn(
                                        user_query=text,
                                        chat_id=str(chat_id),
                                        user_name=user_name,
                                    )
                                    if ai_answer:
                                        bot.send_message(
                                            chat_id,
                                            f"🤖 <b>سراج (المساعد الذكي):</b>\n────────────────────\n{ai_answer}\n\n💡 <i>(للوصول السريع للقوائم كأزرار تفاعلية، أرسل «أزرار»)</i>",
                                            reply_to_message_id=msg_id,
                                        )
                                        continue
                                s_sess.clear_pending_action()
                        except Exception:
                            pass

                        if clean_text in ("/start", "ابدأ"):
                            show_main_menu(bot, chat_id, user_name)
                        else:
                            bot.send_message(
                                chat_id,
                                "✅ تم إلغاء العملية والعودة للقائمة الرئيسية بنجاح.",
                                reply_markup=get_main_menu_keyboard(),
                                reply_to_message_id=msg_id,
                            )
                        continue

                    # إذا أرسل المستخدم استفساراً عاماً أو سؤالاً موجهاً لسراج، نفرغ المعالجات الفرعية المعلقة ليتولى سراج الرد
                    is_inquiry_or_question = (
                        "؟" in text or "?" in text
                        or any(kw in text for kw in [
                            "كم", "ما هي", "ماهي", "ما هو", "ماهو", "هل", "شرح", "وضح", "كيف", "لماذا", "متى",
                            "نظام العمل", "المادة", "مادة", "قانون", "حقوق", "احسب", "حسبة", "ما حكم", "ماحكم", "شروط",
                            "رصيد", "استعلام", "استعلم", "ابحث", "احذف", "حذف", "تقديم", "طلب", "تسوية", "مكافأة", "مكافاة",
                            "اوفرتايم", "أوفرتايم", "إضافي", "اضافي", "سلفة", "قرض", "تجربة", "مخالفة", "جزاء", "حسم",
                            "إجازة", "اجازة", "وضع", "أمومة", "امومة", "أبوة", "ابوة", "تأمينات", "gosi", "عقد", "وثائق", "اقامة", "إقامة"
                        ])
                    )
                    if is_inquiry_or_question:
                        for wiz_dict in (
                            ACTIVE_LEAVE_WIZARDS, ACTIVE_ATTENDANCE_WIZARDS,
                            ACTIVE_DISCIPLINARY_WIZARDS, ACTIVE_EOS_WIZARDS, ACTIVE_GR_WIZARDS,
                            ACTIVE_APPRAISAL_WIZARDS, ACTIVE_LOAN_WIZARDS, ACTIVE_RECRUITMENT_WIZARDS,
                            ACTIVE_CONTRACT_WIZARDS, ACTIVE_PAYROLL_WIZARDS, ACTIVE_ANALYTICS_WIZARDS,
                            ACTIVE_LETTER_WIZARDS, ACTIVE_WARNING_WIZARDS, ACTIVE_EXPENSE_WIZARDS
                        ):
                            wiz_dict.pop(str(chat_id), None)

                    # 0. Check if user is in an active leave wizard
                    if handle_leave_wizard_step(bot, chat_id, user_id, user_name, text, msg_id):
                        continue

                    # 0.1 Check if user is in an active attendance wizard
                    if handle_attendance_wizard_step(bot, chat_id, user_id, user_name, text, msg_id):
                        continue

                    # 0.2 Check if user is in an active disciplinary wizard
                    if handle_disciplinary_wizard_step(bot, chat_id, user_id, user_name, text, msg_id):
                        continue

                    # 0.3 Check if user is in an active EOS wizard (Phase 13)
                    if handle_eos_wizard_step(bot, chat_id, user_id, user_name, text, msg_id):
                        continue

                    # 0.4 Check if user is in an active GR wizard (Phase 14)
                    if handle_gr_wizard_step(bot, chat_id, user_id, user_name, text, msg_id):
                        continue

                    # 0.5 Check if user is in an active Appraisal wizard (Phase 15)
                    if handle_appraisal_wizard_step(bot, chat_id, user_id, user_name, text, msg_id):
                        continue

                    # 0.6 Check if user is in an active Loan wizard (Phase 16)
                    if handle_loan_wizard_step(bot, chat_id, user_id, user_name, text, msg_id):
                        continue

                    # 0.7 Check if user is in an active Recruitment wizard (Phase 17)
                    if handle_recruitment_wizard_step(bot, chat_id, user_id, user_name, text, msg_id):
                        continue

                    # 0.8 Check if user is in an active Contract wizard (Phase 18)
                    if handle_contract_wizard_step(bot, chat_id, user_id, user_name, text, msg_id):
                        continue

                    # 0.9 Check if user is in an active Payroll wizard (Phase 19)
                    if handle_payroll_wizard_step(bot, chat_id, user_id, user_name, text, msg_id):
                        continue

                    # 0.10 Check if user is in an active Analytics Simulator wizard (Phase 20)
                    if handle_analytics_wizard_step(bot, chat_id, user_id, user_name, text, msg_id):
                        continue

                    # 0.11 Check if user is in an active Letter wizard (Phase 22)
                    if handle_letter_wizard_step(bot, chat_id, user_id, user_name, text, msg_id):
                        continue

                    # 0.12 Check if user is in an active Warning wizard (Phase 23)
                    if handle_warning_wizard_step(bot, chat_id, user_id, user_name, text, msg_id):
                        continue

                    # 0.13 Check if user is in an active Expense wizard (Phase 24)
                    if handle_expense_wizard_step(bot, chat_id, user_id, user_name, text, msg_id):
                        continue

                    # 1. Check if user is in an active setup wizard
                    if handle_config_wizard_step(bot, chat_id, user_id, user_name, text, msg_id):
                        continue



                    # 2.0.0.0.0.0.0.0.0.0.0.0.0 Document Expiry Monitoring commands (Phase 25)
                    if any(clean_text.startswith(cmd) for cmd in ("/expir", "/doc", "صلاحيات", "وثائق", "انتهاء_الاقامة", "انتهاء_الجواز", "صلاحية", "تنبيهات_الوثائق")):
                        show_expiry_menu_card(bot, chat_id)
                        continue

                    # 2.0.0.0.0.0.0.0.0.0.0.0 Employee Expenses & Travel commands (Phase 24)
                    if any(clean_text.startswith(cmd) for cmd in ("/expense", "/expenses", "مصروف", "مصروفات", "انتداب", "انتدابات", "عهدة", "عهد", "سفر")):
                        show_expense_menu(bot, chat_id)
                        continue

                    # 2.0.0.0.0.0.0.0.0.0.0 Disciplinary Warning Letters commands (Phase 23)
                    if any(clean_text.startswith(cmd) for cmd in ("/warning", "/warnings", "خطاب إنذار", "خطاب انذار", "لفت نظر", "إنذار رسمي", "انذار رسمي")):
                        show_warning_levels_menu(bot, chat_id)
                        continue

                    # 2.0.0.0.0.0.0.0.0.0 HR Official Letters commands (Phase 22)
                    if any(clean_text.startswith(cmd) for cmd in ("/letter", "/letters", "/cert", "/certificate", "خطاب", "خطابات", "شهادة", "شهاده", "تعريف", "تثبيت راتب")):
                        show_letter_menu(bot, chat_id)
                        continue


                    # 2.0.0.0.0.0.0.0 Sijil Audit PDF commands (Phase 21)
                    if any(clean_text.startswith(cmd) for cmd in ("/audit", "/sijil", "/pdf", "سجل", "تقرير الرقابة", "تقرير التدقيق", "تقرير سجل")):
                        send_sijil_audit_pdf(bot, chat_id, msg_id)
                        continue


                    # 2.0.0.0.0.0.0.0.0.0 Musleh & Autofix commands (Phase 26)
                    if any(clean_text.startswith(cmd) for cmd in ("/autofix", "/repair", "/musleh", "اصلاح تلقائي", "إصلاح تلقائي", "مصلح")):
                        parts = clean_text.split()
                        if len(parts) >= 2 and parts[0] in ("/autofix", "/repair"):
                            sub = parts[1].lower()
                            if sub in ("on", "enable", "1", "true", "تفعيل"):
                                set_autofix_enabled(chat_id, True)
                                log_telegram_audit(user_id, chat_id, "autofix_enabled", {"enabled": True})
                                bot.send_message(
                                    chat_id,
                                    "🟢 <b>تم تفعيل الإصلاح التلقائي بنجاح! (<code>/autofix on</code>)</b>\n"
                                    "────────────────────\n"
                                    "سيقوم وكيل «مصلح» الآن بمعالجة وتصحيح الأخطاء القابلة للعلاج (تواريخ، أرقام هواتف، إيميلات، ومطابقة ضبابية بنسبة ثقة ≥ 90%) تلقائياً وتجهيز الصفوف للإنشاء فوراً.\n\n"
                                    "🔒 <i>صمام الأمان: أرقام الهويات الوطنية والإقامات مستثناة وتظل دائماً خاضعة للقرار البشري.</i>",
                                    reply_to_message_id=msg_id,
                                )
                                continue
                            elif sub in ("off", "disable", "0", "false", "تعطيل"):
                                set_autofix_enabled(chat_id, False)
                                log_telegram_audit(user_id, chat_id, "autofix_disabled", {"enabled": False})
                                bot.send_message(
                                    chat_id,
                                    "⏸️ <b>تم تعطيل الإصلاح التلقائي! (<code>/autofix off</code>)</b>\n"
                                    "────────────────────\n"
                                    "المنظومة الآن في <b>وضع المراجعة فقط (Review Only)</b>.\n"
                                    "سيقوم «مصلح» بالتشخيص وعزل الصفوف المعطوبة وتوليد التوصيات وإحالتها لسراج دون تطبيق أي تصحيح تلقائي إلا بعد موافقتك.",
                                    reply_to_message_id=msg_id,
                                )
                                continue

                        if any(clean_text.startswith(cmd) for cmd in ("/musleh", "مصلح")):
                            show_musleh_info_card(bot, chat_id, message_id=None)
                        else:
                            show_autofix_status_card(bot, chat_id, message_id=None)
                        continue

                    # 2.0.0.0.0.0.0 Analytics & Executive Dashboard commands (Phase 20)
                    if any(clean_text.startswith(cmd) for cmd in ("/analytics", "/dashboard", "/kpi", "مؤشرات", "تحليلات", "لوحة", "داشبورد", "نطاقات")):
                        show_analytics_menu(bot, chat_id)
                        continue

                    # 2.0.0.0.0.0 Payroll commands (Phase 19)
                    if any(clean_text.startswith(cmd) for cmd in ("/payroll", "/payslip", "/wps", "مسير", "مسيرات", "رواتب", "حماية_الاجور", "مدد")):
                        show_payroll_menu(bot, chat_id)
                        continue

                    # 2.0.0.0.0 Contract commands (Phase 18)
                    if any(clean_text.startswith(cmd) for cmd in ("/contract", "/wage", "عقد", "عقود", "راتب", "رواتب", "أجر", "اجر", "بدلات")):
                        show_contract_menu(bot, chat_id)
                        continue

                    # 2.0.0.0 Recruitment commands (Phase 17)
                    if any(clean_text.startswith(cmd) for cmd in ("/recruit", "/recruitment", "/job", "توظيف", "مرشح", "شواغر", "سعودة", "توطين")):
                        show_recruitment_menu(bot, chat_id)
                        continue

                    # 2.0.0 Loan commands (Phase 16)
                    if any(clean_text.startswith(cmd) for cmd in ("/loan", "/advance", "سلفة", "سلفه", "سلف", "قرض", "قروض")):
                        show_loan_menu(bot, chat_id)
                        continue

                    # 2.0 Appraisal commands (Phase 15)
                    if any(clean_text.startswith(cmd) for cmd in ("/appraisal", "/evaluation", "تقييم", "تقييمات", "أداء", "اداء")):
                        show_appraisal_menu(bot, chat_id)
                        continue

                    # 2.1 Government Relations commands (Phase 14)
                    if any(clean_text.startswith(cmd) for cmd in ("/gr", "/iqama", "/visa", "حكومية", "معاملات", "مقيم", "قوى", "جوازات", "إقامة", "اقامة", "فيزا", "تأشيرة", "تاشيرة")):
                        show_gr_menu(bot, chat_id)
                        continue

                    # 2.2 End of Service commands (Phase 13)
                    if any(clean_text.startswith(cmd) for cmd in ("/eos", "/settlement", "نهاية الخدمة", "نهايه الخدمه", "تسوية", "تسويات", "مكافأة", "مكافاة")):
                        show_eos_menu(bot, chat_id)
                        continue

                    # 2.3 Disciplinary commands
                    if any(clean_text.startswith(cmd) for cmd in ("/disciplinary", "/penalty", "جزاءات", "انضباط", "مخالفة", "مخالفات", "جزاء", "إنذار", "انذار")):
                        show_disciplinary_menu(bot, chat_id)
                        continue

                    # 2.4 Attendance commands
                    if any(clean_text.startswith(cmd) for cmd in ("/attendance", "/attend", "حضور", "دوام", "انصراف", "اوفرتايم", "اضافي", "إضافي")):
                        show_attendance_menu(bot, chat_id)
                        continue

                    # 2.5 Leaves commands
                    if any(clean_text.startswith(cmd) for cmd in ("/leave", "/leaves", "إجازات", "اجازات", "إجازة", "اجازة")):
                        show_leaves_menu(bot, chat_id)
                        continue

                    # 2.6 Inquiry check & Greetings / conversational openers
                    is_inquiry_or_question = (
                        "؟" in text or "?" in text
                        or any(kw in text for kw in [
                            "كم", "ما هي", "ماهي", "ما هو", "ماهو", "هل", "شرح", "وضح", "كيف", "لماذا", "متى",
                            "نظام العمل", "المادة", "مادة", "قانون", "حقوق", "احسب", "حسبة", "ما حكم", "ماحكم", "شروط",
                            "رصيد", "استعلام", "استعلم", "ابحث", "احذف", "حذف", "تقديم", "طلب", "تسوية", "مكافأة", "مكافاة",
                            "اوفرتايم", "أوفرتايم", "إضافي", "اضافي", "سلفة", "قرض", "تجربة", "مخالفة", "جزاء", "حسم",
                            "إجازة", "اجازة", "وضع", "أمومة", "امومة", "أبوة", "ابوة", "تأمينات", "gosi", "عقد", "وثائق", "اقامة", "إقامة"
                        ])
                    )

                    greeting_triggers = (
                        "الو", "ألو", "الوو", "الووو", "ألوو", "اهلين", "أهلين",
                        "السلام عليكم", "سلام عليكم", "صباح الخير", "مساء الخير",
                        "يا سراج", "تسمعني", "هل تسمعني"
                    )
                    if not is_inquiry_or_question and (clean_text in greeting_triggers or (len(clean_text.split()) <= 3 and any(clean_text.startswith(cmd) for cmd in greeting_triggers))):
                        greeting_msg = (
                            f"🎙️ <b>أهلاً بك يا {user_name}! معك «سراج» مساعد الموارد البشرية الذكي.</b>\n"
                            f"────────────────────\n"
                            f"أسمعك بكل وضوح 👂✨ تفضل، كيف يمكنني خدمتك اليوم؟\n\n"
                            f"💡 <i>يمكنك سؤالي مباشرة عن نظام العمل أو استعلامات موظفي Odoo كتابةً أو صوتاً.</i>\n"
                            f"<i>(إذا كنت تفضل استخدام الأزرار والقوائم السريعة، اكتب فقط «أزرار» أو «القائمة»)</i>"
                        )
                        bot.send_message(
                            chat_id,
                            greeting_msg,
                            reply_to_message_id=msg_id,
                        )
                        continue

                    # 2.9 Check if user is responding to a pending Seraj clarification (e.g. «الشركة الثانية»)
                    try:
                        from seraj_session_manager import SerajSessionManager
                        active_seraj_session = SerajSessionManager.get_instance().get_session(chat_id)
                        if active_seraj_session.pending_clarification:
                            from seraj_llm_service import SerajLLMService
                            seraj_llm = SerajLLMService()
                            if seraj_llm.is_configured():
                                ai_answer = seraj_llm.chat_turn(
                                    user_query=text,
                                    chat_id=str(chat_id),
                                    user_name=user_name,
                                )
                                if ai_answer:
                                    bot.send_message(
                                        chat_id,
                                        f"🤖 <b>سراج (المساعد الذكي):</b>\n────────────────────\n{ai_answer}\n\n💡 <i>(للوصول السريع للقوائم كأزرار تفاعلية، أرسل «أزرار»)</i>",
                                        reply_to_message_id=msg_id,
                                    )
                                    continue
                    except Exception as e_clar:
                        logger.warning(f"Error handling pending Seraj clarification: {e_clar}")

                    # 3. Start or Menu commands (Strictly explicit request for buttons/menu)
                    explicit_menu_commands = ("/start", "/help", "/menu", "القائمة", "قائمة", "أزرار", "ازرار", "خيارات", "menu", "buttons")
                    if not is_inquiry_or_question and (clean_text in explicit_menu_commands or any(clean_text == cmd for cmd in explicit_menu_commands)):
                        show_main_menu(bot, chat_id, user_name, message_id=None)
                        continue

                    # 4. Templates command
                    if any(clean_text.startswith(cmd) for cmd in ("/template", "/templates", "قوالب", "قالب", "تيمبليت", "تيمبلت")):
                        bot.send_message(
                            chat_id,
                            "📥 <b>مستودع قوالب الموارد البشرية:</b>\nاختر القالب المطلوب ليتم إرساله لك فوراً:",
                            reply_markup=get_templates_menu_keyboard(),
                            reply_to_message_id=msg_id,
                        )
                        continue

                    # 4.1 Fahas live companies & branches inspection command
                    if any(clean_text.startswith(cmd) for cmd in ("/companies", "/fahas", "فاحص", "الشركات", "الفروع", "استعراض الشركات", "تصفح الشركات")):
                        show_companies_branches(bot, chat_id, message_id=None)
                        continue

                    # 5. Connect and Setup commands
                    if any(clean_text.startswith(cmd) for cmd in ("/connect", "/setup", "/odoo", "اتصال", "اودو", "ربط", "تغيير الربط", "ربط قاعدة")):
                        parts = text.strip().split()
                        if len(parts) >= 5 and parts[0].startswith(("/connect", "/setup")):
                            q_url, q_db, q_user, q_key = parts[1], parts[2], parts[3], parts[4]
                            bot.send_message(chat_id, "⏳ <b>جارِ فحص واختبار بيانات الاتصال السريع بـ Odoo...</b>", reply_to_message_id=msg_id)
                            t_res = test_odoo_connection(q_url, q_db, q_user, q_key)
                            if t_res.get("ok"):
                                save_active_odoo_config(q_url, q_db, q_user, q_key)
                                bot.send_message(
                                    chat_id,
                                    f"🎉 <b>تم الاتصال بنجاح بـ Odoo!</b>\nUID: <code>{t_res.get('uid')}</code> | منشآت: <b>{t_res.get('company_count')}</b> | موظفون: <b>{t_res.get('employee_count', 0)}</b> | أقسام: <b>{t_res.get('department_count', 0)}</b>",
                                    reply_to_message_id=msg_id,
                                )
                            else:
                                bot.send_message(
                                    chat_id,
                                    f"❌ <b>فشل الاتصال:</b> <code>{t_res.get('error')}</code>",
                                    reply_to_message_id=msg_id,
                                )
                            continue

                        if any(clean_text.startswith(cmd) for cmd in ("/setup", "ربط قاعدة", "تغيير الربط", "ربط اودو")):
                            ACTIVE_CONFIG_WIZARDS[str(chat_id)] = {"step": "url", "user_id": str(user_id)}
                            prompt_text = (
                                "🔗 <b>معالج ربط قاعدة بيانات Odoo لسراج</b> 🏢\n"
                                "────────────────────\n"
                                "أهلاً بك! سنقوم بإعداد الربط عبر 4 خطوات:\n"
                                "1️⃣ الرابط (URL)\n2️⃣ اسم القاعدة (DB)\n3️⃣ المستخدم (User)\n4️⃣ مفتاح API (Key)\n\n"
                                "🌐 <b>الخطوة 1 من 4:</b>\n"
                                "يرجى إرسال <b>رابط خادم Odoo</b> الآن في المحادثة:\n"
                                "(مثال: <code>https://my-company.odoo.com</code>)"
                            )
                            cancel_kb = {"inline_keyboard": [[{"text": "❌ إلغاء المعالج", "callback_data": "wizard:cancel"}]]}
                            bot.send_message(chat_id, prompt_text, reply_markup=cancel_kb, reply_to_message_id=msg_id)
                            continue

                        show_odoo_settings_card(bot, chat_id)
                        continue

                    # 5.1 Seraj as Primary Conversational Interface and Orchestrator
                    # Handles natural requests,
                    # executes live Odoo queries (Read-Only), and enforces write governance.
                    try:
                        from seraj_llm_service import SerajLLMService
                        seraj_llm = SerajLLMService()
                        if seraj_llm.is_configured():
                            ai_answer = seraj_llm.chat_turn(
                                user_query=text,
                                chat_id=str(chat_id),
                                user_name=user_name,
                            )
                            if ai_answer:
                                bot.send_message(
                                    chat_id,
                                    f"🤖 <b>سراج (المساعد الذكي):</b>\n────────────────────\n{ai_answer}\n\n💡 <i>(للوصول السريع للقوائم كأزرار تفاعلية، أرسل «أزرار»)</i>",
                                    reply_to_message_id=msg_id,
                                )
                                continue
                    except Exception as e_llm:
                        logger.warning(f"Seraj LLM response generation failed: {e_llm}")

                    # 5.3 Fallback for explicit domain menu requests with buttons
                    if any(w in clean_text for w in ("أزرار", "ازرار", "قائمة", "menu", "buttons")):
                        if decision.domain == "leaves":
                            show_leaves_menu(bot, chat_id)
                            continue
                        elif decision.domain == "attendance":
                            show_attendance_menu(bot, chat_id)
                            continue
                        elif decision.domain == "contracts":
                            show_contract_menu(bot, chat_id)
                            continue
                        elif decision.domain == "payroll":
                            show_payroll_menu(bot, chat_id)
                            continue
                        elif decision.domain == "disciplinary":
                            show_disciplinary_menu(bot, chat_id)
                            continue
                        elif decision.domain == "eos":
                            show_eos_menu(bot, chat_id)
                            continue
                        elif decision.domain == "loans":
                            show_loan_menu(bot, chat_id)
                            continue
                        elif decision.domain == "gr":
                            show_gr_menu(bot, chat_id)
                            continue
                        elif decision.domain == "appraisal":
                            show_appraisal_menu(bot, chat_id)
                            continue
                        elif decision.domain == "recruitment":
                            show_recruitment_menu(bot, chat_id)
                            continue
                        elif decision.domain == "analytics":
                            show_analytics_menu(bot, chat_id)
                            continue
                        elif decision.domain == "audit":
                            send_sijil_audit_pdf(bot, chat_id, msg_id)
                            continue
                        elif decision.domain == "letters":
                            show_letter_menu(bot, chat_id)
                            continue
                        elif decision.domain == "expenses":
                            show_expense_menu(bot, chat_id)
                            continue
                        elif decision.domain == "expiries":
                            show_expiry_menu_card(bot, chat_id)
                            continue

                    bot.send_message(
                        chat_id,
                        f"💡 <b>فهمتُ استفسارك:</b> «<i>{text}</i>»\n\n"
                        "هل تود استعراض خيارات الأقسام كأزرار؟ أرسل «أزرار» أو «القائمة» في أي وقت.",
                        reply_to_message_id=msg_id,
                    )
                    continue

        except KeyboardInterrupt:
            print("\nTelegram bot stopped by user.")
            break
        except Exception as exc:
            print(f"Polling warning: {type(exc).__name__}: {exc}", file=sys.stderr)
            time.sleep(poll_interval)


if __name__ == "__main__":
    run_telegram_bot_polling()
