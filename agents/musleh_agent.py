"""
MuslehAgent - وكيل التشخيص والإصلاح الذاتي
==========================================
«مُصلِّح» - Diagnostic & Self-Healing Agent

الدور:
- تشخيص المشاكل في البيانات المُرفوضة (needs_review, rejected)
- اقتراح حلول ذكية (fuzzy matching, auto-correction)
- إصلاح تلقائي للمشاكل البسيطة (90%+ ثقة)
- رفع القرارات المعقدة لـ Seraj

المدخلات:
- صفوف مُرفوضة من Validator
- Live snapshot من Odoo

المخرجات:
- APPLY_AUTO_PATCH: إصلاح تلقائي
- QUARANTINE_AND_PROCEED: عزل الصف
- PROPOSE_MISSING_ENTITY: اقتراح إنشاء كيان جديد
- ESCALATE_TO_HUMAN: رفع لـ Seraj

القيود:
- لا يُعدّل الهويات الوطنية (خط أحمر)
- لا يُعدّل البيانات الشخصية بدون ثقة 90%+
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import (
    BaseAgent,
    AgentGoal,
    AgentMemory,
    AgentPlan,
    AgentReflection,
)

logger = logging.getLogger("musleh_agent")


# ═══════════════════════════════════════════════════════════════
# Decision Types
# ═══════════════════════════════════════════════════════════════

DECISION_APPLY_AUTO_PATCH = "APPLY_AUTO_PATCH"
DECISION_QUARANTINE = "QUARANTINE_AND_PROCEED"
DECISION_PROPOSE_ENTITY = "PROPOSE_MISSING_ENTITY"
DECISION_ESCALATE = "ESCALATE_TO_HUMAN"

CONFIDENCE_THRESHOLD = 0.90  # عتبة الإصلاح التلقائي


class MuslehAgent(BaseAgent):
    """
    وكيل التشخيص والإصلاح - مُصلِّح
    
    يُشخّص المشاكل ويقترح الحلول
    """
    
    def __init__(
        self,
        repository=None,
        auto_repair: bool = False,
    ):
        super().__init__(
            name="Musleh",
            role="Diagnostic & Self-Healing Agent",
        )
        self.repository = repository
        self.auto_repair = auto_repair
    
    # ═══════════════════════════════════════════════════════════════
    # Agentic Loop Implementation
    # ═══════════════════════════════════════════════════════════════
    
    def perceive(
        self,
        goal: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        فهم المشكلة والسياق
        
        يُحلل:
        - نوع المشكلة (failure_code)
        - البيانات المتوفرة
        - المراجع الحية من Odoo
        """
        if isinstance(goal, dict) and context is None:
            context = goal
            goal = AgentGoal(objective="Diagnose and heal", constraints=["No identity modification"])

        context = context or {}
        op_id = context.get("operation_id")
        if not op_id and hasattr(goal, "objective") and isinstance(goal.objective, dict):
            op_id = goal.objective.get("operation_id")

        if op_id:
            try:
                from agents.agent_events_service import emit_agent_event
                emit_agent_event(
                    op_id,
                    "Musleh (Healing)",
                    "perceive",
                    reasoning="Analyzing rejected data, failure reasons, and error types...",
                    status="in_progress"
                )
            except Exception:
                pass

        row = context.get("row", {})
        validation_result = context.get("validation_result", {})
        live_snapshot = context.get("live_snapshot", {})
        
        failure_code = validation_result.get("failure_code", "")
        reasons = validation_result.get("reasons", [])
        fields = row.get("fields", {})
        
        # استخراج القيم
        company = fields.get("company", {}).get("value", "")
        department = fields.get("department", {}).get("value", "")
        job = fields.get("job", {}).get("value", "")
        name = fields.get("name", {}).get("value", "")
        email = fields.get("work_email", {}).get("value", "")
        
        perception = {
            "failure_code": failure_code,
            "reasons": reasons,
            "fields": {
                "name": name,
                "company": company,
                "department": department,
                "job": job,
                "email": email,
            },
            "live_snapshot": live_snapshot,
            "is_identity_issue": self._is_identity_issue(failure_code),  # ✅ استخدام الدالة الجديدة
            "severity": self._assess_severity(failure_code),
            "operation_id": op_id,
        }
        
        self._log_trace("PERCEIVE", perception)
        logger.info(
            f"Perceived issue: {failure_code} for employee '{name}', "
            f"severity={perception['severity']}"
        )

        if op_id:
            try:
                from agents.agent_events_service import emit_agent_event
                emit_agent_event(
                    op_id,
                    "Musleh (Healing)",
                    "perceive",
                    decision=f"Issue: {failure_code or 'validation_error'}, severity={perception['severity']}",
                    status="success"
                )
            except Exception:
                pass
        
        return perception
    
    def plan(
        self,
        goal: Any,
        perception: Dict[str, Any]
    ) -> AgentPlan:
        """
        وضع خطة التشخيص والإصلاح
        
        الخطوات:
        1. Assess - تقييم المشكلة
        2. Consult - استشارة المراجع
        3. Propose - اقتراح الحل
        4. Decide - اتخاذ القرار
        """
        if isinstance(goal, dict):
            goal = AgentGoal(objective=str(goal.get("action", "Diagnose and heal")))

        obj_str = str(getattr(goal, "objective", "musleh"))
        plan = AgentPlan(plan_id=f"musleh-{obj_str[:20]}")

        op_id = perception.get("operation_id")
        if op_id:
            try:
                from agents.agent_events_service import emit_agent_event
                emit_agent_event(
                    op_id,
                    "Musleh (Healing)",
                    "plan",
                    decision="plan_diagnosis",
                    reasoning="Planning diagnostic, reference consultation, and resolution steps",
                    status="in_progress"
                )
            except Exception:
                pass
        
        failure_code = perception["failure_code"]
        is_identity = perception["is_identity_issue"]
        severity = perception["severity"]
        
        # خط أحمر: لا تعديل للهويات
        if is_identity:
            plan.add_step({
                "action": "escalate_identity_issue",
                "description": "هوية مكررة - يُرفع للمسؤول البشري",
                "rationale": "RED LINE: لا تعديل تلقائي للهويات",
                "operation_id": op_id,
            })
            plan.status = "requires_escalation"  # ✅ علامة خاصة

            if op_id:
                try:
                    from agents.agent_events_service import emit_agent_event
                    emit_agent_event(
                        op_id,
                        "Musleh (Healing)",
                        "plan",
                        decision="escalate_identity_red_line",
                        status="success"
                    )
                except Exception:
                    pass

            return plan
        
        # خطة التشخيص العادية
        plan.add_step({
            "action": "assess_issue",
            "description": "تقييم المشكلة والبيانات المتوفرة",
            "operation_id": op_id,
        })
        
        plan.add_step({
            "action": "consult_references",
            "description": "استشارة Fahas للمراجع الحية",
            "operation_id": op_id,
        })
        
        plan.add_step({
            "action": "propose_solutions",
            "description": "اقتراح الحلول الممكنة",
            "operation_id": op_id,
        })
        
        plan.add_step({
            "action": "make_decision",
            "description": "اتخاذ القرار النهائي",
            "rationale": f"auto_repair={self.auto_repair}, severity={severity}",
            "operation_id": op_id,
        })
        
        self._log_trace("PLAN", {"plan_id": plan.plan_id, "steps": len(plan.steps)})
        logger.info(f"Planned {len(plan.steps)} steps for diagnosis")

        if op_id:
            try:
                from agents.agent_events_service import emit_agent_event
                emit_agent_event(
                    op_id,
                    "Musleh (Healing)",
                    "plan",
                    decision=f"Planned {len(plan.steps)} steps for diagnosis",
                    status="success"
                )
            except Exception:
                pass
        
        return plan
    
    def execute(self, plan: AgentPlan) -> Dict[str, Any]:
        """
        تنفيذ خطة التشخيص
        """
        op_id = None
        for step in plan.steps:
            if step.get("operation_id"):
                op_id = step["operation_id"]
                break

        if op_id:
            try:
                from agents.agent_events_service import emit_agent_event
                emit_agent_event(
                    op_id,
                    "Musleh (Healing)",
                    "execute",
                    reasoning="Executing diagnosis and self-healing...",
                    status="in_progress"
                )
            except Exception:
                pass

        result = {
            "decision": None,
            "confidence": 0.0,
            "patches": {},
            "escalation": None,
        }
        
        for i, step in enumerate(plan.steps):
            action = step["action"]
            logger.info(f"Executing step {i+1}/{len(plan.steps)}: {action}")
            
            if action == "escalate_identity_issue":
                # هوية مكررة - رفع فوراً
                result["decision"] = DECISION_ESCALATE
                result["escalation"] = {
                    "reason": "هوية مكررة - يتطلب مراجعة بشرية",
                    "red_line": True,
                }
                plan.mark_step_complete(i)
                break
            
            elif action == "assess_issue":
                # تقييم المشكلة
                assessment = self._assess_issue()
                result["assessment"] = assessment
                plan.mark_step_complete(i)
            
            elif action == "consult_references":
                # استشارة المراجع
                consultation = self._consult_references()
                result["consultation"] = consultation
                plan.mark_step_complete(i)
            
            elif action == "propose_solutions":
                # اقتراح الحلول
                solutions = self._propose_solutions(result)
                result["solutions"] = solutions
                plan.mark_step_complete(i)
            
            elif action == "make_decision":
                # اتخاذ القرار
                decision = self._make_decision(result)
                result.update(decision)
                plan.mark_step_complete(i)
        
        self._log_trace("EXECUTE", {
            "decision": result.get("decision"),
            "confidence": result.get("confidence"),
        })

        if op_id:
            try:
                from agents.agent_events_service import emit_agent_event
                emit_agent_event(
                    op_id,
                    "Musleh (Healing)",
                    "execute",
                    decision=f"Decision: {result.get('decision')}, Confidence: {result.get('confidence', 0.0):.2f}",
                    status="success" if result.get("decision") else "failed"
                )
            except Exception:
                pass
        
        return result
    
    def reflect(
        self,
        goal: AgentGoal,
        plan: AgentPlan,
        result: Dict[str, Any]
    ) -> AgentReflection:
        """
        مراجعة النتائج
        """
        decision = result.get("decision")
        confidence = result.get("confidence", 0.0)
        
        # تقييم النجاح
        success = decision is not None
        
        issues = []
        improvements = []
        
        # فحص القرار
        if decision == DECISION_APPLY_AUTO_PATCH:
            if confidence < CONFIDENCE_THRESHOLD:
                issues.append(f"Confidence {confidence} < {CONFIDENCE_THRESHOLD}")
        
        # اقتراحات التحسين
        if not success:
            improvements.append("Review failure_code classification")
        
        if confidence < 0.8:
            improvements.append("Consider more fuzzy matching sources")
        
        should_retry = (not success) and len(issues) > 0
        
        reflection = AgentReflection(
            success=success,
            confidence=confidence,
            issues=issues,
            improvements=improvements,
            should_retry=should_retry,
            retry_strategy="adjust_threshold" if should_retry else None,
        )
        
        self._log_trace("REFLECT", {
            "success": success,
            "confidence": confidence,
            "should_retry": should_retry,
        })
        
        logger.info(
            f"Reflection: success={success}, confidence={confidence:.2f}, "
            f"should_retry={should_retry}"
        )
        
        return reflection
    
    # ═══════════════════════════════════════════════════════════════
    # Helper Methods
    # ═══════════════════════════════════════════════════════════════
    
    def _assess_severity(self, failure_code: str) -> str:
        """تقييم خطورة المشكلة"""
        if "duplicate" in failure_code.lower():
            return "CRITICAL"  # هوية مكررة
        elif "reference_not_found" in failure_code:
            return "HIGH"  # مرجع مفقود
        elif "invalid" in failure_code:
            return "MEDIUM"  # بيانات غير صحيحة
        else:
            return "LOW"
    
    def _is_identity_issue(self, failure_code: str) -> bool:
        """تحديد إذا كانت مشكلة هوية (خط أحمر)"""
        identity_codes = [
            "duplicate_existing_employee",
            "duplicate_in_file",
            "duplicate_",
        ]
        return any(code in failure_code.lower() for code in identity_codes)
    
    def _assess_issue(self) -> Dict[str, Any]:
        """تقييم المشكلة"""
        # TODO: تحليل تفصيلي
        return {
            "can_auto_fix": self.auto_repair,
            "requires_human": False,
        }
    
    def _consult_references(self) -> Dict[str, Any]:
        """استشارة المراجع الحية"""
        # TODO: استدعاء Fahas للحصول على المراجع
        return {
            "company_exists": True,
            "department_exists": False,
            "job_exists": True,
        }
    
    def _propose_solutions(self, current_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """اقتراح الحلول"""
        solutions = []
        
        consultation = current_result.get("consultation", {})
        
        # مثال: إذا القسم غير موجود
        if not consultation.get("department_exists"):
            solutions.append({
                "type": "fuzzy_match",
                "field": "department",
                "suggestion": "IT Department",  # TODO: fuzzy matching حقيقي
                "confidence": 0.85,
            })
            
            solutions.append({
                "type": "create_entity",
                "field": "department",
                "value": "New Department",
                "confidence": 0.95,
            })
        
        return solutions
    
    def _make_decision(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """اتخاذ القرار النهائي"""
        solutions = result.get("solutions", [])
        
        if not solutions:
            # لا حلول - عزل أو رفع
            return {
                "decision": DECISION_QUARANTINE,
                "confidence": 1.0,
                "rationale": "No viable solutions found",
            }
        
        # اختيار أفضل حل
        best = max(solutions, key=lambda s: s.get("confidence", 0))
        confidence = best.get("confidence", 0.0)
        
        if self.auto_repair and confidence >= CONFIDENCE_THRESHOLD:
            # إصلاح تلقائي
            suggestion = best.get("suggestion") or best.get("value")  # ✅ Fix
            return {
                "decision": DECISION_APPLY_AUTO_PATCH,
                "confidence": confidence,
                "patches": {best["field"]: suggestion},
                "rationale": f"Auto-repair with {confidence:.0%} confidence",
            }
        elif best["type"] == "create_entity":
            # اقتراح إنشاء كيان
            return {
                "decision": DECISION_PROPOSE_ENTITY,
                "confidence": confidence,
                "entity": best,
                "rationale": "Missing entity needs creation",
            }
        else:
            # رفع للمسؤول البشري
            return {
                "decision": DECISION_ESCALATE,
                "confidence": confidence,
                "suggestions": solutions,
                "rationale": "Requires human decision",
            }


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def create_musleh_diagnostic_goal(
    description: str,
    row: Dict[str, Any],
    validation_result: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> AgentGoal:
    """إنشاء هدف لـ Musleh"""
    ctx = context or {}
    ctx.update({
        "row": row,
        "validation_result": validation_result,
    })
    
    return AgentGoal(
        objective=description,
        constraints=[
            "لا تعديل للهويات الوطنية",
            "ثقة 90%+ للإصلاح التلقائي",
            "رفع القرارات المعقدة لـ Seraj",
        ],
        success_criteria=[
            "تحديد المشكلة بدقة",
            "اقتراح حل واضح",
            "confidence > 0.8",
        ],
        max_iterations=5,
        timeout_seconds=60,
    )
