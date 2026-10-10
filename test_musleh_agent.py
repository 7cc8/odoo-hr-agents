#!/usr/bin/env python3
"""
Test MuslehAgent - اختبار وكيل التشخيص
========================================
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from agents.musleh_agent import (
    MuslehAgent,
    create_musleh_diagnostic_goal,
    DECISION_APPLY_AUTO_PATCH,
    DECISION_ESCALATE,
    DECISION_QUARANTINE,
)

logger = logging.getLogger("test_musleh")


def test_basic_diagnosis():
    """اختبار التشخيص الأساسي"""
    print("\n" + "="*60)
    print("TEST 1: Basic Diagnosis")
    print("="*60)
    
    # إنشاء صف مُعطوب بسيط
    problematic_row = {
        "excel_row_number": 10,
        "fields": {
            "name": {"value": "أحمد محمد"},
            "company": {"value": "شركة النخبة"},
            "department": {"value": "IT Deprtment"},  # خطأ إملائي
            "job": {"value": "مطور"},
            "work_email": {"value": "ahmed@company.com"},
        }
    }
    
    validation_result = {
        "final_status": "needs_review",
        "failure_code": "reference_not_found",
        "reasons": ["Department 'IT Deprtment' not found in Odoo"],
    }
    
    # إنشاء الهدف
    goal = create_musleh_diagnostic_goal(
        description="تشخيص مشكلة قسم غير موجود",
        row=problematic_row,
        validation_result=validation_result,
        context={
            "live_snapshot": {
                "companies": [{"id": 1, "name": "شركة النخبة"}],
                "departments": [
                    {"id": 10, "name": "IT Department", "company_id": [1]},
                    {"id": 11, "name": "HR Department", "company_id": [1]},
                ],
                "jobs": [],
            }
        }
    )
    
    # تشغيل الوكيل
    musleh = MuslehAgent(auto_repair=False)
    result = musleh.run(goal)
    
    # عرض النتائج
    print(f"\n✅ Status: {result['status']}")
    print(f"✅ Iterations: {result['iterations']}")
    print(f"✅ Duration: {result.get('duration_seconds', 0):.2f}s")
    
    if result['status'] == 'success':
        decision = result['result'].get('decision')
        confidence = result['result'].get('confidence', 0)
        
        print(f"\n📋 Decision: {decision}")
        print(f"📊 Confidence: {confidence:.0%}")
        
        if decision == DECISION_APPLY_AUTO_PATCH:
            patches = result['result'].get('patches', {})
            print(f"🔧 Patches: {patches}")
        elif decision == DECISION_ESCALATE:
            print(f"⚠️  Needs human review")
    
    return result['status'] == 'success'


def test_identity_issue():
    """اختبار مشكلة هوية مكررة (خط أحمر)"""
    print("\n" + "="*60)
    print("TEST 2: Identity Issue (Red Line)")
    print("="*60)
    
    problematic_row = {
        "excel_row_number": 15,
        "fields": {
            "name": {"value": "محمد أحمد"},
            "company": {"value": "شركة النخبة"},
            "department": {"value": "IT"},
            "job": {"value": "مطور"},
            "work_email": {"value": "mohamed@company.com"},
        }
    }
    
    validation_result = {
        "final_status": "rejected",
        "failure_code": "duplicate_existing_employee",
        "reasons": ["Employee with similar identity already exists"],
    }
    
    goal = create_musleh_diagnostic_goal(
        description="تشخيص هوية مكررة",
        row=problematic_row,
        validation_result=validation_result,
    )
    
    musleh = MuslehAgent(auto_repair=True)  # حتى مع auto_repair=True
    result = musleh.run(goal)
    
    print(f"\n✅ Status: {result['status']}")
    
    if result['status'] == 'success':
        decision = result['result'].get('decision')
        print(f"📋 Decision: {decision}")
        
        # يجب أن يكون ESCALATE (خط أحمر)
        if decision == DECISION_ESCALATE:
            print(f"✅ CORRECT: Identity issues escalated (Red Line)")
            escalation = result['result'].get('escalation', {})
            print(f"⚠️  Reason: {escalation.get('reason')}")
            print(f"🔴 Red Line: {escalation.get('red_line')}")
            return True
        else:
            print(f"❌ WRONG: Should escalate identity issues!")
            return False
    
    return False


def test_auto_repair():
    """اختبار الإصلاح التلقائي"""
    print("\n" + "="*60)
    print("TEST 3: Auto Repair (High Confidence)")
    print("="*60)
    
    problematic_row = {
        "excel_row_number": 20,
        "fields": {
            "name": {"value": "سارة علي"},
            "company": {"value": "شركة النخبة"},
            "department": {"value": "IT Department"},
            "job": {"value": "مطور"},
            "work_email": {"value": "sara@company.com"},
        }
    }
    
    validation_result = {
        "final_status": "needs_review",
        "failure_code": "minor_formatting_issue",
        "reasons": ["Minor data formatting issue"],
    }
    
    goal = create_musleh_diagnostic_goal(
        description="إصلاح تنسيق بسيط",
        row=problematic_row,
        validation_result=validation_result,
    )
    
    musleh = MuslehAgent(auto_repair=True)
    result = musleh.run(goal)
    
    print(f"\n✅ Status: {result['status']}")
    
    if result['status'] == 'success':
        decision = result['result'].get('decision')
        confidence = result['result'].get('confidence', 0)
        
        print(f"📋 Decision: {decision}")
        print(f"📊 Confidence: {confidence:.0%}")
        
        # Note: قد لا يُصلح لأننا لم نُنفّذ fuzzy matching كامل بعد
        print(f"ℹ️  Note: Full auto-repair requires complete implementation")
    
    return result['status'] == 'success'


def main():
    """Main test runner"""
    print("\n" + "🚀"*30)
    print("MUSLEH AGENT TESTING")
    print("🚀"*30)
    
    results = {}
    
    try:
        results['basic_diagnosis'] = test_basic_diagnosis()
    except Exception as e:
        logger.error(f"Basic diagnosis test failed: {e}", exc_info=True)
        results['basic_diagnosis'] = False
    
    try:
        results['identity_issue'] = test_identity_issue()
    except Exception as e:
        logger.error(f"Identity issue test failed: {e}", exc_info=True)
        results['identity_issue'] = False
    
    try:
        results['auto_repair'] = test_auto_repair()
    except Exception as e:
        logger.error(f"Auto repair test failed: {e}", exc_info=True)
        results['auto_repair'] = False
    
    # النتيجة النهائية
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    
    print("\n" + "="*60)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("="*60)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
