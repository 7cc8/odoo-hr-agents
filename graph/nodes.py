"""Graph nodes.

Design rules:
- LLM only decides in: classify_intent (later), seraj_think.
- Everything on the write path is deterministic code.
- The LLM never receives a write tool. Writes happen only in katib_execute,
  after policy_gate + human_approval.
- Memory: nodes return only NEW messages; the reducer appends them per thread.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from langgraph.types import interrupt

from graph.state import SerajState

logger = logging.getLogger("graph.nodes")

MAX_TURNS = 5
HISTORY_LIMIT = 12
ENABLE_WRITE_PATH = os.environ.get("ENABLE_WRITE_PATH", "0") == "1"

_service = None


def _seraj():
    """Lazy singleton of the legacy service; reused for prompt + OpenRouter call."""
    global _service
    if _service is None:
        from seraj_llm_service import SerajLLMService
        _service = SerajLLMService()
    return _service


# --------------------------------------------------------------------------
# History helpers
# --------------------------------------------------------------------------
def sanitize_history(msgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop assistant tool_calls without full tool replies, and orphan tool messages."""
    n = len(msgs)
    kept: List[Dict[str, Any]] = []
    for i, m in enumerate(msgs):
        if m.get("role") == "assistant" and m.get("tool_calls"):
            ids = {tc.get("id") or "call_1" for tc in m["tool_calls"]}
            got = set()
            j = i + 1
            while j < n and msgs[j].get("role") == "tool":
                got.add(msgs[j].get("tool_call_id"))
                j += 1
            if not ids <= got:
                continue
        kept.append(m)

    valid_ids = set()
    for m in kept:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            valid_ids |= {tc.get("id") or "call_1" for tc in m["tool_calls"]}
    return [m for m in kept if m.get("role") != "tool" or m.get("tool_call_id") in valid_ids]


def trim_history(msgs: List[Dict[str, Any]], limit: int = HISTORY_LIMIT) -> List[Dict[str, Any]]:
    """Last `limit` clean messages, always starting at a user message."""
    clean = sanitize_history(msgs)
    window = clean[-limit:]
    while window and window[0].get("role") != "user":
        window = window[1:]
    if not window:
        for m in reversed(clean):
            if m.get("role") == "user":
                return [m]
    return window


# --------------------------------------------------------------------------
# Entry / routing
# --------------------------------------------------------------------------
def ingest_user_message(state: SerajState) -> Dict[str, Any]:
    """Appends the new user query to history and resets per-run scratch fields."""
    query = (state.get("user_query") or "").strip()
    update: Dict[str, Any] = {
        "turns": 0,
        "last_tool_error": None,
        "last_assistant": {},
        "error": None,
        "answer": None,
    }
    if query:
        update["messages"] = [{"role": "user", "content": query}]
    else:
        update["error"] = "empty_query"
    return update


def classify_intent(state: SerajState) -> Dict[str, Any]:
    """Phase 1: everything is 'read'.

    TODO (Phase 3): replace with structured LLM output:
        {intent, action, target, negated}  -> deterministic validation after.
    Until then, write requests stay on the legacy chat_turn path.
    """
    return {"intent": "read"}


def route_after_ingest(state: SerajState) -> str:
    return "finalize" if state.get("error") else "classify_intent"


def route_intent(state: SerajState) -> str:
    if state.get("intent") == "write" and ENABLE_WRITE_PATH:
        return "prepare_plan"
    return "seraj_think"


# --------------------------------------------------------------------------
# Read path: same behaviour as _run_tool_calling_loop, as graph nodes
# --------------------------------------------------------------------------
def seraj_think(state: SerajState) -> Dict[str, Any]:
    from odoo_agent_tools import SERAJ_ODOO_TOOLS_SCHEMA

    svc = _seraj()
    session = svc.session_manager.get_session(state.get("chat_id", "default"))
    system_prompt = svc._build_system_prompt(session, state.get("user_name", "مستخدم"), None)
    messages = [{"role": "system", "content": system_prompt}] + trim_history(state.get("messages", []))

    msg = svc._call_openrouter(
        model_name=svc.model,
        messages=messages,
        tools=SERAJ_ODOO_TOOLS_SCHEMA,
    )
    if not msg:
        return {"error": "llm_no_response", "last_assistant": {}}
    if isinstance(msg, str):
        msg = {"content": msg}

    entry: Dict[str, Any] = {"role": "assistant", "content": msg.get("content") or ""}
    if msg.get("tool_calls"):
        entry["tool_calls"] = msg["tool_calls"]
    return {
        "messages": [entry],
        "last_assistant": msg,
        "turns": state.get("turns", 0) + 1,
    }


def route_after_think(state: SerajState) -> str:
    if state.get("error"):
        return "finalize"
    msg = state.get("last_assistant") or {}
    if msg.get("tool_calls") and state.get("turns", 0) < MAX_TURNS:
        return "fahas_tools"
    return "finalize"


