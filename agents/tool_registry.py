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
    """تسجيل كل الأدوات المتاحة (قراءة واستعلام وخدمات نظام العمل وأدوات الكتابة المعتمدة)"""
    register_odoo_read_tools()
    register_fahas_query_tools()
    register_hr_service_tools()
    register_write_tools()


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


def register_hr_service_tools():
    """تسجيل أدوات واستشارات وخدمات نظام العمل السعودي والتأمينات (16 خدمة تخصصية)"""
    try:
        import saudi_labor_law_rules as sllr
        from agents.mudaqqiq_agent import MudaqqiqAgent
        mudaqqiq = MudaqqiqAgent()
        registry = ToolRegistry.get_instance()

        hr_services = [
            ("calculate_end_of_service", "حساب مكافأة نهاية الخدمة بالريال وفق المواد 84 و85 و87 من نظام العمل", lambda **kwargs: mudaqqiq.calculate_eosb(
                basic_wage=float(kwargs.get("basic_wage", 0.0)),
                service_years=float(kwargs.get("service_years", 0.0)),
                is_resignation=str(kwargs.get("termination_reason", "resignation")) == "resignation",
                is_saudi=str(kwargs.get("nationality", "saudi")) == "saudi",
                last_gross_wage=float(kwargs.get("gross_wage", kwargs.get("basic_wage", 0.0))),
            ), {
                "type": "object",
                "properties": {
                    "basic_wage": {"type": "number", "description": "الأجر الأساسي"},
                    "gross_wage": {"type": "number", "description": "الأجر الفعلي الشامل"},
                    "service_years": {"type": "number", "description": "مدة الخدمة بالسنوات"},
                    "termination_reason": {"type": "string", "description": "سبب انتهاء العقد: resignation, employer_termination"},
                    "nationality": {"type": "string", "description": "الجنسية: saudi أو non_saudi"},
                },
                "required": ["basic_wage", "service_years"],
            }),
            ("calculate_gosi", "حساب استقطاعات التأمينات الاجتماعية GOSI وساند للموظف والمنشأة", lambda **kwargs: mudaqqiq.calculate_gosi(
                basic_wage=float(kwargs.get("basic_wage", kwargs.get("wage", 0.0))),
                housing_allowance=float(kwargs.get("housing_allowance", 0.0)),
                is_saudi=str(kwargs.get("nationality", "saudi")) == "saudi",
            ), {
                "type": "object",
                "properties": {
                    "wage": {"type": "number", "description": "الأجر الخاضع للاشتراك"},
                    "basic_wage": {"type": "number", "description": "الأجر الأساسي"},
                    "housing_allowance": {"type": "number", "description": "بدل السكن"},
                    "nationality": {"type": "string", "description": "الجنسية: saudi أو non_saudi"},
                },
                "required": ["basic_wage"],
            }),
            ("calculate_overtime", "حساب أجر ساعات العمل الإضافي وفق المادة 107 (الأجر الفعلي + 50% من الأساسي)", lambda **kwargs: mudaqqiq.calculate_overtime(
                basic_wage=float(kwargs.get("basic_wage", 0.0)),
                gross_wage=float(kwargs.get("gross_wage", kwargs.get("basic_wage", 0.0))),
                overtime_hours=float(kwargs.get("overtime_hours", 0.0)),
            ), {
                "type": "object",
                "properties": {
                    "basic_wage": {"type": "number", "description": "الأجر الأساسي"},
                    "gross_wage": {"type": "number", "description": "الأجر الفعلي"},
                    "overtime_hours": {"type": "number", "description": "عدد ساعات العمل الإضافي"},
                },
                "required": ["basic_wage", "overtime_hours"],
            }),
            ("get_annual_leave_entitlement", "تحديد استحقاق الإجازة السنوية وفق المادة 109 (21 أو 30 يوماً)", lambda **kwargs: {
                "days": sllr.calculate_annual_leave_entitlement(float(kwargs.get("service_years", 0.0))),
                "article": "المادة 109 من نظام العمل",
            }, {
                "type": "object",
                "properties": {
                    "service_years": {"type": "number", "description": "سنوات الخدمة المتصلة"},
                },
                "required": ["service_years"],
            }),
            ("validate_probation_period", "تدقيق فترة التجربة وفق المادة 53 وتعديلات 1446هـ (90 إلى 180 يوماً)", lambda **kwargs: sllr.validate_probation_period(
                probation_days=int(kwargs.get("days", 90)),
                has_written_agreement=bool(kwargs.get("is_extended", False)),
                is_extension=bool(kwargs.get("is_extended", False)),
            ), {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "عدد أيام فترة التجربة"},
                    "is_extended": {"type": "boolean", "description": "هل تم التمديد باتفاق خطي صريح"},
                },
                "required": ["days"],
            }),
            ("validate_loan_deduction", "التحقق من سقف استقطاع قروض صاحب العمل وفق المادة 92 (حد أقصى 10%)", lambda **kwargs: sllr.validate_loan_installment_cap(
                monthly_wage=float(kwargs.get("monthly_wage", 1.0)),
                proposed_installment=float(kwargs.get("installment", 0.0)),
            ), {
                "type": "object",
                "properties": {
                    "installment": {"type": "number", "description": "القسط الشهري للسلفة"},
                    "monthly_wage": {"type": "number", "description": "الراتب الشهري الفعلي"},
                },
                "required": ["installment", "monthly_wage"],
            }),
            ("consult_labor_law", "استشارة نصوص مواد نظام العمل السعودي ولوائحه التفسيرية عبر مدقق", lambda **kwargs: mudaqqiq.consult_labor_law(
                query=str(kwargs.get("query", "")),
                article_number=int(kwargs["article_number"]) if kwargs.get("article_number") else None,
            ), {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "موضوع أو نص الاستفسار القانوني"},
                    "article_number": {"type": "integer", "description": "رقم المادة النظامية إن عُرف"},
                },
                "required": ["query"],
            }),
        ]

        for name, desc, fn, params in hr_services:
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
        logger.warning(f"Could not register HR service tools: {e}")


