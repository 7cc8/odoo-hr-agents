"""
HaresAgent - وكيل الأمان والحماية
==================================
«حَارِس» - Security & Policy Enforcement Agent

الدور:
- تقييم المخاطر الأمنية (low/medium/high/critical)
- تطبيق السياسات (environment policies, data policies)
- Four-Eyes Principle للعمليات الحساسة
- Deletion Guard للبيانات الهامة
- Approval workflow للعمليات الخطرة

المدخلات:
- نوع العملية (read/write/delete)
- البيانات المطلوبة
- البيئة المستهدفة (prod/test/dev)
- المستخدم/الوكيل الطالب

المخرجات:
- ALLOW: السماح بالعملية
- DENY: رفض العملية
- REQUIRE_APPROVAL: تتطلب موافقة
- ESCALATE: رفع لمستوى أعلى

القيود:
- لا كتابة على Production بدون موافقة
- لا حذف للبيانات الشخصية بدون Four-Eyes
- كل القرارات مُسجّلة (audit trail)
"""
from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Any, Dict, List, Optional

from agents.base_agent import (
    BaseAgent,
    AgentGoal,
    AgentMemory,
    AgentPlan,
    AgentReflection,
)

logger = logging.getLogger("hares_agent")


# ═══════════════════════════════════════════════════════════════
# Security Levels & Decisions
# ═══════════════════════════════════════════════════════════════

class RiskLevel(str, Enum):
    """مستويات المخاطر"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityDecision(str, Enum):
    """قرارات الأمان"""
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    ESCALATE = "ESCALATE"


class OperationType(str, Enum):
    """أنواع العمليات"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    UPDATE = "update"


class Environment(str, Enum):
    """البيئات"""
    PRODUCTION = "production"
    TEST = "test"
    DEV = "dev"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════
# Security Policies
# ═══════════════════════════════════════════════════════════════

# قائمة قواعد البيانات المسموحة للكتابة
try:
    from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS
    WRITABLE_DBS = ALLOWED_TEST_DBS | ALLOWED_DEV_DBS
except ImportError:
    WRITABLE_DBS = frozenset()
    logger.warning("Could not import environment_policy, no writable DBs configured")

# الحقول الحساسة (لا تُعدّل بدون موافقة)
SENSITIVE_FIELDS = {
    "identification_id",  # هوية وطنية
    "passport_id",  # جواز سفر
    "iqama_id",  # إقامة
    "bank_account_id",  # حساب بنكي
    "private_email",  # بريد شخصي
    "private_phone",  # هاتف شخصي
}

# العمليات التي تتطلب Four-Eyes
FOUR_EYES_OPERATIONS = {
    "delete_employee",
    "modify_identity",
    "modify_salary",
    "terminate_contract",
}


