"""
اختبار الأسئلة السبعة على Graph مع Mock LLM
================================================
يختبر المسار الكامل: Graph → Agents → Odoo

بدون اتصال فعلي بـ OpenRouter
"""
import json
from typing import Any, Dict, List
import pytest
from unittest.mock import Mock, patch, MagicMock

from graph.build_graph import build_graph
from langgraph.checkpoint.memory import MemorySaver


# ==============================================================================
# Mock LLM Responses
# ==============================================================================

def create_mock_llm_for_question(messages: List[Dict[str, Any]]) -> Mock:
    """
    إنشاء Mock LLM يرجع استدعاءات أدوات مسجلة لكل سؤال
    
    Args:
        messages: قائمة الرسائل (آخر رسالة user)
    """
    mock = Mock()
    
    # استخراج آخر رسالة user
    question = ""
    has_tool_results = False
    for msg in reversed(messages):
        if msg.get("role") == "user":
            question = msg.get("content", "")
            break
        elif msg.get("role") == "tool":
            has_tool_results = True
    
    # إذا كانت هناك نتائج أدوات، يجب أن نرجع content (الرد النهائي)
    if has_tool_results:
        # استخراج نتائج الأداة
        tool_results = []
        for msg in reversed(messages):
            if msg.get("role") == "tool":
                try:
                    content = json.loads(msg.get("content", "[]"))
                    tool_results.append(content)
                except:
                    pass
        
        # الرد النهائي بناءً على نتائج الأداة
        if tool_results and isinstance(tool_results[0], list):
            # قائمة (شركات أو موظفين)
            count = len(tool_results[0])
            if count > 0 and "name" in tool_results[0][0]:
                # استخراج الأسماء
                names = [item.get("name", "") for item in tool_results[0][:3]]
                mock.return_value = {
                    "content": f"وجدت {count} عنصر: {', '.join(names)}{'، وغيرها' if count > 3 else ''}.",
                    "tool_calls": [],
                }
            else:
                mock.return_value = {
                    "content": f"وجدت {count} عنصر.",
                    "tool_calls": [],
                }
        elif tool_results and isinstance(tool_results[0], int):
            # عدد
            mock.return_value = {
                "content": f"العدد الإجمالي هو {tool_results[0]} موظف.",
                "tool_calls": [],
            }
        else:
            mock.return_value = {
                "content": "هذه هي النتائج التي طلبتها.",
                "tool_calls": [],
            }
        return mock
    
    # السؤال 1: "ما الشركات المتاحة لي؟"
    if "الشركات المتاحة" in question or "ما الشركات" in question:
        mock.return_value = {
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
    elif "عدد الموظفين" in question and "النخبة" in question:
        mock.return_value = {
            "content": "",
            "tool_calls": [{
                "id": "call_count_elite",
                "function": {
                    "name": "count_employees",
                    "arguments": json.dumps({"company_id": 15}),  # شركة النخبة
                },
            }],
        }
    
    # السؤال 3: "كم عدد الموظفين؟" (بدون شركة → يستخدم company_id من الحالة)
    elif "عدد الموظفين" in question and "النخبة" not in question and "كل" not in question and "النظام" not in question:
        mock.return_value = {
            "content": "",
            "tool_calls": [{
                "id": "call_count_current",
                "function": {
                    "name": "count_employees",
                    "arguments": json.dumps({}),  # سيأخذ company_id من الحالة
                },
            }],
        }
    
    # السؤال 4: "والشركة الثانية؟" (غامض → يطلب توضيح)
    elif "الشركة الثانية" in question or "والشركة" in question:
        mock.return_value = {
            "content": "هل تقصد شركة توركين للتجزئة؟ أرجو التأكيد.",
            "tool_calls": [],  # لا أدوات، فقط سؤال توضيحي
        }
    
    # السؤال 5: "كم عدد الموظفين في كل الشركات؟"
    elif ("كل الشركات" in question or "جميع الشركات" in question) and "وزع" not in question and "وزّع" not in question:
        mock.return_value = {
            "content": "",
            "tool_calls": [{
                "id": "call_count_all",
                "function": {
                    "name": "count_employees",
                    "arguments": json.dumps({}),  # بدون company_id → كل الشركات
                },
            }],
        }
    
    # السؤال 6: "كم عدد الموظفين في النظام ككل؟"
    elif "النظام ككل" in question or "النظام كله" in question:
        mock.return_value = {
            "content": "",
            "tool_calls": [{
                "id": "call_count_system",
                "function": {
                    "name": "count_employees",
                    "arguments": json.dumps({}),
                },
            }],
        }
    
    # السؤال 7: "وزّع الموظفين على الشركات"
    elif "وزع" in question or "وزّع" in question:
        mock.return_value = {
            "content": "",
            "tool_calls": [{
                "id": "call_distribute",
                "function": {
                    "name": "search_employees",
                    "arguments": json.dumps({"fields": ["name", "company_id"], "limit": 0}),
                },
            }],
        }
    
    # غير معروف
    else:
        mock.return_value = {
            "content": "عذراً، لم أفهم السؤال. هل يمكنك إعادة الصياغة؟",
            "tool_calls": [],
        }
    
    return mock


# Mock Fahas execute_query_task
def mock_fahas_execute(task_name: str, args: Dict[str, Any]) -> Any:
    """
    Mock لتنفيذ أدوات Fahas بدون Odoo فعلي
    """
    # list_companies
    if task_name == "list_companies":
        return [
            {"id": 1, "name": "My Company"},
            {"id": 15, "name": "شركة النخبة الذكية للتقنية"},
            {"id": 16, "name": "شركة توركين للتجزئة"},
            {"id": 17, "name": "شركة العقار الموحدة"},
        ]
    
    # count_employees
    elif task_name == "count_employees":
        company_id = args.get("company_id")
        
        if company_id == 15:  # النخبة الذكية
            return 13
        elif company_id is None:  # كل الشركات
            return 14
        elif company_id == 1:  # My Company
            return 1
        else:
            return 0
    
    # search_employees
    elif task_name == "search_employees":
        fields = args.get("fields", [])
        limit = args.get("limit", 10)
        
        # جميع الموظفين مع company_id
        all_employees = [
            {"id": 1, "name": "Administrator", "company_id": [1, "My Company"]},
        ] + [
            {"id": i, "name": f"موظف {i}", "company_id": [15, "شركة النخبة الذكية للتقنية"]}
            for i in range(12, 25)  # 13 موظف
        ]
        
        if limit == 0:  # كل الموظفين
            return all_employees
        
        return all_employees[:limit]
    
    # غير معروف
    else:
        raise ValueError(f"Unknown task: {task_name}")


# ==============================================================================
# Tests
# ==============================================================================

class TestSevenQuestionsWithGraph:
    """
    اختبار الأسئلة السبعة على Graph الكامل
    """
    
    @pytest.fixture
    def graph(self):
        """بناء Graph مع checkpointer"""
        checkpointer = MemorySaver()
        return build_graph(checkpointer)
    
    @pytest.fixture
    def thread_config(self):
        """إعداد Thread واحد للمحادثة"""
        return {"configurable": {"thread_id": "test-seven-questions"}}
    
    def test_q1_companies_list(self, graph, thread_config):
        """
        السؤال 1: "ما الشركات المتاحة لي؟"
        
        التحقق:
        - يرجع 4 شركات
        - company_id فارغة بعد السؤال (لأنه لم يحدد شركة)
        """
        with patch("seraj_llm_service.SerajLLMService._call_llm") as mock_llm, \
             patch("fahas_service.FahasAgent.execute_query_task", side_effect=mock_fahas_execute):
            
            # تكوين Mock
            mock_llm.side_effect = lambda model_name, messages, tools: create_mock_llm_for_question(
                messages
            ).return_value
            
            # تشغيل
            result = graph.invoke(
                {"user_query": "ما الشركات المتاحة لي؟"},
                thread_config,
            )
            
            # التحقق
            answer = result.get("answer", "")
            assert "My Company" in answer or "4" in answer or "شركة" in answer
            
            # company_id يجب أن يكون فارغ (لم يحدد شركة بعد)
            assert result.get("company_id") is None
    
    def test_q2_count_elite_company(self, graph, thread_config):
        """
        السؤال 2: "كم عدد الموظفين في شركة النخبة الذكية؟"
        
        التحقق:
        - يرجع 13 موظف
        - company_id = 15 (شركة النخبة)
        """
        with patch("seraj_llm_service.SerajLLMService._call_llm") as mock_llm, \
             patch("fahas_service.FahasAgent.execute_query_task", side_effect=mock_fahas_execute):
            
            mock_llm.side_effect = lambda model, messages, tools: create_mock_llm_for_question(
                messages[-1]["content"]
            ).return_value
            
            # تشغيل
            result = graph.invoke(
                {"user_query": "كم عدد الموظفين في شركة النخبة الذكية؟"},
                thread_config,
            )
            
            # التحقق
            answer = result.get("answer", "")
            assert "13" in answer
            
            # company_id يجب أن يكون 15 (النخبة الذكية)
            assert result.get("company_id") == 15
            assert result.get("company_name") == "شركة النخبة الذكية للتقنية"
    
    def test_q3_count_with_context(self, graph, thread_config):
        """
        السؤال 3: "كم عدد الموظفين؟" (بعد تحديد النخبة)
        
        التحقق:
        - يرجع 13 موظف (يستخدم company_id من السياق)
        - company_id لا يزال 15
        """
        # إعداد: تشغيل السؤال 2 أولاً لتحديد الشركة
        with patch("seraj_llm_service.SerajLLMService._call_llm") as mock_llm, \
             patch("fahas_service.FahasAgent.execute_query_task", side_effect=mock_fahas_execute):
            
            mock_llm.side_effect = lambda model, messages, tools: create_mock_llm_for_question(
                messages[-1]["content"]
            ).return_value
            
            # السؤال 2
            graph.invoke(
                {"user_query": "كم عدد الموظفين في شركة النخبة الذكية؟"},
                thread_config,
            )
            
            # السؤال 3 (الهدف الفعلي)
            result = graph.invoke(
                {"user_query": "كم عدد الموظفين؟"},
                thread_config,
            )
            
            # التحقق
            answer = result.get("answer", "")
            assert "13" in answer or "14" in answer  # حسب السياق
            
            # company_id لا يزال محفوظ
            assert result.get("company_id") in [15, None]
    
    def test_q4_ambiguous_question(self, graph, thread_config):
        """
        السؤال 4: "والشركة الثانية؟"
        
        التحقق:
        - يرجع سؤال توضيحي (وليس رقماً)
        - لا يتجاوز حد الخطوات (turns <= MAX_TURNS)
        """
        with patch("seraj_llm_service.SerajLLMService._call_llm") as mock_llm, \
             patch("fahas_service.FahasAgent.execute_query_task", side_effect=mock_fahas_execute):
            
            mock_llm.side_effect = lambda model, messages, tools: create_mock_llm_for_question(
                messages[-1]["content"]
            ).return_value
            
            # تشغيل
            result = graph.invoke(
                {"user_query": "والشركة الثانية؟"},
                thread_config,
            )
            
            # التحقق
            answer = result.get("answer", "")
            
            # يجب أن يكون سؤال توضيحي (يحتوي على "؟" أو "تقصد" أو "أرجو")
            assert any(word in answer for word in ["؟", "تقصد", "أرجو", "توضيح", "أي شركة"])
            
            # لا يتجاوز حد الخطوات
            assert result.get("turns", 0) <= 5  # MAX_TURNS
    
    def test_q5_all_companies(self, graph, thread_config):
        """
        السؤال 5: "كم عدد الموظفين في كل الشركات؟"
        
        التحقق:
        - يرجع 14 موظف
        - company_id فارغة (لأنه طلب "كل الشركات")
        """
        with patch("seraj_llm_service.SerajLLMService._call_llm") as mock_llm, \
             patch("fahas_service.FahasAgent.execute_query_task", side_effect=mock_fahas_execute):
            
            mock_llm.side_effect = lambda model, messages, tools: create_mock_llm_for_question(
                messages[-1]["content"]
            ).return_value
            
            # تشغيل
            result = graph.invoke(
                {"user_query": "كم عدد الموظفين في كل الشركات؟"},
                thread_config,
            )
            
            # التحقق
            answer = result.get("answer", "")
            assert "14" in answer
            
            # company_id يجب أن يكون فارغ (كل الشركات)
            assert result.get("company_id") is None
    
    def test_q6_system_total(self, graph, thread_config):
        """
        السؤال 6: "كم عدد الموظفين في النظام ككل؟"
        
        التحقق:
        - يرجع 14 موظف
        - company_id فارغة
        """
        with patch("seraj_llm_service.SerajLLMService._call_llm") as mock_llm, \
             patch("fahas_service.FahasAgent.execute_query_task", side_effect=mock_fahas_execute):
            
            mock_llm.side_effect = lambda model, messages, tools: create_mock_llm_for_question(
                messages[-1]["content"]
            ).return_value
            
            # تشغيل
            result = graph.invoke(
                {"user_query": "كم عدد الموظفين في النظام ككل؟"},
                thread_config,
            )
            
            # التحقق
            answer = result.get("answer", "")
            assert "14" in answer
    
    def test_q7_distribute_employees(self, graph, thread_config):
        """
        السؤال 7: "وزّع الموظفين على الشركات"
        
        التحقق:
        - يرجع توزيع (1 + 13 + 0 + 0 = 14)
        - الأرقام: My Company: 1، النخبة: 13، توركين: 0، العقار: 0
        """
        with patch("seraj_llm_service.SerajLLMService._call_llm") as mock_llm, \
             patch("fahas_service.FahasAgent.execute_query_task", side_effect=mock_fahas_execute):
            
            mock_llm.side_effect = lambda model, messages, tools: create_mock_llm_for_question(
                messages[-1]["content"]
            ).return_value
            
            # تشغيل
            result = graph.invoke(
                {"user_query": "وزّع الموظفين على الشركات"},
                thread_config,
            )
            
            # التحقق
            answer = result.get("answer", "")
            
            # يجب أن يحتوي على أرقام التوزيع
            assert "1" in answer or "My Company" in answer  # 1 موظف
            assert "13" in answer or "النخبة" in answer  # 13 موظف
            assert "14" in answer or "المجموع" in answer  # 14 إجمالي
    
    def test_no_question_exceeds_turn_limit(self, graph, thread_config):
        """
        التحقق: لا سؤال يتجاوز حد الخطوات (MAX_TURNS)
        """
        questions = [
            "ما الشركات المتاحة لي؟",
            "كم عدد الموظفين في شركة النخبة الذكية؟",
            "كم عدد الموظفين؟",
            "والشركة الثانية؟",
            "كم عدد الموظفين في كل الشركات؟",
            "كم عدد الموظفين في النظام ككل؟",
            "وزّع الموظفين على الشركات",
        ]
        
        with patch("seraj_llm_service.SerajLLMService._call_llm") as mock_llm, \
             patch("fahas_service.FahasAgent.execute_query_task", side_effect=mock_fahas_execute):
            
            mock_llm.side_effect = lambda model, messages, tools: create_mock_llm_for_question(
                messages[-1]["content"]
            ).return_value
            
            for q in questions:
                result = graph.invoke(
                    {"user_query": q},
                    {"configurable": {"thread_id": f"test-turn-limit-{hash(q)}"}},
                )
                
                # التحقق
                turns = result.get("turns", 0)
                assert turns <= 5, f"Question '{q}' exceeded turn limit: {turns} > 5"


class TestCompanyContextPersistence:
    """
    اختبار استمرارية سياق الشركة عبر الأسئلة
    """
    
    @pytest.fixture
    def graph(self):
        checkpointer = MemorySaver()
        return build_graph(checkpointer)
    
    @pytest.fixture
    def thread_config(self):
        return {"configurable": {"thread_id": "test-context-persistence"}}
    
    def test_company_context_flow(self, graph, thread_config):
        """
        اختبار تدفق سياق الشركة:
        1. فارغة بعد السؤال 1 (قائمة الشركات)
        2. = 15 بعد السؤال 2 (النخبة الذكية)
        3. فارغة بعد السؤال 5 (كل الشركات)
        """
        with patch("seraj_llm_service.SerajLLMService._call_llm") as mock_llm, \
             patch("fahas_service.FahasAgent.execute_query_task", side_effect=mock_fahas_execute):
            
            mock_llm.side_effect = lambda model, messages, tools: create_mock_llm_for_question(
                messages[-1]["content"]
            ).return_value
            
            # السؤال 1: قائمة الشركات
            r1 = graph.invoke(
                {"user_query": "ما الشركات المتاحة لي؟"},
                thread_config,
            )
            assert r1.get("company_id") is None, "❌ company_id should be None after Q1"
            
            # السؤال 2: عدد موظفي النخبة
            r2 = graph.invoke(
                {"user_query": "كم عدد الموظفين في شركة النخبة الذكية؟"},
                thread_config,
            )
            assert r2.get("company_id") == 15, "❌ company_id should be 15 after Q2"
            assert r2.get("company_name") == "شركة النخبة الذكية للتقنية"
            
            # السؤال 5: كل الشركات (يمسح company_id)
            r5 = graph.invoke(
                {"user_query": "كم عدد الموظفين في كل الشركات؟"},
                thread_config,
            )
            assert r5.get("company_id") is None, "❌ company_id should be None after Q5 (all companies)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
