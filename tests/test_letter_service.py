"""
اختبارات وحدة وخدمة خطابات الموارد البشرية وشهادات الرواتب (Phase 22 - LetterService Tests)
========================================================================================
تختبر:
1. أنواع الخطابات المدعومة والتهيئة السليمة.
2. الكشف عن جنسية الموظف (سعودي مقابل وافد) والتوصيف الوظيفي.
3. حساب الراتب والبدلات وتضمينها أو حجبها حسب الطلب.
4. المعاينة الأولية (Dry-Run) وإصدار رمز الموافقة approval_token.
5. فرض مبدأ التحقق المزدوج Four-Eyes ورفض التنفيذ بدون "تأكيد" الصريحة.
6. استدعاء بوابة الكتابة وحفظ السجل في Odoo (approval.request).
7. التحقق المستقل بعد الكتابة (Readback Verification).
8. توليد المستندات HTML ورموز التحقق الرقمية وسجل التدقيق.
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch

from letter_service import (
    LetterService,
    SUPPORTED_LETTER_TYPES,
    LetterSalaryDetails,
    LetterDryRunResult,
    LetterApplyResult,
)
from odoo_letter_write_gateway import OdooLetterWriteGateway, LetterWriteGatewayError


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_employees.return_value = [
        {
            "id": 101,
            "name": "سعد بن خالد الدوسري",
            "identification_id": "1098765432",
            "job_id": [11, "مهندس برمجيات أول"],
            "department_id": [21, "إدارة تقنية المعلومات"],
            "hiring_date": "2022-01-15",
            "country_id": [1, "Saudi Arabia"],
        },
        {
            "id": 102,
            "name": "محمود أحمد رضوان",
            "identification_id": "2498765432",
            "job_id": [12, "أخصائي شبكات"],
            "department_id": [21, "إدارة تقنية المعلومات"],
            "hiring_date": "2023-05-01",
            "country_id": [2, "Egypt"],
        },
    ]
    repo.get_contracts.return_value = [
        {
            "id": 501,
            "employee_id": 101,
            "state": "open",
            "wage": 12000.0,
            "housing_allowance": 3000.0,
            "transportation_allowance": 1200.0,
            "other_allowance": 800.0,
        },
        {
            "id": 502,
            "employee_id": 102,
            "state": "open",
            "wage": 8000.0,
            "housing_allowance": 2000.0,
            "transportation_allowance": 800.0,
            "other_allowance": 0.0,
        },
    ]
    repo.get_approval_categories.return_value = [
        {"id": 3, "name": "General Approval", "has_amount": "optional", "has_date": "optional"},
        {"id": 4, "name": "Letters & Certificates", "has_amount": "no", "has_date": "no"},
    ]
    return repo


@pytest.fixture
def mock_gateway():
    gateway = MagicMock(spec=OdooLetterWriteGateway)
    gateway.create_letter_request.return_value = 8801
    gateway.read_letter_request.return_value = {
        "id": 8801,
        "name": "شهادة تعريف بالراتب - سعد بن خالد الدوسري",
        "request_status": "new",
        "request_employee_id": 101,
        "category_id": 3,
        "to": "إلى من يهمه الأمر",
        "purpose": "إصدار شهادة تعريف بالراتب للموظف",
        "letter_language": "arabic",
        "chamber_of_commerce_stamp": False,
    }
    return gateway


def test_supported_letter_types_count(mock_repo, mock_gateway):
    service = LetterService(repo=mock_repo, gateway=mock_gateway)
    types = service.get_supported_letter_types()
    assert len(types) >= 5
    ids = [t["id"] for t in types]
    assert "salary_certificate" in ids
    assert "employment_certificate" in ids
    assert "bank_letter" in ids
    assert "embassy_letter" in ids
    assert "chamber_certified" in ids


def test_dry_run_saudi_employee_salary_certificate(mock_repo, mock_gateway):
    service = LetterService(repo=mock_repo, gateway=mock_gateway)
    dry_run = service.dry_run_letter(
        employee_id=101,
        letter_type="salary_certificate",
        recipient="مصرف الراجحي",
        purpose="طلب تمويل شخصي",
        language="arabic",
        include_salary=True,
    )

    assert dry_run.is_valid is True
    assert dry_run.employee_name == "سعد بن خالد الدوسري"
    assert dry_run.is_saudi is True
    assert dry_run.nationality_text_ar == "مواطن سعودي"
    assert dry_run.identification_id == "1098765432"
    assert dry_run.salary_details.basic_wage == 12000.0
    assert dry_run.salary_details.housing_allowance == 3000.0
    assert dry_run.salary_details.transportation_allowance == 1200.0
    assert dry_run.salary_details.total_package == 17000.0
    assert dry_run.recipient == "مصرف الراجحي"
    assert dry_run.approval_token != ""
    assert "الهوية الوطنية" in dry_run.preview_body_ar
    assert "17,000.00 ريال سعودي" in dry_run.preview_body_ar


def test_dry_run_expat_employee_employment_certificate_no_salary(mock_repo, mock_gateway):
    service = LetterService(repo=mock_repo, gateway=mock_gateway)
    dry_run = service.dry_run_letter(
        employee_id=102,
        letter_type="employment_certificate",
        recipient="السفارة الإيطالية",
        purpose="طلب تأشيرة سياحية",
        language="both",
        include_salary=False,
    )

    assert dry_run.is_valid is True
    assert dry_run.employee_name == "محمود أحمد رضوان"
    assert dry_run.is_saudi is False
    assert dry_run.nationality_text_ar == "مقيم غير سعودي"
    assert dry_run.identification_id == "2498765432"
    assert dry_run.include_salary is False
    assert "الإقامة النظامية" in dry_run.preview_body_ar
    assert "Resident Identity (Iqama)" in dry_run.preview_body_en
    # لا يذكر الراتب إذا كان include_salary=False
    assert "الراتب الأساسي" not in dry_run.preview_body_ar


def test_dry_run_non_existent_employee(mock_repo, mock_gateway):
    service = LetterService(repo=mock_repo, gateway=mock_gateway)
    dry_run = service.dry_run_letter(
        employee_id=9999,
        letter_type="salary_certificate",
    )
    assert dry_run.is_valid is False
    assert len(dry_run.errors) > 0
    assert "غير موجود" in dry_run.errors[0]
    assert dry_run.approval_token == ""


def test_apply_letter_four_eyes_rejection_without_confirmation(mock_repo, mock_gateway):
    service = LetterService(repo=mock_repo, gateway=mock_gateway)
    dry_run = service.dry_run_letter(employee_id=101, letter_type="salary_certificate")
    assert dry_run.is_valid is True

    # محاولة التطبيق بدون كتابة "تأكيد"
    result = service.apply_letter(
        approval_token=dry_run.approval_token,
        user_confirmation_text="نعم نفذ",
    )
    assert result.is_success is False
    assert result.request_status == "rejected"
    assert "تأكيد" in result.message_ar
    mock_gateway.create_letter_request.assert_not_called()


def test_apply_letter_rejection_invalid_token(mock_repo, mock_gateway):
    service = LetterService(repo=mock_repo, gateway=mock_gateway)
    result = service.apply_letter(
        approval_token="invalid-token-12345",
        user_confirmation_text="تأكيد",
    )
    assert result.is_success is False
    assert "غير صالح" in result.message_ar
    mock_gateway.create_letter_request.assert_not_called()


def test_apply_letter_success_with_readback_and_html(mock_repo, mock_gateway):
    service = LetterService(repo=mock_repo, gateway=mock_gateway)
    dry_run = service.dry_run_letter(
        employee_id=101,
        letter_type="bank_letter",
        recipient="بنك الإنماء",
        purpose="فتح حساب راتب",
        chamber_of_commerce_stamp=True,
    )

    result = service.apply_letter(
        approval_token=dry_run.approval_token,
        user_confirmation_text="تأكيد",
        executor="test_operator",
    )

    assert result.is_success is True
    assert result.approval_request_id == 8801
    assert result.verification_code.startswith("SAR-BAN-")
    assert result.readback_data is not None
    assert result.html_path is not None
    assert os.path.exists(result.html_path)

    # التحقق من استدعاء البوابة بالبيانات الدقيقة
    mock_gateway.create_letter_request.assert_called_once()
    call_args = mock_gateway.create_letter_request.call_args[0][0]
    assert call_args["request_employee_id"] == 101
    assert call_args["to"] == "بنك الإنماء"
    assert call_args["chamber_of_commerce_stamp"] is True
    assert result.verification_code in call_args["name"]

    # التحقق من أن رمز approval_token تم حذفه لمنع إعادة الاستخدام
    assert dry_run.approval_token not in service._pending_tokens


def test_render_letter_html_bilingual(mock_repo, mock_gateway):
    service = LetterService(repo=mock_repo, gateway=mock_gateway)
    dry_run = service.dry_run_letter(
        employee_id=101,
        letter_type="embassy_letter",
        language="both",
        chamber_of_commerce_stamp=True,
    )
    html = service.render_letter_html(dry_run, "SAR-EMB-2026-101-ABCD", 8801)
    assert "النسخة العربية" in html
    assert "English Version" in html
    assert "SAR-EMB-2026-101-ABCD" in html
    assert "تصديق الغرفة التجارية" in html
    assert "شركة النخبة الذكية للتقنية" in html
