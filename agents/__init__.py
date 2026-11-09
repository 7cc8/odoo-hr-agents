"""
Agents Module - منظومة الوكلاء الذكية المعيارية (Vanilla Agentic AI)
=====================================================================
توفر هذه الحزمة المرجعية الحصرية والموحدة لكافة وكلاء المنظومة:
- BaseAgent: النواة والمحرك الأساسي لدورة حياة الوكيل (Perceive -> Plan -> Execute -> Reflect)
- SerajMetaAgent: وكيل التنسيق والتخطيط الذكي الشامل
- FahasAgent: وكيل الاستعلام والفحص المعتمد
- KatibAgent: وكيل الكتابة والاعتماد في Odoo
- MuslehAgent: وكيل التشخيص والإصلاح الذاتي
- HaresAgent: وكيل الحماية والامتثال الأمني
- MudaqqiqAgent: وكيل التدقيق والمطابقة التشريعية لنظام العمل
- MuwaffaqAgent: وكيل المطابقة الذكية للكيانات
- SijilAgent: وكيل التدقيق الجنائي وتوثيق العمليات
- LLMProvider: إدارة واستدعاء النماذج اللغوية
- ToolRegistry: سجل الأدوات وصلاحيات التنفيذ
"""

from agents.base_agent import (
    BaseAgent,
    AgentGoal,
    AgentMemory,
    AgentPlan,
    AgentReflection,
    create_agent_goal,
)
from agents.seraj_meta_agent import (
    SerajMetaAgent,
    AgentHandoff,
    PipelineCheckpoint,
)
from agents.fahas_agent import FahasAgent
from agents.katib_agent import KatibAgent
from agents.musleh_agent import MuslehAgent
from agents.hares_agent import HaresAgent
from agents.mudaqqiq_agent import MudaqqiqAgent
from agents.muwaffaq_agent import MuwaffaqAgent
from agents.sijil_agent import SijilAgent
from agents.tool_registry import ToolRegistry, ToolDefinition
from agents.llm_provider import LLMProvider, get_llm_provider
from seraj_session_manager import SerajSessionState, SerajState

__all__ = [
    "BaseAgent",
    "AgentGoal",
    "AgentMemory",
    "AgentPlan",
    "AgentReflection",
    "create_agent_goal",
    "SerajMetaAgent",
    "AgentHandoff",
    "PipelineCheckpoint",
    "SerajSessionState",
    "SerajState",
    "FahasAgent",
    "KatibAgent",
    "MuslehAgent",
    "HaresAgent",
    "MudaqqiqAgent",
    "MuwaffaqAgent",
    "SijilAgent",
    "ToolRegistry",
    "ToolDefinition",
    "LLMProvider",
    "get_llm_provider",
]
