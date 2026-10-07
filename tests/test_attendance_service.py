"""
اختبارات خدمة الحضور وساعات العمل الإضافية ونظام العمل السعودي
(Tests for Attendance & Overtime Service)
"""

import pytest
from unittest.mock import MagicMock, patch
import os
import json
from datetime import datetime

from attendance_service import (
    AttendanceService,
    AttendanceSummaryResult,
    AttendanceDryRunResult,
    AttendanceExecutionResult,
)
from odoo_attendance_write_gateway import (
    OdooAttendanceWriteGateway,
    AttendanceEnvironmentGuardError,
    AttendanceWriteGatewayError,
)


@pytest.fixture
def mock_readonly_repo():
    repo = MagicMock()
    repo.get_employee.return_value = {
        "id": 100,
        "name": "فيصل العتيبي",
        "department_id": [3, "العمليات التشغيلية"],
        "sex": "male",
        "hiring_date": "2023-01-01",
        "active": True
    }
    # سجلات حضور تجريبية
    repo.get_employee_attendances.return_value = [
        {
            "id": 10,
            "employee_id": [100, "فيصل العتيبي"],
            "date": "2026-10-01",
            "check_in": "2026-10-01 08:00:00",
            "check_out": "2026-10-01 18:00:00",
            "worked_hours": 10.0,  # 8 عادية + 2 إضافية
        },
        {
            "id": 11,
            "employee_id": [100, "فيصل العتيبي"],
            "date": "2026-10-02",
            "check_in": "2026-10-02 08:00:00",
            "check_out": "2026-10-02 16:00:00",
            "worked_hours": 8.0,   # 8 عادية + 0 إضافية
        }
    ]
    repo.get_employee_current_attendance.return_value = None
    return repo


@pytest.fixture
def mock_write_gateway():
    gw = MagicMock()
    gw.check_in.return_value = 88
    gw.check_out.return_value = True
    gw.create_attendance_record.return_value = 99
    gw.read_attendance.return_value = {
        "id": 88,
        "employee_id": [100, "فيصل العتيبي"],
        "check_in": "2026-10-06 08:00:00",
        "check_out": False,
        "worked_hours": 0.0,
    }
    return gw


@pytest.fixture
def temp_audit_log(tmp_path):
    return str(tmp_path / "test_attendance_audit.jsonl")


# =============================================================================
# 1. اختبارات ملخص الحضور وحساب الأوفرتايم (المادتان 98 و 107)
# =============================================================================

def test_attendance_summary_standard_hours(mock_readonly_repo):
    """حساب ساعات العمل العادية والعمل الإضافي بالمعيار القياسي 8 ساعات (المادة 98)"""
    service = AttendanceService(readonly_repo=mock_readonly_repo)
    summary = service.get_attendance_summary(
        employee_id=100,
        is_ramadan=False,
        basic_wage=4800.0,
        gross_wage=7200.0
    )
    assert summary.employee_id == 100
    assert summary.total_days_worked == 2
    assert summary.total_worked_hours == 18.0
    assert summary.total_standard_hours == 16.0  # 8 + 8
    assert summary.total_overtime_hours == 2.0   # 10 - 8 = 2

    # أجر ساعة الأوفرتايم: Gross/240 + 50% Basic/240 = 30 + 10 = 40 ريال للساعة
    # لساعتين = 80 ريال
    assert summary.overtime_compensation_sar == 80.0
    assert "المواد 98 و 107" in summary.statutory_article


def test_attendance_summary_ramadan_hours(mock_readonly_repo):
    """تطبيق تخفيض ساعات العمل في رمضان للمسلمين إلى 6 ساعات يومياً (المادة 98)"""
    service = AttendanceService(readonly_repo=mock_readonly_repo)
    summary = service.get_attendance_summary(
        employee_id=100,
        is_ramadan=True,
        is_muslim=True,
        basic_wage=4800.0,
        gross_wage=7200.0
    )
    # اليوم الأول: 10 ساعات -> 6 عادية + 4 إضافية
    # اليوم الثاني: 8 ساعات -> 6 عادية + 2 إضافية
    # الإجمالي الإضافي: 6 ساعات
    assert summary.total_standard_hours == 12.0
    assert summary.total_overtime_hours == 6.0
    # 6 ساعات × 40 ريال = 240 ريال
    assert summary.overtime_compensation_sar == 240.0
    assert "رمضان 6 ساعات" in summary.statutory_explanation_ar


