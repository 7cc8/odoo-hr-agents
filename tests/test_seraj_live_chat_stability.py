import io
from urllib.error import HTTPError
from unittest.mock import Mock

import pytest

from memory.manager import MemoryManager
from seraj_llm_service import SerajLLMService
from seraj_session_manager import SerajSessionManager


@pytest.mark.parametrize("status, attempts", [(503, 2), (401, 1)])
def test_cloud_retries_only_temporary_gateway_errors(seraj, monkeypatch, status, attempts):
    import llm_config_manager

    service, _ = seraj
    config = {
        "mode": "manual",
        "active_provider": "cloud",
        "local": {"base_url": "http://localhost:11434/v1", "model": "local-test"},
        "cloud": {
            "provider": "custom", "base_url": "https://example.test/v1",
            "model": "cloud-test", "api_key": "dummy", "timeout": 10,
        },
    }
    monkeypatch.setattr(llm_config_manager, "load_llm_config", lambda: config)
    monkeypatch.setattr("seraj_llm_service.time.sleep", Mock())
    monkeypatch.setattr("agents.cost_auditor.CostAuditor.get_instance", Mock())
    response = io.BytesIO(b'{"choices":[{"message":{"content":"OK"}}]}')
    send = Mock(side_effect=[HTTPError(None, status, "", {}, None), response])
    monkeypatch.setattr("urllib.request.urlopen", send)

    reply = service._call_llm("cloud-test", [{"role": "user", "content": "test"}])

    assert send.call_count == attempts
    if status == 503:
        assert reply["content"] == "OK"
        assert reply["_provider_used"] == "cloud"
        assert send.call_args.kwargs["timeout"] < 10
    else:
        assert reply is None
        session = service.session_manager.get_session("failure")
        assert "HTTP 401" in service._fallback_odoo_or_rules("طلب عام تجريبي", session)


@pytest.fixture
def seraj(tmp_path, monkeypatch):
    memory = MemoryManager(storage_dir=tmp_path)
    monkeypatch.setattr(MemoryManager, "get_instance", lambda *args, **kwargs: memory)
    service = SerajLLMService(fahas_agent=Mock())
    service.session_manager = SerajSessionManager()
    return service, memory


def test_contract_coverage_question_reads_aggregate_without_llm(seraj, monkeypatch):
    service, _ = seraj
    service.fahas.count_employee_contract_coverage.return_value = (12, 8)
    monkeypatch.setattr(service, "_run_tool_calling_loop", Mock(side_effect=AssertionError("unexpected LLM call")))

    reply = service.chat_turn("هل جميع الموظفين لديهم عقود ؟", company_id=7)

    assert "**8** من أصل **12**" in reply and "**4**" in reply
    service.fahas.count_employee_contract_coverage.assert_called_once_with(company_id=7, connection_id="default")
    assert service.last_turn_reasoning_steps[0]["agent"] == "fahas"


@pytest.mark.parametrize("contract_field", ["contract_date_start", "contract_ids", "contract_id"])
def test_contract_coverage_selects_searchable_field_in_scoped_company(contract_field):
    from fahas_service import FahasAgent, FahasSecurityError

    repo = Mock()
    repo.get_company_ids.return_value = [7]
    repo._execute_kw.side_effect = [{contract_field: {"searchable": True}}, 12, 8]
    agent = FahasAgent()
    agent.get_repository = Mock(return_value=repo)

    assert agent.count_employee_contract_coverage(7, "test") == (12, 8)
    model, method, domains, options = repo._execute_kw.call_args.args
    assert (model, method) == ("hr.employee", "search_count")
    assert domains == [[("company_id", "=", 7), ("active", "=", True), (contract_field, "!=", False)]]
    assert options["context"]["allowed_company_ids"] == [7]
    with pytest.raises(FahasSecurityError):
        agent.count_employee_contract_coverage(9, "test")
    assert repo._execute_kw.call_count == 3


def test_policy_persists_and_applies_across_sessions(seraj, monkeypatch):
    service, memory = seraj
    policy = "سياسة شركتنا تمنح بدل سكن 25% وبدل نقل 10%"
    assert policy in service.chat_turn("احفظ في ذاكرتك الدائمة أن " + policy, chat_id="save", company_id=7)
    with memory._get_db_connection() as conn:
        assert conn.execute("SELECT count(*) FROM facts WHERE content = ?", (policy,)).fetchone()[0] == 1
    reopened = MemoryManager(storage_dir=memory.storage_dir)
    monkeypatch.setattr(MemoryManager, "get_instance", lambda *args, **kwargs: reopened)
    assert policy in service.chat_turn("استرجع السياسات المحفوظة", chat_id="fresh", company_id=7)
    assert policy in service._build_system_prompt(service.session_manager.get_session("fresh"), "اختبار")
    question = "كم بدل السكن والنقل لموظف راتبه الأساسي 12,000 ريال حسب سياسة شركتنا؟"
    reply = service.chat_turn(question, chat_id="fresh", company_id=7)
    assert "3,000.00" in reply and "1,200.00" in reply
    assert "لا توجد نسبة محفوظة" in service.chat_turn(question, chat_id="other", company_id=8)


