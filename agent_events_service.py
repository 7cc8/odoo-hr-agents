"""
خدمة الأحداث وإدارة سير العمليات لمنظومة الوكلاء (Agent Events & Operations Service)
=====================================================================================
المصدر الحقيقي والمركزي لأحداث التنفيذ الفعلي لمنظومة وكلاء Odoo HR:
- تسجيل الأحداث الحقيقية وتوثيق مسار العمليات دون تزييف أو مؤقتات وهمية.
- متابعة الحالات التشغيلية الدقيقة لكل وكيل من الوكلاء الـ 8 المعتمدين.
- ربط الأحداث مع سجل (Sijil) وتخزينها في الدفتر اللاتراجعي logs/agent_operations_log.jsonl.
- دعم البث المباشر للأحداث (SSE) والاسترجاع المستقل عند انقطاع الاتصال أو تحديث الصفحة.
- حماية سرية البيانات وعزل النطاقات والشركات.
"""

from __future__ import annotations

import os
import json
import uuid
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
AGENT_OPS_LOG_FILE = LOGS_DIR / "agent_operations_log.jsonl"

# تعريف الوكلاء الـ 8 المعتمدين
AGENTS_REGISTRY: Dict[str, Dict[str, Any]] = {
    "seraj": {
        "id": "seraj",
        "name_ar": "سراج",
        "title_ar": "المنسق العام والمحاور",
        "role_ar": "المنسق والمحاور ومتابع المهام",
        "accent_color": "#38bdf8",  # Sky Blue
        "border_color": "#0284c7",
        "bg_soft": "rgba(56, 189, 248, 0.08)",
        "icon": "sparkles",
        "is_helper": False,
        "description_short": "إدارة الحوار وتوجيه الطلبات وتنسيق المهام بين الوكلاء وشرح النتائج",
    },
    "fahas": {
        "id": "fahas",
        "name_ar": "فاحص",
        "title_ar": "وكيل الاستعلام والتحقق",
        "role_ar": "القراءة والتحقق من بيانات Odoo",
        "accent_color": "#06b6d4",  # Cyan
        "border_color": "#0891b2",
        "bg_soft": "rgba(6, 182, 212, 0.08)",
        "icon": "search",
        "is_helper": False,
        "description_short": "القراءة والاستعلام والتحقق المستقل بعد التنفيذ (Readback Verification)",
    },
    "modaqeq": {
        "id": "modaqeq",
        "name_ar": "مدقق",
        "title_ar": "وكيل التدقيق والامتثال",
        "role_ar": "التحقق من البيانات والقواعد",
        "accent_color": "#6366f1",  # Indigo
        "border_color": "#4f46e5",
        "bg_soft": "rgba(99, 102, 241, 0.08)",
        "icon": "shield-check",
        "is_helper": False,
        "description_short": "فحص سلامة البيانات وقواعد نظام العمل والتطابق المرجعي",
    },
    "mowafaq": {
        "id": "mowafaq",
        "name_ar": "موفق",
        "title_ar": "وكيل المطابقة الذكية",
        "role_ar": "المطابقة عند الحاجة",
        "accent_color": "#ec4899",  # Pink
        "border_color": "#db2777",
        "bg_soft": "rgba(236, 72, 153, 0.08)",
        "icon": "git-merge",
        "is_helper": False,
        "description_short": "مطابقة الأسماء والمسميات والكيانات عند الالتباس أو تباين الصياغة",
    },
    "hares": {
        "id": "hares",
        "name_ar": "حارس",
        "title_ar": "وكيل الحوكمة والصلاحيات",
        "role_ar": "الصلاحيات والسياسات والاعتماد",
        "accent_color": "#ef4444",  # Coral Red
        "border_color": "#dc2626",
        "bg_soft": "rgba(239, 68, 68, 0.08)",
        "icon": "lock",
        "is_helper": False,
        "description_short": "حواجز الأمان وعزل النماذج وإصدار خطط الاعتماد والتحقق المزدوج",
    },
    "musleh": {
        "id": "musleh",
        "name_ar": "مصلح",
        "title_ar": "وكيل المعالجة الذاتية",
        "role_ar": "التشخيص والمعالجة ضمن الحدود",
        "accent_color": "#f59e0b",  # Amber
        "border_color": "#d97706",
        "bg_soft": "rgba(245, 158, 11, 0.08)",
        "icon": "wrench",
        "is_helper": False,
        "description_short": "تشخيص الأخطاء التشغيلية والمعالجة الذاتية ضمن السياسات والحجر الصحي",
    },
    "katib": {
        "id": "katib",
        "name_ar": "كاتب",
        "title_ar": "وكيل التنفيذ والكتابة",
        "role_ar": "تنفيذ العملية المعتمدة",
        "accent_color": "#10b981",  # Emerald / Phosphor Green
        "border_color": "#059669",
        "bg_soft": "rgba(16, 185, 129, 0.08)",
        "icon": "pencil",
        "is_helper": False,
        "description_short": "المنفذ الحصري لعمليات الكتابة والتعديل والأرشفة والحذف المحكوم في Odoo",
    },
    "sijil": {
        "id": "sijil",
        "name_ar": "سجل",
        "title_ar": "وكيل الرقابة والتوثيق",
        "role_ar": "توثيق الأحداث والنتائج",
        "accent_color": "#9281f7",  # Iris Violet
        "border_color": "#7c3aed",
        "bg_soft": "rgba(146, 129, 247, 0.08)",
        "icon": "book-open",
        "is_helper": False,
        "description_short": "التوثيق اللاتراجعي للعمليات وإصدار تقارير التدقيق والحوكمة الرسمية PDF",
    },
}

