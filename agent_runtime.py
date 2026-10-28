"""Generic tool-calling agent loop, shared by every LLM-driven agent (Seraj, Fahas analyst, ...).

One place owns the mechanics that every agent needs and that were missing from the ad-hoc loop
inside seraj_llm_service: a hard turn cap, a per-tool timeout, bounded tool results, one record
per tool call (AgentStep) and an event hook for observability.

It stays deliberately dumb about the domain:
* the model call is injected   (call_llm)      -> provider choice/fallback lives with the caller;
* tool execution is injected   (execute_tool)  -> the caller injects session context and turns
  domain exceptions (security rejection, Odoo error) into a ToolOutcome;
* nothing here can write to Odoo: it only runs the tools the caller hands it.
"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

STATUS_ANSWERED = "answered"
STATUS_MAX_TURNS = "max_turns"
STATUS_LLM_UNAVAILABLE = "llm_unavailable"

_TOOL_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="agent-tool")


@dataclass(frozen=True)
class ToolOutcome:
    """What a tool returned to the model. `error` is a human-readable reason when it failed."""

    content: str
    error: Optional[str] = None


@dataclass(frozen=True)
class AgentSpec:
    name: str
    tools_schema: List[Dict[str, Any]]
    max_turns: int = 5
    tool_timeout_s: Optional[float] = 60.0
    max_tool_result_chars: int = 8000


@dataclass
class AgentStep:
    turn: int
    tool: str
    args: Dict[str, Any]
    ok: bool
    seconds: float
    result_chars: int
    truncated: bool = False
    error: Optional[str] = None


@dataclass
class AgentRun:
    status: str
    answer: Optional[str] = None
    steps: List[AgentStep] = field(default_factory=list)
    turns: int = 0
    provider: Optional[str] = None
    model: Optional[str] = None
    last_tool_error: Optional[str] = None

    @property
    def answered(self) -> bool:
        return self.status == STATUS_ANSWERED


CallLLM = Callable[[List[Dict[str, Any]], List[Dict[str, Any]]], Any]
ExecuteTool = Callable[[str, Dict[str, Any]], ToolOutcome]
FinalGuard = Callable[[str, Optional[str]], Optional[str]]
EventSink = Callable[[str, Dict[str, Any]], None]


def _parse_args(raw: Any) -> Dict[str, Any]:
    try:
        args = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return {}
    return args if isinstance(args, dict) else {}


def _truncate(content: str, limit: int) -> tuple[str, bool]:
    if limit and len(content) > limit:
        note = f"\n…[قُصَّت النتيجة: عُرض {limit} من {len(content)} حرفاً. اطلب حقولاً أقل أو أضف limit]"
        return content[:limit] + note, True
    return content, False


def _run_one_tool(spec: AgentSpec, execute_tool: ExecuteTool, name: str, args: Dict[str, Any]) -> ToolOutcome:
    try:
        if spec.tool_timeout_s:
            return _TOOL_POOL.submit(execute_tool, name, args).result(timeout=spec.tool_timeout_s)
        return execute_tool(name, args)
    except FutureTimeout:
        msg = f"انتهت مهلة الأداة «{name}» ({spec.tool_timeout_s} ث)"
        return ToolOutcome(json.dumps({"status": "timeout", "error": msg}, ensure_ascii=False), error=msg)
    except Exception as exc:  # the caller's adapter should classify; this is the safety net
        msg = f"تعذّر تنفيذ الأداة «{name}»: {exc}"
        return ToolOutcome(json.dumps({"status": "error", "error": msg}, ensure_ascii=False), error=msg)


def _emit(on_event: Optional[EventSink], kind: str, payload: Dict[str, Any]) -> None:
    if on_event is None:
        return
    try:
        on_event(kind, payload)
    except Exception:  # observability must never break the agent
        logger.debug("agent event sink failed", exc_info=True)


def run_agent(
    spec: AgentSpec,
    messages: List[Dict[str, Any]],
    *,
    call_llm: CallLLM,
    execute_tool: ExecuteTool,
    final_guard: Optional[FinalGuard] = None,
    on_event: Optional[EventSink] = None,
) -> AgentRun:
    """Run `spec` until the model answers without asking for a tool, or the turn cap is hit."""
    convo = list(messages)
    run = AgentRun(status=STATUS_MAX_TURNS)

    for turn in range(1, spec.max_turns + 1):
        run.turns = turn
        reply = call_llm(convo, spec.tools_schema)

        if not reply:
            run.status = STATUS_LLM_UNAVAILABLE
            return run
        if isinstance(reply, str):  # plain-text models and test doubles
            run.status, run.answer = STATUS_ANSWERED, reply
            return run

        run.provider = reply.get("_provider_used")
        run.model = reply.get("_model_used")
        tool_calls = reply.get("tool_calls")
        content = reply.get("content") or ""

        if not tool_calls:
            if final_guard is not None:
                guarded = final_guard(content, run.last_tool_error)
                if guarded is not None:
                    content = guarded
            run.status, run.answer = STATUS_ANSWERED, content
            return run

        convo.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

        for tc in tool_calls:
            call_id = tc.get("id") or "call_1"
            func = tc.get("function") or {}
            name = func.get("name", "")
            args = _parse_args(func.get("arguments", "{}"))

            started = time.monotonic()
            outcome = _run_one_tool(spec, execute_tool, name, args)
            seconds = round(time.monotonic() - started, 3)
            body, truncated = _truncate(outcome.content, spec.max_tool_result_chars)

            if outcome.error:
                run.last_tool_error = outcome.error
            step = AgentStep(
                turn=turn, tool=name, args=args, ok=outcome.error is None, seconds=seconds,
                result_chars=len(outcome.content), truncated=truncated, error=outcome.error,
            )
            run.steps.append(step)
            _emit(on_event, "tool_call", {"agent": spec.name, **step.__dict__})

            convo.append({"role": "tool", "tool_call_id": call_id, "name": name, "content": body})

    _emit(on_event, "max_turns", {"agent": spec.name, "turns": run.turns})
    return run
