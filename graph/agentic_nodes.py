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
from agent_events_service import get_events_service  # P3: observability
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
    
    # Phase 3, Task 3.4.3: emit start event
    from agents.agent_events_service import emit_agent_event
    
    operation_id = state.get("operation_id") or state.get("excel_run_id")
    if operation_id:
        emit_agent_event(
            operation_id=operation_id,
            agent="Musleh (مصلح)",
            action="heal_start",
            reasoning="تحليل البيانات المرفوضة ومحاولة إصلاحها",
            status="in_progress"
        )
    
    # استخراج البيانات المُرفوضة من الحالة
    rejected_data = state.get("rejected_data", [])
    
    if not rejected_data:
        if operation_id:
            emit_agent_event(
                operation_id=operation_id,
                agent="Musleh (مصلح)",
                action="heal_complete",
                reasoning="لا توجد بيانات مرفوضة للمعالجة",
                status="failed"
            )
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
    
    # P3: emit completion event
    if operation_id:
        status = "completed" if healed_data else "failed"
        events_service.emit_event(
            operation_id=operation_id,
            agent="musleh",
            event_type="healing_completed",
            status=status,
            description_ar=f"مصلح: تم إصلاح {len(healed_data)} سجل من أصل {len(rejected_data)}",
            result_ref={"healed_count": len(healed_data), "total_count": len(rejected_data)}
        )
    
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
    
    # P3: emit start event
    events_service = get_events_service()
    operation_id = state.get("operation_id")
    if operation_id:
        events_service.emit_event(
            operation_id=operation_id,
            agent="hares",
            event_type="security_check_started",
            status="verifying_permissions",
            description_ar="حارس يفحص صلاحيات وأمان العملية المطلوبة",
            from_agent=None,
            to_agent="hares",
            company_id=state.get("company_id"),
            company_name=state.get("company_name"),
        )
    
    # استخراج خطة الكتابة
    write_plan = state.get("write_plan", {})
    
    if not write_plan:
        if operation_id:
            events_service.emit_event(
                operation_id=operation_id,
                agent="hares",
                event_type="security_check_failed",
                status="failed",
                description_ar="حارس: لا توجد خطة كتابة للمراجعة",
                error="No write plan to guard"
            )
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
    
    # P5-S8: التحقق الصحيح من القرار - DENY يجب أن يوقف التنفيذ
    decision = result.get("decision", "DENY")
    
    # approved = True فقط إذا كان القرار ALLOW أو ALLOW_WITH_CONDITIONS
    if decision in ["ALLOW", "ALLOW_WITH_CONDITIONS", "approve", "approve_with_conditions"]:
        approved = True
    elif decision in ["DENY", "REJECT"]:
        approved = False
    elif decision in ["REQUIRE_APPROVAL", "ESCALATE"]:
        # يتطلب موافقة بشرية - لا نوافق تلقائياً
        approved = False
    else:
        # قرار غير معروف - رفض افتراضي (secure by default)
        approved = False
        logger.warning(f"⚠️ Unknown hares decision: {decision}, defaulting to reject")
    
    # P3: emit completion event
    if operation_id:
        status = "completed" if approved else "waiting_approval"
        events_service.emit_event(
            operation_id=operation_id,
            agent="hares",
            event_type="security_check_completed",
            status=status,
            description_ar=f"حارس: {result['decision']} - {reflection.get('risk_summary', '')}",
            result_ref={
                "decision": result["decision"],
                "approved": approved,
                "risk_level": reflection.get("risk_level", "unknown")
            }
        )
    
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
    
    P5-S7: الآن يفحص ApprovalPlan قبل التنفيذ (TTL + consumed + user binding)
    """
    logger.info("✍️ Katib agentic write node")
    
    # P3: emit start event
    events_service = get_events_service()
    operation_id = state.get("operation_id")
    if operation_id:
        events_service.emit_event(
            operation_id=operation_id,
            agent="katib",
            event_type="write_started",
            status="executing_write",
            description_ar="كاتب ينفذ العملية المعتمدة في قاعدة البيانات",
            from_agent="hares",
            to_agent="katib",
            company_id=state.get("company_id"),
            company_name=state.get("company_name"),
        )
    
    # استخراج العملية المعتمدة
    approved_action = state.get("approved_action", {})
    
    if not approved_action:
        if operation_id:
            events_service.emit_event(
                operation_id=operation_id,
                agent="katib",
                event_type="write_failed",
                status="failed",
                description_ar="كاتب: لا توجد عملية معتمدة للتنفيذ",
                error="No approved action"
            )
        return {"write_success": False, "last_tool_error": "No approved action"}
    
    # P5-S7: فحص ApprovalPlan قبل التنفيذ
    plan_id = approved_action.get("plan_id")
    if not plan_id:
        if operation_id:
            events_service.emit_event(
                operation_id=operation_id,
                agent="katib",
                event_type="write_failed",
                status="failed",
                description_ar="كاتب: لا يوجد plan_id في العملية - رفض الأمان",
                error="No plan_id in approved_action"
            )
        return {"write_success": False, "last_tool_error": "P5-S7: No plan_id in approved_action"}
    
    # P5-S7: تحميل والتحقق من ApprovalPlan (يحدث أيضاً في katib_service لكننا نفحص مرة أخرى للأمان)
    try:
        from approval_plan_schema import ApprovalPlan, ApprovalPlanError, validate_plan_for_execution
        
        plan = ApprovalPlan.load(plan_id)
        validate_plan_for_execution(plan)  # TTL + consumed + approved checks
        
        logger.info(f"✅ ApprovalPlan {plan_id} validated successfully")
    
    except ApprovalPlanError as err:
        if operation_id:
            events_service.emit_event(
                operation_id=operation_id,
                agent="katib",
                event_type="write_failed",
                status="failed",
                description_ar=f"كاتب: خطة الاعتماد غير صالحة - {err}",
                error=str(err)
            )
        return {"write_success": False, "last_tool_error": f"P5-S7: Invalid ApprovalPlan - {err}"}
    
    # استدعاء كاتب الذكي
    katib = KatibAgent()
    
    # الدورة الكاملة (Perceive→Plan→Execute→Reflect)
    perception = katib.perceive(approved_action)
    plan = katib.plan(perception)
    result = katib.execute(plan)
    reflection = katib.reflect(perception, plan, result)
    
    # التحقق من النجاح
    success = result.get("success", False)
    
    # P3: emit completion event
    if operation_id:
        status = "completed" if success else "failed"
        events_service.emit_event(
            operation_id=operation_id,
            agent="katib",
            event_type="write_completed",
            status=status,
            description_ar=f"كاتب: {'نجح التنفيذ' if success else 'فشل التنفيذ'} - {reflection.get('decision_rationale_ar', [''])[0] if reflection.get('decision_rationale_ar') else ''}",
            result_ref={
                "success": success,
                "record_id": result.get("record_id"),
                "confidence": reflection.get("confidence_score", 0.0)
            }
        )
    
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


# ========================================================================
# Helper Functions for Rejection Details Formatting (Phase 3, Task 3.2.1 & 3.2.2)
# ========================================================================

def _translate_to_arabic(message: str) -> str:
    """
    Translate error message to Arabic.
    
    Args:
        message: English error message
        
    Returns:
        str: Arabic translation of the error message
    """
    translations = {
        "Department not found": "القسم غير موجود",
        "Job not found": "المسمى الوظيفي غير موجود",
        "Invalid email": "البريد الإلكتروني غير صالح",
        "Invalid email format": "تنسيق البريد الإلكتروني غير صحيح",
        "Invalid date format": "تنسيق التاريخ غير صحيح",
        "Missing required field": "حقل مطلوب مفقود",
        "Invalid phone number": "رقم الهاتف غير صالح",
        "Employee already exists": "الموظف موجود مسبقاً",
        "Contract not found": "العقد غير موجود",
        "Duplicate entry": "إدخال مكرر",
        "Invalid value": "قيمة غير صالحة",
        "Field too long": "الحقل طويل جداً",
        "Field required": "الحقل مطلوب",
        # Add more translations as needed
    }
    return translations.get(message, message)


def _generate_suggestion(error: Dict[str, Any], row_data: Dict[str, Any]) -> str:
    """
    Generate fix suggestion based on error type.
    
    Args:
        error: Error dictionary with field and message
        row_data: Row data from parsed Excel
        
    Returns:
        str: Suggested fix for the error
    """
    field = error.get("field", "")
    message = error.get("message", "")
    
    if field == "department":
        return "استخدم أحد الأقسام الموجودة مثل 'المبيعات' أو 'الموارد البشرية'"
    elif field == "job_id":
        return "تحقق من صحة المسمى الوظيفي أو استخدم رمز الوظيفة الصحيح"
    elif "email" in field.lower():
        return "تأكد من صحة تنسيق البريد الإلكتروني (example@domain.com)"
    elif "date" in field.lower():
        return "استخدم تنسيق التاريخ الصحيح (YYYY-MM-DD)"
    elif "phone" in field.lower():
        return "تحقق من رقم الهاتف (يجب أن يحتوي على أرقام فقط)"
    else:
        return "يرجى مراجعة وتصحيح القيمة"


def _is_auto_fixable(error: Dict[str, Any]) -> bool:
    """
    Determine if error can be auto-fixed by Musleh agent.
    
    Args:
        error: Error dictionary with field and message
        
    Returns:
        bool: True if error is potentially auto-fixable
    """
    field = error.get("field", "")
    message = error.get("message", "").lower()
    
    # Fields that Musleh can potentially auto-fix
    fixable_fields = ["department", "job_id", "date_format"]
    fixable_messages = ["not found", "format", "missing"]
    
    if field in fixable_fields:
        return True
    
    for fixable_msg in fixable_messages:
        if fixable_msg in message:
            return True
    
    return False


def _format_rejection_details(
    rejected_rows: List[Dict[str, Any]],
    state: SerajState
) -> List[Dict[str, Any]]:
    """
    Format rejection details for dashboard display.
    
    This function transforms raw rejection data from dry_run_report into
    a rich, user-friendly format with Arabic translations, suggestions,
    and auto-fix indicators.
    
    Input format (from dry_run_report.py):
    [{"row_number": 3, "errors": [{"field": "department", "message": "Department not found"}]}]
    
    Output format (enhanced):
    [{
        "row_number": 3,
        "name": "محمد أحمد",
        "reason_ar": "القسم غير موجود",
        "field": "department",
        "value": "قسم المبيعات",
        "suggestion": "استخدم أحد الأقسام الموجودة...",
        "can_auto_fix": True
    }]
    
    Args:
        rejected_rows: Raw rejection data from dry-run
        state: Current SerajState with parsed Excel data
        
    Returns:
        List[Dict[str, Any]]: Formatted rejection details
    """
    formatted = []
    parsed_data = state.get("excel_parsed_data", {})
    rows = parsed_data.get("rows", [])
    
    for row in rejected_rows:
        row_idx = row.get("row_number", 0)
        
        # Get row data (handle index out of bounds)
        if row_idx < len(rows):
            row_data = rows[row_idx]
        else:
            row_data = {}
        
        # Process each error for this row
        errors = row.get("errors", [])
        for error in errors:
            field = error.get("field", "unknown")
            message = error.get("message", "")
            
            formatted.append({
                "row_number": row_idx + 1,  # Display as 1-indexed
                "name": row_data.get("name", "N/A"),
                "reason_ar": _translate_to_arabic(message),
                "field": field,
                "value": str(row_data.get(field, "")),
                "suggestion": _generate_suggestion(error, row_data),
                "can_auto_fix": _is_auto_fixable(error)
            })
    
    return formatted


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
    
    # Phase 3, Task 3.4.2: Emit agent event
    from agents.agent_events_service import emit_agent_event
    
    operation_id = state.get("operation_id") or state.get("excel_run_id")
    
    if operation_id:
        emit_agent_event(
            operation_id=operation_id,
            agent="Seraj Meta-Agent",
            action="orchestrate_start",
            reasoning="تحليل الاستعلام واختيار الوكلاء المناسبين",
            status="in_progress"
        )
    
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
        
        # Phase 3, Task 3.4.2: Emit success event
        if operation_id:
            emit_agent_event(
                operation_id=operation_id,
                agent="Seraj Meta-Agent",
                action="orchestrate_complete",
                decision=f"الوكلاء المختارة: {', '.join(selected_names)}",
                reasoning=explanation.get("reasoning", ""),
                status="success"
            )
        
        return updates
    
    except Exception as exc:
        logger.error(f"❌ Meta-Agent orchestration failed: {exc}")
        
        # Phase 3, Task 3.4.2: Emit failure event
        if operation_id:
            emit_agent_event(
                operation_id=operation_id,
                agent="Seraj Meta-Agent",
                action="orchestrate_complete",
                reasoning=f"فشل: {exc}",
                status="failed"
            )
        
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
        
        # حفظ الأنماط المتعلمة (إغلاق بعلم ENABLE_META_LEARNING افتراضه 0)
        import os
        enable_learning = os.environ.get("ENABLE_META_LEARNING", "0") == "1"
        
        if enable_learning and success_rate > 0.7:  # نجاح > 70%
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



# ========================================================================
# Rejection Details Formatting (Phase 3, Tasks 3.2.1 & 3.2.2)
# ========================================================================

def _translate_to_arabic(message: str) -> str:
    """
    Translate error message to Arabic for Dashboard display.

    Args:
        message: English error message from validation

    Returns:
        str: Arabic translation or original if not found
    """
    translations = {
        "Department not found": "القسم غير موجود",
        "Department not found in Odoo": "القسم غير موجود في النظام",
        "Job not found": "المسمى الوظيفي غير موجود",
        "Job position not found": "الوظيفة غير موجودة",
        "Invalid email": "البريد الإلكتروني غير صالح",
        "Invalid email format": "صيغة البريد الإلكتروني غير صحيحة",
        "Invalid date format": "تنسيق التاريخ غير صحيح",
        "Invalid date": "تاريخ غير صالح",
        "Missing required field": "حقل إلزامي مفقود",
        "Required field missing": "حقل مطلوب مفقود",
        "Field is required": "الحقل مطلوب",
        "Duplicate employee": "موظف مكرر",
        "Employee already exists": "الموظف موجود مسبقاً",
        "Invalid work type": "نوع العمل غير صالح",
        "Invalid contract type": "نوع العقد غير صالح",
        "Company not found": "الشركة غير موجودة",
        "Invalid phone number": "رقم الهاتف غير صالح",
        "Invalid national ID": "رقم الهوية غير صالح",
        "Gender not valid": "الجنس غير صالح",
        "Marital status not valid": "الحالة الاجتماعية غير صالحة",
        "Invalid salary": "الراتب غير صالح",
        "Salary must be positive": "يجب أن يكون الراتب موجباً",
        "Name is too short": "الاسم قصير جداً",
        "Name is required": "الاسم مطلوب",
        "Value is too long": "القيمة طويلة جداً",
        "Country not found": "الدولة غير موجودة",
        "Nationality not found": "الجنسية غير موجودة",
        "Resource calendar not found": "جدول الدوام غير موجود",
        "Manager not found": "المدير غير موجود",
        "Coach not found": "المرشد غير موجود",
        "Invalid work location": "موقع العمل غير صالح",
        "Work location not found": "موقع العمل غير موجود",
    }

    # Direct match
    if message in translations:
        return translations[message]

    # Partial match
    for eng, ar in translations.items():
        if eng.lower() in message.lower():
            return ar

    return message


def _generate_suggestion(error: Dict[str, Any], row_data: Dict[str, Any]) -> str:
    """
    Generate a fix suggestion based on error type and field.

    Args:
        error: Error dict with 'field' and 'message' keys
        row_data: Raw row data from Excel

    Returns:
        str: Suggested fix for the error
    """
    field = error.get("field", "")
    message = error.get("message", "")

    suggestions = {
        "department": "تحقق من اسم القسم في Odoo وتأكد من الكتابة الصحيحة",
        "department_id": "تحقق من اسم القسم في Odoo وتأكد من الكتابة الصحيحة",
        "job_id": "تحقق من المسمى الوظيفي في Odoo",
        "job_title": "استخدم المسمى الوظيفي الموجود في النظام",
        "work_email": "تأكد من صحة صيغة البريد الإلكتروني (مثال: name@company.com)",
        "private_email": "تأكد من صحة صيغة البريد الإلكتروني",
        "company_id": "تحقق من اسم الشركة في النظام",
        "parent_id": "تحقق من اسم المدير في قائمة الموظفين",
        "coach_id": "تحقق من اسم المرشد في قائمة الموظفين",
        "resource_calendar_id": "استخدم جدول الدوام المعرّف في النظام",
        "contract_type": "استخدم أحد أنواع العقود المتاحة: (دوام كامل، دوام جزئي، مؤقت)",
        "work_location_id": "تحقق من موقع العمل في الإعدادات",
        "country_id": "استخدم اسم الدولة الرسمي المعتمد",
        "country_of_birth": "استخدم اسم الدولة الرسمي المعتمد",
        "gender": "استخدم: ذكر أو أنثى (Male/Female)",
        "marital": "استخدم: أعزب، متزوج، مطلق، أرمل",
        "identification_id": "تحقق من صحة رقم الهوية الوطنية",
        "mobile_phone": "أدخل رقم الهاتف بالصيغة الدولية (+966XXXXXXXXX)",
        "birthday": "استخدم صيغة التاريخ: YYYY-MM-DD",
        "certificate": "استخدم مستوى التعليم المحدد في النظام",
    }

    if field in suggestions:
        return suggestions[field]

    if "not found" in message.lower():
        return f"تحقق من وجود القيمة '{row_data.get(field, '')}' في النظام"
    elif "required" in message.lower():
        return f"أضف قيمة لحقل '{field}'"
    elif "invalid" in message.lower() or "format" in message.lower():
        return f"راجع صيغة القيمة المُدخلة للحقل '{field}'"

    return "راجع هذا الحقل وتأكد من صحة البيانات"


def _is_auto_fixable(error: Dict[str, Any]) -> bool:
    """
    Determine if an error can be auto-fixed by Musleh agent.

    Fields that Musleh can typically fix via fuzzy matching or normalization.

    Args:
        error: Error dict with 'field' and 'message' keys

    Returns:
        bool: True if Musleh can auto-fix this error
    """
    fixable_fields = {
        "department", "department_id",
        "job_id", "job_title",
        "parent_id",
        "coach_id",
        "resource_calendar_id",
        "work_location_id",
        "gender",
        "marital",
        "contract_type",
        "country_id",
        "country_of_birth",
    }

    fixable_message_patterns = [
        "not found",
        "invalid",
        "not valid",
    ]

    field = error.get("field", "")
    message = error.get("message", "").lower()

    if field in fixable_fields:
        for pattern in fixable_message_patterns:
            if pattern in message:
                return True

    return False


def _format_rejection_details(
    rejected_rows: list,
    state: SerajState
) -> list:
    """
    Format rejection details for Dashboard display (Phase 3, Task 3.2.1).

    Converts raw validation errors into a rich, Arabic-friendly format
    suitable for the Dashboard rejection details table.

    Input format (from dry_run_report.py):
        [{"row_number": 3, "errors": [{"field": "department", "message": "Department not found"}]}]

    Output format (enhanced for Dashboard):
        [{
            "row_number": 3,
            "name": "محمد أحمد",
            "reason_ar": "القسم غير موجود",
            "field": "department",
            "value": "قسم المبيعات",
            "suggestion": "تحقق من اسم القسم في Odoo",
            "can_auto_fix": True
        }]

    Args:
        rejected_rows: List of rejected row dicts from validation
        state: Current SerajState for accessing parsed row data

    Returns:
        List of formatted rejection detail dicts
    """
    formatted = []

    # Get parsed data rows for value lookup
    parsed_data = state.get("excel_parsed_data", {})
    if isinstance(parsed_data, dict):
        rows_list = parsed_data.get("rows", [])
    else:
        rows_list = []

    for row in rejected_rows:
        row_idx = row.get("row_number", 0)
        row_errors = row.get("errors", [])

        # Look up original row data for context
        row_data = {}
        if rows_list:
            # row_number is 1-based, rows_list is 0-based
            list_idx = row_idx - 2  # account for header row
            if 0 <= list_idx < len(rows_list):
                row_data = rows_list[list_idx]

        employee_name = (
            row_data.get("name")
            or row_data.get("employee_name")
            or row_data.get("الاسم")
            or "N/A"
        )

        for error in row_errors:
            field = error.get("field", "")
            value = (
                row_data.get(field, "")
                or error.get("value", "")
                or ""
            )

            formatted.append({
                "row_number": row_idx,
                "name": employee_name,
                "reason_ar": _translate_to_arabic(error.get("message", "")),
                "field": field,
                "value": str(value)[:100],  # truncate long values
                "suggestion": _generate_suggestion(error, row_data),
                "can_auto_fix": _is_auto_fixable(error)
            })

    return formatted


# ========================================================================
# Conditional Execution Node (Phase 3, Task 3.3.1)
# ========================================================================

def conditional_execution_node(state: SerajState) -> Dict[str, Any]:
    """
    Conditional execution decision node for dry-run workflow.
    
    This node implements the branching logic for conditional execution:
    - If rejected_rows == 0: set auto_execute=True → route to immediate execution
    - If rejected_rows > 0: wait for user_execution_choice → route based on decision
    
    Logic Flow:
    1. Check rejected_rows_details count
    2. If count == 0 and accepted > 0: Enable auto-execute (clean dry-run)
    3. If count > 0: Disable auto-execute, wait for user approval
    
    Args:
        state: Current SerajState with validation results
        
    Returns:
        Dict with auto_execute flag and user message
    """
    logger.info("🔀 Conditional execution decision node")
    
    from graph.state import get_rejection_count
    
    rejected_count = get_rejection_count(state)
    accepted_count = state.get("excel_validation_stats", {}).get("accepted", 0)
    
    if rejected_count == 0 and accepted_count > 0:
        # Auto-execute: no errors, proceed immediately
        logger.info(f"✅ Clean dry-run: {accepted_count} rows accepted, 0 rejected - enabling auto-execute")
        return {
            "auto_execute": True,
            "user_execution_choice": "execute",  # implicit approval
            "answer": f"✅ جميع الصفوف ({accepted_count}) مقبولة - جاري التنفيذ الآن..."
        }
    elif rejected_count > 0:
        # Wait for user decision
        logger.info(f"⚠️ Dry-run with rejections: {rejected_count} rejected, {accepted_count} accepted - awaiting user decision")
        return {
            "auto_execute": False,
            "answer": f"⚠️ تم رفض {rejected_count} صفوف، وقبول {accepted_count} صفوف. يرجى اختيار إجراء."
        }
    else:
        # Edge case: no rows at all
        logger.warning("⚠️ No rows processed in dry-run")
        return {
            "auto_execute": False,
            "error": "لا توجد صفوف للمعالجة"
        }
