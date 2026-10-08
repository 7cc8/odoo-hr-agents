"""
اختبارات خدمة إدارة الإجازات ونظام العمل السعودي
(Tests for Leave Service and Odoo Leave Write Gateway)
"""

import pytest
from unittest.mock import MagicMock, patch
import os
import tempfile
import json
from datetime import date, timedelta

from leave_service import (
    LeaveService,
    LeaveTypeInfo,
    EmployeeLeaveSummary,
    LeaveDryRunResult,
    LeaveExecutionResult
)
from odoo_leave_write_gateway import (
    OdooLeaveWriteGateway,
    LeaveEnvironmentGuardError,
    LeaveWriteGatewayError
)
from saudi_labor_law_rules import OccasionLeaveType


@pytest.fixture
def mock_readonly_repo():
    repo = MagicMock()
    # أنماط بيانات الإجازات
    repo.get_leave_types.return_value = [
        {"id": 1, "name": "Paid Time Off", "request_unit": "day", "requires_allocation": True, "active": True},
        {"id": 2, "name": "Sick Time Off", "request_unit": "day", "requires_allocation": False, "active": True},
        {"id": 10, "name": "Marriage Leave", "request_unit": "day", "requires_allocation": False, "active": True},
        {"id": 11, "name": "Maternity Leave", "request_unit": "day", "requires_allocation": False, "active": True},
    ]
    # بيانات موظف تجريبي (خدمة أقل من 5 سنوات)
    repo.get_employee.return_value = {
        "id": 100,
        "name": "أحمد الشمري",
        "department_id": [2, "الموارد البشرية"],
        "gender": "male",
        "create_date": "2024-01-01 10:00:00",
        "active": True
    }
    repo.get_employee_allocations.return_value = [
        {"id": 1, "name": "Annual Allocation", "number_of_days": 21.0, "state": "validate"}
    ]
    repo.get_employee_leaves.return_value = [
        {"id": 5, "name": "إجازة سابقة", "number_of_days": 5.0, "state": "validate"}
    ]
    return repo


@pytest.fixture
def mock_write_gateway():
    gw = MagicMock()
    gw.create_leave.return_value = 501
    gw.read_leave.return_value = {
        "id": 501,
        "employee_id": [100, "أحمد الشمري"],
        "holiday_status_id": [1, "Paid Time Off"],
        "number_of_days": 4.0,
        "state": "confirm"
    }
    return gw


@pytest.fixture
def temp_audit_log(tmp_path):
    return str(tmp_path / "test_leave_audit.jsonl")


# =============================================================================
# 1. اختبارات استعلام الأنواع والأرصدة (Summary & Types)
# =============================================================================

def test_get_leave_types(mock_readonly_repo):
    service = LeaveService(readonly_repo=mock_readonly_repo)
    types = service.get_leave_types()
    assert len(types) == 4
    assert types[0].name == "Paid Time Off"
    assert types[0].requires_allocation is True


def test_get_employee_leave_summary_junior(mock_readonly_repo):
    """موظف خدمته أقل من 5 سنوات: استحقاقه السنوي 21 يوماً (المادة 109)"""
    service = LeaveService(readonly_repo=mock_readonly_repo)
    summary = service.get_employee_leave_summary(100)
    
    assert summary.employee_id == 100
    assert summary.statutory_annual_entitlement == 21
    assert summary.allocated_days == 21.0
    assert summary.consumed_days == 5.0
    assert summary.remaining_days == 16.0


def test_get_employee_leave_summary_senior(mock_readonly_repo):
    """موظف خدمته أكثر من 5 سنوات: استحقاقه السنوي 30 يوماً (المادة 109)"""
    mock_readonly_repo.get_employee.return_value = {
        "id": 200,
        "name": "سعد الخالدي",
        "department_id": [1, "الإدارة"],
        "gender": "male",
        "create_date": "2018-01-01 10:00:00",  # أكثر من 6 سنوات خدمة
        "active": True
    }
    mock_readonly_repo.get_employee_allocations.return_value = []
    mock_readonly_repo.get_employee_leaves.return_value = []
    
    service = LeaveService(readonly_repo=mock_readonly_repo)
    summary = service.get_employee_leave_summary(200)
    
    assert summary.statutory_annual_entitlement == 30
    assert summary.remaining_days == 30.0  # الرصيد المتاح اعتمد الاستحقاق السنوي 30 يوماً


# =============================================================================
# 2. اختبارات التحقق المسبق (Dry Run Validation)
# =============================================================================

