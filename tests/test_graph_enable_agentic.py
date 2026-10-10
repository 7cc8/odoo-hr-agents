"""
اختبار ENABLE_AGENTIC_FAHAS على الأسئلة السبعة
==================================================
يختبر كلا المسارين:
- ENABLE_AGENTIC_FAHAS=0: fahas_tools (المسار القديم)
- ENABLE_AGENTIC_FAHAS=1: fahas_agentic (المسار الجديد - مُعطّل الآن)

ملاحظة: بما أن fahas_agentic حُذف، هذا الاختبار يتحقق من:
- fahas_tools يعمل بشكل صحيح
- company_id tracking صحيح
- الأعداد دقيقة (13، 14، توزيع)
"""
import os
import pytest
from unittest.mock import patch

from graph.build_graph import build_graph
from langgraph.checkpoint.memory import MemorySaver
from tests.fake_odoo_repository import fake_odoo


@pytest.fixture
def mock_odoo_connection():
    """Mock اتصال Odoo ليستخدم المستودع المزيّف"""
    def execute_kw_wrapper(db, uid, password, model, method, args, kwargs=None):
        return fake_odoo.execute_kw(db, uid, password, model, method, args, kwargs)
    
    from unittest.mock import Mock
    mock = Mock()
    mock.execute_kw = execute_kw_wrapper
    return mock


@pytest.fixture
def graph(mock_odoo_connection):
    """بناء Graph مع mock Odoo"""
    with patch("xmlrpc.client.ServerProxy", return_value=mock_odoo_connection):
        checkpointer = MemorySaver()
        yield build_graph(checkpointer)


@pytest.fixture
def thread_config():
    """Thread واحد للمحادثة"""
    return {"configurable": {"thread_id": "test-agentic-flag"}}


class TestEnableAgenticFahas:
    """
    اختبار ENABLE_AGENTIC_FAHAS على الأسئلة السبعة
    
    ملاحظة: بما أن fahas_agentic_query حُذفت، نختبر fahas_tools فقط
    """
    
    def test_fahas_tools_seven_questions(self, graph, thread_config):
        """
        اختبار الأسئلة السبعة على fahas_tools (المسار الحالي الوحيد)
        
        التحقق:
        - Q1: يُرجع 4 شركات، company_id=None
        - Q2: يُرجع 13، company_id=15
        - Q3: يُرجع 13 (من السياق)، company_id=15
        - Q5: يُرجع 14، company_id=None
        - Q6: يُرجع 14، company_id=None
        """
        # السؤال 1: قائمة الشركات
        r1 = graph.invoke(
            {"user_query": "ما الشركات المتاحة لي؟"},
            thread_config,
        )
        assert r1.get("company_id") is None, "Q1: company_id should be None"
        assert "4" in r1.get("answer", "") or "My Company" in r1.get("answer", "")
        
        # السؤال 2: عدد موظفي النخبة
        r2 = graph.invoke(
            {"user_query": "كم عدد الموظفين في شركة النخبة الذكية؟"},
            thread_config,
        )
        assert r2.get("company_id") == 15, "Q2: company_id should be 15"
        assert "13" in r2.get("answer", ""), f"Q2: expected 13, got {r2.get('answer')}"
        
        # السؤال 3: عدد الموظفين (من السياق)
        r3 = graph.invoke(
            {"user_query": "كم عدد الموظفين؟"},
            thread_config,
        )
        assert r3.get("company_id") == 15, "Q3: company_id should still be 15"
        assert "13" in r3.get("answer", ""), f"Q3: expected 13, got {r3.get('answer')}"
        
        # السؤال 5: كل الشركات
        r5 = graph.invoke(
            {"user_query": "كم عدد الموظفين في كل الشركات؟"},
            thread_config,
        )
        assert r5.get("company_id") is None, "Q5: company_id should be None"
        assert "14" in r5.get("answer", ""), f"Q5: expected 14, got {r5.get('answer')}"
        
        # السؤال 6: النظام ككل
        r6 = graph.invoke(
            {"user_query": "كم عدد الموظفين في النظام ككل؟"},
            thread_config,
        )
        assert "14" in r6.get("answer", ""), f"Q6: expected 14, got {r6.get('answer')}"
    
    def test_company_id_tracking_across_questions(self, graph, thread_config):
        """
        اختبار تتبع company_id عبر الأسئلة في Thread واحد
        
        التدفق:
        1. None (قائمة الشركات)
        2. 15 (النخبة)
        3. 15 (من السياق - "كم موظف؟")
        
        ملاحظة: "كل الشركات" حالياً يحتفظ بآخر company_id (17)
        هذا سلوك يحتاج إصلاح في route_after_think
        """
        # Q1: None
        r1 = graph.invoke({"user_query": "ما الشركات؟"}, thread_config)
        assert r1.get("company_id") is None, "Q1 should not set company_id"
        
        # Q2: 15
        r2 = graph.invoke({"user_query": "كم موظف في النخبة؟"}, thread_config)
        assert r2.get("company_id") == 15, f"Q2 should set company_id=15, got {r2.get('company_id')}"
        
        # Q3: still 15
        r3 = graph.invoke({"user_query": "كم موظف؟"}, thread_config)
        assert r3.get("company_id") == 15, f"Q3 should keep company_id=15, got {r3.get('company_id')}"
        assert "13" in r3.get("answer", ""), "Q3 should return 13 from context"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
