"""
اختبار الأسئلة السبعة على Graph الحقيقي
==========================================
- النموذج: سيناريو مسجل (tool_calls ثم نص ثابت)
- Odoo: مستودع مزيّف (My Company=1, النخبة=13, توركين=0, العقار=0)
- fahas_service الحقيقي يعمل فوق المستودع المزيّف
- لا تمثيل لـ Fahas أو النص النهائي
"""
import json
from typing import Any, Dict, List
import pytest
from unittest.mock import Mock, patch

from graph.build_graph import build_graph
from langgraph.checkpoint.memory import MemorySaver
from tests.fake_odoo_repository import fake_odoo


# ==============================================================================
# Mock LLM - سيناريو مسجل
# ==============================================================================

class RecordedLLMScenario:
    """سيناريو مسجل للنموذج: tool_calls ثم نص ثابت"""
    
    def __init__(self):
        self.call_count = {}  # عدد المرات لكل سؤال
    
    def get_response(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """يرجع استجابة بناءً على آخر رسالة user"""
        # استخراج آخر رسالة user
        question = ""
        has_tool_results = False
        for msg in reversed(messages):
            if msg.get("role") == "user":
                question = msg.get("content", "")
                break
            elif msg.get("role") == "tool":
                has_tool_results = True
        
        # Key للتتبع
        key = question[:30]
        self.call_count[key] = self.call_count.get(key, 0) + 1
        call_num = self.call_count[key]
        
        # إذا كانت هناك نتائج أدوات، نرجع النص النهائي
        if has_tool_results:
            # استخراج نتائج الأدوات
            tool_results = []
            tool_names = []
            for msg in reversed(messages):
                if msg.get("role") == "tool":
                    try:
                        # ✅ قراءة المحتوى الفعلي من الأداة
                        content = msg.get("content", "null")
                        if isinstance(content, str):
                            parsed = json.loads(content)
                        else:
                            parsed = content
                        tool_results.append(parsed)
                        tool_names.append(msg.get("name", "unknown"))
                    except Exception as e:
                        print(f"⚠️ خطأ في قراءة tool result: {e}")
                        pass
            
            # ✅ توليد نص خاص بناءً على النتيجة الفعلية
            if tool_results:
                result = tool_results[0]
                tool_name = tool_names[0] if tool_names else "unknown"
                
                # count_records → {"count": int, ...}
                if tool_name == "count_records" and isinstance(result, dict) and "count" in result:
                    count = result["count"]
                    text = f"عدد الموظفين: {count}"
                
                # list_companies → قائمة شركات
                elif tool_name == "list_companies" and isinstance(result, list):
                    count = len(result)
                    if count > 0 and isinstance(result[0], dict) and "name" in result[0]:
                        names = [item.get("name", "?") for item in result[:3]]
                        text = f"الشركات المتاحة ({count}): {', '.join(names)}{'، وغيرها' if count > 3 else ''}."
                    else:
                        text = f"وجدت {count} شركة."
                
                # search_records → {"records": [...]} أو قائمة موظفين
                elif tool_name == "search_records":
                    records = result.get("records", result) if isinstance(result, dict) else result
                    if isinstance(records, list):
                        # تجميع حسب الشركة
                        by_company = {}
                        for emp in records:
                            comp_info = emp.get("company_id")
                            comp_name = comp_info[1] if isinstance(comp_info, list) and len(comp_info) > 1 else "?"
                            by_company[comp_name] = by_company.get(comp_name, 0) + 1
                        
                        dist_text = ", ".join([f"{comp}: {cnt}" for comp, cnt in by_company.items()])
                        total = sum(by_company.values())
                        text = f"التوزيع: {dist_text}. الإجمالي: {total}"
                    else:
                        text = f"وجدت {len(records)} سجل." if isinstance(records, list) else "تم."
                
                # fallback
                else:
                    if isinstance(result, dict) and "count" in result:
                        text = f"النتيجة: {result['count']}"
                    elif isinstance(result, int):
                        text = f"النتيجة: {result}"
                    elif isinstance(result, list):
                        text = f"وجدت {len(result)} عنصر."
                    else:
                        text = "تم تنفيذ الأمر بنجاح."
            else:
                text = "تم."
            
            return {"content": text, "tool_calls": []}
        
        # الاستدعاء الأول → tool_calls
        return self._get_tool_calls_for_question(question)
    
    def _get_tool_calls_for_question(self, question: str) -> Dict[str, Any]:
        """يرجع tool_calls المناسبة لكل سؤال"""
        # السؤال 1: "ما الشركات المتاحة لي؟"
        if "الشركات المتاحة" in question or "ما الشركات" in question:
            return {
                "content": "",
                "tool_calls": [{
                    "id": "call_companies",
                    "function": {
                        "name": "list_companies",
                        "arguments": json.dumps({}),
                    },
                }],
            }
        
        # السؤال 2: "كم عدد الموظفين في شركة النخبة الذكية؟"
        elif "عدد الموظفين" in question and ("النخبة" in question or "الذكية" in question):
            return {
                "content": "",
                "tool_calls": [{
                    "id": "call_count_elite",
                    "function": {
                        "name": "count_records",  # ✅ الاسم الصحيح
                        "arguments": json.dumps({"model": "hr.employee", "company_id": 15}),
                    },
                }],
            }
        
        # السؤال 3: "كم عدد الموظفين؟" (بدون شركة)
        elif "عدد الموظفين" in question and "النخبة" not in question and "كل" not in question and "النظام" not in question and "جميع" not in question:
            return {
                "content": "",
                "tool_calls": [{
                    "id": "call_count_current",
                    "function": {
                        "name": "count_records",  # ✅ الاسم الصحيح
                        "arguments": json.dumps({"model": "hr.employee"}),
                    },
                }],
            }
        
        # السؤال 4: "والشركة الثانية؟" → سؤال توضيحي (لا أدوات)
        elif "الشركة الثانية" in question or ("والشركة" in question and "؟" in question):
            return {
                "content": "هل تقصد شركة توركين للتجزئة؟ أرجو التأكيد.",
                "tool_calls": [],
            }
        
        # السؤال 5: "كم عدد الموظفين في كل الشركات؟"
        elif ("كل الشركات" in question or "جميع الشركات" in question) and "وزع" not in question and "وزّع" not in question:
            return {
                "content": "",
                "tool_calls": [{
                    "id": "call_count_all",
                    "function": {
                        "name": "count_records",  # ✅ الاسم الصحيح
                        "arguments": json.dumps({"model": "hr.employee"}),
                    },
                }],
            }
        
        # السؤال 6: "كم عدد الموظفين في النظام ككل؟"
        elif "النظام ككل" in question or "النظام كله" in question:
            return {
                "content": "",
                "tool_calls": [{
                    "id": "call_count_system",
                    "function": {
                        "name": "count_records",  # ✅ الاسم الصحيح
                        "arguments": json.dumps({"model": "hr.employee"}),
                    },
                }],
            }
        
        # السؤال 7: "وزّع الموظفين على الشركات"
        elif "وزع" in question or "وزّع" in question:
            return {
                "content": "",
                "tool_calls": [{
                    "id": "call_distribute",
                    "function": {
                        "name": "search_records",  # ✅ الاسم الصحيح
                        "arguments": json.dumps({"model": "hr.employee", "fields": ["name", "company_id"], "limit": 0}),
                    },
                }],
            }
        
        # غير معروف
        else:
            return {
                "content": "عذراً، لم أفهم السؤال.",
                "tool_calls": [],
            }


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_llm_scenario():
    """سيناريو LLM مسجل"""
    return RecordedLLMScenario()


@pytest.fixture
def mock_odoo_connection():
    """Mock اتصال Odoo ليستخدم المستودع المزيّف"""
    def execute_kw_wrapper(db, uid, password, model, method, args, kwargs=None):
        return fake_odoo.execute_kw(db, uid, password, model, method, args, kwargs)
    
    mock = Mock()
    mock.execute_kw = execute_kw_wrapper
    return mock


@pytest.fixture
def graph(mock_llm_scenario, mock_odoo_connection):
    """بناء Graph مع Mocks"""
    with patch("seraj_llm_service.SerajLLMService._call_openrouter") as mock_llm, \
         patch("xmlrpc.client.ServerProxy", return_value=mock_odoo_connection):
        
        # Mock LLM يستخدم السيناريو المسجل
        mock_llm.side_effect = lambda model_name, messages, tools: mock_llm_scenario.get_response(messages)
        
        checkpointer = MemorySaver()
        yield build_graph(checkpointer)


@pytest.fixture
def thread_config():
    """Thread واحد للمحادثة"""
    return {"configurable": {"thread_id": "test-seven-questions"}}


# ==============================================================================
# Tests
# ==============================================================================

class TestSevenQuestionsRealGraph:
    """اختبار الأسئلة السبعة على Graph الحقيقي"""
    
    def test_q1_companies_list(self, graph, thread_config):
        """
        السؤال 1: "ما الشركات المتاحة لي؟"
        
        التحقق:
        - يرجع 4 شركات
        - company_id فارغة بعد السؤال
        """
        result = graph.invoke(
            {"user_query": "ما الشركات المتاحة لي؟"},
            thread_config,
        )
        
        answer = result.get("answer", "")
        assert "4" in answer or "My Company" in answer or "النخبة" in answer
        assert result.get("company_id") is None
    
    def test_q2_count_elite_company(self, graph, thread_config):
        """
        السؤال 2: "كم عدد الموظفين في شركة النخبة الذكية؟"
        
        التحقق:
        - يرجع 13 موظف
        - company_id = 15
        """
        result = graph.invoke(
            {"user_query": "كم عدد الموظفين في شركة النخبة الذكية؟"},
            thread_config,
        )
        
        answer = result.get("answer", "")
        assert "13" in answer
        assert result.get("company_id") == 15
        assert result.get("company_name") == "شركة النخبة الذكية للتقنية"
    
    def test_q3_count_with_context(self, graph, thread_config):
        """
        السؤال 3: "كم عدد الموظفين؟" (بعد تحديد النخبة)
        
        التحقق:
        - يرجع 13 موظف (company_id من السياق)
        - company_id لا يزال 15
        """
        # إعداد: السؤال 2 أولاً
        graph.invoke(
            {"user_query": "كم عدد الموظفين في شركة النخبة الذكية؟"},
            thread_config,
        )
        
        # السؤال 3
        result = graph.invoke(
            {"user_query": "كم عدد الموظفين؟"},
            thread_config,
        )
        
        answer = result.get("answer", "")
        # يجب أن يرجع 13 (يستخدم company_id=15 من السياق)
        assert "13" in answer
        assert result.get("company_id") == 15
    
    def test_q4_ambiguous_question(self, graph, thread_config):
        """
        السؤال 4: "والشركة الثانية؟"
        
        التحقق:
        - يرجع سؤال تأكيد (وليس رقماً)
        - لا يتجاوز حد الخطوات
        """
        result = graph.invoke(
            {"user_query": "والشركة الثانية؟"},
            thread_config,
        )
        
        answer = result.get("answer", "")
        # يجب أن يكون سؤال تأكيد
        assert any(word in answer for word in ["؟", "تقصد", "أرجو", "تأكيد", "توركين"])
        assert result.get("turns", 0) <= 5
    
    def test_q5_all_companies(self, graph, thread_config):
        """
        السؤال 5: "كم عدد الموظفين في كل الشركات؟"
        
        التحقق:
        - يرجع 14 موظف
        - company_id فارغة
        """
        result = graph.invoke(
            {"user_query": "كم عدد الموظفين في كل الشركات؟"},
            thread_config,
        )
        
        answer = result.get("answer", "")
        assert "14" in answer
        assert result.get("company_id") is None
    
    def test_q6_system_total(self, graph, thread_config):
        """
        السؤال 6: "كم عدد الموظفين في النظام ككل؟"
        
        التحقق:
        - يرجع 14 موظف
        """
        result = graph.invoke(
            {"user_query": "كم عدد الموظفين في النظام ككل؟"},
            thread_config,
        )
        
        answer = result.get("answer", "")
        assert "14" in answer
    
    def test_q7_distribute_employees(self, graph, thread_config):
        """
        السؤال 7: "وزّع الموظفين على الشركات"
        
        التحقق:
        - مجموع التوزيع = 14 (1 + 13 + 0 + 0)
        - My Company: 1
        - النخبة: 13
        """
        result = graph.invoke(
            {"user_query": "وزّع الموظفين على الشركات"},
            thread_config,
        )
        
        answer = result.get("answer", "")
        # يجب أن يحتوي على 14 (الإجمالي)
        assert "14" in answer
        # وأرقام التوزيع
        assert "1" in answer  # My Company
        assert "13" in answer  # النخبة
    
    def test_company_context_flow(self, graph, thread_config):
        """
        اختبار تدفق سياق الشركة:
        1. None بعد السؤال 1 (قائمة الشركات)
        2. 15 بعد السؤال 2 (النخبة)
        3. None بعد السؤال 5 (كل الشركات)
        """
        # السؤال 1
        r1 = graph.invoke(
            {"user_query": "ما الشركات المتاحة لي؟"},
            thread_config,
        )
        assert r1.get("company_id") is None, "company_id should be None after Q1"
        
        # السؤال 2
        r2 = graph.invoke(
            {"user_query": "كم عدد الموظفين في شركة النخبة الذكية؟"},
            thread_config,
        )
        assert r2.get("company_id") == 15, "company_id should be 15 after Q2"
        
        # السؤال 5
        r5 = graph.invoke(
            {"user_query": "كم عدد الموظفين في كل الشركات؟"},
            thread_config,
        )
        assert r5.get("company_id") is None, "company_id should be None after Q5"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
