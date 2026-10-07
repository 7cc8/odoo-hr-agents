"""
بوابة الكتابة الآمنة لمصروفات الموظفين والانتدابات (Odoo Expense Write Gateway - Phase 24)
========================================================================================
بوابة معزولة ومحمية مخصصة حصرياً لكتابة وإدارة مطالبات المصروفات، الانتدابات، وفواتير العمل في Odoo:
- hr.expense

القواعد والضوابط الصارمة:
1. فحص بيئة العمل (Environment Guard): الحظر القطعي لقواعد الإنتاج الحية ما لم تكن مصرحاً بها.
2. عزل النماذج (Model Isolation): رفض أي استدعاء خارج hr.expense.
3. حظر الحذف (No Unlink Rule): حظر عمليات unlink لحماية السجلات المالية والمحاسبية.
4. إرجاع معرّف السجل المنشأ للتحقق المستقل بعد الكتابة (Readback Verification).
"""

from __future__ import annotations

import os
import xmlrpc.client
from typing import Any, Dict, List, Optional

from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS

EXPENSE_MODEL = "hr.expense"

ALLOWED_EXPENSE_MODELS = frozenset({
    EXPENSE_MODEL,
})

ALLOWED_EXPENSE_METHODS = frozenset({
    "create",
    "write",
    "read",
    "search_read",
    "action_submit_expenses",
})


class ExpenseEnvironmentGuardError(Exception):
    pass


class ExpenseWriteGatewayError(Exception):
    pass


class OdooExpenseWriteGateway:
    """
    بوابة كتابة معزولة ومخصصة لمصروفات الموظفين في Odoo (hr.expense).
    """

    def __init__(
        self,
        url: Optional[str] = None,
        db: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        common: Optional[Any] = None,
        models: Optional[Any] = None,
    ):
        self.url = (url or os.environ.get("ODOO_URL", "")).rstrip("/")
        self.db = db or os.environ.get("ODOO_DB", "")
        self.username = username or os.environ.get("ODOO_USERNAME", "")
        self.password = password or os.environ.get("ODOO_PASSWORD", "") or os.environ.get("ODOO_API_KEY", "")

        self._check_environment_guard()

        self._uid: Optional[int] = None
        self._common = common
        self._models = models

    def _check_environment_guard(self) -> None:
        allowed = ALLOWED_TEST_DBS | ALLOWED_DEV_DBS
        if self.db and self.db not in allowed:
            raise ExpenseEnvironmentGuardError(
                f"حارس البيئة: قاعدة البيانات '{self.db}' غير مصرح بها للكتابة."
            )

    def _get_connection(self) -> tuple[int, Any]:
        self._check_environment_guard()
        if self._uid is not None and self._models is not None:
            return self._uid, self._models

        try:
            if self._common is None:
                self._common = xmlrpc.client.ServerProxy(
                    f"{self.url}/xmlrpc/2/common",
                    allow_none=True
                )
            uid = self._common.authenticate(self.db, self.username, self.password, {})
            if not uid:
                raise ExpenseWriteGatewayError("فشل تسجيل الدخول والتوثيق مع Odoo لبوابة المصروفات.")
            self._uid = uid

            if self._models is None:
                self._models = xmlrpc.client.ServerProxy(
                    f"{self.url}/xmlrpc/2/object",
                    allow_none=True
                )

            return self._uid, self._models
        except Exception as exc:
            if isinstance(exc, (ExpenseEnvironmentGuardError, ExpenseWriteGatewayError)):
                raise
            raise ExpenseWriteGatewayError(f"خطأ في الاتصال مع Odoo: {exc}") from exc

    def _call(self, model: str, method: str, args: List[Any], kwargs: Optional[Dict[str, Any]] = None) -> Any:
        if model not in ALLOWED_EXPENSE_MODELS:
            raise ExpenseWriteGatewayError(
                f"النموذج '{model}' غير مصرح به في بوابة المصروفات. "
                f"النماذج المسموح بها: {list(ALLOWED_EXPENSE_MODELS)}"
            )

        if method in ("unlink", "unlink_all"):
            raise ExpenseWriteGatewayError(
                f"العملية '{method}' محظورة قطعياً لحماية السجلات المالية ومطالبات المصروفات."
            )

        if method not in ALLOWED_EXPENSE_METHODS:
            raise ExpenseWriteGatewayError(
                f"الإجراء '{method}' غير مصرح به في بوابة المصروفات والانتدابات."
            )

        uid, models = self._get_connection()
        kwargs = kwargs or {}

        try:
            return models.execute_kw(self.db, uid, self.password, model, method, args, kwargs)
        except Exception as exc:
            raise ExpenseWriteGatewayError(f"فشل تنفيذ العملية {method} على {model}: {exc}") from exc

    def create_expense(self, values: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> int:
        """إنشاء مطالبة مصروف جديد في Odoo (hr.expense)."""
        if not isinstance(values, dict) or not values:
            raise ExpenseWriteGatewayError("create_expense يتطلب قاموس بيانات غير فارغ.")

        kwargs: Dict[str, Any] = {}
        if context is not None:
            kwargs["context"] = context

        exp_id = self._call(EXPENSE_MODEL, "create", [values], kwargs)
        if not exp_id or not isinstance(exp_id, int):
            raise ExpenseWriteGatewayError(f"فشل إنشاء المصروف، المعرف المسترجع غير صالح: {exp_id}")
        return exp_id

    def read_expense(self, expense_id: int, fields: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """قراءة مصروف محدد للتحقق بعد الكتابة (Readback Verification)."""
        if not isinstance(expense_id, int) or expense_id <= 0:
            raise ExpenseWriteGatewayError("معرف المصروف يجب أن يكون رقماً صحيحاً موجباً.")

        target_fields = fields or [
            "id",
            "name",
            "employee_id",
            "product_id",
            "total_amount",
            "total_amount_currency",
            "state",
            "date",
            "description",
            "company_id",
            "currency_id",
        ]

        res = self._call(EXPENSE_MODEL, "read", [[expense_id]], {"fields": target_fields})
        if res and isinstance(res, list) and len(res) > 0:
            return res[0]
        return None

    def search_expenses(
        self,
        domain: Optional[List[Any]] = None,
        fields: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """البحث واسترجاع المصروفات."""
        target_fields = fields or [
            "id", "name", "employee_id", "total_amount", "state", "date", "product_id"
        ]
        return self._call(
            EXPENSE_MODEL,
            "search_read",
            [domain or []],
            {"fields": target_fields, "limit": limit, "order": "date desc, id desc"}
        )