# الحالات التشغيلية الدقيقة المنصوص عليها
STATUS_LABELS_AR: Dict[str, str] = {
    "idle": "جاهز",
    "ready": "جاهز",
    "analyzing_request": "يحلل الطلب",
    "querying_odoo": "يستعلم من Odoo",
    "inspecting_data": "يفحص البيانات",
    "matching_references": "يقارن المراجع",
    "verifying_permissions": "يتحقق من الصلاحيات",
    "waiting_user_clarification": "ينتظر توضيح المستخدم",
    "waiting_clarification": "ينتظر توضيح المستخدم",
    "waiting_approval": "ينتظر الاعتماد",
    "executing_write": "ينفذ التعديل",
    "verifying_result": "يتحقق من النتيجة",
    "documenting_audit": "يوثق العملية",
    "completed": "اكتمل",
    "failed": "تعذر التنفيذ",
    "inconclusive": "النتيجة غير محسومة",
    "disconnected": "انقطع اتصال متابعة الأحداث",
}


def _mask_safe_ref(obj: Any) -> Any:
    """إزالة الأسرار وكلمات المرور والبيانات الحساسة من مراجع النتائج المعروضة."""
    if isinstance(obj, dict):
        clean = {}
        for k, v in obj.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("password", "token", "secret", "api_key", "credential")):
                clean[k] = "••••••••"
            else:
                clean[k] = _mask_safe_ref(v)
        return clean
    elif isinstance(obj, list):
        return [_mask_safe_ref(i) for i in obj]
    return obj


