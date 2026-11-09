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

    def has_tool(self, name: str) -> bool:
        """التحقق من وجود أداة مسجلة"""
        return name in self.tools
    
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
        """تنفيذ أداة مع التحقق من الصلاحيات والمطابقة الذكية للمعاملات"""
        tool = self.get_tool(tool_name)
        if tool is None:
            raise ValueError(f"Tool {tool_name} not found")
        
        # التحقق من الصلاحية
        if not tool.can_be_used_by(agent_name):
            raise PermissionError(f"Agent {agent_name} not allowed to use tool {tool_name}")
        
        # التحقق من الموافقة للأدوات الحساسة
        if tool.requires_approval and not approved:
            raise PermissionError(f"Tool {tool_name} requires approval before execution")
        
        # تصفية المعاملات حسب توقيع الدالة لمنع أخطاء المعاملات غير المتوقعة
        try:
            import inspect
            sig = inspect.signature(tool.function)
            has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
            call_args = args if has_var_kw else {k: v for k, v in args.items() if k in sig.parameters}

            result = tool.function(**call_args)
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
    """تسجيل كل الأدوات المتاحة (قراءة واستعلام)"""
    register_odoo_read_tools()
    register_fahas_query_tools()
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
                if not tool_name:
                    continue
                
                # الحصول على الدالة الفعلية أو استدعاء الأداة الموحد
                if hasattr(tools, tool_name):
                    actual_fn = getattr(tools, tool_name)
                else:
                    actual_fn = lambda _t=tool_name, **kwargs: tools.execute_tool_call(_t, kwargs)
                    
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


def register_fahas_query_tools():
    """تسجيل أدوات الاستعلام والفحص التخصصية من fahas_service"""
    try:
        from fahas_service import get_fahas_agent
        fahas = get_fahas_agent()
        registry = ToolRegistry.get_instance()

        fahas_tools = [
            ("inspect_employee", "فحص سجلات وتفاصيل موظف محدد بالاسم أو المعرف", fahas.inspect_employee, {
                "type": "object",
                "properties": {
                    "name_or_id": {"type": "string", "description": "اسم أو رقم الموظف"},
                    "company_id": {"type": "integer", "description": "معرف الشركة"},
                    "connection_id": {"type": "string", "description": "معرف الاتصال"},
                },
                "required": ["name_or_id"],
            }),
            ("inspect_references", "فحص السجلات المرجعية الأساسية والأقسام في Odoo", fahas.inspect_references, {
                "type": "object",
                "properties": {
                    "company_id": {"type": "integer", "description": "معرف الشركة"},
                    "connection_id": {"type": "string", "description": "معرف الاتصال"},
                },
            }),
            ("group_count", "حساب أعداد السجلات مجمعة حسب حقل معين", fahas.group_count, {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "اسم الموديل في Odoo"},
                    "groupby_field": {"type": "string", "description": "حقل التجميع"},
                    "domain": {"type": "array", "description": "شروط التصفية"},
                    "company_id": {"type": "integer", "description": "معرف الشركة"},
                    "connection_id": {"type": "string", "description": "معرف الاتصال"},
                },
                "required": ["model", "groupby_field"],
            }),
            ("get_departments", "استعراض قائمة الأقسام النشطة", fahas.get_departments, {
                "type": "object",
                "properties": {
                    "company_id": {"type": "integer", "description": "معرف الشركة"},
                },
            }),
            ("get_jobs", "استعراض قائمة الوظائف المعتمدة", fahas.get_jobs, {
                "type": "object",
                "properties": {
                    "company_id": {"type": "integer", "description": "معرف الشركة"},
                },
            }),
        ]

        for name, desc, fn, params in fahas_tools:
            if name not in registry.tools:
                registry.register_tool(ToolDefinition(
                    name=name,
                    description=desc,
                    function=fn,
                    parameters=params,
                    allowed_agents=None,
                    is_read_only=True,
                ))
    except Exception as e:
        logger.warning(f"Could not register fahas query tools: {e}")


def register_write_tools():
    """تسجيل أدوات الكتابة (تتطلب موافقة)"""
    registry = ToolRegistry.get_instance()
    
    # TODO: تسجيل أدوات الكتابة من katib_service
    # كلها requires_approval=True, is_read_only=False
    pass


# تسجيل تلقائي عند الاستيراد
register_all_tools()  # ✅ مُفعّل الآن