# =============================================================================
# 2. اختبارات الفحص التجريبي المسبق (Dry Run)
# =============================================================================

def test_dry_run_attendance_valid_overtime_and_rest_period(mock_readonly_repo):
    """فحص حركة دوام 10 ساعات مع التحقق من المادة 101 (فترات الراحة) والمادة 107"""
    service = AttendanceService(readonly_repo=mock_readonly_repo)
    res = service.dry_run_attendance_entry(
        employee_id=100,
        date_str="2026-10-06",
        check_in_str="2026-10-06 08:00:00",
        check_out_str="2026-10-06 18:00:00",
        basic_wage=4800.0,
        gross_wage=7200.0
    )
    assert res.is_valid is True
    assert res.worked_hours == 10.0
    assert res.standard_hours == 8.0
    assert res.overtime_hours == 2.0
    assert res.overtime_pay_sar == 80.0
    assert len(res.warnings) > 0
    assert "المادة 101" in res.warnings[0]  # أكثر من 5 ساعات متصلة
    assert res.approval_token.startswith("ATTEND-")
    assert res.can_proceed is True


def test_dry_run_attendance_inverted_times_fails(mock_readonly_repo):
    """فحص وقت الانصراف يسبق الحضور يُرفض فوراً"""
    service = AttendanceService(readonly_repo=mock_readonly_repo)
    res = service.dry_run_attendance_entry(
        employee_id=100,
        date_str="2026-10-06",
        check_in_str="2026-10-06 18:00:00",
        check_out_str="2026-10-06 08:00:00",
    )
    assert res.is_valid is False
    assert len(res.errors) > 0
    assert "يجب أن يكون بعد وقت الحضور" in res.errors[0]
    assert res.can_proceed is False


# =============================================================================
# 3. اختبارات تسجيل الحضور والانصراف الفوري (Check-In & Check-Out)
# =============================================================================

def test_check_in_enforces_confirmation(mock_readonly_repo, mock_write_gateway, temp_audit_log):
    """فشل تسجيل الحضور بدون كلمة 'تأكيد' صريحة"""
    service = AttendanceService(
        readonly_repo=mock_readonly_repo,
        write_gateway=mock_write_gateway,
        audit_log_path=temp_audit_log
    )
    res = service.record_check_in(employee_id=100, confirmation_text="سجل")
    assert res.success is False
    assert "يتطلب تسجيل الحضور كلمة 'تأكيد'" in res.message_ar
    assert mock_write_gateway.check_in.call_count == 0


def test_check_in_success_with_confirmation(mock_readonly_repo, mock_write_gateway, temp_audit_log):
    """نجاح تسجيل الحضور بكلمة 'تأكيد' وقراءة تحقق وسجل تدقيق"""
    service = AttendanceService(
        readonly_repo=mock_readonly_repo,
        write_gateway=mock_write_gateway,
        audit_log_path=temp_audit_log
    )
    res = service.record_check_in(employee_id=100, confirmation_text="تأكيد")
    assert res.success is True
    assert res.attendance_id == 88
    assert res.readback_verified is True
    assert res.audit_logged is True
    assert mock_write_gateway.check_in.call_count == 1


def test_check_in_blocks_duplicate_open_session(mock_readonly_repo, mock_write_gateway, temp_audit_log):
    """حظر تسجيل حضور جديد إذا كان للموظف تسجيل حضور مفتوح بالفعل"""
    mock_readonly_repo.get_employee_current_attendance.return_value = {
        "id": 77,
        "employee_id": [100, "فيصل"],
        "check_in": "2026-10-06 08:30:00",
        "check_out": False
    }
    service = AttendanceService(
        readonly_repo=mock_readonly_repo,
        write_gateway=mock_write_gateway,
        audit_log_path=temp_audit_log
    )
    res = service.record_check_in(employee_id=100, confirmation_text="تأكيد")
    assert res.success is False
    assert "مسجل حضور بالفعل ومفتوح" in res.message_ar
    assert mock_write_gateway.check_in.call_count == 0


