"""The write token must not be a value this repository publishes."""
import os

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import web_service

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", ".claude", ".gitnexus", "__pycache__", "node_modules", "venv", ".venv", "logs", "output", "approvals", "scratch"}
PUBLISHED = "hr-write-secret-token"


def _request(token=None):
    headers = [(b"x-api-key", token.encode())] if token else []
    return Request({"type": "http", "headers": headers, "query_string": b"", "method": "POST", "path": "/x"})


@pytest.fixture
def server_token(monkeypatch):
    def set_token(value):
        monkeypatch.setenv("WRITE_API_TOKEN", value)
        monkeypatch.setattr(web_service, "WRITE_API_TOKEN", value)
    return set_token


@pytest.mark.parametrize("published", sorted(web_service.INSECURE_PUBLISHED_WRITE_TOKENS))
def test_published_values_are_refused_even_with_the_matching_header(server_token, published):
    server_token(published)
    for check in (web_service.verify_api_auth, web_service.verify_write_auth):
        with pytest.raises(HTTPException) as exc:
            check(_request(published))
        assert exc.value.status_code == 503
        assert "علناً" in exc.value.detail


def test_a_generated_token_works_and_a_wrong_one_does_not(server_token):
    server_token("k3Zq-very-long-random-value-0123456789")
    web_service.verify_api_auth(_request("k3Zq-very-long-random-value-0123456789"))
    with pytest.raises(HTTPException) as exc:
        web_service.verify_api_auth(_request(PUBLISHED))
    assert exc.value.status_code == 401


def test_unset_token_still_disables_writes(server_token):
    server_token("")
    with pytest.raises(HTTPException) as exc:
        web_service.verify_api_auth(_request("anything"))
    assert exc.value.status_code == 503


def test_the_published_value_appears_only_in_the_refusal_list():
    """No code, doc or script may ship it again (tests are excluded: they use their own token)."""
    offenders = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and d != "tests" and not d.startswith(".")]
        for name in filenames:
            if os.path.splitext(name)[1].lower() not in {".py", ".md", ".html", ".bat", ".json", ".txt", ".example", ".yml"}:
                continue
            if name.endswith(".patch"):
                continue
            path = os.path.join(dirpath, name)
            if os.path.getsize(path) > 3_000_000:
                continue
            with open(path, encoding="utf-8", errors="ignore") as fh:
                for n, line in enumerate(fh, 1):
                    if PUBLISHED in line:
                        offenders.append(f"{os.path.relpath(path, ROOT)}:{n}")
    assert offenders == ["web_service.py:" + offenders[0].split(":")[1]], offenders


def test_the_bot_has_no_built_in_token():
    import telegram_bot

    assert telegram_bot.WRITE_API_TOKEN == os.environ.get("WRITE_API_TOKEN", "")
    assert PUBLISHED not in open(telegram_bot.__file__, encoding="utf-8").read()
