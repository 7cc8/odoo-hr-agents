"""Memory/history tests for the LangGraph skeleton (no network, no Odoo)."""
import pytest

pytest.importorskip("langgraph")

from graph import nodes as n  # noqa: E402
from graph.state import append_messages  # noqa: E402


def test_reducer_appends():
    assert append_messages([{"a": 1}], [{"b": 2}]) == [{"a": 1}, {"b": 2}]
    assert append_messages(None, [{"b": 2}]) == [{"b": 2}]


def test_ingest_adds_user_message_and_resets_scratch():
    out = n.ingest_user_message({"user_query": "hi", "error": "old", "turns": 3})
    assert out["messages"] == [{"role": "user", "content": "hi"}]
    assert out["turns"] == 0 and out["error"] is None and out["last_assistant"] == {}


def test_ingest_empty_query_sets_error_and_routes_to_finalize():
    out = n.ingest_user_message({"user_query": "   "})
    assert out["error"] == "empty_query"
    assert n.route_after_ingest(out) == "finalize"


def test_sanitize_drops_dangling_tool_calls():
    msgs = [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
        {"role": "user", "content": "q2"},
    ]
    out = n.sanitize_history(msgs)
    assert [m["role"] for m in out] == ["user", "user"]


def test_sanitize_keeps_complete_tool_chain():
    msgs = [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
        {"role": "tool", "tool_call_id": "c1", "content": "{}"},
        {"role": "assistant", "content": "done"},
    ]
    assert len(n.sanitize_history(msgs)) == 4


def test_trim_starts_with_user_and_respects_limit():
    msgs = []
    for i in range(10):
        msgs.append({"role": "user", "content": f"q{i}"})
        msgs.append({"role": "assistant", "content": f"a{i}"})
    out = n.trim_history(msgs, limit=5)
    assert out[0]["role"] == "user"
    assert len(out) <= 5
    assert out[-1]["content"] == "a9"
