import hashlib
import json
from unittest.mock import Mock

import pytest

from api.routers import audit
from excel_template_validator import TEMPLATE_SPECS, _validate_row_by_domain


@pytest.fixture
def appraisal_fields():
    return {
        "emp_id": "1234567890",
        "emp_name": "موظف للاختبار",
        "year": "2026",
        "type": "سنوي",
        "manager": "مدير الاختبار",
        "rating": "جيد",
        "kpi_score": "80",
        "competency_score": "90",
        "total_score": "",
    }


def test_appraisal_scan_reports_missing_model_and_unmatched_employee(appraisal_fields):
    repo = Mock(supports_appraisal_import=False)
    repo.search_employee_candidates.return_value = [
        {"id": 17, "name": appraisal_fields["emp_name"], "identification_id": "0000000000"},
    ]
    status, code, reasons, _, ids = _validate_row_by_domain(
        "appraisal", appraisal_fields, TEMPLATE_SPECS["appraisal"], 3, repo, {},
    )
    assert status == "rejected"
    assert code == "appraisal_unavailable"
    assert len(reasons) == 2
    assert ids["employee_match_id"] is None


def test_appraisal_approval_uses_appraisal_gateway(appraisal_fields, tmp_path, monkeypatch):
    source = tmp_path / "appraisals.xlsx"
    source.write_bytes(b"verified workbook bytes")
    report_file = tmp_path / "dry_run_report.json"
    config = {"url": "https://odoo.example", "db": "stage", "username": "operator", "api_key": "fake"}
    report_file.write_text(json.dumps({
        "header": {
            "run_id": "test-run", "source_hash": hashlib.sha256(source.read_bytes()).hexdigest(),
            "upload_source_file": source.name, "upload_operation_id": "op_test",
            "upload_chat_id": "web_upload_test", "odoo_url": config["url"], "odoo_db": config["db"],
            "template_type": "appraisal",
        },
        "rows": [{
            "final_status": "accepted", "excel_row_number": 3, "row_hash": "test-row",
            "fields": {name: {"value": value} for name, value in appraisal_fields.items()},
            "resolved_ids": {"employee_match_id": 42},
        }],
    }), encoding="utf-8")
    repo = Mock(supports_appraisal_import=True)
    repo.search_employee_candidates.return_value = [{
        "id": 42, "name": appraisal_fields["emp_name"], "identification_id": appraisal_fields["emp_id"],
    }]
    service = Mock()
    service.get_operation.return_value = {"status": "completed"}
    gateway = Mock()
    gateway.create_appraisal_request.return_value = 73
    employee_writer = Mock(side_effect=AssertionError("Employee writer must not handle appraisals"))
    monkeypatch.setattr(audit.writer, "run_writer", employee_writer)
    monkeypatch.setattr(audit, "_get_upload_dir", lambda: tmp_path)
    monkeypatch.setattr(audit, "_get_readonly_repo_cls", lambda: lambda: repo)
    monkeypatch.setattr(audit, "get_active_odoo_config", lambda: config)
    monkeypatch.setattr(audit, "OdooAppraisalWriteGateway", Mock(return_value=gateway))

    payload = audit.AgentApprovalApiRequest(chat_id="web_upload_test", operation_id="op_test")
    response = audit._execute_excel_approval(payload, report_file, service, None)

    assert response["status"] == "success"
    assert response["created_count"] == 1
    assert response["template_type"] == "appraisal"
    assert gateway.create_appraisal_request.call_count == 1
    values = gateway.create_appraisal_request.call_args.kwargs
    assert values["employee_id"] == 42
    assert values["final_percentage"] == 83
    employee_writer.assert_not_called()
