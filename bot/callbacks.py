"""Callback Query Dispatcher for Telegram Bot interactive inline buttons."""
from __future__ import annotations

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from odoo_config_manager import get_active_odoo_config

from bot.client import (
    TelegramBotClient,
    get_tb_symbol,
    log_telegram_audit,
    is_autofix_enabled,
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
)
from bot.keyboards import get_main_menu_keyboard, get_templates_menu_keyboard
from bot.media_handlers import (
    handle_approval_callback,
    handle_musleh_heal_callback,
)
from bot.domain_wizards import *
from bot.navigation import *

logger = logging.getLogger("telegram_bot")

def handle_callback_dispatch(
    bot: TelegramBotClient,
    chat_id: int | str,
    user_id: int | str,
    user_name: str,
    msg_id: int,
    cq_id: str,
    data: str,
) -> None:
    target = get_tb_symbol("handle_callback_dispatch")
    if target is not None and target is not handle_callback_dispatch:
        return target(bot, chat_id, user_id, user_name, msg_id, cq_id, data)

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