def is_odoo_operation_event(event_data: Dict[str, Any]) -> bool:
    """
    التحقق الصارم مما إذا كان الحدث يمثل عملية فعلية مؤثرة داخل Odoo تستوجب التوثيق في «سجل»:
    - حذف (delete / unlink / remove)
    - أرشفة (archive / unarchive)
    - إضافة / إنشاء (create / add / insert / new_employee / batch_imported)
    - تعديل (update / modify / edit / write)

    يُستبعد تماماً وبشكل قاطع:
    - أسئلة واستفسارات المستخدم والرسائل العادية (chat_turn, message_received)
    - استعلامات القراءة والبحث من Odoo (read, count, search, fields_get, odoo_query)
    - استشارات نظام العمل وشروحات المواد القانونية (labor_law_consultation)
    - رسائل المتابعة وطلب التوضيح وتحديثات الحالة العادية
    """
    evt_type = str(event_data.get("event_type", "")).lower()
    desc = str(event_data.get("description_ar", "")).lower()
    agent = str(event_data.get("agent", "")).lower()
    metadata = event_data.get("metadata") or {}
    action = str(metadata.get("action") or event_data.get("action") or "").lower()

    # 1. استبعاد صريح وقاطع لكافة الأسئلة واستعلامات القراءة والاستشارات
    EXCLUDED_TYPES = {
        "operation_started", "query_received", "odoo_query", "task_completed",
        "waiting_clarification", "clarification_answered", "labor_law_consult",
        "labor_law_consultation", "chat_turn", "message_received", "search",
        "read", "count", "browse"
    }
    if evt_type in EXCLUDED_TYPES:
        return False

    # استبعاد أي وصف يرتبط بالاستعلام أو القراءة أو الاستشارة أو المحادثة
    EXCLUDED_WORDS = ("استعلام", "يحلل الطلب", "يشرح النتيجة", "استشارة", "استفسار", "سؤال", "بحث عن")
    if any(w in desc for w in EXCLUDED_WORDS):
        return False

    # 2. أحداث تنفيذ العمليات الفعلية المؤثرة في Odoo
    MUTATING_EVENT_TYPES = {
        "write_executed", "deletion_executed", "record_created", "record_updated",
        "record_archived", "record_unarchived", "record_deleted", "batch_imported",
        "contract_applied", "payroll_applied", "loan_applied", "warning_applied",
        "letter_applied", "expense_applied", "leave_applied", "record_audit_logged"
    }
    if evt_type in MUTATING_EVENT_TYPES:
        return True

    # 3. عمليات كاتب المعتمدة (المنفذ الحصري للعمليات المؤثرة في Odoo)
    if agent == "katib" and event_data.get("status") in ("completed", "executing_write", "success", "executing_delete"):
        return True

    # 4. فحص الإجراء المباشر الصريح (حذف، أرشفة، إضافة، تعديل)
    MUTATING_ACTIONS = {
        "create", "add", "insert", "update", "modify", "edit", "write",
        "archive", "unarchive", "delete", "unlink", "remove", "apply", "import",
        "حذف", "أرشفة", "إضافة", "إنشاء", "تعديل"
    }
    if action in MUTATING_ACTIONS:
        return True

    return False


