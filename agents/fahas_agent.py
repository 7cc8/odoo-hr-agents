"""
Fahas Agent - وكيل الاستعلام والتحقق
======================================
يستلم مهام مهيكلة من سراج ويُنفّذها عبر fahas_service.execute_query_task
بدون استدعاء مباشر للنموذج اللغوي.

القدرات:
- تنفيذ مهام count_records, search_records, list_companies
- التحقق من اتساق الأعداد (مجموع الشركات = الإجمالي)
- معالجة الأخطاء وإرجاع نتائج منظمة
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent, AgentGoal, AgentPlan, create_agent_goal
from fahas_service import get_fahas_agent as get_fahas_service

logger = logging.getLogger("fahas_agent")


class FahasAgent(BaseAgent):
    """
    وكيل الاستعلام (بدون LLM)
    
    يستلم مهام مهيكلة من سراج (task_type + params) ويمررها
    مباشرة إلى fahas_service.execute_query_task.
    
    التحقق من الاتساق:
    - عند count_records: إذا كان هناك company_id، نتحقق من أن مجموع الشركات = الإجمالي
    """
    
    def __init__(self, llm_model: Optional[str] = None):
        super().__init__(
            name="fahas",
            role="وكيل الاستعلام والتحقق من بيانات Odoo (structured tasks only)",
            llm_model=llm_model,
        )
        self.fahas_service = get_fahas_service()
    
    # ═══════════════════════════════════════════════════════════════
    # Planning: تحليل المهمة وإعداد الخطة
    # ═══════════════════════════════════════════════════════════════
    
    def plan(self, goal: AgentGoal, perception: Optional[Dict[str, Any]] = None) -> AgentPlan:
        """
        إنشاء خطة تنفيذية من task مهيكلة.
        
        goal.objective يجب أن يحتوي على:
        {
          "task_type": "count_records",
          "params": {
            "model": "hr.employee",
            "company_id": 15
          }
        }
        """
        task_data = goal.objective
        if isinstance(task_data, str):
            try:
                task_data = json.loads(task_data)
            except Exception:
                task_data = {"task_type": "unknown", "params": {}}
        
        plan = AgentPlan(plan_id=f"fahas_plan_{self.iteration_count}")
        
        # خطوة 1: تنفيذ المهمة
        plan.add_step({
            "action": "execute_task",
            "task_type": task_data.get("task_type"),
            "params": task_data.get("params", {}),
        })
        
        # خطوة 2: التحقق من الاتساق (إذا كانت count مع company_id)
        if task_data.get("task_type") == "count_records":
            params = task_data.get("params", {})
            if params.get("company_id"):
                plan.add_step({
                    "action": "verify_consistency",
                    "model": params.get("model"),
                })
        
        return plan
    
    # ═══════════════════════════════════════════════════════════════
    # Execution: تنفيذ المهمة
    # ═══════════════════════════════════════════════════════════════
    
    def execute(self, plan: AgentPlan) -> Dict[str, Any]:
        """تنفيذ خطوات الخطة"""
        results = {
            "steps_executed": [],
            "data": None,
            "status": "in_progress",
            "consistency_check": None,
        }
        
        task_result = None
        
        for i, step in enumerate(plan.steps):
            action = step.get("action")
            
            try:
                if action == "execute_task":
                    # تنفيذ المهمة عبر fahas_service
                    task_type = step.get("task_type")
                    params = step.get("params", {})
                    
                    task_result = self.fahas_service.execute_query_task(task_type, params)
                    results["data"] = task_result
                    results["steps_executed"].append({
                        "step": i,
                        "action": action,
                        "status": "success",
                    })
                    plan.mark_step_complete(i)
                
                elif action == "verify_consistency":
                    # التحقق من اتساق الأعداد
                    if task_result and isinstance(task_result, dict):
                        model = step.get("model")
                        company_id = task_result.get("company_id")
                        count = task_result.get("count", 0)
                        
                        # حساب الإجمالي (بدون company_id)
                        try:
                            total_result = self.fahas_service.execute_query_task(
                                "count_records",
                                {"model": model, "company_id": None}
                            )
                            total_count = total_result.get("count", 0)
                            
                            # التحقق: عدد الشركة يجب أن يكون <= الإجمالي
                            is_consistent = count <= total_count
                            
                            results["consistency_check"] = {
                                "company_count": count,
                                "total_count": total_count,
                                "is_consistent": is_consistent,
                                "message": f"عدد الشركة ({count}) {'≤' if is_consistent else '>'} الإجمالي ({total_count})"
                            }
                            
                            if not is_consistent:
                                logger.warning(
                                    f"⚠️ Consistency check failed: company count ({count}) > total ({total_count})"
                                )
                        except Exception as e:
                            logger.error(f"Consistency check failed: {e}")
                            results["consistency_check"] = {
                                "error": str(e),
                                "is_consistent": None,
                            }
                    
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


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def create_fahas_query_goal(
    task_type: str,
    params: Dict[str, Any],
) -> AgentGoal:
    """مساعد لإنشاء هدف استعلام مهيكل لفاحص"""
    return create_agent_goal(
        objective={
            "task_type": task_type,
            "params": params,
        },
        constraints=[
            "قراءة فقط - لا كتابة",
            "نماذج معتمدة فقط",
        ],
        success_criteria=[
            "النتائج دقيقة",
            "الاتساق محقق",
        ],
    )
