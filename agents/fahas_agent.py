"""
Fahas Agent - وكيل الاستعلام والتحقق الذكي
==========================================
تحويل "فاحص" من Tool إلى Agentic AI كامل مع:
- فهم الاستعلام وتحليله
- التخطيط لخطوات الاستعلام
- التنفيذ مع إعادة المحاولة
- التحقق من جودة النتائج
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import (
    BaseAgent,
    AgentGoal,
    AgentPlan,
    AgentReflection,
    create_agent_goal,
)
from agents.tool_registry import ToolRegistry
from odoo_readonly_repository import OdooReadonlyRepository

logger = logging.getLogger("fahas_agent")


class FahasAgent(BaseAgent):
    """
    وكيل الاستعلام والتحقق الذكي (Agentic)
    
    القدرات:
    - فهم استعلامات اللغة الطبيعية
    - التخطيط لاستراتيجية الاستعلام (single query vs multiple queries)
    - إعادة الصياغة عند الفشل
    - التحقق من جودة النتائج
    - اكتشاف البيانات المفقودة واقتراح خطوات إضافية
    """
    
    def __init__(
        self,
        repository: Optional[OdooReadonlyRepository] = None,
        llm_model: Optional[str] = None,
    ):
        super().__init__(
            name="fahas",
            role="وكيل الاستعلام والتحقق من بيانات Odoo",
            llm_model=llm_model,
        )
        self.repository = repository or self._get_default_repository()
        self.tool_registry = ToolRegistry.get_instance()
        
        # تحميل الأدوات المتاحة
        self.tools = self.tool_registry.get_tools_schema("fahas")
    
    def _get_default_repository(self) -> OdooReadonlyRepository:
        """الحصول على repository افتراضي"""
        repo = OdooReadonlyRepository()
        repo.connect()
        return repo
    
    # ═══════════════════════════════════════════════════════════════
    # Perception: فهم الاستعلام
    # ═══════════════════════════════════════════════════════════════
    
    def perceive(self, goal: AgentGoal, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        تحليل الاستعلام وفهم:
        - نوع الاستعلام (count, search, specific record)
        - الموديل المستهدف
        - الفلاتر المطلوبة
        - الحقول المطلوبة
        """
        query = goal.objective
        context = context or {}
        
        # استخدام LLM لفهم الاستعلام
        system_prompt = f"""{self.get_system_prompt()}

حلل الاستعلام التالي واستخرج:
1. نوع العملية: count / search / read / describe
2. الموديل المستهدف (مثل hr.employee)
3. الشروط (domain filters)
4. الحقول المطلوبة
5. الحد الأقصى للنتائج

أرجع JSON بهذا الشكل:
{{
  "operation": "search",
  "model": "hr.employee",
  "domain": [["name", "ilike", "أحمد"]],
  "fields": ["name", "job_id", "department_id"],
  "limit": 10,
  "reasoning": "شرح مختصر"
}}
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"الاستعلام: {query}\n\nالسياق الإضافي: {json.dumps(context, ensure_ascii=False)}"}
        ]
        
        llm_response = self._call_llm(messages)
        
        # استخراج التحليل
        try:
            analysis = json.loads(llm_response.get("content", "{}"))
        except Exception:
            # fallback: تحليل بسيط
            analysis = {
                "operation": "search",
                "model": "hr.employee",
                "domain": [],
                "fields": None,
                "limit": 10,
                "reasoning": "Failed to parse LLM response, using defaults",
            }
        
        # حفظ في الذاكرة
        self.memory.add_to_working({
            "type": "perception",
            "query": query,
            "analysis": analysis,
        })
        
        return analysis
    
    # ═══════════════════════════════════════════════════════════════
    # Planning: وضع خطة الاستعلام
    # ═══════════════════════════════════════════════════════════════
    
    def plan(self, goal: AgentGoal, perception: Dict[str, Any]) -> AgentPlan:
        """
        وضع خطة تنفيذية:
        - خطوة واحدة: استعلام بسيط
        - عدة خطوات: استعلام + تحقق + استعلام تفصيلي
        """
        plan = AgentPlan(
            plan_id=f"fahas_plan_{self.iteration_count}",
        )
        
        operation = perception.get("operation", "search")
        model = perception.get("model", "hr.employee")
        
        # خطوة 1: الاستعلام الأساسي
        plan.add_step({
            "action": "query",
            "operation": operation,
            "model": model,
            "domain": perception.get("domain"),
            "fields": perception.get("fields"),
            "limit": perception.get("limit", 10),
        })
        
        # خطوة 2: تحقق من النتائج
        plan.add_step({
            "action": "verify",
            "check": "results_not_empty",
        })
        
        # خطوة 3 (اختيارية): إذا كانت النتائج بحاجة لاستعلامات إضافية
        if operation == "search" and perception.get("fields"):
            plan.add_step({
                "action": "enrich",
                "description": "Fetch related records if needed",
            })
        
        self.memory.add_to_working({
            "type": "plan",
            "steps": len(plan.steps),
        })
        
        return plan
    
    # ═══════════════════════════════════════════════════════════════
    # Execution: تنفيذ الخطة
    # ═══════════════════════════════════════════════════════════════
    
    def execute(self, plan: AgentPlan) -> Dict[str, Any]:
        """تنفيذ خطوات الخطة"""
        results = {
            "steps_executed": [],
            "data": None,
            "status": "in_progress",
        }
        
        for i, step in enumerate(plan.steps):
            action = step.get("action")
            
            try:
                if action == "query":
                    # تنفيذ الاستعلام
                    data = self._execute_query(step)
                    results["data"] = data
                    results["steps_executed"].append({
                        "step": i,
                        "action": action,
                        "status": "success",
                        "result_count": len(data) if isinstance(data, list) else 1,
                    })
                    plan.mark_step_complete(i)
                
                elif action == "verify":
                    # التحقق من النتائج
                    check = step.get("check")
                    if check == "results_not_empty":
                        if not results.get("data"):
                            results["status"] = "no_results"
                            results["steps_executed"].append({
                                "step": i,
                                "action": action,
                                "status": "failed",
                                "reason": "No results found",
                            })
                            plan.mark_step_failed(i, "No results found")
                            break
                    plan.mark_step_complete(i)
                
                elif action == "enrich":
                    # إثراء البيانات
                    # TODO: استعلامات إضافية للـ related fields
                    plan.mark_step_complete(i)
            
            except Exception as e:
                logger.error(f"Step {i} failed: {e}")
                results["steps_executed"].append({
                    "step": i,
                    "action": action,
                    "status": "error",
                    "error": str(e),
                })
                plan.mark_step_failed(i, str(e))
                results["status"] = "error"
                break
        
        if results["status"] == "in_progress":
            results["status"] = "success"
        
        return results
    
    def _execute_query(self, step: Dict[str, Any]) -> Any:
        """تنفيذ استعلام Odoo"""
        operation = step.get("operation")
        model = step.get("model")
        domain = step.get("domain") or []
        fields = step.get("fields")
        limit = step.get("limit", 10)
        
        if operation == "count":
            # استخدام execute_kw مباشرة للـ count
            return self.repository._execute_kw(model, "search_count", [domain])
        
        elif operation == "search":
            # استخدام search_read مباشرة
            kwargs = {"limit": limit}
            if fields:
                kwargs["fields"] = fields
            return self.repository._execute_kw(
                model, "search_read", [domain], kwargs
            )
        
        elif operation == "read":
            ids = step.get("ids", [])
            kwargs = {}
            if fields:
                kwargs["fields"] = fields
            return self.repository._execute_kw(model, "read", [ids], kwargs)
        
        elif operation == "describe":
            # الحصول على fields_get
            return self.repository._execute_kw(model, "fields_get", [])
        
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    # ═══════════════════════════════════════════════════════════════
    # Reflection: مراجعة النتائج
    # ═══════════════════════════════════════════════════════════════
    
    def reflect(self, goal: AgentGoal, plan: AgentPlan, result: Dict[str, Any]) -> AgentReflection:
        """
        مراجعة النتائج:
        - هل النتائج منطقية؟
        - هل تُجيب على السؤال؟
        - هل هناك بيانات ناقصة؟
        - هل يجب إعادة المحاولة؟
        """
        status = result.get("status")
        data = result.get("data")
        
        # محاولة استخدام LLM للتقييم
        system_prompt = f"""{self.get_system_prompt()}

