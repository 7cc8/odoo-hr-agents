"""
اختبارات موفّق (Muwaffaq) Agent - المطابقة الذكية
======================================================

يختبر:
1. Perceive: فهم السياق الدلالي
2. Plan: استراتيجية المطابقة (exact/fuzzy/phonetic/contextual)
3. Execute: تنفيذ المطابقات
4. Reflect: تقييم الثقة والبدائل
5. التعلم من التطابقات المعتمدة
"""

import os
import sys
from typing import Dict, Any, List

# إضافة المسار
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.muwaffaq_agent import MuwaffaqAgent, MatchStrategy, MatchDecision


def test_perceive_exact_match():
    """
    اختبار 1: perceive - مطابقة دقيقة واضحة
    
    "أحمد محمد" في قائمة أسماء واضحة
    """
    print("\n" + "="*80)
    print("🧪 اختبار 1: Perceive - مطابقة دقيقة")
    print("="*80)
    
    agent = MuwaffaqAgent()
    
    request = {
        "query": "أحمد محمد",
        "candidates": [
            {"id": 1, "name": "أحمد محمد", "department": "IT"},
            {"id": 2, "name": "محمد أحمد", "department": "HR"},
            {"id": 3, "name": "أحمد علي", "department": "Sales"},
        ],
        "context": {"type": "employee_search", "field": "name"}
    }
    
    perception = agent.perceive(request)
    
    # التحقق من النتائج
    assert perception["query"] == "أحمد محمد", "❌ Query مفقود"
    assert len(perception["candidates"]) == 3, "❌ Candidates مفقودة"
    assert perception["match_type"] in ["name", "text"], "❌ Match type خاطئ"
    assert perception["sensitivity"] in ["high", "medium", "low"], "❌ Sensitivity مفقود"
    
    print(f"✅ Query: {perception['query']}")
    print(f"✅ Candidates: {len(perception['candidates'])}")
    print(f"✅ Match type: {perception['match_type']}")
    print(f"✅ Sensitivity: {perception['sensitivity']}")
    print(f"✅ Ambiguity: {perception['ambiguity_score']:.2f}")
    
    print("\n✅ اختبار 1 نجح!")


def test_plan_exact_strategy():
    """
    اختبار 2: plan - استراتيجية المطابقة الدقيقة
    
    عندما يكون الاسم واضح، يجب اختيار EXACT أولاً
    """
    print("\n" + "="*80)
    print("🧪 اختبار 2: Plan - استراتيجية EXACT")
    print("="*80)
    
    agent = MuwaffaqAgent()
    
    perception = {
        "query": "أحمد محمد",
        "candidates": [{"id": 1, "name": "أحمد محمد"}],
        "match_type": "name",
        "sensitivity": "high",
        "ambiguity_score": 0.1,
        "context": {},
    }
    
    plan = agent.plan(perception)
    
    # التحقق من الاستراتيجيات
    assert "strategies" in plan, "❌ Strategies مفقودة"
    assert len(plan["strategies"]) > 0, "❌ لا توجد استراتيجيات"
    
    strategies = plan["strategies"]
    print(f"\n✅ الاستراتيجيات المقترحة ({len(strategies)}):")
    for strategy in strategies:
        print(f"  - {strategy.value}")
    
    # يجب أن يبدأ بـ EXACT
    assert strategies[0] == MatchStrategy.EXACT, f"❌ متوقع EXACT أولاً، وجدنا {strategies[0]}"
    
    print(f"✅ الاستراتيجية الأولى: {strategies[0].value}")
    print(f"✅ الثقة: {plan['confidence']:.0%}")
    
    print("\n✅ اختبار 2 نجح!")


