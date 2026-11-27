"""
اختبارات التحقق الصارمة للاستدلال الحقيقي وتتبع الأدوات الحية (Dynamic Tool Traces & True Reasoning Steps)
"""
import pytest
from seraj_llm_service import SerajLLMService, format_tool_trace
from fastapi.testclient import TestClient
from web_service import app


def test_format_tool_trace_fahas_search():
    trace = format_tool_trace(
        "search_employees",
        {"name": "أحمد"},
        {"records": [{"id": 1, "name": "أحمد الغامدي"}]},
        duration_ms=45,
    )
    assert trace["agent"] == "fahas"
    assert trace["agent_name_ar"] == "فاحص"
    assert trace["call_repr"] == "search_employees(name='أحمد')"
    assert trace["duration_ms"] == 45
    assert "أحمد الغامدي" in trace["summary"]


def test_format_tool_trace_mudaqqiq_eosb():
    trace = format_tool_trace(
        "calculate_eosb",
        {"service_years": 6, "last_salary": 10000},
        {"total_eosb": 35000.0},
        duration_ms=28,
    )
    assert trace["agent"] == "mudaqqiq"
    assert trace["agent_name_ar"] == "مدقق"
    assert "calculate_eosb" in trace["call_repr"]
    assert "service_years=6" in trace["call_repr"]
    assert "35,000.00" in trace["summary"]


def test_format_tool_trace_mudaqqiq_gosi():
    trace = format_tool_trace(
        "calculate_gosi",
        {"basic_salary": 8000},
        {"total_contribution": 1720.0},
        duration_ms=22,
    )
    assert trace["agent"] == "mudaqqiq"
    assert trace["agent_name_ar"] == "مدقق"
    assert "1,720.00" in trace["summary"]


def test_format_tool_trace_katib_write():
    trace = format_tool_trace(
        "write_record",
        {"record_id": 42, "values": {"mobile_phone": "0501234567"}},
        {"status": "success"},
        duration_ms=65,
    )
    assert trace["agent"] == "katib"
    assert trace["agent_name_ar"] == "كاتب"
    assert trace["call_repr"] == "write_record(id=42)"
    assert "تحديث بيانات السجل" in trace["summary"]


def test_conversational_true_reasoning_no_odoo():
    seraj = SerajLLMService()
    # استفسار حواري خالص بدون أدوات
    reply = seraj.chat_turn("مرحباً بك سراج، كيف حالك اليوم؟", chat_id="test_conv_1")
    assert isinstance(reply, str)
    assert hasattr(seraj, "last_turn_reasoning_steps")
    steps = seraj.last_turn_reasoning_steps
    assert len(steps) >= 1
    thought_step = steps[0]
    assert thought_step["type"] == "thought"
    assert thought_step["agent"] == "seraj"
    # التأكد من عدم إقحام فاحص أو Odoo في الاستنتاج الحواري
    assert "فاحص" not in thought_step["text"]
    assert "Odoo" not in thought_step["text"]
    assert "أودو" not in thought_step["text"]


def test_pronoun_resolution_reasoning_step():
    seraj = SerajLLMService()
    session = seraj.session_manager.get_session("test_pronoun_1")
    session.update_active_entities(employee_name="أحمد الغامدي", employee_id=101)

    # إرسال استفسار بضمير يعتمد على الذاكرة
    seraj.chat_turn("كم راتبه؟", chat_id="test_pronoun_1")
    steps = seraj.last_turn_reasoning_steps
    thought_steps = [s for s in steps if s.get("type") == "thought"]
    assert len(thought_steps) >= 1
    # التأكد من ظهور خطوة فهم السياق وربط الإدخال بالموظف
    assert any("أحمد الغامدي" in s["text"] for s in thought_steps)


def test_api_chat_returns_reasoning_steps():
    client = TestClient(app)
    res = client.post(
        "/api/seraj/chat",
        json={
            "message": "أهلاً وسهلاً",
            "chat_id": "test_api_reasoning",
            "company_id": 1,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "reasoning_steps" in data
    assert isinstance(data["reasoning_steps"], list)
    assert len(data["reasoning_steps"]) >= 1
    step0 = data["reasoning_steps"][0]
    assert "agent" in step0
    assert "duration_ms" in step0

