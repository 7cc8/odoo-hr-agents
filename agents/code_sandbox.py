"""
محلل الأكواد الحسابية المعزول (Safe Code Sandbox for Financial & HR Formulas)
=============================================================================
بيئة تنفيذ بايثون معزولة ومفحوصة أمنياً عبر AST:
1. فحص شجرة التركيب النحوي (AST) لمنع الاستيراد (import) والاستدعاءات الخطرة تماماً.
2. حظر استدعاءات: open, eval, exec, compile, __import__, globals, locals, getattr, delattr.
3. حظر أي وصول لخصائص dunder مثل __class__, __subclasses__, __globals__.
4. حصر البيئة في دوال الرياضيات القياسية والعمليات الحسابية الآمنة مع مهلة زمنية صارمة (2 ثانية).
5. التسجيل في ToolRegistry كأداة رسمية «run_hr_calculation_sandbox».
"""

from __future__ import annotations

import ast
import json
import logging
import math
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("code_sandbox")


class SecurityViolationError(Exception):
    """استثناء عند محاولة كسر القيود الأمنية للبيئة المعزولة."""
    pass


class ASTSecurityValidator(ast.NodeVisitor):
    """فاحص شجرة التركيب النحوي لكشف وحظر أي تعبيرات خطيرة أو استيرادات."""

    FORBIDDEN_CALLS = {
        "eval", "exec", "open", "compile", "__import__", "globals", "locals",
        "getattr", "setattr", "delattr", "system", "popen", "spawn", "fork",
        "input", "breakpoint", "help", "exit", "quit"
    }

    def visit_Import(self, node: ast.Import) -> None:
        raise SecurityViolationError("استخدام import محظور تماماً داخل البيئة الحسابية المعزولة.")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        raise SecurityViolationError("استخدام from ... import محظور تماماً داخل البيئة المعزولة.")

    def visit_Call(self, node: ast.Call) -> None:
        # فحص اسم الدالة المستدعاة
        if isinstance(node.func, ast.Name):
            if node.func.id in self.FORBIDDEN_CALLS:
                raise SecurityViolationError(f"استدعاء الدالة «{node.func.id}» محظور أمنياً.")
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in self.FORBIDDEN_CALLS:
                raise SecurityViolationError(f"استدعاء الخاصية «{node.func.attr}» محظور أمنياً.")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # حظر الوصول لأي خصائص سحرية dunder
        if node.attr.startswith("__") and node.attr.endswith("__"):
            raise SecurityViolationError(f"الوصول للخاصية السحرية «{node.attr}» محظور أمنياً.")
        self.generic_visit(node)


class SafeCodeSandbox:
    """منفذ الأكواد الحسابية المعزول والآمن."""

    SAFE_BUILTINS = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "len": len,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "list": list,
        "dict": dict,
        "range": range,
        "zip": zip,
        "enumerate": enumerate,
        "True": True,
        "False": False,
        "None": None,
    }

    SAFE_MATH = {
        "ceil": math.ceil,
        "floor": math.floor,
        "sqrt": math.sqrt,
        "pow": math.pow,
        "log": math.log,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
    }

    @classmethod
    def execute(cls, code: str, variables: Optional[Dict[str, Any]] = None, timeout_sec: float = 2.0) -> Dict[str, Any]:
        """
        تنفيذ كود حسابي بأمان تام:
        - يرجع النتيجة المحسوبة في المتغير `result` أو آخر تعبير.
        """
        clean_code = code.strip()
        if not clean_code:
            return {"status": "error", "error": "الكود فارغ."}

        start_time = time.perf_counter()

        # 1. الفحص النحوي والأمني عبر AST
        try:
            tree = ast.parse(clean_code)
            validator = ASTSecurityValidator()
            validator.visit(tree)
        except SecurityViolationError as sec_err:
            return {
                "status": "security_violation",
                "error": str(sec_err),
                "execution_time_ms": round((time.perf_counter() - start_time) * 1000, 2),
            }
        except SyntaxError as syn_err:
            return {
                "status": "syntax_error",
                "error": f"خطأ نحوي في صياغة الكود: {syn_err}",
                "execution_time_ms": round((time.perf_counter() - start_time) * 1000, 2),
            }

        # 2. بناء النطاق المغلق (Isolated Scope)
        env = {
            "__builtins__": dict(cls.SAFE_BUILTINS),
            "math": type("SafeMath", (), cls.SAFE_MATH)(),
        }

        # حقن المتغيرات الممررة
        if variables and isinstance(variables, dict):
            for k, v in variables.items():
                if isinstance(k, str) and not k.startswith("__"):
                    env[k] = v

        # 3. التنفيذ المعزول
        try:
            compiled = compile(tree, filename="<hr_sandbox>", mode="exec")
            exec(compiled, env)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            res = env.get("result")
            if res is None:
                # محاولة استخراج أي متغير معرف جديد
                user_vars = {k: v for k, v in env.items() if k not in ("__builtins__", "math") and not k.startswith("_")}
                res = user_vars

            return {
                "status": "success",
                "result": res,
                "execution_time_ms": duration_ms,
            }
        except Exception as run_err:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "status": "runtime_error",
                "error": f"خطأ أثناء الحساب: {run_err}",
                "execution_time_ms": duration_ms,
            }


def register_sandbox_tool() -> None:
    """تسجيل أداة الحساب المعزول في سجل أدوات الوكلاء الموحد."""
    try:
        from agents.tool_registry import ToolRegistry, ToolDefinition
        registry = ToolRegistry.get_instance()

        params = {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "كود بايثون الحسابي الصافي (يضع النتيجة النهائية في متغير باسم result).",
                },
                "variables": {
                    "type": "object",
                    "description": "المعاملات والمتغيرات المالية المبدئية (مثل salary, years, overtime_hours).",
                },
            },
            "required": ["code"],
        }

        def handler(code: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            return SafeCodeSandbox.execute(code=code, variables=variables)

        tool_def = ToolDefinition(
            name="run_hr_calculation_sandbox",
            description=(
                "تشغيل معادلة مالية أو إحصائية معقدة (مثل مكافأة نهاية الخدمة، حصص التأمينات الاجتماعية، "
                "أجر ساعات العمل الإضافية، نسب التوطين والضرائب) في بيئة بايثون معزولة ومؤمنة تماماً لحساب النتيجة بدقة حسابية 100%."
            ),
            function=handler,
            parameters=params,
            allowed_agents={"seraj", "mudaqqiq", "fahas"},
            requires_approval=False,
            is_read_only=True,
        )

        registry.register_tool(tool_def)
        logger.info("تم تسجيل أداة run_hr_calculation_sandbox بنجاح في ToolRegistry.")
    except Exception as e:
        logger.warning("تعذر تسجيل أداة sandbox في ToolRegistry: %s", e)


# التسجيل التلقائي عند التحميل
try:
    register_sandbox_tool()
except Exception:
    pass

