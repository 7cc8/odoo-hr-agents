"""
اختبارات خدمة وبوابة خطابات الإنذار والمساءلات التأديبية (Phase 23 - WarningService & Gateway Tests)
==================================================================================================
تختبر:
1. ضوابط المادة 66 ومستويات الإنذار.
2. احتساب الأجر اليومي للموظف.
3. فرض سقف الخصم الصارم للمادة 71 (5 أيام كحد أقصى للمخالفة الواحدة) ورفض التجاوز.
4. رصد تقادم المخالفة للمادة 70 (أكثر من 30 يوماً).
5. مبدأ التحقق المزدوج Four-Eyes ورفض الحفظ بدون "تأكيد".
6. استدعاء بوابة الكتابة والتحقق المستقل بعد الحفظ (Readback Verification).
7. عزل النماذج وحظر الحذف في بوابة الإنذارات.
"""

import os
import json
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from warning_service import (
    WarningService,
    WARNING_LEVELS,
    WarningDryRunResult,
    WarningApplyResult,
)
from odoo_warning_write_gateway import (
    OdooWarningWriteGateway,
    WarningEnvironmentGuardError,
    WarningWriteGatewayError,
    WARNING_LETTER_MODEL,
)


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_employees.return_value = [
        {
            "id": 201,
            "name": "عبدالله فهد السبيعي",
            "identification_id": "1087654321",
            "job_id": [15, "مدير مبيعات"],
            "department_id": [25, "إدارة المبيعات والتسويق"],
            "country_id": [1, "Saudi Arabia"],
        },
        {
            "id": 202,
            "name": "كريم عبدالحميد",
            "identification_id": "2387654321",
            "job_id": [16, "مندوب مبيعات ميداني"],
            "department_id": [25, "إدارة المبيعات والتسويق"],
            "country_id": [2, "Egypt"],
        },
    ]
    repo.get_contracts.return_value = [
        {
            "id": 601,
            "employee_id": 201,
            "state": "open",
            "wage": 15000.0,  # daily = 500.0 SAR
        },
        {
            "id": 602,
            "employee_id": 202,
            "state": "open",
            "wage": 6000.0,   # daily = 200.0 SAR
        },
    ]
    repo.get_warning_types.return_value = [
        {"id": 1, "name": "لفت نظر كتابي"},
        {"id": 2, "name": "إنذار كتابي أول"},
        {"id": 3, "name": "إنذار كتابي ثانٍ مع خصم"},
        {"id": 4, "name": "إنذار نهائي بالفصل من العمل"},
    ]
    return repo


@pytest.fixture
def mock_gateway():
    gateway = MagicMock(spec=OdooWarningWriteGateway)
    gateway.create_warning_letter.return_value = 9901
    gateway.read_warning_letter.return_value = {
        "id": 9901,
        "name": "WARN-2026-201-TEST1",
        "employee_id": 201,
        "warning_type_id": 2,
        "state": "draft",
        "has_deduction": False,
        "date_sent": "2026-10-06",
    }
    return gateway


def test_supported_warning_levels():
    assert "notice" in WARNING_LEVELS
    assert "first_warning" in WARNING_LEVELS
    assert "second_warning" in WARNING_LEVELS
    assert "final_warning" in WARNING_LEVELS


def test_daily_wage_calculation(mock_repo, mock_gateway):
    service = WarningService(repo=mock_repo, gateway=mock_gateway)
    # 15,000 / 30 = 500
    assert service.get_employee_daily_wage(201) == 500.0
    # 6,000 / 30 = 200
    assert service.get_employee_daily_wage(202) == 200.0


def test_dry_run_first_warning_no_deduction(mock_repo, mock_gateway):
    service = WarningService(repo=mock_repo, gateway=mock_gateway)
    res = service.dry_run_warning(
        employee_id=201,
        warning_level="first_warning",
        violation_description="التأخر المتكرر عن مواعيد العمل الرسمية بدون عذر مقبول",
    )
    assert res.is_valid is True
    assert res.employee_name == "عبدالله فهد السبيعي"
    assert res.is_saudi is True
    assert res.daily_wage == 500.0
    assert res.has_deduction is False
    assert res.approval_token != ""
    assert res.reference_code.startswith("WARN-")


