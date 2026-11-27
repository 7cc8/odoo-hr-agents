"""
Chat & Multi-Agent Assistant Routes Router
==========================================
Handles unified conversational endpoints for Seraj and agent interaction,
thread management, and assistant discovery.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.common import audit_log_access, verify_write_auth, _get_readonly_repo_cls

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat & Assistants"])


# ==================== SCHEMAS ====================

class SerajChatApiRequest(BaseModel):
    message: str
    chat_id: str = "web_default"
    operation_id: Optional[str] = None
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    connection_id: Optional[str] = "default"
    user_name: Optional[str] = "المستخدم"


class ChatMessage(BaseModel):
    message: str
    thread_id: Optional[str] = None
    file_path: Optional[str] = None


# ==================== CONVERSATIONAL CHAT (SERAJ) ====================

@router.post("/api/seraj/chat")
async def post_seraj_chat_endpoint(payload: SerajChatApiRequest, request: Request) -> Dict[str, Any]:
    """Unified conversational interaction with Seraj, coordinating multi-agent actions."""
    audit_log_access("/api/seraj/chat", request, {"chat_id": payload.chat_id, "op_id": payload.operation_id})
    import asyncio
    from agent_events_service import get_events_service
    from seraj_llm_service import SerajLLMService
    from seraj_hr_context import contract_reference, policy_save_request
    from seraj_session_manager import SerajSessionManager

    # While a delete/archive/create/update awaits confirmation, the next message may
    # confirm and execute it, so the write token is required (the dashboard prompts on 401).
    private_contract = bool(contract_reference(payload.message))
    policy_save = policy_save_request(payload.message) is not None
    if SerajSessionManager.get_instance().get_session(payload.chat_id).pending_action or private_contract or policy_save:
        verify_write_auth(request)

    srv = get_events_service()
    import time, uuid

    # فصل خطوات كل رسالة عن الرسائل السابقة برقم عملية / دورة فريد ومستقل
    op_id = payload.operation_id
    if not op_id or (srv.get_operation(op_id) and srv.get_operation(op_id).get("events")):
        op_id = f"op_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    c_id = payload.company_id
    c_name = payload.company_name
    if not c_id:
        try:
            repo = _get_readonly_repo_cls()()
            def_c = repo.get_default_company()
            c_id = def_c.get("id", 1)
            c_name = def_c.get("name", "الشركة الرئيسية")
        except Exception:
            c_id = 1
            c_name = "الشركة الرئيسية"

    srv.start_operation(
        user_query=payload.message,
        operation_type="conversation",
        company_id=c_id,
        company_name=c_name,
        connection_id=payload.connection_id or "default",
        requester=payload.user_name or "المستخدم",
        chat_id=payload.chat_id,
        operation_id=op_id,
    )

    seraj = SerajLLMService()
    try:
        reply = await asyncio.to_thread(
            seraj.chat_turn,
            user_query=payload.message,
            chat_id=payload.chat_id,
            user_name=payload.user_name or "المستخدم",
            connection_id=payload.connection_id,
            company_id=c_id if private_contract or policy_save else payload.company_id,
            operation_id=op_id,
            **({"allow_contract_pay": True} if private_contract else {}),
        )
    except Exception as exc:
        srv.emit_event(
            operation_id=op_id,
            agent="seraj",
            event_type="error",
            status="failed",
            description_ar=f"واجه سراج خطأ أثناء المعالجة: {exc}",
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=f"تعذر معالجة الطلب: {exc}")

    session = SerajSessionManager.get_instance().get_session(payload.chat_id)
    op = srv.get_operation(op_id)

    from llm_config_manager import load_llm_config
    cfg = load_llm_config()
    prov_used = getattr(seraj, "last_provider_used", None)
    model_used = getattr(seraj, "last_model_used", None)
    prov_name = cfg.get("cloud", {}).get("provider", "Cloud") if prov_used == "cloud" else "Ollama"

    llm_meta = {
        "provider": prov_used,
        "model": model_used,
        "provider_name": prov_name,
        "mode": cfg.get("mode", "auto"),
        "fallback_reason": getattr(seraj, "last_cloud_error", None) if cfg["active_provider"] == "cloud" and prov_used != "cloud" else None,
    }

    if op:
        if session.pending_action:
            op["pending_action"] = session.pending_action
            op["plan"] = session.pending_action
        elif not session.pending_clarification:
            srv.update_operation_status(op_id, "completed")
            op["status"] = "completed"

    return {
        "status": "success",
        "operation_id": op_id,
        "response": reply,
        "operation": op,
        "pending_action": session.pending_action,
        "pending_clarification": session.pending_clarification,
        "llm_meta": llm_meta,
        "reasoning_steps": getattr(seraj, "last_turn_reasoning_steps", []),
        "thinking_duration_sec": getattr(seraj, "last_turn_duration_sec", None),
        "timestamp": getattr(seraj, "last_turn_timestamp", None),
        "user_timestamp": getattr(seraj, "last_turn_user_timestamp", None),
    }


@router.post("/api/seraj/cancel/{operation_id}")
async def cancel_seraj_operation(operation_id: str, request: Request) -> Dict[str, Any]:
    """إلغاء عملية جارية بناءً على طلب المستخدم وإيقاف البث."""
    audit_log_access(f"/api/seraj/cancel/{operation_id}", request, {"op_id": operation_id})
    from agent_events_service import get_events_service
    srv = get_events_service()
    op = srv.get_operation(operation_id)
    if not op:
        return {"status": "not_found", "message": "العملية غير موجودة", "operation_id": operation_id}

    srv.emit_event(
        operation_id=operation_id,
        agent="seraj",
        event_type="operation_cancelled",
        status="cancelled",
        description_ar="تم إيقاف استجابة سراج والوكلاء بناءً على طلب المستخدم (تراجع صريح).",
    )
    srv.update_operation_status(operation_id, "cancelled")
    return {"status": "success", "message": "تم إيقاف العملية بنجاح", "operation_id": operation_id}


# ==================== SESSIONS MANAGEMENT ====================

@router.get("/api/seraj/sessions")
def get_seraj_sessions_endpoint(request: Request) -> Dict[str, Any]:
    """Returns the list of active chat sessions with titles and timestamps."""
    from seraj_session_manager import SerajSessionManager
    sessions = SerajSessionManager.get_instance().list_sessions()
    return {"status": "success", "sessions": sessions}


@router.get("/api/seraj/session/{chat_id}")
def get_seraj_session_detail_endpoint(chat_id: str, request: Request) -> Dict[str, Any]:
    """Returns the full message history and metadata for a specific chat session."""
    from seraj_session_manager import SerajSessionManager
    mgr = SerajSessionManager.get_instance()
    if chat_id not in mgr.sessions:
        s = mgr.get_session(chat_id)
    else:
        s = mgr.sessions[chat_id]
    history = s.history
    if any(message.get("sensitive") for message in history):
        try:
            verify_write_auth(request)
        except HTTPException:
            history = [{**message, "content": "تتطلب تفاصيل العقد رمز المشغّل المعتمد."}
                       if message.get("sensitive") else message for message in history]
    return {
        "status": "success",
        "session": {
            "chat_id": s.chat_id,
            "title": s.title or (f"جلسة {s.chat_id[:8]}" if s.chat_id.startswith("web_") else s.chat_id),
            "created_at": s.created_at,
            "updated_at": s.updated_at,
            "history": history,
            "pending_action": s.pending_action,
            "pending_clarification": s.pending_clarification,
            "company_id": s.company_id,
            "company_name": s.company_name,
            "handoffs": getattr(s, "handoffs", []),
            "checkpoints": getattr(s, "checkpoints", []),
        }
    }


@router.delete("/api/seraj/session/{chat_id}")
def delete_seraj_session_endpoint(chat_id: str, request: Request) -> Dict[str, Any]:
    """Deletes or resets a specific chat session."""
    from seraj_session_manager import SerajSessionManager
    SerajSessionManager.get_instance().reset_session(chat_id)
    return {"status": "success", "message": f"تم تصفير الجلسة {chat_id} بنجاح."}


@router.delete("/api/seraj/sessions")
def clear_all_seraj_sessions_endpoint(request: Request) -> Dict[str, Any]:
    """Clears and deletes all stored chat sessions."""
    from seraj_session_manager import SerajSessionManager
    SerajSessionManager.get_instance().clear_all_sessions()
    return {"status": "success", "message": "تم حذف وتصفير كافة جلسات المحادثة بنجاح."}


# ==================== ASSISTANTS & DISCOVERY ====================

@router.post("/assistants/search")
@router.get("/assistants/search")
async def search_assistants_endpoint(request: Request) -> List[Dict[str, Any]]:
    """Returns the list of available assistants for UI clients."""
    return [
        {
            "assistant_id": "seraj",
            "graph_id": "seraj",
            "name": "سراج - منسق الموارد البشرية Odoo",
            "description": "منسق ومنظومة وكلاء إدارة الموارد البشرية Odoo (8 وكلاء معتمدين)",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "agents": ["seraj", "fahas", "mudaqqiq", "katib", "mowafaq", "hares", "musleh", "sijil"]
            }
        }
    ]


@router.get("/assistants/{assistant_id}")
async def get_assistant_detail_endpoint(assistant_id: str, request: Request) -> Dict[str, Any]:
    """Returns details for a specific assistant."""
    return {
        "assistant_id": assistant_id,
        "graph_id": "seraj",
        "name": "سراج - منسق الموارد البشرية Odoo",
        "description": "منسق ومنظومة وكلاء إدارة الموارد البشرية Odoo",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {}
    }


@router.post("/threads/search")
@router.get("/threads/search")
async def search_threads_endpoint(request: Request) -> List[Dict[str, Any]]:
    """Returns list of threads for conversational clients."""
    from seraj_session_manager import SerajSessionManager
    sessions = SerajSessionManager.get_instance().list_sessions()
    return [
        {
            "thread_id": s["chat_id"],
            "title": s["title"],
            "created_at": s["created_at"],
            "updated_at": s["updated_at"],
            "metadata": {"message_count": s["message_count"]},
        }
        for s in sessions
    ]


# ==================== STANDALONE CHAT ENDPOINT ====================

@router.post("/api/chat")
async def chat_endpoint(req: ChatMessage, request: Request) -> Dict[str, Any]:
    """
    نقطة نهاية المحادثة الموحدة مع دورة حياة تنفيذ الأدوات المنضبطة (Bounded Tool Execution Loop).
    تستعلم أدوات Odoo الحية وتسجل العمليات في سجل الأدوات مع مسار تراجعي ذكي (Fallback).
    """
    audit_log_access("/api/chat", request, {"message_length": len(req.message)})

    try:
        from agents.llm_provider import get_llm_provider
        from agents.tool_registry import ToolRegistry
        from memory.manager import MemoryManager
        from seraj_hr_context import tool_result_text

        thread_id = req.thread_id or f"thread_{int(datetime.now().timestamp())}"
        working_mem = MemoryManager.get_instance().get_working_memory(thread_id)

        provider = get_llm_provider()
        tools_schema = ToolRegistry.get_instance().get_tools_schema("seraj")

        messages = [
            {
                "role": "system",
                "content": "أنت سراج، المساعد والمنسق الذكي لإدارة الموارد البشرية في Odoo. "
                           "ساعد المستخدم في الاستفسارات والعمليات حول الموظفين، الأقسام، الشركات، واللوائح بدقة وموثوقية."
            }
        ]

        # تحميل الرسائل السابقة من الذاكرة العاملة المرتبطة بـ thread_id
        for prev_msg in working_mem.recent_messages:
            role = prev_msg.get("role")
            content = prev_msg.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        # إضافة رسالة المستخدم الحالية للجلسة وللذاكرة العاملة
        messages.append({
            "role": "user",
            "content": req.message
        })
        working_mem.add_message("user", req.message)

        final_content = ""
        max_turns = 4
        current_turn = 0

        while current_turn < max_turns:
            current_turn += 1
            response = provider.call(messages=messages, tools=tools_schema if tools_schema else None, temperature=0.7)

            tool_calls = response.get("tool_calls")
            if not tool_calls:
                final_content = response.get("content", "")
                break

            # تسجيل رد المساعد مع طلبات الأدوات
            assistant_content = response.get("content") or ""
            messages.append({
                "role": "assistant",
                "content": assistant_content,
                "tool_calls": tool_calls,
            })

            # تنفيذ الأدوات عبر سجل الأدوات الموحد
            for call in tool_calls:
                call_id = call.get("id", f"call_{int(time.time())}_{current_turn}")
                fn_info = call.get("function", {})
                fn_name = fn_info.get("name")
                fn_args_raw = fn_info.get("arguments", {})

                if isinstance(fn_args_raw, str):
                    try:
                        fn_args = json.loads(fn_args_raw)
                    except Exception:
                        fn_args = {}
                elif isinstance(fn_args_raw, dict):
                    fn_args = fn_args_raw
                else:
                    fn_args = {}

                try:
                    tool_res = ToolRegistry.get_instance().execute_tool(
                        tool_name=fn_name,
                        agent_name="seraj",
                        args=fn_args,
                    )
                except Exception as tool_err:
                    logger.warning(f"Error executing tool {fn_name}: {tool_err}")
                    tool_res = {"status": "error", "message": str(tool_err)}

                res_str = tool_result_text(tool_res)

                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": fn_name,
                    "content": res_str,
                })
        if not final_content:
            raise HTTPException(status_code=503, detail="تعذّر الحصول على رد من النموذج لهذه الرسالة.")

        # حفظ رد المساعد النهائي في الذاكرة العاملة المرتبطة بـ thread_id
        if final_content:
            working_mem.add_message("assistant", final_content)

        return {
            "status": "success",
            "thread_id": thread_id,
            "response": {
                "content": final_content,
                "provider": response.get("provider", provider.provider)
            },
            "current_agent": "seraj",
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Legacy chat failed")
        raise HTTPException(status_code=500, detail="تعذّر إكمال المحادثة.") from None


# Alias للتوافقية العكسية المطلقة مع أي كود خارجي
chat_with_langgraph = chat_endpoint


@router.get("/api/chat/threads")
async def list_chat_threads(request: Request) -> List[Dict[str, Any]]:
    """List all active chat threads."""
    audit_log_access("/api/chat/threads", request)
    return []


@router.get("/api/chat/threads/{thread_id}/history")
async def get_thread_history(thread_id: str, request: Request) -> Dict[str, Any]:
    """Get message history for a specific thread."""
    audit_log_access(f"/api/chat/threads/{thread_id}/history", request)
    try:
        from memory.manager import MemoryManager
        working_mem = MemoryManager.get_instance().get_working_memory(thread_id)
        return {"thread_id": thread_id, "messages": working_mem.recent_messages}
    except Exception:
        return {"thread_id": thread_id, "messages": []}


# ==================== MEMORY MANAGEMENT ====================

class MemoryItemRequest(BaseModel):
    content: str
    key: Optional[str] = ""
    category: Optional[str] = "general"
    importance: Optional[int] = 3


class MemoryItemUpdateRequest(BaseModel):
    content: Optional[str] = None
    key: Optional[str] = None
    category: Optional[str] = None
    importance: Optional[int] = None


@router.get("/api/memory/items")
def get_memory_items(category: Optional[str] = None, request: Request = None) -> Dict[str, Any]:
    """استرجاع كافة عناصر الذاكرة طويلة المدى والكيانات النشطة للجلسات."""
    if request:
        audit_log_access("/api/memory/items", request)
    from memory.manager import MemoryManager
    from seraj_session_manager import SerajSessionManager
    mgr = MemoryManager.get_instance()
    facts = mgr.get_long_term_facts(category=category)
    stats = mgr.get_memory_stats()

    active_sessions = SerajSessionManager.get_instance().list_sessions()
    recent_active_entities = {}
    for s_info in active_sessions[:5]:
        s = SerajSessionManager.get_instance().get_session(s_info["chat_id"])
        if s.active_entities:
            recent_active_entities[s_info["chat_id"]] = {
                "title": s_info["title"],
                "entities": s.active_entities,
                "summary": s.get_context_summary(),
            }

    return {
        "status": "success",
        "facts": facts,
        "active_entities_by_session": recent_active_entities,
        "stats": stats,
    }


@router.get("/api/memory/episodes")
def get_memory_episodes(
    limit: int = 50,
    offset: int = 0,
    q: Optional[str] = None,
    request: Request = None,
) -> Dict[str, Any]:
    """استرجاع سجل حلقات الذاكرة من SQLite مع دعم البحث والتصفح."""
    if request:
        audit_log_access("/api/memory/episodes", request)
    from memory.manager import MemoryManager
    mgr = MemoryManager.get_instance()
    res = mgr.get_episodes_list(limit=limit, offset=offset, q=q)
    return {
        "status": "success",
        "items": res.get("items", []),
        "total": res.get("total", 0),
        "limit": limit,
        "offset": offset,
    }


@router.post("/api/memory/items")
def create_memory_item(payload: MemoryItemRequest, request: Request) -> Dict[str, Any]:
    """إضافة حقيقة جديدة إلى الذاكرة طويلة المدى لسراج والوكلاء."""
    audit_log_access("/api/memory/items", request, {"action": "create", "key": payload.key})
    from memory.manager import MemoryManager
    mgr = MemoryManager.get_instance()
    item = mgr.save_long_term_fact(
        content=payload.content,
        key=payload.key or "",
        category=payload.category or "general",
        importance=payload.importance or 3,
    )
    return {"status": "success", "item": item}


@router.put("/api/memory/items/{item_id}")
def update_memory_item(item_id: str, payload: MemoryItemUpdateRequest, request: Request) -> Dict[str, Any]:
    """تعديل حقيقة في الذاكرة طويلة المدى."""
    audit_log_access(f"/api/memory/items/{item_id}", request, {"action": "update", "id": item_id})
    from memory.manager import MemoryManager
    mgr = MemoryManager.get_instance()
    updated = mgr.update_long_term_fact(
        fact_id=item_id,
        updates=payload.model_dump(exclude_unset=True),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="عنصر الذاكرة غير موجود")
    return {"status": "success", "item": updated}


@router.delete("/api/memory/items/{item_id}")
def delete_memory_item(item_id: str, request: Request) -> Dict[str, Any]:
    """حذف حقيقة محددة من الذاكرة طويلة المدى."""
    audit_log_access(f"/api/memory/items/{item_id}", request, {"action": "delete", "id": item_id})
    from memory.manager import MemoryManager
    mgr = MemoryManager.get_instance()
    ok = mgr.delete_long_term_fact(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="عنصر الذاكرة غير موجود")
    return {"status": "success", "deleted_id": item_id}


@router.delete("/api/memory/clear")
def clear_memory_items(request: Request) -> Dict[str, Any]:
    """مسح كافة الحقائق المحفوظة في الذاكرة طويلة المدى."""
    audit_log_access("/api/memory/clear", request, {"action": "clear"})
    from memory.manager import MemoryManager
    mgr = MemoryManager.get_instance()
    count = mgr.clear_long_term_facts()
    return {"status": "success", "cleared_count": count}


@router.get("/api/telemetry/cost")
def get_cost_telemetry_endpoint(request: Request) -> Dict[str, Any]:
    """استرجاع إحصائيات استهلاك وتكاليف نماذج الذكاء الاصطناعي."""
    audit_log_access("/api/telemetry/cost", request, {"action": "read"})
    from agents.cost_auditor import CostAuditor
    return CostAuditor.get_instance().get_cost_summary()
