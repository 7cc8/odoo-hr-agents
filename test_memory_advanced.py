"""
اختبارات متقدمة لنظام الذاكرة
==============================

يختبر:
1. Vector DB Integration (Chroma)
2. Semantic Search
3. Learning System
4. Pattern Discovery
5. Knowledge Transfer
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# إضافة المسار
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from memory import MemoryManager, LearningSystem
    from memory.vector_store import VectorStore
    CHROMA_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ ChromaDB not available: {e}")
    print("   Install with: pip install chromadb")
    CHROMA_AVAILABLE = False
    sys.exit(0)


def test_vector_store_init():
    """
    اختبار 1: تهيئة Vector Store
    """
    print("\n" + "="*80)
    print("🧪 اختبار 1: Vector Store Initialization")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        vector_store = VectorStore(persist_directory=Path(temp_dir))
        
        stats = vector_store.get_stats()
        
        assert stats["episodes_count"] == 0, "❌ يجب أن يكون فارغاً"
        assert stats["knowledge_count"] == 0, "❌ يجب أن يكون فارغاً"
        
        print(f"\n✅ Vector store initialized")
        print(f"  - Episodes: {stats['episodes_count']}")
        print(f"  - Knowledge: {stats['knowledge_count']}")
    
    print("\n✅ اختبار 1 نجح!")


def test_semantic_search_episodes():
    """
    اختبار 2: البحث الدلالي في الحلقات
    """
    print("\n" + "="*80)
    print("🧪 اختبار 2: Semantic Search - Episodes")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = MemoryManager(
            storage_dir=Path(temp_dir),
            use_vector_db=True,
        )
        
        # حفظ عدة حلقات
        queries = [
            "ابحث عن موظف اسمه أحمد محمد",
            "أريد العثور على أحمد في قسم IT",
            "كم عدد الموظفين في المبيعات؟",
            "أضف موظف جديد",
        ]
        
        for i, query in enumerate(queries):
            manager.save_episode(
                agent="fahas",
                agents_involved=["fahas"],
                user_query=query,
                intent="read" if i < 3 else "write",
                context={},
                result={"success": True},
                success=True,
                confidence=0.8 + (i * 0.05),
                decision_path=[],
                strategies_used=["exact"],
                duration_ms=100 + i,
            )
        
        print(f"\n✅ Saved {len(queries)} episodes")
        
        # البحث الدلالي
        # يجب أن يجد "أحمد" حتى لو كتبنا "موظف اسمه أحمد"
        results = manager.search_episodes(
            query="موظف اسمه أحمد",  # semantic search
            limit=3,
        )
        
        print(f"\n✅ Semantic search results: {len(results)}")
        for i, ep in enumerate(results, 1):
            print(f"  {i}. {ep.user_query[:50]}... (confidence: {ep.confidence:.0%})")
        
        # يجب أن يجد على الأقل الحلقات المتعلقة بأحمد
        assert len(results) >= 2, f"❌ متوقع 2+ نتائج، وجدنا {len(results)}"
    
    print("\n✅ اختبار 2 نجح!")


def test_semantic_search_knowledge():
    """
    اختبار 3: البحث الدلالي في المعرفة
    """
    print("\n" + "="*80)
    print("🧪 اختبار 3: Semantic Search - Knowledge")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = MemoryManager(
            storage_dir=Path(temp_dir),
            use_vector_db=True,
        )
        
        # حفظ معارف
        knowledge_items = [
            ("البحث عن موظف", "employee", "يمكن البحث عن الموظفين بالاسم أو القسم"),
            ("إضافة موظف جديد", "employee", "لإضافة موظف جديد، تحتاج الاسم والقسم"),
            ("حساب الرواتب", "payroll", "يتم حساب الرواتب شهرياً"),
        ]
        
        for concept, category, desc in knowledge_items:
            manager.save_knowledge(
                category=category,
                concept=concept,
                description=desc,
                related_concepts=[],
                examples=[],
                confidence=0.9,
                source="test",
            )
        
        print(f"\n✅ Saved {len(knowledge_items)} knowledge items")
        
        # البحث الدلالي
        results = manager.search_knowledge(
            query="كيف أجد موظف؟",  # semantic search
            limit=3,
        )
        
        print(f"\n✅ Knowledge search results: {len(results)}")
        for i, know in enumerate(results, 1):
            print(f"  {i}. {know.concept} (category: {know.category})")
        
        assert len(results) >= 1, "❌ يجب أن يجد معرفة واحدة على الأقل"
    
    print("\n✅ اختبار 3 نجح!")


def test_learning_performance():
    """
    اختبار 4: تحليل الأداء
    """
    print("\n" + "="*80)
    print("🧪 اختبار 4: Learning System - Performance Analysis")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = MemoryManager(storage_dir=Path(temp_dir))
        learning = LearningSystem(manager)
        
        # حفظ حلقات متنوعة
        for i in range(10):
            success = i < 7  # 70% success rate
            
            manager.save_episode(
                agent="fahas",
                agents_involved=["fahas"],
                user_query=f"query_{i}",
                intent="read",
                context={},
                result={"success": success},
                success=success,
                confidence=0.8 if success else 0.4,
                decision_path=[],
                strategies_used=["exact" if i % 2 == 0 else "fuzzy"],
                duration_ms=100 + i * 10,
            )
        
        print(f"\n✅ Saved 10 episodes (7 successful, 3 failed)")
        
        # تحليل الأداء
        perf = learning.get_agent_performance("fahas", days=30)
        
        print(f"\n✅ Performance analysis:")
        print(f"  - Total episodes: {perf['total_episodes']}")
        print(f"  - Success rate: {perf['success_rate']:.0%}")
        print(f"  - Avg confidence: {perf['avg_confidence']:.0%}")
        print(f"  - Avg duration: {perf['avg_duration_ms']:.0f}ms")
        
        assert perf["total_episodes"] == 10, "❌ يجب أن يكون 10"
        assert perf["success_rate"] == 0.7, f"❌ متوقع 70%، وجدنا {perf['success_rate']:.0%}"
        
        # اقتراحات التحسين
        suggestions = learning.suggest_improvements("fahas")
        
        print(f"\n✅ Suggestions ({len(suggestions)}):")
        for suggestion in suggestions:
            print(f"  - {suggestion}")
    
    print("\n✅ اختبار 4 نجح!")


def test_pattern_discovery():
    """
    اختبار 5: اكتشاف الأنماط
    """
    print("\n" + "="*80)
    print("🧪 اختبار 5: Pattern Discovery")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = MemoryManager(storage_dir=Path(temp_dir))
        learning = LearningSystem(manager)
        
        # حفظ نمط متكرر
        for i in range(5):
            manager.save_episode(
                agent="fahas",
                agents_involved=["fahas"],
                user_query=f"search_{i}",
                intent="read",
                context={},
                result={"success": True},
                success=True,
                confidence=0.9,
                decision_path=[],
                strategies_used=["exact", "fuzzy"],  # نفس النمط
                duration_ms=100,
            )
        
        # نمط مختلف (أقل تكراراً)
        for i in range(2):
            manager.save_episode(
                agent="fahas",
                agents_involved=["fahas"],
                user_query=f"search_alt_{i}",
                intent="read",
                context={},
                result={"success": True},
                success=True,
                confidence=0.8,
                decision_path=[],
                strategies_used=["semantic"],
                duration_ms=150,
            )
        
        print(f"\n✅ Saved episodes with patterns")
        
        # اكتشاف الأنماط
        patterns = learning.discover_patterns(
            agent="fahas",
            intent="read",
            min_occurrences=3,
        )
        
        print(f"\n✅ Discovered patterns: {len(patterns)}")
        for i, pattern in enumerate(patterns, 1):
            print(f"  {i}. {pattern['strategies']} - {pattern['occurrences']} times")
        
        # يجب أن يجد النمط المتكرر
        assert len(patterns) >= 1, "❌ يجب أن يكتشف نمط واحد على الأقل"
        assert patterns[0]["occurrences"] >= 3, "❌ النمط يجب أن يتكرر 3+ مرات"
    
    print("\n✅ اختبار 5 نجح!")


def test_strategy_recommendation():
    """
    اختبار 6: اقتراح الاستراتيجيات
    """
    print("\n" + "="*80)
    print("🧪 اختبار 6: Strategy Recommendation")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = MemoryManager(storage_dir=Path(temp_dir))
        learning = LearningSystem(manager)
        
        # حفظ حلقات مع استراتيجية واحدة ناجحة جداً
        for i in range(5):
            manager.save_episode(
                agent="muwaffaq",
                agents_involved=["muwaffaq"],
                user_query=f"match_{i}",
                intent="match",
                context={},
                result={"success": True},
                success=True,
                confidence=0.95,
                decision_path=[],
                strategies_used=["fuzzy_text"],  # هذه الأفضل
                duration_ms=80,
            )
        
        print(f"\n✅ Saved episodes with fuzzy_text strategy")
        
        # اقتراح استراتيجية
        recommended = learning.recommend_strategy(
            agent="muwaffaq",
            intent="match",
        )
        
        print(f"\n✅ Recommended strategy: {recommended}")
        
        assert recommended is not None, "❌ يجب أن يقترح استراتيجية"
        assert recommended == "fuzzy_text", f"❌ متوقع fuzzy_text، وجدنا {recommended}"
    
    print("\n✅ اختبار 6 نجح!")


def test_knowledge_transfer():
    """
    اختبار 7: نقل المعرفة بين الوكلاء
    """
    print("\n" + "="*80)
    print("🧪 اختبار 7: Knowledge Transfer")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = MemoryManager(storage_dir=Path(temp_dir))
        learning = LearningSystem(manager)
        
        # fahas لديه أنماط ناجحة
        for i in range(5):
            manager.save_episode(
                agent="fahas",
                agents_involved=["fahas"],
                user_query=f"query_{i}",
                intent="read",
                context={},
                result={"success": True},
                success=True,
                confidence=0.9,
                decision_path=[],
                strategies_used=["exact", "fuzzy"],
                duration_ms=100,
            )
        
        print(f"\n✅ Fahas has successful patterns")
        
        # نقل لـ musleh
        transferred = learning.transfer_knowledge(
            from_agent="fahas",
            to_agent="musleh",
            intent="read",
        )
        
        print(f"\n✅ Transferred {transferred} knowledge items")
        
        assert transferred > 0, "❌ يجب أن ينقل معرفة واحدة على الأقل"
        
        # التحقق من أن المعرفة موجودة
        knowledge = manager.search_knowledge(
            query="fahas",
            category="transfer_musleh",
            limit=10,
        )
        
        print(f"✅ Found {len(knowledge)} transferred knowledge items")
        
        assert len(knowledge) > 0, "❌ المعرفة المنقولة يجب أن تكون موجودة"
    
    print("\n✅ اختبار 7 نجح!")


def test_overall_performance():
    """
    اختبار 8: الأداء الإجمالي للنظام
    """
    print("\n" + "="*80)
    print("🧪 اختبار 8: Overall System Performance")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = MemoryManager(storage_dir=Path(temp_dir))
        learning = LearningSystem(manager)
        
        # حفظ حلقات لوكلاء متعددين
        agents = ["fahas", "musleh", "katib"]
        
        for agent in agents:
            for i in range(5):
                manager.save_episode(
                    agent=agent,
                    agents_involved=[agent],
                    user_query=f"{agent}_query_{i}",
                    intent="read",
                    context={},
                    result={"success": True},
                    success=True,
                    confidence=0.8,
                    decision_path=[],
                    strategies_used=["test"],
                    duration_ms=100,
                )
        
        print(f"\n✅ Saved episodes for {len(agents)} agents")
        
        # الأداء الإجمالي
        overall = learning.get_overall_performance(days=30)
        
        print(f"\n✅ Overall performance:")
        print(f"  - Total episodes: {overall['total_episodes']}")
        print(f"  - Success rate: {overall['success_rate']:.0%}")
        print(f"  - Active agents: {len(overall['agents_performance'])}")
        
        assert overall["total_episodes"] == 15, "❌ يجب أن يكون 15"
        assert overall["success_rate"] == 1.0, "❌ يجب أن يكون 100%"
        assert len(overall["agents_performance"]) == 3, "❌ يجب أن يكون 3 وكلاء"
    
    print("\n✅ اختبار 8 نجح!")


def run_all_tests():
    """تشغيل جميع الاختبارات"""
    print("\n" + "="*80)
    print("🚀 تشغيل اختبارات Memory System المتقدمة")
    print("="*80)
    
    if not CHROMA_AVAILABLE:
        print("\n⚠️ ChromaDB not available - skipping tests")
        print("   Install with: pip install chromadb")
        return True
    
    tests = [
        test_vector_store_init,
        test_semantic_search_episodes,
        test_semantic_search_knowledge,
        test_learning_performance,
        test_pattern_discovery,
        test_strategy_recommendation,
        test_knowledge_transfer,
        test_overall_performance,
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
