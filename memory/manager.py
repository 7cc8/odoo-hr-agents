"""
Memory Manager - مدير الذاكرة الموحد
====================================

يدير جميع أنواع الذاكرة ويوفر واجهة موحدة
"""

import json
import logging
import os
import sqlite3
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
    
    _instance: Optional["MemoryManager"] = None

    @classmethod
    def get_instance(
        cls,
        storage_dir: Optional[Path] = None,
        use_vector_db: bool = False,
        vector_db_type: str = "chroma",
    ) -> "MemoryManager":
        """Singleton accessor for shared memory across all agents and sessions."""
        if cls._instance is None:
            cls._instance = cls(
                storage_dir=storage_dir,
                use_vector_db=use_vector_db,
                vector_db_type=vector_db_type,
            )
        return cls._instance

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
        
        # SQLite Database (قاعدة بيانات الذاكرة الموحدة للحقائق والحلقات)
        self.db_path = self.storage_dir / "memory.db"
        self._init_sqlite_db()

        if use_vector_db:
            self._init_vector_db()
        
        logger.info(f"✅ MemoryManager initialized: storage={self.storage_dir}, vector_db={use_vector_db}")

    def _get_db_connection(self) -> sqlite3.Connection:
        """فتح اتصال آمن بقاعدة بيانات الذاكرة SQLite"""
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite_db(self) -> None:
        """تهيئة قاعدة بيانات SQLite للذاكرة وترحيل الحلقات والحقائق التراكمية"""
        try:
            with self._get_db_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS facts (
                        id TEXT PRIMARY KEY,
                        key TEXT,
                        content TEXT,
                        category TEXT,
                        importance INTEGER,
                        created_at TEXT,
                        updated_at TEXT
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS episodes (
                        id TEXT PRIMARY KEY,
                        episode_id TEXT UNIQUE,
                        agent TEXT,
                        agents_involved TEXT,
                        user_query TEXT,
                        result_summary TEXT,
                        success INTEGER,
                        created_at TEXT,
                        raw_json TEXT
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoints (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        checkpoint_id TEXT UNIQUE,
                        operation_id TEXT,
                        chat_id TEXT,
                        agent_name TEXT,
                        turn_number INTEGER,
                        state_json TEXT,
                        created_at TEXT
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS rag_chunks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chunk_id TEXT UNIQUE,
                        category TEXT,
                        article_number TEXT,
                        title TEXT,
                        content TEXT,
                        source TEXT,
                        metadata_json TEXT,
                        created_at TEXT
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS token_usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT,
                        operation_id TEXT,
                        agent_name TEXT,
                        model TEXT,
                        provider TEXT,
                        prompt_tokens INTEGER,
                        completion_tokens INTEGER,
                        total_tokens INTEGER,
                        estimated_cost_usd REAL,
                        latency_ms REAL,
                        created_at TEXT
                    )
                """)
                conn.execute("CREATE VIEW IF NOT EXISTS long_term_facts AS SELECT * FROM facts")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_created_at ON episodes(created_at)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_agent ON episodes(agent)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_op ON checkpoints(operation_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_chat ON checkpoints(chat_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_cat ON rag_chunks(category)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_art ON rag_chunks(article_number)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_chat ON token_usage(chat_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_op ON token_usage(operation_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_created ON token_usage(created_at)")

                # محاولة إنشاء جدول FTS5 إذا كانت إضافة fts5 مفعلة في نسخة SQLite
                try:
                    conn.execute("""
                        CREATE VIRTUAL TABLE IF NOT EXISTS rag_fts USING fts5(
                            title,
                            content,
                            category,
                            source,
                            tokenize='unicode61'
                        )
                    """)
                except Exception as fts_err:
                    logger.debug("FTS5 table creation notice: %s", fts_err)

                conn.commit()

                # 1. ترحيل الحقائق إذا كان الجدول فارغاً
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM facts")
                facts_count = cur.fetchone()[0]
                if facts_count == 0:
                    facts_from_json = self._read_long_term_facts_raw()
                    if not facts_from_json:
                        now_iso = datetime.now().isoformat()
                        facts_from_json = [
                            {
                                "id": "fact_seed_01",
                                "key": "ضوابط نظام العمل السعودي",
                                "content": "الالتزام التام بنظام العمل السعودي (المرسوم الملكي م/51): المادة 84 لمكافأة نهاية الخدمة، المادة 107 لساعات العمل الإضافية، المادة 109 للإجازة السنوية.",
                                "category": "نظام العمل",
                                "importance": 5,
                                "created_at": now_iso,
                                "updated_at": now_iso
                            },
                            {
                                "id": "fact_seed_02",
                                "key": "حوكمة بوابة الاعتماد البشري (HITL)",
                                "content": "لا يتم تنفيذ أي عملية إنشاء أو تعديل لموظف أو عقد داخل Odoo إلا عبر خطة عمل موقعة من الوكيل «حارس» ومعتمدة صراحة من المشغّل البشري.",
                                "category": "الحوكمة والأمان",
                                "importance": 5,
                                "created_at": now_iso,
                                "updated_at": now_iso
                            },
                            {
                                "id": "fact_seed_03",
                                "key": "سياسة استقطاعات التأمينات GOSI",
                                "content": "الموظف السعودي يخضع لـ 9.75% (معاشات 9% + ساند 0.75%) بحد أقصى للأجر الخاضع 45,000 ريال، والموظف غير السعودي 2% أخطار مهنية تتحملها المنشأة.",
                                "category": "التأمينات الاجتماعية",
                                "importance": 4,
                                "created_at": now_iso,
                                "updated_at": now_iso
                            }
                        ]
                    for f in facts_from_json:
                        conn.execute(
                            "INSERT OR REPLACE INTO facts (id, key, content, category, importance, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                f.get("id", f"fact_{uuid.uuid4().hex[:8]}"),
                                f.get("key", ""),
                                f.get("content", ""),
                                f.get("category", "general"),
                                int(f.get("importance", 3)),
                                f.get("created_at", datetime.now().isoformat()),
                                f.get("updated_at", datetime.now().isoformat())
                            )
                        )
                    conn.commit()
                    self._write_long_term_facts_raw(facts_from_json)

                # 2. ترحيل سجل حلقات الذاكرة (Episodes) السابقة إلى SQLite
                cur.execute("SELECT COUNT(*) FROM episodes")
                episodes_count = cur.fetchone()[0]
                ep_files = list(self.episodes_dir.glob("*.json"))
                if episodes_count < len(ep_files):
                    batch = []
                    for ep_file in ep_files:
                        try:
                            with open(ep_file, "r", encoding="utf-8") as ef:
                                data = json.load(ef)
                            ep_id = data.get("episode_id") or ep_file.stem
                            ag = data.get("agent") or "unknown"
                            ag_inv = json.dumps(data.get("agents_involved") or [], ensure_ascii=False)
                            u_query = data.get("user_query") or ""
                            res = data.get("result") or {}
                            res_sum = ""
                            if isinstance(res, dict):
                                res_sum = str(res.get("summary") or res.get("reply") or res.get("status") or "")[:500]
                            elif isinstance(res, str):
                                res_sum = res[:500]
                            succ = 1 if data.get("success", True) else 0
                            c_at = str(data.get("timestamp") or datetime.now().isoformat())
                            batch.append((
                                f"ep_{ep_id}",
                                ep_id,
                                ag,
                                ag_inv,
                                u_query,
                                res_sum,
                                succ,
                                c_at,
                                json.dumps(data, ensure_ascii=False, default=str)
                            ))
                            if len(batch) >= 100:
                                conn.executemany(
                                    "INSERT OR IGNORE INTO episodes (id, episode_id, agent, agents_involved, user_query, result_summary, success, created_at, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                    batch
                                )
                                conn.commit()
                                batch = []
                        except Exception:
                            continue
                    if batch:
                        conn.executemany(
                            "INSERT OR IGNORE INTO episodes (id, episode_id, agent, agents_involved, user_query, result_summary, success, created_at, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            batch
                        )
                        conn.commit()
        except Exception as e:
            logger.error(f"Error initializing SQLite memory db: {e}", exc_info=True)

    
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
        
        # حفظ في ملف بشكل ذري وآمن
        episode_file = self.episodes_dir / f"{episode_id}.json"
        payload_str = "{}"
        try:
            payload_str = json.dumps(episode.to_dict(), ensure_ascii=False, indent=2, default=str)
            with open(episode_file, "w", encoding="utf-8") as f:
                f.write(payload_str)
        except Exception as write_err:
            logger.warning(f"Failed to write episode {episode_id}: {write_err}")

        # تسجيل الحلقة فوراً في قاعدة بيانات SQLite
        try:
            with self._get_db_connection() as conn:
                res_sum = ""
                if isinstance(result, dict):
                    res_sum = str(result.get("summary") or result.get("reply") or result.get("status") or "")[:500]
                elif isinstance(result, str):
                    res_sum = result[:500]
                conn.execute(
                    "INSERT OR REPLACE INTO episodes (id, episode_id, agent, agents_involved, user_query, result_summary, success, created_at, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"ep_{episode_id}",
                        episode_id,
                        agent,
                        json.dumps(agents_involved, ensure_ascii=False),
                        user_query,
                        res_sum,
                        1 if success else 0,
                        datetime.now().isoformat(),
                        payload_str,
                    )
                )
                conn.commit()
        except Exception as sqle:
            logger.warning(f"Failed to record episode in SQLite: {sqle}")
        
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
        
        # وإلا، بحث تقليدي فائق السرعة عبر scandir مع فرز زمني للأحدث
        episodes = []
        file_entries = []
        try:
            with os.scandir(self.episodes_dir) as it:
                for entry in it:
                    if entry.name.endswith(".json"):
                        file_entries.append((entry.stat().st_mtime, entry.path))
            file_entries.sort(key=lambda x: x[0], reverse=True)
        except Exception:
            file_entries = [(p.stat().st_mtime, str(p)) for p in self.episodes_dir.glob("*.json")]

        cutoff_ts = time_range[0].timestamp() if time_range else None
        
        for mtime, episode_path in file_entries:
            # تخطي سريع للملفات الأقدم من النطاق الزمني المحدد
            if cutoff_ts and mtime < (cutoff_ts - 3600):
                break

            try:
                with open(episode_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                episode = Episode.from_dict(data)
            except Exception:
                continue
            
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
        """الحصول على إحصائيات الذاكرة الموحدة من SQLite ومحرك الملفات"""
        try:
            with self._get_db_connection() as conn:
                ep_count = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
                facts_count = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        except Exception:
            ep_count = len(list(self.episodes_dir.glob("*.json")))
            facts_count = len(self._read_long_term_facts_raw())

        knowledge_count = len(list(self.semantic_dir.glob("*.json")))
        profile_count = len(list(self.profiles_dir.glob("*.json")))
        
        return {
            "episodes": ep_count,
            "semantic_knowledge": knowledge_count,
            "profiles": profile_count,
            "working_memories": len(self._working_memories),
            "long_term_facts": facts_count,
            "storage_dir": str(self.storage_dir),
            "storage_engine": "SQLite (memory_store/memory.db)",
            "vector_db_enabled": self.use_vector_db,
        }

    # ========================================================================
    # Long-Term Facts & Episodes Persistence (قاعدة بيانات SQLite والذاكرة التراكمية)
    # ========================================================================

    @property
    def long_term_facts_path(self) -> Path:
        return self.storage_dir / "long_term_facts.json"

    def _read_long_term_facts_raw(self) -> List[Dict[str, Any]]:
        p = self.long_term_facts_path
        if not p.exists():
            return []
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning("Failed to read long term facts: %s", e)
            return []

    def _write_long_term_facts_raw(self, facts: List[Dict[str, Any]]) -> None:
        p = self.long_term_facts_path
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(facts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to write long term facts: %s", e)

    def get_long_term_facts(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """الحصول على كافة حقائق وقواعد الذاكرة طويلة المدى من SQLite."""
        try:
            with self._get_db_connection() as conn:
                if category:
                    rows = conn.execute("SELECT * FROM facts WHERE category = ? ORDER BY created_at DESC", (category,)).fetchall()
                else:
                    rows = conn.execute("SELECT * FROM facts ORDER BY created_at DESC").fetchall()
                facts = [dict(r) for r in rows]
                if facts:
                    return facts
        except Exception as e:
            logger.warning(f"Failed reading facts from SQLite: {e}")
        facts = self._read_long_term_facts_raw()
        if category:
            facts = [f for f in facts if f.get("category") == category]
        return sorted(facts, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_long_term_fact(self, fact_id: str) -> Optional[Dict[str, Any]]:
        """الحصول على حقيقة محددة بالمعرف."""
        try:
            with self._get_db_connection() as conn:
                row = conn.execute("SELECT * FROM facts WHERE id = ?", (fact_id,)).fetchone()
                if row:
                    return dict(row)
        except Exception:
            pass
        for f in self._read_long_term_facts_raw():
            if f.get("id") == fact_id:
                return f
        return None

    def save_long_term_fact(
        self,
        content: str,
        key: str = "",
        category: str = "general",
        importance: int = 3,
        fact_id: Optional[str] = None,
        require_sqlite: bool = False,
    ) -> Dict[str, Any]:
        """حفظ أو إنشاء حقيقة جديدة في الذاكرة طويلة المدى في SQLite ومزامنتها مع JSON."""
        now_iso = datetime.now().isoformat()
        clean_content = content.strip()
        clean_key = (key or clean_content[:30]).strip()
        target_id = fact_id or f"fact_{uuid.uuid4().hex[:8]}"
        record = {
            "id": target_id,
            "key": clean_key,
            "content": clean_content,
            "category": category or "general",
            "importance": max(1, min(5, int(importance or 3))),
            "created_at": now_iso,
            "updated_at": now_iso,
        }

        try:
            with self._get_db_connection() as conn:
                existing = conn.execute("SELECT created_at FROM facts WHERE id = ?", (target_id,)).fetchone()
                if existing:
                    record["created_at"] = existing["created_at"]
                conn.execute(
                    "INSERT OR REPLACE INTO facts (id, key, content, category, importance, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        record["id"],
                        record["key"],
                        record["content"],
                        record["category"],
                        record["importance"],
                        record["created_at"],
                        record["updated_at"],
                    )
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving fact to SQLite: {e}")
            if require_sqlite:
                raise

        # تزامن مع ملف JSON للاحتياط
        facts = self._read_long_term_facts_raw()
        facts = [f for f in facts if f.get("id") != target_id]
        facts.insert(0, record)
        try:
            self._write_long_term_facts_raw(facts)
        except OSError:
            if not require_sqlite:
                raise
            logger.warning("Fact saved to SQLite but its JSON mirror could not be refreshed")
        logger.info(f"💾 Long-term fact saved to SQLite & JSON: {record['key']} ({record['id']})")
        return record

    def update_long_term_fact(self, fact_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """تحديث حقيقة قائمة في SQLite."""
        record = self.get_long_term_fact(fact_id)
        if not record:
            return None
        for k in ("key", "content", "category", "importance"):
            if k in updates and updates[k] is not None:
                record[k] = updates[k]
        record["updated_at"] = datetime.now().isoformat()
        try:
            with self._get_db_connection() as conn:
                conn.execute(
                    "UPDATE facts SET key=?, content=?, category=?, importance=?, updated_at=? WHERE id=?",
                    (record["key"], record["content"], record["category"], record["importance"], record["updated_at"], fact_id)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating fact in SQLite: {e}")

        # مزامنة JSON
        facts = self._read_long_term_facts_raw()
        for idx, f in enumerate(facts):
            if f.get("id") == fact_id:
                facts[idx] = record
                break
        self._write_long_term_facts_raw(facts)
        return record

    def delete_long_term_fact(self, fact_id: str) -> bool:
        """حذف حقيقة من الذاكرة طويلة المدى في SQLite و JSON."""
        ok = False
        try:
            with self._get_db_connection() as conn:
                cur = conn.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
                conn.commit()
                ok = cur.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting fact from SQLite: {e}")

        facts = self._read_long_term_facts_raw()
        filtered = [f for f in facts if f.get("id") != fact_id]
        if len(filtered) < len(facts):
            self._write_long_term_facts_raw(filtered)
            ok = True
        logger.info(f"🗑️ Long-term fact deleted: {fact_id} (success={ok})")
        return ok

    def clear_long_term_facts(self) -> int:
        """مسح كافة الحقائق المحفوظة في الذاكرة طويلة المدى."""
        count = 0
        try:
            with self._get_db_connection() as conn:
                cur = conn.execute("DELETE FROM facts")
                conn.commit()
                count = cur.rowcount
        except Exception as e:
            logger.error(f"Error clearing facts from SQLite: {e}")
        self._write_long_term_facts_raw([])
        logger.info(f"🧹 Cleared {count} long-term facts.")
        return count

    def get_episodes_list(self, limit: int = 50, offset: int = 0, q: Optional[str] = None) -> Dict[str, Any]:
        """استرجاع قائمة حلقات الذاكرة من SQLite مع دعم البحث والتصفح"""
        try:
            with self._get_db_connection() as conn:
                if q and q.strip():
                    pattern = f"%{q.strip()}%"
                    total = conn.execute(
                        "SELECT COUNT(*) FROM episodes WHERE user_query LIKE ? OR result_summary LIKE ? OR agent LIKE ?",
                        (pattern, pattern, pattern)
                    ).fetchone()[0]
                    rows = conn.execute(
                        "SELECT episode_id, agent, agents_involved, user_query, result_summary, success, created_at FROM episodes WHERE user_query LIKE ? OR result_summary LIKE ? OR agent LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                        (pattern, pattern, pattern, limit, offset)
                    ).fetchall()
                else:
                    total = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
                    rows = conn.execute(
                        "SELECT episode_id, agent, agents_involved, user_query, result_summary, success, created_at FROM episodes ORDER BY created_at DESC LIMIT ? OFFSET ?",
                        (limit, offset)
                    ).fetchall()
                items = [dict(r) for r in rows]
                for item in items:
                    if isinstance(item.get("agents_involved"), str):
                        try:
                            item["agents_involved"] = json.loads(item["agents_involved"])
                        except Exception:
                            item["agents_involved"] = [item.get("agent")]
                return {"items": items, "total": total, "limit": limit, "offset": offset}
        except Exception as e:
            logger.error(f"Error reading episodes from SQLite: {e}")
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

    def get_long_term_summary(self, max_items: int = 10) -> str:
        """توليد ملخص نصي موجز للحقائق لحقنها في الـ System Prompt لسراج."""
        facts = self.get_long_term_facts()
        if not facts:
            return ""
        lines = []
        for f in facts[:max_items]:
            cat = f.get("category", "عام")
            title = f.get("key") or "معلومة"
            cnt = f.get("content", "").replace("\n", " ").strip()
            lines.append(f"• [{cat}] {title}: {cnt}")
        return "\n".join(lines)