def test_dry_run_article_71_valid_deduction(mock_repo, mock_gateway):
    service = WarningService(repo=mock_repo, gateway=mock_gateway)
    res = service.dry_run_warning(
        employee_id=201,
        warning_level="second_warning",
        violation_description="الغياب بدون إذن لمدة يومين",
        has_deduction=True,
        deduction_days=2.0,
    )
    assert res.is_valid is True
    assert res.has_deduction is True
    assert res.deduction_days == 2.0
    # 2 days * 500 = 1000 SAR
    assert res.deduction_amount == 1000.0
    assert any("المادة 71" in n for n in res.legal_notes)


def test_dry_run_article_71_exceeding_ceiling_rejected(mock_repo, mock_gateway):
    service = WarningService(repo=mock_repo, gateway=mock_gateway)
    # محاولة خصم 7 أيام (أعلى من سقف الـ 5 أيام النظامي للمادة 71)
    res = service.dry_run_warning(
        employee_id=201,
        warning_level="second_warning",
        violation_description="مخالفة جسيمة",
        has_deduction=True,
        deduction_days=7.0,
    )
    assert res.is_valid is False
    assert len(res.errors) > 0
    assert any("المادة 71" in err for err in res.errors)


def test_dry_run_article_70_statute_of_limitations_warning(mock_repo, mock_gateway):
    service = WarningService(repo=mock_repo, gateway=mock_gateway)
    old_date = (date.today() - timedelta(days=45)).isoformat()
    res = service.dry_run_warning(
        employee_id=201,
        warning_level="first_warning",
        violation_description="واقعة قديمة",
        violation_date=old_date,
    )
    # لا يمنع الإنشاء كلياً ولكن يضيف تنبيهاً قانونياً حرجاً بسقوط الحق
    assert any("المادة 70" in n for n in res.legal_notes)


def test_apply_warning_four_eyes_rejection_without_confirmation(mock_repo, mock_gateway):
    service = WarningService(repo=mock_repo, gateway=mock_gateway)
    dry_run = service.dry_run_warning(employee_id=201, warning_level="first_warning")
    assert dry_run.is_valid is True

    result = service.apply_warning(
        approval_token=dry_run.approval_token,
        user_confirmation_text="نعم اعتمد",
    )
    assert result.is_success is False
    assert result.state == "rejected"
    assert "تأكيد" in result.message_ar
    mock_gateway.create_warning_letter.assert_not_called()


def test_apply_warning_success_with_readback_and_html(mock_repo, mock_gateway):
    service = WarningService(repo=mock_repo, gateway=mock_gateway)
    dry_run = service.dry_run_warning(
        employee_id=202,
        warning_level="second_warning",
        violation_description="عدم تسليم العهدة في الموعد المحدد",
        has_deduction=True,
        deduction_days=1.0,
    )
    assert dry_run.is_valid is True

    result = service.apply_warning(
        approval_token=dry_run.approval_token,
        user_confirmation_text="تأكيد",
        executor="hr_specialist",
    )
    assert result.is_success is True
    assert result.warning_letter_id == 9901
    assert result.readback_data is not None
    assert result.html_path is not None
    assert os.path.exists(result.html_path)

    mock_gateway.create_warning_letter.assert_called_once()
    call_args = mock_gateway.create_warning_letter.call_args[0][0]
    assert call_args["employee_id"] == 202
    assert call_args["has_deduction"] is True
    assert call_args["deduction_amount"] == 200.0  # 1 day * 200 SAR


def test_warning_gateway_guards_and_no_unlink():
    mock_common = MagicMock()
    mock_common.authenticate.return_value = 5
    mock_models = MagicMock()

    gw = OdooWarningWriteGateway(
        url="https://fake.odoo.com",
        db="odooprosys-hr19-main-37916265",
        username="admin",
        password="pwd",
        common=mock_common,
        models=mock_models,
    )

    # 1. منع unlink
    with pytest.raises(WarningWriteGatewayError) as exc_info:
        gw._call(WARNING_LETTER_MODEL, "unlink", [[9901]])
    assert "محظورة قطعياً" in str(exc_info.value)

    # 2. منع النماذج غير المصرح بها
    with pytest.raises(WarningWriteGatewayError) as exc_info:
        gw._call("res.users", "create", [{"name": "fake"}])
    assert "غير مصرح به في بوابة الإنذارات" in str(exc_info.value)
