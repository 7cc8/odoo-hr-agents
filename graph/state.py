"""Shared state for the Seraj graph."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict

Intent = Literal["read", "write", "clarify"]


class SerajState(TypedDict, total=False):
    # input
    chat_id: str
    user_query: str
    user_name: str
    connection_id: Optional[str]
    company_id: Optional[int]

    # routing
    intent: Intent

    # read path (agent loop)
    messages: List[Dict[str, Any]]
    last_assistant: Dict[str, Any]
    turns: int
    last_tool_error: Optional[str]

    # write path (deterministic, human-gated)
    plan: Optional[Dict[str, Any]]
    policy_ok: Optional[bool]
    approved: Optional[bool]
    exec_result: Optional[Dict[str, Any]]
    verified: Optional[bool]

    # output
    answer: Optional[str]
    error: Optional[str]
