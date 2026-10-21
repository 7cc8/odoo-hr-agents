"""Laya (laya_service / laya_neural_consultant) was removed. Guard against it creeping back.

The scan ignores third-party tooling folders and a short allow-list of files that
legitimately keep the word (explained next to each entry).
"""
import inspect
import os
import re

import agent_events_service
from agent_events_service import AGENTS_REGISTRY, AgentEventsService
from seraj_llm_service import SerajLLMService
from seraj_session_manager import ConversationSession

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", ".claude", ".gitnexus", "graphify-out", "__pycache__", "node_modules", "venv", ".venv", "logs", "output", "approvals"}
TEXT_EXT = {".py", ".md", ".html", ".bat", ".txt", ".json", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".example"}

# Not "Layan" (a first name) and not Arabic words that merely contain the letters (e.g. الولايات).
LAYA_RE = re.compile(r"(?<![A-Za-z])laya(?![A-Za-z])|(?<![\u0621-\u064A])لايا(?![\u0621-\u064A])", re.IGNORECASE)

ALLOWED = {
    # Reads the historical audit log of the removed engine so old audit records stay visible.
    "sijil_audit_service.py",
    # Regression guard: the Laya menu button must not come back.
    os.path.join("tests", "test_telegram_bot.py"),
    # Recorded output of a past live Telegram run (historical data, not code).
    os.path.join("tests", "live_telegram_results.json"),
    # This file.
    os.path.join("tests", "test_no_laya_leftovers.py"),
}


def _project_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext in TEXT_EXT:
                path = os.path.join(dirpath, name)
                if os.path.getsize(path) < 3_000_000:
                    yield path


def test_no_references_to_laya_in_project_files():
    offenders = []
    for path in _project_files():
        rel = os.path.relpath(path, ROOT)
        if rel in ALLOWED:
            continue
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for n, line in enumerate(fh, 1):
                if LAYA_RE.search(line):
                    offenders.append(f"{rel}:{n}: {line.strip()[:100]}")
    assert not offenders, "Laya references found:\n" + "\n".join(offenders[:25])


def test_laya_modules_are_not_importable():
    for name in ("laya_service", "laya_neural_consultant"):
        try:
            __import__(name)
        except ImportError:
            continue
        raise AssertionError(f"{name} is importable again")


def test_event_service_has_no_laya_fields_and_eight_agents():
    for fn in (AgentEventsService.emit_event, getattr(AgentEventsService, "emit", AgentEventsService.emit_event)):
        assert "laya_used" not in inspect.signature(fn).parameters
    assert "laya" not in AGENTS_REGISTRY
    assert len(AGENTS_REGISTRY) == 8


def test_system_prompt_is_coherent_without_laya():
    svc = SerajLLMService(api_key="sk-or-test")
    session = ConversationSession(chat_id="prompt-test")
    prompt = svc._build_system_prompt(session, "خالد")
    assert not LAYA_RE.search(prompt)

    sections = prompt.split("مسؤولياتك الصريحة كـ «سراج»:")[1].split("مسؤولية وكيل «فاحص»")[0]
    assert [int(n) for n in re.findall(r"^(\d+)\. ", sections, re.M)] == [1, 2, 3, 4]

    rules = prompt.split("قواعد العمل والاستعلام الإلزامية الصارمة:")[1]
    assert [int(n) for n in re.findall(r"^(\d+)\. ", rules, re.M)] == list(range(1, 11))


def test_chat_turn_and_prompt_builders_do_not_accept_laya_decision():
    for fn in (SerajLLMService.chat_turn, SerajLLMService._build_system_prompt, SerajLLMService.generate_grounded_response):
        assert "laya_decision" not in inspect.signature(fn).parameters
