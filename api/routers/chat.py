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
def post_seraj_chat_endpoint(payload: SerajChatApiRequest, request: Request) -> Dict[str, Any]:
    """Unified conversational interaction with Seraj, coordinating multi-agent actions."""
    audit_log_access("/api/seraj/chat", request, {"chat_id": payload.chat_id, "op_id": payload.operation_id})
    from agent_events_service import get_events_service
    from seraj_llm_service import SerajLLMService
    from seraj_session_manager import SerajSessionManager

    # While a delete/archive/create/update awaits confirmation, the next message may
    # confirm and execute it, so the write token is required (the dashboard prompts on 401).
    if SerajSessionManager.get_instance().get_session(payload.chat_id).pending_action:
        verify_write_auth(request)

    srv = get_events_service()
    op_id = payload.operation_id
    if not op_id:
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

        op_id = srv.start_operation(
            user_query=payload.message,
            operation_type="conversation",
            company_id=c_id,
            company_name=payload.company_name or "شركة النخبة الذكية للتقنية",
            connection_id=payload.connection_id or "default",
            requester=payload.user_name or "المستخدم",
            chat_id=payload.chat_id,
        )

    seraj = SerajLLMService()
    try:
        reply = seraj.chat_turn(
            user_query=payload.message,
            chat_id=payload.chat_id,
            user_name=payload.user_name or "المستخدم",
            connection_id=payload.connection_id,
            company_id=payload.company_id,
            operation_id=op_id,
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
    prov_used = getattr(seraj, "last_provider_used", None) or cfg.get("active_provider", "local")
    model_used = getattr(seraj, "last_model_used", None) or cfg.get("cloud" if prov_used == "cloud" else "local", {}).get("model")
    prov_name = cfg.get("cloud", {}).get("provider", "Cloud") if prov_used == "cloud" else "Ollama"

    llm_meta = {
        "provider": prov_used,
        "model": model_used,
        "provider_name": prov_name,
        "mode": cfg.get("mode", "auto"),
    }

    if op and session.pending_action:
        op["pending_action"] = session.pending_action
        op["plan"] = session.pending_action

    return {
        "status": "success",
        "operation_id": op_id,
        "response": reply,
        "operation": op,
        "pending_action": session.pending_action,
        "pending_clarification": session.pending_clarification,
        "llm_meta": llm_meta,
    }


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
    return []


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

                res_str = json.dumps(tool_res, ensure_ascii=False) if not isinstance(tool_res, str) else tool_res

                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": fn_name,
                    "content": res_str,
                })
        else:
            final_content = final_content or (response.get("content") if "response" in locals() else "") or "تم تنفيذ العمليات الاستعلامية واكتملت الدورات المسموحة."

        if provider.provider == "fallback":
            final_content = f"{final_content}\n\n" \
                     "🌟 **ملاحظة:** النظام يعمل في وضع Fallback الآمن.\n" \
                     "لتجربة أكثر ذكاءً، راجع التعليمات أعلاه!"

        # حفظ رد المساعد النهائي في الذاكرة العاملة المرتبطة بـ thread_id
        if final_content:
            working_mem.add_message("assistant", final_content)

        return {
            "status": "success",
            "thread_id": thread_id,
            "response": {
                "content": final_content,
                "provider": provider.provider
            },
            "current_agent": "seraj",
        }

    except Exception as exc:
        logger.error(f"Chat error: {exc}")
        thread_id = req.thread_id or f"thread_{int(datetime.now().timestamp())}"
        err_msg = (
            f"مرحباً! أنا سراج. استلمت رسالتك: '{req.message[:50]}...'\n\n"
            "حالياً أعمل في وضع محدود. للحصول على ردود أفضل:\n"
            "1. ثبّت Ollama: https://ollama.ai/download\n"
            "2. أو أضف OPENAI_API_KEY في .env"
        )
        try:
            from memory.manager import MemoryManager
            MemoryManager.get_instance().get_working_memory(thread_id).add_message("assistant", err_msg)
        except Exception:
            pass

        return {
            "status": "success",
            "thread_id": thread_id,
            "response": {
                "content": err_msg,
                "provider": "fallback"
            },
            "current_agent": "seraj",
            "error": str(exc)
        }


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