def test_dry_run_valid_annual_leave(mock_readonly_repo):
    """طلب إجازة سنوية سليم برصيد متاح"""
    service = LeaveService(readonly_repo=mock_readonly_repo)
    res = service.dry_run_leave_request(
        employee_id=100,
        holiday_status_id=1,
        date_from="2026-10-10",
        date_to="2026-10-13",  # 4 أيام
        reason="إجازة اعتيادية"
    )
    assert res.is_valid is True
    assert res.number_of_days == 4.0
    assert res.balance_before == 16.0
    assert res.balance_after == 12.0
    assert "المادة 109" in res.statutory_article
    assert res.approval_token.startswith("LEAVE-")
    assert res.can_proceed is True


def test_dry_run_inverted_dates_fails(mock_readonly_repo):
    """تاريخ النهاية يسبق البداية يرفض فوراً"""
    service = LeaveService(readonly_repo=mock_readonly_repo)
    res = service.dry_run_leave_request(
        employee_id=100,
        holiday_status_id=1,
        date_from="2026-10-20",
        date_to="2026-10-10",
        reason="خطأ تواريخ"
    )
    assert res.is_valid is False
    assert len(res.errors) > 0
    assert "يسبق تاريخ البداية" in res.errors[0]
    assert res.can_proceed is False


def test_dry_run_occasion_leave_1446h_caps(mock_readonly_repo):
    """إجازة مناسبة (وفاة أخ/أخت - تعديل 1446هـ: 3 أيام)"""
    service = LeaveService(readonly_repo=mock_readonly_repo)
    # طلب 5 أيام مع أن الاستحقاق 3 أيام
    res = service.dry_run_leave_request(
        employee_id=100,
        holiday_status_id=10,
        date_from="2026-10-10",
        date_to="2026-10-14",  # 5 أيام
        occasion_type=OccasionLeaveType.DEATH_SIBLING
    )
    assert res.is_valid is True
    assert "المادة 113" in res.statutory_article
    assert len(res.warnings) > 0
    assert "تتجاوز الاستحقاق النظامي" in res.warnings[0]


def test_dry_run_maternity_leave_gender_check(mock_readonly_repo):
    """إجازة الوضع ترفض للموظف الذكر بموجب المادة 116"""
    service = LeaveService(readonly_repo=mock_readonly_repo)
    res = service.dry_run_leave_request(
        employee_id=100,  # gender = male
        holiday_status_id=11,
        date_from="2026-10-10",
        date_to="2026-12-10",
        reason="إجازة وضع"
    )
    assert res.is_valid is False
    assert any("المادة 116" in e for e in res.errors)


# =============================================================================
# 3. اختبارات اعتماد وتنفيذ طلب الإجازة (Apply & Four-Eyes Principle)
# =============================================================================

def test_apply_leave_requires_confirmation_keyword(mock_readonly_repo, mock_write_gateway, temp_audit_log):
    """فشل التنفيذ بدون كلمة 'تأكيد' صريحة (مبدأ العينين الأربع)"""
    service = LeaveService(
        readonly_repo=mock_readonly_repo,
        write_gateway=mock_write_gateway,
        audit_log_path=temp_audit_log
    )
    # 1. تجهيز الطلب والحصول على التوكن
    dry_res = service.dry_run_leave_request(100, 1, "2026-10-10", "2026-10-13")
    token = dry_res.approval_token

    # 2. محاولة التنفيذ بنص عشوائي مثل 'نعم' أو 'موافق' بدلاً من 'تأكيد'
    exec_res = service.apply_leave_request(approval_token=token, user_confirmation_text="موافق")
    assert exec_res.success is False
    assert "يتطلب تنفيذ طلب الإجازة كلمة 'تأكيد'" in exec_res.message_ar
    assert mock_write_gateway.create_leave.call_count == 0


def test_apply_leave_success_with_confirmation(mock_readonly_repo, mock_write_gateway, temp_audit_log):
    """نجاح التنفيذ بكلمة 'تأكيد' مع قراءة تحقق وسجل تدقيق"""
    service = LeaveService(
        readonly_repo=mock_readonly_repo,
        write_gateway=mock_write_gateway,
        audit_log_path=temp_audit_log
    )
    dry_res = service.dry_run_leave_request(100, 1, "2026-10-10", "2026-10-13")
    token = dry_res.approval_token

    exec_res = service.apply_leave_request(approval_token=token, user_confirmation_text="تأكيد")
    assert exec_res.success is True
    assert exec_res.leave_id == 501
    assert exec_res.readback_verified is True
    assert exec_res.audit_logged is True
    assert mock_write_gateway.create_leave.call_count == 1

    # التحقق من وجود سجل التدقيق في الملف
    assert os.path.exists(temp_audit_log)
    with open(temp_audit_log, "r", encoding="utf-8") as f:
        line = f.readline()
        data = json.loads(line)
        assert data["leave_id"] == 501
        assert data["employee_id"] == 100
        assert data["readback_verified"] is True