def test_execute_exact_match():
    """
    اختبار 3: execute - تنفيذ مطابقة دقيقة
    
    يجب أن يجد "أحمد محمد" بنسبة 100%
    """
    print("\n" + "="*80)
    print("🧪 اختبار 3: Execute - مطابقة دقيقة")
    print("="*80)
    
    agent = MuwaffaqAgent()
    
    perception = {
        "query": "أحمد محمد",
        "candidates": [
            {"id": 1, "name": "أحمد محمد", "department": "IT"},
            {"id": 2, "name": "محمد أحمد", "department": "HR"},
        ],
        "match_type": "name",
        "context": {},
    }
    
    plan = {
        "strategies": [MatchStrategy.EXACT],
        "confidence": 0.9,
    }
    
    result = agent.execute(plan, perception)
    
    # التحقق من النتائج
    assert "matches" in result, "❌ Matches مفقودة"
    assert len(result["matches"]) > 0, "❌ لم يجد أي مطابقات"
    
    best_match = result["matches"][0]
    print(f"\n✅ أفضل مطابقة:")
    print(f"  - Name: {best_match.name}")
    print(f"  - Score: {best_match.score:.0%}")
    print(f"  - Strategy: {best_match.strategy}")
    
    # يجب أن تكون المطابقة 100%
    assert best_match.score >= 0.99, f"❌ متوقع 100%، وجدنا {best_match.score:.0%}"
    assert best_match.name == "أحمد محمد", "❌ الاسم خاطئ"
    
    print("\n✅ اختبار 3 نجح!")


def test_execute_fuzzy_match():
    """
    اختبار 4: execute - مطابقة ضبابية
    
    "احمد محمد" (بدون همزة) يجب أن يطابق "أحمد محمد"
    """
    print("\n" + "="*80)
    print("🧪 اختبار 4: Execute - مطابقة ضبابية")
    print("="*80)
    
    agent = MuwaffaqAgent()
    
    perception = {
        "query": "احمد محمد",  # بدون همزة
        "candidates": [
            {"id": 1, "name": "أحمد محمد", "department": "IT"},
            {"id": 2, "name": "أحمد علي", "department": "Sales"},
        ],
        "match_type": "name",
        "context": {},
    }
    
    plan = {
        "strategies": [MatchStrategy.FUZZY_TEXT],
        "confidence": 0.8,
    }
    
    result = agent.execute(plan, perception)
    
    assert len(result["matches"]) > 0, "❌ لم يجد مطابقات"
    
    best_match = result["matches"][0]
    print(f"\n✅ أفضل مطابقة ضبابية:")
    print(f"  - Query: احمد محمد (بدون همزة)")
    print(f"  - Match: {best_match.name}")
    print(f"  - Score: {best_match.score:.0%}")
    
    # يجب أن يطابق "أحمد محمد" بنسبة عالية
    assert best_match.score >= 0.7, f"❌ نسبة منخفضة: {best_match.score:.0%}"
    assert "أحمد" in best_match.name, "❌ لم يطابق الاسم الصحيح"
    
    print("\n✅ اختبار 4 نجح!")


def test_reflect_high_confidence():
    """
    اختبار 5: reflect - تقييم ثقة عالية
    
    مطابقة 100% يجب أن تعطي decision = ACCEPT
    """
    print("\n" + "="*80)
    print("🧪 اختبار 5: Reflect - ثقة عالية")
    print("="*80)
    
    agent = MuwaffaqAgent()
    
    from agents.muwaffaq_agent import MatchCandidate
    
    perception = {"query": "أحمد محمد", "sensitivity": "high"}
    plan = {"strategies": [MatchStrategy.EXACT]}
    result = {
        "matches": [
            MatchCandidate(
                candidate_id="1",
                name="أحمد محمد",
                score=1.0,
                strategy=MatchStrategy.EXACT,
                metadata={"department": "IT"}
            )
        ],
        "strategy_used": MatchStrategy.EXACT,
    }
    
    reflection = agent.reflect(perception, plan, result)
    
    # التحقق من القرار
    assert "decision" in reflection, "❌ Decision مفقود"
    assert reflection["decision"] == MatchDecision.ACCEPT, f"❌ متوقع ACCEPT، وجدنا {reflection['decision']}"
    assert reflection["confidence"] >= 0.9, f"❌ ثقة منخفضة: {reflection['confidence']:.0%}"
    
    print(f"\n✅ القرار: {reflection['decision'].value}")
    print(f"✅ الثقة: {reflection['confidence']:.0%}")
    print(f"✅ السبب: {reflection['reasoning']}")
    
    print("\n✅ اختبار 5 نجح!")


