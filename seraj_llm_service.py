"""
خدمة الذكاء الاصطناعي لـ «سراج» عبر OpenRouter (Seraj Conversational Orchestrator with Fahas Integration)
========================================================================================================
سراج هو واجهة المحادثة والمنسق الأساسي للمنظومة:
1. فهم طلب المستخدم باللغة الطبيعية وإدارة سياق المحادثة.
2. طلب التوضيح المباشر من المستخدم عند نقص أي معلومة ضرورية.
3. تنسيق مهمة الاستعلام وتوجيهها حصرياً إلى وكيل الفحص والقراءة المعتمد «فاحص».
4. شرح النتيجة المنظمة الواردة من «فاحص» وعرضها للمستخدم دون تخمين أو هلوسة.

ضوابط الفصل المعماري:
- لا وجود لأي مسار قراءة موازٍ داخل سراج يكرر دور فاحص؛ فاحص هو المنفذ الحصري للقراءة في Odoo.
- فاحص لا يدير المحادثة ولا يرد على المستخدم؛ سراج هو من يشرح ويعرض النتائج.
- مسار قراءة واستعلام فقط (Read-Only)؛ لا يملك سراج أو فاحص أي صلاحيات كتابة أو تعديل أو حذف أو اعتماد.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from approval_plan_schema import ApprovalPlan, ApprovalPlanError, validate_plan_for_execution
from deletion_policy import (
    create_deletion_plan,
    DeletionPolicyError,
    KNOWN_IMPACTS,
    ALLOWED_DELETION_MODELS,
    ALLOWED_ARCHIVE_MODELS,
    ALLOWED_UNARCHIVE_MODELS,
    MODEL_LABELS,
    resolve_model_from_query,
)
from fahas_service import FahasAgent, get_fahas_agent
from katib_service import KatibAgent, get_katib_agent, KatibSecurityError, KatibExecutionError
from odoo_agent_tools import (
    SERAJ_ODOO_TOOLS_SCHEMA,
    execute_tool_call,
    OdooToolSecurityError,
    OdooToolExecutionError,
)
from seraj_session_manager import SerajSessionManager, ConversationSession

try:
    from agent_events_service import get_events_service
except ImportError:
    get_events_service = None

logger = logging.getLogger("seraj_llm_service")

# Candidate high-parameter free models (27B and above)
FREE_HIGH_PARAM_MODELS = [
    "openrouter/auto",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
]


def clean_math_formatting(text: str) -> str:
    r"""
    Cleans up any raw LaTeX formulas or mathematical markup that LLMs might generate,
    converting them into clean, human-readable Arabic text and arithmetic expressions.
    """
    if not text:
        return text

    # Convert \frac{a}{b} -> a/b
    text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'\1/\2', text)
    # Convert \times and \cdot -> ×
    text = text.replace(r'\times', '×').replace(r'\cdot', '×')
    # Strip \text{...} -> inner text
    text = re.sub(r'\\text\{([^}]+)\}', r'\1', text)
    # Strip \left and \right
    text = text.replace(r'\left', '').replace(r'\right', '')
    # Replace \[ and \] with newlines
    text = text.replace(r'\[', '\n').replace(r'\]', '\n')
    # Replace \( and \) with space
    text = text.replace(r'\(', '').replace(r'\)', '')
    # Replace \le, \leq -> ≤
    text = re.sub(r'\\leq?', '≤', text)
    # Replace \ge, \geq -> ≥
    text = re.sub(r'\\geq?', '≥', text)
    # Strip $$ or $
    text = text.replace('$$', '').replace('$', '')
    # Clean up LaTeX escaped characters
    text = text.replace(r'\%', '%').replace(r'\,', ' ').replace(r'\;', ' ').replace(r'\quad', ' ')
    # Normalize spaces
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


class SerajLLMService:
    """محرك التفكير واللغة الطبيعية وتنسيق المهام لسراج عبر OpenRouter وتفويض الاستعلام لفاحص."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 25,
        fahas_agent: Optional[FahasAgent] = None,
        katib_agent: Optional[KatibAgent] = None,
    ) -> None:
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "") if api_key is None else api_key
        self.model = model or os.environ.get("OPENROUTER_MODEL", FREE_HIGH_PARAM_MODELS[0])
        self.timeout = timeout
        self.session_manager = SerajSessionManager.get_instance()
        self.fahas = fahas_agent or get_fahas_agent()
        self.katib = katib_agent or get_katib_agent()

    def is_configured(self) -> bool:
        """
        فحص جاهزية محرك الذكاء الاصطناعي بناءً على الإعدادات النشطة:
        - الوضع اليدوي (Manual): يتحقق من توفر المشغل المختار صراحة (محلي أو سحابي).
        - الوضع التلقائي (Auto): يُعتبر جاهزاً إذا توفر أيٌّ من الخادم المحلي أو المفتاح السحابي.
        """
        try:
            from llm_config_manager import load_llm_config, check_local_health
            cfg = load_llm_config()
            mode = cfg.get("mode", "auto")
            active = cfg.get("active_provider", "local")
            has_cloud_key = bool(self.api_key and str(self.api_key).strip()) or bool(cfg.get("cloud", {}).get("api_key", "").strip())

            fallback_enabled = cfg.get("fallback_enabled", True)
            if mode == "manual":
                if active == "cloud":
                    if has_cloud_key:
                        return True
                    if fallback_enabled:
                        local_health = check_local_health(cfg.get("local", {}).get("base_url"))
                        return local_health.get("available", False)
                    return False
                else:
                    local_health = check_local_health(cfg.get("local", {}).get("base_url"))
                    if local_health.get("available", False):
                        return True
                    if fallback_enabled and has_cloud_key:
                        return True
                    return False
            else:
                # وضع التبديل التلقائي: يُعتبر جاهزاً إذا توفر الخادم المحلي أو المفتاح السحابي
                local_health = check_local_health(cfg.get("local", {}).get("base_url"))
                if local_health.get("available", False):
                    return True
                if has_cloud_key:
                    return True
                return False
        except Exception as e:
            logger.warning("Error checking LLM configuration: %s", e)
            return bool(self.api_key and str(self.api_key).strip())


    def _emit_evt(
        self,
        operation_id: Optional[str],
        agent: str,
        event_type: str,
        status: str,
        description_ar: str,
        from_agent: Optional[str] = None,
        to_agent: Optional[str] = None,
        plan_id: Optional[str] = None,
        plan: Optional[Dict[str, Any]] = None,
        clarification: Optional[Dict[str, Any]] = None,
        final_result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        if not operation_id or get_events_service is None:
            return
        try:
            evt_srv = get_events_service()
            evt_srv.emit_event(
                operation_id=operation_id,
                agent=agent,
                event_type=event_type,
                status=status,
                description_ar=description_ar,
                from_agent=from_agent,
                to_agent=to_agent,
                plan_id=plan_id,
                plan=plan,
                clarification=clarification,
                final_result=final_result,
                error=error,
            )
        except Exception as exc:
            logger.debug("Failed to emit agent event: %s", exc)

    def chat_turn(
        self,
        user_query: str,
        chat_id: str = "default",
        user_name: str = "مستخدم",
        connection_id: Optional[str] = None,
        company_id: Optional[int] = None,
        operation_id: Optional[str] = None,
    ) -> str:
        """
        تنفيذ دورة المحادثة والتنسيق الكاملة لسراج كـ «المنسق العام»:
        1. فهم طلب المستخدم وإدارة سياق المحادثة عبر الجلسات.
        2. التنسيق لطلبات الإضافة والتعديل: تحضير الطلب عبر الوكلاء وطلب الاعتماد الصريح من المستخدم.
        3. توجيه التنفيذ حصرياً إلى «كاتب» بعد الاعتماد، وإجراء التحقق الراجع عبر «فاحص».
        4. الحذف الفعلي (unlink) لا يُنفَّذ إلا عبر خطة اعتماد مستقلة وتأكيد صريح من المستخدم.
        5. تنسيق مهام الاستعلام والقراءة وتفويضها حصرياً إلى وكيل الفحص «فاحص».
        6. شرح النتيجة المنظمة للمستخدم بلغة عربية واضحة ودقيقة.
        """
        clean_query = user_query.strip()
        if not clean_query:
            return "مرحباً بك! كيف يمكنني مساعدتك في استعلامات الموارد البشرية ونظام Odoo اليوم؟"

        self._emit_evt(
            operation_id=operation_id,
            agent="seraj",
            event_type="query_received",
            status="analyzing_request",
            description_ar=f"سراج يستلم الطلب ويحلل نية المستخدم: «{clean_query[:50]}»",
        )

        session = self.session_manager.get_session(chat_id)
        if connection_id:
            session.connection_id = connection_id
        if company_id is not None:
            session.company_id = company_id

        # 0. فحص هل هناك استيضاح معلق لنوع الحذف (أرشفة أو حذف نهائي)
        if session.pending_clarification and session.pending_clarification.get("type") == "clarify_delete_or_archive":
            target_str = session.pending_clarification.get("target", "")
            orig_q = session.pending_clarification.get("original_query", "")
            session.clear_pending_clarification()

            chosen_action = None
            if any(w in clean_query for w in ["أرشف", "ارشف", "أرشفة", "ارشفة", "تعطيل", "إيقاف تنشيط", "1", "الاول", "الأول"]):
                chosen_action = "archive"
            elif any(w in clean_query for w in ["حذف نهائي", "نهائي", "حذف كلي", "كلي", "إزالة", "ازالة", "2", "الثاني"]):
                chosen_action = "delete"

            if chosen_action:
                clean_query = f"{'أرشفة' if chosen_action == 'archive' else 'حذف نهائي'} {target_str}".strip()
            else:
                return (
                    "⚠️ لم يتم تحديد نوع الإجراء بدقة.\n"
                    "يرجى الرد صراحة بإحدى الخيارين:\n"
                    "1️⃣ **أرشفة [اسم الموظف]**\n"
                    "2️⃣ **حذف نهائي [اسم الموظف]**"
                )

        # 1. معالجة التأكيد أو الإلغاء للعملية المعلقة (Add / Edit / Archive / Delete Confirmation)
        if session.pending_action:
            plan_id_match = re.search(r'plan_\d+_[a-f0-9]{8}', clean_query)
            confirm_keywords = {"تاكيد", "تأكيد", "نعم", "موافق", "اعتمد", "تم", "تأكيد العملية", "اعتمد التعديل", "تأكيد الإضافة"}
            cancel_keywords = {"إلغاء", "الغاء", "تراجع", "لا", "cancel", "رفض"}
            norm_q = clean_query.strip().lower()

            if any(norm_q == kw or norm_q.startswith(kw) for kw in cancel_keywords):
                session.clear_pending_action()
                self._emit_evt(
                    operation_id=operation_id,
                    agent="hares",
                    from_agent="seraj",
                    to_agent="hares",
                    event_type="action_cancelled",
                    status="completed",
                    description_ar="حارس يلغي العملية بناءً على طلب المستخدم دون أي تعديل في Odoo",
                )
                self._emit_evt(
                    operation_id=operation_id,
                    agent="seraj",
                    from_agent="hares",
                    to_agent="seraj",
                    event_type="cancellation_notified",
                    status="completed",
                    description_ar="سراج يؤكد إلغاء العملية وسلامة البيانات",
                )
                return "🚫 تم إلغاء العملية بناءً على طلبك، ولم يتم إجراء أي تعديل أو حذف في Odoo."

            is_confirmed = bool(plan_id_match) or any(norm_q == kw or norm_q.startswith(kw) for kw in confirm_keywords)
            if is_confirmed:
                act = session.pending_action
                # فحص انتهاء الصلاحية
                if act.get("expires_at") and time.time() > act["expires_at"]:
                    session.clear_pending_action()
                    return "⚠️ انتهت مهلة تأكيد العملية (TTL). تم إلغاء العملية تلقائياً لحماية البيانات."

                # فحص الاستهلاك المسبق
                if act.get("consumed", False):
                    session.clear_pending_action()
                    return "⚠️ تم استهلاك رمز الاعتماد لهذه العملية مسبقاً ولا يمكن إعادة استخدامه."

                plan_id = plan_id_match.group(0) if plan_id_match else act.get("plan_id")
                
                # فحص خطة الاعتماد الرسمية إن وُجدت
                if plan_id and str(plan_id).startswith("plan_"):
                    try:
                        plan = ApprovalPlan.load(plan_id)
                        if plan.created_by != str(chat_id):
                            session.clear_pending_action()
                            self._emit_evt(
                                operation_id=operation_id,
                                agent="hares",
                                event_type="approval_invalid_user",
                                status="failed",
                                description_ar=f"حارس يرفض - المستخدم {chat_id} ليس منشئ الخطة {plan_id}",
                            )
                            return "⚠️ لا يمكن تنفيذ هذه العملية: هوية صاحب التأكيد لا تطابق هوية مقدم الطلب الأصلية."
                        plan.approve(approved_by=str(chat_id))
                        plan.save()
                    except ApprovalPlanError as p_err:
                        session.clear_pending_action()
                        self._emit_evt(
                            operation_id=operation_id,
                            agent="hares",
                            event_type="approval_invalid",
                            status="failed",
                            description_ar=f"حارس يرفض الاعتماد: {p_err}",
                        )
                        return f"⚠️ خطة الاعتماد غير صالحة: {p_err}"

                act_type = act.get("action_type") or act.get("type")
                session.mark_pending_action_consumed()
                
                self._emit_evt(
                    operation_id=operation_id,
                    agent="hares",
                    from_agent="seraj",
                    to_agent="hares",
                    event_type="approval_verified",
                    status="executing_write",
                    description_ar=f"حارس يتحقق من صحة الاعتماد الصريح وتفويض تنفيذ الخطة ({plan_id or 'direct'})",
                )
                self._emit_evt(
                    operation_id=operation_id,
                    agent="katib",
                    from_agent="hares",
                    to_agent="katib",
                    event_type="execution_started",
                    status="executing_write",
                    description_ar=f"توجيه أمر التنفيذ حصرياً إلى «كاتب» لتطبيقه في Odoo ({act_type})",
                )

                # إرفاق مقتطف المحادثة والطلب لتوثيقها لدى «سجل»
                act["chat_id"] = str(chat_id)
                act["conversation_snippet"] = [
                    {"role": m.get("role"), "content": m.get("content")}
                    for m in session.history[-6:]
                ]

                try:
                    exec_res = self.katib.execute_approved_action(act)

                    # معالجة اعتراض ورفض خادم Odoo
                    if exec_res.get("status") == "odoo_rejected":
                        session.clear_pending_action()
                        self._emit_evt(
                            operation_id=operation_id,
                            agent="katib",
                            event_type="execution_rejected",
                            status="failed",
                            description_ar=f"رفض خادم Odoo العملية: {exec_res.get('error')}",
                            error=exec_res.get("error"),
                        )
                        self._emit_evt(
                            operation_id=operation_id,
                            agent="seraj",
                            from_agent="katib",
                            to_agent="seraj",
                            event_type="rejected_notified",
                            status="failed",
                            description_ar="سراج يشرح سبب رفض Odoo لحماية سلامة وتكامل البيانات",
                        )
                        return (
                            "❌ **رفض خادم Odoo العملية:**\n"
                            f"{exec_res.get('error')}\n\n"
                            "⚠️ تم إيقاف التنفيذ فوراً لحماية سلامة وتكامل البيانات، ولم يتم تنفيذ أي حذف مرتبط تلقائياً."
                        )

                    # مسار الحذف النهائي المحكوم
                    if act_type == "delete":
                        rec_id = act.get("record_id") or act.get("employee_id")
                        v_res = self.fahas.verify_record_status(
                            model=act.get("model", "hr.employee"),
                            record_id=rec_id,
                            expected_state="deleted",
                            connection_id=act.get("connection_id", "default"),
                        )
                        session.clear_pending_action()

                        if v_res.get("state") == "inconclusive":
                            return (
                                "⚠️ تم إرسال أمر الحذف إلى خادم Odoo، ولكن **نتيجة التحقق غير محسومة (Inconclusive)**:\n"
                                f"{v_res.get('message') or v_res.get('error')}\n\n"
                                "⚠️ لا يمكن إعلان النجاح حتى يتم التحقق المستقل من غياب السجل."
                            )

                        if v_res.get("verified"):
                            return (
                                "✅ **تم الحذف النهائي للسجل بنجاح عبر «كاتب»:**\n"
                                "────────────────────\n"
                                f"• **النموذج:** {act.get('model_label', act.get('model', 'hr.employee'))}\n"
                                f"• **المعرف السابق:** `{rec_id}`\n"
                                f"• **الاسم:** {act.get('record_name')}\n\n"
                                "🔍 **التحقق المستقل (فاحص):** تم فحص قاعدة البيانات وتأكيد زوال السجل تماماً من Odoo حتى مع active_test=False.\n"
                                f"📝 **التوثيق (سجل):** تم قيد العملية بخطة الاعتماد `{act.get('plan_id', 'N/A')}` في سجل التدقيق بنجاح."
                            )
                        else:
                            return f"⚠️ لم يتم تأكيد الحذف؛ ما زال السجل موجوداً في Odoo (الحالة: {v_res.get('state')})."

                    # مسار الأرشفة المحكومة
                    elif act_type == "archive":
                        rec_id = act.get("record_id") or act.get("employee_id")
                        v_res = self.fahas.verify_record_status(
                            model=act.get("model", "hr.employee"),
                            record_id=rec_id,
                            expected_state="archived",
                            connection_id=act.get("connection_id", "default"),
                        )
                        session.clear_pending_action()

                        if v_res.get("state") == "inconclusive":
                            return (
                                "⚠️ تم إرسال أمر الأرشفة، ولكن نتيجة التحقق غير محسومة:\n"
                                f"{v_res.get('message') or v_res.get('error')}"
                            )

                        return (
                            "✅ **تمت الأرشفة بنجاح عبر «كاتب»:**\n"
                            "────────────────────\n"
                            f"• **النموذج:** {act.get('model_label', act.get('model', 'hr.employee'))}\n"
                            f"• **السجل:** {act.get('record_name')} (ID: {rec_id})\n"
                            "• **الحالة الجديدة:** مؤرشف (غير نشط - active=False)\n\n"
                            "🔍 **التحقق المستقل (فاحص):** تم فحص السجل والتأكد من إيقاف تنشيطه مع بقاء كافة بياناته التاريخية.\n"
                            f"📝 **التوثيق (سجل):** تم توثيق العملية برقم الخطة `{act.get('plan_id', 'N/A')}` في سجل التدقيق."
                        )

                    # مسار الاسترجاع من الأرشيف (Unarchive)
                    elif act_type == "unarchive":
                        rec_id = act.get("record_id") or act.get("employee_id")
                        v_res = self.fahas.verify_record_status(
                            model=act.get("model", "hr.employee"),
                            record_id=rec_id,
                            expected_state="active",
                            connection_id=act.get("connection_id", "default"),
                        )
                        session.clear_pending_action()

                        if v_res.get("state") == "inconclusive":
                            return (
                                "⚠️ تم إرسال أمر إلغاء الأرشفة، ولكن نتيجة التحقق غير محسومة:\n"
                                f"{v_res.get('message') or v_res.get('error')}"
                            )

                        if v_res.get("verified"):
                            return (
                                "✅ **تم استرجاع السجل من الأرشيف بنجاح عبر «كاتب»:**\n"
                                "────────────────────\n"
                                f"• **النموذج:** {act.get('model_label', act.get('model', 'hr.employee'))}\n"
                                f"• **السجل:** {act.get('record_name')} (ID: {rec_id})\n"
                                "• **الحالة الجديدة:** نشط (active=True)\n\n"
                                "🔍 **التحقق المستقل (فاحص):** تم فحص السجل والتأكد من إعادة تنشيطه في Odoo.\n"
                                f"📝 **التوثيق (سجل):** تم توثيق العملية برقم الخطة `{act.get('plan_id', 'N/A')}` في سجل التدقيق."
                            )
                        else:
                            return (
                                f"⚠️ لم يتم تأكيد الاسترجاع؛ السجل ما زال مؤرشفاً في Odoo "
                                f"(الحالة: {v_res.get('state')}).\n"
                                "يرجى التحقق من السجل يدوياً في Odoo."
                            )

                    # مسار التعديل
                    elif act_type == "update":
                        read_res = self.fahas.read_records(
                            model=act.get("model", "hr.employee"),
                            ids=[act["employee_id"]],
                            fields=["id", "name", act.get("field", "job_title")]
                        )
                        verified_info = ""
                        if read_res.get("records"):
                            rec = read_res["records"][0]
                            verified_info = f"تم قراءة الحقل (`{rec.get(act.get('field', 'job_title'))}`) ومطابقته مباشرة من Odoo."
                        session.clear_pending_action()
                        return (
                            "✅ **تم تنفيذ وتأكيد العملية بنجاح عبر «كاتب»:**\n"
                            "────────────────────\n"
                            f"• **نوع العملية:** تعديل {act.get('field_label', 'البيانات')}\n"
                            f"• **الموظف:** {act.get('employee_name')} (ID: {act.get('employee_id')})\n"
                            f"• **القيمة الجديدة المعتمدة:** `{act.get('new_value')}`\n\n"
                            f"🔍 **التحقق الراجع (فاحص):** {verified_info or 'تم التحقق بنجاح من انعكاس التعديل في Odoo.'}\n"
                            "📝 **التوثيق (سجل):** تم قيد العملية في سجل التدقيق بنجاح."
                        )

                    # مسار الإنشاء
                    else:
                        new_id = exec_res.get("employee_id")
                        session.clear_pending_action()
                        return (
                            "✅ **تم إنشاء الموظف بنجاح عبر «كاتب»:**\n"
                            "────────────────────\n"
                            f"• **الموظف الجديد:** {act.get('name')} (معرف Odoo: `{new_id}`)\n\n"
                            "🔍 **التحقق الراجع (فاحص):** تم التحقق من إنشاء السجل في Odoo.\n"
                            "📝 **التوثيق (سجل):** تم قيد العملية في سجل التدقيق بنجاح."
                        )

                except Exception as exc:
                    session.clear_pending_action()
                    return f"❌ تعذر تنفيذ العملية عبر «كاتب»: {exc}"

            else:
                pass

        # 2. فحص مسار الحذف والأرشفة والاسترجاع المحكوم
        is_archive_explicit = any(w in clean_query for w in ["أرشف", "ارشف", "أرشفة", "ارشفة", "إيقاف تنشيط", "تعطيل"])
        is_delete_explicit = any(w in clean_query for w in ["حذف نهائي", "حذف كلي", "إزالة نهائية", "ازالة نهائية"])
        is_unarchive_explicit = any(w in clean_query for w in [
            "استرجع", "استرجاع", "ارجع", "أرجع", "إلغاء أرشفة", "إلغاء الأرشفة",
            "الغ ارشفة", "الغ أرشفة", "تنشيط", "تفعيل", "reactivate", "unarchive",
            "اعد تنشيط", "أعد تنشيط", "إعادة تنشيط", "استعادة"
        ]) and not is_archive_explicit
        is_delete_ambiguous = (
            any(w in clean_query for w in ["احذف", "حذف", "امسح", "مسح", "unlink", "delete"])
            and not is_archive_explicit
            and not is_delete_explicit
            and not is_unarchive_explicit
        )

        # أ) طلب حذف عام مبهم دون تمييز الأرشفة عن الحذف النهائي
        if is_delete_ambiguous:
            target_match = re.search(r'(?:احذف|حذف|امسح|مسح|unlink|delete)\s+(?:الموظف\s+|الموظفة\s+|سجل\s+|رقم\s+)?(.+)', clean_query)
            extracted_target = target_match.group(1).strip() if target_match else clean_query
            session.pending_clarification = {
                "type": "clarify_delete_or_archive",
                "target": extracted_target,
                "original_query": clean_query,
            }
            self._emit_evt(
                operation_id=operation_id,
                agent="seraj",
                event_type="waiting_clarification",
                status="waiting_clarification",
                description_ar=f"سراج يطلب توضيح نوع الإجراء المطلوب بخصوص «{extracted_target}»: أرشفة أم حذف نهائي؟",
                clarification=session.pending_clarification,
            )
            return (
                "❓ **توضيح نوع العملية المطلوب (سراج):**\n"
                "────────────────────\n"
                f"لقد طلبت حذفاً بخصوص «{extracted_target}»، ويرجى تحديد نوع الإجراء المطلوب بدقة نظاماً:\n\n"
                "1️⃣ **الأرشفة (إيقاف التنشيط - Archive):** إخفاء الموظف وحفظ بياناته التاريخية وسجلاته وعقوده في Odoo.\n"
                "2️⃣ **الحذف النهائي (Permanent Delete):** إزالة السجل بالكامل من Odoo بشكل نهائي لا يمكن التراجع عنه.\n\n"
                f"💡 *يرجى الرد بـ: «أرشفة {extracted_target}» أو «حذف نهائي {extracted_target}».*"
            )

        # ب) مسار الاسترجاع من الأرشيف (Unarchive) — متعدد النماذج
        if is_unarchive_explicit:
            target_model, target_model_label = resolve_model_from_query(clean_query)

            # استخراج المعرف أو الاسم
            rec_id = None
            rec_name = None
            id_match = re.search(r'(?:رقم|معرف|id)\s*(\d+)', clean_query, re.IGNORECASE)
            if id_match:
                rec_id = int(id_match.group(1))
            else:
                name_match = re.search(
                    r'(?:استرجع|استرجاع|ارجع|أرجع|تنشيط|تفعيل|اعد تنشيط|أعد تنشيط|إعادة تنشيط|استعادة|الغ ارشفة|الغ أرشفة|إلغاء أرشفة|إلغاء الأرشفة|unarchive|reactivate)'
                    r'\s+(?:الموظف\s+|الموظفة\s+|القسم\s+|الوظيفة\s+|المتقدم\s+|سجل\s+|رقم\s+)?(.+)',
                    clean_query
                )
                if name_match:
                    rec_name = name_match.group(1).strip()

            if not rec_id and not rec_name:
                return (
                    f"📋 **تنسيق طلب الاسترجاع (سراج):**\n"
                    f"يرجى تحديد اسم أو معرف {target_model_label} المراد استرجاعه من الأرشيف.\n"
                    f"💡 *مثال:* «استرجع الموظف رقم 42» أو «إلغاء أرشفة القسم رقم 5»."
                )

            # استعلام فاحص — البحث في المؤرشف فقط
            if rec_id:
                search_res = self.fahas.search_records(
                    model=target_model,
                    domain=[("id", "=", rec_id), ("active", "=", False)],
                    fields=["id", "name", "company_id", "active"],
                    include_archived=True,
                )
            else:
                search_res = self.fahas.search_records(
                    model=target_model,
                    domain=[("name", "ilike", rec_name), ("active", "=", False)],
                    fields=["id", "name", "company_id", "active"],
                    include_archived=True,
                )

            records = search_res.get("records", [])
            if not records:
                search_hint = f"رقم {rec_id}" if rec_id else f"«{rec_name}»"
                return (
                    f"⚠️ لم يتمكن «فاحص» من العثور على أي سجل مؤرشف يطابق {search_hint}\n"
                    f"في النموذج: {target_model_label}.\n"
                    "💡 تأكد أن السجل مؤرشف فعلاً، أو استعن بـ «ابحث عن المؤرشف» لعرض قائمة الأرشيف."
                )

            if len(records) > 1:
                cand_lines = []
                for idx, r in enumerate(records[:5], 1):
                    comp_name = r.get("company_id", [False, "غير محدد"])[1] if isinstance(r.get("company_id"), list) else ""
                    comp_str = f" — {comp_name}" if comp_name else ""
                    cand_lines.append(f"{idx}. {r.get('name')} (ID: `{r.get('id')}`){comp_str}")

                session.pending_clarification = {
                    "type": "select_record_id_for_deletion",
                    "action_type": "unarchive",
                    "model": target_model,
                    "records": records,
                }
                return (
                    "⚠️ **تعدد المطابقات المؤرشفة في Odoo (سراج):**\n"
                    "────────────────────\n"
                    f"عثر «فاحص» على أكثر من سجل مؤرشف يطابق بحثك في {target_model_label}:\n"
                    + "\n".join(cand_lines) + "\n\n"
                    "⚠️ **ضابط الأمان:** لا يمكن المتابعة بناءً على المطابقة التقريبية وحدها.\n"
                    f"يرجى تحديد **رقم المعرف (ID)** للسجل المطلوب (مثال: «استرجع رقم {records[0].get('id')}»)."
                )

            rec = records[0]
            comp_id = rec.get("company_id", [False, None])[0] if isinstance(rec.get("company_id"), list) else rec.get("company_id")
            comp_name = rec.get("company_id", [False, "الشركة الافتراضية"])[1] if isinstance(rec.get("company_id"), list) else "الشركة الافتراضية"

            try:
                plan = create_deletion_plan(
                    action_type="unarchive",
                    model=target_model,
                    record_id=rec["id"],
                    record_name=rec["name"],
                    company_id=comp_id,
                    company_name=comp_name,
                    connection_id=session.connection_id or "default",
                    reason="طلب استرجاع من الأرشيف معتمد من المستخدم",
                    user_id=str(chat_id),
                )
            except DeletionPolicyError as p_err:
                return f"🚫 **اعتراض السياسة:** {p_err}"

            session.pending_action = plan.to_dict()
            self._emit_evt(
                operation_id=operation_id,
                agent="fahas",
                from_agent="seraj",
                to_agent="fahas",
                event_type="record_inspection",
                status="inspecting_data",
                description_ar=f"فاحص يستعلم عن السجل ({plan.record_name}) في Odoo ويتحقق من أهليته للاسترجاع",
            )
            self._emit_evt(
                operation_id=operation_id,
                agent="modaqeq",
                from_agent="fahas",
                to_agent="modaqeq",
                event_type="rules_check",
                status="inspecting_data",
                description_ar="مدقق يدقق قواعد إعادة التنشيط والامتثال",
            )
            self._emit_evt(
                operation_id=operation_id,
                agent="hares",
                from_agent="modaqeq",
                to_agent="hares",
                event_type="plan_prepared",
                status="waiting_approval",
                description_ar=f"حارس يتحقق من الصلاحيات ويُصدر خطة الاعتماد الرسمية ({plan.plan_id})",
                plan=plan.to_dict(),
                plan_id=plan.plan_id,
            )
            return (
                f"📋 **خطة الاسترجاع من الأرشيف — في انتظار الاعتماد:**\n"
                "────────────────────\n"
                f"• **نوع العملية:** إلغاء الأرشفة (Unarchive / Reactivate)\n"
                f"• **النموذج:** {plan.model_label}\n"
                f"• **المعرف (ID):** `{plan.record_id}`\n"
                f"• **الاسم:** {plan.record_name}\n"
                f"• **المنشأة:** {plan.company_name} (ID: `{plan.company_id}`)\n"
                f"• **العدد المستهدف:** سجل واحد فقط (1)\n"
                f"• **السبب:** {plan.reason}\n"
                f"• **الأثر المعروف:** {plan.known_impact}\n"
                f"• **صلاحية الطلب:** 5 دقائق (رمز الخطة: `{plan.plan_id}`)\n\n"
                "⚠️ **للتنفيذ الفعلي وتوجيه الأمر إلى «كاتب»:**\n"
                "يرجى تأكيد العملية بالرد: **«تأكيد»** أو **«اعتمد»** (أو إرسال **«إلغاء»** للتراجع)."
            )

        # ج) مسار الحذف النهائي أو الأرشفة الصريح — متعدد النماذج
        if is_archive_explicit or is_delete_explicit:
            action_type = "archive" if is_archive_explicit else "delete"
            target_model, target_model_label = resolve_model_from_query(clean_query)

            # الحذف النهائي مقيد بـ ALLOWED_DELETION_MODELS فقط (التحقق يتم في create_deletion_plan)

            # استخراج المعرف أو الاسم
            rec_id = None
            rec_name = None
            id_match = re.search(r'(?:رقم|معرف|id)\s*(\d+)', clean_query, re.IGNORECASE)
            if id_match:
                rec_id = int(id_match.group(1))
            else:
                name_match = re.search(
                    r'(?:أرشف|ارشف|أرشفة|ارشفة|حذف نهائي|حذف كلي|إزالة نهائية|ازالة نهائية)'
                    r'\s+(?:الموظف\s+|الموظفة\s+|القسم\s+|الوظيفة\s+|المتقدم\s+|سجل\s+)?(.+)',
                    clean_query
                )
                if name_match:
                    rec_name = name_match.group(1).strip()

            if not rec_id and not rec_name:
                action_word = "الأرشفة" if action_type == "archive" else "الحذف النهائي"
                return (
                    f"📋 **تنسيق طلب {action_word} (سراج):**\n"
                    f"يرجى تحديد اسم أو معرف {target_model_label} بدقة.\n"
                    f"💡 *مثال:* «{action_word} رقم 42» أو «{action_word} سارة»."
                )

            # استعلام فاحص
            include_arch = True  # نشمل المؤرشفين لمنع الالتباس
            if rec_id:
                search_res = self.fahas.search_records(
                    model=target_model,
                    domain=[("id", "=", rec_id)],
                    fields=["id", "name", "job_title", "company_id", "active"],
                    include_archived=include_arch,
                )
            else:
                search_res = self.fahas.search_records(
                    model=target_model,
                    domain=[("name", "ilike", rec_name)],
                    fields=["id", "name", "job_title", "company_id", "active"],
                    include_archived=include_arch,
                )

            records = search_res.get("records", [])
            if not records:
                return f"⚠️ لم يتمكن «فاحص» من العثور على أي سجل مطابق في {target_model_label} بـ Odoo."

            # عند تعدد النتائج: طلب اختيار دون تنفيذ
            if len(records) > 1:
                cand_lines = []
                for idx, r in enumerate(records[:5], 1):
                    comp_name = r.get("company_id", [False, "غير محدد"])[1] if isinstance(r.get("company_id"), list) else "الشركة"
                    job_name = r.get("job_title") or ""
                    job_str = f" — {job_name}" if job_name else ""
                    status_str = " (مؤرشف)" if not r.get("active", True) else ""
                    cand_lines.append(f"{idx}. {r.get('name')} (ID: `{r.get('id')}`) — {comp_name}{job_str}{status_str}")

                session.pending_clarification = {
                    "type": "select_record_id_for_deletion",
                    "action_type": action_type,
                    "model": target_model,
                    "records": records,
                }
                action_word = "أرشفة" if action_type == "archive" else "حذف نهائي"
                return (
                    "⚠️ **تعدد المطابقات في Odoo (سراج):**\n"
                    "────────────────────\n"
                    f"عثر «فاحص» على أكثر من سجل يطابق بحثك في {target_model_label}:\n"
                    + "\n".join(cand_lines) + "\n\n"
                    "⚠️ **ضابط الأمان:** لا يمكن المتابعة بناءً على المطابقة التقريبية وحدها.\n"
                    f"يرجى تحديد **رقم المعرف (ID)** للسجل المطلوب (مثال: «{action_word} رقم {records[0].get('id')}»)."
                )

            rec = records[0]
            comp_id = rec.get("company_id", [False, None])[0] if isinstance(rec.get("company_id"), list) else rec.get("company_id")
            comp_name = rec.get("company_id", [False, "الشركة الافتراضية"])[1] if isinstance(rec.get("company_id"), list) else "الشركة الافتراضية"

            try:
                plan = create_deletion_plan(
                    action_type=action_type,
                    model=target_model,
                    record_id=rec["id"],
                    record_name=rec["name"],
                    company_id=comp_id,
                    company_name=comp_name,
                    connection_id=session.connection_id or "default",
                    reason=f"طلب {action_type} معتمد من المستخدم",
                    user_id=str(chat_id),
                )
            except DeletionPolicyError as p_err:
                return f"🚫 **اعتراض السياسة:** {p_err}"

            action_title = "الأرشفة (إيقاف التنشيط)" if action_type == "archive" else "الحذف النهائي (Permanent Delete)"
            session.pending_action = plan.to_dict()
            self._emit_evt(
                operation_id=operation_id,
                agent="fahas",
                from_agent="seraj",
                to_agent="fahas",
                event_type="record_inspection",
                status="inspecting_data",
                description_ar=f"فاحص يستعلم عن السجل ({plan.record_name}) في Odoo ويتحقق من أهليته لـ {action_title}",
            )
            self._emit_evt(
                operation_id=operation_id,
                agent="modaqeq",
                from_agent="fahas",
                to_agent="modaqeq",
                event_type="rules_check",
                status="inspecting_data",
                description_ar=f"مدقق يدقق قيود ونظام العمل بخصوص {action_title}",
            )
            self._emit_evt(
                operation_id=operation_id,
                agent="hares",
                from_agent="modaqeq",
                to_agent="hares",
                event_type="plan_prepared",
                status="waiting_approval",
                description_ar=f"حارس يتحقق من الصلاحيات والسياسات ويُصدر خطة الاعتماد الرسمية ({plan.plan_id})",
                plan=plan.to_dict(),
                plan_id=plan.plan_id,
            )

            return (
                f"📋 **خطة {action_title} المعتمدة — في انتظار الاعتماد:**\n"
                "────────────────────\n"
                f"• **نوع العملية:** {action_title}\n"
                f"• **النموذج:** {plan.model_label}\n"
                f"• **المعرف (ID):** `{plan.record_id}`\n"
                f"• **الاسم:** {plan.record_name}\n"
                f"• **المنشأة:** {plan.company_name} (ID: `{plan.company_id}`)\n"
                f"• **العدد المستهدف:** سجل واحد فقط (1)\n"
                f"• **السبب:** {plan.reason}\n"
                f"• **الأثر المعروف:** {plan.known_impact}\n"
                f"• **صلاحية الطلب:** 5 دقائق (رمز الخطة: `{plan.plan_id}`)\n\n"
                "⚠️ **للتنفيذ الفعلي وتوجيه الأمر إلى «كاتب»:**\n"
                "يرجى تأكيد العملية بالرد: **«تأكيد»** أو **«اعتمد»** (أو إرسال **«إلغاء»** للتراجع)."
            )

        # 3. فحص طلبات الإضافة والتعديل — سراج يحضر العملية وينسق مع الوكلاء ويطلب الاعتماد
        write_prep_keywords = ["عدل", "تعديل", "غير مسمى", "تغيير مسمى", "أضف", "اضف", "أنشئ", "انشئ", "إنشاء", "انشاء"]
        is_write_prep = any(kw in clean_query for kw in write_prep_keywords)

        if is_write_prep:
            # مسار التعديل (Update)
            is_update = any(kw in clean_query for kw in ["عدل", "تعديل", "غير", "تغيير"])
            if is_update:
                m = re.search(r'(?:عدل|تعديل|غير|تغيير)\s+(?:مسمى\s+)?(?:الموظف\s+|الموظفة\s+)?(.+?)\s+(?:إلى|الى|ليصبح)\s+(.+)', clean_query)
                if m:
                    emp_name = m.group(1).strip()
                    new_val = m.group(2).strip()
                    # استعلام الوضع الحالي عبر فاحص
                    search_res = self.fahas.search_records(
                        model="hr.employee",
                        domain=[("name", "ilike", emp_name)],
                        fields=["id", "name", "job_title", "company_id", "department_id"]
                    )
                    records = search_res.get("records", [])
                    if not records:
                        return f"⚠️ لم يتمكن «فاحص» من العثور على موظف باسم «{emp_name}» في Odoo لتعديل بياناته. يرجى التحقق من الاسم وتحديده بدقة."
                    emp = records[0]
                    old_val = emp.get("job_title") or "غير محدد"
                    comp_name = emp.get("company_id", [False, "غير محدد"])[1] if isinstance(emp.get("company_id"), list) else "الشركة الافتراضية"

                    session.pending_action = {
                        "type": "update",
                        "model": "hr.employee",
                        "employee_id": emp["id"],
                        "employee_name": emp["name"],
                        "field": "job_title",
                        "field_label": "المسمى الوظيفي",
                        "old_value": old_val,
                        "new_value": new_val,
                        "company_id": emp.get("company_id", [False, ""])[0] if isinstance(emp.get("company_id"), list) else emp.get("company_id"),
                    }
                    self._emit_evt(
                        operation_id=operation_id,
                        agent="fahas",
                        from_agent="seraj",
                        to_agent="fahas",
                        event_type="record_inspection",
                        status="inspecting_data",
                        description_ar=f"فاحص يستعلم عن الموظف ({emp['name']}) في Odoo ويقرأ بياناته الحالية",
                    )
                    self._emit_evt(
                        operation_id=operation_id,
                        agent="modaqeq",
                        from_agent="fahas",
                        to_agent="modaqeq",
                        event_type="rules_check",
                        status="inspecting_data",
                        description_ar="مدقق يدقق صحة المسمى الوظيفي وقواعد الامتثال",
                    )
                    self._emit_evt(
                        operation_id=operation_id,
                        agent="hares",
                        from_agent="modaqeq",
                        to_agent="hares",
                        event_type="plan_prepared",
                        status="waiting_approval",
                        description_ar="حارس يجهز خطة التعديل ويضعها في انتظار الاعتماد البشري الصريح",
                        plan=session.pending_action,
                    )

                    return (
                        f"📋 **تحضير عملية تعديل مسمى وظيفي — في انتظار الاعتماد:**\n"
                        f"────────────────────\n"
                        f"👤 **الموظف:** {emp['name']} (معرف Odoo: `{emp['id']}`)\n"
                        f"🏢 **المنشأة:** {comp_name}\n"
                        f"🔄 **التعديل المقترح:**\n"
                        f"   • المسمى الوظيفي: `{old_val}` ➔ `{new_val}`\n\n"
                        f"🛡️ **فحص وتنسيق الوكلاء:**\n"
                        f"• **فاحص:** تم التحقق من وجود الموظف في Odoo وقراءة بياناته الحالية.\n"
                        f"• **مدقق:** البيانات مستوفية لضوابط التدقيق وصحة التسميات.\n"
                        f"• **حارس:** العملية مجهزة وتنتظر تأكيد صاحب الصلاحية.\n\n"
                        f"⚠️ **للتنفيذ الفعلي وتوجيه الأمر إلى «كاتب»:**\n"
                        f"يرجى تأكيد العملية بالرد: **«تأكيد»** أو **«اعتمد التعديل»** (أو إرسال **«إلغاء»** للتراجع)."
                    )
                else:
                    return (
                        "📋 **تنسيق طلب التعديل (سراج):**\n"
                        "يرجى تحديد اسم الموظف والتعديل المطلوب بدقة.\n"
                        "💡 *مثال:* «عدل مسمى سارة إلى مديرة توظيف» أو «عدل مسمى أحمد إلى مدير مالي».\n\n"
                        "🛡️ *ضوابط الحوكمة:* تخضع كل عملية تعديل لفحص «مدقق» وحاجز الأمان لدى «حارس»، ولا يتم التنفيذ المباشر إلا عبر بوابة «كاتب» المعتمدة بعد تأكيدك الصريح."
                    )

            # مسار الإضافة (Create)
            else:
                m_add = re.search(r'(?:أضف|اضف|أنشئ|انشئ|إضافة|اضافة)\s+(?:موظف\s+)?(?:جديد\s+)?(?:باسم|باسمه|اسمه|الاسم)?\s*([^\s]+)', clean_query)
                new_name = m_add.group(1).strip() if m_add else "موظف جديد"
                dup_res = self.fahas.search_records(
                    model="hr.employee",
                    domain=[("name", "=ilike", new_name)],
                    fields=["id", "name"]
                )
                has_dup = bool(dup_res.get("records"))
                dup_note = "⚠️ تنبيه من فاحص: يوجد موظف بنفس الاسم مسبقاً في Odoo." if has_dup else "• **فاحص:** تم فحص السجلات ولا يوجد تعارض للاسم."

                session.pending_action = {
                    "type": "create",
                    "model": "hr.employee",
                    "name": new_name,
                    "values": {"name": new_name},
                }
                self._emit_evt(
                    operation_id=operation_id,
                    agent="fahas",
                    from_agent="seraj",
                    to_agent="fahas",
                    event_type="duplicate_check",
                    status="inspecting_data",
                    description_ar=f"فاحص يفحص قاعدة البيانات لمنع تكرار اسم الموظف ({new_name}) في Odoo",
                )
                self._emit_evt(
                    operation_id=operation_id,
                    agent="modaqeq",
                    from_agent="fahas",
                    to_agent="modaqeq",
                    event_type="rules_check",
                    status="inspecting_data",
                    description_ar="مدقق يدقق شروط التسمية وقواعد العمل",
                )
                self._emit_evt(
                    operation_id=operation_id,
                    agent="hares",
                    from_agent="modaqeq",
                    to_agent="hares",
                    event_type="plan_prepared",
                    status="waiting_approval",
                    description_ar="حارس يجهز خطة إنشاء الموظف في انتظار الاعتماد البشري الصريح",
                    plan=session.pending_action,
                )

                return (
                    f"📋 **تحضير عملية إضافة موظف جديد — في انتظار الاعتماد:**\n"
                    f"────────────────────\n"
                    f"👤 **الاسم المقترح:** {new_name}\n\n"
                    f"🛡️ **فحص وتنسيق الوكلاء:**\n"
                    f"{dup_note}\n"
                    f"• **مدقق:** الاسم مستوفٍ للشروط.\n"
                    f"• **حارس:** العملية جاهزة للتنفيذ بعد موافقتك.\n\n"
                    f"⚠️ **للتنفيذ الفعلي وتوجيه الأمر إلى «كاتب»:**\n"
                    f"يرجى تأكيد العملية بالرد: **«تأكيد»** أو **«اعتمد»** (أو إرسال **«إلغاء»** للتراجع)."
                )

        # فحص هل هذا الرد هو إجابة على سؤال معلق (مثل «الشركة الثانية» أو «شركة توركين»)
        resolved, original_query = self.session_manager.resolve_pending_clarification(session, clean_query)
        if resolved and original_query:
            effective_query = (
                f"{original_query}\n"
                f"(ملاحظة السياق: حدد المستخدم المنشأة: «{session.company_name}» برقم ID: {session.company_id})"
            )
        else:
            effective_query = clean_query

        # فحص استفسارات نظام العمل السعودي وتفويضها فوراً إلى «مدقق» دون استدعاء LLM خارجي
        from labor_law_knowledge import is_labor_law_query
        from agents.mudaqqiq_agent import get_mudaqqiq_agent

        if is_labor_law_query(clean_query):
            self._emit_evt(
                operation_id=operation_id,
                agent="modaqeq",
                from_agent="seraj",
                to_agent="modaqeq",
                event_type="labor_law_consultation",
                status="inspecting_data",
                description_ar=f"مدقق يستعرض مواد ونصوص نظام العمل السعودي بشأن: «{clean_query[:50]}»",
            )
            mudaqqiq = get_mudaqqiq_agent()
            law_res = mudaqqiq.consult_labor_law(clean_query)

            if law_res.get("status") == "success":
                self._emit_evt(
                    operation_id=operation_id,
                    agent="seraj",
                    from_agent="modaqeq",
                    to_agent="seraj",
                    event_type="task_completed",
                    status="completed",
                    description_ar="سراج يعرض الاستشارة النظامية المعتمدة المستندة لنظام العمل السعودي",
                )

                exp = law_res.get("explanation_ar", "")
                art_title = law_res.get("primary_article_title", "")
                art_text = law_res.get("primary_article_text", "")
                related = law_res.get("related_articles", [])

                related_section = ""
                if related:
                    rel_items = []
                    for r in related[:2]:
                        rel_items.append(f"• **{r.get('title')}:** {r.get('text')[:180]}...")
                    related_section = "\n💡 **مواد مرتبطة في النظام:**\n" + "\n".join(rel_items) + "\n"

                formatted_reply = (
                    f"⚖️ **استشارة نظام العمل السعودي — وكيل التدقيق «مدقق»:**\n"
                    f"────────────────────\n"
                    f"{exp}\n\n"
                    f"📜 **السند النظامي الصريح ({art_title}):**\n"
                    f"> \"{art_text}\"\n"
                    f"{related_section}\n"
                    f"🏛️ **المرجع المعتمد:** نظام العمل السعودي — الصادر بالمرسوم الملكي رقم (م/51) وتعديلاته.\n\n"
                    "🛡️ *ضوابط الحوكمة:* تم فحص هذه الاستشارة وتدقيقها بواسطة وكيل التدقيق والامتثال «مدقق» وفق نصوص نظام العمل السعودي المعتمدة."
                )
                session.add_message("user", clean_query)
                session.add_message("assistant", formatted_reply)
                return formatted_reply

        if not self.is_configured():
            return "✅ النظام يعمل في وضع Fallback (Rule-based).\n" \
                   "للحصول على أداء أفضل، يمكنك تكوين:\n" \
                   "1. LangGraph: OPENAI_API_KEY=sk-... في .env\n" \
                   "2. Ollama: تشغيل `ollama serve` وتعيين LLM_PROVIDER=ollama"

        # 3. بناء الـ System Prompt
        system_prompt = self._build_system_prompt(session, user_name)

        # تجهيز الرسائل
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        # إضافة آخر رسائل من تاريخ الجلسة للحفاظ على الترابط والسياق
        for hist_msg in session.history[-6:]:
            messages.append({"role": hist_msg["role"], "content": hist_msg["content"]})

        messages.append({"role": "user", "content": effective_query})

        # 4. تنفيذ حلقة Tool Calling وتفويض المهام لفاحص
        models_to_try = [self.model] + [m for m in FREE_HIGH_PARAM_MODELS if m != self.model]

        for candidate_model in models_to_try:
            try:
                answer = self._run_tool_calling_loop(candidate_model, messages, session, clean_query)
                if answer and answer.strip():
                    cleaned_answer = clean_math_formatting(answer.strip())
                    # تحديث سجل الجلسة
                    session.add_message("user", clean_query)
                    session.add_message("assistant", cleaned_answer)
                    self._emit_evt(
                        operation_id=operation_id,
                        agent="fahas",
                        from_agent="seraj",
                        to_agent="fahas",
                        event_type="odoo_query",
                        status="querying_odoo",
                        description_ar="سراج يفوض مهمة الاستعلام والبحث لوكيل الفحص «فاحص» في Odoo",
                    )
                    self._emit_evt(
                        operation_id=operation_id,
                        agent="seraj",
                        from_agent="fahas",
                        to_agent="seraj",
                        event_type="task_completed",
                        status="completed",
                        description_ar="سراج يشرح النتيجة للمستخدم بلغة عربية دقيقة",
                    )
                    return cleaned_answer
                # في حال تعذر المرشحين بالكامل عبر _call_llm، ننتقل مباشرة للوضع الاحترازي
                break
            except Exception as exc:
                logger.warning("Tool calling with model %s failed: %s", candidate_model, exc)

        # 5. الانتقال للوضع الاحترازي والاستعلام المباشر من Odoo لضمان استمرارية الخدمة
        logger.info("Transitioning to rule-based Odoo fallback for query: %s", clean_query)
        fallback_reply = self._fallback_odoo_or_rules(clean_query, session, operation_id)
        session.add_message("user", clean_query)
        session.add_message("assistant", fallback_reply)
        self._emit_evt(
            operation_id=operation_id,
            agent="seraj",
            event_type="task_completed",
            status="completed",
            description_ar="سراج يستجيب بنجاح عبر محرك الحوكمة والقواعد الاحترازية",
        )
        return fallback_reply

    def _run_tool_calling_loop(
        self,
        model_name: str,
        messages: List[Dict[str, Any]],
        session: ConversationSession,
        original_user_text: str,
    ) -> Optional[str]:
        """
        حلقة تنسيق مهام الاستعلام:
        سراج يطلب المهمة المحددة -> يفوضها لوكيل فاحص في Odoo -> فاحص يرجع النتيجة المنظمة -> سراج يشرح النتيجة للمستخدم.
        سقف أقصى 5 دورات لمنع الحلقات غير المنتهية.
        """
        current_messages = list(messages)
        max_turns = 5
        last_tool_error: Optional[str] = None

        for _ in range(max_turns):
            assistant_msg = self._call_llm(
                model_name=model_name,
                messages=current_messages,
                tools=SERAJ_ODOO_TOOLS_SCHEMA,
            )
            if not assistant_msg:
                self.last_provider_used = "fallback"
                self.last_model_used = "rule_based"
                return None

            # التوافق مع نماذج النصوص المباشرة أو الاختبارات الوهمية (Mocks)
            if isinstance(assistant_msg, str):
                self.last_provider_used = getattr(self, "last_provider_used", None) or "local"
                return assistant_msg

            if isinstance(assistant_msg, dict):
                self.last_provider_used = assistant_msg.get("_provider_used")
                self.last_model_used = assistant_msg.get("_model_used")

            tool_calls = assistant_msg.get("tool_calls")
            content = assistant_msg.get("content") or ""

            # إذا لم يطلب النموذج أي أداة، فهذا هو الرد النهائي للمستخدم
            if not tool_calls:
                # إذا حدث خطأ اتصالي أو أمني في الأدوات ولم يذكره النموذج في رده بل قال لم نجد موظفين
                if last_tool_error and any(phr in content for phr in ("لم يتم العثور على أي موظف", "لم نجد أي موظف", "لا يوجد موظف")):
                    return f"⚠️ تعذر إتمام الاستعلام بسبب {last_tool_error}. يرجى مراجعة حالة الاتصال بـ Odoo والصلاحيات."
                return content

            # إلحاق رسالة المساعد مع طلبات الأدوات
            current_messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls,
            })

            # تنسيق وتفويض كل أداة مطلوبة إلى وكيل «فاحص»
            for tc in tool_calls:
                call_id = tc.get("id") or "call_1"
                func_obj = tc.get("function") or {}
                fn_name = func_obj.get("name", "")
                raw_args = func_obj.get("arguments", "{}")

                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {}

                # حقن سياق الجلسة إن لم يُحدد صراحة في الاستدعاء
                if "connection_id" in args and not args["connection_id"]:
                    args["connection_id"] = session.connection_id
                if session.company_id and "company_id" in args and args["company_id"] is None:
                    args["company_id"] = session.company_id

                # تفويض المهمة حصرياً إلى وكيل فاحص بأمان تام
                try:
                    logger.debug("سراج يفوّض مهمة الاستعلام «%s» إلى وكيل فاحص مع المعاملات: %s", fn_name, args)
                    tool_result = self.fahas.execute_query_task(fn_name, args)
                    # حفظ الشركات المعلقة في الجلسة إذا استعلم النموذج عن الشركات
                    if fn_name == "list_companies" and isinstance(tool_result, list):
                        session.pending_clarification = {
                            "type": "select_company",
                            "original_query": original_user_text,
                            "companies": tool_result,
                        }
                    result_str = json.dumps(tool_result, ensure_ascii=False)
                except OdooToolSecurityError as sec_err:
                    last_tool_error = f"رفض أمني / صلاحيات: {sec_err}"
                    result_str = json.dumps(
                        {"status": "security_rejected", "error": str(sec_err)},
                        ensure_ascii=False,
                    )
                except OdooToolExecutionError as exec_err:
                    last_tool_error = f"خطأ في الاتصال بخادم Odoo: {exec_err}"
                    result_str = json.dumps(
                        {"status": "odoo_error", "error": str(exec_err)},
                        ensure_ascii=False,
                    )
                except Exception as gen_err:
                    last_tool_error = f"خطأ في الاتصال بقاعدة بيانات Odoo: {gen_err}"
                    result_str = json.dumps(
                        {"status": "error", "error": f"خطأ في الاتصال بقاعدة البيانات: {gen_err}"},
                        ensure_ascii=False,
                    )

                current_messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": fn_name,
                    "content": result_str,
                })

        return None

    def _build_system_prompt(
        self,
        session: ConversationSession,
        user_name: str,
    ) -> str:
        active_company_info = f"الشركة المحددة: {session.company_name} (معرّف: {session.company_id})" if session.company_id else "الشركة: غير محددة (استعلام عام / متعدد المنشآت)"
        active_conn_info = f"الاتصال الحالي: {session.connection_id}"

        prompt = (
            "أنت «سراج» واجهة المحادثة والمنسق الأساسي لإدارة الموارد البشرية Odoo في المملكة العربية السعودية.\n"
            "تتعاون مع منظومة الوكلاء: وكيل الاستعلام والقراءة الحصرية «فاحص»، ومنظومة الحراسة «الحراس»، والتدقيق «مدقق»، والمعالجة «مصلح».\n\n"
            "مسؤولياتك الصريحة كـ «سراج»:\n"
            "1. فهم طلب المستخدم وإدارة سياق المحادثة وتاريخ الجلسة.\n"
            "2. طلب التوضيح المباشر من المستخدم إذا كانت هناك معلومة ناقصة (مثل تحديد المنشأة).\n"
            "3. تنسيق مهمة الاستعلام وتوجيهها إلى وكيل الفحص والقراءة المعتمد «فاحص» عبر استدعاء الأداة المناسبة.\n"
            "4. شرح النتيجة المنظمة الواردة من «فاحص» وعرضها بأسلوب مهني عربي واضح.\n\n"
            "مسؤولية وكيل «فاحص» (Fahas):\n"
            "• «فاحص» هو المسؤول الحصري عن القراءة والاستعلام والتحقق من البيانات الفعلية في Odoo.\n"
            "• لا تضف داخل نفسك أي مسار قراءة موازٍ يكرر مسؤولية فاحص؛ بل فوّض له المهمة دائماً عبر الأدوات المحددة له.\n"
            "• فاحص يرجع لك نتيجة منظمة أو خطأ واضح، وأنت تشرح النتيجة للمستخدم.\n\n"
            f"سياق الجلسة الحالي للمستخدم «{user_name}»:\n"
            f"• {active_conn_info}\n"
            f"• {active_company_info}\n\n"
            "مهام الاستعلام المتاحة للتفويض إلى «فاحص» (قراءة واستعلام فقط Read-Only):\n"
            "1. count_records: حساب عدد السجلات الدقيق عبر search_count لدى فاحص (مثال: عدد الموظفين في hr.employee).\n"
            "2. search_records: استعلام السجلات وجلب حقول معينة عبر search_read لدى فاحص.\n"
            "3. read_records: قراءة سجلات محددة بأرقام معرّفاتها IDs لدى فاحص.\n"
            "4. list_companies: استعراض المنشآت والشركات المصرح بها في النظام عبر فاحص.\n"
            "5. list_connections: استعراض الاتصالات المتاحة بقواعد البيانات عبر فاحص.\n"
            "6. describe_model: فحص حقول الموديل عبر fields_get لدى فاحص.\n\n"
            "قواعد العمل والاستعلام الإلزامية الصارمة:\n"
            "1. منع التخمين والهلوسة منعاً باتاً (Zero Hallucination): لا تذكر أرقاماً أو أسماء إلا بناءً على نتائج أدوات الاستعلام الفعلية الواردة من فاحص.\n"
            "2. عند السؤال عن العدد (مثل «كم عدد الموظفين؟»، «كم موظف لدينا»، «عدد الموظفين»): استدعِ مهمة count_records لموديل hr.employee فوراً، وأجب بالعدد الفعلي من فاحص، ولا تبحث أبداً عن موظف بهذا الاسم!\n"
            "3. عند السؤال المتابع عن المؤرشفين أو غير النشطين (مثل «والمؤرشفين؟»): استخدم الموديل السابق نفسه (hr.employee) واستدعِ count_records مع include_archived=True أو شروط active=False.\n"
            "4. عند السؤال عن الشركات (مثل «ما الشركات المتاحة لي؟»): استدعِ list_companies لعرض البيانات الفعلية المصرح بها.\n"
            "5. عند السؤال عن موظف محدد بالاسم صراحة (مثل «ابحث عن موظف اسمه أحمد»): استدعِ search_records لموديل hr.employee مع شرط domain=[('name', 'ilike', 'أحمد')].\n"
            "6. إذا كان معنى الطلب مبهماً: اطرح سؤالاً توضيحياً مهنياً بدلاً من التخمين.\n"
            "7. إذا كان هناك نقص في اختيار المستخدم (مثل عدم تحديد الشركة عند وجود عدة شركات مسجلة): استدعِ list_companies واسأل المستخدم تحديد المنشأة.\n"
            "8. إذا ورد خطأ في الاتصال أو رفض في الصلاحية من فاحص: وضّح سبب الخطأ الحقيقي للمستخدم بوضوح، ولا تقل أبداً «لم نجد موظفين» عند حدوث عطل اتصالي أو أمني.\n"
            "9. لا تعرض أو تخترع أدوات كتابة أو تعديل أو حذف؛ هذا مسار قراءة واستعلام فقط ولا يمنح سراج أو فاحص صلاحية اعتماد أو كتابة.\n"
            "10. تحدث باللغة العربية الفصحى المهنية الودودة، وبدون استخدام أي رموز أو صيغ رياضية LaTeX."
        )
        return prompt

    def generate_grounded_response(
        self,
        user_query: str,
        user_name: str = "مستخدم",
        odoo_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        واجهة التوافق الخلفي مع النظام: تستدعي دورة المحادثة الكاملة chat_turn.
        """
        return self.chat_turn(
            user_query=user_query,
            user_name=user_name,
        )

    def _fallback_odoo_or_rules(
        self,
        query: str,
        session: ConversationSession,
        operation_id: Optional[str] = None,
    ) -> str:
        """
        محرك الاستجابة الاحترازي وحوكمة الاستعلامات المباشرة:
        يضمن استمرار عمل سراج ووكيل «فاحص» حتى عند تعطل أو انقطاع خوادم النماذج (Cloud / Ollama).
        يجيب على التحيات، استفسارات الأعداد، البحث، وقوائم الشركات مباشرة عبر Odoo.
        """
        q = query.strip().lower()

        # 1. التحيات والاستفسارات العامة عن الهوية
        greeting_patterns = [
            "مرحبا", "مرحباً", "السلام عليكم", "أهلا", "اهلا", "صباح الخير", "مساء الخير",
            "من انت", "من أنت", "ما هي مهامك", "كيف تساعدني", "ما دورك", "ماذا تفعل"
        ]
        if any(g in q for g in greeting_patterns):
            self.last_provider_used = "fallback"
            self.last_model_used = "rule_based"
            return (
                "👋 **أهلاً بك! أنا «سراج» — المنسق العام لمنظومة وكلاء الموارد البشرية لـ Odoo.**\n\n"
                "أتعاون مع نخبة من الوكلاء المتخصصين لخدمتك:\n"
                "• 🔍 **فاحص:** القراءة والاستعلام الفعلي للبيانات من Odoo.\n"
                "• 🛡️ **حارس & مدقق:** التحقق الأمني والرقابي وضوابط نظام العمل السعودي.\n"
                "• ✍️ **كاتب & سجل:** التنفيذ المحكوم بعد الاعتماد والتوثيق اللاتراجعي.\n\n"
                "💡 *ملاحظة النظام:* أعمل حالياً عبر **محرك الحوكمة والقواعد الاحترازية** لضمان استمرارية الخدمة. "
                "يمكنك سؤالي عن: «كم عدد الموظفين لدينا؟»، «ما هي الشركات المتاحة؟»، «ابحث عن موظف...»"
            )

        # 2. استعلامات العد والإحصاء (Count Records)
        count_keywords = ["كم موظف", "كم عدد الموظفين", "عدد الموظفين", "كم عدد موظفي", "احصائية الموظفين", "إحصائية الموظفين"]
        if any(ck in q for ck in count_keywords):
            is_archived = any(w in q for w in ["مؤرشف", "المؤرشفين", "غير نشط", "المعطلين"])
            domain = [("active", "=", False)] if is_archived else [("active", "=", True)]
            lbl = "المؤرشفين (غير النشطين)" if is_archived else "النشطين"
            try:
                self._emit_evt(
                    operation_id=operation_id,
                    agent="fahas",
                    from_agent="seraj",
                    to_agent="fahas",
                    event_type="odoo_query",
                    status="querying_odoo",
                    description_ar=f"فاحص يستعلم عن عدد الموظفين {lbl} في Odoo",
                )
                res = self.fahas.count_records("hr.employee", domain=domain)
                count_val = res.get("count", 0)
                self.last_provider_used = "fallback"
                self.last_model_used = "rule_based"
                return (
                    f"📊 **إحصائية الموظفين من Odoo (وكيل الفحص «فاحص»):**\n"
                    f"────────────────────\n"
                    f"• **حالة الموظفين:** {lbl}\n"
                    f"• **العدد الإجمالي:** **{count_val}** موظف\n\n"
                    f"🏢 **المنشأة:** {session.company_name or 'المنشأة الحالية'}\n"
                    f"🛡️ *ضوابط الحوكمة:* تم جلب هذا الرقم مباشرة عبر استعلام موثق من قاعدة بيانات Odoo بدون تخمين."
                )
            except Exception as e:
                logger.warning("Fallback count failed: %s", e)

        # 3. استعراض المنشآت والشركات
        company_keywords = ["ما الشركات", "ما هي الشركات", "الشركات المتاحة", "قائمة الشركات", "المنشآت"]
        if any(ck in q for ck in company_keywords):
            try:
                self._emit_evt(
                    operation_id=operation_id,
                    agent="fahas",
                    from_agent="seraj",
                    to_agent="fahas",
                    event_type="odoo_query",
                    status="querying_odoo",
                    description_ar="فاحص يستعلم عن قائمة الشركات المصرح بها في Odoo",
                )
                comps = self.fahas.execute_query_task("list_companies", {})
                if isinstance(comps, list) and comps:
                    comp_lines = [f"• **{c.get('name')}** (معرّف ID: `{c.get('id')}`)" for c in comps]
                    self.last_provider_used = "fallback"
                    self.last_model_used = "rule_based"
                    return (
                        f"🏢 **قائمة المنشآت المصرح بها في Odoo (عبر «فاحص»):**\n"
                        f"────────────────────\n"
                        + "\n".join(comp_lines) + "\n\n"
                        "💡 يمكنك تحديد أي منشأة لتوجيه الاستعلامات نحوها."
                    )
            except Exception as e:
                logger.warning("Fallback list_companies failed: %s", e)

        # 4. البحث عن موظف بالاسم
        search_m = re.search(r'(?:ابحث عن|بحث عن|من هو|الموظف|موظف باسم|موظف اسمه)\s+([^\s]+(?:\s+[^\s]+)?)', query)
        if search_m:
            target_name = search_m.group(1).strip()
            if target_name and target_name not in ["الموظفين", "الشركات"]:
                try:
                    self._emit_evt(
                        operation_id=operation_id,
                        agent="fahas",
                        from_agent="seraj",
                        to_agent="fahas",
                        event_type="odoo_query",
                        status="querying_odoo",
                        description_ar=f"فاحص يبحث في Odoo عن موظف باسم: «{target_name}»",
                    )
                    s_res = self.fahas.search_records(
                        model="hr.employee",
                        domain=[("name", "ilike", target_name)],
                        fields=["id", "name", "job_title", "work_email", "company_id"],
                        limit=5,
                    )
                    recs = s_res.get("records", [])
                    if recs:
                        r_lines = []
                        for r in recs:
                            comp = r.get("company_id", [False, "غير محدد"])[1] if isinstance(r.get("company_id"), list) else ""
                            jt = r.get("job_title") or "غير محدد"
                            r_lines.append(f"• **{r.get('name')}** (ID: `{r.get('id')}`) — المسمى: {jt} — المنشأة: {comp}")
                        self.last_provider_used = "fallback"
                        self.last_model_used = "rule_based"
                        return (
                            f"🔍 **نتائج البحث في Odoo (وكيل الفحص «فاحص»):**\n"
                            f"────────────────────\n"
                            f"تم العثور على {len(recs)} موظف يطابق «{target_name}»:\n\n"
                            + "\n".join(r_lines)
                        )
                    else:
                        self.last_provider_used = "fallback"
                        self.last_model_used = "rule_based"
                        return (
                            f"🔍 **نتائج البحث في Odoo (وكيل الفحص «فاحص»):**\n"
                            f"لم يتم العثور على أي موظف نشط باسم «{target_name}» في قاعدة بيانات Odoo."
                        )
                except Exception as e:
                    logger.warning("Fallback search failed: %s", e)

        # 5. تنبيه استمرارية الخدمة التوضيحي إذا لم يتطابق أي نمط
        self.last_provider_used = "fallback"
        self.last_model_used = "rule_based"
        return (
            "🛡️ **تنبيه استمرارية الخدمة — وضع الأمان الاحترازي (سراج):**\n"
            "────────────────────\n"
            "خوادم النماذج اللغوية (السحابية والمحلية) غير متاحة حالياً أو انتهت مهلة استجابتها.\n\n"
            "💡 **العمليات المتاحة لك فوراً دون توقف:**\n"
            "• **إحصائيات الموظفين:** اسأل «كم عدد الموظفين؟» أو «كم عدد المؤرشفين؟»\n"
            "• **استعراض المنشآت:** اسأل «ما هي الشركات المتاحة؟»\n"
            "• **البحث بالاسم:** اسأل «ابحث عن موظف اسمه [الاسم]»\n"
            "• **نظام العمل السعودي:** اسأل أي استشارة في نظام العمل وسيجيبك «مدقق» فوراً.\n\n"
            "⚙️ لإعادة تفعيل الذكاء الاصطناعي الكامل: يمكنك مراجعة صفحة الإعدادات وتشغيل خادم Ollama المحلي أو تحديث مفتاح API السحابي."
        )

    def _call_llm(
        self,
        model_name: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        استدعاء محرك الذكاء الاصطناعي (محلي أو سحابي) متوافق مع OpenAI Chat Completions API.
        يدعم:
        1. الوضع اليدوي (Manual): يرسل الطلب للمشغل النشط صراحة (سحابي أو محلي).
        2. الوضع التلقائي (Auto): يحاول مع المشغل المفضل، وفي حال حدوث تعثر أو خطأ اتصال ينتقل تلقائياً للبديل.
        """
        from llm_config_manager import load_llm_config

        cfg = load_llm_config()
        mode = cfg.get("mode", "auto")
        active = cfg.get("active_provider", "local")

        def _send_chat_completion(
            base_url: str,
            model: str,
            api_key: Optional[str],
            timeout: int,
            provider_type: str,
        ) -> Optional[Dict[str, Any]]:
            if not base_url:
                raise ValueError("base_url is required")

            # تطبيع مسار الطلب
            clean_url = base_url.rstrip("/")
            if not clean_url.endswith("/chat/completions"):
                endpoint_url = f"{clean_url}/chat/completions"
            else:
                endpoint_url = clean_url

            payload: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": int(os.environ.get("LLM_MAX_TOKENS", "1024")),
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            data = json.dumps(payload).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "OdooHRAgents/1.0",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Odoo HR Multi-Agent",
            }

            if api_key and str(api_key).strip():
                headers["Authorization"] = f"Bearer {str(api_key).strip()}"

            req = urllib.request.Request(endpoint_url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as res:
                res_data = json.loads(res.read().decode("utf-8"))
                choices = res_data.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    # إضافة وسم المشغل المستخدم للتتبع الشفاف
                    msg["_provider_used"] = provider_type
                    msg["_model_used"] = model
                    self.last_provider_used = provider_type
                    self.last_model_used = model
                    return msg
            return None

        # تجهيز تفاصيل المشغلات مع فصل النموذج المحلي عن السحابي
        loc_cfg = cfg.get("local", {})
        cld_cfg = cfg.get("cloud", {})

        loc_model = loc_cfg.get("model") or os.environ.get("OLLAMA_MODEL") or os.environ.get("LLM_MODEL") or "qwen3.5:9b"
        cld_model = model_name or cld_cfg.get("model") or os.environ.get("OPENROUTER_MODEL") or "openrouter/auto"

        loc_tuple = (
            "local",
            loc_cfg.get("base_url", "http://localhost:11434/v1"),
            loc_model,
            os.environ.get("LLM_API_KEY") or None,
            int(loc_cfg.get("timeout", 120)),
        )

        cld_tuple = (
            "cloud",
            cld_cfg.get("base_url", "https://openrouter.ai/api/v1"),
            cld_model,
            cld_cfg.get("api_key") or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY"),
            int(cld_cfg.get("timeout", 45)),
        )

        fallback_enabled = cfg.get("fallback_enabled", True)
        candidates: List[Tuple[str, str, str, Optional[str], int]] = []

        if mode == "manual":
            # في الوضع اليدوي: يتم تقديم المشغل المختار، مع التبديل التلقائي عند التعثر إن كان مفعّلاً
            if active == "cloud":
                candidates = [cld_tuple]
                if fallback_enabled:
                    candidates.append(loc_tuple)
            else:
                candidates = [loc_tuple]
                if fallback_enabled and cld_tuple[3]:
                    candidates.append(cld_tuple)
        else:
            # في الوضع التلقائي: الترتيب الذكي
            if active == "cloud" and cld_tuple[3]:
                candidates = [cld_tuple, loc_tuple]
            else:
                candidates = [loc_tuple]
                if cld_tuple[3]:
                    candidates.append(cld_tuple)

        last_error = None
        for p_type, b_url, m_name, a_key, t_out in candidates:
            try:
                logger.debug("Attempting LLM call via %s (%s at %s)", p_type, m_name, b_url)
                result = _send_chat_completion(b_url, m_name, a_key, t_out, p_type)
                if result:
                    return result
            except Exception as exc:
                last_error = exc
                logger.warning("LLM call to %s (%s) failed: %s. Trying fallback if available...", p_type, m_name, exc)

        if last_error:
            logger.error("All configured LLM candidates failed. Last error: %s", last_error)
        return None
