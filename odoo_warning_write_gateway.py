"""
بوابة الكتابة الآمنة لخطابات الإنذار والمساءلات التأديبية (Odoo Warning Write Gateway - Phase 23)
=============================================================================================
بوابة معزولة ومحمية مخصصة حصرياً لكتابة وإدارة خطابات الإنذار، لفت النظر، والمساءلات في نماذج Odoo:
- warning.letter
- warning.type

القواعد والضوابط الصارمة:
1. فحص بيئة العمل (Environment Guard): الحظر القطعي لقواعد الإنتاج الحية ما لم تكن مصرحاً بها.
2. عزل النماذج (Model Isolation): رفض أي استدعاء خارج warning.letter و warning.type.
3. حظر الحذف (No Unlink Rule): حظر عمليات unlink لحماية السجلات والقرارات التأديبية.
4. إرجاع معرّف السجل المنشأ للتحقق المستقل بعد الكتابة (Readback Verification).
"""

from __future__ import annotations

import os
import xmlrpc.client
from typing import Any, Dict, List, Optional

from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS

WARNING_LETTER_MODEL = "warning.letter"
WARNING_TYPE_MODEL = "warning.type"

ALLOWED_WARNING_MODELS = frozenset({
    WARNING_LETTER_MODEL,
    WARNING_TYPE_MODEL,
})

ALLOWED_WARNING_METHODS = frozenset({
    "create",
    "write",
    "read",
    "search_read",
})


class WarningEnvironmentGuardError(Exception):
    pass


class WarningWriteGatewayError(Exception):
    pass


class OdooWarningWriteGateway:
    """
    بوابة كتابة معزولة ومخصصة لخطابات الإنذار والمساءلات في Odoo (warning.letter).
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
            raise WarningEnvironmentGuardError(
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
                raise WarningWriteGatewayError("فشل تسجيل الدخول والتوثيق مع Odoo لبوابة الإنذارات.")
            self._uid = uid

            if self._models is None:
                self._models = xmlrpc.client.ServerProxy(
                    f"{self.url}/xmlrpc/2/object",
                    allow_none=True
                )

            return self._uid, self._models
        except Exception as exc:
            if isinstance(exc, (WarningEnvironmentGuardError, WarningWriteGatewayError)):
                raise
            raise WarningWriteGatewayError(f"خطأ في الاتصال مع Odoo: {exc}") from exc

    def _call(self, model: str, method: str, args: List[Any], kwargs: Optional[Dict[str, Any]] = None) -> Any:
        if model not in ALLOWED_WARNING_MODELS:
            raise WarningWriteGatewayError(
                f"النموذج '{model}' غير مصرح به في بوابة الإنذارات. "
                f"النماذج المسموح بها: {list(ALLOWED_WARNING_MODELS)}"
            )

        if method in ("unlink", "unlink_all"):
            raise WarningWriteGatewayError(
                f"العملية '{method}' محظورة قطعياً لحماية سجلات الجزاءات والإنذارات الرسمية."
            )

        if method not in ALLOWED_WARNING_METHODS:
            raise WarningWriteGatewayError(
                f"الإجراء '{method}' غير مصرح به في بوابة الإنذارات التأديبية."
            )

        uid, models = self._get_connection()
        kwargs = kwargs or {}

        try:
            return models.execute_kw(self.db, uid, self.password, model, method, args, kwargs)
        except Exception as exc:
            raise WarningWriteGatewayError(f"فشل تنفيذ العملية {method} على {model}: {exc}") from exc

    def create_warning_letter(self, values: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> int:
        """إنشاء خطاب إنذار في Odoo (warning.letter)."""
        if not isinstance(values, dict) or not values:
            raise WarningWriteGatewayError("create_warning_letter يتطلب قاموس بيانات غير فارغ.")

        kwargs: Dict[str, Any] = {}
        if context is not None:
            kwargs["context"] = context

        res_id = self._call(WARNING_LETTER_MODEL, "create", [values], kwargs)
        if not res_id or not isinstance(res_id, int):
            raise WarningWriteGatewayError(f"فشل إنشاء خطاب الإنذار، المعرف المسترجع غير صالح: {res_id}")
        return res_id

    def create_warning_type(self, name: str) -> int:
        """إنشاء نوع إنذار جديد في Odoo (warning.type)."""
        if not name or not name.strip():
            raise WarningWriteGatewayError("اسم نوع الإنذار لا يمكن أن يكون فارغاً.")
        type_id = self._call(WARNING_TYPE_MODEL, "create", [{"name": name.strip()}])
        if not type_id or not isinstance(type_id, int):
            raise WarningWriteGatewayError(f"فشل إنشاء نوع الإنذار: {name}")
        return type_id

    def read_warning_letter(self, letter_id: int, fields: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """قراءة خطاب إنذار محدد للتحقق بعد الكتابة (Readback Verification)."""
        if not isinstance(letter_id, int) or letter_id <= 0:
            raise WarningWriteGatewayError("معرف خطاب الإنذار يجب أن يكون رقماً صحيحاً موجباً.")

        target_fields = fields or [
            "id",
            "name",
            "employee_id",
            "department_id",
            "job_id",
            "warning_type_id",
            "date_sent",
            "email_subject",
            "notes",
            "state",
            "has_deduction",
            "deduction_amount",
            "deduction_date",
            "company_id",
        ]

        res = self._call(WARNING_LETTER_MODEL, "read", [[letter_id]], {"fields": target_fields})
        if res and isinstance(res, list) and len(res) > 0:
            return res[0]
        return None

    def search_warning_letters(
        self,
        domain: Optional[List[Any]] = None,
        fields: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """البحث واسترجاع خطابات الإنذار."""
        target_fields = fields or [
            "id", "name", "employee_id", "warning_type_id", "date_sent", "state", "has_deduction"
        ]
        return self._call(
            WARNING_LETTER_MODEL,
            "search_read",
            [domain or []],
            {"fields": target_fields, "limit": limit, "order": "date_sent desc, id desc"}
        )
