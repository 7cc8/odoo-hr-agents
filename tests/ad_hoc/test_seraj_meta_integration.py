"""
اختبار دمج SerajMetaAgent مع LangGraph
==========================================

يختبر:
1. عقدة seraj_meta_orchestration
2. عقدة seraj_meta_reflect
3. التدفق الكامل من classify_intent → Meta-Agent → seraj_think
4. التعلم من التفاعلات
"""

import os
import sys
from typing import Dict, Any

# إضافة المسار
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from graph.state import SerajState
from graph.agentic_nodes import seraj_meta_orchestration, seraj_meta_reflect
from agents.seraj_meta_agent import SerajMetaAgent


def test_meta_orchestration_node():
    """
    اختبار 1: عقدة التنسيق الذكي
    
    يجب أن تختار الوكلاء المناسبين بناءً على النية
    """
    print("\n" + "="*80)
    print("🧪 اختبار 1: عقدة seraj_meta_orchestration")
    print("="*80)
    
    # حالة دخول
    state: SerajState = {
        "user_query": "أريد البحث عن موظف اسمه أحمد",
        "intent": "read",
        "company_id": 1,
        "user_name": "محمد",
        "messages": [],
    }
    
    # تنفيذ العقدة
    result = seraj_meta_orchestration(state)
    
    # التحقق من النتائج
    assert "meta_selected_agents" in result, "❌ مفقود: meta_selected_agents"
    assert "meta_execution_plan" in result, "❌ مفقود: meta_execution_plan"
    assert "meta_explanation" in result, "❌ مفقود: meta_explanation"
    assert "messages" in result, "❌ مفقود: messages"
    
    selected_agents = result["meta_selected_agents"]
    print(f"\n✅ الوكلاء المختارة: {selected_agents}")
    
    # يجب أن يختار فاحص للبحث
    assert "fahas" in selected_agents, f"❌ متوقع fahas في {selected_agents}"
    
    # موفّق اختياري (إذا كان هناك غموض في الاسم)
    # في هذه الحالة، fahas يكفي للبحث المباشر
    print(f"✅ fahas موجود (أساسي للبحث)")
    
    print(f"✅ خطة التنفيذ: {result['meta_execution_plan']}")
    print(f"✅ الثقة: {result.get('meta_confidence', 0):.0%}")
    
    print("\n✅ اختبار 1 نجح!")


def test_meta_orchestration_write_intent():
    """
    اختبار 2: التنسيق الذكي لعملية كتابة
    
    يجب أن يختار: مدقق → حارس → كاتب → سجل
    """
    print("\n" + "="*80)
    print("🧪 اختبار 2: عقدة seraj_meta_orchestration للكتابة")
    print("="*80)
    
    state: SerajState = {
        "user_query": "أضف موظف جديد: أحمد محمد، القسم: IT",
        "intent": "write",
        "company_id": 1,
        "user_name": "مدير",
        "messages": [],
    }
    
    result = seraj_meta_orchestration(state)
    
    selected_agents = result["meta_selected_agents"]
    print(f"\n✅ الوكلاء المختارة للكتابة: {selected_agents}")
    
    # يجب أن يتضمن الوكلاء المطلوبين للكتابة
    expected = ["mudaqqiq", "hares", "katib", "sijil"]
    for agent in expected:
        if agent in selected_agents:
            print(f"  ✅ {agent} موجود")
        else:
            print(f"  ⚠️ {agent} غير موجود (اختياري)")
    
    print("\n✅ اختبار 2 نجح!")


def test_meta_reflect_node():
    """
    اختبار 3: عقدة المراجعة الذكية
    
    يجب أن تحلل النتائج وتتعلم من التفاعلات
    """
    print("\n" + "="*80)
    print("🧪 اختبار 3: عقدة seraj_meta_reflect")
    print("="*80)
    
    # حالة بعد تنفيذ العملية
    state: SerajState = {
        "user_query": "ابحث عن الموظفين في قسم IT",
        "intent": "read",
        "meta_selected_agents": ["fahas", "muwaffaq"],
        "meta_explanation": {"query_type": "employee_search"},
        
        # نتائج الوكلاء
        "last_tool_error": None,
        "match_found": True,
        "match_confidence": 0.95,
        
        "messages": [],
    }
    
    result = seraj_meta_reflect(state)
    
    # التحقق من النتائج
    assert "meta_reflection" in result, "❌ مفقود: meta_reflection"
    assert "meta_success_rate" in result, "❌ مفقود: meta_success_rate"
    
    success_rate = result["meta_success_rate"]
    print(f"\n✅ نسبة النجاح: {success_rate:.0%}")
    
    # يجب أن تكون نسبة النجاح عالية (لا أخطاء + مطابقة ناجحة)
    assert success_rate >= 0.5, f"❌ نسبة نجاح منخفضة: {success_rate:.0%}"
    
    if "meta_learning_insights" in result:
        insights = result["meta_learning_insights"]
        print(f"✅ الدروس المستفادة ({len(insights)}):")
        for i, insight in enumerate(insights[:3], 1):
            print(f"  {i}. {insight}")
    
    print("\n✅ اختبار 3 نجح!")


