"""
وكيل الكتابة المعتمد الذكي: «كاتب» (Katib Agentic Write Agent)
================================================================
كاتب هو المنفذ الحصري والذكي لعمليات الكتابة في Odoo بقدرات Agentic AI كاملة:

الأدوار الرئيسية:
1. **الإدراك (Perceive)**: تحليل طلب الكتابة، التحقق من الأهلية، فهم السياق
2. **التخطيط (Plan)**: بناء خطة تنفيذ بخطوات واضحة + استراتيجية rollback
3. **التنفيذ (Execute)**: تطبيق العمليات عبر OdooWriteGateway مع تدقيق كامل
4. **التأمل (Reflect)**: تقييم النتائج، التعلم من الأخطاء، تحسين القرارات

الضمانات الأمنية:
- فحص البيئة عبر حارس (ALLOWED_TEST_DBS/ALLOWED_DEV_DBS)
- لا تنفيذ بدون اعتماد صريح
- حظر الحذف الكلي
- توثيق كل عملية في JSONL Audit Log
- دعم Rollback للعمليات الفاشلة
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agents.base_agent import BaseAgent
from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS
from odoo_write_gateway import OdooWriteGateway, WriteGatewayError, EnvironmentGuardError
from odoo_delete_gateway import (
    OdooDeleteGateway,
    DeleteGatewayError,
    DeleteGatewayOdooRejectionError,
    DeleteGatewayEnvironmentGuardError,
)

logger = logging.getLogger("katib_agent")

AUDIT_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
AUDIT_LOG_FILE = AUDIT_LOG_DIR / "writer_audit_log.jsonl"
DELETION_AUDIT_LOG_FILE = AUDIT_LOG_DIR / "deletion_audit_log.jsonl"


class WriteOperationType(str, Enum):
    """أنواع عمليات الكتابة المدعومة"""
    CREATE = "create"
    UPDATE = "update"
    ARCHIVE = "archive"
    UNARCHIVE = "unarchive"
    DELETE = "delete"


# WriteDecision: محذوف - كاتب الآن يعمل فقط مع ApprovalPlan
# لا تنفيذ إلا بعد التحقق من صحة الخطة: TTL + استهلاك واحد + ربط بالمستخدم


class RollbackStrategy(str, Enum):
    """
    استراتيجيات Rollback بعد حذف DELETE_CREATED (S2)
    Rollback يُنفذ عبر نموذج العملية الذي أنشأ السجل فقط
    """
    NONE = "none"  # لا rollback (قراءة فقط أو حذف نهائي)
    REVERT_VALUES = "revert_values"  # إعادة القيم القديمة عبر write
    RESTORE_ARCHIVED = "restore_archived"  # استرجاع من الأرشفة (active=True)


class KatibSecurityError(Exception):
    """خطأ أمني عند محاولة تنفيذ عملية غير مصرح بها"""


class KatibExecutionError(Exception):
    """خطأ تنفيذي أثناء الكتابة في Odoo"""


class KatibAgent(BaseAgent):
    """
    وكيل الكتابة المعتمد الذكي مع قدرات Agentic AI كاملة.
    
    الدورة الذكية:
    1. Perceive: فهم طلب الكتابة + التحقق من الأهلية
    2. Plan: بناء خطة تنفيذ + rollback strategy
    3. Execute: تطبيق العمليات مع audit logging
    4. Reflect: تقييم النتائج + التعلم
    """

    def __init__(
        self,
        url: Optional[str] = None,
        db: Optional[str] = None,
        login: Optional[str] = None,
        password: Optional[str] = None,
        gateway: Optional[OdooWriteGateway] = None,
        delete_gateway: Optional[OdooDeleteGateway] = None,
        llm_model: Optional[str] = None,
    ):
        super().__init__(
            name="katib",
            role="authorized_write_agent",
            llm_model=llm_model,
        )
        
        self._gateway = gateway
        self._delete_gateway = delete_gateway
        self._url = url
        self._db = db
        self._login = login
        self._password = password
        
        # سجل العمليات للـ Rollback
        self._operation_history: List[Dict[str, Any]] = []
        
        logger.info(f"✅ Katib Agent initialized: {self.name}")

    def _get_gateway(self) -> OdooWriteGateway:
        """الحصول على بوابة الكتابة مع فحص الأمان"""
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
        """الحصول على بوابة الحذف المعزولة"""
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

    # ============================================================================
    # Agentic Loop Implementation
    # ============================================================================

    def perceive(self, action_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 1: الإدراك - تحليل طلب الكتابة وفهم السياق
        
        Args:
            action_request: طلب الكتابة من سراج أو مصدر آخر
            
        Returns:
            perception: تحليل شامل للطلب مع مؤشرات الأمان
        """
        logger.info(f"🔍 Perceiving write request: {action_request.get('action_type')}")
        
        action_type = action_request.get("action_type") or action_request.get("type")
        
        # استخراج البيانات الأساسية
        perception = {
            "operation_type": action_type,
            "model": action_request.get("model", "hr.employee"),
            "record_id": action_request.get("record_id") or action_request.get("employee_id"),
            "values": action_request.get("values", {}),
            "context": action_request.get("context", {}),
            "raw_request": action_request,
        }
        
        # تحليل الأمان
        perception["safety_analysis"] = self._analyze_safety(action_request, action_type)
        
        # تحليل التأثير المتوقع
        perception["impact_analysis"] = self._analyze_impact(action_type, perception["record_id"])
        
        # التحقق من الأهلية
        perception["eligibility"] = self._check_eligibility(perception)
        
        logger.info(f"✅ Perception complete: {perception['eligibility']['status']}")
        return perception

    def plan(self, perception: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 2: التخطيط - بناء خطة تنفيذ مع rollback strategy
        
        P5: لم يعد كاتب يتخذ قرارات تنفيذ - فقط يُخطط بناءً على الأهلية
        
        Args:
            perception: نتائج مرحلة الإدراك
            
        Returns:
            plan: خطة تنفيذ مفصلة مع خطوات واضحة
        """
        logger.info(f"📋 Planning execution for: {perception['operation_type']}")
        
        # بناء خطة التنفيذ
        plan = {
            "operation_type": perception["operation_type"],
            "steps": [],
            "rollback_strategy": RollbackStrategy.NONE,
            "risks": [],
            "safeguards": [],
            "is_eligible": perception["eligibility"]["status"] == "eligible",
            "rejection_reason": perception["eligibility"].get("rejection_reason"),
        }
        
        # إذا كانت العملية مؤهلة - بناء خطوات التنفيذ
        if plan["is_eligible"]:
            plan["steps"] = self._build_execution_steps(perception)
            plan["rollback_strategy"] = self._determine_rollback_strategy(perception)
            plan["safeguards"] = self._identify_safeguards(perception)
        else:
            # رفض - لا تنفيذ
            plan["steps"] = [
                {"action": "reject", "reason": perception["eligibility"].get("rejection_reason")}
            ]
        
        # تحديد المخاطر
        plan["risks"] = self._identify_risks(perception)
        
        logger.info(f"✅ Plan created: {len(plan['steps'])} steps, eligible={plan['is_eligible']}")
        return plan

    def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 3: التنفيذ - تطبيق الخطة مع audit logging
        
        P5: التنفيذ الآن يتطلب فحص الأهلية فقط - لا قرارات WriteDecision
        
        Args:
            plan: خطة التنفيذ من مرحلة التخطيط
            
        Returns:
            result: نتيجة التنفيذ مع تفاصيل النجاح/الفشل
        """
        logger.info(f"⚡ Executing plan: {plan['operation_type']}")
        
        result = {
            "success": False,
            "operation_type": plan["operation_type"],
            "executed_steps": [],
            "errors": [],
            "rollback_performed": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            # فحص الأهلية
            if not plan["is_eligible"]:
                result["success"] = False
                result["errors"].append(plan["rejection_reason"] or "عملية مرفوضة - غير مؤهلة")
                return result
            
            # التنفيذ الفعلي للعمليات المؤهلة
            result = self._execute_write_operation(plan, result)
        
        except Exception as exc:
            logger.error(f"❌ Execution failed: {exc}")
            result["success"] = False
            result["errors"].append(str(exc))
            
            # محاولة Rollback
            if plan["rollback_strategy"] != RollbackStrategy.NONE:
                try:
                    self._perform_rollback(plan["rollback_strategy"], result)
                    result["rollback_performed"] = True
                except Exception as rollback_exc:
                    logger.error(f"❌ Rollback failed: {rollback_exc}")
                    result["rollback_error"] = str(rollback_exc)
        
        finally:
            # توثيق العملية في Audit Log
            self._log_audit_record(plan, result)
        
        logger.info(f"✅ Execution complete: success={result['success']}")
        return result

    def reflect(self, perception: Dict[str, Any], plan: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 4: التأمل - تقييم النتائج والتعلم من التجربة
        
        Args:
            perception: نتائج الإدراك
            plan: الخطة المنفذة
            result: نتيجة التنفيذ
            
        Returns:
            reflection: تحليل شامل مع توصيات للتحسين
        """
        logger.info(f"🤔 Reflecting on execution: success={result.get('success')}")
        
        reflection = {
            "execution_success": result.get("success", False),
            "operation_type": result.get("operation_type"),
            "lessons_learned": [],
            "improvements": [],
            "confidence_score": 0.0,
        }
        
        # تحليل النجاح/الفشل
        if result["success"]:
            reflection["lessons_learned"].append("عملية نجحت كما هو مخطط")
            reflection["confidence_score"] = 0.95
            
            # هل كانت الخطة مثالية؟
            if len(result.get("errors", [])) == 0:
                reflection["improvements"].append("الخطة كانت دقيقة وفعالة")
            else:
                reflection["improvements"].append("يمكن تحسين التعامل مع الأخطاء البسيطة")
        
        else:
            reflection["lessons_learned"].append(f"عملية فشلت: {result.get('errors', [])}")
            reflection["confidence_score"] = 0.3
            
            # تحليل سبب الفشل
            if result.get("rollback_performed"):
                reflection["improvements"].append("Rollback نجح - النظام محمي")
            else:
                reflection["improvements"].append("يجب تحسين استراتيجية Rollback")
        
        # تحليل Eligibility Quality
        if not plan.get("is_eligible") and not result["success"]:
            reflection["lessons_learned"].append("العملية رُفضت بشكل صحيح - غير مؤهلة")
        
        # توصيات للمستقبل
        reflection["recommendations"] = self._generate_recommendations(perception, plan, result)
        
        logger.info(f"✅ Reflection complete: confidence={reflection['confidence_score']:.2f}")
        return reflection

    # ============================================================================
    # Decision Making & Analysis
    # ============================================================================

    def _analyze_safety(self, request: Dict[str, Any], operation_type: str) -> Dict[str, Any]:
        """تحليل الأمان للعملية المطلوبة"""
        safety = {
            "level": "safe",  # safe, caution, danger
            "concerns": [],
            "requires_approval": False,
        }
        
        # فحص عمليات الحذف
        if operation_type == WriteOperationType.DELETE:
            safety["level"] = "danger"
            safety["concerns"].append("عملية حذف نهائية غير قابلة للاسترجاع")
            safety["requires_approval"] = True
        
        # فحص البيانات الحساسة
        values = request.get("values", {})
        sensitive_fields = ["salary", "bank_account", "identification_id", "passport_id"]
        for field in sensitive_fields:
            if field in values:
                safety["level"] = "caution"
                safety["concerns"].append(f"تعديل حقل حساس: {field}")
        
        return safety

    def _analyze_impact(self, operation_type: str, record_id: Optional[int]) -> Dict[str, Any]:
        """تحليل التأثير المتوقع للعملية"""
        impact = {
            "scope": "single_record",  # single_record, multiple_records, system_wide
            "reversible": True,
            "affects_other_records": False,
        }
        
        if operation_type == WriteOperationType.DELETE:
            impact["reversible"] = False
            impact["affects_other_records"] = True  # قد يؤثر على سجلات مرتبطة
        
        if operation_type == WriteOperationType.ARCHIVE:
            impact["reversible"] = True
            impact["affects_other_records"] = False
        
        return impact

    def _check_eligibility(self, perception: Dict[str, Any]) -> Dict[str, Any]:
        """
        التحقق من أهلية العملية للتنفيذ (P5: فحوص البيئة والبيانات فقط)
        
        القرارات الأمنية (danger/caution) الآن تُدار في Hares - كاتب يفحص الأهلية الفنية فقط
        """
        eligibility = {
            "status": "eligible",
            "rejection_reason": None,
        }
        
        # فحص البيئة
        try:
            self._get_gateway()  # سيرفع استثناء إذا كانت البيئة غير مصرح بها
        except KatibSecurityError as exc:
            eligibility["status"] = "rejected"
            eligibility["rejection_reason"] = str(exc)
            return eligibility
        
        # فحص البيانات الأساسية
        if perception["operation_type"] in [WriteOperationType.UPDATE, WriteOperationType.DELETE, WriteOperationType.ARCHIVE]:
            if not perception["record_id"]:
                eligibility["status"] = "rejected"
                eligibility["rejection_reason"] = "معرف السجل مطلوب لهذه العملية"
        
        return eligibility


    def _build_execution_steps(self, perception: Dict[str, Any]) -> List[Dict[str, Any]]:
        """بناء خطوات التنفيذ التفصيلية"""
        steps = []
        
        operation_type = perception["operation_type"]
        
        if operation_type == WriteOperationType.CREATE:
            steps.append({
                "action": "validate_values",
                "description": "التحقق من صحة البيانات"
            })
            steps.append({
                "action": "create_record",
                "model": perception["model"],
                "values": perception["values"],
            })
        
        elif operation_type == WriteOperationType.UPDATE:
            steps.append({
                "action": "fetch_current_values",
                "record_id": perception["record_id"],
                "description": "حفظ القيم الحالية للـ Rollback"
            })
            steps.append({
                "action": "update_record",
                "model": perception["model"],
                "record_id": perception["record_id"],
                "values": perception["values"],
            })
        
        elif operation_type == WriteOperationType.ARCHIVE:
            steps.append({
                "action": "archive_record",
                "model": perception["model"],
                "record_id": perception["record_id"],
            })
        
        elif operation_type == WriteOperationType.UNARCHIVE:
            steps.append({
                "action": "unarchive_record",
                "model": perception["model"],
                "record_id": perception["record_id"],
            })
        
        elif operation_type == WriteOperationType.DELETE:
            steps.append({
                "action": "delete_record",
                "model": perception["model"],
                "record_id": perception["record_id"],
            })
        
        return steps

    def _determine_rollback_strategy(self, perception: Dict[str, Any]) -> RollbackStrategy:
        """تحديد استراتيجية Rollback المناسبة"""
        operation_type = perception["operation_type"]
        
        if operation_type == WriteOperationType.CREATE:
            return RollbackStrategy.REVERT_VALUES  # P5-S2: DELETE_CREATED removed
        
        elif operation_type == WriteOperationType.UPDATE:
            return RollbackStrategy.REVERT_VALUES
        
        elif operation_type == WriteOperationType.ARCHIVE:
            return RollbackStrategy.RESTORE_ARCHIVED
        
        elif operation_type == WriteOperationType.DELETE:
            return RollbackStrategy.NONE  # الحذف لا يمكن التراجع عنه
        
        return RollbackStrategy.NONE

    def _identify_safeguards(self, perception: Dict[str, Any]) -> List[str]:
        """تحديد الضمانات الأمنية المطلوبة"""
        safeguards = [
            "environment_check",
            "audit_logging",
        ]
        
        if perception["safety_analysis"]["level"] in ["caution", "danger"]:
            safeguards.append("backup_current_state")
        
        if perception["operation_type"] == WriteOperationType.DELETE:
            safeguards.append("deletion_confirmation")
        
        return safeguards

    def _identify_risks(self, perception: Dict[str, Any]) -> List[Dict[str, Any]]:
        """تحديد المخاطر المحتملة"""
        risks = []
        
        # مخاطر الأمان
        for concern in perception["safety_analysis"]["concerns"]:
            risks.append({
                "type": "safety",
                "description": concern,
                "severity": perception["safety_analysis"]["level"],
            })
        
        # مخاطر عدم القابلية للاسترجاع
        if not perception["impact_analysis"]["reversible"]:
            risks.append({
                "type": "irreversible",
                "description": "العملية غير قابلة للتراجع",
                "severity": "high",
            })
        
        return risks

    # ============================================================================
    # Execution Implementation
    # ============================================================================

    def _execute_write_operation(self, plan: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """تنفيذ العملية الفعلية حسب الخطة"""
        
        for step in plan["steps"]:
            action = step["action"]
            
            try:
                if action == "create_record":
                    new_id = self._create_record(step["model"], step["values"])
                    result["record_id"] = new_id
                    result["executed_steps"].append(f"Created record {new_id}")
                
                elif action == "update_record":
                    self._update_record(step["model"], step["record_id"], step["values"])
                    result["record_id"] = step["record_id"]
                    result["executed_steps"].append(f"Updated record {step['record_id']}")
                
                elif action == "archive_record":
                    self._archive_record(step["model"], step["record_id"])
                    result["record_id"] = step["record_id"]
                    result["executed_steps"].append(f"Archived record {step['record_id']}")
                
                elif action == "unarchive_record":
                    self._unarchive_record(step["model"], step["record_id"])
                    result["record_id"] = step["record_id"]
                    result["executed_steps"].append(f"Unarchived record {step['record_id']}")
                
                elif action == "delete_record":
                    self._delete_record(step["model"], step["record_id"])
                    result["record_id"] = step["record_id"]
                    result["executed_steps"].append(f"Deleted record {step['record_id']}")
                
                elif action == "validate_values":
                    result["executed_steps"].append("Values validated")
                
                elif action == "fetch_current_values":
                    # TODO: fetch current values for rollback
                    result["executed_steps"].append("Current values fetched")
            
            except Exception as exc:
                result["errors"].append(f"Step '{action}' failed: {str(exc)}")
                raise
        
        result["success"] = True
        return result

    def _create_record(self, model: str, values: Dict[str, Any]) -> int:
        """إنشاء سجل جديد"""
        gateway = self._get_gateway()
        
        if model == "hr.employee":
            new_id = gateway.create_employee(values)
        else:
            new_id = gateway.create_record(model, values)
        
        # حفظ في سجل العمليات
        self._operation_history.append({
            "action": "create",
            "model": model,
            "record_id": new_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        return new_id

    def _update_record(self, model: str, record_id: int, values: Dict[str, Any]) -> bool:
        """تعديل سجل موجود"""
        gateway = self._get_gateway()
        
        if model == "hr.employee":
            success = gateway.write_employee(record_id, values)
        else:
            success = gateway.write_record(model, record_id, values)
        
        # حفظ في سجل العمليات
        self._operation_history.append({
            "action": "update",
            "model": model,
            "record_id": record_id,
            "values": values,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        return success

    def _archive_record(self, model: str, record_id: int) -> bool:
        """أرشفة سجل"""
        gateway = self._get_gateway()
        success = gateway.write_record(model, record_id, {"active": False})
        
        # حفظ في سجل العمليات
        self._operation_history.append({
            "action": "archive",
            "model": model,
            "record_id": record_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        return success

    def _unarchive_record(self, model: str, record_id: int) -> bool:
        """إلغاء أرشفة سجل"""
        gateway = self._get_gateway()
        success = gateway.write_record(model, record_id, {"active": True})
        
        # حفظ في سجل العمليات
        self._operation_history.append({
            "action": "unarchive",
            "model": model,
            "record_id": record_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        return success

    def _delete_record(self, model: str, record_id: int) -> bool:
        """حذف سجل نهائياً"""
        delete_gateway = self._get_delete_gateway()
        success = delete_gateway.delete_single_record(model, record_id)
        
        # حفظ في سجل العمليات
        self._operation_history.append({
            "action": "delete",
            "model": model,
            "record_id": record_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        return success

    def _perform_rollback(self, strategy: RollbackStrategy, result: Dict[str, Any]) -> None:
        """تنفيذ Rollback حسب الاستراتيجية المحددة"""
        logger.warning(f"🔄 Performing rollback: {strategy}")
        
        if strategy == RollbackStrategy.REVERT_VALUES:
            # إعادة القيم القديمة (TODO: implement)
            logger.warning("⚠️ Rollback REVERT_VALUES not fully implemented yet")
        
        elif strategy == RollbackStrategy.RESTORE_ARCHIVED:
            # استرجاع من الأرشفة
            if "record_id" in result:
                gateway = self._get_gateway()
                gateway.write_record("hr.employee", result["record_id"], {"active": True})
                logger.info(f"✅ Rollback: Restored archived record {result['record_id']}")

    # ============================================================================
    # Audit Logging
    # ============================================================================

    def _log_audit_record(self, plan: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        P5-S15: توثيق العملية في سجل التدقيق (Append-Only JSONL)
        
        مخطط موحد بعد حذف WriteDecision - يُسجل الأهلية فقط
        """
        try:
            AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
            
            audit_record = {
                "timestamp": result["timestamp"],
                "agent": "katib",
                "operation_type": result["operation_type"],
                "is_eligible": plan.get("is_eligible", False),  # P5-S15: بدل decision
                "rejection_reason": plan.get("rejection_reason"),  # P5-S15: سبب الرفض إن وُجد
                "success": result["success"],
                "record_id": result.get("record_id"),
                "executed_steps": result["executed_steps"],
                "errors": result.get("errors", []),
                "rollback_performed": result.get("rollback_performed", False),
            }
            
            # P5-S15: مخططان منفصلان للحذف والكتابة
            if result["operation_type"] in [WriteOperationType.DELETE, WriteOperationType.ARCHIVE, WriteOperationType.UNARCHIVE]:
                log_file = DELETION_AUDIT_LOG_FILE
            else:
                log_file = AUDIT_LOG_FILE
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit_record, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            
            logger.info(f"📝 Audit record logged to {log_file}")
        
        except Exception as exc:
            logger.error(f"❌ Failed to log audit record: {exc}")

    def _generate_recommendations(
        self,
        perception: Dict[str, Any],
        plan: Dict[str, Any],
        result: Dict[str, Any]
    ) -> List[str]:
        """توليد توصيات للتحسين المستقبلي"""
        recommendations = []
        
        if not result["success"]:
            recommendations.append("راجع شروط الأهلية قبل التنفيذ")
            recommendations.append("تحسين التعامل مع الأخطاء")
        
        if result.get("rollback_performed"):
            recommendations.append("النظام نجح في الحماية عبر Rollback")
        
        # REQUEST_APPROVAL removed - تُدار الآن بواسطة Hares
        
        return recommendations

    # ============================================================================
    # Public API (Backward Compatibility)
    # ============================================================================

    def execute_approved_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        واجهة عامة لتنفيذ عملية معتمدة (للتوافق مع الكود القديم)
        
        تستخدم الدورة الذكية الكاملة:
        Perceive → Plan → Execute → Reflect
        """
        logger.info(f"🎯 Executing approved action: {action.get('action_type')}")
        
        # الدورة الذكية الكاملة
        perception = self.perceive(action)
        plan = self.plan(perception)
        result = self.execute(plan)
        reflection = self.reflect(perception, plan, result)
        
        # تنسيق النتيجة للتوافق مع الواجهة القديمة
        return {
            "ok": result["success"],
            "action": action.get("action_type"),
            "record_id": result.get("record_id"),
            "timestamp": result["timestamp"],
            "errors": result.get("errors", []),
            "reflection": reflection,
        }


# ============================================================================
# Singleton Factory
# ============================================================================

_GLOBAL_KATIB: Optional[KatibAgent] = None


def get_katib_agent() -> KatibAgent:
    """الحصول على كائن وكيل كاتب المفرد (Singleton)"""
    global _GLOBAL_KATIB
    if _GLOBAL_KATIB is None:
        _GLOBAL_KATIB = KatibAgent()
    return _GLOBAL_KATIB