class AgentEventsService:
    """
    محرك إدارة الأحداث والعمليات لمنظومة الوكلاء.
    Thread-safe، يحفظ السجلات في الذاكرة وفي ملف JSONL اللاتراجعي الموحد مع سجل.
    """

    _instance: Optional[AgentEventsService] = None
    _lock = threading.Lock()

    def __init__(self):
        self._lock = threading.Lock()
        self.operations: Dict[str, Dict[str, Any]] = {}
        self.operation_events: Dict[str, List[Dict[str, Any]]] = {}
        self.agent_statuses: Dict[str, Dict[str, Any]] = {
            a_id: {
                "agent_id": a_id,
                "status_code": "ready",
                "status_label": "جاهز",
                "active_operation_id": None,
                "last_active_at": None,
                "last_task": "في انتظار المهام",
            }
            for a_id in AGENTS_REGISTRY
        }
        self._load_recent_from_disk()

    @classmethod
    def get_instance(cls) -> AgentEventsService:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _load_recent_from_disk(self) -> None:
        """قراءة آخر أحداث مسجلة لتهيئة الحالة عند إعادة تشغيل الخادم."""
        if not AGENT_OPS_LOG_FILE.exists():
            return
        try:
            with open(AGENT_OPS_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                # P3: تحسين - تحميل آخر 200 سطر بدلاً من 100 لضمان تغطية أفضل
                for line in lines[-200:]:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                        if not is_odoo_operation_event(evt):
                            continue
                        op_id = evt.get("operation_id")
                        if not op_id:
                            continue
                        if op_id not in self.operation_events:
                            self.operation_events[op_id] = []
                        self.operation_events[op_id].append(evt)
                        if op_id not in self.operations:
                            self.operations[op_id] = {
                                "operation_id": op_id,
                                "created_at": evt.get("timestamp"),
                                "updated_at": evt.get("timestamp"),
                                "user_query": evt.get("user_query", "عملية موثقة"),
                                "operation_type": evt.get("operation_type", "operation"),
                                "status": evt.get("status", "completed"),
                                "status_label": STATUS_LABELS_AR.get(evt.get("status", "completed"), "اكتمل"),
                                "active_agent": evt.get("agent", "sijil"),
                                "company_id": evt.get("company_id"),
                                "company_name": evt.get("company_name"),
                                "connection_id": evt.get("connection_id", "default"),
                                "requester": evt.get("requester", "المستخدم"),
                                "plan_id": evt.get("plan_id"),
                                "plan": None,
                                "clarification": None,
                                "laya_used": evt.get("laya_used", False),
                            }
                    except Exception:
                        continue
        except Exception:
            pass

    def start_operation(
        self,
        user_query: str,
        operation_type: str = "query",
        company_id: Optional[int] = None,
        company_name: Optional[str] = None,
        connection_id: str = "default",
        requester: str = "المستخدم",
        chat_id: str = "default",
        operation_id: Optional[str] = None,
    ) -> str:
        """بدء عملية جديدة وتسجيلها في المنظومة."""
        with self._lock:
            op_id = operation_id or f"op_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            now_iso = datetime.now(timezone.utc).isoformat()

            self.operations[op_id] = {
                "operation_id": op_id,
                "created_at": now_iso,
                "updated_at": now_iso,
                "user_query": user_query.strip(),
                "operation_type": operation_type,
                "status": "analyzing_request",
                "status_label": STATUS_LABELS_AR.get("analyzing_request", "يحلل الطلب"),
                "active_agent": "seraj",
                "company_id": company_id,
                "company_name": company_name,
                "connection_id": connection_id,
                "requester": requester,
                "chat_id": chat_id,
                "plan_id": None,
                "plan": None,
                "clarification": None,
                "laya_used": False,
                "result": None,
                "error": None,
            }
            self.operation_events[op_id] = []

            # تحديث حالة سراج
            self.agent_statuses["seraj"]["status_code"] = "analyzing_request"
            self.agent_statuses["seraj"]["status_label"] = STATUS_LABELS_AR["analyzing_request"]
            self.agent_statuses["seraj"]["active_operation_id"] = op_id
            self.agent_statuses["seraj"]["last_active_at"] = now_iso
            self.agent_statuses["seraj"]["last_task"] = f"استلام وتحليل الطلب: «{user_query[:40]}...»"

            # تسجيل الحدث الأولي
            self._emit_event_locked(
                operation_id=op_id,
                agent="seraj",
                event_type="operation_started",
                status="analyzing_request",
                description_ar=f"سراج يستلم الطلب ويحلل نية المستخدم: «{user_query[:50]}»",
                from_agent=None,
                to_agent="seraj",
                company_id=company_id,
                company_name=company_name,
                connection_id=connection_id,
            )

            return op_id

    def emit_event(
        self,
        operation_id: str,
        agent: str = "system",
        event_type: str = "custom",
        status: str = "completed",
        description_ar: str = "",
        from_agent: Optional[str] = None,
        to_agent: Optional[str] = None,
        plan_id: Optional[str] = None,
        plan_version: Optional[str] = None,
        task_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
        result_ref: Optional[Dict[str, Any]] = None,
        laya_used: Optional[bool] = None,
        company_id: Optional[int] = None,
        company_name: Optional[str] = None,
        connection_id: Optional[str] = None,
        plan: Optional[Dict[str, Any]] = None,
        clarification: Optional[Dict[str, Any]] = None,
        final_result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """تسجيل حدث تنفيذي فعلي ونشره وتوثيقه في ملف التدقيق."""
        # توافقية مع استدعاءات تمرر agent_name أو details
        if "agent_name" in kwargs and (not agent or agent == "system"):
            agent = kwargs.pop("agent_name")
        if "details" in kwargs and result_ref is None:
            result_ref = kwargs.pop("details")
        if not description_ar:
            description_ar = f"{agent}: {event_type}"

        with self._lock:
            return self._emit_event_locked(
                operation_id=operation_id,
                agent=agent,
                event_type=event_type,
                status=status,
                description_ar=description_ar,
                from_agent=from_agent,
                to_agent=to_agent,
                plan_id=plan_id,
                plan_version=plan_version,
                task_id=task_id,
                attempt_id=attempt_id,
                result_ref=result_ref,
                laya_used=laya_used,
                company_id=company_id,
                company_name=company_name,
                connection_id=connection_id,
                plan=plan,
                clarification=clarification,
                final_result=final_result,
                error=error,
                metadata=metadata,
                **kwargs,
            )

    def _emit_event_locked(
        self,
        operation_id: str,
        agent: str,
        event_type: str,
        status: str,
        description_ar: str,
        from_agent: Optional[str] = None,
        to_agent: Optional[str] = None,
        plan_id: Optional[str] = None,
        plan_version: Optional[str] = None,
        task_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
        result_ref: Optional[Dict[str, Any]] = None,
        laya_used: Optional[bool] = None,
        company_id: Optional[int] = None,
        company_name: Optional[str] = None,
        connection_id: Optional[str] = None,
        plan: Optional[Dict[str, Any]] = None,
        clarification: Optional[Dict[str, Any]] = None,
        final_result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()
        evt_list = self.operation_events.setdefault(operation_id, [])
        seq = len(evt_list) + 1
        evt_id = f"evt_{operation_id}_{seq}"

        safe_result = _mask_safe_ref(result_ref) if result_ref else None

        event_data: Dict[str, Any] = {
            "event_id": evt_id,
            "operation_id": operation_id,
            "sequence": seq,
            "timestamp": now_iso,
            "agent": agent,
            "event_type": event_type,
            "status": status,
            "status_label": STATUS_LABELS_AR.get(status, status),
            "description_ar": description_ar,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "plan_id": plan_id,
            "plan_version": plan_version,
            "task_id": task_id,
            "attempt_id": attempt_id,
            "result_ref": safe_result,
            "laya_used": bool(laya_used),
            "company_id": company_id,
            "company_name": company_name,
            "connection_id": connection_id,
            "metadata": metadata or {},
        }
        if error:
            event_data["error"] = error

        evt_list.append(event_data)

        # تحديث العملية
        if operation_id in self.operations:
            op = self.operations[operation_id]
            op["updated_at"] = now_iso
            op["active_agent"] = to_agent or agent
            op["status"] = status
            op["status_label"] = STATUS_LABELS_AR.get(status, status)
            if plan_id:
                op["plan_id"] = plan_id
            if plan:
                op["plan"] = plan
            if clarification:
                op["clarification"] = clarification
            if laya_used:
                op["laya_used"] = True
            if final_result:
                op["result"] = _mask_safe_ref(final_result)
            if error:
                op["error"] = error

        # تحديث حالة الوكيل النشط
        target_agent = to_agent or agent
        if target_agent in self.agent_statuses:
            self.agent_statuses[target_agent]["status_code"] = status
            self.agent_statuses[target_agent]["status_label"] = STATUS_LABELS_AR.get(status, status)
            self.agent_statuses[target_agent]["active_operation_id"] = operation_id
            self.agent_statuses[target_agent]["last_active_at"] = now_iso
            self.agent_statuses[target_agent]["last_task"] = description_ar

        # إذا اكتملت العملية أو فشلت، تعود الوكلاء تدريجياً لحالة الجاهزية
        if status in ("completed", "failed", "cancelled"):
            if target_agent in self.agent_statuses:
                self.agent_statuses[target_agent]["active_operation_id"] = None
                self.agent_statuses[target_agent]["status_code"] = "ready"
                self.agent_statuses[target_agent]["status_label"] = "جاهز"

        # قيد الحدث في دفتر سجل اللاتراجعي فقط إذا كان عملية فعلية داخل Odoo (حذف، أرشفة، إضافة، تعديل)
        if is_odoo_operation_event(event_data):
            try:
                with open(AGENT_OPS_LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event_data, ensure_ascii=False) + "\n")
            except Exception:
                pass

        return event_data

    def get_operation(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """استرجاع بيانات العملية وكافة أحداثها وخط سيرها."""
        with self._lock:
            op = self.operations.get(operation_id)
            if op:
                res = dict(op)
                res["events"] = list(self.operation_events.get(operation_id, []))
                return res
            
            # P3: البحث في القرص عند عدم وجود العملية في الذاكرة
            return self._search_operation_on_disk(operation_id)
    
    def _search_operation_on_disk(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """البحث عن عملية محددة في ملف السجل على القرص"""
        if not AGENT_OPS_LOG_FILE.exists():
            return None
        
        try:
            operation_events = []
            operation_data = None
            
            with open(AGENT_OPS_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                        if evt.get("operation_id") == operation_id:
                            operation_events.append(evt)
                            # إنشاء بيانات العملية من أول حدث
                            if operation_data is None:
                                operation_data = {
                                    "operation_id": operation_id,
                                    "created_at": evt.get("timestamp"),
                                    "updated_at": evt.get("timestamp"),
                                    "user_query": evt.get("user_query", "عملية موثقة"),
                                    "operation_type": evt.get("operation_type", "operation"),
                                    "status": evt.get("status", "completed"),
                                    "status_label": STATUS_LABELS_AR.get(evt.get("status", "completed"), "اكتمل"),
                                    "active_agent": evt.get("agent", "sijil"),
                                    "company_id": evt.get("company_id"),
                                    "company_name": evt.get("company_name"),
                                    "connection_id": evt.get("connection_id", "default"),
                                    "requester": evt.get("requester", "المستخدم"),
                                    "plan_id": evt.get("plan_id"),
                                    "laya_used": evt.get("laya_used", False),
                                }
                            else:
                                # تحديث آخر تحديث
                                operation_data["updated_at"] = evt.get("timestamp")
                                operation_data["status"] = evt.get("status", operation_data["status"])
                                operation_data["status_label"] = STATUS_LABELS_AR.get(evt.get("status", operation_data["status"]), operation_data["status_label"])
                    except Exception:
                        continue
            
            if operation_data and operation_events:
                operation_data["events"] = operation_events
                return operation_data
            
            return None
            
        except Exception:
            return None

    def get_operation_events(self, operation_id: str, after_seq: int = 0) -> List[Dict[str, Any]]:
        """استرجاع الأحداث اللاحقة لتسلسل معين لدعم التحديث السريع."""
        with self._lock:
            events = self.operation_events.get(operation_id, [])
            return [e for e in events if e.get("sequence", 0) > after_seq]

    def get_recent_operations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """استرجاع قائمة العمليات الأخيرة مرتبة من الأحدث للأقدم."""
        with self._lock:
            ops = list(self.operations.values())
            ops.sort(key=lambda x: str(x.get("updated_at", "")), reverse=True)
            return ops[:limit]

    def get_agents_overview(self) -> List[Dict[str, Any]]:
        """استرجاع بطاقات وهوية كافة الوكلاء الـ 8 + لايا وحالاتهم الحالية."""
        with self._lock:
            result = []
            for a_id, meta in AGENTS_REGISTRY.items():
                st = self.agent_statuses.get(a_id, {})
                item = dict(meta)
                item["status_code"] = st.get("status_code", "ready")
                item["status_label"] = st.get("status_label", "جاهز")
                item["active_operation_id"] = st.get("active_operation_id")
                item["last_active_at"] = st.get("last_active_at")
                item["last_task"] = st.get("last_task", "في انتظار المهام")
                result.append(item)
            return result

    def get_active_operation(self) -> Optional[Dict[str, Any]]:
        """استرجاع العملية النشطة الحالية إن وجدت."""
        with self._lock:
            for op in reversed(list(self.operations.values())):
                if op.get("status") not in ("completed", "failed", "cancelled"):
                    res = dict(op)
                    res["events"] = list(self.operation_events.get(op["operation_id"], []))
                    return res
            # إذا لم توجد عملية نشطة، نرجع أحدث عملية
            if self.operations:
                latest = list(self.operations.values())[-1]
                res = dict(latest)
                res["events"] = list(self.operation_events.get(latest["operation_id"], []))
                return res
            return None

    def clear_memory(self) -> None:
        """مسح كافة العمليات والأحداث من الذاكرة لإعادة الضبط النظيف."""
        with self._lock:
            self.operations.clear()
            self.operation_events.clear()
            for st in self.agent_statuses.values():
                st["status_code"] = "ready"
                st["status_label"] = "جاهز"
                st["active_operation_id"] = None
                st["last_task"] = "في انتظار المهام"


def get_events_service() -> AgentEventsService:
    return AgentEventsService.get_instance()
