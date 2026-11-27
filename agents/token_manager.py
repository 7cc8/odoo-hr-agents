"""
مدير حد الكلمات والنافذة المنزلقة (Token Manager & Sliding Window)
==================================================================
يحسب استهلاك التوكنات ويطبق نافذة منزلقة ذكية تضغط السياق القديم:
1. تقدير دقيق لتوكنات اللغة العربية والنصوص والإنجليزية وJSON.
2. تطبيق Sliding Window مع تلخيص وضغط الرسائل الأقدم تلقائياً.
3. حماية حدود النافذة لمنع تجاوز السقف الأقصى للنموذج (Context Window Limit).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class TokenManager:
    """مدير سقف التوكنات والنافذة المنزلقة المدمج."""

    DEFAULT_MAX_CONTEXT_TOKENS = 4096
    DEFAULT_COMPLETION_RESERVE = 1024

    @classmethod
    def count_tokens(cls, text: str) -> int:
        """
        تقدير عدد التوكنات لنص معين:
        - الحروف العربية تستغرق عادة توكن لكل 2.5 - 3.2 حرف.
        - الحروف الإنجليزية والرموز البرمجية تستغرق توكن لكل ~4 أحرف.
        """
        if not text:
            return 0
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        other_chars = len(text) - arabic_chars
        # تقدير متحفظ لضمان عدم تجاوز السقف
        tokens = math.ceil(arabic_chars / 2.7) + math.ceil(other_chars / 3.8)
        return max(1, tokens)

    @classmethod
    def count_message_tokens(cls, messages: List[Dict[str, Any]]) -> int:
        """حساب إجمالي التوكنات لقائمة رسائل كاملة تشمل الترويسة والأدوار."""
        total = 0
        for m in messages:
            content = str(m.get("content") or "")
            role = str(m.get("role") or "")
            total += cls.count_tokens(content) + cls.count_tokens(role) + 4
        return total + 2

    @classmethod
    def apply_sliding_window(
        cls,
        messages: List[Dict[str, Any]],
        max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        reserve_for_completion: int = DEFAULT_COMPLETION_RESERVE,
    ) -> List[Dict[str, Any]]:
        """
        تطبيق النافذة المنزلقة الذكية:
        - الحفاظ الدائم على رسالة النظام (System Prompt).
        - الحفاظ على أحدث 4 رسائل مستمرة (آخر دورة أو دورتين).
        - إذا كان المجموع يتجاوز الميزانية، تلخيص الرسائل الأقدم في سطر واحد ودمجها.
        """
        if not messages:
            return []

        budget = max(512, max_tokens - reserve_for_completion)
        current_tokens = cls.count_message_tokens(messages)

        if current_tokens <= budget:
            return list(messages)

        # فصل رسائل النظام عن رسائل الحوار
        system_msgs = [m for m in messages if m.get("role") == "system"]
        chat_msgs = [m for m in messages if m.get("role") != "system"]

        if not chat_msgs:
            return messages

        # الحفاظ على آخر رسالتين كحد أدنى
        recent_count = min(len(chat_msgs), 4)
        recent_msgs = chat_msgs[-recent_count:]
        older_msgs = chat_msgs[:-recent_count]

        # ضغط وتلخيص الرسائل القديمة
        summary_snippets = []
        for m in older_msgs:
            role_label = "المستخدم" if m.get("role") == "user" else "سراج"
            text_snip = (m.get("content") or "").strip().replace("\n", " ")[:80]
            summary_snippets.append(f"{role_label}: {text_snip}")

        compressed_content = "ملخص المحادثة السابقة: " + " | ".join(summary_snippets) if summary_snippets else ""
        synthetic_summary_msg = {"role": "system", "content": compressed_content} if compressed_content else None

        result = list(system_msgs)
        if synthetic_summary_msg:
            result.append(synthetic_summary_msg)
        result.extend(recent_msgs)

        # إذا كانت لا تزال تتجاوز، نقلل أحدث الرسائل
        while len(recent_msgs) > 2 and cls.count_message_tokens(result) > budget:
            recent_msgs.pop(0)
            result = list(system_msgs)
            if synthetic_summary_msg:
                result.append(synthetic_summary_msg)
            result.extend(recent_msgs)

        return result


import math

