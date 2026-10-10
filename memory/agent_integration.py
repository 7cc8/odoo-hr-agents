"""
Agent Integration with Memory System
====================================

دمج نظام الذاكرة مع الوكلاء الموجودة
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from memory.manager import MemoryManager
from memory.types import Episode

logger = logging.getLogger("memory.agent_integration")


class MemoryEnabledAgent:
    """
    Mixin class لإضافة قدرات الذاكرة لأي وكيل
    
    الاستخدام:
    ```python
    class MyAgent(MemoryEnabledAgent, BaseAgent):
        def __init__(self):
            BaseAgent.__init__(self, name="my_agent", ...)
            MemoryEnabledAgent.__init__(self)
    ```
    """
    
    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        """
        Args:
            memory_manager: مدير الذاكرة (إذا لم يُحدد، سيُنشأ واحد جديد)
        """
        self.memory = memory_manager or MemoryManager()
        self._episode_start_time: Optional[float] = None
        self._current_episode_data: Dict[str, Any] = {}
    
    def start_episode_tracking(
        self,
        user_query: str,
        intent: str,
        context: Dict[str, Any],
        company_id: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """بدء تتبع حلقة تفاعل جديدة"""
        self._episode_start_time = time.time()
        self._current_episode_data = {
            "user_query": user_query,
            "intent": intent,
            "context": context,
            "company_id": company_id,
            "user_id": user_id,
            "decision_path": [],
            "strategies_used": [],
        }
    
    def log_decision(self, decision: str) -> None:
        """تسجيل قرار في مسار القرارات"""
        if "decision_path" in self._current_episode_data:
            self._current_episode_data["decision_path"].append(decision)
    
    def log_strategy(self, strategy: str) -> None:
        """تسجيل استراتيجية مستخدمة"""
        if "strategies_used" in self._current_episode_data:
            self._current_episode_data["strategies_used"].append(strategy)
    
    def finish_episode_tracking(
        self,
        result: Dict[str, Any],
        success: bool,
        confidence: float,
        agents_involved: Optional[List[str]] = None,
    ) -> str:
        """
        إنهاء تتبع الحلقة وحفظها
        
        Returns:
            episode_id: معرف الحلقة المحفوظة
        """
        if not self._episode_start_time:
            logger.warning("⚠️ Episode tracking not started!")
            return ""
        
        duration_ms = int((time.time() - self._episode_start_time) * 1000)
        
        # استخراج الدروس المستفادة من النتيجة
        lessons = []
        if success:
            lessons.append(f"نجح باستخدام {', '.join(self._current_episode_data['strategies_used'])}")
        else:
            lessons.append(f"فشل - سبب: {result.get('error', 'unknown')}")
        
        # حفظ الحلقة
        episode_id = self.memory.save_episode(
            agent=self.name if hasattr(self, "name") else "unknown",
            agents_involved=agents_involved or [self.name] if hasattr(self, "name") else [],
            user_query=self._current_episode_data["user_query"],
            intent=self._current_episode_data["intent"],
            context=self._current_episode_data["context"],
            result=result,
            success=success,
            confidence=confidence,
            decision_path=self._current_episode_data["decision_path"],
            strategies_used=self._current_episode_data["strategies_used"],
            duration_ms=duration_ms,
            company_id=self._current_episode_data.get("company_id"),
            user_id=self._current_episode_data.get("user_id"),
        )
        
        # تحديث الملف الشخصي
        user_id = self._current_episode_data.get("user_id")
        if user_id:
            episode = self.memory.get_episode(episode_id)
            if episode:
                self.memory.update_profile_from_episode(user_id, episode)
        
        # إعادة تعيين
        self._episode_start_time = None
        self._current_episode_data = {}
        
        return episode_id
    
    def get_similar_episodes(
        self,
        query: str,
        intent: str,
        limit: int = 5,
    ) -> List[Episode]:
        """الحصول على حلقات مشابهة من الذاكرة"""
        return self.memory.search_episodes(
            query=query,
            agent=self.name if hasattr(self, "name") else None,
            intent=intent,
            limit=limit,
        )
    
    def get_successful_patterns(
        self,
        intent: str,
        min_confidence: float = 0.7,
        limit: int = 5,
    ) -> List[Episode]:
        """الحصول على الأنماط الناجحة السابقة"""
        return self.memory.get_successful_patterns(
            agent=self.name if hasattr(self, "name") else "",
            intent=intent,
            min_confidence=min_confidence,
            limit=limit,
        )
    
    def learn_from_episode(self, episode: Episode) -> None:
        """
        التعلم من حلقة سابقة
        
        يمكن للوكيل تخصيص هذه الدالة حسب احتياجاته
        """
        if episode.success:
            logger.info(f"📚 Learning from successful episode: {episode.episode_id}")
            # يمكن تخصيص التعلم هنا
        else:
            logger.info(f"📚 Learning from failed episode: {episode.episode_id}")
            # يمكن تعلم ما يجب تجنبه


def enhance_agent_with_memory(agent_class):
    """
    Decorator لإضافة قدرات الذاكرة لأي agent class
    
    الاستخدام:
    ```python
    @enhance_agent_with_memory
    class MyAgent(BaseAgent):
        ...
    ```
    """
    class MemoryEnhancedAgent(MemoryEnabledAgent, agent_class):
        def __init__(self, *args, memory_manager=None, **kwargs):
            agent_class.__init__(self, *args, **kwargs)
            MemoryEnabledAgent.__init__(self, memory_manager=memory_manager)
    
    return MemoryEnhancedAgent


# ============================================================================
# Integration Helpers for Existing Agents
# ============================================================================

def create_memory_aware_agent(agent_instance, memory_manager: Optional[MemoryManager] = None):
    """
    تحويل وكيل موجود ليصبح memory-aware
    
    Args:
        agent_instance: نسخة من أي وكيل
        memory_manager: مدير الذاكرة (اختياري)
    
    Returns:
        نفس الوكيل لكن مع قدرات الذاكرة
    """
    # إضافة memory manager للوكيل
    agent_instance.memory = memory_manager or MemoryManager()
    
    # إضافة الدوال
    agent_instance.start_episode_tracking = lambda *args, **kwargs: MemoryEnabledAgent.start_episode_tracking(agent_instance, *args, **kwargs)
    agent_instance.log_decision = lambda decision: MemoryEnabledAgent.log_decision(agent_instance, decision)
    agent_instance.log_strategy = lambda strategy: MemoryEnabledAgent.log_strategy(agent_instance, strategy)
    agent_instance.finish_episode_tracking = lambda *args, **kwargs: MemoryEnabledAgent.finish_episode_tracking(agent_instance, *args, **kwargs)
    agent_instance.get_similar_episodes = lambda *args, **kwargs: MemoryEnabledAgent.get_similar_episodes(agent_instance, *args, **kwargs)
    agent_instance.get_successful_patterns = lambda *args, **kwargs: MemoryEnabledAgent.get_successful_patterns(agent_instance, *args, **kwargs)
    
    # تهيئة المتغيرات الداخلية
    agent_instance._episode_start_time = None
    agent_instance._current_episode_data = {}
    
    logger.info(f"✅ Enhanced {agent_instance.name} with memory capabilities")
    
    return agent_instance
