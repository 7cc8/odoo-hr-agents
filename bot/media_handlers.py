"""Media and execution handlers for Telegram Bot (Excel, Voice, Approvals, API Write)."""
from __future__ import annotations

import os
import sys
import json
import time
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import dry_run_report
from odoo_readonly_repository import OdooReadonlyRepository

from bot.client import (
    TelegramBotClient,
    get_ssl_context,
    log_telegram_audit,
    get_tb_symbol,
    is_autofix_enabled,
    PENDING_CONFIRMATIONS,
    DEFAULT_COMPANY_ID,
    DEFAULT_MAX_ROWS,
    WRITE_API_TOKEN,
    API_BASE_URL,
    UPLOAD_DIR,
)

logger = logging.getLogger("telegram_bot")

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
    if not WRITE_API_TOKEN:
        bot.send_message(
            chat_id,
            "⛔ <b>لم يُنفَّذ شيء:</b> رمز الكتابة غير مضبوط في بيئة البوت (WRITE_API_TOKEN).",
            reply_to_message_id=reply_to_msg_id,
        )
        log_telegram_audit(user_id, chat_id, "api_write_blocked_no_token", {"run_id": run_id})
        return
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


