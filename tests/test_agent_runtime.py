"""agent_runtime.run_agent: the loop every LLM-driven agent shares."""
import json
import time
from unittest.mock import MagicMock

import pytest

import seraj_llm_service
from agent_runtime import (
    AgentSpec, STATUS_ANSWERED, STATUS_LLM_UNAVAILABLE, STATUS_MAX_TURNS, ToolOutcome, run_agent,
)
from fahas_service import FahasAgent
from katib_service import KatibAgent
from seraj_llm_service import SerajLLMService
from seraj_session_manager import ConversationSession

SCHEMA = [{"type": "function", "function": {"name": "count_records", "parameters": {"type": "object"}}}]
SPEC = AgentSpec(name="t", tools_schema=SCHEMA, max_turns=3, tool_timeout_s=1.0, max_tool_result_chars=200)


def call(name="count_records", args=None, call_id="c1"):
    return {"content": "", "tool_calls": [{"id": call_id, "function": {"name": name, "arguments": json.dumps(args or {})}}]}


def scripted(*replies):
    """call_llm that returns the given replies in order and records every messages list it saw."""
    seen, it = [], iter(replies)

    def fn(messages, tools):
        seen.append([dict(m) for m in messages])
        return next(it)

    fn.seen = seen
    return fn


def ok(content="1"):
    return lambda name, args: ToolOutcome(content)


def test_answers_without_tools():
    run = run_agent(SPEC, [{"role": "user", "content": "hi"}], call_llm=scripted({"content": "hello"}), execute_tool=ok())
    assert (run.status, run.answer, run.turns, run.steps) == (STATUS_ANSWERED, "hello", 1, [])


def test_tool_round_trip_appends_assistant_and_tool_messages():
    llm = scripted(call(args={"model": "hr.employee"}), {"content": "42 موظفاً"})
    tool = MagicMock(return_value=ToolOutcome('{"count": 42}'))
    run = run_agent(SPEC, [{"role": "user", "content": "كم؟"}], call_llm=llm, execute_tool=tool)
    assert run.answer == "42 موظفاً" and run.turns == 2
    tool.assert_called_once_with("count_records", {"model": "hr.employee"})
    second = llm.seen[1]
    assert [m["role"] for m in second] == ["user", "assistant", "tool"]
    assert second[2] == {"role": "tool", "tool_call_id": "c1", "name": "count_records", "content": '{"count": 42}'}
    assert [(s.turn, s.tool, s.ok) for s in run.steps] == [(1, "count_records", True)]


def test_plain_text_reply_is_an_answer():
    assert run_agent(SPEC, [], call_llm=scripted("نص مباشر"), execute_tool=ok()).answer == "نص مباشر"


@pytest.mark.parametrize("reply", [None, "", {}])
def test_no_reply_means_llm_unavailable(reply):
    run = run_agent(SPEC, [], call_llm=scripted(reply), execute_tool=ok())
    assert (run.status, run.answer) == (STATUS_LLM_UNAVAILABLE, None)


def test_turn_cap_stops_a_model_that_never_answers():
    llm = scripted(*[call(call_id=f"c{i}") for i in range(10)])
    run = run_agent(SPEC, [], call_llm=llm, execute_tool=ok())
    assert (run.status, run.answer, run.turns, len(run.steps)) == (STATUS_MAX_TURNS, None, 3, 3)


def test_tool_exception_is_shown_to_the_model_and_the_loop_continues():
    def boom(name, args):
        raise RuntimeError("odoo down")

    llm = scripted(call(), {"content": "تعذر الاستعلام"})
    run = run_agent(SPEC, [], call_llm=llm, execute_tool=boom)
    tool_msg = llm.seen[1][-1]
    assert json.loads(tool_msg["content"])["status"] == "error" and "odoo down" in tool_msg["content"]
    assert run.answered and run.last_tool_error and not run.steps[0].ok


def test_a_slow_tool_times_out_instead_of_hanging():
    spec = AgentSpec(name="t", tools_schema=SCHEMA, max_turns=2, tool_timeout_s=0.05)

    def slow(name, args):
        time.sleep(0.5)
        return ToolOutcome("late")

    llm = scripted(call(), {"content": "تعذر"})
    started = time.monotonic()
    run = run_agent(spec, [], call_llm=llm, execute_tool=slow)
    assert time.monotonic() - started < 0.4
    assert json.loads(llm.seen[1][-1]["content"])["status"] == "timeout"
    assert "انتهت مهلة" in run.last_tool_error


