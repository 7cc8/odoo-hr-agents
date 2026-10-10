"""
Memory Types and Data Structures
=================================

تعريفات أنواع الذاكرة المختلفة
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MemoryType(str, Enum):
    """أنواع الذاكرة"""
    WORKING = "working"  # ذاكرة قصيرة المدى (session)
    EPISODIC = "episodic"  # ذاكرة الحلقات (past interactions)
    SEMANTIC = "semantic"  # ذاكرة دلالية (general knowledge)
    PROFILE = "profile"  # ذاكرة التفضيلات (user/company preferences)


@dataclass
class Episode:
    """
    حلقة تفاعل واحدة (Episodic Memory)
    
    تمثل تفاعل كامل مع وكيل واحد أو أكثر
    """
    episode_id: str
    timestamp: datetime
    agent: str  # الوكيل الرئيسي
    agents_involved: List[str]  # جميع الوكلاء المشاركة
    
    # المدخلات
    user_query: str
    intent: str
    context: Dict[str, Any]
    
    # المخرجات
    result: Dict[str, Any]
    success: bool
    confidence: float
    
    # التعلم
    decision_path: List[str]  # مسار القرارات المتخذة
    strategies_used: List[str]  # الاستراتيجيات المستخدمة
    errors_encountered: List[str]  # الأخطاء التي واجهتها
    lessons_learned: List[str]  # الدروس المستفادة
    
    # Metadata
    duration_ms: int
    company_id: Optional[int] = None
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى dictionary للتخزين"""
        return {
            "episode_id": self.episode_id,
            "timestamp": self.timestamp.isoformat(),
            "agent": self.agent,
            "agents_involved": self.agents_involved,
            "user_query": self.user_query,
            "intent": self.intent,
            "context": self.context,
            "result": self.result,
            "success": self.success,
            "confidence": self.confidence,
            "decision_path": self.decision_path,
            "strategies_used": self.strategies_used,
            "errors_encountered": self.errors_encountered,
            "lessons_learned": self.lessons_learned,
            "duration_ms": self.duration_ms,
            "company_id": self.company_id,
            "user_id": self.user_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Episode":
        """إنشاء من dictionary"""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class SemanticKnowledge:
    """
    معرفة دلالية (Semantic Memory)
    
    تمثل مفهوم أو معرفة عامة تعلمها النظام
    """
    knowledge_id: str
    category: str  # employee, department, policy, procedure, etc.
    concept: str  # المفهوم الرئيسي
    description: str
    
    # العلاقات
    related_concepts: List[str]  # مفاهيم مرتبطة
    examples: List[str]  # أمثلة
    
    # التعلم
    confidence: float  # ثقة النظام في هذه المعرفة
    source: str  # من أين تعلمها؟ (episodes, rules, manual)
    learned_at: datetime
    updated_at: datetime
    usage_count: int = 0  # كم مرة استُخدمت؟
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى dictionary"""
        return {
            "knowledge_id": self.knowledge_id,
            "category": self.category,
            "concept": self.concept,
            "description": self.description,
            "related_concepts": self.related_concepts,
            "examples": self.examples,
            "confidence": self.confidence,
            "source": self.source,
            "learned_at": self.learned_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "usage_count": self.usage_count,
            "tags": self.tags,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticKnowledge":
        """إنشاء من dictionary"""
        data["learned_at"] = datetime.fromisoformat(data["learned_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


@dataclass
class UserProfile:
    """
    ملف المستخدم (Profile Memory)
    
    تفضيلات وسلوك المستخدم أو الشركة
    """
    profile_id: str
    profile_type: str  # user, company
    
    # التفضيلات
    preferences: Dict[str, Any]  # تفضيلات عامة
    language: str = "ar"
    timezone: str = "UTC"
    
    # السلوك
    common_queries: List[str] = field(default_factory=list)  # استعلامات شائعة
    frequent_agents: Dict[str, int] = field(default_factory=dict)  # الوكلاء الأكثر استخداماً
    success_patterns: List[Dict[str, Any]] = field(default_factory=list)  # أنماط ناجحة
    
    # التعلم
    learned_preferences: Dict[str, Any] = field(default_factory=dict)  # تفضيلات متعلمة
    avoided_patterns: List[str] = field(default_factory=list)  # أنماط يتجنبها
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    interaction_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى dictionary"""
        return {
            "profile_id": self.profile_id,
            "profile_type": self.profile_type,
            "preferences": self.preferences,
            "language": self.language,
            "timezone": self.timezone,
            "common_queries": self.common_queries,
            "frequent_agents": self.frequent_agents,
            "success_patterns": self.success_patterns,
            "learned_preferences": self.learned_preferences,
            "avoided_patterns": self.avoided_patterns,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "interaction_count": self.interaction_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        """إنشاء من dictionary"""
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


@dataclass
class WorkingMemory:
    """
    ذاكرة العمل (Working Memory)
    
    ذاكرة قصيرة المدى للجلسة الحالية فقط
    """
    session_id: str
    started_at: datetime
    
    # السياق الحالي
    current_query: str = ""
    current_intent: str = ""
    current_agent: Optional[str] = None
    
    # التاريخ الحديث
    recent_messages: List[Dict[str, Any]] = field(default_factory=list)
    recent_decisions: List[str] = field(default_factory=list)
    
    # الحالة
    active_agents: List[str] = field(default_factory=list)
    pending_actions: List[str] = field(default_factory=list)
    
    # Temporary data
    temp_data: Dict[str, Any] = field(default_factory=dict)
    
    def clear(self) -> None:
        """مسح الذاكرة"""
        self.recent_messages = []
        self.recent_decisions = []
        self.active_agents = []
        self.pending_actions = []
        self.temp_data = {}