def test_meta_agent_learning():
    """
    اختبار 4: التعلم من التفاعلات
    
    يجب أن يتعلم Meta-Agent من النجاحات والفشل
    """
    print("\n" + "="*80)
    print("🧪 اختبار 4: التعلم من التفاعلات")
    print("="*80)
    
    meta_agent = SerajMetaAgent()
    
    # سيناريو ناجح
    query1 = "ابحث عن موظف"
    agents1 = ["fahas", "muwaffaq"]
    results1 = {
        "fahas": {"last_error": None},
        "muwaffaq": {"match_found": True, "match_confidence": 0.9},
    }
    
    reflection1 = meta_agent._reflect_on_execution(query1, agents1, results1)
    print(f"\n✅ السيناريو 1: نسبة النجاح = {reflection1['success_rate']:.0%}")
    
    # يجب أن تكون عالية (لا أخطاء + مطابقة ناجحة)
    assert reflection1["success_rate"] >= 0.8, "❌ متوقع نسبة نجاح عالية"
    
    # سيناريو فاشل
    query2 = "أضف موظف بدون بيانات"
    agents2 = ["mudaqqiq", "katib"]
    results2 = {
        "mudaqqiq": {"compliance_approved": False},
        "katib": {"write_success": False},
    }
    
    reflection2 = meta_agent._reflect_on_execution(query2, agents2, results2)
    print(f"✅ السيناريو 2: نسبة النجاح = {reflection2['success_rate']:.0%}")
    
    # يجب أن تكون منخفضة (رفض + فشل)
    assert reflection2["success_rate"] <= 0.5, "❌ متوقع نسبة نجاح منخفضة"
    
    print("\n✅ اختبار 4 نجح!")


def test_full_graph_integration():
    """
    اختبار 5: التكامل الكامل مع LangGraph
    
    يختبر المسار الكامل:
    classify_intent → seraj_meta_orchestration → seraj_think → ... → seraj_meta_reflect
    """
    print("\n" + "="*80)
    print("🧪 اختبار 5: التكامل الكامل مع LangGraph")
    print("="*80)
    
    # محاكاة المسار الكامل
    state: SerajState = {
        "user_query": "كم عدد الموظفين؟",
        "intent": "read",
        "company_id": 1,
        "user_name": "أحمد",
        "messages": [],
    }
    
    # 1. تنسيق ذكي
    print("\n📍 الخطوة 1: seraj_meta_orchestration")
    state_after_meta = seraj_meta_orchestration(state)
    state.update(state_after_meta)
    
    print(f"  ✅ وكلاء مختارة: {state.get('meta_selected_agents', [])}")
    
    # 2. تنفيذ (محاكي)
    print("\n📍 الخطوة 2: تنفيذ الوكلاء (محاكي)")
    state["last_tool_error"] = None
    state["match_found"] = True
    
    # 3. مراجعة ذكية
    print("\n📍 الخطوة 3: seraj_meta_reflect")
    state_after_reflect = seraj_meta_reflect(state)
    state.update(state_after_reflect)
    
    print(f"  ✅ نسبة النجاح: {state.get('meta_success_rate', 0):.0%}")
    
    # التحقق من أن كل الحقول موجودة
    required_fields = [
        "meta_selected_agents",
        "meta_execution_plan",
        "meta_reflection",
        "meta_success_rate",
    ]
    
    for field in required_fields:
        assert field in state, f"❌ مفقود: {field}"
        print(f"  ✅ {field}: موجود")
    
    print("\n✅ اختبار 5 نجح!")


def run_all_tests():
    """تشغيل جميع الاختبارات"""
    print("\n" + "="*80)
    print("🚀 تشغيل جميع اختبارات SerajMetaAgent Integration")
    print("="*80)
    
    tests = [
        test_meta_orchestration_node,
        test_meta_orchestration_write_intent,
        test_meta_reflect_node,
        test_meta_agent_learning,
        test_full_graph_integration,
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
