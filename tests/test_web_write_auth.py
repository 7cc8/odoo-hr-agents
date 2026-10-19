"""Write-token enforcement on mutating endpoints that used to be open (phase-1-5)."""
import pytest
from fastapi.testclient import TestClient

import web_service
from seraj_session_manager import SerajSessionManager
from web_service import app

client = TestClient(app)
# Handlers behind a valid token may blow up on the missing Odoo; that is not an auth failure.
lenient = TestClient(app, raise_server_exceptions=False)
TOKEN = "unit-test-write-token"
GOOD = {"X-API-Key": TOKEN}
BAD = {"X-API-Key": "wrong-token"}

APPLY_BODY = {"approval_token": "none", "user_confirmation_text": "تأكيد", "executor": "tester"}
WRITE_ENDPOINTS = [
    ("/api/approve-and-execute", {"run_id": "does-not-exist"}),
    ("/api/letters/apply", APPLY_BODY),
    ("/api/warnings/apply", APPLY_BODY),
    ("/api/expenses/apply", APPLY_BODY),
]


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setenv("WRITE_API_TOKEN", TOKEN)


@pytest.mark.parametrize("path,body", WRITE_ENDPOINTS)
def test_rejects_missing_token(path, body):
    assert client.post(path, json=body).status_code == 401


@pytest.mark.parametrize("path,body", WRITE_ENDPOINTS)
def test_rejects_wrong_token(path, body):
    assert client.post(path, json=body, headers=BAD).status_code == 401


@pytest.mark.parametrize("path,body", WRITE_ENDPOINTS)
def test_disabled_when_token_not_configured(monkeypatch, path, body):
    monkeypatch.setenv("WRITE_API_TOKEN", "")
    monkeypatch.setattr(web_service, "WRITE_API_TOKEN", "")
    assert client.post(path, json=body, headers=GOOD).status_code == 503


@pytest.mark.parametrize("path,body", WRITE_ENDPOINTS)
def test_valid_token_passes_authentication(path, body):
    # The handler may still fail later (unknown run/token) but never on authentication.
    assert lenient.post(path, json=body, headers=GOOD).status_code not in (401, 503)


class _FakeSeraj:
    def __init__(self, *a, **k):
        self.last_provider_used = None
        self.last_model_used = None

    def chat_turn(self, **kwargs):
        return "ok"


@pytest.fixture
def chat(monkeypatch):
    import seraj_llm_service
    monkeypatch.setattr(seraj_llm_service, "SerajLLMService", _FakeSeraj)
    session = SerajSessionManager.get_instance().get_session("auth-test-chat")
    session.clear_pending_action()
    yield session
    session.clear_pending_action()


CHAT_BODY = {"message": "مرحبا", "chat_id": "auth-test-chat", "company_id": 1,
             "company_name": "x", "operation_id": "op_auth_test"}


def test_chat_without_pending_write_needs_no_token(chat):
    assert client.post("/api/seraj/chat", json=CHAT_BODY).status_code != 401


def test_chat_with_pending_write_requires_token(chat):
    chat.pending_action = {"type": "delete", "plan_id": "plan_1_deadbeef"}
    assert client.post("/api/seraj/chat", json=CHAT_BODY).status_code == 401
    assert client.post("/api/seraj/chat", json=CHAT_BODY, headers=BAD).status_code == 401
    assert lenient.post("/api/seraj/chat", json=CHAT_BODY, headers=GOOD).status_code not in (401, 503)
