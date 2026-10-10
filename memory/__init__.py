"""
Memory System for Odoo HR Agents
=================================

نظام ذاكرة موحد لجميع الوكلاء مع 4 أنواع:

1. **Working Memory**: ذاكرة قصيرة المدى (الجلسة الحالية)
2. **Episodic Memory**: ذاكرة الحلقات (تفاعلات سابقة كاملة)
3. **Semantic Memory**: ذاكرة دلالية (معرفة عامة ومفاهيم)
4. **Profile Memory**: ذاكرة التفضيلات (تفضيلات المستخدم والشركة)

+ **Vector DB**: Chroma DB لـ semantic search
+ **Learning System**: نظام التعلم الذكي

الاستخدام:
```python
from memory import MemoryManager, LearningSystem

# مع Vector DB
manager = MemoryManager(use_vector_db=True)

# حفظ تفاعل
manager.save_episode(
    agent="fahas",
    query="ابحث عن موظف",
    result={"success": True},
    context={}
)

# البحث الدلالي
similar = manager.search_episodes(
    query="موظف في قسم IT",  # semantic search!
    limit=5
)

# التعلم
learning = LearningSystem(manager)
performance = learning.get_agent_performance("fahas")
suggestions = learning.suggest_improvements("fahas")
```
"""

from memory.manager import MemoryManager
from memory.types import (
    MemoryType,
    Episode,
    SemanticKnowledge,
    UserProfile,
)
from memory.learning import LearningSystem

# Optional: Vector Store (requires chromadb)
try:
    from memory.vector_store import VectorStore
    VECTOR_STORE_AVAILABLE = True
except ImportError:
    VECTOR_STORE_AVAILABLE = False

__all__ = [
    "MemoryManager",
    "MemoryType",
    "Episode",
    "SemanticKnowledge",
    "UserProfile",
    "LearningSystem",
]

if VECTOR_STORE_AVAILABLE:
    __all__.append("VectorStore")