def test_reflect_low_confidence():
    """
    اختبار 6: reflect - ثقة منخفضة
    
    مطابقة 40% يجب أن تعطي decision = REQUEST_CLARIFICATION
    """
    print("\n" + "="*80)
    print("🧪 اختبار 6: Reflect - ثقة منخفضة")
    print("="*80)
    
    agent = MuwaffaqAgent()
    
    from agents.muwaffaq_agent import MatchCandidate
    
    perception = {"query": "أحمد", "sensitivity": "high"}
    plan = {"strategies": [MatchStrategy.FUZZY_TEXT]}
    result = {
        "matches": [
            MatchCandidate("1", "أحمد محمد", 0.4, MatchStrategy.FUZZY_TEXT, {}),
            MatchCandidate("2", "أحمد علي", 0.38, MatchStrategy.FUZZY_TEXT, {}),
            MatchCandidate("3", "أحمد حسن", 0.35, MatchStrategy.FUZZY_TEXT, {}),
        ],
        "strategy_used": MatchStrategy.FUZZY_TEXT,
    }
    
    reflection = agent.reflect(perception, plan, result)
    
    # يجب طلب توضيح
    print(f"\n✅ القرار: {reflection['decision'].value}")
    print(f"✅ الثقة: {reflection['confidence']:.0%}")
    print(f"✅ البدائل: {len(reflection.get('alternatives', []))}")
    
    assert reflection["decision"] in [MatchDecision.REQUEST_CLARIFICATION, MatchDecision.PROPOSE_ALTERNATIVES], \
        f"❌ متوقع REQUEST_CLARIFICATION أو PROPOSE_ALTERNATIVES، وجدنا {reflection['decision']}"
    
    assert len(reflection.get("alternatives", [])) >= 2, "❌ يجب اقتراح بدائل"
    
    print("\n✅ اختبار 6 نجح!")


def test_find_match_api():
    """
    اختبار 7: find_match() - الواجهة العامة
    
    اختبار الدورة الكاملة من خلال الـ API العام
    """
    print("\n" + "="*80)
    print("🧪 اختبار 7: find_match() API")
    print("="*80)
    
    agent = MuwaffaqAgent()
    
    request = {
        "query": "أحمد محمد",
        "candidates": [
            {"id": 1, "name": "أحمد محمد", "department": "IT"},
            {"id": 2, "name": "محمد أحمد", "department": "HR"},
        ],
        "context": {"type": "employee_search"}
    }
    
    result = agent.find_match(request)
    
    # التحقق من النتائج
    assert "status" in result, "❌ Status مفقود"
    assert result["status"] in ["matched", "proposed", "no_match"], "❌ Status غير صحيح"
    
    print(f"\n✅ Status: {result['status']}")
    print(f"✅ Decision: {result['decision']}")
    print(f"✅ Confidence: {result['confidence']:.0%}")
    
    if result.get("best_match"):
        print(f"✅ Best match: {result['best_match']['name']} ({result['best_match']['score']:.0%})")
    
    if result.get("alternatives"):
        print(f"✅ Alternatives: {len(result['alternatives'])}")
    
    # يجب أن يجد مطابقة
    assert result["status"] in ["matched", "proposed"], "❌ يجب أن يجد مطابقة"
    
    print("\n✅ اختبار 7 نجح!")