# =============================================================================
# 4. اختبارات حارس البيئة وبوابة كتابة الإجازات (OdooLeaveWriteGateway)
# =============================================================================

def test_leave_write_gateway_environment_guard():
    """حظر قاعدة بيانات إنتاجية غير مصرح بها"""
    with pytest.raises(LeaveEnvironmentGuardError) as exc_info:
        OdooLeaveWriteGateway(
            url="https://odoo.example.com",
            db="production_db_live",
            login="admin",
            password="key"
        )
    assert "حارس البيئة" in str(exc_info.value)


def test_leave_write_gateway_model_and_method_restrictions():
    """حظر نماذج وإجراءات غير مسموحة"""
    with patch("xmlrpc.client.ServerProxy") as mock_proxy:
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 2
        mock_common.version.return_value = {"server_version": "17.0"}
        
        mock_models = MagicMock()
        mock_proxy.side_effect = [mock_common, mock_models]
        
        gw = OdooLeaveWriteGateway(
            url="https://odoo.example.com",
            db="odooprosys-hr19-main-37916265",
            login="admin",
            password="key",
            common=mock_common,
            models=mock_models
        )
        
        # حظر نموذج غير مصرح به
        with pytest.raises(LeaveWriteGatewayError):
            gw._call("res.partner", "create", [{}])

        # حظر ميثود غير مصرح به
        with pytest.raises(LeaveWriteGatewayError):
            gw._call("hr.leave", "unlink", [[1]])


# =============================================================================
# 5. اختبارات نقاط نهاية واجهة برمجة التطبيقات API (FastAPI Integration)
# =============================================================================

def test_api_leaves_endpoints(mock_readonly_repo, mock_write_gateway):
    from fastapi.testclient import TestClient
    from web_service import app
    import web_service

    # حقن الـ mocks داخل web_service
    test_service = LeaveService(readonly_repo=mock_readonly_repo, write_gateway=mock_write_gateway)
    web_service._global_leave_service = test_service

    client = TestClient(app)

    # 1. اختبار جلب الأنواع
    resp_types = client.get("/api/leaves/types")
    assert resp_types.status_code == 200
    data_types = resp_types.json()
    assert data_types["status"] == "success"
    assert data_types["count"] == 4

    # 2. اختبار جلب ملخص ورصيد موظف
    resp_summary = client.get("/api/leaves/summary/100")
    assert resp_summary.status_code == 200
    data_summary = resp_summary.json()
    assert data_summary["status"] == "success"
    assert data_summary["summary"]["employee_name"] == "أحمد الشمري"
    assert data_summary["summary"]["statutory_annual_entitlement"] == 21

    # 3. اختبار الفحص الجاف Dry Run
    payload_dry = {
        "employee_id": 100,
        "holiday_status_id": 1,
        "request_date_from": "2026-10-15",
        "request_date_to": "2026-10-18",
        "reason": "إجازة اعتيادية"
    }
    resp_dry = client.post("/api/leaves/dry-run", json=payload_dry)
    assert resp_dry.status_code == 200
    data_dry = resp_dry.json()
    assert data_dry["status"] == "success"
    assert data_dry["result"]["is_valid"] is True
    token = data_dry["result"]["approval_token"]
    assert token.startswith("LEAVE-")

    # 4. اختبار التطبيق بدون توكن أمان (401 Unauthorized)
    resp_apply_no_auth = client.post("/api/leaves/apply", json={"approval_token": token, "confirmation_text": "تأكيد"})
    assert resp_apply_no_auth.status_code == 401

    # 5. اختبار التطبيق مع توكن الأمان وكلمة 'تأكيد'
    headers = {"X-API-Key": web_service.WRITE_API_TOKEN}
    resp_apply = client.post(
        "/api/leaves/apply",
        json={"approval_token": token, "confirmation_text": "تأكيد"},
        headers=headers
    )
    assert resp_apply.status_code == 200
    data_apply = resp_apply.json()
    assert data_apply["status"] == "success"
    assert data_apply["leave_id"] == 501

