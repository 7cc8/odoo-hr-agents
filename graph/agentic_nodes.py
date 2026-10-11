"""
Agentic Nodes - عقد LangGraph للوكلاء الذكية
=============================================
تكامل الوكلاء الجدد مع LangGraph
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from agents.base_agent import create_agent_goal
from agents.musleh_agent import MuslehAgent
from agents.hares_agent import HaresAgent
from agents.katib_agent import KatibAgent
from agents.mudaqqiq_agent import MudaqqiqAgent
from agents.muwaffaq_agent import MuwaffaqAgent
from agents.sijil_agent import SijilAgent
from agents.seraj_meta_agent import SerajMetaAgent
from graph.state import SerajState

logger = logging.getLogger("graph.agentic_nodes")


# ═══════════════════════════════════════════════════════════════
# FAHAS: حُذفت fahas_agentic_query - نستخدم fahas_tools المُختبر
# ═══════════════════════════════════════════════════════════════


def musleh_agentic_heal(state: SerajState) -> Dict[str, Any]:
    """
    عقدة مصلح الذكية - معالجة البيانات المُرفوضة
    
    يُستدعى عندما تكون هناك بيانات needs_review أو rejected
    """
    logger.info("🔧 Musleh agentic heal node")
    
    # استخراج البيانات المُرفوضة من الحالة
    rejected_data = state.get("rejected_data", [])
    
    if not rejected_data:
        return {"last_tool_error": "No rejected data to heal"}
    
    # استدعاء مصلح
    musleh = MuslehAgent()
    
    healed_data = []
    for item in rejected_data:
        try:
            diagnosis_request = {
                "row": item,
                "errors": item.get("validation_errors", []),
                "context": {"company_id": state.get("company_id")},
            }
            
            # الدورة الكاملة
            perception = musleh.perceive(diagnosis_request)
            plan = musleh.plan(perception)
            result = musleh.execute(plan, perception)
            reflection = musleh.reflect(perception, plan, result)
            
            # إذا نجح الإصلاح
            if result.get("fixed"):
                healed_data.append(result["fixed_row"])
        
        except Exception as exc:
            logger.error(f"❌ Musleh failed: {exc}")
            continue
    
    return {
        "healed_data": healed_data,
        "messages": [{
            "role": "assistant",
            "content": f"✅ تم إصلاح {len(healed_data)} سجل من أصل {len(rejected_data)}",
        }],
    }


def hares_agentic_guard(state: SerajState) -> Dict[str, Any]:
    """
    عقدة حارس الذكية - فحص الأمان قبل الكتابة
    
    يُستدعى قبل katib_execute للتحقق من الأمان
    """
    logger.info("🛡️ Hares agentic guard node")
    
    # استخراج خطة الكتابة
    write_plan = state.get("write_plan", {})
    
    if not write_plan:
        return {"security_approved": False, "last_tool_error": "No write plan to guard"}
    
    # استدعاء حارس
    hares = HaresAgent()
    
    security_request = {
        "action": write_plan.get("action"),
        "data": write_plan.get("data"),
        "context": {
            "company_id": state.get("company_id"),
            "user": state.get("user"),
        },
    }
    
    # الدورة الكاملة
    perception = hares.perceive(security_request)
    plan = hares.plan(perception)
    result = hares.execute(plan)
    reflection = hares.reflect(perception, plan, result)
    
    # التحقق من القرار
    approved = result["decision"] in ["approve", "approve_with_conditions"]
    
    return {
        "security_approved": approved,
        "security_decision": result["decision"],
        "security_reasoning": reflection.get("reasoning", []),
        "messages": [{
            "role": "assistant",
            "content": f"🛡️ حارس: {result['decision']} - {reflection.get('risk_summary', '')}",
        }],
    }


def katib_agentic_write(state: SerajState) -> Dict[str, Any]:
    """
    عقدة كاتب الذكية - تنفيذ عمليات الكتابة
    
    استبدال katib_execute القديم بنسخة ذكية
    """
    logger.info("✍️ Katib agentic write node")
    
    # استخراج العملية المعتمدة
    approved_action = state.get("approved_action", {})
    
    if not approved_action:
        return {"write_success": False, "last_tool_error": "No approved action"}
    
    # استدعاء كاتب الذكي
    katib = KatibAgent()
    
    # الدورة الكاملة (Perceive→Plan→Execute→Reflect)
    perception = katib.perceive(approved_action)
    plan = katib.plan(perception)
    result = katib.execute(plan)
    reflection = katib.reflect(perception, plan, result)
    
    # التحقق من النجاح
    success = result.get("success", False)
    
    return {
        "write_success": success,
        "write_result": {
            "record_id": result.get("record_id"),
            "confidence": reflection.get("confidence_score", 0.0),
            "executed_steps": result.get("executed_steps", []),
        },
        "messages": [{
            "role": "assistant",
            "content": f"✅ كاتب: {'نجح' if success else 'فشل'} - {reflection.get('decision_rationale_ar', [''])[0] if reflection.get('decision_rationale_ar') else ''}",
        }],
    }


def mudaqqiq_agentic_verify(state: SerajState) -> Dict[str, Any]:
    """
    عقدة مدقق الذكية - التحقق من الامتثال
    
    يُستدعى للتحقق من امتثال البيانات للأنظمة
    """
    logger.info("📋 Mudaqqiq agentic verify node")
    
    # استخراج البيانات للتحقق
    data_to_verify = state.get("data_to_verify", {})
    
    if not data_to_verify:
        return {"compliance_approved": False, "last_tool_error": "No data to verify"}
    
    # استدعاء مدقق
    mudaqqiq = MudaqqiqAgent()
    
    # الدورة الكاملة
    result = mudaqqiq.verify_compliance(data_to_verify)
    
    # التحقق من القرار
    approved = result["decision"] in ["approve", "approve_with_conditions"]
    
    return {
        "compliance_approved": approved,
        "compliance_status": result["status"],
        "compliance_decision": result["decision"],
        "compliance_violations": result.get("violations", []),
        "compliance_confidence": result.get("confidence_score", 0.0),
        "messages": [{
            "role": "assistant",
            "content": f"📋 مدقق: {result['decision']} - {result.get('decision_rationale_ar', [''])[0] if result.get('decision_rationale_ar') else ''}",
        }],
    }


def muwaffaq_agentic_match(state: SerajState) -> Dict[str, Any]:
    """
    عقدة موفّق الذكية - المطابقة الذكية
    
    يُستدعى لمطابقة البيانات (أسماء، أقسام، إلخ)
    """
    logger.info("🔗 Muwaffaq agentic match node")
    
    # استخراج طلب المطابقة
    match_request = state.get("match_request", {})
    
    if not match_request:
        return {"match_found": False, "last_tool_error": "No match request"}
    
    # استدعاء موفّق
    muwaffaq = MuwaffaqAgent()
    
    # الدورة الكاملة
    result = muwaffaq.find_match(match_request)
    
    # التحقق من النجاح
    match_found = result["status"] in ["matched", "proposed"]
    
    return {
        "match_found": match_found,
        "best_match": result.get("best_match"),
        "match_alternatives": result.get("alternatives", []),
        "match_confidence": result.get("confidence", 0.0),
        "messages": [{
            "role": "assistant",
            "content": f"🔗 موفّق: {result['decision']} - ثقة {result['confidence']:.0%}",
        }],
    }



def sijil_agentic_audit(state: SerajState) -> Dict[str, Any]:
    """
    عقدة سجل الذكية - التدقيق والرقابة
    
    يُستدعى بعد العمليات الحرجة لتوثيق وتدقيق السجلات
    """
    logger.info("📁 Sijil agentic audit node")
    
    # استخراج طلب التدقيق
    audit_scope = state.get("audit_scope", "comprehensive")
    
    # استدعاء سجل
    sijil = SijilAgent()
    
    audit_request = {
        "scope": audit_scope,
        "focus_areas": state.get("audit_focus_areas", []),
        "time_range": state.get("audit_time_range"),
    }
    
    # الدورة الكاملة
    result = sijil.audit(audit_request)
    
    # التحقق من النتائج
    has_critical = any(
        f for f in result.get("critical_findings", [])
    )
    
    return {
        "audit_logged": True,
        "audit_summary": result.get("summary", {}),
        "audit_anomalies": result.get("anomalies", []),
        "audit_decision": result.get("decision"),
        "audit_compliance_score": result.get("summary", {}).get("compliance_score", 0.0),
        "should_escalate_audit": result.get("should_escalate", False),
        "messages": [{
            "role": "assistant",
            "content": f"📁 سجل: {result.get('decision')} - امتثال {result.get('summary', {}).get('compliance_score', 0):.0%}",
        }],
    }


def seraj_meta_orchestration(state: SerajState) -> Dict[str, Any]:
    """
    عقدة سراج Meta-Agent - التنسيق الذكي
    
    هذه العقدة تستخدم SerajMetaAgent لاتخاذ قرارات ذكية:
    - اختيار الوكلاء المناسبين بناءً على النية
    - التعلم من التفاعلات السابقة
    - تفسير القرارات المتخذة
    - إدارة الذاكرة طويلة المدى
    
    الفرق عن seraj_think القديم:
    - seraj_think: يستخدم LLM مباشرة لتوليد الردود
    - seraj_meta_orchestration: يستخدم Meta-Agent للتفكير الاستراتيجي
    """
    logger.info("🧠 Seraj Meta-Agent orchestration")
    
    # استخراج البيانات من الحالة
    user_query = state.get("user_query", "")
    intent = state.get("intent", "read")
    company_id = state.get("company_id")
    user_name = state.get("user_name", "مستخدم")
    
    # إنشاء SerajMetaAgent
    meta_agent = SerajMetaAgent()
    
    # إعداد الطلب
    request = {
        "query": user_query,
        "intent": intent,
        "context": {
            "company_id": company_id,
            "user_name": user_name,
            "conversation_history": state.get("messages", []),
            "current_state": {
                "compliance_approved": state.get("compliance_approved"),
                "security_approved": state.get("security_approved"),
                "write_success": state.get("write_success"),
                "match_found": state.get("match_found"),
                "audit_logged": state.get("audit_logged"),
            },
        },
    }
    
    # استدعاء Meta-Agent
    try:
        result = meta_agent.orchestrate(request)
        
        # استخراج القرارات
        # ملاحظة: orchestrate يرجع agents_used بدلاً من selected_agents
        selected_agents_raw = result.get("agents_used", [])
        
        # تحويل من AgentType enum إلى strings
        selected_agents = []
        for agent in selected_agents_raw:
            # إذا كان AgentType enum
            if hasattr(agent, "value"):
                selected_agents.append(agent.value)
            else:
                selected_agents.append(str(agent))
        
        execution_plan = {
            "sequence": "sequential" if not result.get("parallel_possible", False) else "parallel",
            "order": selected_agents,
        }
        recommendations = []  # يمكن إضافتها لاحقاً
        explanation = {
            "reasoning": result.get("reasoning", ""),
            "query_type": result.get("intent", ""),
        }
        
        # بناء رسالة توضيحية
        agents_ar = {
            "fahas": "فاحص",
            "musleh": "مصلح",
            "hares": "حارس",
            "katib": "كاتب",
            "mudaqqiq": "مدقق",
            "muwaffaq": "موفّق",
            "sijil": "سجل",
        }
        
        selected_names = [agents_ar.get(a, a) for a in selected_agents]
        orchestration_msg = f"🧠 سراج: اخترت الوكلاء التالية: {', '.join(selected_names)}\n"
        orchestration_msg += f"📋 خطة التنفيذ: {execution_plan.get('sequence', 'تسلسلي')}\n"
        
        if explanation.get("reasoning"):
            orchestration_msg += f"💡 السبب: {explanation['reasoning']}\n"
        
        # إغلاق بعلم ENABLE_META_TRACES (افتراضه 0)
        import os
        enable_traces = os.environ.get("ENABLE_META_TRACES", "0") == "1"
        
        updates = {
            "meta_selected_agents": selected_agents,
            "meta_execution_plan": execution_plan,
            "meta_recommendations": recommendations,
            "meta_explanation": explanation,
            "meta_confidence": result.get("confidence", 0.0),
        }
        
        if enable_traces:
            # حد agent_traces بآخر 20 عنصراً
            current_traces = state.get("agent_traces", [])
            new_trace = {
                "agent": "seraj_meta_orchestration",
                "timestamp": __import__("datetime").datetime.now().isoformat(),
                "content": orchestration_msg,
            }
            updated_traces = (current_traces + [new_trace])[-20:]
            updates["agent_traces"] = updated_traces
        
        return updates
    
    except Exception as exc:
        logger.error(f"❌ Meta-Agent orchestration failed: {exc}")
        return {
            "error": f"فشل التنسيق الذكي: {exc}",
            "meta_selected_agents": [],
        }


def seraj_meta_reflect(state: SerajState) -> Dict[str, Any]:
    """
    عقدة المراجعة الذكية - تحليل نتائج الوكلاء
    
    تُستدعى بعد تنفيذ الوكلاء لتحليل النتائج والتعلم
    """
    logger.info("🔍 Seraj Meta-Agent reflection")
    
    meta_agent = SerajMetaAgent()
    
    # جمع نتائج الوكلاء
    agent_results = {
        "fahas": {
            "last_error": state.get("last_tool_error"),
        },
        "musleh": {
            "healed_data": state.get("healed_data", []),
        },
        "hares": {
            "security_approved": state.get("security_approved"),
            "security_decision": state.get("security_decision"),
        },
        "katib": {
            "write_success": state.get("write_success"),
            "write_result": state.get("write_result"),
        },
        "mudaqqiq": {
            "compliance_approved": state.get("compliance_approved"),
            "compliance_decision": state.get("compliance_decision"),
        },
        "muwaffaq": {
            "match_found": state.get("match_found"),
            "match_confidence": state.get("match_confidence"),
        },
        "sijil": {
            "audit_logged": state.get("audit_logged"),
            "audit_decision": state.get("audit_decision"),
        },
    }
    
    # تحليل النتائج
    try:
        reflection = meta_agent._reflect_on_execution(
            state.get("user_query", ""),
            state.get("meta_selected_agents", []),
            agent_results,
        )
        
        # التعلم من النتائج
        success_rate = reflection.get("success_rate", 0.0)
        learning_insights = reflection.get("learning_insights", [])
        
        # حفظ الأنماط المتعلمة
        if success_rate > 0.7:  # نجاح > 70%
            pattern = {
                "intent": state.get("intent"),
                "query_type": state.get("meta_explanation", {}).get("query_type"),
                "selected_agents": state.get("meta_selected_agents", []),
                "success": True,
                "success_rate": success_rate,
            }
            meta_agent._save_learned_pattern(pattern)
        
        reflection_msg = f"🔍 المراجعة: نسبة النجاح {success_rate:.0%}\n"
        if learning_insights:
            reflection_msg += f"💡 الدروس المستفادة:\n"
            for insight in learning_insights[:3]:  # أول 3 فقط
                reflection_msg += f"  - {insight}\n"
        
        # إغلاق بعلم ENABLE_META_TRACES (افتراضه 0)
        import os
        enable_traces = os.environ.get("ENABLE_META_TRACES", "0") == "1"
        
        updates = {
            "meta_reflection": reflection,
            "meta_success_rate": success_rate,
            "meta_learning_insights": learning_insights,
        }
        
        if enable_traces:
            # حد agent_traces بآخر 20 عنصراً
            current_traces = state.get("agent_traces", [])
            new_trace = {
                "agent": "seraj_meta_reflect",
                "timestamp": __import__("datetime").datetime.now().isoformat(),
                "content": reflection_msg,
            }
            updated_traces = (current_traces + [new_trace])[-20:]
            updates["agent_traces"] = updated_traces
        
        return updates
    
    except Exception as exc:
        logger.error(f"❌ Meta-Agent reflection failed: {exc}")
        return {
            "meta_reflection": {"error": str(exc)},
        }
