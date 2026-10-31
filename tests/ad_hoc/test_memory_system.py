"""
اختبارات نظام الذاكرة
====================

يختبر:
1. Working Memory
2. Episodic Memory
3. Semantic Memory
4. Profile Memory
5. Agent Integration
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# إضافة المسار
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory import MemoryManager, MemoryType
from memory.agent_integration import create_memory_aware_agent


def test_working_memory():
    """
    اختبار 1: Working Memory - ذاكرة قصيرة المدى
    """
    print("\n" + "="*80)
    print("🧪 اختبار 1: Working Memory")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = MemoryManager(storage_dir=Path(temp_dir))
        
        # الحصول على working memory لجلسة
        wm = manager.get_working_memory("session_123")
        
        assert wm.session_id == "session_123", "❌ Session ID خاطئ"
        assert len(wm.recent_messages) == 0, "❌ يجب أن تكون فارغة"
        
        # إضافة بيانات
        wm.recent_messages.append({"role": "user", "content": "مرحباً"})
        wm.current_query = "ابحث عن موظف"
        wm.current_agent = "fahas"
        
        # التحقق
        assert len(wm.recent_messages) == 1, "❌ يجب أن يكون message واحد"
        assert wm.current_query == "ابحث عن موظف", "❌ Query خاطئ"
        
        print(f"✅ Session ID: {wm.session_id}")
        print(f"✅ Messages: {len(wm.recent_messages)}")
        print(f"✅ Current agent: {wm.current_agent}")
        
        # مسح الذاكرة
        manager.clear_working_memory("session_123")
        wm2 = manager.get_working_memory("session_123")
        
        # يجب إنشاء جديدة
        assert wm2.session_id == "session_123", "❌ يجب إنشاء جديدة"
        assert len(wm2.recent_messages) == 0, "❌ يجب أن تكون فارغة بعد المسح"
        
        print("✅ Working memory cleared successfully")
    
    print("\n✅ اختبار 1 نجح!")


def test_episodic_memory():
    """
    اختبار 2: Episodic Memory - حفظ واسترجاع الحلقات
    """
    print("\n" + "="*80)
    print("🧪 اختبار 2: Episodic Memory")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = MemoryManager(storage_dir=Path(temp_dir))
        
        # حفظ حلقة
        episode_id = manager.save_episode(
            agent="fahas",
            agents_involved=["fahas", "muwaffaq"],
            user_query="ابحث عن أحمد محمد",
            intent="read",
            context={"company_id": 1},
            result={"success": True, "records": 1},
            success=True,
            confidence=0.95,
            decision_path=["perceive", "plan", "execute", "reflect"],
            strategies_used=["exact_match"],
            duration_ms=450,
            company_id=1,
            user_id="user_123",
        )
        
        print(f"\n✅ Saved episode: {episode_id}")
        
        # استرجاع الحلقة
        episode = manager.get_episode(episode_id)
        
        assert episode is not None, "❌ فشل استرجاع الحلقة"
        assert episode.agent == "fahas", "❌ Agent خاطئ"
        assert episode.success == True, "❌ Success خاطئ"
        assert episode.confidence == 0.95, "❌ Confidence خاطئ"
        assert len(episode.agents_involved) == 2, "❌ Agents involved خاطئ"
        
        print(f"✅ Retrieved episode:")
        print(f"  - Agent: {episode.agent}")
        print(f"  - Query: {episode.user_query}")
        print(f"  - Success: {episode.success}")
        print(f"  - Confidence: {episode.confidence:.0%}")
        print(f"  - Duration: {episode.duration_ms}ms")
        
        # البحث في الحلقات
        episodes = manager.search_episodes(
            agent="fahas",
            intent="read",
            success=True,
            limit=10,
        )
        
        assert len(episodes) == 1, f"❌ متوقع حلقة واحدة، وجدنا {len(episodes)}"
        print(f"✅ Search found {len(episodes)} episodes")
        
        # البحث بنص
        episodes_with_query = manager.search_episodes(
            query="أحمد",
            limit=10,
        )
        
        assert len(episodes_with_query) >= 1, "❌ يجب أن يجد الحلقة"
        print(f"✅ Text search found {len(episodes_with_query)} episodes")
    
    print("\n✅ اختبار 2 نجح!")


def test_semantic_memory():
    """
    اختبار 3: Semantic Memory - المعرفة الدلالية
    """
    print("\n" + "="*80)
    print("🧪 اختبار 3: Semantic Memory")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = MemoryManager(storage_dir=Path(temp_dir))
        
        # حفظ معرفة
        knowledge_id = manager.save_knowledge(
            category="employee",
            concept="البحث عن موظف بالاسم",
            description="يمكن البحث عن الموظفين باستخدام الاسم الكامل أو الجزئي",
            related_concepts=["مطابقة الأسماء", "البحث النصي"],
            examples=[
                "ابحث عن أحمد محمد",
                "أين موظف اسمه علي؟",
            ],
            confidence=0.9,
            source="episodes",
            tags=["search", "employee", "name"],
        )
        
        print(f"\n✅ Saved knowledge: {knowledge_id}")
        
        # استرجاع المعرفة
        knowledge = manager.get_knowledge(knowledge_id)
        
        assert knowledge is not None, "❌ فشل استرجاع المعرفة"
        assert knowledge.concept == "البحث عن موظف بالاسم", "❌ Concept خاطئ"
        assert knowledge.confidence == 0.9, "❌ Confidence خاطئ"
        assert len(knowledge.examples) == 2, "❌ Examples خاطئة"
        
        print(f"✅ Retrieved knowledge:")
        print(f"  - Concept: {knowledge.concept}")
        print(f"  - Category: {knowledge.category}")
        print(f"  - Confidence: {knowledge.confidence:.0%}")
        print(f"  - Examples: {len(knowledge.examples)}")
        
        # البحث في المعرفة
        results = manager.search_knowledge(
            query="موظف",
            category="employee",
            limit=5,
        )
        
        assert len(results) >= 1, "❌ يجب أن يجد المعرفة"
        print(f"✅ Knowledge search found {len(results)} results")
    
    print("\n✅ اختبار 3 نجح!")


def test_profile_memory():
    """
    اختبار 4: Profile Memory - التفضيلات
    """
    print("\n" + "="*80)
    print("🧪 اختبار 4: Profile Memory")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = MemoryManager(storage_dir=Path(temp_dir))
        
        # حفظ ملف
        manager.save_profile(
            profile_id="user_123",
            profile_type="user",
            preferences={
                "language": "ar",
                "preferred_agent": "fahas",
            },
            language="ar",
        )
        
        print(f"\n✅ Saved profile: user_123")
        
        # استرجاع الملف
        profile = manager.get_profile("user_123")
        
        assert profile is not None, "❌ فشل استرجاع الملف"
        assert profile.profile_type == "user", "❌ Profile type خاطئ"
        assert profile.language == "ar", "❌ Language خاطئ"
        
        print(f"✅ Retrieved profile:")
        print(f"  - Type: {profile.profile_type}")
        print(f"  - Language: {profile.language}")
        print(f"  - Interactions: {profile.interaction_count}")
        
        # تحديث من حلقة
        episode_id = manager.save_episode(
            agent="fahas",
            agents_involved=["fahas"],
            user_query="test query",
            intent="read",
            context={},
            result={"success": True},
            success=True,
            confidence=0.8,
            decision_path=[],
            strategies_used=["exact"],
            duration_ms=100,
            user_id="user_123",
        )
        
        episode = manager.get_episode(episode_id)
        manager.update_profile_from_episode("user_123", episode)
        
        # التحقق من التحديث
        updated_profile = manager.get_profile("user_123")
        
        assert updated_profile.interaction_count == 1, "❌ Interaction count يجب أن يكون 1"
        assert len(updated_profile.success_patterns) == 1, "❌ يجب حفظ النمط الناجح"
        
        print(f"✅ Profile updated from episode:")
        print(f"  - Interactions: {updated_profile.interaction_count}")
        print(f"  - Success patterns: {len(updated_profile.success_patterns)}")
    
    print("\n✅ اختبار 4 نجح!")


def test_agent_integration():
    """
    اختبار 5: دمج الذاكرة مع الوكلاء
    """
    print("\n" + "="*80)
    print("🧪 اختبار 5: Agent Integration")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = MemoryManager(storage_dir=Path(temp_dir))
        
        # محاكاة وكيل
        class FakeAgent:
            def __init__(self):
                self.name = "test_agent"
        
        agent = FakeAgent()
        
        # تحويله لـ memory-aware
        agent = create_memory_aware_agent(agent, memory_manager=manager)
        
        # التحقق من الدوال الجديدة
        assert hasattr(agent, "memory"), "❌ memory مفقود"
        assert hasattr(agent, "start_episode_tracking"), "❌ start_episode_tracking مفقود"
        assert hasattr(agent, "finish_episode_tracking"), "❌ finish_episode_tracking مفقود"
        
        print(f"\n✅ Agent enhanced with memory:")
        print(f"  - Has memory: {hasattr(agent, 'memory')}")
        print(f"  - Has tracking: {hasattr(agent, 'start_episode_tracking')}")
        
        # استخدام الذاكرة
        agent.start_episode_tracking(
            user_query="test",
            intent="read",
            context={},
        )
        
        agent.log_decision("perceive_completed")
        agent.log_strategy("exact_match")
        
        episode_id = agent.finish_episode_tracking(
            result={"success": True},
            success=True,
            confidence=0.9,
        )
        
        print(f"✅ Episode tracked and saved: {episode_id}")
        
        # التحقق من الحفظ
        episode = manager.get_episode(episode_id)
        
        assert episode is not None, "❌ فشل حفظ الحلقة"
        assert len(episode.decision_path) == 1, "❌ Decision path يجب أن يحتوي على قرار واحد"
        assert len(episode.strategies_used) == 1, "❌ Strategies يجب أن تحتوي على استراتيجية واحدة"
        
        print(f"✅ Episode verification:")
        print(f"  - Decisions: {len(episode.decision_path)}")
        print(f"  - Strategies: {len(episode.strategies_used)}")
    
    print("\n✅ اختبار 5 نجح!")


def test_successful_patterns():
    """
    اختبار 6: استرجاع الأنماط الناجحة
    """
    print("\n" + "="*80)
    print("🧪 اختبار 6: Successful Patterns")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = MemoryManager(storage_dir=Path(temp_dir))
        
        # حفظ عدة حلقات ناجحة
        for i in range(5):
            manager.save_episode(
                agent="fahas",
                agents_involved=["fahas"],
                user_query=f"query_{i}",
                intent="read",
                context={},
                result={"success": True},
                success=True,
                confidence=0.8 + (i * 0.02),  # confidence يزيد
                decision_path=["perceive", "plan", "execute"],
                strategies_used=["exact"],
                duration_ms=100 + i,
            )
        
        # حفظ حلقة فاشلة
        manager.save_episode(
            agent="fahas",
            agents_involved=["fahas"],
            user_query="failed_query",
            intent="read",
            context={},
            result={"success": False},
            success=False,
            confidence=0.3,
            decision_path=["perceive"],
            strategies_used=[],
            duration_ms=50,
        )
        
        print(f"\n✅ Saved 6 episodes (5 successful, 1 failed)")
        
        # استرجاع الناجحة فقط
        successful = manager.get_successful_patterns(
            agent="fahas",
            intent="read",
            min_confidence=0.7,
            limit=10,
        )
        
        assert len(successful) == 5, f"❌ متوقع 5 ناجحة، وجدنا {len(successful)}"
        
        print(f"✅ Retrieved {len(successful)} successful patterns")
        
        for i, ep in enumerate(successful[:3], 1):
            print(f"  {i}. {ep.user_query} - confidence {ep.confidence:.0%}")
    
    print("\n✅ اختبار 6 نجح!")


def test_memory_stats():
    """
    اختبار 7: إحصائيات الذاكرة
    """
    print("\n" + "="*80)
    print("🧪 اختبار 7: Memory Statistics")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = MemoryManager(storage_dir=Path(temp_dir))
        
        # إضافة بيانات
        manager.save_episode(
            agent="test",
            agents_involved=["test"],
            user_query="q",
            intent="read",
            context={},
            result={},
            success=True,
            confidence=0.9,
            decision_path=[],
            strategies_used=[],
            duration_ms=100,
        )
        
        manager.save_knowledge(
            category="test",
            concept="test concept",
            description="desc",
            related_concepts=[],
            examples=[],
            confidence=0.8,
            source="manual",
        )
        
        manager.save_profile(
            profile_id="test_profile",
            profile_type="user",
            preferences={},
        )
        
        # الحصول على الإحصائيات
        stats = manager.get_memory_stats()
        
        print(f"\n✅ Memory Statistics:")
        print(f"  - Episodes: {stats['episodes']}")
        print(f"  - Knowledge: {stats['semantic_knowledge']}")
        print(f"  - Profiles: {stats['profiles']}")
        print(f"  - Working memories: {stats['working_memories']}")
        print(f"  - Vector DB: {stats['vector_db_enabled']}")
        
        assert stats["episodes"] == 1, "❌ Episodes count خاطئ"
        assert stats["semantic_knowledge"] == 1, "❌ Knowledge count خاطئ"
        assert stats["profiles"] == 1, "❌ Profiles count خاطئ"
    
    print("\n✅ اختبار 7 نجح!")


def run_all_tests():
    """تشغيل جميع الاختبارات"""
    print("\n" + "="*80)
    print("🚀 تشغيل جميع اختبارات Memory System")
    print("="*80)
    
    tests = [
        test_working_memory,
        test_episodic_memory,
        test_semantic_memory,
        test_profile_memory,
        test_agent_integration,
        test_successful_patterns,
        test_memory_stats,
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
