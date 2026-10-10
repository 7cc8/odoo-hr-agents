"""
Base Agent Class - البنية الأساسية لكل الوكلاء
=============================================
يوفر الإطار الموحد لبناء Agentic AI مع:
- Goal/Perception/Reasoning/Planning
- Tool Use + Memory + Reflection
- Guardrails + Observability (LangSmith)
"""
from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# تحميل متغيرات البيئة
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("base_agent")


@dataclass
class AgentGoal:
    """تعريف الهدف والقيود"""
    objective: str
    constraints: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    max_iterations: int = 10
    timeout_seconds: int = 300


@dataclass
class AgentMemory:
    """ذاكرة الوكيل (قصيرة + طويلة)"""
    working_memory: List[Dict[str, Any]] = field(default_factory=list)  # Current context
    episodic_memory: List[Dict[str, Any]] = field(default_factory=list)  # Past episodes
    semantic_memory: Dict[str, Any] = field(default_factory=dict)  # Domain knowledge
    profile_memory: Dict[str, Any] = field(default_factory=dict)  # User/system preferences
    
    def add_to_working(self, item: Dict[str, Any]) -> None:
        """إضافة لذاكرة العمل الحالية"""
        self.working_memory.append({
            **item,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    
    def add_episode(self, episode: Dict[str, Any]) -> None:
        """حفظ حلقة كاملة للرجوع لها لاحقاً"""
        self.episodic_memory.append({
            **episode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    
    def update_semantic(self, key: str, value: Any) -> None:
        """تحديث المعرفة الدلالية"""
        self.semantic_memory[key] = value
    
    def get_context_window(self, limit: int = 10) -> List[Dict[str, Any]]:
        """الحصول على آخر N عناصر من ذاكرة العمل"""
        return self.working_memory[-limit:]


@dataclass
class AgentPlan:
    """خطة العمل"""
    plan_id: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    current_step: int = 0
    status: str = "pending"  # pending, in_progress, completed, failed
    
    def add_step(self, step: Dict[str, Any]) -> None:
        """إضافة خطوة للخطة"""
        self.steps.append({
            **step,
            "step_number": len(self.steps) + 1,
            "status": "pending",
        })
    
    def mark_step_complete(self, step_number: int) -> None:
        """تعليم خطوة كمكتملة"""
        if 0 <= step_number < len(self.steps):
            self.steps[step_number]["status"] = "completed"
    
    def mark_step_failed(self, step_number: int, error: str) -> None:
        """تعليم خطوة كفاشلة"""
        if 0 <= step_number < len(self.steps):
            self.steps[step_number]["status"] = "failed"
            self.steps[step_number]["error"] = error


@dataclass
class AgentReflection:
    """نتيجة التأمل والمراجعة"""
    success: bool
    confidence: float
    issues: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    should_retry: bool = False
    retry_strategy: Optional[str] = None


class BaseAgent(ABC):
    """
    الفئة الأساسية لكل الوكلاء الذكية (Agentic AI)
    
    كل وكيل يرث من هذه الفئة ويُطبق:
    - perceive(): تحليل المدخلات والسياق
    - plan(): وضع خطة العمل
    - execute(): تنفيذ الخطة
    - reflect(): مراجعة النتائج
    - run(): الحلقة الكاملة
    """
    
    def __init__(
        self,
        name: str,
        role: str,
        llm_model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        checkpointer: Optional[Any] = None,  # اختياري - للوكلاء الطويلة فقط
    ):
        self.name = name
        self.role = role
        self.llm_model = llm_model or os.environ.get("OPENROUTER_MODEL", "openrouter/auto")
        self.tools = tools or []
        self.memory = AgentMemory()
        self.current_goal: Optional[AgentGoal] = None
        self.current_plan: Optional[AgentPlan] = None
        self.iteration_count = 0
        self.checkpointer = checkpointer  # None = stateless, MemorySaver = stateful
        
        # Guardrails
        self.max_iterations = 10
        self.timeout_seconds = 300
        
        # Observability
        self.trace_log: List[Dict[str, Any]] = []
    
    # ═══════════════════════════════════════════════════════════════
    # Core Agentic Loop
    # ═══════════════════════════════════════════════════════════════
    
    def run(self, goal: AgentGoal, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        الحلقة الرئيسية للوكيل:
        Goal → Perceive → Plan → Execute → Reflect → (Retry if needed)
        """
        self.current_goal = goal
        self.iteration_count = 0
        start_time = datetime.now(timezone.utc)
        
        self._log_trace("START", {"goal": goal.objective})
        
        try:
            # 1. Perception: فهم السياق
            perception = self.perceive(goal, context)
            self._log_trace("PERCEIVE", perception)
            
            # 2. Planning: وضع خطة
            plan = self.plan(goal, perception)
            self.current_plan = plan
            self._log_trace("PLAN", {"steps": len(plan.steps)})
            
            # 3. Execution Loop
            while self.iteration_count < self.max_iterations:
                self.iteration_count += 1
                
                # تنفيذ الخطة
                result = self.execute(plan)
                self._log_trace("EXECUTE", {"iteration": self.iteration_count, "status": result.get("status")})
                
                # 4. Reflection: مراجعة النتائج
                reflection = self.reflect(goal, plan, result)
                self._log_trace("REFLECT", {
                    "success": reflection.success,
                    "confidence": reflection.confidence,
                    "should_retry": reflection.should_retry,
                })
                
                # إذا نجح وثقة عالية → خروج
                if reflection.success and reflection.confidence >= 0.8:
                    # حفظ في الذاكرة الطويلة
                    self.memory.add_episode({
                        "goal": goal.objective,
                        "plan": plan.steps,
                        "result": result,
                        "reflection": reflection,
                        "iterations": self.iteration_count,
                    })
                    
                    self._log_trace("SUCCESS", {"confidence": reflection.confidence})
                    
                    return {
                        "status": "success",
                        "result": result,
                        "reflection": reflection,
                        "iterations": self.iteration_count,
                        "duration_seconds": (datetime.now(timezone.utc) - start_time).total_seconds(),
                        "trace": self.trace_log,
                    }
                
                # إذا يحتاج إعادة محاولة
                if reflection.should_retry and self.iteration_count < self.max_iterations:
                    self._log_trace("RETRY", {"strategy": reflection.retry_strategy})
                    # تعديل الخطة حسب استراتيجية الإعادة
                    plan = self._adjust_plan(plan, reflection)
                    continue
                
                # إذا فشل نهائياً
                break
            
            # فشل بعد استنفاد المحاولات
            self._log_trace("FAILED", {"iterations": self.iteration_count})
            return {
                "status": "failed",
                "error": "Max iterations reached or reflection failed",
                "result": result if 'result' in locals() else None,
                "iterations": self.iteration_count,
                "duration_seconds": (datetime.now(timezone.utc) - start_time).total_seconds(),
                "trace": self.trace_log,
            }
            
        except Exception as e:
            self._log_trace("ERROR", {"error": str(e)})
            logger.error(f"Agent {self.name} failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "iterations": self.iteration_count,
                "trace": self.trace_log,
            }
    
    # ═══════════════════════════════════════════════════════════════
    # Abstract Methods - يجب تطبيقها في كل وكيل
    # ═══════════════════════════════════════════════════════════════
    
    @abstractmethod
    def perceive(self, goal: AgentGoal, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Perception: تحليل المدخلات وفهم السياق
        
        Returns:
            Dict مع المعلومات المستخلصة من السياق
        """
        pass
    
    @abstractmethod
    def plan(self, goal: AgentGoal, perception: Dict[str, Any]) -> AgentPlan:
        """
        Planning: وضع خطة تنفيذية
        
        Returns:
            AgentPlan مع الخطوات المحددة
        """
        pass
    
    @abstractmethod
    def execute(self, plan: AgentPlan) -> Dict[str, Any]:
        """
        Execution: تنفيذ الخطة
        
        Returns:
            Dict مع النتائج
        """
        pass
    
    @abstractmethod
    def reflect(self, goal: AgentGoal, plan: AgentPlan, result: Dict[str, Any]) -> AgentReflection:
        """
        Reflection: مراجعة النتائج وتقييم النجاح
        
        Returns:
            AgentReflection مع التقييم
        """
        pass
    
    # ═══════════════════════════════════════════════════════════════
    # Helper Methods
    # ═══════════════════════════════════════════════════════════════
    
    def _call_llm(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        استدعاء النموذج اللغوي
        
        يستخدم LLMProvider الموحد الذي يدعم:
        - OpenRouter (مدفوع)
        - Ollama (محلي/مجاني)
        - Fallback (rule-based)
        """
        from agents.llm_provider import get_llm_provider
        
        provider = get_llm_provider()
        return provider.call(messages, tools, temperature)
    
    def _use_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """استدعاء أداة"""
        for tool in self.tools:
            if tool.get("name") == tool_name:
                fn = tool.get("function")
                if fn:
                    return fn(**args)
        raise ValueError(f"Tool {tool_name} not found")
    
    def _adjust_plan(self, plan: AgentPlan, reflection: AgentReflection) -> AgentPlan:
        """تعديل الخطة بناءً على التأمل"""
        # استراتيجيات مختلفة للتعديل
        if reflection.retry_strategy == "add_verification":
            plan.add_step({"action": "verify", "description": "Additional verification step"})
        elif reflection.retry_strategy == "different_approach":
            # إعادة التخطيط
            pass
        return plan
    
    def _log_trace(self, event: str, data: Dict[str, Any]) -> None:
        """تسجيل حدث في trace log للمراقبة"""
        self.trace_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": self.name,
            "event": event,
            "data": data,
        })
    
    def get_system_prompt(self) -> str:
        """الحصول على system prompt للوكيل"""
        return f"""أنت {self.name}، وكيل ذكي متخصص في {self.role}.

مسؤولياتك:
- فهم الأهداف المطلوبة وتحليل السياق
- وضع خطط تنفيذية واضحة
- استخدام الأدوات المتاحة لتحقيق الأهداف
- مراجعة النتائج والتأكد من جودتها

القواعد:
- كن دقيقاً ولا تتخيل معلومات غير موجودة
- استخدم الأدوات المتاحة لك بدلاً من التخمين
- راجع عملك وتأكد من النتائج قبل الإنهاء
- عند الفشل، حاول مقاربة مختلفة
"""


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def create_agent_goal(
    objective: str,
    constraints: Optional[List[str]] = None,
    success_criteria: Optional[List[str]] = None,
) -> AgentGoal:
    """مساعد لإنشاء هدف للوكيل"""
    return AgentGoal(
        objective=objective,
        constraints=constraints or [],
        success_criteria=success_criteria or ["Task completed successfully"],
    )
