"""Test-wide settings.

The write-token tests used to rely on whatever WRITE_API_TOKEN the developer had in .env (which, following
the old CHAT_SETUP.md, was the value published in this repository). The server now refuses published values,
so the suite fixes its own token instead of depending on a developer's environment.
"""
from __future__ import annotations

import importlib
import os
import shutil
import tempfile
from pathlib import Path
import pytest

TEST_WRITE_TOKEN = "unit-test-write-token"

# Must run before web_service / telegram_bot are imported: both read the variable at import time, and
# load_dotenv() never overrides an existing variable.
os.environ["WRITE_API_TOKEN"] = TEST_WRITE_TOKEN


@pytest.fixture(autouse=True, scope="session")
def readonly_odoo_network_during_tests():
    """Real XML-RPC can read. Exercise mutations only through a test gateway."""
    import xmlrpc.client
    original = xmlrpc.client.Transport.request
    reads = {"read", "search", "search_read", "search_count", "read_group", "fields_get",
             "name_search", "name_get", "check_access_rights", "default_get", "get_metadata"}

    def guard(transport, host, handler, body, verbose=False):
        if "/xmlrpc" in handler:
            params, method = xmlrpc.client.loads(body)
            if method in {"execute_kw", "execute"}:
                if len(params) < 5 or params[4] not in reads:
                    pytest.fail("Test attempted a real Odoo mutation. Inject a test gateway.")
            elif method not in {"version", "authenticate", "login"}:
                pytest.fail("Unexpected Odoo RPC in test.")
        return original(transport, host, handler, body, verbose)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(xmlrpc.client.Transport, "request", guard)
        yield


@pytest.fixture(autouse=True, scope="session")
def isolate_test_logs():
    """
    عزل بيئة تشغيل الاختبارات ومنع تلوث سجلات النظام الحية logs/.
    يوجه كافة السجلات والدفاتر اللاتراجعية إلى مجلد مؤقت منعزل أثناء تشغيل الاختبارات.
    """
    temp_dir = tempfile.TemporaryDirectory()
    temp_path = Path(temp_dir.name)
    (temp_path / "agent_events").mkdir(parents=True, exist_ok=True)
    (temp_path / "pending_leave_approvals.json").write_text("{}", encoding="utf-8")

    os.environ["TEST_LOGS_DIR"] = str(temp_path)

    modules_to_patch = [
        ("agent_events_service", "LOGS_DIR", temp_path),
        ("agent_events_service", "AGENT_OPS_LOG_FILE", temp_path / "agent_operations_log.jsonl"),
        ("sijil_audit_service", "LOGS_DIR", temp_path),
        ("katib_service", "AUDIT_LOG_DIR", temp_path),
        ("katib_service", "AUDIT_LOG_FILE", temp_path / "writer_audit_log.jsonl"),
        ("katib_service", "DELETION_AUDIT_LOG_FILE", temp_path / "deletion_audit_log.jsonl"),
        ("warning_service", "WARNING_AUDIT_LOG_FILE", str(temp_path / "warning_audit_log.jsonl")),
        ("leave_service", "AUDIT_LOG_FILE", str(temp_path / "leave_audit_log.jsonl")),
        ("leave_service", "PENDING_APPROVALS_FILE", str(temp_path / "pending_leave_approvals.json")),
        ("attendance_service", "ATTENDANCE_AUDIT_LOG_FILE", str(temp_path / "attendance_audit_log.jsonl")),
        ("letter_service", "LETTER_AUDIT_LOG_FILE", str(temp_path / "letter_audit_log.jsonl")),
        ("expense_service", "EXPENSE_AUDIT_LOG_FILE", str(temp_path / "expense_audit_log.jsonl")),
        ("contract_service", "CONTRACT_AUDIT_LOG_FILE", str(temp_path / "contract_audit_log.jsonl")),
        ("disciplinary_service", "DISCIPLINARY_AUDIT_LOG_FILE", str(temp_path / "disciplinary_audit_log.jsonl")),
        ("eos_service", "EOS_AUDIT_LOG_FILE", str(temp_path / "eos_audit_log.jsonl")),
        ("loan_service", "LOAN_AUDIT_LOG_FILE", str(temp_path / "loan_audit_log.jsonl")),
        ("gr_service", "GR_AUDIT_LOG_FILE", str(temp_path / "gr_audit_log.jsonl")),
        ("appraisal_service", "APPRAISAL_AUDIT_LOG_FILE", str(temp_path / "appraisal_audit_log.jsonl")),
        ("payroll_service", "PAYROLL_AUDIT_LOG_FILE", str(temp_path / "payroll_audit_log.jsonl")),
        ("recruitment_service", "RECRUITMENT_AUDIT_LOG_FILE", str(temp_path / "recruitment_audit_log.jsonl")),
        ("document_expiry_service", "EXPIRY_AUDIT_LOG", str(temp_path / "expiry_monitor_log.jsonl")),
        ("agents.agent_events_service", "EVENTS_DIR", temp_path / "agent_events"),
    ]

    for mod_name, attr, val in modules_to_patch:
        try:
            mod = importlib.import_module(mod_name)
            setattr(mod, attr, val)
        except Exception:
            pass

    yield temp_path

    try:
        temp_dir.cleanup()
    except Exception:
        pass
