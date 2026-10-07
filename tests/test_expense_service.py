"""
اختبارات خدمة وبوابة مصروفات الموظفين والانتدابات (Phase 24 - ExpenseService & Gateway Tests)
==========================================================================================
تختبر:
1. التصنيفات المدعومة لمطالبات المصروفات.
2. احتساب ضريبة القيمة المضافة ZATCA (15%) والمبلغ غير الخاضع.
3. فحص القيود المالية (المبلغ أكبر من صفر، وجود الموظف).
4. مبدأ التحقق المزدوج Four-Eyes ورفض الحفظ بدون "تأكيد".
5. استدعاء بوابة الكتابة والتحقق المستقل بعد الحفظ (Readback Verification).
6. عزل النماذج وحظر الحذف في بوابة المصروفات.
"""

import os
import json
import pytest
from unittest.mock import MagicMock

from expense_service import (
    ExpenseService,
    SUPPORTED_EXPENSE_CATEGORIES,
    ExpenseDryRunResult,
    ExpenseApplyResult,
)
from odoo_expense_write_gateway import (
    OdooExpenseWriteGateway,
    ExpenseEnvironmentGuardError,
    ExpenseWriteGatewayError,
    EXPENSE_MODEL,
)


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_employees.return_value = [
        {
            "id": 301,
            "name": "سلطان بن عبدالعزيز المطيري",
            "identification_id": "1076543210",
            "job_id": [18, "مهندس مشاريع"],
            "department_id": [28, "إدارة العمليات الميدانية"],
            "company_id": [15, "شركة النخبة الذكية"],
            "currency_id": [148, "SAR"],
            "country_id": [1, "Saudi Arabia"],
        },
    ]
    return repo


@pytest.fixture
def mock_gateway():
    gateway = MagicMock(spec=OdooExpenseWriteGateway)
    gateway.create_expense.return_value = 7701
    gateway.read_expense.return_value = {
        "id": 7701,
        "name": "تذاكر طيران الرياض-جدة (EXP-2026-301-TEST)",
        "employee_id": 301,
        "product_id": 7,
        "total_amount": 1150.0,
        "state": "draft",
        "date": "2026-10-06",
        "company_id": 15,
    }
    return gateway


def test_supported_expense_categories():
    assert "travel" in SUPPORTED_EXPENSE_CATEGORIES
    assert "hotel" in SUPPORTED_EXPENSE_CATEGORIES
    assert "meals" in SUPPORTED_EXPENSE_CATEGORIES
    assert "mileage" in SUPPORTED_EXPENSE_CATEGORIES
    assert "communication" in SUPPORTED_EXPENSE_CATEGORIES
    assert "general" in SUPPORTED_EXPENSE_CATEGORIES


def test_dry_run_expense_with_vat(mock_repo, mock_gateway):
    service = ExpenseService(repo=mock_repo, gateway=mock_gateway)
    # 1,150 SAR with 15% VAT => untaxed 1000.0, tax 150.0
    res = service.dry_run_expense(
        employee_id=301,
        expense_category="travel",
        total_amount=1150.0,
        description="تذاكر طيران لحضور اجتماع مشروع جدة",
        includes_vat=True,
    )
    assert res.is_valid is True
    assert res.employee_name == "سلطان بن عبدالعزيز المطيري"
    assert res.total_amount == 1150.0
    assert res.untaxed_amount == 1000.0
    assert res.tax_amount == 150.0
    assert res.approval_token != ""
    assert res.reference_code.startswith("EXP-")


def test_dry_run_expense_without_vat(mock_repo, mock_gateway):
    service = ExpenseService(repo=mock_repo, gateway=mock_gateway)
    res = service.dry_run_expense(
        employee_id=301,
        expense_category="general",
        total_amount=500.0,
        description="نثريات مكتبية بدون فاتورة ضريبية",
        includes_vat=False,
    )
    assert res.is_valid is True
    assert res.total_amount == 500.0
    assert res.untaxed_amount == 500.0
    assert res.tax_amount == 0.0


def test_dry_run_expense_zero_amount_rejected(mock_repo, mock_gateway):
    service = ExpenseService(repo=mock_repo, gateway=mock_gateway)
    res = service.dry_run_expense(
        employee_id=301,
        total_amount=0.0,
    )
    assert res.is_valid is False
    assert any("أكبر من الصفر" in err for err in res.errors)


def test_apply_expense_four_eyes_rejection_without_confirmation(mock_repo, mock_gateway):
    service = ExpenseService(repo=mock_repo, gateway=mock_gateway)
    dry_run = service.dry_run_expense(
        employee_id=301,
        total_amount=300.0,
        expense_category="meals",
    )
    assert dry_run.is_valid is True

    result = service.apply_expense(
        approval_token=dry_run.approval_token,
        user_confirmation_text="نعم احفظ",
    )
    assert result.is_success is False
    assert result.state == "rejected"
    assert "تأكيد" in result.message_ar
    mock_gateway.create_expense.assert_not_called()


def test_apply_expense_success_with_readback_and_html(mock_repo, mock_gateway):
    service = ExpenseService(repo=mock_repo, gateway=mock_gateway)
    dry_run = service.dry_run_expense(
        employee_id=301,
        total_amount=1150.0,
        expense_category="travel",
        description="انتداب عمل رسمي",
    )
    assert dry_run.is_valid is True

    result = service.apply_expense(
        approval_token=dry_run.approval_token,
        user_confirmation_text="تأكيد",
        executor="finance_user",
    )
    assert result.is_success is True
    assert result.expense_id == 7701
    assert result.readback_data is not None
    assert result.html_path is not None
    assert os.path.exists(result.html_path)

    mock_gateway.create_expense.assert_called_once()
    call_args = mock_gateway.create_expense.call_args[0][0]
    assert call_args["employee_id"] == 301
    assert call_args["total_amount"] == 1150.0


def test_expense_gateway_guards_and_no_unlink():
    mock_common = MagicMock()
    mock_common.authenticate.return_value = 5
    mock_models = MagicMock()

    gw = OdooExpenseWriteGateway(
        url="https://fake.odoo.com",
        db="odooprosys-hr19-main-37916265",
        username="admin",
        password="pwd",
        common=mock_common,
        models=mock_models,
    )

    # 1. منع unlink
    with pytest.raises(ExpenseWriteGatewayError) as exc_info:
        gw._call(EXPENSE_MODEL, "unlink", [[7701]])
    assert "محظورة قطعياً" in str(exc_info.value)

    # 2. منع النماذج غير المصرح بها
    with pytest.raises(ExpenseWriteGatewayError) as exc_info:
        gw._call("account.move", "create", [{"name": "fake"}])
    assert "غير مصرح به في بوابة المصروفات" in str(exc_info.value)
