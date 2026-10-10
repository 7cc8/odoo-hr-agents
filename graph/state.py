"""Shared state for the Seraj graph."""
from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict

Intent = Literal["read", "write", "clarify"]


def append_messages(left: Optional[List[Dict[str, Any]]], right: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Reducer: nodes return ONLY new messages; they are appended to the thread history."""
    return list(left or []) + list(right or [])


class SerajState(TypedDict, total=False):
    # input (overwritten on every run)
    chat_id: str
    user_query: str
    user_name: str
    connection_id: Optional[str]

    # sticky company context (persists per thread_id)
    company_id: Optional[int]
    company_name: Optional[str]
    companies: Dict[str, str]  # id -> name, learned from company-listing tools

    # routing
    intent: Intent

    # conversation memory (persists per thread_id)
    messages: Annotated[List[Dict[str, Any]], append_messages]

    # per-run scratch (reset by ingest_user_message)
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
