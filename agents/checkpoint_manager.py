"""
مدير نقاط التفتيش وحزمة التصعيد البشري (Checkpoint Manager & Escalation Context Package)
======================================================================================
1. حفظ لقطات حالة الوكلاء (Checkpoints) في SQLite memory.db عند نهاية كل دورة.
2. تجميع حزمة سياق التصعيد البشري (EscalationContextPackage) عند تعثر المهام أو استنفاد المحاولات.
3. تمكين المشرف البشري من استئناف أو اعتماد أو رفض المهمة مع كامل الأدلة وسجل الخطوات.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("checkpoint_manager")


@dataclass
class EscalationContextPackage:
    """حزمة سياق التصعيد للمشرف البشري (HITL Escalation Package)."""
    operation_id: str
    chat_id: str
    trigger_reason: str
    failed_agent: str
    attempt_count: int
    last_error: Optional[str]
    session_state: Dict[str, Any]
    checkpoints_history: List[Dict[str, Any]]
    recommended_action: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_markdown(self) -> str:
        """صياغة تقرير تصعيد غني بتنسيق Markdown موجه للمشرف البشري."""
        state_summary = json.dumps(self.session_state, ensure_ascii=False, indent=2)
        steps_count = len(self.checkpoints_history)
        err_msg = self.last_error or "تجاوز الحد الأقصى للمحاولات دون حسم قاطع."
        return (
            f"🚨 **حزمة تصعيد بشري محكومة — Human Escalation Package**\n"
            f"────────────────────────────────────────────────────\n"
            f"• **رقم العملية:** `{self.operation_id}`\n"
            f"• **معرف الجلسة:** `{self.chat_id}`\n"
            f"• **الوكيل المتأثر:** `{self.failed_agent}` (عدد المحاولات: {self.attempt_count})\n"
            f"• **سبب التصعيد:** {self.trigger_reason}\n"
            f"• **الخطأ الأخير:** `{err_msg}`\n"
            f"• **عدد نقاط التفتيش المحفوظة:** {steps_count}\n\n"
            f"💡 **الإجراء الموصى به للمشرف:**\n"
            f"{self.recommended_action}\n\n"
            f"📋 **ملخص الحالة عند التوقف (State Snapshot):**\n"
            f"```json\n{state_summary}\n```\n"
            f"⏱️ *وقت الإنشاء:* {self.created_at}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CheckpointManager:
    """مدير نقاط التفتيش المعتمد على SQLite."""

    _instance: Optional[CheckpointManager] = None

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> CheckpointManager:
        if cls._instance is None:
            cls._instance = cls(db_path=db_path)
        return cls._instance

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path(__file__).resolve().parent.parent / "memory_store" / "memory.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def save_checkpoint(
        self,
        operation_id: str,
        chat_id: str,
        agent_name: str,
        turn_number: int,
        state: Dict[str, Any],
    ) -> Optional[str]:
        """حفظ نقطة تفتيش جديدة لحالة العملية."""
        chk_id = f"chk_{operation_id}_{turn_number}_{uuid.uuid4().hex[:4]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        state_str = json.dumps(state, ensure_ascii=False, default=str)

        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO checkpoints (checkpoint_id, operation_id, chat_id, agent_name, turn_number, state_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (chk_id, operation_id, chat_id, agent_name, turn_number, state_str, now_iso)
                )
                conn.commit()
            return chk_id
        except Exception as e:
            logger.warning("فشل حفظ نقطة التفتيش: %s", e)
            return None

    def get_checkpoints(self, operation_id: str) -> List[Dict[str, Any]]:
        """استرجاع كافة نقاط التفتيش التابعة لعملية معينة."""
        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT checkpoint_id, operation_id, chat_id, agent_name, turn_number, state_json, created_at
                    FROM checkpoints
                    WHERE operation_id = ?
                    ORDER BY id ASC
                    """,
                    (operation_id,)
                )
                rows = cur.fetchall()
                result = []
                for r in rows:
                    st = {}
                    try:
                        st = json.loads(r["state_json"]) if r["state_json"] else {}
                    except Exception:
                        pass
                    result.append({
                        "checkpoint_id": r["checkpoint_id"],
                        "operation_id": r["operation_id"],
                        "chat_id": r["chat_id"],
                        "agent_name": r["agent_name"],
                        "turn_number": r["turn_number"],
                        "state": st,
                        "created_at": r["created_at"],
                    })
                return result
        except Exception as e:
            logger.warning("فشل استرجاع نقاط التفتيش: %s", e)
            return []

    def create_escalation_package(
        self,
        operation_id: str,
        chat_id: str,
        failed_agent: str,
        reason: str,
        attempt_count: int,
        last_error: Optional[str] = None,
        session_state: Optional[Dict[str, Any]] = None,
        recommended_action: str = "مراجعة معطيات الطلب واعتماد أو تعديل المتغيرات يدوياً.",
    ) -> EscalationContextPackage:
        """توليد حزمة تصعيد بشري شاملة مع حفظها."""
        history = self.get_checkpoints(operation_id)
        pkg = EscalationContextPackage(
            operation_id=operation_id,
            chat_id=chat_id,
            trigger_reason=reason,
            failed_agent=failed_agent,
            attempt_count=attempt_count,
            last_error=last_error,
            session_state=session_state or {},
            checkpoints_history=history,
            recommended_action=recommended_action,
        )
        # حفظ نقطة تفتيش نهائية للتصعيد
        self.save_checkpoint(
            operation_id=operation_id,
            chat_id=chat_id,
            agent_name=failed_agent,
            turn_number=attempt_count,
            state={"escalation_package": pkg.to_dict()},
        )
        return pkg