def fahas_tools(state: SerajState) -> Dict[str, Any]:
    """Delegates every tool call to Fahas (read-only, whitelisted)."""
    from fahas_service import get_fahas_agent
    from odoo_agent_tools import OdooToolExecutionError, OdooToolSecurityError

    fahas = get_fahas_agent()
    new_msgs: List[Dict[str, Any]] = []
    last_error: Optional[str] = state.get("last_tool_error")

    for tc in (state.get("last_assistant") or {}).get("tool_calls", []):
        call_id = tc.get("id") or "call_1"
        fn = tc.get("function") or {}
        name = fn.get("name", "")
        raw = fn.get("arguments", "{}")
        try:
            args = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            args = {}
        if "connection_id" in args and not args["connection_id"]:
            args["connection_id"] = state.get("connection_id")
        if state.get("company_id") and "company_id" in args and args["company_id"] is None:
            args["company_id"] = state["company_id"]

        try:
            result = fahas.execute_query_task(name, args)
            result_str = json.dumps(result, ensure_ascii=False)
        except OdooToolSecurityError as e:
            last_error = f"رفض أمني / صلاحيات: {e}"
            result_str = json.dumps({"status": "security_rejected", "error": str(e)}, ensure_ascii=False)
        except OdooToolExecutionError as e:
            last_error = f"خطأ في الاتصال بخادم Odoo: {e}"
            result_str = json.dumps({"status": "odoo_error", "error": str(e)}, ensure_ascii=False)
        except Exception as e:
            last_error = f"خطأ في الاتصال بقاعدة بيانات Odoo: {e}"
            result_str = json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)

        new_msgs.append({"role": "tool", "tool_call_id": call_id, "name": name, "content": result_str})

    return {"messages": new_msgs, "last_tool_error": last_error}


def finalize(state: SerajState) -> Dict[str, Any]:
    from seraj_llm_service import clean_math_formatting

    err_code = state.get("error")
    if err_code == "empty_query":
        return {"answer": "اكتب سؤالك أولاً لأساعدك."}
    if err_code:
        return {"answer": "⚠️ واجهت صعوبة في معالجة طلبك حالياً. يرجى إعادة المحاولة."}

    content = ((state.get("last_assistant") or {}).get("content") or "").strip()
    err = state.get("last_tool_error")
    if err and any(p in content for p in ("لم يتم العثور على أي موظف", "لم نجد أي موظف", "لا يوجد موظف")):
        return {"answer": f"⚠️ تعذر إتمام الاستعلام بسبب {err}. يرجى مراجعة حالة الاتصال بـ Odoo والصلاحيات."}
    if not content:
        return {"answer": "⚠️ لم أستطع إكمال الطلب ضمن الحد الأقصى للخطوات."}
    return {"answer": clean_math_formatting(content)}


# --------------------------------------------------------------------------
# Write path (STUBS). Deterministic. Disabled unless ENABLE_WRITE_PATH=1.
# --------------------------------------------------------------------------
def prepare_plan(state: SerajState) -> Dict[str, Any]:
    # TODO: Fahas resolves target by ID -> unified Plan (plan_id, TTL, single-use).
    #       Reuse deletion_policy.create_deletion_plan, extend to update/create.
    return {"error": "write_path_not_implemented"}


def policy_gate(state: SerajState) -> Dict[str, Any]:
    # TODO: Muddaqiq (rules) + Hares (policy/permissions/env) as real code, no events-only stubs.
    return {"policy_ok": False}


def route_after_policy(state: SerajState) -> str:
    return "human_approval" if state.get("policy_ok") else "finalize_write"


def human_approval(state: SerajState) -> Dict[str, Any]:
    """Pauses the graph. Resume with Command(resume={'approved': True, 'plan_id': ...})."""
    plan = state.get("plan") or {}
    decision = interrupt({"plan": plan, "question": "اعتماد الخطة؟ (تأكيد/إلغاء)"})
    ok = (
        isinstance(decision, dict)
        and decision.get("approved") is True
        and decision.get("plan_id") == plan.get("plan_id")
    )
    return {"approved": ok}


def route_after_approval(state: SerajState) -> str:
    return "katib_execute" if state.get("approved") else "finalize_write"


def katib_execute(state: SerajState) -> Dict[str, Any]:
    # TODO: get_katib_agent().execute_approved_action(plan) after session-style validity check.
    return {"exec_result": {"status": "not_implemented"}}


def fahas_verify(state: SerajState) -> Dict[str, Any]:
    # TODO: independent verification; compare read value with expected value.
    return {"verified": False}


def sijil_log(state: SerajState) -> Dict[str, Any]:
    # TODO: write audit record via sijil_audit_service (must not swallow errors silently).
    return {}


def finalize_write(state: SerajState) -> Dict[str, Any]:
    if state.get("error"):
        return {"answer": "⚠️ مسار الكتابة غير مفعّل بعد في الرسم البياني."}
    if state.get("approved") is False:
        return {"answer": "🚫 تم إلغاء العملية دون أي تعديل في Odoo."}
    if state.get("verified"):
        return {"answer": "✅ تم التنفيذ والتحقق والتوثيق."}
    return {"answer": "⚠️ لم يتم تأكيد نتيجة العملية."}
