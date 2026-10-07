"""
اختبارات وحدة وخدمة رصد صلاحيات الوثائق والتنبيهات المجدولة (Phase 25 - DocumentExpiryService Tests)
========================================================================================================
التحقق من صحة:
1. تصنيف الوثائق الست (هوية/إقامة، جواز، تأشيرة، رخصة عمل، فترة تجربة، عقد عمل).
2. مستويات الخطورة (منتهي الصلاحية، حرج، تحذيري، تنبيه مبكر، آمن).
3. استثناء رخص العمل للمواطنين السعوديين تلقائياً.
4. دقة حساب الأيام المتبقية والمستحقات.
5. الفلترة حسب الفئة والنافذة الزمنية ومستوى الخطورة.
6. توليد بطاقة إشعارات تيليقرام والتقرير المؤسسي HTML.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock

from document_expiry_service import (
    DocumentExpiryService,
    DOCUMENT_CATEGORIES,
    SEVERITY_LEVELS,
    DocumentExpiryScanResult,
)


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    return repo


@pytest.fixture
def sample_employees():
    base_date = date(2026, 10, 1)
    return [
        {
            # 1. وافد مقيم بهوية وإقامة منتهية الصلاحية منذ 5 أيام
            "id": 101,
            "name": "طارق محمود",
            "country_id": [2, "مصر"],
            "identification_id": "2456789012",
            "department_id": [1, "تقنية المعلومات"],
            "job_id": [1, "مهندس برمجيات"],
            "id_expiry_date": (base_date - timedelta(days=5)).isoformat(),
            "passport_expiration_date": (base_date + timedelta(days=200)).isoformat(),
            "visa_expire": False,
            "work_permit_expiration_date": (base_date + timedelta(days=15)).isoformat(),
            "trial_date_end": False,
            "contract_date_end": (base_date + timedelta(days=80)).isoformat(),
            "active": True,
        },
        {
            # 2. موظف سعودي في فترة التجربة تنتهي خلال 6 أيام (حرج)
            "id": 102,
            "name": "سعد بن خالد العتيبي",
            "country_id": [1, "المملكة العربية السعودية"],
            "identification_id": "1098765432",
            "department_id": [2, "الموارد البشرية"],
            "job_id": [2, "أخصائي توظيف"],
            "id_expiry_date": (base_date + timedelta(days=400)).isoformat(),
            "passport_expiration_date": (base_date + timedelta(days=120)).isoformat(),
            "visa_expire": False,
            "work_permit_expiration_date": (base_date + timedelta(days=10)).isoformat(),  # يجب إهمالها لسعودي
            "trial_date_end": (base_date + timedelta(days=6)).isoformat(),
            "contract_date_end": False,
            "active": True,
        },
        {
            # 3. وافد لديه جواز سفر ينتهي خلال 25 يوماً (تحذيري)
            "id": 103,
            "name": "جون سميث",
            "country_id": [3, "بريطانيا"],
            "identification_id": "2345678901",
            "department_id": [3, "العمليات"],
            "job_id": [3, "مدير مشاريع"],
            "id_expiry_date": (base_date + timedelta(days=150)).isoformat(),
            "passport_expiration_date": (base_date + timedelta(days=25)).isoformat(),
            "visa_expire": (base_date + timedelta(days=45)).isoformat(),
            "work_permit_expiration_date": (base_date + timedelta(days=120)).isoformat(),
            "trial_date_end": False,
            "contract_date_end": (base_date + timedelta(days=25)).isoformat(),
            "active": True,
        },
        {
            # 4. موظف كل وثائقه سارية لأكثر من 150 يوماً (آمن)
            "id": 104,
            "name": "نورة المنصور",
            "country_id": [1, "Saudi Arabia"],
            "identification_id": "1087654321",
            "department_id": [1, "تقنية المعلومات"],
            "job_id": [4, "محللة بيانات"],
            "id_expiry_date": (base_date + timedelta(days=365)).isoformat(),
            "passport_expiration_date": (base_date + timedelta(days=500)).isoformat(),
            "visa_expire": False,
            "work_permit_expiration_date": False,
            "trial_date_end": False,
            "contract_date_end": False,
            "active": True,
        },
    ]


def test_scan_expiries_basic(mock_repo, sample_employees):
    ref_date = date(2026, 10, 1)
    service = DocumentExpiryService(repo=mock_repo)

    result = service.scan_expiries(
        reference_date=ref_date,
        max_days=90,
        employees_data=sample_employees,
    )

    assert isinstance(result, DocumentExpiryScanResult)
    assert result.total_employees_scanned == 4
    assert result.total_alerts > 0

    # طارق: إقامة منتهية (-5 أيام) -> expired
    # طارق: رخصة عمل (15 يوماً) -> warning
    # طارق: عقد عمل (80 يوماً) -> notice
    # سعد: فترة تجربة (6 أيام) -> critical
    # (رخصة عمل سعد مهملة لأنه سعودي)
    # جون: جواز سفر (25 يوماً) -> warning
    # جون: تأشيرة (45 يوماً) -> notice
    # جون: عقد عمل (25 يوماً) -> warning
    # نورة: آمنة

    assert result.expired_count == 1
    assert result.critical_count == 1
    assert result.warning_count >= 3
    assert result.notice_count >= 2


def test_saudi_exempt_from_work_permit(mock_repo, sample_employees):
    ref_date = date(2026, 10, 1)
    service = DocumentExpiryService(repo=mock_repo)

    result = service.scan_expiries(
        reference_date=ref_date,
        max_days=90,
        category_filter="work_permit",
        employees_data=sample_employees,
    )

    # فقط المقيمين يظهرون في فحص رخص العمل (طارق فقط)
    emp_ids = [it.employee_id for it in result.items]
    assert 101 in emp_ids
    assert 102 not in emp_ids  # سعد مواطن سعودي لا يخضع لرخص العمل


def test_filter_by_max_days(mock_repo, sample_employees):
    ref_date = date(2026, 10, 1)
    service = DocumentExpiryService(repo=mock_repo)

    # طلب التنبيهات حتى 7 أيام فقط (يشمل المنتهي والحرج)
    result = service.scan_expiries(
        reference_date=ref_date,
        max_days=7,
        employees_data=sample_employees,
    )

    for item in result.items:
        assert item.days_remaining <= 7
    assert result.expired_count == 1
    assert result.critical_count == 1
    assert result.warning_count == 0
    assert result.notice_count == 0


def test_filter_by_severity(mock_repo, sample_employees):
    ref_date = date(2026, 10, 1)
    service = DocumentExpiryService(repo=mock_repo)

    result = service.scan_expiries(
        reference_date=ref_date,
        max_days=90,
        severity_filter="expired",
        employees_data=sample_employees,
    )

    assert result.total_alerts == 1
    assert result.items[0].severity == "expired"
    assert result.items[0].employee_id == 101
    assert result.items[0].days_remaining == -5


def test_telegram_message_formatting(mock_repo, sample_employees):
    ref_date = date(2026, 10, 1)
    service = DocumentExpiryService(repo=mock_repo)

    result = service.scan_expiries(
        reference_date=ref_date,
        max_days=90,
        employees_data=sample_employees,
    )

    msg = service.format_telegram_summary_message(result, top_n=5)
    assert "تنبيه عاجل" in msg or "تقرير متابعة" in msg
    assert "منتهية الصلاحية" in msg
    assert "طارق محمود" in msg
    assert "سعد بن خالد العتيبي" in msg


def test_html_report_rendering(mock_repo, sample_employees):
    ref_date = date(2026, 10, 1)
    service = DocumentExpiryService(repo=mock_repo)

    result = service.scan_expiries(
        reference_date=ref_date,
        max_days=90,
        employees_data=sample_employees,
    )

    html = service.render_html_report(result)
    assert "<!DOCTYPE html>" in html
    assert "تقرير الرصد الاستباقي لانتهاء الوثائق والصلاحيات" in html
    assert "طارق محمود" in html
    assert "badge-expired" in html
    assert "badge-critical" in html


def test_empty_employees(mock_repo):
    service = DocumentExpiryService(repo=mock_repo)
    result = service.scan_expiries(
        employees_data=[],
    )

    assert result.total_employees_scanned == 0
    assert result.total_alerts == 0
    msg = service.format_telegram_summary_message(result)
    assert "ممتاز ونظامي" in msg
