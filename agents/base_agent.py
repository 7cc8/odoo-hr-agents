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
    """تعريف الهدف والقيود مع التوافقية العكسية لـ description و context"""
    objective: str = ""
    description: str = ""
    constraints: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    max_iterations: int = 10
    timeout_seconds: int = 300
    context: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.objective and self.description:
            self.objective = self.description
        elif not self.description and self.objective:
            self.description = self.objective


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
        """حفظ حلقة كاملة للرجوع لها لاحقاً ومزامنتها مع مدير الذاكرة الموحد"""
        self.episodic_memory.append({
            **episode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        try:
            from memory.manager import MemoryManager
            mm = MemoryManager.get_instance()
            goal_text = str(episode.get("goal") or episode.get("query") or "agent_execution")
            mm.save_episode(
                agent=episode.get("agent", "agent"),
                agents_involved=episode.get("agents_involved", [episode.get("agent", "agent")]),
                user_query=goal_text,
                intent=str(episode.get("intent", "task")),
                context=episode.get("context", {}),
                result=episode.get("result", {}),
                success=bool(episode.get("success", True)),
                confidence=float(episode.get("confidence", 0.9)),
                decision_path=episode.get("decision_path", []),
                strategies_used=episode.get("strategies_used", []),
                duration_ms=int(episode.get("duration_ms", 0)),
            )
        except Exception:
            pass
    
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
        self.llm_model = llm_model or os.environ.get("LLM_MODEL", "qwen3.5:9b")
        self.llm_provider: Optional[Any] = None
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
        self.system_prompt: str = self.get_system_prompt()

    def recall_similar_episodes(self, query: str, limit: int = 3) -> List[Any]:
        """استرجاع حلقات تفاعل سابقة مشابهة من الذاكرة المركزية الموحدة"""
        try:
            from memory.manager import MemoryManager
            mm = MemoryManager.get_instance()
            return mm.search_episodes(query=query, limit=limit)
        except Exception:
            return []

    def get_semantic_knowledge(self, concept: str) -> Optional[Any]:
        """استرجاع معرفة دلالية من الذاكرة المركزية"""
        try:
            from memory.manager import MemoryManager
            mm = MemoryManager.get_instance()
            return mm.get_semantic_knowledge(concept)
        except Exception:
            return None
    
    # ═══════════════════════════════════════════════════════════════
    # Core Agentic Loop
    # ═══════════════════════════════════════════════════════════════

    def _call_perceive(self, goal: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """استدعاء perceive بدعم نمطين: (goal, context) أو (request_dict)."""
        import inspect
        sig = inspect.signature(self.perceive)
        names = [p.name for p in sig.parameters.values()]
        if "goal" in names:
            return self.perceive(goal, context)

        # Style B: Request dictionary
        req: Dict[str, Any] = {}
        if isinstance(context, dict):
            req.update(context)
        if hasattr(goal, "objective"):
            try:
                loaded = json.loads(goal.objective)
                if isinstance(loaded, dict):
                    req.update(loaded)
                else:
                    req["query"] = str(goal.objective)
            except Exception:
                req["query"] = str(goal.objective)
        elif isinstance(goal, dict):
            req.update(goal)
        else:
            req["query"] = str(goal)
        if "query" not in req and hasattr(goal, "objective"):
            req["query"] = str(goal.objective)
        if "context" not in req:
            req["context"] = context or {}
        return self.perceive(req)

    def _call_plan(self, goal: Any, perception: Dict[str, Any]) -> Any:
        """استدعاء plan بدعم نمطين: (goal, perception) أو (perception)."""
        import inspect
        sig = inspect.signature(self.plan)
        names = [p.name for p in sig.parameters.values()]
        if "goal" in names:
            return self.plan(goal, perception)
        return self.plan(perception)

    def _call_execute(self, plan: Any, perception: Dict[str, Any]) -> Dict[str, Any]:
        """استدعاء execute بدعم (plan) أو (plan, perception)."""
        import inspect
        sig = inspect.signature(self.execute)
        names = [p.name for p in sig.parameters.values()]
        if "perception" in names:
            return self.execute(plan, perception)
        return self.execute(plan)

    def _call_reflect(self, goal: Any, plan: Any, result: Dict[str, Any], perception: Dict[str, Any]) -> Any:
        """استدعاء reflect بدعم (goal, plan, result) أو (perception, plan, result)."""
        import inspect
        sig = inspect.signature(self.reflect)
        names = [p.name for p in sig.parameters.values()]
        if "goal" in names:
            return self.reflect(goal, plan, result)
        return self.reflect(perception, plan, result)
    
    def run(self, goal: AgentGoal, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        الحلقة الرئيسية للوكيل:
        Goal → Perceive → Plan → Execute → Reflect → (Retry if needed)
        """
        self.current_goal = goal
        self.iteration_count = 0
        start_time = datetime.now(timezone.utc)
        
        goal_text = goal.objective if hasattr(goal, "objective") else str(goal)
        self._log_trace("START", {"goal": goal_text})
        
        try:
            # 1. Perception: فهم السياق
            perception = self._call_perceive(goal, context)
            self._log_trace("PERCEIVE", perception if isinstance(perception, dict) else {})
            
            # 2. Planning: وضع خطة
            plan = self._call_plan(goal, perception)
            self.current_plan = plan
            steps_cnt = (
                len(plan.steps) if hasattr(plan, "steps")
                else (len(plan.get("steps", plan.get("execution_order", []))) if isinstance(plan, dict) else 1)
            )
            self._log_trace("PLAN", {"steps": steps_cnt})
            
            # 3. Execution Loop
            while self.iteration_count < self.max_iterations:
                self.iteration_count += 1
                
                # تنفيذ الخطة
                result = self._call_execute(plan, perception)
                status_val = result.get("status") if isinstance(result, dict) else "completed"
                self._log_trace("EXECUTE", {"iteration": self.iteration_count, "status": status_val})
                
                # 4. Reflection: مراجعة النتائج
                reflection = self._call_reflect(goal, plan, result, perception)
                if isinstance(reflection, dict):
                    success = bool(reflection.get("success", result.get("overall_success", True) if isinstance(result, dict) else True))
                    conf = float(reflection.get("confidence", reflection.get("confidence_in_decision", 0.9)))
                    should_retry = bool(reflection.get("should_retry", False))
                    retry_strat = reflection.get("retry_strategy")
                else:
                    success = getattr(reflection, "success", True)
                    conf = getattr(reflection, "confidence", 0.9)
                    should_retry = getattr(reflection, "should_retry", False)
                    retry_strat = getattr(reflection, "retry_strategy", None)

                self._log_trace("REFLECT", {
                    "success": success,
                    "confidence": conf,
                    "should_retry": should_retry,
                })
                
                # إذا نجح أو اكتمل التقييم بدون إعادة محاولة → خروج
                if success and (conf >= 0.7 or not should_retry):
                    plan_steps = (
                        plan.steps if hasattr(plan, "steps")
                        else (plan.get("steps", plan.get("execution_order")) if isinstance(plan, dict) else [])
                    )
                    self.memory.add_episode({
                        "agent": self.name,
                        "goal": goal_text,
                        "plan": plan_steps,
                        "result": result,
                        "reflection": reflection,
                        "confidence": conf,
                        "iterations": self.iteration_count,
                    })
                    
                    self._log_trace("SUCCESS", {"confidence": conf})
                    
                    return {
                        "status": "success",
                        "result": result,
                        "reflection": reflection,
                        "iterations": self.iteration_count,
                        "duration_seconds": (datetime.now(timezone.utc) - start_time).total_seconds(),
                        "trace": self.trace_log,
                    }
                
                # إذا يحتاج إعادة محاولة
                if should_retry and self.iteration_count < self.max_iterations:
                    self._log_trace("RETRY", {"strategy": retry_strat})
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
        
        call_messages = list(messages)
        if not any(m.get("role") == "system" for m in call_messages):
            call_messages.insert(0, {"role": "system", "content": self.system_prompt})

        provider = get_llm_provider()
        return provider.call(call_messages, tools, temperature)
    
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
    
    def get_system_prompt(self, context: Optional[Dict[str, Any]] = None) -> str:
        """الحصول على system prompt للوكيل من سجل الأوامر المعياري"""
        try:
            from agents.prompts import get_agent_system_prompt
            return get_agent_system_prompt(self.name, context=context)
        except Exception:
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
