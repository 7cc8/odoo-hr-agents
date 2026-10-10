"""
اختبارات سجل (Sijil) Agent - التدقيق الذكي
============================================

يختبر:
1. Perceive: تحليل السجلات المتاحة
2. Plan: استراتيجية التدقيق (comprehensive/focused/quick)
3. Execute: جمع وتحليل من 12+ مصدر JSONL
4. Reflect: تقييم الشمولية + توصيات
5. كشف الشذوذ (Anomaly detection)
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta

# إضافة المسار
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.sijil_agent import SijilAgent, AuditScope, AnomalyType, AuditDecision


def create_temp_logs(temp_dir: Path) -> None:
    """إنشاء سجلات مؤقتة للاختبار"""
    
    # سجل كاتب (write operations)
    katib_log = temp_dir / "katib_audit.jsonl"
    with open(katib_log, "w", encoding="utf-8") as f:
        for i in range(5):
            record = {
                "timestamp": (datetime.now() - timedelta(hours=i)).isoformat(),
                "agent": "katib",
                "operation": "create" if i % 2 == 0 else "update",
                "record_id": f"emp_{100+i}",
                "user": "admin",
                "success": True,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    # سجل حارس (security decisions)
    hares_log = temp_dir / "hares_security.jsonl"
    with open(hares_log, "w", encoding="utf-8") as f:
        for i in range(3):
            record = {
                "timestamp": (datetime.now() - timedelta(hours=i*2)).isoformat(),
                "agent": "hares",
                "decision": "approve" if i < 2 else "reject",
                "risk_level": "medium",
                "user": "manager",
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    # سجل مدقق (compliance checks)
    mudaqqiq_log = temp_dir / "mudaqqiq_compliance.jsonl"
    with open(mudaqqiq_log, "w", encoding="utf-8") as f:
        for i in range(4):
            record = {
                "timestamp": (datetime.now() - timedelta(hours=i*3)).isoformat(),
                "agent": "mudaqqiq",
                "decision": "approve",
                "violations": [],
                "confidence": 0.95,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def test_perceive_comprehensive_audit():
    """
    اختبار 1: perceive - تدقيق شامل
    
    يجب أن يكتشف جميع السجلات المتاحة
    """
    print("\n" + "="*80)
    print("🧪 اختبار 1: Perceive - تدقيق شامل")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        create_temp_logs(temp_path)
        
        agent = SijilAgent(logs_dir=temp_path)
        
        request = {
            "scope": "comprehensive",
            "focus_areas": [],
            "time_range": None,
        }
        
        perception = agent.perceive(request)
        
        # التحقق من النتائج
        assert "scope" in perception, "❌ Scope مفقود"
        assert "available_logs" in perception, "❌ Available logs مفقودة"
        assert "estimated_records" in perception, "❌ Estimated records مفقود"
        
        print(f"\n✅ Scope: {perception['scope']}")
        print(f"✅ Available logs: {len(perception['available_logs'])}")
        print(f"✅ Estimated records: {perception['estimated_records']}")
        print(f"✅ Priority: {perception['priority']}")
        
        # يجب أن يجد 3 سجلات على الأقل
        assert len(perception["available_logs"]) >= 3, "❌ يجب أن يجد 3 سجلات على الأقل"
        
        print("\n✅ اختبار 1 نجح!")


def test_plan_focused_audit():
    """
    اختبار 2: plan - تدقيق مُركّز
    
    التركيز على أمان + امتثال فقط
    """
    print("\n" + "="*80)
    print("🧪 اختبار 2: Plan - تدقيق مركّز")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        create_temp_logs(temp_path)
        
        agent = SijilAgent(logs_dir=temp_path)
        
        perception = {
            "scope": AuditScope.FOCUSED,
            "focus_areas": ["security", "compliance"],
            "available_logs": [
                temp_path / "hares_security.jsonl",
                temp_path / "mudaqqiq_compliance.jsonl",
                temp_path / "katib_audit.jsonl",
            ],
            "estimated_records": 12,
            "priority": "medium",
        }
        
        plan = agent.plan(perception)
        
        # التحقق من الخطة
        assert "log_files" in plan, "❌ Log files مفقودة"
        assert "analysis_depth" in plan, "❌ Analysis depth مفقود"
        assert "anomaly_detection" in plan, "❌ Anomaly detection مفقود"
        
        print(f"\n✅ Log files to analyze: {len(plan['log_files'])}")
        print(f"✅ Analysis depth: {plan['analysis_depth']}")
        print(f"✅ Anomaly detection: {plan['anomaly_detection']}")
        
        # يجب أن يحلل السجلات المطلوبة فقط
        log_names = [f.name for f in plan["log_files"]]
        assert "hares_security.jsonl" in log_names, "❌ يجب أن يتضمن hares"
        assert "mudaqqiq_compliance.jsonl" in log_names, "❌ يجب أن يتضمن mudaqqiq"
        
        print("\n✅ اختبار 2 نجح!")


def test_execute_collect_logs():
    """
    اختبار 3: execute - جمع وتحليل السجلات
    
    يجب أن يجمع جميع السجلات ويحللها
    """
    print("\n" + "="*80)
    print("🧪 اختبار 3: Execute - جمع السجلات")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        create_temp_logs(temp_path)
        
        agent = SijilAgent(logs_dir=temp_path)
        
        perception = {
            "scope": AuditScope.COMPREHENSIVE,
            "available_logs": list(temp_path.glob("*.jsonl")),
        }
        
        plan = {
            "log_files": list(temp_path.glob("*.jsonl")),
            "analysis_depth": "full",
            "anomaly_detection": True,
            "time_filter": None,
        }
        
        result = agent.execute(plan, perception)
        
        # التحقق من النتائج
        assert "records_analyzed" in result, "❌ Records analyzed مفقود"
        assert "operations" in result, "❌ Operations مفقود"
        assert "anomalies" in result, "❌ Anomalies مفقودة"
        assert "summary" in result, "❌ Summary مفقود"
        
        print(f"\n✅ Records analyzed: {result['records_analyzed']}")
        print(f"✅ Operations: {result['operations']}")
        print(f"✅ Anomalies found: {len(result['anomalies'])}")
        print(f"✅ Compliance score: {result['summary'].compliance_score:.0%}")
        
        # يجب أن يجد سجلات
        assert result["records_analyzed"] > 0, "❌ لم يحلل أي سجلات"
        
        print("\n✅ اختبار 3 نجح!")


def test_detect_anomalies():
    """
    اختبار 4: كشف الشذوذات
    
    إضافة شذوذات مقصودة ليكتشفها
    """
    print("\n" + "="*80)
    print("🧪 اختبار 4: كشف الشذوذات")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # إنشاء سجل مع شذوذ (عمليات كثيرة من نفس المستخدم)
        log_file = temp_path / "anomaly_test.jsonl"
        with open(log_file, "w", encoding="utf-8") as f:
            # 20 عملية من نفس المستخدم في ساعة واحدة (شاذ!)
            for i in range(20):
                record = {
                    "timestamp": (datetime.now() - timedelta(minutes=i*2)).isoformat(),
                    "agent": "katib",
                    "operation": "delete",  # عمليات حذف كثيرة (شاذ!)
                    "user": "suspicious_user",
                    "success": True,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        
        agent = SijilAgent(logs_dir=temp_path)
        
        perception = {
            "scope": AuditScope.COMPREHENSIVE,
            "available_logs": [log_file],
        }
        
        plan = {
            "log_files": [log_file],
            "analysis_depth": "full",
            "anomaly_detection": True,
            "time_filter": None,
        }
        
        result = agent.execute(plan, perception)
        
        print(f"\n✅ Anomalies detected: {len(result['anomalies'])}")
        
        for anomaly in result["anomalies"][:3]:  # أول 3 فقط
            print(f"\n  🚨 Anomaly:")
            print(f"     Type: {anomaly.anomaly_type}")
            print(f"     Severity: {anomaly.severity}")
            print(f"     Description: {anomaly.description}")
        
        # يجب أن يكتشف شذوذات
        assert len(result["anomalies"]) > 0, "❌ لم يكتشف الشذوذات المقصودة"
        
        # يجب أن يكتشف HIGH_FREQUENCY أو SUSPICIOUS_PATTERN
        types = [a.anomaly_type for a in result["anomalies"]]
        assert AnomalyType.HIGH_FREQUENCY in types or AnomalyType.SUSPICIOUS_PATTERN in types, \
            "❌ لم يكتشف النوع الصحيح من الشذوذ"
        
        print("\n✅ اختبار 4 نجح!")


def test_reflect_high_compliance():
    """
    اختبار 5: reflect - امتثال عالي
    
    نظام سليم يجب أن يحصل على APPROVE
    """
    print("\n" + "="*80)
    print("🧪 اختبار 5: Reflect - امتثال عالي")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        create_temp_logs(temp_path)
        
        agent = SijilAgent(logs_dir=temp_path)
        
        from agents.sijil_agent import AuditSummary
        
        perception = {"scope": AuditScope.COMPREHENSIVE}
        plan = {"analysis_depth": "full"}
        result = {
            "records_analyzed": 12,
            "anomalies": [],  # لا توجد شذوذات
            "summary": AuditSummary(
                total_records=12,
                time_range=("2024-01-01", "2024-01-02"),
                operations={"create": 5, "update": 5, "delete": 2},
                compliance_score=0.95,  # امتثال عالي
                critical_findings=[],
            ),
        }
        
        reflection = agent.reflect(perception, plan, result)
        
        # التحقق من القرار
        assert "decision" in reflection, "❌ Decision مفقود"
        assert "completeness" in reflection, "❌ Completeness مفقود"
        assert "recommendations" in reflection, "❌ Recommendations مفقودة"
        
        print(f"\n✅ Decision: {reflection['decision'].value}")
        print(f"✅ Completeness: {reflection['completeness']:.0%}")
        print(f"✅ Recommendations: {len(reflection['recommendations'])}")
        
        # يجب أن يوافق على النظام السليم
        assert reflection["decision"] in [AuditDecision.APPROVE, AuditDecision.MONITOR], \
            f"❌ متوقع APPROVE أو MONITOR، وجدنا {reflection['decision']}"
        
        print("\n✅ اختبار 5 نجح!")


def test_reflect_critical_findings():
    """
    اختبار 6: reflect - نتائج حرجة
    
    شذوذات خطيرة يجب أن تعطي ESCALATE
    """
    print("\n" + "="*80)
    print("🧪 اختبار 6: Reflect - نتائج حرجة")
    print("="*80)
    
    agent = SijilAgent()
    
    from agents.sijil_agent import AuditSummary, AuditAnomaly
    
    perception = {"scope": AuditScope.COMPREHENSIVE}
    plan = {"analysis_depth": "full"}
    result = {
        "records_analyzed": 50,
        "anomalies": [
            AuditAnomaly(
                anomaly_type=AnomalyType.UNAUTHORIZED_ACCESS,
                severity="critical",
                description="Unauthorized access attempt detected",
                timestamp=datetime.now().isoformat(),
                affected_records=["emp_123"],
            ),
        ],
        "summary": AuditSummary(
            total_records=50,
            time_range=("2024-01-01", "2024-01-02"),
            operations={"delete": 30, "update": 20},  # حذف كثير (مريب!)
            compliance_score=0.45,  # امتثال منخفض
            critical_findings=["unauthorized_access"],
        ),
    }
    
    reflection = agent.reflect(perception, plan, result)
    
    print(f"\n✅ Decision: {reflection['decision'].value}")
    print(f"✅ Should escalate: {reflection.get('should_escalate', False)}")
    print(f"✅ Recommendations: {len(reflection['recommendations'])}")
    
    # يجب التصعيد
    assert reflection["decision"] == AuditDecision.ESCALATE, \
        f"❌ متوقع ESCALATE مع نتائج حرجة، وجدنا {reflection['decision']}"
    
    assert reflection.get("should_escalate", False), "❌ يجب أن يوصي بالتصعيد"
    
    print("\n✅ اختبار 6 نجح!")


def test_audit_api():
    """
    اختبار 7: audit() - الواجهة العامة
    
    اختبار الدورة الكاملة من خلال الـ API العام
    """
    print("\n" + "="*80)
    print("🧪 اختبار 7: audit() API")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        create_temp_logs(temp_path)
        
        agent = SijilAgent(logs_dir=temp_path)
        
        request = {
            "scope": "comprehensive",
            "focus_areas": [],
            "time_range": None,
        }
        
        result = agent.audit(request)
        
        # التحقق من النتائج
        assert "status" in result, "❌ Status مفقود"
        assert "decision" in result, "❌ Decision مفقود"
        assert "summary" in result, "❌ Summary مفقود"
        
        print(f"\n✅ Status: {result['status']}")
        print(f"✅ Decision: {result['decision']}")
        print(f"✅ Records analyzed: {result['summary']['total_records']}")
        print(f"✅ Compliance score: {result['summary']['compliance_score']:.0%}")
        print(f"✅ Anomalies: {len(result.get('anomalies', []))}")
        
        # يجب أن ينجح
        assert result["status"] == "completed", "❌ يجب أن ينجح التدقيق"
        
        print("\n✅ اختبار 7 نجح!")


def test_time_range_filter():
    """
    اختبار 8: تصفية بالوقت
    
    تدقيق آخر 24 ساعة فقط
    """
    print("\n" + "="*80)
    print("🧪 اختبار 8: تصفية بالوقت")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # إنشاء سجلات قديمة وجديدة
        log_file = temp_path / "time_test.jsonl"
        with open(log_file, "w", encoding="utf-8") as f:
            # 5 سجلات قديمة (قبل 48 ساعة)
            for i in range(5):
                record = {
                    "timestamp": (datetime.now() - timedelta(hours=48+i)).isoformat(),
                    "agent": "katib",
                    "operation": "update",
                    "old": True,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            
            # 3 سجلات جديدة (آخر 12 ساعة)
            for i in range(3):
                record = {
                    "timestamp": (datetime.now() - timedelta(hours=i*4)).isoformat(),
                    "agent": "katib",
                    "operation": "create",
                    "new": True,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        
        agent = SijilAgent(logs_dir=temp_path)
        
        # تدقيق آخر 24 ساعة فقط
        request = {
            "scope": "comprehensive",
            "time_range": 24,  # hours
        }
        
        result = agent.audit(request)
        
        print(f"\n✅ Records analyzed: {result['summary']['total_records']}")
        
        # يجب أن يحلل 3 سجلات فقط (الجديدة)
        assert result['summary']['total_records'] == 3, \
            f"❌ متوقع 3 سجلات (الجديدة)، وجدنا {result['summary']['total_records']}"
        
        print("\n✅ اختبار 8 نجح!")


def test_quick_audit():
    """
    اختبار 9: تدقيق سريع
    
    نظرة عامة بدون تحليل عميق
    """
    print("\n" + "="*80)
    print("🧪 اختبار 9: تدقيق سريع")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        create_temp_logs(temp_path)
        
        agent = SijilAgent(logs_dir=temp_path)
        
        request = {
            "scope": "quick",
        }
        
        result = agent.audit(request)
        
        print(f"\n✅ Status: {result['status']}")
        print(f"✅ Records analyzed: {result['summary']['total_records']}")
        print(f"✅ Analysis was: Quick overview")
        
        # يجب أن ينجح بسرعة
        assert result["status"] == "completed", "❌ يجب أن ينجح التدقيق السريع"
        
        print("\n✅ اختبار 9 نجح!")


def test_compliance_recommendations():
    """
    اختبار 10: توصيات الامتثال
    
    يجب أن يقدم توصيات مفيدة
    """
    print("\n" + "="*80)
    print("🧪 اختبار 10: توصيات الامتثال")
    print("="*80)
    
    agent = SijilAgent()
    
    from agents.sijil_agent import AuditSummary, AuditAnomaly
    
    perception = {"scope": AuditScope.COMPREHENSIVE}
    plan = {"analysis_depth": "full"}
    result = {
        "records_analyzed": 100,
        "anomalies": [
            AuditAnomaly(
                AnomalyType.MISSING_AUDIT,
                "medium",
                "Some operations not logged",
                datetime.now().isoformat(),
                []
            ),
        ],
        "summary": AuditSummary(
            total_records=100,
            time_range=("2024-01-01", "2024-01-02"),
            operations={"create": 50, "update": 40, "delete": 10},
            compliance_score=0.75,
            critical_findings=[],
        ),
    }
    
    reflection = agent.reflect(perception, plan, result)
    
    recommendations = reflection.get("recommendations", [])
    
    print(f"\n✅ Recommendations ({len(recommendations)}):")
    for i, rec in enumerate(recommendations[:5], 1):  # أول 5
        print(f"  {i}. {rec}")
    
    # يجب أن يكون هناك توصيات
    assert len(recommendations) > 0, "❌ يجب أن يقدم توصيات"
    
    print("\n✅ اختبار 10 نجح!")


def run_all_tests():
    """تشغيل جميع الاختبارات"""
    print("\n" + "="*80)
    print("🚀 تشغيل جميع اختبارات SijilAgent")
    print("="*80)
    
    tests = [
        test_perceive_comprehensive_audit,
        test_plan_focused_audit,
        test_execute_collect_logs,
        test_detect_anomalies,
        test_reflect_high_compliance,
        test_reflect_critical_findings,
        test_audit_api,
        test_time_range_filter,
        test_quick_audit,
        test_compliance_recommendations,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n❌ فشل الاختبار: {test.__name__}")
            print(f"   الخطأ: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*80)
    print(f"📊 النتائج: {passed} نجح، {failed} فشل من أصل {len(tests)}")
    print("="*80)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
