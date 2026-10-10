"""
Tool Registry - مدير الأدوات الموحد
====================================
يُدير كل الأدوات المتاحة للوكلاء مع:
- تسجيل الأدوات وتعريفها
- التحقق من الصلاحيات
- تتبع الاستخدام
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("tool_registry")


class ToolDefinition:
    """تعريف أداة"""
    def __init__(
        self,
        name: str,
        description: str,
        function: Callable,
        parameters: Dict[str, Any],
        allowed_agents: Optional[Set[str]] = None,
        requires_approval: bool = False,
        is_read_only: bool = True,
    ):
        self.name = name
        self.description = description
        self.function = function
        self.parameters = parameters
        self.allowed_agents = allowed_agents  # None = all agents
        self.requires_approval = requires_approval
        self.is_read_only = is_read_only
        self.call_count = 0
        self.last_called = None
    
    def can_be_used_by(self, agent_name: str) -> bool:
        """التحقق من صلاحية الوكيل لاستخدام الأداة"""
        if self.allowed_agents is None:
            return True
        return agent_name in self.allowed_agents
    
    def to_schema(self) -> Dict[str, Any]:
        """تحويل لصيغة OpenAI function schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


class ToolRegistry:
    """مدير الأدوات المركزي"""
    
    _instance: Optional[ToolRegistry] = None
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
    
    @classmethod
    def get_instance(cls) -> ToolRegistry:
        """Singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def register_tool(self, tool: ToolDefinition) -> None:
        """تسجيل أداة جديدة"""
        if tool.name in self.tools:
            logger.warning(f"Tool {tool.name} already registered, overwriting")
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} (read_only={tool.is_read_only})")
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """الحصول على أداة"""
        return self.tools.get(name)
    
    def get_tools_for_agent(self, agent_name: str, read_only: bool = True) -> List[ToolDefinition]:
        """الحصول على الأدوات المتاحة لوكيل معين"""
        return [
            tool for tool in self.tools.values()
            if tool.can_be_used_by(agent_name) and (not read_only or tool.is_read_only)
        ]
    
    def get_tools_schema(self, agent_name: str) -> List[Dict[str, Any]]:
        """الحصول على schemas الأدوات لوكيل معين"""
        tools = self.get_tools_for_agent(agent_name)
        return [tool.to_schema() for tool in tools]
    
    def execute_tool(
        self,
        tool_name: str,
        agent_name: str,
        args: Dict[str, Any],
        approved: bool = False,
    ) -> Any:
        """تنفيذ أداة"""
        tool = self.get_tool(tool_name)
        if tool is None:
            raise ValueError(f"Tool {tool_name} not found")
        
        # التحقق من الصلاحية
        if not tool.can_be_used_by(agent_name):
            raise PermissionError(f"Agent {agent_name} not allowed to use tool {tool_name}")
        
        # التحقق من الموافقة للأدوات الحساسة
        if tool.requires_approval and not approved:
            raise PermissionError(f"Tool {tool_name} requires approval before execution")
        
        # تنفيذ
        try:
            result = tool.function(**args)
            tool.call_count += 1
            from datetime import datetime, timezone
            tool.last_called = datetime.now(timezone.utc)
            return result
        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}")
            raise


# ═══════════════════════════════════════════════════════════════
# Tool Registration Helpers
# ═══════════════════════════════════════════════════════════════

def register_all_tools():
    """تسجيل كل الأدوات المتاحة"""
    register_odoo_read_tools()
    # register_write_tools()  # لاحقاً


def register_odoo_read_tools():
    """تسجيل أدوات القراءة من Odoo"""
    try:
        # استيراد من الملف الموجود
        import odoo_agent_tools as tools
        
        registry = ToolRegistry.get_instance()
        
        # الحصول على schema الموجود
        if hasattr(tools, 'SERAJ_ODOO_TOOLS_SCHEMA'):
            for tool_schema in tools.SERAJ_ODOO_TOOLS_SCHEMA:
                fn_def = tool_schema.get("function", {})
                tool_name = fn_def.get("name")
                
                # محاولة الحصول على الدالة الفعلية
                if hasattr(tools, tool_name):
                    actual_fn = getattr(tools, tool_name)
                    
                    registry.register_tool(ToolDefinition(
                        name=tool_name,
                        description=fn_def.get("description", ""),
                        function=actual_fn,
                        parameters=fn_def.get("parameters", {}),
                        allowed_agents=None,  # متاح لكل الوكلاء (قراءة فقط)
                        is_read_only=True,
                    ))
                    logger.info(f"Registered read tool: {tool_name}")
        
        logger.info(f"Registered {len(registry.tools)} read tools")
        
    except ImportError as e:
        logger.warning(f"Could not import odoo_agent_tools: {e}")
    except Exception as e:
        logger.error(f"Error registering tools: {e}")


def register_write_tools():
    """تسجيل أدوات الكتابة (تتطلب موافقة)"""
    registry = ToolRegistry.get_instance()
    
    # TODO: تسجيل أدوات الكتابة من katib_service
    # كلها requires_approval=True, is_read_only=False
    pass


# تسجيل تلقائي عند الاستيراد
register_all_tools()  # ✅ مُفعّل الآن
