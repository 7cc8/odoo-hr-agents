"""Shared state for the Seraj graph."""
from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple, TypedDict

Intent = Literal["read", "write", "clarify"]


def append_messages(left: Optional[List[Dict[str, Any]]], right: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Reducer: nodes return ONLY new messages; they are appended to the thread history."""
    return list(left or []) + list(right or [])


class SerajState(TypedDict, total=False):
    # input (overwritten on every run)
    chat_id: str
    user_query: str
    user_name: str
    connection_id: Optional[str]
    
    # P3: observability and events
    operation_id: Optional[str]

    # sticky company context (persists per thread_id)
    company_id: Optional[int]
    company_name: Optional[str]
    companies: Dict[str, str]  # id -> name, learned from company-listing tools

    # routing
    intent: Intent

    # conversation memory (persists per thread_id)
    messages: Annotated[List[Dict[str, Any]], append_messages]

    # per-run scratch (reset by ingest_user_message)
    last_assistant: Dict[str, Any]
    turns: int
    last_tool_error: Optional[str]

    # write path (deterministic, human-gated)
    plan: Optional[Dict[str, Any]]
    policy_ok: Optional[bool]
    approved: Optional[bool]
    exec_result: Optional[Dict[str, Any]]
    verified: Optional[bool]

    # ========================================================================
    # New Agentic Agents State Fields
    # ========================================================================
    
    # Musleh (مصلح) - Diagnostic & Healing
    rejected_data: Optional[List[Dict[str, Any]]]  # بيانات مُرفوضة تحتاج معالجة
    healed_data: Optional[List[Dict[str, Any]]]  # بيانات تم إصلاحها
    
    # Hares (حارس) - Security Guard
    security_approved: Optional[bool]  # هل وافق الحارس؟
    security_decision: Optional[str]  # قرار الحارس
    security_reasoning: Optional[List[str]]  # تفسير القرار
    
    # Katib (كاتب) - Write Agent
    approved_action: Optional[Dict[str, Any]]  # عملية معتمدة للكتابة
    write_plan: Optional[Dict[str, Any]]  # خطة الكتابة
    write_success: Optional[bool]  # هل نجحت الكتابة؟
    write_result: Optional[Dict[str, Any]]  # نتيجة الكتابة
    
    # Mudaqqiq (مدقق) - Compliance Verification
    data_to_verify: Optional[Dict[str, Any]]  # بيانات للتحقق من امتثالها
    compliance_approved: Optional[bool]  # هل البيانات ممتثلة؟
    compliance_status: Optional[str]  # حالة الامتثال
    compliance_decision: Optional[str]  # قرار المدقق
    compliance_violations: Optional[List[Dict[str, Any]]]  # المخالفات
    compliance_confidence: Optional[float]  # ثقة المدقق
    
    # Muwaffaq (موفّق) - Matching Agent
    match_request: Optional[Dict[str, Any]]  # طلب مطابقة
    match_found: Optional[bool]  # هل وُجدت مطابقة؟
    best_match: Optional[Dict[str, Any]]  # أفضل مطابقة
    match_alternatives: Optional[List[Dict[str, Any]]]  # بدائل
    match_confidence: Optional[float]  # ثقة المطابقة
    
    # Sijil (سجل) - Audit Trail
    audit_scope: Optional[str]  # نطاق التدقيق
    audit_focus_areas: Optional[List[str]]  # مجالات التركيز
    audit_time_range: Optional[Tuple[str, str]]  # نطاق الوقت
    audit_logged: Optional[bool]  # هل تم التوثيق؟
    audit_record_id: Optional[str]  # معرف سجل التدقيق
    audit_summary: Optional[Dict[str, Any]]  # ملخص التدقيق
    audit_anomalies: Optional[List[Dict[str, Any]]]  # الشذوذات المكتشفة
    audit_decision: Optional[str]  # قرار سجل
    audit_compliance_score: Optional[float]  # نسبة الامتثال
    should_escalate_audit: Optional[bool]  # هل يجب التصعيد؟
    
    # Agent Traces (for observability)
    agent_traces: Optional[List[Dict[str, Any]]]  # تتبع الوكلاء
    agent_reflections: Optional[List[Dict[str, Any]]]  # مراجعات الوكلاء
    
    # Shared Memory (for multi-agent coordination)
    shared_memory: Optional[Dict[str, Any]]  # ذاكرة مشتركة بين الوكلاء

    # ========================================================================
    # Meta-Agent State Fields (SerajMetaAgent)
    # ========================================================================
    
    # Meta-Agent Decision Making
    meta_selected_agents: Optional[List[str]]  # الوكلاء المختارة بواسطة Meta-Agent
    meta_execution_plan: Optional[Dict[str, Any]]  # خطة التنفيذ
    meta_recommendations: Optional[List[str]]  # توصيات Meta-Agent
    meta_explanation: Optional[Dict[str, Any]]  # تفسير القرارات
    meta_confidence: Optional[float]  # ثقة Meta-Agent في القرارات
    
    # Meta-Agent Reflection & Learning
    meta_reflection: Optional[Dict[str, Any]]  # مراجعة النتائج
    meta_success_rate: Optional[float]  # نسبة النجاح
    meta_learning_insights: Optional[List[str]]  # الدروس المستفادة
    
    # Meta-Agent Memory
    meta_interaction_id: Optional[str]  # معرف التفاعل الحالي
    meta_similar_patterns: Optional[List[Dict[str, Any]]]  # أنماط مشابهة من الماضي

    # output
    answer: Optional[str]
    error: Optional[str]

    # ========================================================================
    # P4: Excel Workflow State Fields
    # ========================================================================
    
    # Excel file processing
    excel_file_path: Optional[str]  # مسار ملف Excel
    excel_parsed_data: Optional[Dict[str, Any]]  # البيانات المحللة من Excel
    excel_run_id: Optional[str]  # معرف عملية الاستيراد
    excel_row_count: Optional[int]  # عدد الصفوف
    excel_error: Optional[str]  # رمز الخطأ
    excel_error_message: Optional[str]  # رسالة الخطأ
    
    # Validation
    excel_validation_results: Optional[List[Any]]  # نتائج التحقق
    excel_validation_stats: Optional[Dict[str, int]]  # إحصائيات التحقق
    
    # Healing
    excel_healed_results: Optional[List[Dict[str, Any]]]  # نتائج الإصلاح
    
    # Dry-run report
    excel_dry_run_report: Optional[Dict[str, Any]]  # تقرير dry-run
    excel_requires_four_eyes: Optional[bool]  # هل يتطلب موافقة مزدوجة
    
    # Approval
    excel_approval: Optional[Dict[str, Any]]  # بيانات الاعتماد
    excel_approval_path: Optional[str]  # مسار ملف الاعتماد
    needs_human_approval: Optional[bool]  # يحتاج موافقة بشرية
    excel_approved_by: Optional[str]  # المعتمد
    excel_approved_at: Optional[str]  # وقت الاعتماد

    # ========================================================================
    # P5: Conditional Execution & Rejection Details (Phase 3)
    # ========================================================================
    
    # Conditional Execution & Rejection Details
    rejected_rows_details: Optional[List[Dict[str, Any]]]  # تفاصيل الصفوف المرفوضة للعرض
    user_execution_choice: Optional[str]  # "execute" | "fix" | "cancel" - قرار المستخدم
    auto_execute: Optional[bool]  # تفعيل التنفيذ التلقائي للملفات النظيفة



# ========================================================================
# Helper Functions for State Field Validation (Phase 3, Task 3.1.2)
# ========================================================================

def has_rejection_details(state: SerajState) -> bool:
    """
    Check if state has rejection details populated.
    
    Returns True if rejected_rows_details field exists and contains data.
    Used to determine if rejection information is available for display.
    
    Args:
        state: SerajState instance to check
        
    Returns:
        bool: True if rejection details exist and are non-empty
    """
    details = state.get("rejected_rows_details")
    return details is not None and isinstance(details, list) and len(details) > 0


def is_auto_executable(state: SerajState) -> bool:
    """
    Check if operation can be auto-executed without user approval.
    
    Returns True if auto_execute flag is explicitly set to True.
    This indicates a clean dry-run (0 rejected rows) that should proceed immediately.
    
    Args:
        state: SerajState instance to check
        
    Returns:
        bool: True if auto_execute is explicitly True
    """
    return state.get("auto_execute", False) is True


def get_rejection_count(state: SerajState) -> int:
    """
    Get the count of rejected rows from state.
    
    Returns the number of rejected rows if rejection details are populated,
    otherwise returns 0.
    
    Args:
        state: SerajState instance to check
        
    Returns:
        int: Number of rejected rows
    """
    details = state.get("rejected_rows_details", [])
    return len(details) if details else 0


def has_user_decision(state: SerajState) -> bool:
    """
    Check if user has made an execution decision.
    
    Returns True if user_execution_choice is set to a valid choice.
    
    Args:
        state: SerajState instance to check
        
    Returns:
        bool: True if user decision exists
    """
    choice = state.get("user_execution_choice")
    return choice is not None and choice in ["execute", "fix", "cancel"]


def needs_conditional_approval(state: SerajState) -> bool:
    """
    Determine if operation needs conditional approval workflow.
    
    Returns True if there are rejected rows and no user decision yet made.
    This indicates the operation should present approval options to the user.
    
    Args:
        state: SerajState instance to check
        
    Returns:
        bool: True if conditional approval workflow should be triggered
    """
    return has_rejection_details(state) and not has_user_decision(state)
