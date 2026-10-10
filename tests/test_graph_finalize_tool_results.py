"""
اختبار انحدار: finalize يعرض نتائج الأدوات عند غياب نص النموذج
==========================================================================
"""
import pytest
from graph.nodes import finalize


def test_finalize_shows_tool_results_when_llm_content_missing():
    """
    اختبار انحدار: عندما لا يكتب النموذج جواباً لكن توجد نتائج أدوات،
    يجب عرض نتائج الأدوات بدلاً من رسالة "لم أستطع إكمال الطلب"
    """
    # حالة: tool results موجودة لكن content فارغ
    state = {
        "last_assistant": {"content": ""},  # ← فارغ
        "messages": [
            {"role": "user", "content": "ما الشركات المتاحة؟"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1", "function": {"name": "list_companies"}}]},
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "name": "list_companies",
                "content": '[{"id": 1, "name": "My Company"}, {"id": 15, "name": "النخبة الذكية"}]',
            },
        ],
    }
    
    result = finalize(state)
    answer = result.get("answer", "")
    
    # يجب أن يعرض النتائج، ليس رسالة العجز
    assert "2 عنصر" in answer or "My Company" in answer or "النخبة" in answer
    assert "لم أستطع إكمال" not in answer  # ← الخلل القديم


def test_finalize_shows_count_result():
    """
    عندما تكون نتيجة الأداة رقماً (count)
    """
    state = {
        "last_assistant": {"content": ""},
        "messages": [
            {"role": "user", "content": "كم عدد الموظفين؟"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1", "function": {"name": "count_employees"}}]},
            {"role": "tool", "tool_call_id": "call_1", "name": "count_employees", "content": "14"},
        ],
    }
    
    result = finalize(state)
    answer = result.get("answer", "")
    
    assert "14" in answer
    assert "لم أستطع إكمال" not in answer


def test_finalize_still_shows_error_when_no_results():
    """
    عندما لا توجد نتائج أدوات أيضاً، يعرض رسالة العجز
    """
    state = {
        "last_assistant": {"content": ""},
        "messages": [
            {"role": "user", "content": "سؤال"},
            {"role": "assistant", "content": ""},  # لا tool_calls
        ],
    }
    
    result = finalize(state)
    answer = result.get("answer", "")
    
    # هنا يجب أن تظهر رسالة العجز (لا نتائج أدوات)
    assert "لم أستطع إكمال" in answer


def test_finalize_prefers_llm_content_when_present():
    """
    عندما يكتب النموذج جواباً، يُفضَّل على نتائج الأدوات الخام
    """
    state = {
        "last_assistant": {"content": "وجدت شركتين: My Company والنخبة الذكية."},
        "messages": [
            {"role": "user", "content": "ما الشركات؟"},
            {"role": "assistant", "content": "وجدت شركتين...", "tool_calls": [...]},
            {"role": "tool", "content": '[...]'},
        ],
    }
    
    result = finalize(state)
    answer = result.get("answer", "")
    
    # يجب أن يستخدم content من النموذج
    assert "وجدت شركتين" in answer
    assert "عنصر" not in answer  # ليس العرض الخام