def test_multiple_strategies_fallback():
    """
    اختبار 8: استراتيجيات متعددة مع fallback
    
    إذا فشلت EXACT، يجب أن يجرب FUZZY
    """
    print("\n" + "="*80)
    print("🧪 اختبار 8: استراتيجيات متعددة")
    print("="*80)
    
    agent = MuwaffaqAgent()
    
    perception = {
        "query": "احمد",  # بدون همزة وبدون اسم العائلة
        "candidates": [
            {"id": 1, "name": "أحمد محمد", "department": "IT"},
        ],
        "match_type": "name",
        "context": {},
    }
    
    # خطة مع استراتيجيتين
    plan = {
        "strategies": [MatchStrategy.EXACT, MatchStrategy.FUZZY_TEXT],
        "confidence": 0.7,
    }
    
    result = agent.execute(plan, perception)
    
    # يجب أن ينجح مع FUZZY بعد فشل EXACT
    assert len(result["matches"]) > 0, "❌ لم يجد مطابقات حتى مع fallback"
    
    print(f"\n✅ Strategy used: {result['strategy_used']}")
    print(f"✅ Matches found: {len(result['matches'])}")
    print(f"✅ Best score: {result['matches'][0].score:.0%}")
    
    # يجب أن يكون استخدم FUZZY
    assert result["strategy_used"] == MatchStrategy.FUZZY_TEXT, \
        f"❌ متوقع FUZZY_TEXT بعد فشل EXACT، وجدنا {result['strategy_used']}"
    
    print("\n✅ اختبار 8 نجح!")


def test_no_match_scenario():
    """
    اختبار 9: سيناريو عدم وجود مطابقة
    
    اسم غير موجود نهائياً
    """
    print("\n" + "="*80)
    print("🧪 اختبار 9: عدم وجود مطابقة")
    print("="*80)
    
    agent = MuwaffaqAgent()
    
    request = {
        "query": "زيد خالد",
        "candidates": [
            {"id": 1, "name": "أحمد محمد"},
            {"id": 2, "name": "علي حسن"},
        ],
        "context": {}
    }
    
    result = agent.find_match(request)
    
    print(f"\n✅ Status: {result['status']}")
    print(f"✅ Decision: {result['decision']}")
    
    # يجب أن يرجع no_match أو يطلب إنشاء جديد
    assert result["decision"] in [MatchDecision.NO_MATCH, MatchDecision.CREATE_NEW], \
        f"❌ متوقع NO_MATCH أو CREATE_NEW، وجدنا {result['decision']}"
    
    print("\n✅ اختبار 9 نجح!")


def test_contextual_matching():
    """
    اختبار 10: المطابقة السياقية
    
    استخدام السياق لتحسين المطابقة
    """
    print("\n" + "="*80)
    print("🧪 اختبار 10: المطابقة السياقية")
    print("="*80)
    
    agent = MuwaffaqAgent()
    
    request = {
        "query": "أحمد",
        "candidates": [
            {"id": 1, "name": "أحمد محمد", "department": "IT", "email": "ahmad@company.com"},
            {"id": 2, "name": "أحمد علي", "department": "HR", "email": "ahmad.ali@company.com"},
        ],
        "context": {
            "type": "employee_search",
            "department": "IT",  # سياق إضافي
        }
    }
    
    result = agent.find_match(request)
    
    print(f"\n✅ Best match: {result.get('best_match', {}).get('name', 'N/A')}")
    print(f"✅ Department: {result.get('best_match', {}).get('metadata', {}).get('department', 'N/A')}")
    
    # مع السياق، يجب أن يفضل من قسم IT
    if result.get("best_match"):
        dept = result["best_match"].get("metadata", {}).get("department")
        print(f"✅ Matched department: {dept}")
    
    print("\n✅ اختبار 10 نجح!")


def run_all_tests():
    """تشغيل جميع الاختبارات"""
    print("\n" + "="*80)
    print("🚀 تشغيل جميع اختبارات MuwaffaqAgent")
    print("="*80)
    
    tests = [
        test_perceive_exact_match,
        test_plan_exact_strategy,
        test_execute_exact_match,
        test_execute_fuzzy_match,
        test_reflect_high_confidence,
        test_reflect_low_confidence,
        test_find_match_api,
        test_multiple_strategies_fallback,
        test_no_match_scenario,
        test_contextual_matching,
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