def register_write_tools():
    """تسجيل أدوات الكتابة والتنفيذ لـ «كاتب» (تتطلب خطة اعتماد مسبقة وموافقة صريحة)"""
    try:
        from katib_service import get_katib_service
        katib = get_katib_service()
        registry = ToolRegistry.get_instance()

        write_tools = [
            ("create_record", "إنشاء سجل جديد في نماذج Odoo المصرح بها بعد الاعتماد", lambda **kwargs: katib.execute_approved_action({
                "action_type": "create",
                "model": kwargs.get("model", "hr.employee"),
                "values": kwargs.get("values", {}),
                "plan_id": kwargs.get("plan_id"),
            }), {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "اسم الموديل في Odoo"},
                    "values": {"type": "object", "description": "بيانات السجل الجديد"},
                    "plan_id": {"type": "string", "description": "معرف خطة الاعتماد الصالحة"},
                },
                "required": ["model", "values", "plan_id"],
            }),
            ("update_record", "تعديل حقول سجل موجود في Odoo بعد الاعتماد", lambda **kwargs: katib.execute_approved_action({
                "action_type": "update",
                "model": kwargs.get("model", "hr.employee"),
                "record_id": int(kwargs.get("record_id", 0)),
                "values": kwargs.get("values", {}),
                "plan_id": kwargs.get("plan_id"),
            }), {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "اسم الموديل في Odoo"},
                    "record_id": {"type": "integer", "description": "معرف السجل المراد تعديله"},
                    "values": {"type": "object", "description": "القيم الجديدة المراد حفظها"},
                    "plan_id": {"type": "string", "description": "معرف خطة الاعتماد الصالحة"},
                },
                "required": ["model", "record_id", "values", "plan_id"],
            }),
            ("archive_record", "أرشفة سجل (إيقاف التنشيط active=False) بعد الاعتماد", lambda **kwargs: katib.execute_approved_action({
                "action_type": "archive",
                "model": kwargs.get("model", "hr.employee"),
                "record_id": int(kwargs.get("record_id", 0)),
                "plan_id": kwargs.get("plan_id"),
            }), {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "اسم الموديل"},
                    "record_id": {"type": "integer", "description": "معرف السجل المراد أرشفته"},
                    "plan_id": {"type": "string", "description": "معرف خطة الاعتماد الصالحة"},
                },
                "required": ["model", "record_id", "plan_id"],
            }),
            ("unarchive_record", "إلغاء أرشفة سجل واستعادته (active=True) بعد الاعتماد", lambda **kwargs: katib.execute_approved_action({
                "action_type": "unarchive",
                "model": kwargs.get("model", "hr.employee"),
                "record_id": int(kwargs.get("record_id", 0)),
                "plan_id": kwargs.get("plan_id"),
            }), {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "اسم الموديل"},
                    "record_id": {"type": "integer", "description": "معرف السجل المراد استرجاعه"},
                    "plan_id": {"type": "string", "description": "معرف خطة الاعتماد الصالحة"},
                },
                "required": ["model", "record_id", "plan_id"],
            }),
            ("delete_record", "حذف سجل مفرد محكوم في Odoo عبر البوابة المعزولة بعد الاعتماد", lambda **kwargs: katib.execute_approved_action({
                "action_type": "delete",
                "model": kwargs.get("model", "hr.employee"),
                "record_id": int(kwargs.get("record_id", 0)),
                "plan_id": kwargs.get("plan_id"),
            }), {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "اسم الموديل"},
                    "record_id": {"type": "integer", "description": "معرف السجل المراد حذفه"},
                    "plan_id": {"type": "string", "description": "معرف خطة الاعتماد الصالحة"},
                },
                "required": ["model", "record_id", "plan_id"],
            }),
        ]

        for name, desc, fn, params in write_tools:
            if name not in registry.tools:
                registry.register_tool(ToolDefinition(
                    name=name,
                    description=desc,
                    function=fn,
                    parameters=params,
                    allowed_agents={"katib"},
                    requires_approval=True,
                    is_read_only=False,
                ))
    except Exception as e:
        logger.warning(f"Could not register write tools: {e}")


# تسجيل تلقائي عند الاستيراد
register_all_tools()