def test_huge_tool_results_are_truncated_for_the_model_only():
    llm = scripted(call(), {"content": "x"})
    run = run_agent(SPEC, [], call_llm=llm, execute_tool=ok("A" * 5000))
    sent = llm.seen[1][-1]["content"]
    assert len(sent) < 400 and "قُصَّت" in sent
    assert run.steps[0].truncated and run.steps[0].result_chars == 5000


def test_malformed_or_non_object_arguments_become_empty_args():
    tool = MagicMock(return_value=ToolOutcome("{}"))
    bad = {"content": "", "tool_calls": [{"id": "a", "function": {"name": "count_records", "arguments": "{not json"}},
                                         {"id": "b", "function": {"name": "count_records", "arguments": "[1, 2]"}}]}
    run_agent(SPEC, [], call_llm=scripted(bad, {"content": "ok"}), execute_tool=tool)
    assert [c.args for c in tool.call_args_list] == [("count_records", {}), ("count_records", {})]


def test_several_tool_calls_in_one_turn_run_in_order():
    order = []
    two = {"content": "", "tool_calls": [
        {"id": "a", "function": {"name": "first", "arguments": "{}"}},
        {"id": "b", "function": {"name": "second", "arguments": "{}"}}]}
    run_agent(SPEC, [], call_llm=scripted(two, {"content": "ok"}),
              execute_tool=lambda n, a: order.append(n) or ToolOutcome("{}"))
    assert order == ["first", "second"]


def test_final_guard_can_replace_the_answer():
    def guard(content, last_error):
        return f"⚠️ {last_error}" if last_error and "لا يوجد" in content else None

    llm = scripted(call(), {"content": "لا يوجد موظف"})
    err = lambda n, a: ToolOutcome("{}", error="Odoo غير متاح")
    assert run_agent(SPEC, [], call_llm=llm, execute_tool=err, final_guard=guard).answer == "⚠️ Odoo غير متاح"


def test_events_are_emitted_per_tool_and_a_broken_sink_is_ignored():
    got = []
    run_agent(SPEC, [], call_llm=scripted(call(), {"content": "x"}), execute_tool=ok(),
              on_event=lambda kind, payload: got.append((kind, payload["tool"], payload["ok"])))
    assert got == [("tool_call", "count_records", True)]

    def broken(kind, payload):
        raise RuntimeError("sink down")

    assert run_agent(SPEC, [], call_llm=scripted(call(), {"content": "x"}), execute_tool=ok(), on_event=broken).answered


# ---- Seraj's own loop now runs on the runtime ----

def _seraj(llm, fahas):
    seraj = SerajLLMService(api_key="sk-or-test", fahas_agent=fahas, katib_agent=MagicMock(spec=KatibAgent))
    seraj._call_llm = llm
    return seraj


def test_seraj_loop_truncates_huge_results_and_emits_a_dashboard_event(monkeypatch):
    fahas = MagicMock(spec=FahasAgent)
    fahas.execute_query_task.return_value = [{"id": i, "name": "x" * 50} for i in range(500)]
    seen = []

    def fake_llm(model_name, messages, tools=None):
        seen.append(list(messages))
        return call("search_records", {"model": "hr.employee"}) if len(seen) == 1 else {"content": "تم"}

    events = MagicMock()
    monkeypatch.setattr(seraj_llm_service, "get_events_service", lambda: events)
    answer = _seraj(fake_llm, fahas)._run_tool_calling_loop(
        "m", [{"role": "system", "content": "s"}], ConversationSession(chat_id="rt"), "q", operation_id="op1")

    assert answer == "تم"
    tool_msg = seen[1][-1]
    assert tool_msg["role"] == "tool" and len(tool_msg["content"]) < 8300 and "قُصَّت" in tool_msg["content"]
    kwargs = events.emit_event.call_args.kwargs
    assert kwargs["operation_id"] == "op1" and kwargs["event_type"] == "odoo_query"
    assert kwargs["metadata"]["tool"] == "search_records" and kwargs["metadata"]["truncated"] is True


def test_seraj_loop_without_operation_id_emits_nothing(monkeypatch):
    fahas = MagicMock(spec=FahasAgent)
    fahas.execute_query_task.return_value = {"count": 1}
    events = MagicMock()
    monkeypatch.setattr(seraj_llm_service, "get_events_service", lambda: events)
    replies = iter([call("count_records", {"model": "hr.employee"}), {"content": "1"}])
    seraj = _seraj(lambda **kw: next(replies), fahas)
    assert seraj._run_tool_calling_loop("m", [], ConversationSession(chat_id="rt2"), "q") == "1"
    events.emit_event.assert_not_called()
