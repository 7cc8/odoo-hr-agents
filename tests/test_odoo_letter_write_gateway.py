"""
اختبارات بوابة الكتابة الآمنة للخطابات والموافقات (Phase 22 - Letter Gateway Tests)
=================================================================================
تختبر:
1. فحص حارس البيئة (Environment Guard) ومنع الكتابة في قواعد غير مصرح بها.
2. عزل النماذج (Model Isolation) ومنع أي نموذج خارج approval.request و approval.category.
3. حظر الحذف الصارم (No Unlink Rule) على مستوى البوابة.
4. استدعاء create و read والتحقق من المعرفات.
"""

import pytest
from unittest.mock import MagicMock

from odoo_letter_write_gateway import (
    OdooLetterWriteGateway,
    LetterEnvironmentGuardError,
    LetterWriteGatewayError,
    APPROVAL_REQUEST_MODEL,
    APPROVAL_CATEGORY_MODEL,
)


def test_letter_gateway_environment_guard_blocks_unauthorized_db():
    with pytest.raises(LetterEnvironmentGuardError):
        OdooLetterWriteGateway(
            url="https://fake.odoo.com",
            db="production_unauthorized_company_db",
            username="admin",
            password="pwd",
        )


def test_letter_gateway_model_isolation():
    mock_common = MagicMock()
    mock_common.authenticate.return_value = 5
    mock_models = MagicMock()

    gw = OdooLetterWriteGateway(
        url="https://fake.odoo.com",
        db="odooprosys-hr19-main-37916265",
        username="admin",
        password="pwd",
        common=mock_common,
        models=mock_models,
    )

    # نموذج غير مسموح به في بوابة الخطابات مثل hr.employee
    with pytest.raises(LetterWriteGatewayError) as exc_info:
        gw._call("hr.employee", "create", [{"name": "Test"}])
    assert "غير مصرح به في بوابة الخطابات" in str(exc_info.value)


def test_letter_gateway_no_unlink_enforcement():
    mock_common = MagicMock()
    mock_common.authenticate.return_value = 5
    mock_models = MagicMock()

    gw = OdooLetterWriteGateway(
        url="https://fake.odoo.com",
        db="odooprosys-hr19-main-37916265",
        username="admin",
        password="pwd",
        common=mock_common,
        models=mock_models,
    )

    # محاولة unlink محظورة
    with pytest.raises(LetterWriteGatewayError) as exc_info:
        gw._call(APPROVAL_REQUEST_MODEL, "unlink", [[101]])
    assert "محظورة قطعياً" in str(exc_info.value)


def test_letter_gateway_create_and_read():
    mock_common = MagicMock()
    mock_common.authenticate.return_value = 5
    mock_models = MagicMock()
    mock_models.execute_kw.side_effect = [
        8805,  # for create
        [{"id": 8805, "name": "شهادة تعريف", "request_status": "new"}],  # for read
    ]

    gw = OdooLetterWriteGateway(
        url="https://fake.odoo.com",
        db="odooprosys-hr19-main-37916265",
        username="admin",
        password="pwd",
        common=mock_common,
        models=mock_models,
    )

    req_id = gw.create_letter_request({"name": "شهادة تعريف", "request_employee_id": 10})
    assert req_id == 8805

    readback = gw.read_letter_request(req_id)
    assert readback is not None
    assert readback["id"] == 8805
    assert readback["name"] == "شهادة تعريف"
