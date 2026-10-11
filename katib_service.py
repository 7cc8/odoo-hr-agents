"""
خدمة وكيل الكتابة المعتمد: «كاتب» (Katib Authorized Write Gateway & Execution)
=============================================================================
كاتب هو المنفذ الحصري والوحيد لأي عمليات كتابة (إنشاء create، تعديل write) في Odoo:
1. لا ينفذ كاتب أي أمر إلا بعد استيفاء الاعتماد الصريح وفحص البيئة عبر «حارس».
2. التحقق من أن قاعدة البيانات مصرح بالكتابة فيها (ALLOWED_TEST_DBS أو ALLOWED_DEV_DBS).
3. حظر أي عمليات حذف كلي (unlink) حظراً باتاً.
4. تنفيذ العملية عبر OdooWriteGateway وإرجاع النتيجة الفنية الدقيقة.
5. توثيق العملية فوراً عبر سجل التدقيق JSONL.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from approval_plan_schema import ApprovalPlan, ApprovalPlanError, validate_plan_for_execution
from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS
from odoo_write_gateway import OdooWriteGateway, WriteGatewayError, EnvironmentGuardError
from odoo_delete_gateway import (
    OdooDeleteGateway,
    DeleteGatewayError,
    DeleteGatewayOdooRejectionError,
    DeleteGatewayEnvironmentGuardError,
)

logger = logging.getLogger("katib_service")

AUDIT_LOG_DIR = Path(__file__).resolve().parent / "logs"
AUDIT_LOG_FILE = AUDIT_LOG_DIR / "writer_audit_log.jsonl"
DELETION_AUDIT_LOG_FILE = AUDIT_LOG_DIR / "deletion_audit_log.jsonl"


class KatibSecurityError(Exception):
    """خطأ أمني عند محاولة تنفيذ عملية غير مصرح بها أو على بيئة غير مسموحة."""


class KatibExecutionError(Exception):
    """خطأ تنفيذي أثناء الكتابة في قاعدة بيانات Odoo."""


class KatibAgent:
    """وكيل الكتابة المعتمد والمنفذ الحصري لعمليات الإنشاء والتعديل في Odoo."""

    def __init__(
        self,
        url: Optional[str] = None,
        db: Optional[str] = None,
        login: Optional[str] = None,
        password: Optional[str] = None,
        gateway: Optional[OdooWriteGateway] = None,
        delete_gateway: Optional[OdooDeleteGateway] = None,
    ) -> None:
        self._gateway = gateway
        self._delete_gateway = delete_gateway
        self._url = url
        self._db = db
        self._login = login
        self._password = password

    def _get_gateway(self) -> OdooWriteGateway:
        if self._gateway is not None:
            return self._gateway

        url = self._url or os.environ.get("ODOO_URL", "")
        db = self._db or os.environ.get("ODOO_DB", "")
        login = self._login or os.environ.get("ODOO_USER") or os.environ.get("ODOO_USERNAME", "")
        password = self._password or os.environ.get("ODOO_API_KEY", "")

        if not all([url, db, login, password]):
            raise KatibSecurityError("بيانات الاتصال ببوابة الكتابة غير مكتملة في ملف البيئة.")

        # فحص البيئة (حارس)
        all_allowed_dbs = ALLOWED_TEST_DBS | ALLOWED_DEV_DBS
        if db not in all_allowed_dbs:
            raise KatibSecurityError(
                f"حارس البيئة: قاعدة البيانات «{db}» غير مدرجة ضمن بيئات الاختبار المصرح بالكتابة فيها."
            )

        self._gateway = OdooWriteGateway(url=url, db=db, login=login, password=password)
        return self._gateway

    def _get_delete_gateway(self) -> OdooDeleteGateway:
        if self._delete_gateway is not None:
            return self._delete_gateway

        url = self._url or os.environ.get("ODOO_URL", "")
        db = self._db or os.environ.get("ODOO_DB", "")
        login = self._login or os.environ.get("ODOO_USER") or os.environ.get("ODOO_USERNAME", "")
        password = self._password or os.environ.get("ODOO_API_KEY", "")

        if not all([url, db, login, password]):
            raise KatibSecurityError("بيانات الاتصال ببوابة الحذف المعزولة غير مكتملة في ملف البيئة.")

        all_allowed_dbs = ALLOWED_TEST_DBS | ALLOWED_DEV_DBS
        if db not in all_allowed_dbs:
            raise KatibSecurityError(
                f"حارس البيئة: قاعدة البيانات «{db}» غير مصرح بالحذف فيها نهائياً."
            )

        self._delete_gateway = OdooDeleteGateway(url=url, db=db, login=login, password=password)
        return self._delete_gateway

    def log_audit_record(self, record: Dict[str, Any]) -> None:
        """توثيق العملية في سجل التدقيق (Append-Only JSONL)."""
        try:
            AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as exc:
            logger.error("فشل توثيق العملية في سجل التدقيق: %s", exc)

    def log_deletion_record(self, record: Dict[str, Any]) -> None:
        """توثيق عمليات الأرشفة والحذف في سجل مخصص دون تخزين أسرار أو نسخ بيانات شخصية غير لازمة."""
        try:
            AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(DELETION_AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as exc:
            logger.error("فشل توثيق العملية في سجل تدقيق الحذف: %s", exc)

    def create_employee(self, values: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> int:
        """إنشاء موظف جديد بعد اعتماد العملية."""
        gateway = self._get_gateway()
        new_id = gateway.create_employee(values, context=context)
        self.log_audit_record({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": "katib_write",
            "action": "create_employee",
            "employee_id": new_id,
            "values": values,
            "status": "success",
        })
        return new_id

    def update_employee(
        self, employee_id: int, values: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """تعديل موظف موجود بعد اعتماد العملية."""
        gateway = self._get_gateway()
        success = gateway.write_employee(employee_id, values, context=context)
        self.log_audit_record({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": "katib_write",
            "action": "update_employee",
            "employee_id": employee_id,
            "values": values,
            "status": "success" if success else "failed",
        })
        return success

    def execute_approved_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        تنفيذ عملية معتمدة قادمة من منسق المهام «سراج» بعد موافقة صاحب الصلاحية:
        يدعم الإنشاء (create)، التعديل (update)، الأرشفة (archive)، والحذف المحكوم (delete).
        الحذف ينفذ حصرياً عبر البوابة المعزولة OdooDeleteGateway لسجل مفرد فقط.
        
        P5-S3: التحقق من ApprovalPlan (TTL + استهلاك واحد + مستخدم)
        """
        action_type = action.get("action_type") or action.get("type")
        
        # P5-S3: فحص ApprovalPlan قبل التنفيذ
        plan_id = action.get("plan_id")
        if not plan_id:
            raise KatibSecurityError(
                "P5-S3: لا تنفيذ بدون plan_id. كل عملية كتابة تتطلب ApprovalPlan صالحة."
            )
        
        try:
            # تحميل الخطة
            plan = ApprovalPlan.load(plan_id)
            
            # التحقق من صلاحية الخطة (TTL + consumed + approved)
            validate_plan_for_execution(plan)
            
            # استهلاك الخطة (single-use)
            plan.consume()
            plan.save()
            
            logger.info(f"✅ ApprovalPlan {plan_id} consumed successfully")
        
        except ApprovalPlanError as err:
            logger.error(f"❌ ApprovalPlan validation failed: {err}")
            raise KatibSecurityError(f"P5-S3: خطة غير صالحة - {err}") from err

        # مسار الأرشفة المحكومة
        if action_type == "archive":
            model = action.get("model", "hr.employee")
            rec_id = action.get("record_id") or action.get("employee_id")
            if not rec_id or not isinstance(rec_id, int):
                raise KatibExecutionError("معرف السجل غير محدد أو غير صالح للأرشفة.")
            gateway = self._get_gateway()
            ok = gateway.write_record(model, rec_id, {"active": False})
            del_rec = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": "katib_archive",
                "action": "archive",
                "model": model,
                "record_id": rec_id,
                "plan_id": action.get("plan_id"),
                "status": "success" if ok else "failed",
            }
            if action.get("conversation_snippet"):
                del_rec["conversation_snippet"] = action.get("conversation_snippet")
            if action.get("reason"):
                del_rec["original_request"] = action.get("reason")
            if action.get("chat_id"):
                del_rec["chat_id"] = action.get("chat_id")
            self.log_deletion_record(del_rec)
            return {
                "ok": ok,
                "action": "archive",
                "model": model,
                "record_id": rec_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # مسار إلغاء الأرشفة / الاسترجاع (Unarchive / Restore)
        elif action_type == "unarchive":
            model = action.get("model", "hr.employee")
            rec_id = action.get("record_id") or action.get("employee_id")
            if not rec_id or not isinstance(rec_id, int):
                raise KatibExecutionError("معرف السجل غير محدد أو غير صالح للاسترجاع من الأرشفة.")
            gateway = self._get_gateway()
            ok = gateway.write_record(model, rec_id, {"active": True})
            del_rec = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": "katib_unarchive",
                "action": "unarchive",
                "model": model,
                "record_id": rec_id,
                "plan_id": action.get("plan_id"),
                "status": "success" if ok else "failed",
            }
            if action.get("conversation_snippet"):
                del_rec["conversation_snippet"] = action.get("conversation_snippet")
            if action.get("reason"):
                del_rec["original_request"] = action.get("reason")
            if action.get("chat_id"):
                del_rec["chat_id"] = action.get("chat_id")
            self.log_deletion_record(del_rec)
            return {
                "ok": ok,
                "action": "unarchive",
                "model": model,
                "record_id": rec_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # مسار الحذف النهائي المحكوم
        elif action_type == "delete":
            model = action.get("model", "hr.employee")
            record_id = action.get("record_id") or action.get("employee_id")
            if not record_id or not isinstance(record_id, int):
                raise KatibExecutionError("معرف السجل غير محدد أو غير صالح للحذف.")

            del_gateway = self._get_delete_gateway()
            try:
                ok = del_gateway.delete_single_record(model=model, record_id=record_id)
                del_rec = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "stage": "katib_delete",
                    "action": "delete",
                    "model": model,
                    "record_id": record_id,
                    "plan_id": action.get("plan_id"),
                    "status": "success",
                }
                if action.get("conversation_snippet"):
                    del_rec["conversation_snippet"] = action.get("conversation_snippet")
                if action.get("reason"):
                    del_rec["original_request"] = action.get("reason")
                if action.get("chat_id"):
                    del_rec["chat_id"] = action.get("chat_id")
                self.log_deletion_record(del_rec)
                return {
                    "ok": True,
                    "action": "delete",
                    "model": model,
                    "record_id": record_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            except DeleteGatewayOdooRejectionError as err:
                del_rec = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "stage": "katib_delete",
                    "action": "delete",
                    "model": model,
                    "record_id": record_id,
                    "plan_id": action.get("plan_id"),
                    "status": "odoo_rejected",
                    "error": str(err),
                }
                if action.get("conversation_snippet"):
                    del_rec["conversation_snippet"] = action.get("conversation_snippet")
                if action.get("reason"):
                    del_rec["original_request"] = action.get("reason")
                if action.get("chat_id"):
                    del_rec["chat_id"] = action.get("chat_id")
                self.log_deletion_record(del_rec)
                return {
                    "ok": False,
                    "status": "odoo_rejected",
                    "action": "delete",
                    "model": model,
                    "record_id": record_id,
                    "error": str(err),
                }

        elif action_type == "update":
            emp_id = action.get("record_id") or action.get("employee_id")
            if not emp_id or not isinstance(emp_id, int):
                raise KatibExecutionError("معرف الموظف غير محدد أو غير صالح للتعديل.")
            field_name = action.get("field")
            new_val = action.get("new_value")
            values = action.get("values") or {field_name: new_val}
            
            ok = self.update_employee(emp_id, values)
            return {
                "ok": ok,
                "action": "update",
                "employee_id": emp_id,
                "values": values,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        elif action_type == "create":
            values = action.get("values") or {
                "name": action.get("name"),
                "work_email": action.get("work_email"),
                "company_id": action.get("company_id"),
            }
            new_id = self.create_employee(values)
            return {
                "ok": True,
                "action": "create",
                "employee_id": new_id,
                "values": values,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        raise KatibExecutionError(f"نوع العملية «{action_type}» غير مدعوم لدى كاتب.")


_GLOBAL_KATIB: Optional[KatibAgent] = None


def get_katib_agent() -> KatibAgent:
    """الحصول على كائن وكيل كاتب المفرد (Singleton)."""
    global _GLOBAL_KATIB
    if _GLOBAL_KATIB is None:
        _GLOBAL_KATIB = KatibAgent()
    return _GLOBAL_KATIB
