import os

from fastapi.testclient import TestClient

from web_service import app


client = TestClient(app)


def test_dashboard_never_embeds_write_token(monkeypatch):
    monkeypatch.setenv("WRITE_API_TOKEN", "test-secret-that-must-not-leak")
    response = client.get("/")
    assert response.status_code == 200
    assert "test-secret-that-must-not-leak" not in response.text
    assert 'name="api-token"' not in response.text


def test_settings_mutation_requires_authentication(monkeypatch):
    monkeypatch.setenv("WRITE_API_TOKEN", "test-secret")
    response = client.post(
        "/api/settings/llm",
        json={"mode": "auto", "active_provider": "local"},
    )
    assert response.status_code == 401


def test_settings_mutation_accepts_configured_secret(monkeypatch):
    monkeypatch.setenv("WRITE_API_TOKEN", "test-secret")
    response = client.post(
        "/api/settings/llm",
        headers={"X-API-Key": "test-secret"},
        json={"mode": "auto", "active_provider": "local"},
    )
    assert response.status_code == 200


def test_template_catalog_is_allowlisted():
    response = client.get("/api/templates/catalog")
    assert response.status_code == 200
    entries = response.json()["templates"]
    assert any(item["template_type"] == "master" for item in entries)
    assert any(item["template_type"] == "modular" for item in entries)
    assert all("path" not in item for item in entries)


def test_approval_rejects_artifact_path_outside_output(monkeypatch):
    monkeypatch.setenv("WRITE_API_TOKEN", "test-secret")
    response = client.post(
        "/api/approve",
        headers={"X-API-Key": "test-secret"},
        json={
            "report_path": "C:/Windows/win.ini",
            "approved_by": "tester",
            "rows": [2],
        },
    )
    assert response.status_code == 400
    assert "غير مسموح" in response.json()["detail"]

