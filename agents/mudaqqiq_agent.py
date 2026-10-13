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
import saudi_labor_law_rules as sllr

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

        op_id = check_request.get("operation_id") or check_request.get("context", {}).get("operation_id")
        if op_id:
            try:
                from agents.agent_events_service import emit_agent_event
                emit_agent_event(
                    op_id,
                    "Mudaqqiq (Compliance)",
                    "perceive",
                    reasoning="Analyzing compliance requirements and identifying applicable legal rules...",
                    status="in_progress"
                )
            except Exception:
                pass
        
        # استخراج البيانات الأساسية
        perception = {
            "check_type": check_request.get("type", "general"),
            "category": check_request.get("category", ComplianceCategory.GENERAL),
            "context": check_request.get("context", {}),
            "data": check_request.get("data", {}),
            "raw_request": check_request,
            "operation_id": op_id,
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

        if op_id:
            try:
                from agents.agent_events_service import emit_agent_event
                emit_agent_event(
                    op_id,
                    "Mudaqqiq (Compliance)",
                    "perceive",
                    decision=f"Identified {len(perception['applicable_rules'])} applicable rules",
                    status="success"
                )
            except Exception:
                pass

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

        op_id = perception.get("operation_id") or perception.get("context", {}).get("operation_id")
        if op_id:
            try:
                from agents.agent_events_service import emit_agent_event
                emit_agent_event(
                    op_id,
                    "Mudaqqiq (Compliance)",
                    "plan",
                    decision="verify_compliance_rules",
                    reasoning="Building verification steps prioritized by severity",
                    status="in_progress"
                )
            except Exception:
                pass
        
        plan = {
            "verification_steps": [],
            "rules_to_check": perception["applicable_rules"],
            "priority_order": [],
            "expected_duration": "short",  # short, medium, long
            "data": perception.get("data", {}),
            "context": perception.get("context", {}),
            "operation_id": op_id,
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

        if op_id:
            try:
                from agents.agent_events_service import emit_agent_event
                emit_agent_event(
                    op_id,
                    "Mudaqqiq (Compliance)",
                    "plan",
                    decision=f"Created {len(plan['verification_steps'])} verification steps",
                    status="success"
                )
            except Exception:
                pass

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

        op_id = plan.get("operation_id") or plan.get("context", {}).get("operation_id")
        if op_id:
            try:
                from agents.agent_events_service import emit_agent_event
                emit_agent_event(
                    op_id,
                    "Mudaqqiq (Compliance)",
                    "execute",
                    reasoning="Applying compliance rules and checks...",
                    status="in_progress"
                )
            except Exception:
                pass
        
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

        if op_id:
            try:
                from agents.agent_events_service import emit_agent_event
                emit_agent_event(
                    op_id,
                    "Mudaqqiq (Compliance)",
                    "execute",
                    decision=f"Status: {result['status'].value if hasattr(result['status'], 'value') else result['status']}, Violations: {len(result['violations'])}",
                    status="success" if result["status"] == ComplianceStatus.COMPLIANT else "failed"
                )
            except Exception:
                pass

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

    def _find_rule(self, rule_id: str) -> Optional[ComplianceRule]:
        """البحث عن قاعدة بالمعرف"""
        for r in self._rules_database:
            if r.rule_id == rule_id:
                return r
        return None

    def _execute_rule_check(self, step: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
        """تنفيذ فحص قاعدة واحدة باستخدام محرك القواعد الحتمي (saudi_labor_law_rules)"""
        rule_id = step["rule_id"]
        data = plan.get("data", {})
        context = plan.get("context", {})

        # 1. الحد الأدنى للراتب للسعوديين (labor_law_01)
        if rule_id == "labor_law_01":
            basic_sal = data.get("basic_salary") if "basic_salary" in data else data.get("basic_wage")
            is_saudi = context.get("saudi_employee") or data.get("employee_type") == "saudi" or data.get("is_saudi")
            if is_saudi and basic_sal is not None and float(basic_sal) < 4000.0:
                rule = self._find_rule(rule_id)
                return {
                    "passed": False,
                    "rule_id": rule_id,
                    "check_method": step["check_method"],
                    "violation": {
                        "rule": rule,
                        "violation_description_ar": f"الراتب المحدد ({float(basic_sal):,.2f} ريال) أقل من الحد الأدنى للمواطن السعودي في نطاقات (4,000 ريال)",
                        "severity": rule.severity if rule else "critical",
                        "article_reference": rule.article_reference if rule else "نظام العمل وقرارات التوطين",
                    }
                }

        # 2. فترة التجربة (labor_law_03)
        elif rule_id == "labor_law_03":
            probation_days = data.get("probation_days")
            if probation_days is not None:
                has_written = data.get("has_written_agreement", False)
                res = sllr.validate_probation_period(int(probation_days), has_written_agreement=has_written)
                if not res.is_valid:
                    rule = self._find_rule(rule_id)
                    return {
                        "passed": False,
                        "rule_id": rule_id,
                        "check_method": step["check_method"],
                        "violation": {
                            "rule": rule,
                            "violation_description_ar": res.message_ar,
                            "severity": rule.severity if rule else "medium",
                            "article_reference": res.article,
                        }
                    }

        # 3. التأمينات الاجتماعية للموظف السعودي (gosi_01)
        elif rule_id == "gosi_01":
            basic_sal = data.get("basic_salary") if "basic_salary" in data else data.get("basic_wage")
            gosi_contr = data.get("gosi_contribution") if "gosi_contribution" in data else data.get("gosi_employee_contribution")
            if basic_sal is not None and gosi_contr is not None:
                calc = sllr.calculate_gosi_contributions(float(basic_sal), float(data.get("housing_allowance", 0.0)), is_saudi=True)
                if abs(float(gosi_contr) - calc.total_employee) > 1.0:
                    rule = self._find_rule(rule_id)
                    return {
                        "passed": False,
                        "rule_id": rule_id,
                        "check_method": step["check_method"],
                        "violation": {
                            "rule": rule,
                            "violation_description_ar": f"استقطاع التأمينات ({float(gosi_contr):,.2f} ريال) لا يطابق النسبة النظامية ({calc.total_employee:,.2f} ريال)",
                            "severity": rule.severity if rule else "critical",
                            "article_reference": calc.article_reference,
                        }
                    }

        # 4. الحد الأقصى للاستقطاعات (deduction_01)
        elif rule_id == "deduction_01":
            basic_sal = data.get("basic_salary") if "basic_salary" in data else data.get("basic_wage")
            deductions = data.get("total_monthly_deductions") if "total_monthly_deductions" in data else data.get("deduction_amount")
            if basic_sal is not None and deductions is not None:
                if float(deductions) > float(basic_sal) * 0.50:
                    rule = self._find_rule(rule_id)
                    return {
                        "passed": False,
                        "rule_id": rule_id,
                        "check_method": step["check_method"],
                        "violation": {
                            "rule": rule,
                            "violation_description_ar": f"إجمالي الاستقطاعات الشهرية ({float(deductions):,.2f} ريال) يتجاوز سقف 50% من الأجر",
                            "severity": rule.severity if rule else "critical",
                            "article_reference": "المادة 92 من نظام العمل",
                        }
                    }

        # 5. مدة العقد ونوعه لغير السعودي (contract_01)
        elif rule_id == "contract_01":
            duration_years = data.get("contract_duration_years")
            if duration_years is not None and float(duration_years) > 4.0:
                rule = self._find_rule(rule_id)
                return {
                    "passed": False,
                    "rule_id": rule_id,
                    "check_method": step["check_method"],
                    "violation": {
                        "rule": rule,
                        "violation_description_ar": f"مدة العقد المحدد ({duration_years} سنوات) تزيد على السقف النظامي (4 سنوات)",
                        "severity": rule.severity if rule else "medium",
                        "article_reference": "المادة 55 من نظام العمل",
                    }
                }

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

    def consult_labor_law(self, query: str, article_number: Optional[int] = None) -> Dict[str, Any]:
        """
        استشارة قانونية ونظامية من وكيل التدقيق «مدقق» استناداً إلى نصوص نظام العمل السعودي واللوائح.
        """
        from labor_law_knowledge import LaborLawKnowledgeBase
        kb = LaborLawKnowledgeBase.get_instance()

        articles = []
        if article_number and article_number in kb.articles:
            articles = [kb.articles[article_number]]
        else:
            articles = kb.search(query, top_k=3)

        if not articles:
            return {
                "status": "not_found",
                "agent": "mudaqqiq",
                "role": "وكيل التدقيق والامتثال لنظام العمل السعودي",
                "query": query,
                "message_ar": "لم يتم العثور على مادة مطابقة في نظام العمل السعودي لهذا الاستعلام.",
                "articles": [],
            }

        primary = articles[0]
        # شروحات ملخصة لأبرز المواد
        explanation = ""
        if primary.article_number == 98:
            explanation = (
                "وفقاً للمادة (98) من نظام العمل السعودي:\n"
                "• ساعات العمل الفعلية العادية: لا تزيد على ثماني (8) ساعات يومياً (إذا اعتمد المعيار اليومي) أو 48 ساعة أسبوعياً (إذا اعتمد المعيار الأسبوعي).\n"
                "• ساعات العمل في شهر رمضان المبارك للمسلمين: تُخفض ساعات العمل الفعلية بحيث لا تزيد على ست (6) ساعات في اليوم الواحد، أو ست وثلاثين (36) ساعة في الأسبوع."
            )
        elif primary.article_number == 53:
            explanation = (
                "وفقاً للمادة (53) من نظام العمل السعودي وتعديلاتها:\n"
                "• الأصل في فترة التجربة ألا تزيد على تسعين (90) يوماً.\n"
                "• يجوز باتفاق مكتوب صريح بين العامل وصاحب العمل تمديدها بما لا يتجاوز مائة وثمانين (180) يوماً.\n"
                "• لا تدخل في حساب فترة التجربة إجازة عيدي الفطر والأضحى والإجازة المرضية."
            )
        elif primary.article_number == 109:
            explanation = (
                "وفقاً للمادة (109) من نظام العمل السعودي:\n"
                "• يستحق العامل إجازة سنوية بأجر لا تقل عن 21 يوماً.\n"
                "• تُزاد إلى 30 يوماً إذا أمضى العامل خمس سنوات متصلة في خدمة صاحب العمل."
            )
        elif primary.article_number in (151, 116):
            explanation = (
                "وفقاً للمادة (151) من نظام العمل السعودي وتعديلاته:\n"
                "• للمرأة العاملة الحق في إجازة وضع بأجر كامل.\n"
                "• يحظر تشغيل المرأة بعد الوضع بأي حال من الأحوال خلال الستة أسابيع التالية له."
            )
        elif primary.article_number in (84, 85):
            explanation = (
                "وفقاً للمادتين (84 و 85) من نظام العمل:\n"
                "• تُحسب مكافأة نهاية الخدمة بأجر نصف شهر عن كل سنة من السنوات الخمس الأولى، وأجر شهر كامل عن كل سنة تالية.\n"
                "• في حال الاستقالة: يستحق ثلث المكافأة بعد خدمة من سنتين إلى 5 سنوات، وثلثيها إذا زادت على 5 سنوات ولم تبلغ 10، وتستحق كاملة إذا بلغت 10 سنوات فأكثر."
            )
        else:
            explanation = f"تنص المادة ({primary.article_number}) صراحة على ما يلي: {primary.text}"

        return {
            "status": "success",
            "agent": "mudaqqiq",
            "role": "وكيل التدقيق والامتثال لنظام العمل السعودي",
            "query": query,
            "primary_article_number": primary.article_number,
            "primary_article_title": primary.title,
            "primary_article_text": primary.text,
            "explanation_ar": explanation,
            "related_articles": [
                {"number": a.article_number, "title": a.title, "text": a.text}
                for a in articles[1:]
            ],
            "legal_source": "نظام العمل السعودي (المرسوم الملكي م/51 وتعديلاته)",
        }

    # ============================================================================
    # Deterministic Compliance & Calculation Methods (via saudi_labor_law_rules)
    # ============================================================================

    def calculate_gosi(
        self,
        basic_wage: float,
        housing_allowance: float = 0.0,
        is_saudi: bool = True
    ) -> sllr.GOSIContributionResult:
        """حساب اشتراكات التأمينات الاجتماعية وساند بدقة تامة"""
        return sllr.calculate_gosi_contributions(basic_wage, housing_allowance, is_saudi)

    def calculate_eosb(
        self,
        basic_wage: float = 0.0,
        service_years: float = 0.0,
        is_resignation: bool = False,
        resignation_reason: sllr.ResignationReason = sllr.ResignationReason.STANDARD,
        is_saudi: bool = True,
        last_gross_wage: Optional[float] = None
    ) -> sllr.EOSBCalculationResult:
        """حساب مكافأة نهاية الخدمة بالريال وفق المواد 84 و 85 و 87"""
        effective_wage = last_gross_wage if last_gross_wage is not None else basic_wage
        return sllr.calculate_end_of_service_benefit(
            last_gross_wage=effective_wage,
            service_years=service_years,
            is_saudi=is_saudi,
            is_resignation=is_resignation,
            resignation_reason=resignation_reason,
        )

    def calculate_overtime(
        self,
        basic_wage: float,
        gross_wage: float,
        overtime_hours: float
    ) -> sllr.OvertimeCalculationResult:
        """حساب أجر ساعات العمل الإضافية وفق المادة 107"""
        return sllr.calculate_overtime_pay(basic_wage, gross_wage, overtime_hours)

    def validate_probation(
        self,
        probation_days: int,
        has_written_agreement: bool = False
    ) -> sllr.RuleValidationResult:
        """التحقق من ضوابط فترة التجربة وفق المادة 53 وتعديلات 1446هـ"""
        return sllr.validate_probation_period(probation_days, has_written_agreement)

    def validate_contract_type(
        self,
        is_saudi: bool,
        contract_type: sllr.ContractType
    ) -> sllr.RuleValidationResult:
        """التحقق من نوع العقد وفق المادة 37 (حظر العقود غير المحددة لغير السعودي)"""
        return sllr.validate_contract_type_for_nationality(is_saudi, contract_type)

    def validate_disciplinary(
        self,
        infraction_deduction_days: float,
        daily_wage: float,
        prior_deductions_this_month_days: float = 0.0,
        suspension_days: float = 0.0
    ) -> sllr.RuleValidationResult:
        """التحقق من الجزاءات التأديبية وفق المادة 70"""
        return sllr.validate_disciplinary_deduction(
            infraction_deduction_days=infraction_deduction_days,
            daily_wage=daily_wage,
            prior_deductions_this_month_days=prior_deductions_this_month_days,
            suspension_days=suspension_days,
        )

    def validate_working_hours(
        self,
        daily_hours: float,
        weekly_hours: float,
        is_ramadan: bool = False,
        is_muslim: bool = True
    ) -> sllr.RuleValidationResult:
        """التحقق من ساعات العمل وفق المادة 98 (بما فيها ساعات رمضان للمسلمين)"""
        max_daily = sllr.RAMADAN_MUSLIM_DAILY_HOURS if (is_ramadan and is_muslim) else sllr.STANDARD_DAILY_WORKING_HOURS
        max_weekly = sllr.RAMADAN_MUSLIM_WEEKLY_HOURS if (is_ramadan and is_muslim) else sllr.STANDARD_WEEKLY_WORKING_HOURS

        if daily_hours > max_daily or weekly_hours > max_weekly:
            season_str = "في شهر رمضان للمسلمين" if (is_ramadan and is_muslim) else "العادية"
            return sllr.RuleValidationResult(
                is_valid=False,
                article="المادة 98",
                code="EXCEEDED_MAX_WORKING_HOURS",
                message_ar=f"مخالفة للمادة 98: ساعات العمل الفعلية {season_str} يجب ألا تتجاوز {max_daily} ساعات يومياً أو {max_weekly} ساعة أسبوعياً.",
                details={"daily_hours": daily_hours, "max_daily": max_daily, "weekly_hours": weekly_hours, "max_weekly": max_weekly}
            )
        return sllr.RuleValidationResult(
            is_valid=True,
            article="المادة 98",
            code="WORKING_HOURS_COMPLIANT",
            message_ar="ساعات العمل متوافقة مع ضوابط المادة 98 من نظام العمل.",
            details={"daily_hours": daily_hours, "weekly_hours": weekly_hours}
        )

    def calculate_annual_leave(self, service_years: float) -> int:
        """حساب أيام الإجازة السنوية وفق المادة 109"""
        return sllr.calculate_annual_leave_entitlement(service_years)

    def get_occasion_leave_days(self, leave_type: sllr.OccasionLeaveType) -> int:
        """إرجاع عدد أيام إجازات المناسبات وفق المادة 113 وتعديلات 1446هـ"""
        return sllr.get_occasion_leave_statutory_days(leave_type)


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
