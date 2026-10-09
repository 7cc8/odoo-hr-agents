"""Regression tests for real audit routing, persistence, status and Excel processing.

All Odoo calls are mocked. These tests must never mutate a real Odoo database.
"""
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

import agent_events_service as events
from seraj_session_manager import SerajSessionManager
from sijil_audit_service import SijilAuditService
from web_service import app


@pytest.fixture
def cockpit(tmp_path, monkeypatch):
    monkeypatch.setattr(events, "AGENT_OPS_LOG_FILE", tmp_path / "operations.jsonl")
    srv = events.AgentEventsService()
    monkeypatch.setattr(events.AgentEventsService, "_instance", srv)
    monkeypatch.setattr(SerajSessionManager, "_instance", SerajSessionManager())
    import web_service
    monkeypatch.setattr(web_service, "UPLOAD_DIR", tmp_path)
    return srv, TestClient(app), tmp_path


def test_disk_replay_uses_final_state_and_full_history(cockpit):
    srv, _, _ = cockpit
    op = srv.start_operation("طلب مستقل", chat_id="chat_a", company_id=22)
    for i in range(110):
        srv.emit_event(op, "fahas", "checked", "inspecting_data", f"فحص {i}")
    srv.emit_event(op, "sijil", "done", "completed", "اكتمل", plan_id="plan_abc")
    srv.record_turn(op, "طلب مستقل", "الرد الفعلي")
    restored = events.AgentEventsService().get_operation(op)
    assert restored["status"] == "completed"
    assert restored["chat_id"] == "chat_a"
    assert restored["company_id"] == 22
    assert restored["user_query"] == "طلب مستقل"
    assert restored["plan_id"] == "plan_abc"
    assert len(restored["events"]) == 113
    assert restored["messages"][-1]["content"] == "الرد الفعلي"


def test_terminal_state_releases_all_agents_but_not_other_operations(cockpit):
    srv, _, _ = cockpit
    first = srv.start_operation("أ")
    srv.emit_event(first, "fahas", "check", "querying_odoo", "يفحص")
    second = srv.start_operation("ب")
    srv.emit_event(first, "katib", "done", "completed", "اكتمل")
    states = {a["id"]: a for a in srv.get_agents_overview()}
    assert states["fahas"]["status_code"] == "ready"
    assert states["katib"]["status_code"] == "ready"
    assert states["seraj"]["active_operation_id"] == second


def test_restart_marks_orphaned_processing_inconclusive(cockpit):
    srv, _, _ = cockpit
    op = srv.start_operation("عملية انقطعت", chat_id="lost")
    replay = events.AgentEventsService()
    restored = replay.get_operation(op)
    assert restored["status"] == "inconclusive"
    assert restored["events"][-1]["event_type"] == "recovery_interrupted"
    assert restored["chat_id"] == "lost"
    # Repeated restart does not keep appending recovery events.
    assert len(events.AgentEventsService().get_operation(op)["events"]) == len(restored["events"])


def test_search_finds_operations_older_than_fifty_and_plan_alias(cockpit):
    srv, _, tmp = cockpit
    target = srv.start_operation("طلب قديم")
    srv.emit_event(target, "hares", "plan", "waiting_approval", "خطة", plan_id="plan_xyz")
    for i in range(60):
        srv.start_operation(f"طلب {i}")
    audit = SijilAuditService(logs_dir=tmp)
    assert audit.search_operations(target)["operation"]["operation_id"] == target
    assert audit.search_operations("plan_xyz")["operation"]["operation_id"] == target
    assert audit.get_operation_detail(f"OP-AGENTS-{target}")["operation_id"] == target
    assert audit.get_operation_detail("plan_xyz")["final_status_code"] == "waiting_approval"


def test_audit_paginates_ten_and_rejects_invalid_bounds(cockpit):
    srv, client, _ = cockpit
    ids = [srv.start_operation(f"عملية {i}") for i in range(14)]
    headers = {"X-API-Key": "hr-write-secret-token"}
    first = client.get("/api/sijil/recent?limit=10", headers=headers).json()
    second = client.get("/api/sijil/recent?limit=10&offset=10", headers=headers).json()
    assert len(first["operations"]) == 10
    assert first["total"] >= 14
    assert {r["identifier"] for r in first["operations"]}.isdisjoint(
        {r["identifier"] for r in second["operations"]}
    )
    assert client.get("/api/sijil/recent?limit=0", headers=headers).status_code == 422
    assert client.get("/api/sijil/recent?offset=-1", headers=headers).status_code == 422
    assert any(r["identifier"] in ids for r in first["operations"])


