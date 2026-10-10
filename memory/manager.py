"""
Memory Manager - مدير الذاكرة الموحد
====================================

يدير جميع أنواع الذاكرة ويوفر واجهة موحدة
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from memory.types import (
    Episode,
    MemoryType,
    SemanticKnowledge,
    UserProfile,
    WorkingMemory,
)

logger = logging.getLogger("memory.manager")


class MemoryManager:
    """
    مدير الذاكرة الموحد
    
    يوفر:
    1. حفظ واسترجاع Episodic Memory
    2. إدارة Semantic Knowledge
    3. إدارة User/Company Profiles
    4. Working Memory للجلسة الحالية
    5. Semantic search (بدون Vector DB في البداية، ثم مع Chroma)
    """
    
    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        use_vector_db: bool = False,
        vector_db_type: str = "chroma",
    ):
        """
        Args:
            storage_dir: مجلد التخزين (افتراضي: ./memory_store)
            use_vector_db: هل نستخدم Vector DB؟
            vector_db_type: نوع Vector DB (chroma أو qdrant)
        """
        self.storage_dir = storage_dir or Path("./memory_store")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # المجلدات الفرعية
        self.episodes_dir = self.storage_dir / "episodes"
        self.semantic_dir = self.storage_dir / "semantic"
        self.profiles_dir = self.storage_dir / "profiles"
        
        for d in [self.episodes_dir, self.semantic_dir, self.profiles_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Working memory (في الذاكرة فقط)
        self._working_memories: Dict[str, WorkingMemory] = {}
        
        # Vector DB
        self.use_vector_db = use_vector_db
        self.vector_db_type = vector_db_type
        self._vector_db = None
        
        if use_vector_db:
            self._init_vector_db()
        
        logger.info(f"✅ MemoryManager initialized: storage={self.storage_dir}, vector_db={use_vector_db}")
    
    # ========================================================================
    # Working Memory (قصيرة المدى)
    # ========================================================================
    
    def get_working_memory(self, session_id: str) -> WorkingMemory:
        """الحصول على ذاكرة العمل للجلسة"""
        if session_id not in self._working_memories:
            self._working_memories[session_id] = WorkingMemory(
                session_id=session_id,
                started_at=datetime.now(),
            )
        return self._working_memories[session_id]
    
    def clear_working_memory(self, session_id: str) -> None:
        """مسح ذاكرة العمل"""
        if session_id in self._working_memories:
            self._working_memories[session_id].clear()
            logger.info(f"🧹 Cleared working memory for session: {session_id}")
    
    # ========================================================================
    # Episodic Memory (الحلقات السابقة)
    # ========================================================================
    
    def save_episode(
        self,
        agent: str,
        agents_involved: List[str],
        user_query: str,
        intent: str,
        context: Dict[str, Any],
        result: Dict[str, Any],
        success: bool,
        confidence: float,
        decision_path: List[str],
        strategies_used: List[str],
        duration_ms: int,
        company_id: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        حفظ حلقة تفاعل
        
        Returns:
            episode_id: معرف الحلقة
        """
        episode_id = f"ep_{uuid.uuid4().hex[:12]}"
        
        episode = Episode(
            episode_id=episode_id,
            timestamp=datetime.now(),
            agent=agent,
            agents_involved=agents_involved,
            user_query=user_query,
            intent=intent,
            context=context,
            result=result,
            success=success,
            confidence=confidence,
            decision_path=decision_path,
            strategies_used=strategies_used,
            errors_encountered=result.get("errors", []),
            lessons_learned=result.get("lessons_learned", []),
            duration_ms=duration_ms,
            company_id=company_id,
            user_id=user_id,
        )
        
        # حفظ في ملف
        episode_file = self.episodes_dir / f"{episode_id}.json"
        with open(episode_file, "w", encoding="utf-8") as f:
            json.dump(episode.to_dict(), f, ensure_ascii=False, indent=2)
        
        # إضافة إلى Vector DB (إذا مفعّل)
        if self.use_vector_db and self._vector_db:
            self._add_to_vector_db(episode)
        
        logger.info(f"💾 Saved episode: {episode_id} (agent={agent}, success={success})")
        return episode_id
    
    def get_episode(self, episode_id: str) -> Optional[Episode]:
        """الحصول على حلقة بالمعرف"""
        episode_file = self.episodes_dir / f"{episode_id}.json"
        
        if not episode_file.exists():
            return None
        
        with open(episode_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return Episode.from_dict(data)
    
    def search_episodes(
        self,
        query: Optional[str] = None,
        agent: Optional[str] = None,
        intent: Optional[str] = None,
        success: Optional[bool] = None,
        company_id: Optional[int] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        limit: int = 10,
    ) -> List[Episode]:
        """
        البحث في الحلقات السابقة
        
        Args:
            query: استعلام نصي (سيستخدم semantic search إذا مفعّل Vector DB)
            agent: تصفية بالوكيل
            intent: تصفية بالنية
            success: تصفية بالنجاح/الفشل
            company_id: تصفية بالشركة
            time_range: نطاق زمني
            limit: الحد الأقصى للنتائج
        
        Returns:
            قائمة الحلقات المطابقة
        """
        # إذا كان هناك استعلام نصي و Vector DB مفعّل، استخدم semantic search
        if query and self.use_vector_db and self._vector_db:
            return self._semantic_search_episodes(query, filters={
                "agent": agent,
                "intent": intent,
                "success": success,
                "company_id": company_id,
            }, limit=limit)
        
        # وإلا، بحث تقليدي
        episodes = []
        
        for episode_file in self.episodes_dir.glob("*.json"):
            with open(episode_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            episode = Episode.from_dict(data)
            
            # التصفية
            if agent and episode.agent != agent:
                continue
            if intent and episode.intent != intent:
                continue
            if success is not None and episode.success != success:
                continue
            if company_id and episode.company_id != company_id:
                continue
            if time_range:
                start, end = time_range
                if not (start <= episode.timestamp <= end):
                    continue
            
            # بحث نصي بسيط
            if query:
                query_lower = query.lower()
                if not (
                    query_lower in episode.user_query.lower()
                    or any(query_lower in s.lower() for s in episode.strategies_used)
                ):
                    continue
            
            episodes.append(episode)
        
        # ترتيب بالوقت (الأحدث أولاً)
        episodes.sort(key=lambda e: e.timestamp, reverse=True)
        
        return episodes[:limit]
    
    def get_recent_episodes(
        self,
        agent: Optional[str] = None,
        hours: int = 24,
        limit: int = 10,
    ) -> List[Episode]:
        """الحصول على الحلقات الأخيرة"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return self.search_episodes(
            agent=agent,
            time_range=(cutoff, datetime.now()),
            limit=limit,
        )
    
    def get_successful_patterns(
        self,
        agent: str,
        intent: str,
        min_confidence: float = 0.7,
        limit: int = 5,
    ) -> List[Episode]:
        """الحصول على الأنماط الناجحة لوكيل ونية معينة"""
        episodes = self.search_episodes(
            agent=agent,
            intent=intent,
            success=True,
            limit=limit * 2,  # نحضر أكثر ثم نصفي
        )
        
        # تصفية بالثقة
        high_confidence = [e for e in episodes if e.confidence >= min_confidence]
        
        return high_confidence[:limit]
    
    # ========================================================================
    # Semantic Memory (المعرفة الدلالية)
    # ========================================================================
    
    def save_knowledge(
        self,
        category: str,
        concept: str,
        description: str,
        related_concepts: List[str],
        examples: List[str],
        confidence: float,
        source: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        حفظ معرفة دلالية
        
        Returns:
            knowledge_id: معرف المعرفة
        """
        knowledge_id = f"know_{uuid.uuid4().hex[:12]}"
        
        knowledge = SemanticKnowledge(
            knowledge_id=knowledge_id,
            category=category,
            concept=concept,
            description=description,
            related_concepts=related_concepts,
            examples=examples,
            confidence=confidence,
            source=source,
            learned_at=datetime.now(),
            updated_at=datetime.now(),
            usage_count=0,
            tags=tags or [],
            metadata=metadata or {},
        )
        
        # حفظ في ملف
        knowledge_file = self.semantic_dir / f"{knowledge_id}.json"
        with open(knowledge_file, "w", encoding="utf-8") as f:
            json.dump(knowledge.to_dict(), f, ensure_ascii=False, indent=2)
        
        # إضافة إلى Vector DB
        if self.use_vector_db and self._vector_db:
            self._add_knowledge_to_vector_db(knowledge)
        
        logger.info(f"💡 Saved knowledge: {concept} (category={category})")
        return knowledge_id
    
    def get_knowledge(self, knowledge_id: str) -> Optional[SemanticKnowledge]:
        """الحصول على معرفة بالمعرف"""
        knowledge_file = self.semantic_dir / f"{knowledge_id}.json"
        
        if not knowledge_file.exists():
            return None
        
        with open(knowledge_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return SemanticKnowledge.from_dict(data)
    
    def search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[SemanticKnowledge]:
        """البحث في المعرفة الدلالية"""
        if self.use_vector_db and self._vector_db:
            return self._semantic_search_knowledge(query, category, limit)
        
        # بحث تقليدي
        knowledge_list = []
        
        for knowledge_file in self.semantic_dir.glob("*.json"):
            with open(knowledge_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            knowledge = SemanticKnowledge.from_dict(data)
            
            if category and knowledge.category != category:
                continue
            
            # بحث نصي بسيط
            query_lower = query.lower()
            if (
                query_lower in knowledge.concept.lower()
                or query_lower in knowledge.description.lower()
                or any(query_lower in ex.lower() for ex in knowledge.examples)
            ):
                knowledge_list.append(knowledge)
        
        return knowledge_list[:limit]
    
    # ========================================================================
    # Profile Memory (التفضيلات)
    # ========================================================================
    
    def save_profile(
        self,
        profile_id: str,
        profile_type: str,
        preferences: Dict[str, Any],
        language: str = "ar",
    ) -> None:
        """حفظ ملف مستخدم/شركة"""
        profile = UserProfile(
            profile_id=profile_id,
            profile_type=profile_type,
            preferences=preferences,
            language=language,
        )
        
        profile_file = self.profiles_dir / f"{profile_id}.json"
        with open(profile_file, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"👤 Saved profile: {profile_id} (type={profile_type})")
    
    def get_profile(self, profile_id: str) -> Optional[UserProfile]:
        """الحصول على ملف المستخدم"""
        profile_file = self.profiles_dir / f"{profile_id}.json"
        
        if not profile_file.exists():
            return None
        
        with open(profile_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return UserProfile.from_dict(data)
    
    def update_profile_from_episode(
        self,
        profile_id: str,
        episode: Episode,
    ) -> None:
        """تحديث الملف بناءً على حلقة تفاعل"""
        profile = self.get_profile(profile_id)
        
        if not profile:
            # إنشاء ملف جديد
            profile = UserProfile(
                profile_id=profile_id,
                profile_type="user",
                preferences={},
            )
        
        # تحديث الإحصائيات
        profile.interaction_count += 1
        profile.updated_at = datetime.now()
        
        # إضافة الاستعلام للاستعلامات الشائعة
        if episode.user_query not in profile.common_queries:
            profile.common_queries.append(episode.user_query)
            # الحد الأقصى 50 استعلام
            if len(profile.common_queries) > 50:
                profile.common_queries = profile.common_queries[-50:]
        
        # تحديث الوكلاء الأكثر استخداماً
        for agent in episode.agents_involved:
            profile.frequent_agents[agent] = profile.frequent_agents.get(agent, 0) + 1
        
        # حفظ النمط الناجح
        if episode.success and episode.confidence >= 0.7:
            pattern = {
                "intent": episode.intent,
                "agents": episode.agents_involved,
                "strategies": episode.strategies_used,
                "confidence": episode.confidence,
            }
            profile.success_patterns.append(pattern)
            # الحد الأقصى 100 نمط
            if len(profile.success_patterns) > 100:
                profile.success_patterns = profile.success_patterns[-100:]
        
        # حفظ
        profile_file = self.profiles_dir / f"{profile_id}.json"
        with open(profile_file, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
    
    # ========================================================================
    # Vector DB (Phase 5.2 - سنضيفه لاحقاً)
    # ========================================================================
    
    def _init_vector_db(self) -> None:
        """تهيئة Vector DB (Chroma)"""
        try:
            from memory.vector_store import VectorStore
            
            vector_db_dir = self.storage_dir / "vector_db"
            self._vector_db = VectorStore(persist_directory=vector_db_dir)
            
            logger.info(f"✅ Vector DB initialized: {self._vector_db.get_stats()}")
        except ImportError:
            logger.warning("⚠️ ChromaDB not available. Install with: pip install chromadb")
            self.use_vector_db = False
        except Exception as e:
            logger.error(f"❌ Failed to initialize Vector DB: {e}")
            self.use_vector_db = False
    
    def _add_to_vector_db(self, episode: Episode) -> None:
        """إضافة حلقة إلى Vector DB"""
        if not self._vector_db:
            return
        
        try:
            from memory.vector_store import prepare_episode_text
            
            # تحضير النص
            text = prepare_episode_text(episode.to_dict())
            
            # metadata للتصفية
            metadata = {
                "agent": episode.agent,
                "intent": episode.intent,
                "success": episode.success,
                "confidence": episode.confidence,
                "timestamp": episode.timestamp.isoformat(),
            }
            
            if episode.company_id:
                metadata["company_id"] = episode.company_id
            
            self._vector_db.add_episode(
                episode_id=episode.episode_id,
                text=text,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"❌ Failed to add episode to vector DB: {e}")
    
    def _add_knowledge_to_vector_db(self, knowledge: SemanticKnowledge) -> None:
        """إضافة معرفة إلى Vector DB"""
        if not self._vector_db:
            return
        
        try:
            from memory.vector_store import prepare_knowledge_text
            
            # تحضير النص
            text = prepare_knowledge_text(knowledge.to_dict())
            
            # metadata
            metadata = {
                "category": knowledge.category,
                "confidence": knowledge.confidence,
                "source": knowledge.source,
                "usage_count": knowledge.usage_count,
            }
            
            self._vector_db.add_knowledge(
                knowledge_id=knowledge.knowledge_id,
                text=text,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"❌ Failed to add knowledge to vector DB: {e}")
    
    def _semantic_search_episodes(
        self,
        query: str,
        filters: Dict[str, Any],
        limit: int,
    ) -> List[Episode]:
        """بحث دلالي في الحلقات"""
        if not self._vector_db:
            return []
        
        try:
            # البحث في Vector DB
            results = self._vector_db.search_episodes(
                query=query,
                filters=filters,
                limit=limit,
            )
            
            # تحميل الحلقات الكاملة
            episodes = []
            for result in results:
                episode = self.get_episode(result["episode_id"])
                if episode:
                    episodes.append(episode)
            
            return episodes
        except Exception as e:
            logger.error(f"❌ Semantic search failed: {e}")
            return []
    
    def _semantic_search_knowledge(
        self,
        query: str,
        category: Optional[str],
        limit: int,
    ) -> List[SemanticKnowledge]:
        """بحث دلالي في المعرفة"""
        if not self._vector_db:
            return []
        
        try:
            # البحث في Vector DB
            results = self._vector_db.search_knowledge(
                query=query,
                category=category,
                limit=limit,
            )
            
            # تحميل المعرفة الكاملة
            knowledge_list = []
            for result in results:
                knowledge = self.get_knowledge(result["knowledge_id"])
                if knowledge:
                    knowledge_list.append(knowledge)
            
            return knowledge_list
        except Exception as e:
            logger.error(f"❌ Semantic search failed: {e}")
            return []
    
    # ========================================================================
    # Statistics & Insights
    # ========================================================================
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """الحصول على إحصائيات الذاكرة"""
        episode_count = len(list(self.episodes_dir.glob("*.json")))
        knowledge_count = len(list(self.semantic_dir.glob("*.json")))
        profile_count = len(list(self.profiles_dir.glob("*.json")))
        
        return {
            "episodes": episode_count,
            "semantic_knowledge": knowledge_count,
            "profiles": profile_count,
            "working_memories": len(self._working_memories),
            "storage_dir": str(self.storage_dir),
            "vector_db_enabled": self.use_vector_db,
        }
