"""Routing tests for the LangGraph skeleton (no network, no Odoo)."""
import pytest

pytest.importorskip("langgraph")

from graph import nodes as n  # noqa: E402


def test_stops_when_no_tool_calls():
    assert n.route_after_think({"last_assistant": {"content": "x"}, "turns": 1}) == "finalize"


def test_goes_to_tools_when_requested():
    st = {"last_assistant": {"tool_calls": [{"id": "1"}]}, "turns": 1}
    assert n.route_after_think(st) == "fahas_tools"


def test_turn_cap_enforced():
    st = {"last_assistant": {"tool_calls": [{"id": "1"}]}, "turns": n.MAX_TURNS}
    assert n.route_after_think(st) == "finalize"


def test_error_short_circuits():
    assert n.route_after_think({"error": "llm_no_response"}) == "finalize"


def test_write_disabled_by_default():
    assert n.route_intent({"intent": "write"}) == "seraj_think"


def test_approval_requires_matching_plan_id_route():
    assert n.route_after_approval({"approved": False}) == "finalize_write"
    assert n.route_after_approval({"approved": True}) == "katib_execute"


def test_policy_failure_blocks_approval():
    assert n.route_after_policy({"policy_ok": False}) == "finalize_write"