def test_legacy_deletion_search_and_display_id_open_same_record(cockpit):
    _, _, tmp = cockpit
    record = {"plan_id": "legacy_123", "action": "archive", "record_id": 42,
              "status": "success", "timestamp": "2026-10-09T00:00:00Z"}
    (tmp / "deletion_audit_log.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    audit = SijilAuditService(logs_dir=tmp)
    result = audit.search_operations("legacy_123")["operation"]
    assert result["identifier"] == "del_legacy_123"
    assert audit.get_operation_detail(result["operation_id"])["identifier"] == result["identifier"]


def test_chat_records_actual_reply_and_ends_processing(cockpit):
    srv, client, _ = cockpit
    with patch("seraj_llm_service.SerajLLMService.chat_turn", return_value="رد فعلي"):
        data = client.post("/api/seraj/chat", json={"chat_id": "unique_a", "message": "طلب"}).json()
    op = data["operation"]
    assert op["status"] == "completed"
    assert op["messages"][-1]["content"] == "رد فعلي"
    assert op["chat_id"] == "unique_a"
    assert client.get(f"/api/agents/operations/{op['operation_id']}").json()["operation"]["messages"] == op["messages"]


def test_missing_model_key_is_failed_not_completed(cockpit):
    _, client, _ = cockpit
    with patch("seraj_llm_service.SerajLLMService.is_configured", return_value=False):
        data = client.post("/api/seraj/chat", json={"message": "سؤال عام", "chat_id": "no_model"}).json()
    assert data["operation"]["status"] == "failed"
    assert any(e["event_type"] == "configuration_error" for e in data["operation"]["events"])


def test_direct_answer_does_not_invent_fahas_query(cockpit):
    _, client, _ = cockpit
    with patch("seraj_llm_service.SerajLLMService.is_configured", return_value=True), patch(
        "seraj_llm_service.SerajLLMService._call_openrouter", return_value={"content": "رد معرفي بلا استعلام"}
    ):
        data = client.post("/api/seraj/chat", json={"message": "سؤال عام", "chat_id": "direct"}).json()
    assert data["operation"]["status"] == "completed"
    assert not any(e["agent"] == "fahas" for e in data["operation"]["events"])


def test_real_query_events_surround_actual_tool_execution(cockpit):
    _, client, _ = cockpit
    tool = {"id": "read", "function": {"name": "search_records", "arguments": "{}"}}
    with patch("seraj_llm_service.SerajLLMService.is_configured", return_value=True), patch(
        "seraj_llm_service.SerajLLMService._call_openrouter",
        side_effect=[{"tool_calls": [tool]}, {"content": "نتيجة القراءة"}]
    ), patch("fahas_service.FahasAgent.execute_query_task", return_value={"records": []}) as read:
        data = client.post("/api/seraj/chat", json={"message": "سؤال عام", "chat_id": "read"}).json()
    read.assert_called_once()
    types = [e["event_type"] for e in data["operation"]["events"]]
    assert types.index("odoo_query") < types.index("query_returned")
    assert data["operation"]["status"] == "completed"


def test_operation_chat_cannot_be_silently_rebound(cockpit):
    srv, client, _ = cockpit
    op = srv.start_operation("عملية أ", chat_id="chat_a")
    payload = {"operation_id": op, "chat_id": "chat_b", "message": "تأكيد"}
    assert client.post("/api/seraj/chat", json=payload).status_code == 409
    assert client.post("/api/agents/approve", json=payload).status_code == 409
    assert client.post("/api/agents/cancel", json=payload).status_code == 409


def test_resume_preserves_company_scope(cockpit):
    srv, client, _ = cockpit
    op = srv.start_operation("شركة 22", chat_id="scope", company_id=22)
    with patch("seraj_llm_service.SerajLLMService.chat_turn", return_value="رد") as turn:
        res = client.post("/api/seraj/chat", json={
            "chat_id": "scope", "message": "متابعة", "operation_id": op, "company_id": 99,
        })
    assert res.status_code == 200
    assert turn.call_args.kwargs["company_id"] == 22


def test_pending_decision_not_running_and_no_fake_verification(cockpit):
    srv, client, tmp = cockpit
    def pending(**kw):
        SerajSessionManager.get_instance().get_session(kw["chat_id"]).pending_action = {"plan_id": "p"}
        return "ينتظر اعتمادك"
    with patch("seraj_llm_service.SerajLLMService.chat_turn", side_effect=pending):
        data = client.post("/api/seraj/chat", json={"message": "تعديل", "chat_id": "pending"}).json()
    op = data["operation_id"]
    assert data["operation"]["status"] == "waiting_approval"
    assert client.get(f"/api/agents/operations/{op}/events").json()["is_active"] is False
    assert SijilAuditService(logs_dir=tmp).get_operation_detail(op)["verification_result"]["verified"] is False


def test_failed_excel_never_reports_success(cockpit):
    _, client, _ = cockpit
    with patch("dry_run_report.build_full_report", side_effect=ValueError("ملف تالف")):
        data = client.post("/api/agents/upload", files={"file": ("../../bad.xlsx", b"bad")}).json()
    assert data["status"] == "error"
    assert data["operation"]["status"] == "failed"
    assert "ملف تالف" in data["message"]
    assert data["filename"] == "bad.xlsx"
    assert client.post("/api/agents/upload", files={"file": ("bad.csv", b"data")}).status_code == 415
    assert client.post("/api/agents/upload", files={"file": ("empty.xlsx", b"")}).status_code == 400


def test_real_excel_parser_validator_and_saved_report(cockpit):
    _, client, _ = cockpit
    workbook = Workbook()
    ws = workbook.active
    ws.title = "Employees"
    ws.append(["name", "work_email", "work_phone", "mobile_phone", "job_title", "company", "department", "job", "hiring_date"])
    ws.append(["أحمد", "ahmad@example.com", "", "0501112222", "", "شركة أ", "", "", "2026-10-01"])
    ws.append(["سارة", "invalid-email", "", "0501113333", "", "شركة أ", "", "", "2026-10-01"])
    stream = io.BytesIO()
    workbook.save(stream)
    repo = MagicMock()
    repo.get_live_reference_snapshot.return_value = {"companies": [{"id": 22, "name": "شركة أ"}], "departments": [], "jobs": []}
    repo.search_employee_email_candidates.return_value = []
    repo.get_session_info.return_value = {"odoo_db": "test_db"}
    with patch("dry_run_report.OdooReadonlyRepository", return_value=repo):
        response = client.post("/api/agents/upload", data={"chat_id": "xlsx", "company_id": 22},
            files={"file": ("employees.xlsx", stream.getvalue())})
    data = response.json()
    assert data["status"] == "success"
    report = data["dry_run_report"]
    assert report["total_rows"] == 2
    assert report["accepted_count"] == 1
    assert report["rejected_count"] == 1
    assert report["rows"][1]["reasons"]
    assert data["operation"]["status"] == "completed"
    assert not any(e["agent"] == "katib" for e in data["operation"]["events"])
    assert client.get(report["report_url"]).status_code == 200


def test_status_uses_real_company_list_and_masks_secret(cockpit):
    _, client, _ = cockpit
    cfg = {"url": "https://test.odoo.com", "db": "db_b", "username": "user", "api_key": "do-not-return"}
    companies = [{"id": i, "name": f"شركة {i}"} for i in range(1, 32)]
    with patch("odoo_config_manager.get_active_odoo_config", return_value=cfg), patch(
        "odoo_config_manager.test_odoo_connection", return_value={"ok": True, "companies": companies}
    ):
        response = client.get("/api/status")
    assert response.json()["companies"] == companies
    assert response.json()["odoo"]["database"] == "db_b"
    assert "do-not-return" not in response.text


def test_connection_switch_validated_and_blocks_pending_operations(cockpit):
    srv, client, _ = cockpit
    body = {"url": "https://test.odoo.com", "db": "new_db", "username": "user", "api_key": "test-secret"}
    headers = {"X-API-Key": "hr-write-secret-token"}
    assert client.post("/api/settings/connection", json=body).status_code == 401
    with patch("odoo_config_manager.test_odoo_connection", return_value={"ok": False, "error": "تعذر"}), patch(
        "odoo_config_manager.save_active_odoo_config"
    ) as save:
        assert client.post("/api/settings/connection", json=body, headers=headers).status_code == 400
        save.assert_not_called()
    with patch("odoo_config_manager.test_odoo_connection", return_value={"ok": True, "companies": []}), patch(
        "odoo_config_manager.save_active_odoo_config"
    ) as save:
        assert client.post("/api/settings/connection", json=body, headers=headers).status_code == 200
        save.assert_called_once()
    srv.start_operation("عملية معلقة")
    assert client.post("/api/settings/connection", json=body, headers=headers).status_code == 409


def test_agent_cards_have_capabilities_and_real_history(cockpit):
    srv, client, _ = cockpit
    op = srv.start_operation("اختبار")
    srv.emit_event(op, "fahas", "query", "querying_odoo", "قراءة حقيقية")
    agents = client.get("/api/agents/overview").json()["agents"]
    fahas = next(a for a in agents if a["id"] == "fahas")
    assert fahas["capabilities"]
    assert fahas["recent_tasks"][0]["description_ar"] == "قراءة حقيقية"
    assert fahas["operation_count"] == 1


def test_governance_pdf_is_real_a4_and_white(cockpit, tmp_path):
    # Browser renderer must exist in production; never return a fake PDF header.
    from playwright.sync_api import sync_playwright
    audit = SijilAuditService(logs_dir=tmp_path)
    html = audit.generate_html_report()
    document = tmp_path / "governance.html"
    document.write_text(html, encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(document.as_uri())
        page.emulate_media(media="print")
        assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(255, 255, 255)"
        browser.close()
    pdf = audit._render_html_to_pdf(document, tmp_path / "report.pdf")
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000