class HaresAgent(BaseAgent):
    """
    وكيل الأمان والحماية - حَارِس
    
    يُقيّم المخاطر ويطبق السياسات الأمنية
    """
    
    def __init__(
        self,
        environment: Optional[str] = None,
        strict_mode: bool = True,
    ):
        super().__init__(
            name="Hares",
            role="Security & Policy Enforcement Agent",
        )
        self.environment = self._detect_environment(environment)
        self.strict_mode = strict_mode
        self.writable_dbs = WRITABLE_DBS
    
    # ═══════════════════════════════════════════════════════════════
    # Agentic Loop Implementation
    # ═══════════════════════════════════════════════════════════════
    
    def perceive(
        self,
        goal: AgentGoal,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        تحليل العملية المطلوبة والمخاطر
        """
        context = context or {}
        
        operation = context.get("operation", {})
        operation_type = operation.get("type", OperationType.READ)
        target_model = operation.get("model", "")
        target_db = context.get("database", "")
        affected_records = operation.get("records", [])
        modified_fields = operation.get("fields", [])
        requestor = context.get("requestor", "unknown")
        
        # تحديد البيئة
        env = self._identify_environment(target_db)
        
        # تقييم المخاطر الأولي
        risk = self._assess_risk(
            operation_type=operation_type,
            environment=env,
            model=target_model,
            fields=modified_fields,
        )
        
        # فحص البيانات الحساسة
        has_sensitive = self._has_sensitive_data(modified_fields)
        
        # فحص Four-Eyes
        requires_four_eyes = self._requires_four_eyes(
            operation_type, target_model, modified_fields
        )
        
        perception = {
            "operation_type": operation_type,
            "environment": env,
            "target_model": target_model,
            "target_db": target_db,
            "risk_level": risk,
            "has_sensitive_data": has_sensitive,
            "requires_four_eyes": requires_four_eyes,
            "affected_count": len(affected_records),
            "requestor": requestor,
            "is_writable_db": target_db in self.writable_dbs,
        }
        
        self._log_trace("PERCEIVE", perception)
        logger.info(
            f"Perceived operation: {operation_type} on {target_model}, "
            f"risk={risk}, env={env}"
        )
        
        return perception
    
    def plan(
        self,
        goal: AgentGoal,
        perception: Dict[str, Any]
    ) -> AgentPlan:
        """
        وضع خطة التحقق الأمني
        
        الخطوات:
        1. Check Environment - فحص البيئة
        2. Assess Risk - تقييم المخاطر
        3. Apply Policies - تطبيق السياسات
        4. Make Decision - اتخاذ القرار
        """
        plan = AgentPlan(plan_id=f"hares-{goal.objective[:20]}")
        
        operation_type = perception["operation_type"]
        environment = perception["environment"]
        risk_level = perception["risk_level"]
        
        # خطة التحقق
        plan.add_step({
            "action": "check_environment",
            "description": f"التحقق من البيئة: {environment}",
            "rationale": "Environment must be authorized for this operation",
        })
        
        plan.add_step({
            "action": "assess_risk",
            "description": f"تقييم المخاطر: {risk_level}",
            "rationale": f"Operation: {operation_type}, Risk: {risk_level}",
        })
        
        plan.add_step({
            "action": "apply_policies",
            "description": "تطبيق السياسات الأمنية",
            "rationale": "Check against all security policies",
        })
        
        plan.add_step({
            "action": "make_decision",
            "description": "اتخاذ القرار الأمني النهائي",
            "rationale": f"strict_mode={self.strict_mode}",
        })
        
        self._log_trace("PLAN", {
            "plan_id": plan.plan_id,
            "steps": len(plan.steps),
            "risk": risk_level,
        })
        
        logger.info(f"Planned {len(plan.steps)} security checks")
        
        return plan
    
    def execute(self, plan: AgentPlan) -> Dict[str, Any]:
        """
        تنفيذ خطة التحقق الأمني
        """
        result = {
            "decision": None,
            "risk_level": None,
            "violations": [],
            "requirements": [],
        }
        
        for i, step in enumerate(plan.steps):
            action = step["action"]
            logger.info(f"Executing security check {i+1}/{len(plan.steps)}: {action}")
            
            if action == "check_environment":
                # فحص البيئة
                env_check = self._check_environment()
                result["environment_check"] = env_check
                
                if not env_check["is_authorized"]:
                    result["violations"].append(env_check["violation"])
                
                plan.mark_step_complete(i)
            
            elif action == "assess_risk":
                # تقييم المخاطر
                risk_assessment = self._assess_risk_detailed()
                result["risk_assessment"] = risk_assessment
                result["risk_level"] = risk_assessment["level"]
                
                plan.mark_step_complete(i)
            
            elif action == "apply_policies":
                # تطبيق السياسات
                policy_check = self._apply_policies()
                result["policy_check"] = policy_check
                
                if policy_check["violations"]:
                    result["violations"].extend(policy_check["violations"])
                
                if policy_check["requirements"]:
                    result["requirements"].extend(policy_check["requirements"])
                
                plan.mark_step_complete(i)
            
            elif action == "make_decision":
                # اتخاذ القرار
                decision = self._make_security_decision(result)
                result.update(decision)
                
                plan.mark_step_complete(i)
        
        self._log_trace("EXECUTE", {
            "decision": result.get("decision"),
            "risk": result.get("risk_level"),
            "violations": len(result.get("violations", [])),
        })
        
        return result
    
    def reflect(
        self,
        goal: AgentGoal,
        plan: AgentPlan,
        result: Dict[str, Any]
    ) -> AgentReflection:
        """
        مراجعة القرار الأمني
        """
        decision = result.get("decision")
        risk_level = result.get("risk_level")
        violations = result.get("violations", [])
        
        # تقييم النجاح
        success = decision is not None
        
        # حساب الثقة
        confidence = 1.0
        if violations:
            confidence = 0.5  # وجود انتهاكات يقلل الثقة
        elif risk_level == RiskLevel.CRITICAL:
            confidence = 0.7
        elif risk_level == RiskLevel.HIGH:
            confidence = 0.85
        
        issues = []
        improvements = []
        
        # فحص الانتهاكات
        if violations:
            issues.append(f"{len(violations)} security violations detected")
        
        # اقتراحات
        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            improvements.append("Consider additional approval layer")
        
        if decision == SecurityDecision.DENY and not violations:
            improvements.append("Review denial reason for false positives")
        
        reflection = AgentReflection(
            success=success,
            confidence=confidence,
            issues=issues,
            improvements=improvements,
            should_retry=False,  # القرارات الأمنية لا تُعاد
        )
        
        self._log_trace("REFLECT", {
            "success": success,
            "confidence": confidence,
            "violations": len(violations),
        })
        
        logger.info(
            f"Security reflection: decision={decision}, confidence={confidence:.2f}, "
            f"violations={len(violations)}"
        )
        
        return reflection
    
    # ═══════════════════════════════════════════════════════════════
    # Helper Methods
    # ═══════════════════════════════════════════════════════════════
    
    def _detect_environment(self, env_hint: Optional[str]) -> Environment:
        """تحديد البيئة من environment variable أو hint"""
        if env_hint:
            return Environment(env_hint.lower())
        
        # من environment variable
        odoo_url = os.environ.get("ODOO_URL", "")
        if "prod" in odoo_url.lower():
            return Environment.PRODUCTION
        elif "test" in odoo_url.lower() or "staging" in odoo_url.lower():
            return Environment.TEST
        elif "dev" in odoo_url.lower():
            return Environment.DEV
        
        return Environment.UNKNOWN
    
    def _identify_environment(self, database: str) -> Environment:
        """تحديد البيئة من اسم قاعدة البيانات"""
        if database in self.writable_dbs:
            if "dev" in database.lower():
                return Environment.DEV
            else:
                return Environment.TEST
        
        # افتراضياً: production
        return Environment.PRODUCTION
    
    def _assess_risk(
        self,
        operation_type: str,
        environment: Environment,
        model: str,
        fields: List[str],
    ) -> RiskLevel:
        """تقييم مستوى المخاطر"""
        
        # عمليات الحذف دائماً عالية المخاطر
        if operation_type == OperationType.DELETE:
            return RiskLevel.CRITICAL
        
        # الكتابة على production = خطيرة
        if operation_type in (OperationType.WRITE, OperationType.UPDATE):
            if environment == Environment.PRODUCTION:
                return RiskLevel.CRITICAL
            
            # تعديل بيانات حساسة
            if any(f in SENSITIVE_FIELDS for f in fields):
                return RiskLevel.HIGH
            
            # تعديل بيانات موظفين
            if "employee" in model.lower():
                return RiskLevel.MEDIUM
        
        # القراءة آمنة عموماً
        return RiskLevel.LOW
    
    def _has_sensitive_data(self, fields: List[str]) -> bool:
        """فحص وجود بيانات حساسة"""
        return any(f in SENSITIVE_FIELDS for f in fields)
    
    def _requires_four_eyes(
        self,
        operation_type: str,
        model: str,
        fields: List[str],
    ) -> bool:
        """فحص الحاجة لـ Four-Eyes"""
        
        # الحذف دائماً يحتاج Four-Eyes
        if operation_type == OperationType.DELETE:
            return True
        
        # تعديل بيانات حساسة
        if self._has_sensitive_data(fields):
            return True
        
        # TODO: فحص FOUR_EYES_OPERATIONS
        
        return False
    
    def _check_environment(self) -> Dict[str, Any]:
        """فحص البيئة"""
        # TODO: تطبيق كامل
        return {
            "is_authorized": self.environment in (Environment.TEST, Environment.DEV),
            "violation": None if self.environment != Environment.PRODUCTION else {
                "type": "unauthorized_environment",
                "message": "Write operations on production require approval",
            },
        }
    
    def _assess_risk_detailed(self) -> Dict[str, Any]:
        """تقييم المخاطر التفصيلي"""
        # TODO: تطبيق كامل
        return {
            "level": RiskLevel.MEDIUM,
            "factors": ["write_operation", "employee_data"],
        }
    
    def _apply_policies(self) -> Dict[str, Any]:
        """تطبيق السياسات"""
        # TODO: تطبيق كامل
        return {
            "violations": [],
            "requirements": [],
        }
    
    def _make_security_decision(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """اتخاذ القرار الأمني النهائي"""
        violations = result.get("violations", [])
        requirements = result.get("requirements", [])
        risk_level = result.get("risk_level", RiskLevel.LOW)
        
        # وجود انتهاكات = رفض
        if violations:
            return {
                "decision": SecurityDecision.DENY,
                "reason": f"{len(violations)} security violations",
                "rationale": "Security policy violations must be resolved",
            }
        
        # مخاطر حرجة = تتطلب موافقة
        if risk_level == RiskLevel.CRITICAL:
            return {
                "decision": SecurityDecision.REQUIRE_APPROVAL,
                "reason": "Critical risk level",
                "approval_level": "senior",
                "rationale": "Critical operations require senior approval",
            }
        
        # متطلبات إضافية = تتطلب موافقة
        if requirements:
            return {
                "decision": SecurityDecision.REQUIRE_APPROVAL,
                "reason": "Additional requirements needed",
                "requirements": requirements,
                "rationale": "Operation requires additional authorization",
            }
        
        # مخاطر عالية في strict mode = تتطلب موافقة
        if self.strict_mode and risk_level == RiskLevel.HIGH:
            return {
                "decision": SecurityDecision.REQUIRE_APPROVAL,
                "reason": "High risk in strict mode",
                "approval_level": "manager",
                "rationale": "High-risk operations require manager approval in strict mode",
            }
        
        # آمن = سماح
        return {
            "decision": SecurityDecision.ALLOW,
            "reason": "Security checks passed",
            "rationale": f"Risk level {risk_level} is acceptable",
        }


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def create_hares_security_goal(
    description: str,
    operation: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> AgentGoal:
    """إنشاء هدف لـ Hares"""
    ctx = context or {}
    ctx.update({"operation": operation})
    
    return AgentGoal(
        objective=description,
        constraints=[
            "لا كتابة على Production بدون موافقة",
            "لا تعديل للبيانات الحساسة بدون Four-Eyes",
            "كل القرارات مُسجّلة في audit trail",
        ],
        success_criteria=[
            "تقييم المخاطر دقيق",
            "تطبيق السياسات كامل",
            "القرار واضح ومُبرّر",
        ],
        max_iterations=3,
        timeout_seconds=30,
    )
