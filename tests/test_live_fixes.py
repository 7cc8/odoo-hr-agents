import pytest
from starlette.testclient import TestClient
from web_service import app
from seraj_llm_service import SerajLLMService
from seraj_session_manager import SerajSessionManager

client = TestClient(app)
AUTH_HEADERS = {"X-API-Key": "unit-test-write-token"}

def test_name_extraction_variants():
    seraj = SerajLLMService()
    
    # 1. Full name with preposition
    res1 = seraj.chat_turn("اضف موظف جديد بأسم ناصر الزهراني", chat_id="test_name_1")
    assert "ناصر الزهراني" in res1
    assert "بأسم" not in res1.split("الاسم المقترح:")[1].split("\n")[0].strip()

    # 2. Add employee without name
    res2 = seraj.chat_turn("اضف موظف جديد", chat_id="test_name_2")
    assert "**الاسم المقترح:** (يرجى كتابة الاسم" in res2
    assert "الاسم المقترح:** جديد" not in res2

def test_approve_conversational_with_department_not_hijacked():
    # 1. Create a plan
    seraj = SerajLLMService()
    chat_id = "web_test_add_full"
    res = seraj.chat_turn("اضف موظف جديد بأسم ناصر الزهراني", chat_id=chat_id)
    session = SerajSessionManager.get_instance().get_session(chat_id)
    assert session.pending_action is not None
    plan_id = session.pending_action["plan_id"]
    
    # 2. Approve via API with modified payload (department and job)
    res_api = client.post(
        "/api/agents/approve",
        headers=AUTH_HEADERS,
        json={
            "chat_id": chat_id,
            "operation_id": "op_test_123",
            "plan_id": plan_id,
            "modified_payload": {
                "name": "ناصر الزهراني",
                "department_id": "1",
                "job_title": "مطور برمجيات اول"
            }
        }
    )
    assert res_api.status_code == 200
    data = res_api.json()
    assert data["status"] == "success"
    # Verify it was NOT hijacked by excel batch
    assert "تعذر تنفيذ السجلات في Odoo" not in data["response"]
    assert ("تم إنشاء الموظف بنجاح" in data["response"] or "ID #" in data["response"])

def test_approve_conditional_json_and_form():
    # Test JSON payload
    res_json = client.post(
        "/api/approve-conditional",
        headers=AUTH_HEADERS,
        json={
            "operation_id": "op_cond_1",
            "chat_id": "web_test",
            "user_choice": "execute"
        }
    )
    assert res_json.status_code == 200
    assert res_json.json()["status"] == "success"

    # Test Form payload
    res_form = client.post(
        "/api/approve-conditional",
        headers=AUTH_HEADERS,
        data={
            "operation_id": "op_cond_2",
            "user_choice": "cancel"
        }
    )
    assert res_form.status_code == 200
    assert res_form.json()["status"] == "success"

def test_cancel_operation_cleans_status():
    from agent_events_service import get_events_service
    srv = get_events_service()
    seraj = SerajLLMService()
    chat_id = "web_test_cancel_flow"
    op_id = "op_test_cancel_456"

    # 1. Create a plan
    res = seraj.chat_turn("اضف موظف جديد بأسم خالد العتيبي", chat_id=chat_id, operation_id=op_id)
    session = SerajSessionManager.get_instance().get_session(chat_id)
    assert session.pending_action is not None

    # 2. Cancel via API
    res_cancel = client.post(
        "/api/agents/cancel",
        headers=AUTH_HEADERS,
        json={"chat_id": chat_id, "operation_id": op_id}
    )
    assert res_cancel.status_code == 200
    data = res_cancel.json()
    assert data["status"] == "success"
    assert "تم إلغاء العملية بناءً على طلبك" in data["response"]
    
    # 3. Verify status in events service is cancelled
    op = srv.get_operation(op_id)
    assert op is not None
    assert op["status"] == "cancelled"
    assert session.pending_action is None
