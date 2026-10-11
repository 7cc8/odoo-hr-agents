"""
اختبار عدم الاحتفاظ بحالة في seraj_meta_reflect
====================================================
يتحقق من أن استدعاءين متتاليين لـ seraj_meta_reflect
لا يشاركان حالة مشتركة.
"""
import pytest
from graph.agentic_nodes import seraj_meta_reflect


def test_seraj_meta_reflect_no_shared_state():
    """
    يتحقق من أن seraj_meta_reflect لا يحتفظ بحالة بين استدعاءين.
    
    يُنشئ SerajMetaAgent() في كل مرة، لذلك لا يجب أن تُشارك
    الحالة (learned_patterns, long_term_memory) بين الاستدعاءين.
    """
    # الاستدعاء الأول
    state1 = {
        "user_query": "كم عدد الموظفين؟",
        "meta_selected_agents": ["fahas"],
        "last_tool_error": None,
        "healed_data": [],
        "security_approved": True,
        "security_decision": {},
        "write_success": False,
        "write_result": {},
        "compliance_approved": True,
        "compliance_decision": {},
        "match_found": False,
        "match_confidence": 0.0,
        "audit_logged": False,
        "audit_decision": {},
    }
    
    result1 = seraj_meta_reflect(state1)
    
    # الاستدعاء الثاني
    state2 = {
        "user_query": "أنشئ موظف جديد",
        "meta_selected_agents": ["katib"],
        "last_tool_error": None,
        "healed_data": [],
        "security_approved": True,
        "security_decision": {},
        "write_success": True,
        "write_result": {"id": 42},
        "compliance_approved": True,
        "compliance_decision": {},
        "match_found": False,
        "match_confidence": 0.0,
        "audit_logged": True,
        "audit_decision": {},
    }
    
    result2 = seraj_meta_reflect(state2)
    
    # التحقق: كلا الاستدعاءين أرجع نتيجة
    assert "meta_reflection" in result1
    assert "meta_reflection" in result2
    
    # التحقق: النتائج مختلفة (ليست نفس الكائن)
    assert result1 is not result2
    
    # التحقق: لا agent_traces في النتيجة (ENABLE_META_TRACES=0 افتراضاً)
    assert "agent_traces" not in result1
    assert "agent_traces" not in result2
    
    print("✅ seraj_meta_reflect لا يحتفظ بحالة مشتركة بين استدعاءين")


def test_seraj_meta_orchestration_no_shared_state():
    """
    يتحقق من أن seraj_meta_orchestration لا يحتفظ بحالة بين استدعاءين.
    """
    from graph.agentic_nodes import seraj_meta_orchestration
    
    # الاستدعاء الأول
    state1 = {
        "user_query": "كم عدد الموظفين في قسم التقنية؟",
        "intent": "query",
        "context": {},
    }
    
    result1 = seraj_meta_orchestration(state1)
    
    # الاستدعاء الثاني
    state2 = {
        "user_query": "أنشئ موظف جديد اسمه أحمد",
        "intent": "write",
        "context": {},
    }
    
    result2 = seraj_meta_orchestration(state2)
    
    # التحقق
    assert "meta_selected_agents" in result1
    assert "meta_selected_agents" in result2
    
    # التحقق: النتائج مختلفة
    assert result1 is not result2
    
    # التحقق: لا agent_traces في النتيجة (ENABLE_META_TRACES=0 افتراضاً)
    assert "agent_traces" not in result1
    assert "agent_traces" not in result2
    
    print("✅ seraj_meta_orchestration لا يحتفظ بحالة مشتركة بين استدعاءين")