قيّم النتائج التالية:

الهدف: {goal.objective}
النتيجة: {json.dumps(result, ensure_ascii=False, indent=2)}

أجب بـ JSON:
{{
  "success": true/false,
  "confidence": 0.0-1.0,
  "issues": ["قائمة بالمشاكل"],
  "improvements": ["اقتراحات للتحسين"],
  "should_retry": true/false,
  "retry_strategy": "different_filters / broader_search / specific_ids / null"
}}
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "قيّم النتائج"}
        ]
        
        llm_response = self._call_llm(messages)
        
        try:
            evaluation = json.loads(llm_response.get("content", "{}"))
        except Exception:
            # Fallback: تقييم قائم على القواعد البسيطة
            logger.info("Using rule-based reflection (LLM unavailable)")
            
            success = status == "success" and data is not None
            
            # تقييم جودة النتائج
            if success:
                if isinstance(data, int):
                    # عملية count ناجحة
                    confidence = 0.95
                    issues = []
                elif isinstance(data, list):
                    # عملية search ناجحة
                    if len(data) > 0:
                        confidence = 0.90
                        issues = []
                    else:
                        confidence = 0.70
                        issues = ["No results found"]
                else:
                    confidence = 0.80
                    issues = []
            else:
                confidence = 0.30
                issues = ["Execution failed"]
            
            evaluation = {
                "success": success,
                "confidence": confidence,
                "issues": issues,
                "improvements": [],
                "should_retry": not success and confidence < 0.5,
                "retry_strategy": "broader_search" if not success else None,
            }
        
        reflection = AgentReflection(
            success=evaluation.get("success", False),
            confidence=evaluation.get("confidence", 0.5),
            issues=evaluation.get("issues", []),
            improvements=evaluation.get("improvements", []),
            should_retry=evaluation.get("should_retry", False),
            retry_strategy=evaluation.get("retry_strategy"),
        )
        
        self.memory.add_to_working({
            "type": "reflection",
            "reflection": reflection,
        })
        
        return reflection


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def create_fahas_query_goal(query: str, context: Optional[Dict[str, Any]] = None) -> AgentGoal:
    """مساعد لإنشاء هدف استعلام لفاحص"""
    return create_agent_goal(
        objective=query,
        constraints=[
            "قراءة فقط - لا كتابة",
            "نماذج HR فقط",
            "حد أقصى 100 سجل لكل استعلام",
        ],
        success_criteria=[
            "النتائج تُجيب على السؤال",
            "البيانات دقيقة وكاملة",
            "لا أخطاء تقنية",
        ],
    )
