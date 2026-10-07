"""
اختبارات واجهات برمجة التطبيقات للمرحلتين 24 و 25 (Web Service API Endpoints Tests for Phases 24 & 25)
========================================================================================================
التحقق من:
- نقاط نهاية المصروفات والانتدابات (/api/expenses/...)
- نقاط نهاية الرصد الاستباقي للوثائق والصلاحيات (/api/alerts/expiries/...)
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from web_service import app
from expense_service import ExpenseDryRunResult, ExpenseApplyResult
from document_expiry_service import DocumentExpiryScanResult, DocumentExpiryItem


@pytest.fixture
def client():
    return TestClient(app)


def test_get_expense_categories(client):
    res = client.get("/api/expenses/categories")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert len(data["categories"]) >= 6
    cat_ids = [c["id"] for c in data["categories"]]
    assert "travel" in cat_ids
    assert "hotel" in cat_ids
    assert "general" in cat_ids


def test_get_employee_expenses(client):
    with patch("odoo_readonly_repository.OdooReadonlyRepository.get_hr_expenses", return_value=[{"id": 1, "name": "Travel", "total_amount": 500}]):
        res = client.get("/api/expenses/employee/15")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["count"] == 1
        assert data["expenses"][0]["id"] == 1


def test_expense_dry_run_endpoint(client):
    mock_dry = ExpenseDryRunResult(
        is_valid=True,
        employee_id=15,
        employee_name="سعيد القحطاني",
        is_saudi=True,
        nationality_text_ar="مواطن سعودي",
        identification_id="1029384756",
        job_title="مهندس",
        department_name="تقنية المعلومات",
        expense_category="travel",
        category_title_ar="تذاكر سفر وانتقالات رسمية",
        product_id=7,
        total_amount=1150.0,
        includes_vat=True,
        untaxed_amount=1000.0,
        tax_amount=150.0,
        expense_date="2026-10-06",
        description="تذاكر سفر لحضور معرض تقني",
        reference_code="EXP-2026-15-ABC123",
        company_id=15,
        approval_token="TOK-EXP-123",
        created_at_iso="2026-10-06T12:00:00Z",
        preview_body_ar="مطالبة سفر",
    )
    with patch("expense_service.ExpenseService.dry_run_expense", return_value=mock_dry):
        payload = {
            "employee_id": 15,
            "expense_category": "travel",
            "total_amount": 1150.0,
            "description": "تذاكر سفر",
            "includes_vat": True,
        }
        res = client.post("/api/expenses/dry-run", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["dry_run"]["approval_token"] == "TOK-EXP-123"
        assert data["dry_run"]["tax_amount"] == 150.0


def test_expense_apply_endpoint_requires_confirmation(client):
    from expense_service import _SHARED_PENDING_EXPENSE_TOKENS, ExpenseDryRunResult
    _SHARED_PENDING_EXPENSE_TOKENS["TOK-EXP-123"] = MagicMock(
        spec=ExpenseDryRunResult,
        employee_id=15,
        employee_name="سعيد",
        total_amount=500.0,
        reference_code="EXP-1",
    )
    res = client.post("/api/expenses/apply", json={"approval_token": "TOK-EXP-123", "user_confirmation_text": "نعم"})
    assert res.status_code == 400
    assert "تأكيد" in res.json()["detail"]


def test_get_expiries_alerts_endpoint(client):
    mock_scan = DocumentExpiryScanResult(
        scan_date="2026-10-06",
        total_employees_scanned=10,
        total_alerts=2,
        expired_count=1,
        critical_count=1,
        warning_count=0,
        notice_count=0,
        safe_count=8,
        items=[
            DocumentExpiryItem(
                employee_id=101,
                employee_name="محمد سالم",
                is_saudi=False,
                nationality_text_ar="مقيم وافد",
                identification_id="2012345678",
                job_title="فني",
                department_name="الصيانة",
                category_id="iqama",
                category_title_ar="هوية مقيم (الإقامة)",
                category_title_en="National ID / Iqama",
                field_name="id_expiry_date",
                expiry_date="2026-10-01",
                days_remaining=-5,
                severity="expired",
                severity_label_ar="منتهي الصلاحية",
                severity_badge_color="#EF4444",
                legal_article_ar="نظام الإقامة وجوازات السفر",
                authority="الجوازات",
            )
        ],
        by_category={"iqama": 1},
        by_severity={"expired": 1, "critical": 1},
        by_department={"الصيانة": 1},
    )
    with patch("document_expiry_service.DocumentExpiryService.scan_expiries", return_value=mock_scan):
        res = client.get("/api/alerts/expiries?max_days=30")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["total_alerts"] == 2
        assert len(data["items"]) == 1
        assert data["items"][0]["employee_name"] == "محمد سالم"


def test_post_scan_expiries_endpoint(client):
    mock_scan = DocumentExpiryScanResult(
        scan_date="2026-10-06",
        total_employees_scanned=15,
        total_alerts=1,
        expired_count=0,
        critical_count=1,
        warning_count=0,
        notice_count=0,
        safe_count=14,
        items=[],
        by_category={},
        by_severity={},
        by_department={},
    )
    with patch("document_expiry_service.DocumentExpiryService.scan_expiries", return_value=mock_scan):
        res = client.post("/api/alerts/expiries/scan", json={"max_days": 15})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["critical_count"] == 1


def test_get_expiries_html_report(client):
    with patch("document_expiry_service.DocumentExpiryService.render_html_report", return_value="<html><body>Report</body></html>"):
        res = client.get("/api/alerts/expiries/html")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "Report" in res.text