def test_check_out_success(mock_readonly_repo, mock_write_gateway, temp_audit_log):
    """نجاح تسجيل الانصراف لسجل حضور مفتوح"""
    mock_readonly_repo.get_employee_current_attendance.return_value = {
        "id": 88,
        "employee_id": [100, "فيصل"],
        "check_in": "2026-10-06 08:00:00",
        "check_out": False
    }
    mock_write_gateway.read_attendance.return_value = {
        "id": 88,
        "employee_id": [100, "فيصل"],
        "check_in": "2026-10-06 08:00:00",
        "check_out": "2026-10-06 17:00:00",
        "worked_hours": 9.0
    }
    service = AttendanceService(
        readonly_repo=mock_readonly_repo,
        write_gateway=mock_write_gateway,
        audit_log_path=temp_audit_log
    )
    res = service.record_check_out(employee_id=100, confirmation_text="تأكيد")
    assert res.success is True
    assert res.attendance_id == 88
    assert res.worked_hours == 9.0
    assert res.overtime_hours == 1.0  # 9 - 8
    assert res.readback_verified is True
    assert mock_write_gateway.check_out.call_count == 1


# =============================================================================
# 4. اختبارات حارس البيئة وبوابة كتابة الحضور
# =============================================================================

def test_attendance_write_gateway_environment_guard():
    """حظر قواعد البيانات الإنتاجية غير المصرح بها"""
    with pytest.raises(AttendanceEnvironmentGuardError):
        OdooAttendanceWriteGateway(
            url="https://odoo.example.com",
            db="production_unauthorized",
            login="admin",
            password="key"
        )


def test_attendance_write_gateway_model_restrictions():
    """حظر استدعاء نماذج خارج hr.attendance"""
    with patch("xmlrpc.client.ServerProxy") as mock_proxy:
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 2
        mock_common.version.return_value = {"server_version": "17.0"}
        mock_models = MagicMock()
        mock_proxy.side_effect = [mock_common, mock_models]

        gw = OdooAttendanceWriteGateway(
            url="https://odoo.example.com",
            db="odooprosys-hr19-main-37916265",
            login="admin",
            password="key",
            common=mock_common,
            models=mock_models
        )
        with pytest.raises(AttendanceWriteGatewayError):
            gw._call("res.users", "create", [{}])


# =============================================================================
# 5. اختبارات نقاط نهاية واجهة API (FastAPI Integration)
# =============================================================================

def test_api_attendance_endpoints(mock_readonly_repo, mock_write_gateway):
    from fastapi.testclient import TestClient
    from web_service import app
    import web_service

    test_service = AttendanceService(readonly_repo=mock_readonly_repo, write_gateway=mock_write_gateway)
    web_service._global_attendance_service = test_service

    client = TestClient(app)

    # 1. اختبار استعلام الملخص والأوفرتايم
    resp_sum = client.get("/api/attendance/summary/100")
    assert resp_sum.status_code == 200
    data_sum = resp_sum.json()
    assert data_sum["status"] == "success"
    assert data_sum["summary"]["employee_name"] == "فيصل العتيبي"
    assert data_sum["summary"]["total_worked_hours"] == 18.0
    assert data_sum["summary"]["total_overtime_hours"] == 2.0

    # 2. اختبار الفحص التجريبي المسبق Dry Run
    payload_dry = {
        "employee_id": 100,
        "date": "2026-10-06",
        "check_in": "2026-10-06 08:00:00",
        "check_out": "2026-10-06 18:00:00",
        "basic_wage": 4800.0,
        "gross_wage": 7200.0,
    }
    resp_dry = client.post("/api/attendance/dry-run", json=payload_dry)
    assert resp_dry.status_code == 200
    data_dry = resp_dry.json()
    assert data_dry["status"] == "success"
    assert data_dry["result"]["overtime_hours"] == 2.0
    token = data_dry["result"]["approval_token"]
    assert token.startswith("ATTEND-")

    # 3. اختبار تسجيل الحضور الفوري Check-In (مع توكن وبكلمة 'تأكيد')
    headers = {"X-API-Key": web_service.WRITE_API_TOKEN}
    resp_cin = client.post(
        "/api/attendance/check-in",
        json={"employee_id": 100, "confirmation_text": "تأكيد"},
        headers=headers
    )
    assert resp_cin.status_code == 200
    data_cin = resp_cin.json()
    assert data_cin["status"] == "success"
    assert data_cin["action"] == "CHECK_IN"

