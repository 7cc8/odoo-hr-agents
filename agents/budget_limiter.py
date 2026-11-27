"""
قاطع ميزانية التوكنات والحلقات (Iteration & Token Budget Limiter)
================================================================
1. كبح الحلقات اللانهائية وتحديد سقف دورات التفكير (Max Turns = 5).
2. كبح استهلاك التوكنات (Max Tokens Per Task = 16,000 tokens).
3. إيقاف المهمة فوراً عند تجاوز أي حد وتوليد حزمة تصعيد بشري (Escalation Package).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("budget_limiter")


class BudgetExceededError(Exception):
    """استثناء عند تجاوز ميزانية التوكنات أو الحد الأقصى للدورات."""
    pass


class BudgetLimiter:
    """قاطع ميزانية العمليات الموحد."""

    DEFAULT_MAX_TURNS = 5
    DEFAULT_MAX_TOKENS = 16000

    def __init__(
        self,
        max_turns: int = DEFAULT_MAX_TURNS,
        max_tokens_per_task: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self.max_turns = max_turns
        self.max_tokens_per_task = max_tokens_per_task
        self._op_tokens: Dict[str, int] = {}
        self._op_turns: Dict[str, int] = {}

    def record_usage(self, operation_id: str, tokens: int) -> int:
        """تسجيل توكنات إضافية مستهلكة للعملية وترجيع الإجمالي التراكمي."""
        curr = self._op_tokens.get(operation_id, 0) + tokens
        self._op_tokens[operation_id] = curr
        return curr

    def record_turn(self, operation_id: str) -> int:
        """تسجيل دورة جديدة وترجيع رقم الدورة الحالية."""
        curr = self._op_turns.get(operation_id, 0) + 1
        self._op_turns[operation_id] = curr
        return curr

    def check_limits(
        self,
        operation_id: str,
        chat_id: str = "default",
        agent_name: str = "seraj",
        session_state: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        التحقق من الحدود:
        يرجع (True, None) إذا كانت العملية ضمن الحدود.
        يرجع (False, error_reason) ويولد حزمة تصعيد بشري إذا تم تجاوز الحدود.
        """
        turns = self._op_turns.get(operation_id, 0)
        tokens = self._op_tokens.get(operation_id, 0)

        if turns > self.max_turns:
            reason = f"تجاوز الحد الأقصى لدورات تفكير الوكيل ({turns}/{self.max_turns} دورة)."
            self._escalate(operation_id, chat_id, agent_name, reason, turns, session_state)
            return False, reason

        if tokens > self.max_tokens_per_task:
            reason = f"تجاوز سقف استهلاك التوكنات المسموح للمهمة ({tokens}/{self.max_tokens_per_task} توكن)."
            self._escalate(operation_id, chat_id, agent_name, reason, turns, session_state)
            return False, reason

        return True, None

    def _escalate(
        self,
        operation_id: str,
        chat_id: str,
        agent_name: str,
        reason: str,
        turns: int,
        session_state: Optional[Dict[str, Any]],
    ) -> None:
        try:
            from agents.checkpoint_manager import CheckpointManager
            cm = CheckpointManager.get_instance()
            cm.create_escalation_package(
                operation_id=operation_id,
                chat_id=chat_id,
                failed_agent=agent_name,
                reason=reason,
                attempt_count=turns,
                last_error=reason,
                session_state=session_state or {},
                recommended_action="مراجعة التوجيه المعقد وتجزئة السؤال إلى استفسارات أصغر أو اعتماد النتيجة يدوياً.",
            )
            logger.warning("تم إيقاف العملية %s وتصعيدها للمشرف البشري: %s", operation_id, reason)
        except Exception as e:
            logger.error("تعذر تصعيد العملية %s: %s", operation_id, e)