def test_eosb_uses_actual_wage_and_months_before_legal_rag(seraj, monkeypatch):
    service, _ = seraj
    monkeypatch.setattr(service, "_run_tool_calling_loop", Mock(side_effect=AssertionError("calculation should be direct")))
    reply = service.chat_turn("موظف راتبه الأساسي 10,000 ريال وبدل السكن 2,500 ريال، قدم استقالته بعد خدمة 6 سنوات وشهرين. كم يستحق مكافأة نهاية خدمة حسب نظام العمل السعودي؟")
    assert "12,500.00" in reply and "6.1667" in reply and "30,555.56" in reply
    assert "المادة 84" in reply and "المادة 85" in reply and "المادة 2" not in reply
    assert [step["tool"] for step in service.last_turn_reasoning_steps] == ["calculate_eosb"]
    messages = service.session_manager.get_session("default").history
    assert messages[0]["timestamp"] <= messages[1]["timestamp"]
    assert messages[1]["thinking_duration_sec"] == service.last_turn_duration_sec


def test_employee_list_contract_reference_and_empty_department(seraj):
    service, _ = seraj

    def search(model, **kwargs):
        if model == "hr.department":
            return {"records": [{"id": 11, "name": "المحاسبة"}]}
        if kwargs["domain"]:
            assert kwargs["domain"] == [("department_id", "=", 11)]
            return {"records": []}
        return {"records": [{"id": 10, "name": "الموظف الأول"}, {"id": 20, "name": "الموظف الثاني"}]}

    service.fahas.search_records.side_effect = search
    service.fahas.get_employee_contract.return_value = {
        "found": True, "employee_name": "الموظف الأول", "employee_id": 10, "wage": 8000,
        "housing_allowance": 2000, "transport_allowance": 800, "date_start": "2025-01-02", "state": "open",
    }
    assert "الموظف الأول" in service.chat_turn("اعرض قائمة الموظفين", company_id=7)
    followup = "كم راتب أول موظف في القائمة؟ ومتى بدأ عقده؟"
    assert "رمز المشغّل" in service.chat_turn(followup, company_id=7)
    service.fahas.get_employee_contract.assert_not_called()
    reply = service.chat_turn(followup, company_id=7, allow_contract_pay=True)
    assert "8,000.00" in reply and "2025-01-02" in reply
    assert service.session_manager.get_session("default").history[-1]["sensitive"]
    service.fahas.get_employee_contract.assert_called_once_with(employee_id_or_name=10, company_id=7, connection_id="default")
    reply = service.chat_turn("كم موظف في قسم تقنية المعلومات؟", company_id=7)
    assert "0 موظفين" in reply and "المحاسبة" in reply and "الموظف الأول" not in reply


def test_english_tool_synthesis_is_replaced_for_arabic_requests(seraj, monkeypatch):
    service, _ = seraj
    service.fahas.execute_query_task.return_value = {"records": [{"id": 1, "name": "محمد"}]}
    calls = []

    def provider(model_name, messages, tools=None):
        calls.append(list(messages))
        if len(calls) == 1:
            return {"content": "", "tool_calls": [{"id": "one", "function": {
                "name": "search_records", "arguments": '{"model":"hr.employee"}',
            }}]}
        return {"content": "I can see you've shared a JSON response."}

    monkeypatch.setattr(service, "_call_llm", provider)
    service.current_turn_steps = []
    session = service.session_manager.get_session("lang")
    reply = service._run_tool_calling_loop("test", [{"role": "user", "content": "ابحث عن محمد"}], session, "ابحث عن محمد")
    assert "محمد" in reply and "JSON" not in reply
    tool_messages = [message["content"] for message in calls[1] if message["role"] == "tool"]
    assert tool_messages[0].startswith("[نتيجة أداة النظام الداخلية")


def test_english_request_can_receive_english_reply(seraj, monkeypatch):
    service, _ = seraj
    answer = "Here is the requested information."
    monkeypatch.setattr(service, "_call_llm", Mock(return_value={"content": answer}))
    session = service.session_manager.get_session("english")
    query = "Please describe your role."
    assert service._run_tool_calling_loop("test", [{"role": "user", "content": query}], session, query) == answer
