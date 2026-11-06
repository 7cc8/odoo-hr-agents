"""
MetroCity Pixel-Agents Bridge - جسر ربط وكلاء سراج الثمانية بمحرك MetroCity
=========================================================================
يكتب أحداث الوكلاء الثمانية بصيغة JSONL الحية التي يراقبها محرك pablodelucca/pixel-agents
لتحريك شخصيات MetroCity (المشي للمكتب، الكتابة، القراءة، وطلب موافقة المالك).
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("pixel_office_bridge")

# تعريف الوكلاء الثمانية وأدواتهم التمثيلية في أنيميشن MetroCity
METROCITY_AGENTS = {
    "seraj":    {"name_ar": "سراج (CEO)",     "default_tool": "Task"},
    "fahas":    {"name_ar": "فاحص (Query)",   "default_tool": "Grep"},
    "mudaqqiq": {"name_ar": "مدقق (Law)",     "default_tool": "Read"},
    "musleh":   {"name_ar": "مصلح (Healer)",  "default_tool": "Edit"},
    "muwaffaq": {"name_ar": "موفّق (Match)",  "default_tool": "Glob"},
    "hares":    {"name_ar": "حارس (Guard)",   "default_tool": "Bash"},
    "katib":    {"name_ar": "كاتب (Writer)",  "default_tool": "Write"},
    "sijil":    {"name_ar": "سجل (Audit)",    "default_tool": "Read"},
}


class MetroCityBridge:
    """يبث حالة الوكلاء الثمانية مباشرة إلى المجلد الذي يراقبه محرك pixel-agents"""

    def __init__(self, project_slug: str = "d--mjrm0-Documents-odoo-hr-agents-2"):
        claude_root = Path.home() / ".claude" / "projects" / project_slug
        claude_root.mkdir(parents=True, exist_ok=True)
        self.sessions_dir = claude_root

    def _session_file(self, agent_id: str) -> Path:
        return self.sessions_dir / f"agent-{agent_id}.jsonl"

    def spawn_agent(self, agent_id: str, task_text: str) -> None:
        """إدخال الوكيل إلى المكتب والجلوس على الكرسي المخصص له"""
        meta = METROCITY_AGENTS.get(agent_id, {"name_ar": agent_id, "default_tool": "Read"})
        record = {
            "type": "user",
            "sessionId": f"agent-{agent_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": {
                "role": "user",
                "content": f"[{meta['name_ar']}] {task_text}",
            },
        }
        self._append_jsonl(agent_id, record)

    def start_working(self, agent_id: str, action_desc: str, tool_override: Optional[str] = None) -> str:
        """تفعيل أنيميشن الكتابة على الكيبورد أو القراءة في المكتب"""
        meta = METROCITY_AGENTS.get(agent_id, {"name_ar": agent_id, "default_tool": "Read"})
        tool_name = tool_override or meta["default_tool"]
        tool_use_id = f"toolu_{agent_id}_{int(time.time() * 1000)}"
        record = {
            "type": "assistant",
            "sessionId": f"agent-{agent_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": f"{meta['name_ar']}: {action_desc}"},
                    {
                        "type": "tool_use",
                        "id": tool_use_id,
                        "name": tool_name,
                        "input": {"description": action_desc, "agent": agent_id},
                    },
                ],
            },
        }
        self._append_jsonl(agent_id, record)
        return tool_use_id

    def finish_working(self, agent_id: str, tool_use_id: str, summary: str) -> None:
        """إنهاء الأداة الحالية وإرجاع الوكيل لوضع الجاهزية/الاستراحة"""
        record = {
            "type": "user",
            "sessionId": f"agent-{agent_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": summary,
                    }
                ],
            },
        }
        self._append_jsonl(agent_id, record)

    def _append_jsonl(self, agent_id: str, payload: Dict[str, Any]) -> None:
        try:
            path = self._session_file(agent_id)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.debug(f"Failed writing MetroCity JSONL for {agent_id}: {exc}")
