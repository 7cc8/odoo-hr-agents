"""
وكيل الرقابة والتدقيق الذكي: «سجل» (Sijil Agentic Audit Agent)
=====================================================================
سجل هو الوكيل المسؤول عن الرقابة والتدقيق المستمر:

الأدوار الرئيسية:
1. **الإدراك (Perceive)**: تحليل السجلات واكتشاف الأنماط
2. **التخطيط (Plan)**: استراتيجية التدقيق (شامل/انتقائي/استباقي)
3. **التنفيذ (Execute)**: جمع وتحليل السجلات وإنتاج التقارير
4. **التأمل (Reflect)**: تقييم الشمولية واكتشاف الشذوذ

القدرات الرئيسية:
- جمع سجلات من 12+ ملف JSONL
- اكتشاف الشذوذ (Anomaly Detection)
- توليد تقارير HTML/PDF
- تنبيهات استباقية (Proactive Alerts)
- تتبع الامتثال عبر الزمن
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agents.base_agent import BaseAgent

logger = logging.getLogger("sijil_agent")

# Audit log files locations
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"


class AuditScope(str, Enum):
    """نطاق التدقيق"""
    COMPREHENSIVE = "comprehensive"  # تدقيق شامل لكل السجلات
    SELECTIVE = "selective"  # تدقيق انتقائي (حسب الفترة/النوع)
    ANOMALY_ONLY = "anomaly_only"  # فقط الشذوذات
    PROACTIVE = "proactive"  # تدقيق استباقي (للتنبيهات)


class AnomalyType(str, Enum):
    """أنواع الشذوذ"""
    UNUSUAL_PATTERN = "unusual_pattern"  # نمط غير معتاد
    FREQUENCY_SPIKE = "frequency_spike"  # ارتفاع مفاجئ
    UNAUTHORIZED_ACCESS = "unauthorized_access"  # وصول غير مصرح
    DATA_INCONSISTENCY = "data_inconsistency"  # عدم اتساق البيانات
    SECURITY_BREACH = "security_breach"  # خرق أمني محتمل


class AuditDecision(str, Enum):
    """قرارات سجل"""
    APPROVE_CLEAN = "approve_clean"  # السجلات نظيفة
    ALERT_ANOMALIES = "alert_anomalies"  # تنبيه بشذوذات
    ESCALATE_CRITICAL = "escalate_critical"  # تصعيد لحالة حرجة
    REQUEST_INVESTIGATION = "request_investigation"  # طلب تحقيق


@dataclass
class AuditAnomaly:
    """شذوذ مكتشف"""
    anomaly_id: str
    anomaly_type: AnomalyType
    severity: str  # low, medium, high, critical
    description_ar: str
    timestamp: str
    affected_records: int
    recommended_action_ar: str


@dataclass
class AuditSummary:
    """ملخص التدقيق"""
    total_operations: int
    operations_by_type: Dict[str, int]
    operations_by_agent: Dict[str, int]
    anomalies: List[AuditAnomaly]
    time_range: Tuple[str, str]
    compliance_score: float  # 0.0 - 1.0


class SijilAgent(BaseAgent):
    """
    وكيل الرقابة والتدقيق الذكي مع قدرات Agentic AI كاملة.
    
    الدورة الذكية:
    1. Perceive: تحليل السجلات واكتشاف الأنماط
    2. Plan: استراتيجية التدقيق
    3. Execute: جمع وتحليل وإنتاج التقارير
    4. Reflect: تقييم الشمولية والتعلم
    """

    def __init__(self, logs_dir: Optional[Path] = None, llm_model: Optional[str] = None):
        super().__init__(
            name="sijil",
            role="audit_and_governance_agent",
            llm_model=llm_model,
        )
        
        self.logs_dir = logs_dir or LOGS_DIR
        
        # قائمة ملفات السجلات المعروفة
        self.audit_log_files = [
            "agent_operations_log.jsonl",
            "writer_audit_log.jsonl",
            "deletion_audit_log.jsonl",
            "employee_audit_log.jsonl",
            "contract_audit_log.jsonl",
            "payroll_audit_log.jsonl",
            "loan_audit_log.jsonl",
            "eos_audit_log.jsonl",
            "gr_audit_log.jsonl",
            "appraisal_audit_log.jsonl",
            "recruitment_audit_log.jsonl",
            "disciplinary_audit_log.jsonl",
        ]
        
        # سجل الشذوذات المكتشفة (للتعلم)
        self._known_anomalies: List[AuditAnomaly] = []
        
        logger.info(f"✅ Sijil Agent initialized with {len(self.audit_log_files)} audit sources")

    # ============================================================================
    # Agentic Loop Implementation
    # ============================================================================

    def perceive(self, audit_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 1: الإدراك - تحليل السجلات واكتشاف الأنماط
        
        Args:
            audit_request: طلب التدقيق
            
        Returns:
            perception: تحليل شامل للسجلات
        """
        logger.info(f"🔍 Perceiving audit request")
        
        # استخراج البيانات الأساسية
        perception = {
            "scope": audit_request.get("scope", AuditScope.COMPREHENSIVE),
            "time_range": audit_request.get("time_range"),  # (start, end)
            "focus_areas": audit_request.get("focus_areas", []),  # قائمة المجالات
            "raw_request": audit_request,
        }
        
        # جمع السجلات
        perception["available_logs"] = self._scan_available_logs()
        perception["total_records"] = self._count_total_records(perception["available_logs"])
        
        # تحليل أولي للأنماط
        perception["patterns"] = self._analyze_patterns_quick(perception["available_logs"])
        
        # تحديد مستوى الأولوية
        perception["priority_level"] = self._assess_priority(perception)
        
        logger.info(f"✅ Perception complete: {perception['total_records']} records from {len(perception['available_logs'])} files")
        return perception

    def plan(self, perception: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 2: التخطيط - بناء استراتيجية التدقيق
        
        Args:
            perception: نتائج مرحلة الإدراك
            
        Returns:
            plan: خطة التدقيق المفصلة
        """
        logger.info(f"📋 Planning audit strategy")
        
        plan = {
            "scope": perception["scope"],
            "audit_steps": [],
            "anomaly_detection_enabled": True,
            "report_format": "comprehensive",  # comprehensive, summary, alerts_only
        }
        
        # بناء خطوات التدقيق
        if perception["scope"] == AuditScope.COMPREHENSIVE:
            plan["audit_steps"] = [
                {"action": "collect_all_logs", "description": "جمع كل السجلات"},
                {"action": "analyze_operations", "description": "تحليل العمليات"},
                {"action": "detect_anomalies", "description": "اكتشاف الشذوذات"},
                {"action": "calculate_compliance", "description": "حساب نسبة الامتثال"},
                {"action": "generate_report", "description": "إنتاج التقرير"},
            ]
        
        elif perception["scope"] == AuditScope.SELECTIVE:
            plan["audit_steps"] = [
                {"action": "collect_selective_logs", "description": "جمع سجلات انتقائية"},
                {"action": "analyze_focused", "description": "تحليل مركّز"},
                {"action": "generate_summary", "description": "إنتاج ملخص"},
            ]
        
        elif perception["scope"] == AuditScope.ANOMALY_ONLY:
            plan["audit_steps"] = [
                {"action": "scan_for_anomalies", "description": "مسح الشذوذات"},
                {"action": "classify_anomalies", "description": "تصنيف الشذوذات"},
                {"action": "generate_alerts", "description": "إنتاج تنبيهات"},
            ]
        
        elif perception["scope"] == AuditScope.PROACTIVE:
            plan["audit_steps"] = [
                {"action": "monitor_recent", "description": "مراقبة الأحدث"},
                {"action": "predict_issues", "description": "التنبؤ بالمشاكل"},
                {"action": "send_proactive_alerts", "description": "إرسال تنبيهات استباقية"},
            ]
        
        # تحديد المدة المتوقعة
        if perception["total_records"] > 10000:
            plan["expected_duration"] = "long"
        elif perception["total_records"] > 1000:
            plan["expected_duration"] = "medium"
        else:
            plan["expected_duration"] = "short"
        
        logger.info(f"✅ Plan created: {len(plan['audit_steps'])} steps, duration={plan['expected_duration']}")
        return plan

    def execute(self, plan: Dict[str, Any], perception: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 3: التنفيذ - جمع وتحليل السجلات
        
        Args:
            plan: خطة التدقيق
            perception: نتائج الإدراك
            
        Returns:
            result: نتيجة التدقيق مع التقرير
        """
        logger.info(f"⚡ Executing audit plan")
        
        result = {
            "summary": None,
            "anomalies": [],
            "report": None,
            "alerts": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # تنفيذ كل خطوة
        all_records = []
        for step in plan["audit_steps"]:
            action = step["action"]
            
            try:
                if action == "collect_all_logs":
                    all_records = self._collect_all_logs(perception["available_logs"])
                    logger.info(f"   Collected {len(all_records)} records")
                
                elif action == "analyze_operations":
                    operations_summary = self._analyze_operations(all_records)
                    logger.info(f"   Analyzed operations by type: {operations_summary}")
                
                elif action == "detect_anomalies":
                    anomalies = self._detect_anomalies(all_records)
                    result["anomalies"] = anomalies
                    logger.info(f"   Detected {len(anomalies)} anomalies")
                
                elif action == "calculate_compliance":
                    compliance_score = self._calculate_compliance_score(all_records, result["anomalies"])
                    logger.info(f"   Compliance score: {compliance_score:.1%}")
                
                elif action == "generate_report":
                    summary = self._generate_summary(all_records, result["anomalies"])
                    result["summary"] = summary
                    logger.info(f"   Generated comprehensive report")
                
                elif action in ["scan_for_anomalies", "monitor_recent"]:
                    recent_records = self._get_recent_records(all_records or self._collect_all_logs(perception["available_logs"]), hours=24)
                    anomalies = self._detect_anomalies(recent_records)
                    result["anomalies"] = anomalies
                    logger.info(f"   Scanned {len(recent_records)} recent records, found {len(anomalies)} anomalies")
            
            except Exception as exc:
                logger.error(f"❌ Step '{action}' failed: {exc}")
                continue
        
        # إنشاء الملخص النهائي
        if not result["summary"]:
            result["summary"] = self._generate_summary(all_records, result["anomalies"])
        
        logger.info(f"✅ Execution complete: {result['summary'].total_operations if result['summary'] else 0} operations audited")
        return result

    def reflect(self, perception: Dict[str, Any], plan: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 4: التأمل - تقييم الشمولية والتعلم
        
        Args:
            perception: نتائج الإدراك
            plan: الخطة المنفذة
            result: نتيجة التنفيذ
            
        Returns:
            reflection: تحليل شامل مع توصيات
        """
        logger.info(f"🤔 Reflecting on audit results")
        
        reflection = {
            "decision": self._make_decision(result),
            "completeness_score": 0.0,
            "critical_findings": [],
            "recommendations": [],
            "should_escalate": False,
        }
        
        # تقييم الشمولية
        if result["summary"]:
            reflection["completeness_score"] = self._assess_completeness(perception, result)
        
        # تحليل النتائج الحرجة
        critical_anomalies = [a for a in result["anomalies"] if a.severity == "critical"]
        if critical_anomalies:
            reflection["critical_findings"] = [
                f"{a.description_ar} ({a.affected_records} سجل متأثر)"
                for a in critical_anomalies
            ]
            reflection["should_escalate"] = True
        
        # توصيات
        reflection["recommendations"] = self._generate_recommendations(result)
        
        # التعلم من الشذوذات الجديدة
        for anomaly in result["anomalies"]:
            if anomaly.severity in ["high", "critical"]:
                self._known_anomalies.append(anomaly)
        
        logger.info(f"✅ Reflection complete: decision={reflection['decision']}, completeness={reflection['completeness_score']:.1%}")
        return reflection

    # ============================================================================
    # Audit Operations Implementation
    # ============================================================================

    def _scan_available_logs(self) -> List[Path]:
        """مسح ملفات السجلات المتوفرة"""
        available = []
        for log_file in self.audit_log_files:
            path = self.logs_dir / log_file
            if path.exists():
                available.append(path)
        return available

    def _count_total_records(self, log_files: List[Path]) -> int:
        """عد إجمالي السجلات"""
        total = 0
        for path in log_files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    total += sum(1 for _ in f)
            except Exception:
                continue
        return total

    def _analyze_patterns_quick(self, log_files: List[Path]) -> Dict[str, Any]:
        """تحليل سريع للأنماط"""
        patterns = {
            "most_active_agent": None,
            "most_common_operation": None,
            "peak_activity_hour": None,
        }
        # TODO: implement pattern analysis
        return patterns

    def _assess_priority(self, perception: Dict[str, Any]) -> str:
        """تقييم مستوى الأولوية"""
        if perception["total_records"] > 5000:
            return "high"
        elif perception["total_records"] > 1000:
            return "medium"
        else:
            return "low"

    def _collect_all_logs(self, log_files: List[Path]) -> List[Dict[str, Any]]:
        """جمع كل السجلات"""
        all_records = []
        for path in log_files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            record = json.loads(line.strip())
                            record["_source_file"] = path.name
                            all_records.append(record)
                        except json.JSONDecodeError:
                            continue
            except Exception as exc:
                logger.error(f"Failed to read {path}: {exc}")
                continue
        
        # ترتيب حسب الوقت
        all_records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
        return all_records

    def _get_recent_records(self, records: List[Dict[str, Any]], hours: int = 24) -> List[Dict[str, Any]]:
        """الحصول على السجلات الأخيرة"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()
        
        return [r for r in records if r.get("timestamp", "") >= cutoff_str]

    def _analyze_operations(self, records: List[Dict[str, Any]]) -> Dict[str, int]:
        """تحليل العمليات حسب النوع"""
        operations_count = {}
        for record in records:
            op_type = record.get("action") or record.get("operation_type") or record.get("stage", "unknown")
            operations_count[op_type] = operations_count.get(op_type, 0) + 1
        return operations_count

    def _detect_anomalies(self, records: List[Dict[str, Any]]) -> List[AuditAnomaly]:
        """اكتشاف الشذوذات"""
        anomalies = []
        
        # كشف الأنماط غير المعتادة
        # TODO: implement ML-based anomaly detection
        
        # مثال بسيط: عدد كبير من الفشل
        failed_operations = [r for r in records if r.get("status") == "failed" or not r.get("success", True)]
        if len(failed_operations) > 10:
            anomalies.append(AuditAnomaly(
                anomaly_id=f"anom_{datetime.now().timestamp()}",
                anomaly_type=AnomalyType.UNUSUAL_PATTERN,
                severity="medium",
                description_ar=f"عدد كبير من العمليات الفاشلة: {len(failed_operations)}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                affected_records=len(failed_operations),
                recommended_action_ar="مراجعة أسباب الفشل وإصلاح المشاكل",
            ))
        
        return anomalies

    def _calculate_compliance_score(self, records: List[Dict[str, Any]], anomalies: List[AuditAnomaly]) -> float:
        """حساب نسبة الامتثال"""
        if not records:
            return 1.0
        
        # نسبة السجلات النظيفة
        total = len(records)
        affected = sum(a.affected_records for a in anomalies)
        clean = total - affected
        
        return clean / total if total > 0 else 1.0

    def _generate_summary(self, records: List[Dict[str, Any]], anomalies: List[AuditAnomaly]) -> AuditSummary:
        """إنشاء ملخص التدقيق"""
        operations_by_type = self._analyze_operations(records)
        
        # حساب العمليات حسب الوكيل
        operations_by_agent = {}
        for record in records:
            agent = record.get("agent") or record.get("from_agent", "unknown")
            operations_by_agent[agent] = operations_by_agent.get(agent, 0) + 1
        
        # نطاق الوقت
        timestamps = [r.get("timestamp") for r in records if r.get("timestamp")]
        time_range = (min(timestamps), max(timestamps)) if timestamps else ("", "")
        
        # نسبة الامتثال
        compliance_score = self._calculate_compliance_score(records, anomalies)
        
        return AuditSummary(
            total_operations=len(records),
            operations_by_type=operations_by_type,
            operations_by_agent=operations_by_agent,
            anomalies=anomalies,
            time_range=time_range,
            compliance_score=compliance_score,
        )

    def _assess_completeness(self, perception: Dict[str, Any], result: Dict[str, Any]) -> float:
        """تقييم شمولية التدقيق"""
        # نسبة الملفات المفحوصة
        expected_files = len(self.audit_log_files)
        scanned_files = len(perception["available_logs"])
        
        return scanned_files / expected_files if expected_files > 0 else 0.0

    def _make_decision(self, result: Dict[str, Any]) -> AuditDecision:
        """اتخاذ القرار النهائي"""
        if not result["anomalies"]:
            return AuditDecision.APPROVE_CLEAN
        
        critical_count = sum(1 for a in result["anomalies"] if a.severity == "critical")
        if critical_count > 0:
            return AuditDecision.ESCALATE_CRITICAL
        
        high_count = sum(1 for a in result["anomalies"] if a.severity == "high")
        if high_count > 3:
            return AuditDecision.REQUEST_INVESTIGATION
        
        return AuditDecision.ALERT_ANOMALIES

    def _generate_recommendations(self, result: Dict[str, Any]) -> List[str]:
        """توليد توصيات"""
        recommendations = []
        
        if not result["summary"]:
            return recommendations
        
        # توصيات حسب نسبة الامتثال
        if result["summary"].compliance_score < 0.90:
            recommendations.append("تحسين إجراءات التدقيق والمراجعة")
        
        if result["summary"].compliance_score >= 0.95:
            recommendations.append("الحفاظ على المستوى العالي من الامتثال")
        
        # توصيات حسب الشذوذات
        if len(result["anomalies"]) > 5:
            recommendations.append("مراجعة شاملة للعمليات الأخيرة")
        
        return recommendations

    # ============================================================================
    # Public API
    # ============================================================================

    def audit(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        واجهة عامة للتدقيق
        
        تستخدم الدورة الذكية الكاملة:
        Perceive → Plan → Execute → Reflect
        """
        logger.info(f"🎯 Starting audit: {request.get('scope')}")
        
        # الدورة الذكية الكاملة
        perception = self.perceive(request)
        plan = self.plan(perception)
        result = self.execute(plan, perception)
        reflection = self.reflect(perception, plan, result)
        
        # تنسيق النتيجة النهائية
        return {
            "summary": {
                "total_operations": result["summary"].total_operations if result["summary"] else 0,
                "operations_by_type": result["summary"].operations_by_type if result["summary"] else {},
                "operations_by_agent": result["summary"].operations_by_agent if result["summary"] else {},
                "compliance_score": result["summary"].compliance_score if result["summary"] else 0.0,
                "time_range": result["summary"].time_range if result["summary"] else ("", ""),
            },
            "anomalies": [
                {
                    "type": a.anomaly_type,
                    "severity": a.severity,
                    "description": a.description_ar,
                    "affected_records": a.affected_records,
                    "recommended_action": a.recommended_action_ar,
                }
                for a in result["anomalies"]
            ],
            "decision": reflection["decision"],
            "completeness_score": reflection["completeness_score"],
            "critical_findings": reflection["critical_findings"],
            "recommendations": reflection["recommendations"],
            "should_escalate": reflection["should_escalate"],
            "timestamp": result["timestamp"],
        }


# ============================================================================
# Singleton Factory
# ============================================================================

_GLOBAL_SIJIL: Optional[SijilAgent] = None


def get_sijil_agent() -> SijilAgent:
    """الحصول على كائن وكيل سجل المفرد (Singleton)"""
    global _GLOBAL_SIJIL
    if _GLOBAL_SIJIL is None:
        _GLOBAL_SIJIL = SijilAgent()
    return _GLOBAL_SIJIL
