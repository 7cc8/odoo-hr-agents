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

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("seraj_session_manager")


@dataclass
class ConversationSession:
    chat_id: str
    connection_id: str = "default"
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    pending_clarification: Optional[Dict[str, Any]] = None
    pending_action: Optional[Dict[str, Any]] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    last_query_topic: Optional[str] = None

    def add_message(self, role: str, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None) -> None:
        """إضافة رسالة إلى تاريخ الجلسة مع الحفاظ على سقف أقصى 12 رسالة لمنع تضخم السياق."""
        msg: Dict[str, Any] = {"role": role, "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.history.append(msg)
        if len(self.history) > 12:
            self.history = self.history[-12:]

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
