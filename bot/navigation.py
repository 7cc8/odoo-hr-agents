"""Navigation cards, Odoo settings, and interactive employee selection for Telegram Bot."""
from __future__ import annotations

import os
import sys
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from odoo_config_manager import (
    get_active_odoo_config,
    save_active_odoo_config as _save_active_odoo_config,
    test_odoo_connection as _test_odoo_connection,
)
from letter_service import SUPPORTED_LETTER_TYPES

from bot.client import (
    TelegramBotClient,
    get_tb_symbol,
    log_telegram_audit,
    ROOT_DIR,
    ACTIVE_CONFIG_WIZARDS,
    ACTIVE_LEAVE_WIZARDS,
    ACTIVE_ATTENDANCE_WIZARDS,
    ACTIVE_DISCIPLINARY_WIZARDS,
    ACTIVE_EOS_WIZARDS,
    ACTIVE_GR_WIZARDS,
    ACTIVE_APPRAISAL_WIZARDS,
    ACTIVE_LOAN_WIZARDS,
    ACTIVE_CONTRACT_WIZARDS,
    ACTIVE_PAYROLL_WIZARDS,
    ACTIVE_LETTER_WIZARDS,
    ACTIVE_WARNING_WIZARDS,
    ACTIVE_EXPENSE_WIZARDS,
    PENDING_ATTENDANCE_CONFIRMATIONS,
)
from bot.keyboards import get_main_menu_keyboard, get_templates_menu_keyboard, TEMPLATES_CATALOG
from bot.domain_wizards import (
    prompt_leave_type_selection,
    show_employee_leaves_balance,
    show_employee_attendance_card,
    show_employee_disciplinary_card,
)


def save_active_odoo_config(*args, **kwargs) -> Any:
    target = get_tb_symbol("save_active_odoo_config")
    if target is not None and target is not save_active_odoo_config:
        return target(*args, **kwargs)
    return _save_active_odoo_config(*args, **kwargs)


def test_odoo_connection(*args, **kwargs) -> Any:
    target = get_tb_symbol("test_odoo_connection")
    if target is not None and target is not test_odoo_connection:
        return target(*args, **kwargs)
    return _test_odoo_connection(*args, **kwargs)

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

