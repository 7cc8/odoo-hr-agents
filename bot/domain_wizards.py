"""Domain service adapters, wizards, and inspection cards for the 13 HR modules."""
from __future__ import annotations

import os
import sys
import json
import time
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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





from odoo_config_manager import get_active_odoo_config

from bot.client import (
    TelegramBotClient,
    get_tb_symbol,
    log_telegram_audit,
    is_autofix_enabled,
    PENDING_CONFIRMATIONS,
    PENDING_LEAVE_CONFIRMATIONS,
    ACTIVE_LEAVE_WIZARDS,
    PENDING_ATTENDANCE_CONFIRMATIONS,
    ACTIVE_ATTENDANCE_WIZARDS,
    PENDING_DISCIPLINARY_CONFIRMATIONS,
    ACTIVE_DISCIPLINARY_WIZARDS,
    PENDING_EOS_CONFIRMATIONS,
    ACTIVE_EOS_WIZARDS,
    PENDING_GR_CONFIRMATIONS,
    ACTIVE_GR_WIZARDS,
    PENDING_APPRAISAL_CONFIRMATIONS,
    ACTIVE_APPRAISAL_WIZARDS,
    PENDING_LOAN_CONFIRMATIONS,
    ACTIVE_LOAN_WIZARDS,
    PENDING_RECRUITMENT_CONFIRMATIONS,
    ACTIVE_RECRUITMENT_WIZARDS,
    PENDING_CONTRACT_CONFIRMATIONS,
    ACTIVE_CONTRACT_WIZARDS,
    PENDING_PAYROLL_CONFIRMATIONS,
    ACTIVE_PAYROLL_WIZARDS,
    ACTIVE_ANALYTICS_WIZARDS,
    PENDING_LETTER_CONFIRMATIONS,
    ACTIVE_LETTER_WIZARDS,
    PENDING_WARNING_CONFIRMATIONS,
    ACTIVE_WARNING_WIZARDS,
    PENDING_EXPENSE_CONFIRMATIONS,
    ACTIVE_EXPENSE_WIZARDS,
    AUTOFIX_ENABLED_BY_CHAT,
    DEFAULT_COMPANY_ID,
    DEFAULT_MAX_ROWS,
)
from bot.keyboards import get_main_menu_keyboard, get_templates_menu_keyboard
from bot.media_handlers import execute_via_backend_api

# =============================================================================
# وظائف إدارة الإجازات ونظام العمل السعودي (Phase 10: Leaves Management)
# =============================================================================

_BOT_LEAVE_SERVICE: Optional[LeaveService] = None

def get_leave_service_for_bot(force_refresh: bool = False) -> LeaveService:
    target = get_tb_symbol("get_leave_service_for_bot")
    if target is not None and target is not get_leave_service_for_bot:
        return target(force_refresh=force_refresh)
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
    target = get_tb_symbol("show_employee_leaves_balance")
    if target is not None and target is not show_employee_leaves_balance:
        if message_id is not None:
            return target(bot, chat_id, employee_id, message_id=message_id)
        return target(bot, chat_id, employee_id)
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
    target = get_tb_symbol("get_attendance_service_for_bot")
    if target is not None and target is not get_attendance_service_for_bot:
        return target(force_refresh=force_refresh)
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
    target = get_tb_symbol("get_disciplinary_service_for_bot")
    if target is not None and target is not get_disciplinary_service_for_bot:
        return target(force_refresh=force_refresh)
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
    target = get_tb_symbol("get_eos_service_for_bot")
    if target is not None and target is not get_eos_service_for_bot:
        return target(force_refresh=force_refresh)
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
    target = get_tb_symbol("get_gr_service_for_bot")
    if target is not None and target is not get_gr_service_for_bot:
        return target(force_refresh=force_refresh)
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
    target = get_tb_symbol("get_appraisal_service_for_bot")
    if target is not None and target is not get_appraisal_service_for_bot:
        return target(force_refresh=force_refresh)
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
    target = get_tb_symbol("get_loan_service_for_bot")
    if target is not None and target is not get_loan_service_for_bot:
        return target(force_refresh=force_refresh)
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
    target = get_tb_symbol("get_recruitment_service_for_bot")
    if target is not None and target is not get_recruitment_service_for_bot:
        return target(force_refresh=force_refresh)
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
    target = get_tb_symbol("get_contract_service_for_bot")
    if target is not None and target is not get_contract_service_for_bot:
        return target(force_refresh=force_refresh)
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
    target = get_tb_symbol("get_payroll_service_for_bot")
    if target is not None and target is not get_payroll_service_for_bot:
        return target(force_refresh=force_refresh)
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
    target = get_tb_symbol("get_analytics_service_for_bot")
    if target is not None and target is not get_analytics_service_for_bot:
        return target(force_refresh=force_refresh)
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
    target = get_tb_symbol("get_expense_service_for_bot")
    if target is not None and target is not get_expense_service_for_bot:
        return target(force_refresh=force_refresh)
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
    target = get_tb_symbol("get_expiry_service_for_bot")
    if target is not None and target is not get_expiry_service_for_bot:
        return target(force_refresh=force_refresh)
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

