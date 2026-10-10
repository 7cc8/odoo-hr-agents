"""
Vector Store Integration - Chroma DB
====================================

دمج ChromaDB لـ semantic search على الذاكرة
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logging.warning("⚠️ ChromaDB not installed. Run: pip install chromadb")

logger = logging.getLogger("memory.vector_store")


class VectorStore:
    """
    Vector Store باستخدام ChromaDB
    
    يوفر semantic search على:
    1. Episodes (الحلقات السابقة)
    2. Semantic Knowledge (المعرفة الدلالية)
    """
    
    def __init__(
        self,
        persist_directory: Optional[Path] = None,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        """
        Args:
            persist_directory: مجلد حفظ البيانات (افتراضي: ./chroma_db)
            embedding_model: نموذج التضمين (افتراضي: all-MiniLM-L6-v2 سريع وخفيف)
        """
        if not CHROMA_AVAILABLE:
            raise ImportError(
                "ChromaDB not installed. Install with: pip install chromadb"
            )
        
        self.persist_directory = persist_directory or Path("./chroma_db")
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # تهيئة ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )
        
        # Collections
        self.episodes_collection = self.client.get_or_create_collection(
            name="episodes",
            metadata={"description": "Episodic memory - past interactions"},
        )
        
        self.knowledge_collection = self.client.get_or_create_collection(
            name="semantic_knowledge",
            metadata={"description": "Semantic memory - general knowledge"},
        )
        
        logger.info(f"✅ VectorStore initialized: {self.persist_directory}")
        logger.info(f"   Episodes: {self.episodes_collection.count()} items")
        logger.info(f"   Knowledge: {self.knowledge_collection.count()} items")
    
    # ========================================================================
    # Episodes
    # ========================================================================
    
    def add_episode(
        self,
        episode_id: str,
        text: str,
        metadata: Dict[str, Any],
    ) -> None:
        """
        إضافة حلقة إلى Vector DB
        
        Args:
            episode_id: معرف الحلقة
            text: النص للتضمين (user_query + strategies + result)
            metadata: بيانات إضافية (agent, intent, success, confidence, etc.)
        """
        try:
            self.episodes_collection.add(
                ids=[episode_id],
                documents=[text],
                metadatas=[metadata],
            )
            logger.debug(f"Added episode to vector store: {episode_id}")
        except Exception as e:
            logger.error(f"❌ Failed to add episode {episode_id}: {e}")
    
    def search_episodes(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        البحث الدلالي في الحلقات
        
        Args:
            query: استعلام نصي
            filters: تصفية بـ metadata (agent, intent, success, etc.)
            limit: عدد النتائج
        
        Returns:
            قائمة النتائج مع distances و metadata
        """
        try:
            # بناء where clause من filters
            where_clause = None
            if filters:
                # تحويل filters إلى Chroma where format
                where_clause = {}
                for key, value in filters.items():
                    if value is not None:
                        where_clause[key] = value
            
            results = self.episodes_collection.query(
                query_texts=[query],
                n_results=limit,
                where=where_clause if where_clause else None,
            )
            
            # تنسيق النتائج
            formatted_results = []
            
            if results["ids"] and results["ids"][0]:
                for i, episode_id in enumerate(results["ids"][0]):
                    formatted_results.append({
                        "episode_id": episode_id,
                        "distance": results["distances"][0][i] if results.get("distances") else 0.0,
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                        "document": results["documents"][0][i] if results.get("documents") else "",
                    })
            
            logger.debug(f"Vector search found {len(formatted_results)} episodes for: '{query[:50]}...'")
            return formatted_results
        
        except Exception as e:
            logger.error(f"❌ Episode search failed: {e}")
            return []
    
    def get_similar_episodes(
        self,
        episode_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        الحصول على حلقات مشابهة لحلقة معينة
        
        Args:
            episode_id: معرف الحلقة المرجعية
            limit: عدد النتائج
        
        Returns:
            قائمة الحلقات المشابهة
        """
        try:
            # الحصول على الحلقة الأصلية
            result = self.episodes_collection.get(
                ids=[episode_id],
                include=["documents"],
            )
            
            if not result["documents"]:
                logger.warning(f"Episode {episode_id} not found in vector store")
                return []
            
            # البحث بنفس النص
            document = result["documents"][0]
            similar = self.search_episodes(
                query=document,
                limit=limit + 1,  # +1 لأنه سيرجع نفسه
            )
            
            # إزالة الحلقة نفسها
            similar = [s for s in similar if s["episode_id"] != episode_id]
            
            return similar[:limit]
        
        except Exception as e:
            logger.error(f"❌ Failed to get similar episodes: {e}")
            return []
    
    # ========================================================================
    # Semantic Knowledge
    # ========================================================================
    
    def add_knowledge(
        self,
        knowledge_id: str,
        text: str,
        metadata: Dict[str, Any],
    ) -> None:
        """
        إضافة معرفة إلى Vector DB
        
        Args:
            knowledge_id: معرف المعرفة
            text: النص للتضمين (concept + description + examples)
            metadata: بيانات إضافية (category, confidence, etc.)
        """
        try:
            self.knowledge_collection.add(
                ids=[knowledge_id],
                documents=[text],
                metadatas=[metadata],
            )
            logger.debug(f"Added knowledge to vector store: {knowledge_id}")
        except Exception as e:
            logger.error(f"❌ Failed to add knowledge {knowledge_id}: {e}")
    
    def search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        البحث الدلالي في المعرفة
        
        Args:
            query: استعلام نصي
            category: تصفية بالفئة
            limit: عدد النتائج
        
        Returns:
            قائمة النتائج
        """
        try:
            where_clause = None
            if category:
                where_clause = {"category": category}
            
            results = self.knowledge_collection.query(
                query_texts=[query],
                n_results=limit,
                where=where_clause,
            )
            
            # تنسيق النتائج
            formatted_results = []
            
            if results["ids"] and results["ids"][0]:
                for i, knowledge_id in enumerate(results["ids"][0]):
                    formatted_results.append({
                        "knowledge_id": knowledge_id,
                        "distance": results["distances"][0][i] if results.get("distances") else 0.0,
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                        "document": results["documents"][0][i] if results.get("documents") else "",
                    })
            
            logger.debug(f"Vector search found {len(formatted_results)} knowledge for: '{query[:50]}...'")
            return formatted_results
        
        except Exception as e:
            logger.error(f"❌ Knowledge search failed: {e}")
            return []
    
    # ========================================================================
    # Utilities
    # ========================================================================
    
    def delete_episode(self, episode_id: str) -> bool:
        """حذف حلقة من Vector DB"""
        try:
            self.episodes_collection.delete(ids=[episode_id])
            logger.debug(f"Deleted episode from vector store: {episode_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete episode {episode_id}: {e}")
            return False
    
    def delete_knowledge(self, knowledge_id: str) -> bool:
        """حذف معرفة من Vector DB"""
        try:
            self.knowledge_collection.delete(ids=[knowledge_id])
            logger.debug(f"Deleted knowledge from vector store: {knowledge_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete knowledge {knowledge_id}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """الحصول على إحصائيات Vector Store"""
        return {
            "episodes_count": self.episodes_collection.count(),
            "knowledge_count": self.knowledge_collection.count(),
            "persist_directory": str(self.persist_directory),
        }
    
    def reset(self) -> None:
        """⚠️ مسح كل البيانات (للتطوير فقط!)"""
        logger.warning("⚠️ Resetting vector store - all data will be lost!")
        self.client.reset()
        
        # إعادة إنشاء collections
        self.episodes_collection = self.client.get_or_create_collection("episodes")
        self.knowledge_collection = self.client.get_or_create_collection("semantic_knowledge")
        
        logger.info("✅ Vector store reset complete")


def prepare_episode_text(episode_data: Dict[str, Any]) -> str:
    """
    تحضير نص الحلقة للتضمين
    
    يدمج: user_query + intent + strategies + result summary
    """
    parts = [
        f"Query: {episode_data.get('user_query', '')}",
        f"Intent: {episode_data.get('intent', '')}",
    ]
    
    if episode_data.get("strategies_used"):
        strategies = ", ".join(episode_data["strategies_used"])
        parts.append(f"Strategies: {strategies}")
    
    if episode_data.get("result"):
        result = episode_data["result"]
        if isinstance(result, dict):
            if result.get("success"):
                parts.append("Result: Success")
            else:
                parts.append(f"Result: Failed - {result.get('error', 'unknown')}")
    
    if episode_data.get("lessons_learned"):
        lessons = " | ".join(episode_data["lessons_learned"][:2])  # أول 2 فقط
        parts.append(f"Lessons: {lessons}")
    
    return " | ".join(parts)


def prepare_knowledge_text(knowledge_data: Dict[str, Any]) -> str:
    """
    تحضير نص المعرفة للتضمين
    
    يدمج: concept + description + examples
    """
    parts = [
        f"Concept: {knowledge_data.get('concept', '')}",
        f"Description: {knowledge_data.get('description', '')}",
    ]
    
    if knowledge_data.get("examples"):
        examples = " | ".join(knowledge_data["examples"][:3])  # أول 3 أمثلة
        parts.append(f"Examples: {examples}")
    
    if knowledge_data.get("related_concepts"):
        related = ", ".join(knowledge_data["related_concepts"][:3])
        parts.append(f"Related: {related}")
    
    return " | ".join(parts)
