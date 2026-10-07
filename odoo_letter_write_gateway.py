"""
بوابة الكتابة الآمنة لخطابات الموارد البشرية وطلبات الاعتماد (Odoo Letter Write Gateway - Phase 22)
================================================================================================
بوابة معزولة ومحمية مخصصة حصرياً لكتابة وإدارة خطابات الموارد البشرية،
شهادات التعريف بالراتب، وطلبات الاعتماد في نماذج Odoo:
- approval.request
- approval.category

تطبق القواعد الصارمة التالية:
1. فحص بيئة العمل (Environment Guard): الحظر القطعي لقواعد الإنتاج الحية ما لم تكن مصرحاً بها.
2. حظر النماذج غير المصرح بها (Model Isolation): رفض أي استدعاء خارج النماذج المحددة.
3. حظر الحذف (No Unlink): حظر عمليات unlink لحماية السجلات والخطابات الرسمية.
4. إرجاع معرّف السجل المنشأ للتحقق المستقل بعد الكتابة (Readback Verification).
"""

from __future__ import annotations

import os
import xmlrpc.client
from typing import Any, Dict, List, Optional

from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS

APPROVAL_REQUEST_MODEL = "approval.request"
APPROVAL_CATEGORY_MODEL = "approval.category"

ALLOWED_LETTER_MODELS = frozenset({
    APPROVAL_REQUEST_MODEL,
    APPROVAL_CATEGORY_MODEL,
})

ALLOWED_LETTER_METHODS = frozenset({
    "create",
    "write",
    "read",
    "search_read",
    "action_confirm",
    "action_approve",
    "action_refuse",
    "action_cancel",
})


class LetterEnvironmentGuardError(Exception):
    pass


class LetterWriteGatewayError(Exception):
    pass


class OdooLetterWriteGateway:
    """
    بوابة كتابة معزولة ومخصصة لطلبات الخطابات والموافقات الرسمية في Odoo (approval.request).
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
            raise LetterEnvironmentGuardError(
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
                raise LetterWriteGatewayError("فشل تسجيل الدخول والتوثيق مع Odoo لبوابة الخطابات.")
            self._uid = uid

            if self._models is None:
                self._models = xmlrpc.client.ServerProxy(
                    f"{self.url}/xmlrpc/2/object",
                    allow_none=True
                )

            return self._uid, self._models
        except Exception as exc:
            if isinstance(exc, (LetterEnvironmentGuardError, LetterWriteGatewayError)):
                raise
            raise LetterWriteGatewayError(f"خطأ في الاتصال مع Odoo: {exc}") from exc

    def _call(self, model: str, method: str, args: List[Any], kwargs: Optional[Dict[str, Any]] = None) -> Any:
        if model not in ALLOWED_LETTER_MODELS:
            raise LetterWriteGatewayError(
                f"النموذج '{model}' غير مصرح به في بوابة الخطابات. "
                f"النماذج المسموح بها: {list(ALLOWED_LETTER_MODELS)}"
            )

        if method in ("unlink", "unlink_all"):
            raise LetterWriteGatewayError(
                f"العملية '{method}' محظورة قطعياً لحماية السجلات والخطابات الرسمية الصادرة."
            )

        if method not in ALLOWED_LETTER_METHODS:
            raise LetterWriteGatewayError(
                f"الإجراء '{method}' غير مصرح به في بوابة الخطابات والموافقات."
            )

        uid, models = self._get_connection()
        kwargs = kwargs or {}

        try:
            return models.execute_kw(self.db, uid, self.password, model, method, args, kwargs)
        except Exception as exc:
            raise LetterWriteGatewayError(f"فشل تنفيذ العملية {method} على {model}: {exc}") from exc

    def create_letter_request(self, values: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> int:
        """إنشاء طلب خطاب أو موافقة رسمية في Odoo."""
        if not isinstance(values, dict) or not values:
            raise LetterWriteGatewayError("create_letter_request يتطلب قاموس بيانات غير فارغ.")

        kwargs: Dict[str, Any] = {}
        if context is not None:
            kwargs["context"] = context

        req_id = self._call(APPROVAL_REQUEST_MODEL, "create", [values], kwargs)
        if not req_id or not isinstance(req_id, int):
            raise LetterWriteGatewayError(f"فشل إنشاء طلب الخطاب، المعرف المسترجع غير صالح: {req_id}")
        return req_id

    def read_letter_request(self, request_id: int, fields: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """قراءة طلب خطاب محدد للتحقق بعد الكتابة (Readback Verification)."""
        if not isinstance(request_id, int) or request_id <= 0:
            raise LetterWriteGatewayError("معرف الطلب يجب أن يكون رقماً صحيحاً موجباً.")

        target_fields = fields or [
            "id",
            "name",
            "request_status",
            "request_employee_id",
            "category_id",
            "to",
            "purpose",
            "letter_language",
            "chamber_of_commerce_stamp",
            "date",
            "company_id",
        ]

        res = self._call(APPROVAL_REQUEST_MODEL, "read", [[request_id]], {"fields": target_fields})
        if res and isinstance(res, list) and len(res) > 0:
            return res[0]
        return None

    def search_letter_requests(
        self,
        domain: Optional[List[Any]] = None,
        fields: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """البحث واسترجاع طلبات الخطابات."""
        target_fields = fields or [
            "id", "name", "request_status", "request_employee_id", "category_id", "to", "date"
        ]
        return self._call(
            APPROVAL_REQUEST_MODEL,
            "search_read",
            [domain or []],
            {"fields": target_fields, "limit": limit, "order": "id desc"}
        )
