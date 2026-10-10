"""
Agents Module - الوكلاء الذكية (Agentic AI)
============================================
"""
from agents.base_agent import (
    BaseAgent,
    AgentGoal,
    AgentMemory,
    AgentPlan,
    AgentReflection,
    create_agent_goal,
)
from agents.tool_registry import ToolRegistry, ToolDefinition

# سنضيف الوكلاء تدريجياً
# from agents.fahas_agent import FahasAgent
# from agents.musleh_agent import MuslehAgent
# ...

__all__ = [
    "BaseAgent",
    "AgentGoal",
    "AgentMemory",
    "AgentPlan",
    "AgentReflection",
    "create_agent_goal",
    "ToolRegistry",
    "ToolDefinition",
]
