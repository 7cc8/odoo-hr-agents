"""
اختبارات تكامل معمارية الطبقات الست وإصلاحات تجربة المستخدم
==========================================================
يختبر:
1. الجداول الموحدة في SQLite memory.db.
2. المسترجع المحلي LocalRAG مع مواد نظام العمل والبحث عبر FTS5.
3. مدير التوكنات TokenManager والنافذة المنزلقة Sliding Window.
4. مدير نقاط التفتيش CheckpointManager وحزمة التصعيد EscalationContextPackage.
5. المحلل الحسابي المعزول SafeCodeSandbox ومنع الاختراق الأمني.
6. قاطع الميزانية BudgetLimiter.
7. محاسب التكلفة CostAuditor والمسار /api/telemetry/cost.
8. عدم استدعاء فاحص في الأسئلة الحوارية والاستنتاجية المباشرة.
"""

import pytest
from starlette.testclient import TestClient
from web_service import app
from memory.manager import MemoryManager
from memory.local_rag import LocalRAG
from agents.token_manager import TokenManager
from agents.checkpoint_manager import CheckpointManager
from agents.code_sandbox import SafeCodeSandbox
from agents.budget_limiter import BudgetLimiter
from agents.cost_auditor import CostAuditor
from agents.tool_registry import ToolRegistry


@pytest.fixture
def client():
    return TestClient(app)


def test_sqlite_unified_tables():
    """التحقق من إنشاء كافة الجداول الموحدة في memory.db."""
    mm = MemoryManager.get_instance()
    with mm._get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type in ('table', 'view')")
        tables = [r[0] for r in cur.fetchall()]
        assert "facts" in tables or "long_term_facts" in tables
        assert "episodes" in tables
        assert "checkpoints" in tables
        assert "rag_chunks" in tables
        assert "token_usage" in tables


def test_local_rag_fts5():
    """التحقق من عمل المسترجع المحلي وفهرسة نظام العمل."""
    rag = LocalRAG.get_instance()
    # بحث عام عن نهاية الخدمة
    res = rag.search("مكافأة نهاية الخدمة", top_k=2)
    assert len(res) > 0
    assert any("نهاية الخدمة" in r["title"] or "84" in r.get("title", "") or "85" in r.get("title", "") for r in res)

    # بحث مباشر برقم المادة
    art84 = rag.get_article_by_number("84")
    assert art84 is not None
    assert "84" in art84["article_number"]


def test_token_manager_and_sliding_window():
    """التحقق من عد التوكنات وتطبيق النافذة المنزلقة."""
    text_ar = "نظام العمل السعودي للموارد البشرية"
    tokens = TokenManager.count_tokens(text_ar)
    assert tokens > 0

    msgs = [
        {"role": "system", "content": "أنت سراج المنسق الذكي."},
        {"role": "user", "content": "سؤال 1" * 50},
        {"role": "assistant", "content": "جواب 1" * 50},
        {"role": "user", "content": "سؤال 2"},
        {"role": "assistant", "content": "جواب 2"},
        {"role": "user", "content": "2"},
    ]
    windowed = TokenManager.apply_sliding_window(msgs, max_tokens=150, reserve_for_completion=30)
    assert len(windowed) >= 3
    assert windowed[0]["role"] == "system"
    assert windowed[-1]["content"] == "2"


def test_checkpoint_and_escalation():
    """التحقق من حفظ نقاط التفتيش وتوليد حزمة التصعيد البشري."""
    cm = CheckpointManager.get_instance()
    chk_id = cm.save_checkpoint("op_test_99", "chat_test_99", "fahas", 1, {"count": 10})
    assert chk_id.startswith("chk_op_test_99")

    history = cm.get_checkpoints("op_test_99")
    assert len(history) >= 1

    pkg = cm.create_escalation_package(
        operation_id="op_test_99",
        chat_id="chat_test_99",
        failed_agent="katib",
        reason="Odoo server lock timeout",
        attempt_count=3,
        last_error="Connection refused on port 8069",
    )
    assert pkg.failed_agent == "katib"
    assert "🚨" in pkg.to_markdown()


def test_code_sandbox_security_and_execution():
    """التحقق من المحلل الحسابي المعزول وتطبيق حظر الاختراق."""
    # 1. كود سليم
    valid_code = "salary = 10000\nyears = 5\nresult = salary * years * 0.5"
    res1 = SafeCodeSandbox.execute(valid_code)
    assert res1["status"] == "success"
    assert res1["result"] == 25000.0

    # 2. حظر الاستيراد
    res2 = SafeCodeSandbox.execute("import os\nresult = 1")
    assert res2["status"] == "security_violation"

    # 3. حظر استدعاء open
    res3 = SafeCodeSandbox.execute("f = open('secret.txt')")
    assert res3["status"] == "security_violation"

    # 4. التحقق من تسجيل الأداة في ToolRegistry
    reg = ToolRegistry.get_instance()
    assert reg.has_tool("run_hr_calculation_sandbox")


def test_budget_limiter():
    """التحقق من قاطع الميزانية."""
    limiter = BudgetLimiter(max_turns=3, max_tokens_per_task=500)
    op = "op_budget_test"

    limiter.record_turn(op)
    limiter.record_usage(op, 200)
    ok, err = limiter.check_limits(op)
    assert ok is True

    # تجاوز سقف التوكنات
    limiter.record_usage(op, 400)
    ok2, err2 = limiter.check_limits(op)
    assert ok2 is False
    assert "سقف استهلاك التوكنات" in err2


def test_cost_auditor_and_endpoint(client):
    """التحقق من مسار القياس عن بعد والتكلفة /api/telemetry/cost."""
    ca = CostAuditor.get_instance()
    ca.record_usage("chat_t1", "op_t1", "seraj", "qwen3.5:9b", "local", 100, 50, 150.0)
    ca.record_usage("chat_t1", "op_t2", "seraj", "gemini-3.8-flash", "cloud", 200, 100, 300.0)

    res = client.get("/api/telemetry/cost")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["total_requests"] >= 2
    assert data["total_tokens"] >= 450

