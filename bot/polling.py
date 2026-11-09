"""Telegram Bot Long-Polling Loop and Message Event Dispatcher."""
from __future__ import annotations

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from bot.client import (
    TelegramBotClient,
    get_tb_symbol,
    get_allowed_users,
    is_user_authorized,
    log_telegram_audit,
    set_autofix_enabled,
    PENDING_CONFIRMATIONS,
    ACTIVE_CONFIG_WIZARDS,
    ACTIVE_LEAVE_WIZARDS,
    ACTIVE_ATTENDANCE_WIZARDS,
    ACTIVE_DISCIPLINARY_WIZARDS,
    ACTIVE_EOS_WIZARDS,
    ACTIVE_GR_WIZARDS,
    ACTIVE_APPRAISAL_WIZARDS,
    ACTIVE_LOAN_WIZARDS,
    ACTIVE_RECRUITMENT_WIZARDS,
    ACTIVE_CONTRACT_WIZARDS,
    ACTIVE_PAYROLL_WIZARDS,
    ACTIVE_ANALYTICS_WIZARDS,
    ACTIVE_EXPENSE_WIZARDS,
    ACTIVE_LETTER_WIZARDS,
    ACTIVE_WARNING_WIZARDS,
    PENDING_LEAVE_CONFIRMATIONS,
    PENDING_ATTENDANCE_CONFIRMATIONS,
    PENDING_DISCIPLINARY_CONFIRMATIONS,
    PENDING_EOS_CONFIRMATIONS,
    PENDING_GR_CONFIRMATIONS,
    PENDING_APPRAISAL_CONFIRMATIONS,
    PENDING_LOAN_CONFIRMATIONS,
    PENDING_RECRUITMENT_CONFIRMATIONS,
    PENDING_CONTRACT_CONFIRMATIONS,
    PENDING_PAYROLL_CONFIRMATIONS,
    PENDING_LETTER_CONFIRMATIONS,
    PENDING_WARNING_CONFIRMATIONS,
    PENDING_EXPENSE_CONFIRMATIONS,
    DEFAULT_COMPANY_ID,
)
from bot.keyboards import get_main_menu_keyboard, get_templates_menu_keyboard
from bot.media_handlers import handle_excel_document, handle_voice_message, execute_via_backend_api
from bot.domain_wizards import *
from bot.navigation import *
from bot.callbacks import handle_callback_dispatch

logger = logging.getLogger("telegram_bot")

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

