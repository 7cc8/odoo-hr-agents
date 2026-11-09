"""
مدير سياق جلسات المحادثة لسراج (Seraj Conversation Session Manager)
==================================================================
يحفظ سياق المحادثة عبر الجلسات والرسائل المتتالية:
1. الاتصال المختار (connection_id)
2. المنشأة / الشركة المختارة (company_id)
3. السؤال المعلق الذي ينتظر توضيحاً (pending_clarification)
4. سجل المحادثة (history) للأسئلة المتابعة مثل «والمؤرشفين؟»
5. فض الالتباس عند إجابة المستخدم مثل «الشركة الثانية» أو «شركة النخبة» دون تفسيرها كاسم موظف.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, TypedDict

logger = logging.getLogger("seraj_session_manager")


class SerajSessionState(TypedDict, total=False):
    """حالة جلسة وعمليات سراج في بيئة الوكلاء الموحدة (Vanilla Agentic AI)."""
    operation_id: Optional[str]
    company_id: Optional[int]
    chat_id: Optional[str]
    user_query: Optional[str]
    rejected_rows_details: Optional[List[Dict[str, Any]]]
    user_execution_choice: Optional[str]
    auto_execute: Optional[bool]
    excel_validation_stats: Optional[Dict[str, Any]]
    status: Optional[str]


# اسم مستعار للتوافقية الكاملة مع بنية الوكلاء المعمارية
SerajState = SerajSessionState


@dataclass
class ConversationSession:
    chat_id: str
    connection_id: str = "default"
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    pending_clarification: Optional[Dict[str, Any]] = None
    pending_action: Optional[Dict[str, Any]] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    handoffs: List[Dict[str, Any]] = field(default_factory=list)
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)
    last_query_topic: Optional[str] = None
    title: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def record_handoff(
        self,
        from_agent: str,
        to_agent: str,
        intent: str,
        context_summary: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """توثيق عملية تسليم وتفويض المهام بين الوكلاء وحفظها في سياق الجلسة."""
        ho = {
            "handoff_id": f"ho_{int(datetime.now().timestamp() * 1000)}",
            "from_agent": from_agent,
            "to_agent": to_agent,
            "intent": intent,
            "context_summary": context_summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload or {},
        }
        self.handoffs.append(ho)
        if len(self.handoffs) > 50:
            self.handoffs = self.handoffs[-50:]
        return ho

    def record_checkpoint(
        self,
        phase: str,
        agent: str,
        status: str = "success",
        artifacts: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """تسجيل نقطة تفتيش وحفظ لحالة خط أنابيب الوكلاء."""
        cp = {
            "checkpoint_id": f"cp_{int(datetime.now().timestamp() * 1000)}",
            "phase": phase,
            "agent": agent,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "artifacts": artifacts or {},
        }
        self.checkpoints.append(cp)
        if len(self.checkpoints) > 50:
            self.checkpoints = self.checkpoints[-50:]
        return cp

    def add_message(self, role: str, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None) -> None:
        """إضافة رسالة إلى تاريخ الجلسة مع الحفاظ على سقف أقصى 30 رسالة وتحديث الطابع الزمني والعنوان ومزامنتها مع ذاكرة العمل الموحدة."""
        msg: Dict[str, Any] = {"role": role, "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.history.append(msg)
        if len(self.history) > 30:
            self.history = self.history[-30:]

        self.updated_at = datetime.now(timezone.utc).isoformat()
        if not self.title and role == "user":
            first_line = content.strip().split("\n")[0][:45].strip()
            self.title = first_line or "محادثة استفسار"

        try:
            from memory.manager import MemoryManager
            wm = MemoryManager.get_instance().get_working_memory(self.chat_id)
            wm.add_message(role=role, content=content, tool_calls=tool_calls)
        except Exception:
            pass

    def clear_pending_clarification(self) -> None:
        self.pending_clarification = None

    def clear_pending_action(self) -> None:
        self.pending_action = None

    def is_pending_action_valid(self, user_id: Optional[str] = None) -> Tuple[bool, str]:
        """فحص صلاحية العملية المعلقة: استهلاك مسبق، انتهاء مهلة TTL، أو اختلاف الهوية."""
        if not self.pending_action:
            return False, "لا توجد عملية معلقة في انتظار الاعتماد."

        import time
        if self.pending_action.get("consumed"):
            return False, "⚠️ تم استهلاك هذا الاعتماد مسبقاً ولا يمكن إعادة تنفيذه."

        expires_at = self.pending_action.get("expires_at")
        if expires_at and time.time() > float(expires_at):
            return False, "⚠️ انتهت صلاحية هذا الاعتماد (تجاوزت مهلة الـ 5 دقائق). يرجى طلب اعتماد جديد."

        creator_user_id = self.pending_action.get("user_id")
        if user_id and creator_user_id and str(creator_user_id) != str(user_id):
            return False, "⚠️ لا يمكن تنفيذ هذه العملية: هوية صاحب التأكيد لا تطابق هوية مقدم الطلب الأصلية."

        return True, "صالح"

    def mark_pending_action_consumed(self) -> None:
        """وسم العملية بأنها استهلكت لمنع إعادة التنفيذ."""
        if self.pending_action:
            self.pending_action["consumed"] = True


class SerajSessionManager:
    """مدير الجلسات الموزع للمحادثات."""

    _instance: Optional[SerajSessionManager] = None

    def __init__(self) -> None:
        self.sessions: Dict[str, ConversationSession] = {}

    @classmethod
    def get_instance(cls) -> SerajSessionManager:
        if cls._instance is None:
            cls._instance = SerajSessionManager()
        return cls._instance

    def get_session(self, chat_id: str | int) -> ConversationSession:
        cid = str(chat_id)
        if cid not in self.sessions:
            self.sessions[cid] = ConversationSession(chat_id=cid)
        return self.sessions[cid]

    def reset_session(self, chat_id: str | int) -> None:
        cid = str(chat_id)
        if cid in self.sessions:
            del self.sessions[cid]

    def list_sessions(self) -> List[Dict[str, Any]]:
        """إرجاع قائمة بكافة الجلسات النشطة مرتبة تنازلياً حسب آخر نشاط."""
        result = []
        for s in sorted(self.sessions.values(), key=lambda x: x.updated_at, reverse=True):
            display_title = s.title
            if not display_title:
                display_title = f"جلسة {s.chat_id[:8]}" if s.chat_id.startswith("web_") else s.chat_id
            last_msg = ""
            if s.history:
                last_msg = str(s.history[-1].get("content") or "")[:80]
            result.append({
                "chat_id": s.chat_id,
                "title": display_title,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "message_count": len(s.history),
                "last_message": last_msg,
            })
        return result

    def resolve_pending_clarification(
        self,
        session: ConversationSession,
        user_input: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        فحص هل هناك سؤال توضيحي معلق (مثل اختيار الشركة) ومعالجة رد المستخدم عليه.
        مثال: المستخدم يكتب «الشركة الثانية» أو «شركة النخبة» أو «15» أو «الكل».
        يرجع (True, original_query) إذا تم فض الالتباس بنجاح واستئناف السؤال الأصلي.
        """
        if not session.pending_clarification:
            return False, None

        p_type = session.pending_clarification.get("type")
        orig_query = session.pending_clarification.get("original_query", "")
        clean_text = user_input.strip()

        if p_type == "select_company":
            companies = session.pending_clarification.get("companies", [])
            # 1. فحص الكلمات الترتيبية: الأولى، الثانية، الثالثة...
            ordinal_map = {
                "الاولى": 0, "الأولى": 0, "الاول": 0, "الأول": 0, "1": 0,
                "الثانية": 1, "الثانيه": 1, "الثاني": 1, "2": 1,
                "الثالثة": 2, "الثالثه": 2, "الثالث": 2, "3": 2,
                "الرابعة": 3, "الرابعه": 3, "الرابع": 3, "4": 3,
                "الخامسة": 4, "الخامسه": 4, "الخامس": 4, "5": 4,
            }

            matched_company = None

            # فحص عبارة «الشركة الثانية» أو «الثانية»
            for ord_word, idx in ordinal_map.items():
                if ord_word in clean_text.replace("الشركة", "").strip().split():
                    if 0 <= idx < len(companies):
                        matched_company = companies[idx]
                        break

            # فحص خيار «الكل» أو «جميع الشركات»
            if not matched_company and any(all_word in clean_text for all_word in ("الكل", "جميع الشركات", "كل الشركات", "عام")):
                session.company_id = None
                session.company_name = "جميع الشركات"
                session.clear_pending_clarification()
                return True, orig_query

            # فحص المطابقة برقم الـ ID
            if not matched_company and clean_text.isdigit():
                c_id = int(clean_text)
                for comp in companies:
                    if comp.get("id") == c_id:
                        matched_company = comp
                        break

            # فحص المطابقة بالاسم
            if not matched_company:
                for comp in companies:
                    c_name = comp.get("name", "")
                    if clean_text in c_name or c_name in clean_text:
                        matched_company = comp
                        break

            if matched_company:
                session.company_id = matched_company.get("id")
                session.company_name = matched_company.get("name")
                session.clear_pending_clarification()
                logger.info(f"Resolved company clarification for chat {session.chat_id}: {session.company_name} (ID: {session.company_id})")
                return True, orig_query

        return False, None
