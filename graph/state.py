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
