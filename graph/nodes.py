"""Graph nodes.

Design rules:
- LLM only decides in: classify_intent (later), seraj_think.
- Everything on the write path is deterministic code.
- The LLM never receives a write tool. Writes happen only in katib_execute,
  after policy_gate + human_approval.
- Memory: nodes return only NEW messages; the reducer appends them per thread.
- Company context is explicit state (company_id/company_name), not LLM memory.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Set

from langgraph.types import interrupt

from graph.state import SerajState

logger = logging.getLogger("graph.nodes")

MAX_TURNS = 5
HISTORY_LIMIT = 12
ENABLE_WRITE_PATH = os.environ.get("ENABLE_WRITE_PATH", "0") == "1"

ALL_COMPANIES_PHRASES = (
    "كل الشركات", "جميع الشركات", "كافة الشركات",
    "كل المنشآت", "جميع المنشآت", "كل المنشات", "جميع المنشات",
)

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
# Company-context helpers (pure, unit-tested)
# --------------------------------------------------------------------------
def wants_all_companies(query: str) -> bool:
    q = query or ""
    return any(p in q for p in ALL_COMPANIES_PHRASES)


def collect_companies(obj: Any, out: Dict[str, str]) -> None:
    """Walks a tool result and records every {id, name} pair as id->name."""
    if isinstance(obj, dict):
        if "id" in obj and isinstance(obj.get("name"), str):
            try:
                out[str(int(obj["id"]))] = obj["name"]
            except (TypeError, ValueError):
                pass
        for v in obj.values():
            collect_companies(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_companies(v, out)


def resolve_company_args(name: str, args: Dict[str, Any], company_id: Optional[int], accepts: Optional[Set[str]]):
    """Returns (args, company_id).

    - explicit company_id in the tool call becomes the sticky company;
    - otherwise the sticky company is injected into tools that accept it.
    """
    explicit = args.get("company_id")
    if explicit not in (None, ""):
        try:
            return args, int(explicit)
        except (TypeError, ValueError):
            return args, company_id
    if company_id and not name.startswith("list_compan"):
        takes = ("company_id" in args) if accepts is None else (name in accepts)
        if takes:
            args["company_id"] = company_id
    return args, company_id


def _tools_accepting_company() -> Optional[Set[str]]:
    try:
        from odoo_agent_tools import SERAJ_ODOO_TOOLS_SCHEMA
    except Exception:
        return None
    names: Set[str] = set()
    for t in SERAJ_ODOO_TOOLS_SCHEMA:
        fn = t.get("function", t)
        props = (fn.get("parameters") or {}).get("properties") or {}
        if "company_id" in props:
            names.add(fn.get("name"))
    return names


def company_suffix(answer: str, company_id: Optional[int], company_name: Optional[str]) -> str:
    if not company_id or not company_name or company_name in answer:
        return answer
    return f"{answer}\n\n(ضمن شركة {company_name})"


def build_session_context(company_id: Optional[int], company_name: Optional[str]) -> str:
    lines = ["\n\n[سياق الجلسة]"]
    if company_id:
        lines.append(
            f"- الشركة المحددة حالياً: {company_name or 'غير معروفة الاسم'} (المعرّف {company_id}). "
            "استخدمها تلقائياً في الاستعلامات ما لم يطلب المستخدم غيرها أو يقل «كل الشركات»."
        )
    lines.append(
        "- إذا كانت عبارة المستخدم نسبية أو غامضة (مثل «الشركة الثانية» أو «الأخرى» أو «نفسها») "
        "فأكّد التفسير بسؤال قصير ولا تخمّن."
    )
    return "\n".join(lines)


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
    if wants_all_companies(query):
        update["company_id"] = None
        update["company_name"] = None
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
    # ✅ جديد: نذهب للـ Meta-Agent للتخطيط الذكي
    return "seraj_meta_orchestration"


# --------------------------------------------------------------------------
# Read path: same behaviour as _run_tool_calling_loop, as graph nodes
# --------------------------------------------------------------------------
def seraj_think(state: SerajState) -> Dict[str, Any]:
    from odoo_agent_tools import SERAJ_ODOO_TOOLS_SCHEMA

    svc = _seraj()
    session = svc.session_manager.get_session(state.get("chat_id", "default"))
    system_prompt = svc._build_system_prompt(session, state.get("user_name", "مستخدم"), None)
    system_prompt += build_session_context(state.get("company_id"), state.get("company_name"))
    messages = [{"role": "system", "content": system_prompt}] + trim_history(state.get("messages", []))

    try:
        msg = svc._call_openrouter(
            model_name=svc.model,
            messages=messages,
            tools=SERAJ_ODOO_TOOLS_SCHEMA,
        )
    except (ValueError, Exception) as e:
        # التعامل مع أخطاء LLM (ValueError, HTTPError, Timeout, إلخ)
        import logging
        logger = logging.getLogger("seraj_think")
        logger.error(f"❌ LLM error in seraj_think: {e}")
        return {
            "error": "llm_error",
            "last_tool_error": str(e),
            "last_assistant": {},
        }
    
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
        # ✅ fahas_tools هو المسار الوحيد بعد حذف fahas_agentic_query
        return "fahas_tools"
    return "finalize"


def fahas_tools(state: SerajState) -> Dict[str, Any]:
    """Delegates every tool call to Fahas (read-only, whitelisted)."""
    from fahas_service import get_fahas_agent
    from odoo_agent_tools import OdooToolExecutionError, OdooToolSecurityError

    fahas = get_fahas_agent()
    accepts = _tools_accepting_company()
    company_id: Optional[int] = state.get("company_id")
    companies: Dict[str, str] = dict(state.get("companies") or {})
    new_msgs: List[Dict[str, Any]] = []
    last_error: Optional[str] = state.get("last_tool_error")

    for tc in (state.get("last_assistant") or {}).get("tool_calls", []):
        call_id = tc.get("id") or "call_1"
        fn = tc.get("function") or {}
        name = fn.get("name", "")
        raw = fn.get("arguments", "{}")
        try:
            args = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except Exception:
            args = {}
        if "connection_id" in args and not args["connection_id"]:
            args["connection_id"] = state.get("connection_id")
        args, company_id = resolve_company_args(name, args, company_id, accepts)

        try:
            result = fahas.execute_query_task(name, args)
            result_str = json.dumps(result, ensure_ascii=False)
            # ✅ تجميع الشركات من أي نتيجة تحتوي على company (بما في ذلك count_records)
            if "compan" in name or (isinstance(result, dict) and result.get("company_id")):
                collect_companies(result, companies)
                # إذا كان company_id محدداً في النتيجة، أضف الشركة من قاعدة البيانات
                if isinstance(result, dict) and result.get("company_id") and str(result["company_id"]) not in companies:
                    try:
                        comp_result = fahas.execute_query_task("list_companies", {})
                        for comp in comp_result:
                            if comp.get("id") == result["company_id"]:
                                companies[str(comp["id"])] = comp.get("name", "")
                                break
                    except:
                        pass
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

    company_name = companies.get(str(company_id)) if company_id else None
    return {
        "messages": new_msgs,
        "last_tool_error": last_error,
        "company_id": company_id,
        "company_name": company_name,
        "companies": companies,
    }


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
    
    # إذا لم يكتب النموذج جواباً لكن توجد نتائج أدوات، اعرضها
    if not content:
        messages = state.get("messages", [])
        tool_results = []
        for msg in reversed(messages):
            if msg.get("role") == "tool":
                try:
                    result = json.loads(msg.get("content", "null"))
                    tool_results.append(result)
                except:
                    pass
            elif msg.get("role") == "assistant":
                break  # توقف عند آخر assistant message
        
        if tool_results:
            # عرض نتائج الأدوات بدلاً من رسالة العجز
            first_result = tool_results[0]
            if isinstance(first_result, list):
                count = len(first_result)
                if count > 0 and isinstance(first_result[0], dict) and "name" in first_result[0]:
                    names = [item.get("name", "") for item in first_result[:3]]
                    answer = f"وجدت {count} عنصر: {', '.join(names)}{'، وغيرها' if count > 3 else ''}."
                else:
                    answer = f"وجدت {count} عنصر."
            elif isinstance(first_result, int):
                answer = f"العدد الإجمالي: {first_result}"
            elif isinstance(first_result, dict):
                answer = json.dumps(first_result, ensure_ascii=False, indent=2)
            else:
                answer = str(first_result)
            return {"answer": company_suffix(answer, state.get("company_id"), state.get("company_name"))}
        
        # لا توجد نتائج أدوات أيضاً
        return {"answer": "⚠️ لم أستطع إكمال الطلب ضمن الحد الأقصى للخطوات."}
    
    answer = clean_math_formatting(content)
    return {"answer": company_suffix(answer, state.get("company_id"), state.get("company_name"))}


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


# ==============================================================================
# New Routing Functions for Agentic Agents
# ==============================================================================

def route_after_compliance(state: SerajState) -> str:
    """
    التوجيه بعد التحقق من الامتثال (mudaqqiq_verify)
    
    Returns:
        - "hares_guard": إذا كان الامتثال موافق → نكمل للحارس
        - "musleh_heal": إذا كانت هناك مخالفات قابلة للإصلاح → نذهب للمصلح
        - "finalize_write": إذا كان هناك مخالفات حرجة → رفض
    """
    approved = state.get("compliance_approved", False)
    violations = state.get("compliance_violations", [])
    
    if approved:
        logger.info("✅ Compliance approved → hares_guard")
        return "hares_guard"
    
    # التحقق من إمكانية الإصلاح
    can_fix = any(v.get("can_be_fixed", False) for v in violations)
    
    if can_fix:
        logger.info("🔧 Violations can be fixed → musleh_heal")
        return "musleh_heal"
    
    logger.info("❌ Critical violations → finalize_write")
    return "finalize_write"


def route_after_security(state: SerajState) -> str:
    """
    التوجيه بعد فحص الأمان (hares_guard)
    
    Returns:
        - "policy_gate": إذا وافق الحارس → نكمل
        - "finalize_write": إذا رفض → توقف
    """
    approved = state.get("security_approved", False)
    
    if approved:
        logger.info("✅ Security approved → policy_gate")
        return "policy_gate"
    
    logger.info("❌ Security rejected → finalize_write")
    return "finalize_write"


def route_to_matching(state: SerajState) -> str:
    """
    التوجيه للمطابقة (muwaffaq_match)
    
    يُستدعى عندما تحتاج سراج لمطابقة بيانات
    """
    has_match_request = bool(state.get("match_request"))
    
    if has_match_request:
        logger.info("🔗 Match request found → muwaffaq_match")
        return "muwaffaq_match"
    
    return "seraj_think"
