"""
اختبارات وكيل الكتابة الذكي: كاتب (Katib Agentic Write Agent Tests)
=====================================================================
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from agents.katib_agent import (
    KatibAgent,
    WriteOperationType,
    WriteDecision,
    RollbackStrategy,
    get_katib_agent,
)


# ============================================================================
# Mock Gateways
# ============================================================================

class MockWriteGateway:
    """بوابة كتابة وهمية للاختبار"""
    
    def __init__(self):
        self.created_records = []
        self.updated_records = []
        self.archived_records = []
    
    def create_employee(self, values: Dict[str, Any], context=None) -> int:
        """محاكاة إنشاء موظف"""
        new_id = len(self.created_records) + 100
        self.created_records.append({"id": new_id, "values": values})
        return new_id
    
    def write_employee(self, employee_id: int, values: Dict[str, Any], context=None) -> bool:
        """محاكاة تعديل موظف"""
        self.updated_records.append({"id": employee_id, "values": values})
        return True
    
    def write_record(self, model: str, record_id: int, values: Dict[str, Any], context=None) -> bool:
        """محاكاة تعديل سجل"""
        if values.get("active") is False:
            self.archived_records.append({"model": model, "id": record_id})
        return True
    
    def create_record(self, model: str, values: Dict[str, Any], context=None) -> int:
        """محاكاة إنشاء سجل عام"""
        new_id = len(self.created_records) + 100
        self.created_records.append({"model": model, "id": new_id, "values": values})
        return new_id


class MockDeleteGateway:
    """بوابة حذف وهمية للاختبار"""
    
    def __init__(self):
        self.deleted_records = []
    
    def delete_single_record(self, model: str, record_id: int) -> bool:
        """محاكاة حذف سجل"""
        self.deleted_records.append({"model": model, "id": record_id})
        return True


# ============================================================================
# Test Cases
# ============================================================================

def test_katib_perceive_create_operation():
    """اختبار مرحلة الإدراك لعملية إنشاء"""
    print("\n" + "="*70)
    print("TEST 1: Perceive - Create Operation")
    print("="*70)
    
    mock_gateway = MockWriteGateway()
    agent = KatibAgent(gateway=mock_gateway)
    
    # طلب إنشاء موظف جديد
    action_request = {
        "action_type": "create",
        "model": "hr.employee",
        "values": {
            "name": "أحمد محمد",
            "work_email": "ahmed@example.com",
        }
    }
    
    perception = agent.perceive(action_request)
    
    # التحقق من النتائج
    assert perception["operation_type"] == "create"
    assert perception["model"] == "hr.employee"
    assert perception["eligibility"]["status"] == "eligible"
    assert perception["safety_analysis"]["level"] == "safe"
    
    print(f"✅ Operation Type: {perception['operation_type']}")
    print(f"✅ Model: {perception['model']}")
    print(f"✅ Eligibility: {perception['eligibility']['status']}")
    print(f"✅ Safety Level: {perception['safety_analysis']['level']}")
    print("\n✅ TEST PASSED: Perceive correctly analyzed CREATE operation")


def test_katib_perceive_dangerous_operation():
    """اختبار مرحلة الإدراك لعملية خطرة (حذف)"""
    print("\n" + "="*70)
    print("TEST 2: Perceive - Dangerous DELETE Operation")
    print("="*70)
    
    mock_gateway = MockWriteGateway()
    mock_delete_gateway = MockDeleteGateway()
    agent = KatibAgent(gateway=mock_gateway, delete_gateway=mock_delete_gateway)
    
    # طلب حذف موظف
    action_request = {
        "action_type": "delete",
        "model": "hr.employee",
        "record_id": 42,
    }
    
    perception = agent.perceive(action_request)
    
    # التحقق من النتائج
    assert perception["operation_type"] == "delete"
    assert perception["safety_analysis"]["level"] == "danger"
    assert perception["safety_analysis"]["requires_approval"] is True
    assert not perception["impact_analysis"]["reversible"]
    
    print(f"✅ Operation Type: {perception['operation_type']}")
    print(f"✅ Safety Level: {perception['safety_analysis']['level']}")
    print(f"✅ Requires Approval: {perception['safety_analysis']['requires_approval']}")
    print(f"✅ Reversible: {perception['impact_analysis']['reversible']}")
    print("\n✅ TEST PASSED: Perceive correctly identified DANGEROUS operation")


def test_katib_plan_safe_operation():
    """اختبار مرحلة التخطيط لعملية آمنة"""
    print("\n" + "="*70)
    print("TEST 3: Plan - Safe Operation")
    print("="*70)
    
    mock_gateway = MockWriteGateway()
    agent = KatibAgent(gateway=mock_gateway)
    
    # إنشاء perception لعملية آمنة
    action_request = {
        "action_type": "update",
        "model": "hr.employee",
        "record_id": 10,
        "values": {"work_phone": "+966501234567"}
    }
    
    perception = agent.perceive(action_request)
    plan = agent.plan(perception)
    
    # التحقق من النتائج
    assert plan["decision"] == WriteDecision.EXECUTE_IMMEDIATE
    assert len(plan["steps"]) > 0
    assert plan["rollback_strategy"] == RollbackStrategy.REVERT_VALUES
    
    print(f"✅ Decision: {plan['decision']}")
    print(f"✅ Steps Count: {len(plan['steps'])}")
    print(f"✅ Rollback Strategy: {plan['rollback_strategy']}")
    print(f"✅ Safeguards: {plan['safeguards']}")
    print("\n✅ TEST PASSED: Plan created for SAFE operation")


def test_katib_plan_dangerous_operation():
    """اختبار مرحلة التخطيط لعملية خطرة"""
    print("\n" + "="*70)
    print("TEST 4: Plan - Dangerous Operation Requires Approval")
    print("="*70)
    
    mock_gateway = MockWriteGateway()
    mock_delete_gateway = MockDeleteGateway()
    agent = KatibAgent(gateway=mock_gateway, delete_gateway=mock_delete_gateway)
    
    # إنشاء perception لعملية خطرة
    action_request = {
        "action_type": "delete",
        "model": "hr.employee",
        "record_id": 99,
    }
    
    perception = agent.perceive(action_request)
    plan = agent.plan(perception)
    
    # التحقق من النتائج
    assert plan["decision"] == WriteDecision.REQUEST_APPROVAL
    assert plan["steps"][0]["action"] == "request_human_approval"
    
    print(f"✅ Decision: {plan['decision']}")
    print(f"✅ First Step: {plan['steps'][0]['action']}")
    print(f"✅ Reason: {plan['steps'][0]['reason']}")
    print("\n✅ TEST PASSED: Dangerous operation requires approval")


def test_katib_execute_create_operation():
    """اختبار تنفيذ عملية إنشاء"""
    print("\n" + "="*70)
    print("TEST 5: Execute - CREATE Employee")
    print("="*70)
    
    mock_gateway = MockWriteGateway()
    agent = KatibAgent(gateway=mock_gateway)
    
    # دورة كاملة: Perceive → Plan → Execute
    action_request = {
        "action_type": "create",
        "model": "hr.employee",
        "values": {
            "name": "فاطمة أحمد",
            "work_email": "fatima@example.com",
        }
    }
    
    perception = agent.perceive(action_request)
    plan = agent.plan(perception)
    result = agent.execute(plan)
    
    # التحقق من النتائج
    assert result["success"] is True
    assert "record_id" in result
    assert len(mock_gateway.created_records) == 1
    assert mock_gateway.created_records[0]["values"]["name"] == "فاطمة أحمد"
    
    print(f"✅ Success: {result['success']}")
    print(f"✅ Record ID: {result.get('record_id')}")
    print(f"✅ Executed Steps: {result['executed_steps']}")
    print(f"✅ Created Records: {len(mock_gateway.created_records)}")
    print("\n✅ TEST PASSED: CREATE operation executed successfully")


def test_katib_execute_update_operation():
    """اختبار تنفيذ عملية تعديل"""
    print("\n" + "="*70)
    print("TEST 6: Execute - UPDATE Employee")
    print("="*70)
    
    mock_gateway = MockWriteGateway()
    agent = KatibAgent(gateway=mock_gateway)
    
    # دورة كاملة: Perceive → Plan → Execute
    action_request = {
        "action_type": "update",
        "model": "hr.employee",
        "record_id": 50,
        "values": {
            "mobile_phone": "+966551234567",
        }
    }
    
    perception = agent.perceive(action_request)
    plan = agent.plan(perception)
    result = agent.execute(plan)
    
    # التحقق من النتائج
    assert result["success"] is True
    assert result["record_id"] == 50
    assert len(mock_gateway.updated_records) == 1
    
    print(f"✅ Success: {result['success']}")
    print(f"✅ Record ID: {result['record_id']}")
    print(f"✅ Updated Records: {len(mock_gateway.updated_records)}")
    print(f"✅ Executed Steps: {result['executed_steps']}")
    print("\n✅ TEST PASSED: UPDATE operation executed successfully")


def test_katib_reflect_successful_operation():
    """اختبار مرحلة التأمل بعد عملية ناجحة"""
    print("\n" + "="*70)
    print("TEST 7: Reflect - Successful Operation")
    print("="*70)
    
    mock_gateway = MockWriteGateway()
    agent = KatibAgent(gateway=mock_gateway)
    
    # دورة كاملة مع Reflection
    action_request = {
        "action_type": "create",
        "model": "hr.employee",
        "values": {"name": "محمد علي", "work_email": "mohamed@example.com"}
    }
    
    perception = agent.perceive(action_request)
    plan = agent.plan(perception)
    result = agent.execute(plan)
    reflection = agent.reflect(perception, plan, result)
    
    # التحقق من النتائج
    assert reflection["execution_success"] is True
    assert reflection["confidence_score"] > 0.8
    assert len(reflection["lessons_learned"]) > 0
    
    print(f"✅ Execution Success: {reflection['execution_success']}")
    print(f"✅ Confidence Score: {reflection['confidence_score']:.2f}")
    print(f"✅ Lessons Learned: {reflection['lessons_learned']}")
    print(f"✅ Recommendations: {reflection['recommendations']}")
    print("\n✅ TEST PASSED: Reflection completed for successful operation")


def test_katib_full_agentic_loop():
    """اختبار الدورة الذكية الكاملة"""
    print("\n" + "="*70)
    print("TEST 8: Full Agentic Loop (Perceive→Plan→Execute→Reflect)")
    print("="*70)
    
    mock_gateway = MockWriteGateway()
    agent = KatibAgent(gateway=mock_gateway)
    
    # طلب تعديل بيانات حساسة (salary)
    action_request = {
        "action_type": "update",
        "model": "hr.employee",
        "record_id": 30,
        "values": {
            "salary": 15000.0,  # حقل حساس
        }
    }
    
    # الدورة الكاملة
    print("\n🔍 Phase 1: PERCEIVE")
    perception = agent.perceive(action_request)
    print(f"   Safety Level: {perception['safety_analysis']['level']}")
    print(f"   Concerns: {perception['safety_analysis']['concerns']}")
    
    print("\n📋 Phase 2: PLAN")
    plan = agent.plan(perception)
    print(f"   Decision: {plan['decision']}")
    print(f"   Rollback Strategy: {plan['rollback_strategy']}")
    
    print("\n⚡ Phase 3: EXECUTE")
    result = agent.execute(plan)
    print(f"   Success: {result['success']}")
    print(f"   Steps Executed: {len(result['executed_steps'])}")
    
    print("\n🤔 Phase 4: REFLECT")
    reflection = agent.reflect(perception, plan, result)
    print(f"   Confidence Score: {reflection['confidence_score']:.2f}")
    print(f"   Improvements: {reflection['improvements']}")
    
    # التحقق النهائي
    assert perception["safety_analysis"]["level"] == "caution"  # بيانات حساسة
    assert plan["decision"] == WriteDecision.EXECUTE_WITH_BACKUP
    assert result["success"] is True
    assert reflection["confidence_score"] > 0.8
    
    print("\n✅ TEST PASSED: Full Agentic Loop completed successfully")


def test_katib_backward_compatibility():
    """اختبار التوافق مع الواجهة القديمة"""
    print("\n" + "="*70)
    print("TEST 9: Backward Compatibility (execute_approved_action)")
    print("="*70)
    
    mock_gateway = MockWriteGateway()
    agent = KatibAgent(gateway=mock_gateway)
    
    # استخدام الواجهة القديمة
    action = {
        "action_type": "create",
        "values": {
            "name": "خالد عبدالله",
            "work_email": "khaled@example.com"
        }
    }
    
    result = agent.execute_approved_action(action)
    
    # التحقق من التوافق
    assert result["ok"] is True
    assert "record_id" in result
    assert "reflection" in result
    assert result["action"] == "create"
    
    print(f"✅ OK: {result['ok']}")
    print(f"✅ Record ID: {result['record_id']}")
    print(f"✅ Action: {result['action']}")
    print(f"✅ Has Reflection: {'reflection' in result}")
    print("\n✅ TEST PASSED: Backward compatibility maintained")


def test_katib_singleton():
    """اختبار Singleton Factory"""
    print("\n" + "="*70)
    print("TEST 10: Singleton Factory Pattern")
    print("="*70)
    
    agent1 = get_katib_agent()
    agent2 = get_katib_agent()
    
    assert agent1 is agent2
    assert agent1.name == agent2.name
    
    print(f"✅ Agent 1 Name: {agent1.name}")
    print(f"✅ Agent 2 Name: {agent2.name}")
    print(f"✅ Same Instance: {agent1 is agent2}")
    print("\n✅ TEST PASSED: Singleton pattern working correctly")


# ============================================================================
# Run All Tests
# ============================================================================

def run_all_tests():
    """تشغيل جميع الاختبارات"""
    print("\n" + "="*70)
    print("KATIB AGENT - AGENTIC AI TESTS")
    print("="*70)
    
    tests = [
        test_katib_perceive_create_operation,
        test_katib_perceive_dangerous_operation,
        test_katib_plan_safe_operation,
        test_katib_plan_dangerous_operation,
        test_katib_execute_create_operation,
        test_katib_execute_update_operation,
        test_katib_reflect_successful_operation,
        test_katib_full_agentic_loop,
        test_katib_backward_compatibility,
        test_katib_singleton,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as exc:
            print(f"\n❌ TEST FAILED: {test_func.__name__}")
            print(f"   Error: {exc}")
            failed += 1
        except Exception as exc:
            print(f"\n❌ TEST ERROR: {test_func.__name__}")
            print(f"   Error: {exc}")
            failed += 1
    
    # النتيجة النهائية
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! KatibAgent is fully functional!")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review.")
    
    print("="*70)


if __name__ == "__main__":
    run_all_tests()
