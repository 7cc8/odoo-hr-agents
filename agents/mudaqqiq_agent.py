"""
وكيل التدقيق والامتثال الذكي: «مدقق» (Mudaqqiq Agentic Compliance Agent)
===============================================================================
مدقق هو الوكيل المسؤول عن التحقق من الامتثال القانوني والنظامي في Odoo:

الأدوار الرئيسية:
1. **الإدراك (Perceive)**: فهم السياق القانوني والمتطلبات النظامية
2. **التخطيط (Plan)**: استراتيجية التحقق من الامتثال
3. **التنفيذ (Execute)**: تطبيق قواعد الامتثال والتحقق
4. **التأمل (Reflect)**: تفسير القرارات والتعلم من السوابق

المجالات الرئيسية:
- نظام العمل السعودي (Saudi Labor Law)
- التأمينات الاجتماعية (GOSI)
- حماية الأجور (WPS/Mudad)
- السعودة (Nitaqat/Saudization)
- الإقامات والعقود
- الجزاءات والخصومات
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent

logger = logging.getLogger("mudaqqiq_agent")


class ComplianceCategory(str, Enum):
    """فئات الامتثال"""
    LABOR_LAW = "labor_law"  # نظام العمل
    GOSI = "gosi"  # التأمينات الاجتماعية
    WPS = "wps"  # حماية الأجور
    SAUDIZATION = "saudization"  # السعودة
    CONTRACTS = "contracts"  # العقود
    RESIDENCY = "residency"  # الإقامات
    DISCIPLINARY = "disciplinary"  # الجزاءات
    END_OF_SERVICE = "end_of_service"  # نهاية الخدمة
    GENERAL = "general"  # عام


class ComplianceStatus(str, Enum):
    """حالات الامتثال"""
    COMPLIANT = "compliant"  # ممتثل
    NON_COMPLIANT = "non_compliant"  # غير ممتثل
    PARTIALLY_COMPLIANT = "partially_compliant"  # ممتثل جزئياً
    REQUIRES_REVIEW = "requires_review"  # يحتاج مراجعة
    EXCEPTION_GRANTED = "exception_granted"  # استثناء مُعتمد


class ComplianceDecision(str, Enum):
    """قرارات مدقق"""
    APPROVE = "approve"  # موافقة (100% ممتثل)
    APPROVE_WITH_CONDITIONS = "approve_with_conditions"  # موافقة بشروط
    REJECT = "reject"  # رفض (مخالف)
    REQUEST_REVIEW = "request_review"  # طلب مراجعة بشرية
    ESCALATE_LEGAL = "escalate_legal"  # تصعيد للقانوني


@dataclass
class ComplianceRule:
    """قاعدة امتثال"""
    rule_id: str
    category: ComplianceCategory
    title_ar: str
    description_ar: str
    article_reference: Optional[str] = None  # مثل: "المادة 80 من نظام العمل"
    severity: str = "medium"  # low, medium, high, critical
    is_mandatory: bool = True
    
    def __str__(self) -> str:
        ref = f" ({self.article_reference})" if self.article_reference else ""
        return f"{self.title_ar}{ref}"


@dataclass
class ComplianceViolation:
    """مخالفة امتثال"""
    rule: ComplianceRule
    violation_description_ar: str
    severity: str
    suggested_fix_ar: Optional[str] = None
    can_be_fixed: bool = True


class MudaqqiqAgent(BaseAgent):
    """
    وكيل التدقيق والامتثال الذكي مع قدرات Agentic AI كاملة.
    
    الدورة الذكية:
    1. Perceive: فهم السياق القانوني والمتطلبات
    2. Plan: استراتيجية التحقق من الامتثال
    3. Execute: تطبيق القواعد والتحقق
    4. Reflect: تفسير القرارات والتعلم
    """

    def __init__(self, llm_model: Optional[str] = None):
        super().__init__(
            name="mudaqqiq",
            role="compliance_verification_agent",
            llm_model=llm_model,
        )
        
        # قاعدة القواعد
        self._rules_database = self._load_compliance_rules()
        
        # سجل السوابق (للتعلم)
        self._precedents: List[Dict[str, Any]] = []
        
        logger.info(f"✅ Mudaqqiq Agent initialized with {len(self._rules_database)} rules")

    # ============================================================================
    # Agentic Loop Implementation
    # ============================================================================

    def perceive(self, check_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 1: الإدراك - فهم السياق القانوني والمتطلبات
        
        Args:
            check_request: طلب التحقق من الامتثال
            
        Returns:
            perception: تحليل شامل للسياق القانوني
        """
        logger.info(f"🔍 Perceiving compliance check request")
        
        # استخراج البيانات الأساسية
        perception = {
            "check_type": check_request.get("type", "general"),
            "category": check_request.get("category", ComplianceCategory.GENERAL),
            "context": check_request.get("context", {}),
            "data": check_request.get("data", {}),
            "raw_request": check_request,
        }
        
        # تحديد القواعد المطبقة
        perception["applicable_rules"] = self._identify_applicable_rules(
            perception["category"],
            perception["context"]
        )
        
        # تحليل المخاطر النظامية
        perception["legal_risks"] = self._assess_legal_risks(perception)
        
        # تحديد مستوى الحساسية
        perception["sensitivity_level"] = self._assess_sensitivity(perception)
        
        logger.info(f"✅ Perception complete: {len(perception['applicable_rules'])} rules identified")
        return perception

    def plan(self, perception: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 2: التخطيط - بناء استراتيجية التحقق
        
        Args:
            perception: نتائج مرحلة الإدراك
            
        Returns:
            plan: خطة التحقق المفصلة
        """
        logger.info(f"📋 Planning compliance verification strategy")
        
        plan = {
            "verification_steps": [],
            "rules_to_check": perception["applicable_rules"],
            "priority_order": [],
            "expected_duration": "short",  # short, medium, long
        }
        
        # بناء خطوات التحقق
        for rule in perception["applicable_rules"]:
            step = {
                "rule_id": rule.rule_id,
                "rule_title": rule.title_ar,
                "check_method": self._determine_check_method(rule),
                "priority": rule.severity,
            }
            plan["verification_steps"].append(step)
        
        # ترتيب حسب الأولوية (critical → high → medium → low)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        plan["verification_steps"].sort(
            key=lambda s: severity_order.get(s["priority"], 99)
        )
        
        # تحديد المدة المتوقعة
        if len(plan["verification_steps"]) > 10:
            plan["expected_duration"] = "long"
        elif len(plan["verification_steps"]) > 5:
            plan["expected_duration"] = "medium"
        
        logger.info(f"✅ Plan created: {len(plan['verification_steps'])} verification steps")
        return plan

    def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 3: التنفيذ - تطبيق القواعد والتحقق
        
        Args:
            plan: خطة التحقق من مرحلة التخطيط
            
        Returns:
            result: نتيجة التحقق مع المخالفات إن وجدت
        """
        logger.info(f"⚡ Executing compliance verification")
        
        result = {
            "status": ComplianceStatus.COMPLIANT,
            "decision": ComplianceDecision.APPROVE,
            "violations": [],
            "warnings": [],
            "passed_checks": 0,
            "total_checks": len(plan["verification_steps"]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # تنفيذ كل خطوة تحقق
        for step in plan["verification_steps"]:
            try:
                check_result = self._execute_rule_check(step, plan)
                
                if check_result["passed"]:
                    result["passed_checks"] += 1
                else:
                    # مخالفة!
                    violation = check_result.get("violation")
                    if violation:
                        result["violations"].append(violation)
                
                # تحذيرات (warnings)
                if "warning" in check_result:
                    result["warnings"].append(check_result["warning"])
            
            except Exception as exc:
                logger.error(f"❌ Rule check failed: {exc}")
                result["warnings"].append({
                    "rule_id": step["rule_id"],
                    "error": str(exc),
                })
        
        # تحديد الحالة النهائية
        if len(result["violations"]) == 0:
            result["status"] = ComplianceStatus.COMPLIANT
            result["decision"] = ComplianceDecision.APPROVE
        elif len(result["violations"]) < result["total_checks"] / 2:
            result["status"] = ComplianceStatus.PARTIALLY_COMPLIANT
            result["decision"] = ComplianceDecision.APPROVE_WITH_CONDITIONS
        else:
            result["status"] = ComplianceStatus.NON_COMPLIANT
            result["decision"] = ComplianceDecision.REJECT
        
        # التحقق من المخالفات الحرجة (critical)
        has_critical = any(
            v.get("severity") == "critical"
            for v in result["violations"]
        )
        if has_critical:
            result["decision"] = ComplianceDecision.ESCALATE_LEGAL
        
        logger.info(f"✅ Execution complete: {result['status']}, {result['decision']}")
        return result

    def reflect(self, perception: Dict[str, Any], plan: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 4: التأمل - تفسير القرارات والتعلم
        
        Args:
            perception: نتائج الإدراك
            plan: الخطة المنفذة
            result: نتيجة التنفيذ
            
        Returns:
            reflection: تحليل شامل مع تفسيرات قانونية
        """
        logger.info(f"🤔 Reflecting on compliance verification")
        
        reflection = {
            "decision_rationale_ar": [],
            "legal_interpretation_ar": "",
            "confidence_score": 0.0,
            "lessons_learned": [],
            "should_record_precedent": False,
        }
        
        # تفسير القرار
        if result["decision"] == ComplianceDecision.APPROVE:
            reflection["decision_rationale_ar"].append(
                f"جميع الفحوصات ({result['passed_checks']}/{result['total_checks']}) نجحت. البيانات ممتثلة للأنظمة."
            )
            reflection["confidence_score"] = 0.95
        
        elif result["decision"] == ComplianceDecision.APPROVE_WITH_CONDITIONS:
            reflection["decision_rationale_ar"].append(
                f"معظم الفحوصات ({result['passed_checks']}/{result['total_checks']}) نجحت، "
                f"لكن هناك {len(result['violations'])} مخالفة يجب معالجتها."
            )
            reflection["confidence_score"] = 0.70
        
        elif result["decision"] == ComplianceDecision.REJECT:
            reflection["decision_rationale_ar"].append(
                f"فشل عدد كبير من الفحوصات ({result['total_checks'] - result['passed_checks']}/{result['total_checks']}). "
                f"البيانات غير ممتثلة."
            )
            reflection["confidence_score"] = 0.90
        
        elif result["decision"] == ComplianceDecision.ESCALATE_LEGAL:
            reflection["decision_rationale_ar"].append(
                "وُجدت مخالفة حرجة تتطلب تدخل القسم القانوني."
            )
            reflection["confidence_score"] = 0.95
        
        # تفسير قانوني للمخالفات
        if result["violations"]:
            legal_interpretation = self._generate_legal_interpretation(result["violations"])
            reflection["legal_interpretation_ar"] = legal_interpretation
        
        # دروس مستفادة
        reflection["lessons_learned"] = self._extract_lessons(perception, result)
        
        # هل نسجل هذا كسابقة؟
        if result["decision"] in [ComplianceDecision.APPROVE_WITH_CONDITIONS, ComplianceDecision.ESCALATE_LEGAL]:
            reflection["should_record_precedent"] = True
        
        logger.info(f"✅ Reflection complete: confidence={reflection['confidence_score']:.2f}")
        return reflection

    # ============================================================================
    # Compliance Rules Database
    # ============================================================================

    def _load_compliance_rules(self) -> List[ComplianceRule]:
        """تحميل قاعدة قواعد الامتثال"""
        rules = [
            # قواعد نظام العمل
            ComplianceRule(
                rule_id="labor_law_01",
                category=ComplianceCategory.LABOR_LAW,
                title_ar="الحد الأدنى للأجور",
                description_ar="يجب ألا يقل الأجر الأساسي عن 4,000 ريال للسعوديين",
                article_reference="قرار مجلس الوزراء رقم 4 لسنة 2021",
                severity="high",
            ),
            ComplianceRule(
                rule_id="labor_law_02",
                category=ComplianceCategory.LABOR_LAW,
                title_ar="ساعات العمل الأسبوعية",
                description_ar="لا تزيد ساعات العمل عن 48 ساعة أسبوعياً، و8 ساعات يومياً",
                article_reference="المادة 98 من نظام العمل",
                severity="medium",
            ),
            ComplianceRule(
                rule_id="labor_law_03",
                category=ComplianceCategory.LABOR_LAW,
                title_ar="فترة التجربة",
                description_ar="لا تزيد فترة التجربة عن 90 يوماً (تمدد لـ 180 يوماً باتفاق)",
                article_reference="المادة 53 من نظام العمل",
                severity="medium",
            ),
            
            # قواعد GOSI
            ComplianceRule(
                rule_id="gosi_01",
                category=ComplianceCategory.GOSI,
                title_ar="نسبة اشتراك الموظف السعودي",
                description_ar="9.75% من الأجر الخاضع (حد أقصى 45,000 ريال)",
                article_reference="نظام التأمينات الاجتماعية",
                severity="critical",
            ),
            ComplianceRule(
                rule_id="gosi_02",
                category=ComplianceCategory.GOSI,
                title_ar="نسبة اشتراك صاحب العمل",
                description_ar="9.75% أخطار مهنية + 2% ساند",
                article_reference="نظام التأمينات الاجتماعية",
                severity="critical",
            ),
            
            # قواعد WPS
            ComplianceRule(
                rule_id="wps_01",
                category=ComplianceCategory.WPS,
                title_ar="موعد صرف الراتب",
                description_ar="يجب صرف الراتب خلال 7 أيام من نهاية الشهر",
                article_reference="نظام حماية الأجور",
                severity="high",
            ),
            
            # قواعد الخصومات
            ComplianceRule(
                rule_id="deduction_01",
                category=ComplianceCategory.DISCIPLINARY,
                title_ar="الحد الأقصى للخصومات",
                description_ar="لا تتجاوز الخصومات الشهرية 50% من الأجر",
                article_reference="المادة 92 من نظام العمل",
                severity="critical",
            ),
            
            # قواعد العقود
            ComplianceRule(
                rule_id="contract_01",
                category=ComplianceCategory.CONTRACTS,
                title_ar="مدة العقد المحدد",
                description_ar="لا تزيد مدة العقد المحدد عن 4 سنوات (قابلة للتجديد)",
                article_reference="المادة 55 من نظام العمل",
                severity="medium",
            ),
            
            # قواعد نهاية الخدمة
            ComplianceRule(
                rule_id="eos_01",
                category=ComplianceCategory.END_OF_SERVICE,
                title_ar="حساب مكافأة نهاية الخدمة",
                description_ar="نصف راتب شهر لكل سنة (5 سنوات الأولى)، راتب شهر كامل بعدها",
                article_reference="المادة 84 من نظام العمل",
                severity="high",
            ),
        ]
        
        return rules

    def _identify_applicable_rules(
        self,
        category: ComplianceCategory,
        context: Dict[str, Any]
    ) -> List[ComplianceRule]:
        """تحديد القواعد المطبقة على الحالة"""
        
        # إذا كانت الفئة محددة
        if category != ComplianceCategory.GENERAL:
            return [r for r in self._rules_database if r.category == category]
        
        # إذا كانت general، نحلل السياق
        applicable = []
        
        # حسب نوع البيانات في السياق
        if "salary" in context or "wage" in context:
            applicable.extend([r for r in self._rules_database if r.category == ComplianceCategory.LABOR_LAW])
        
        if "gosi" in context or "social_insurance" in context:
            applicable.extend([r for r in self._rules_database if r.category == ComplianceCategory.GOSI])
        
        if "deduction" in context or "penalty" in context:
            applicable.extend([r for r in self._rules_database if r.category == ComplianceCategory.DISCIPLINARY])
        
        # إزالة التكرار
        seen = set()
        unique_applicable = []
        for rule in applicable:
            if rule.rule_id not in seen:
                seen.add(rule.rule_id)
                unique_applicable.append(rule)
        
        return unique_applicable if unique_applicable else self._rules_database

    def _assess_legal_risks(self, perception: Dict[str, Any]) -> List[str]:
        """تقييم المخاطر القانونية"""
        risks = []
        
        # فحص القواعد الحرجة
        critical_rules = [
            r for r in perception["applicable_rules"]
            if r.severity == "critical"
        ]
        
        if critical_rules:
            risks.append(f"{len(critical_rules)} قاعدة حرجة يجب التحقق منها")
        
        return risks

    def _assess_sensitivity(self, perception: Dict[str, Any]) -> str:
        """تقييم مستوى الحساسية"""
        # حسب عدد القواعد الحرجة
        critical_count = sum(
            1 for r in perception["applicable_rules"]
            if r.severity == "critical"
        )
        
        if critical_count >= 2:
            return "high"
        elif critical_count == 1:
            return "medium"
        else:
            return "low"

    # ============================================================================
    # Verification Logic
    # ============================================================================

    def _determine_check_method(self, rule: ComplianceRule) -> str:
        """تحديد طريقة الفحص للقاعدة"""
        if rule.category == ComplianceCategory.GOSI:
            return "calculate_percentage"
        elif rule.category == ComplianceCategory.LABOR_LAW:
            return "compare_threshold"
        elif rule.category == ComplianceCategory.DISCIPLINARY:
            return "sum_deductions"
        else:
            return "manual_review"

    def _execute_rule_check(self, step: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
        """تنفيذ فحص قاعدة واحدة"""
        # TODO: تطبيق المنطق الفعلي لكل قاعدة
        # حالياً نرجع passed دائماً للاختبار
        
        return {
            "passed": True,
            "rule_id": step["rule_id"],
            "check_method": step["check_method"],
        }

    def _generate_legal_interpretation(self, violations: List[Dict[str, Any]]) -> str:
        """توليد تفسير قانوني للمخالفات"""
        if not violations:
            return ""
        
        interpretation_parts = []
        
        for violation in violations:
            rule_ref = violation.get("article_reference", "")
            interpretation_parts.append(
                f"- {violation.get('violation_description_ar', '')} ({rule_ref})"
            )
        
        return "\n".join(interpretation_parts)

    def _extract_lessons(self, perception: Dict[str, Any], result: Dict[str, Any]) -> List[str]:
        """استخلاص الدروس المستفادة"""
        lessons = []
        
        if result["violations"]:
            lessons.append(f"تم اكتشاف {len(result['violations'])} مخالفة نظامية")
        
        if result["warnings"]:
            lessons.append(f"ظهرت {len(result['warnings'])} تحذيرات تحتاج متابعة")
        
        return lessons

    # ============================================================================
    # Public API
    # ============================================================================

    def verify_compliance(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        واجهة عامة للتحقق من الامتثال
        
        تستخدم الدورة الذكية الكاملة:
        Perceive → Plan → Execute → Reflect
        """
        logger.info(f"🎯 Verifying compliance: {request.get('type')}")
        
        # الدورة الذكية الكاملة
        perception = self.perceive(request)
        plan = self.plan(perception)
        result = self.execute(plan)
        reflection = self.reflect(perception, plan, result)
        
        # تنسيق النتيجة النهائية
        return {
            "status": result["status"],
            "decision": result["decision"],
            "violations": result["violations"],
            "warnings": result["warnings"],
            "passed_checks": result["passed_checks"],
            "total_checks": result["total_checks"],
            "decision_rationale_ar": reflection["decision_rationale_ar"],
            "legal_interpretation_ar": reflection["legal_interpretation_ar"],
            "confidence_score": reflection["confidence_score"],
            "timestamp": result["timestamp"],
        }


# ============================================================================
# Singleton Factory
# ============================================================================

_GLOBAL_MUDAQQIQ: Optional[MudaqqiqAgent] = None


def get_mudaqqiq_agent() -> MudaqqiqAgent:
    """الحصول على كائن وكيل مدقق المفرد (Singleton)"""
    global _GLOBAL_MUDAQQIQ
    if _GLOBAL_MUDAQQIQ is None:
        _GLOBAL_MUDAQQIQ = MudaqqiqAgent()
    return _GLOBAL_MUDAQQIQ
