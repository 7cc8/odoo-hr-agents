"""
بوابة الحذف المعزولة لـ «كاتب» (Isolated Deletion Gateway for Katib)
===================================================================
1. بوابة معزولة تماماً ومخصصة حصرياً لتنفيذ عمليات الحذف المعتمدة تحت مسؤولية «كاتب».
2. لا تُستورد ولا تُخلط مع OdooWriteGateway (التي تبقى رافضة لـ unlink تماماً).
3. لا تُستورد داخل سراج أو فاحص أو أدوات الاستعلام.
4. تطبق حارس البيئة الصارم (فقط ALLOWED_TEST_DBS أو ALLOWED_DEV_DBS).
5. تنفذ الحذف لسجل واحد فقط لكل طلب (Single Record Only) على النماذج المسموحة حصراً.
6. لا تستخدم SQL مباشر ولا تتجاوز صلاحيات Odoo؛ وإذا رفض Odoo العملية تتوقف وتعيد سبب الرفض فوراً.
"""

from __future__ import annotations

import logging
import xmlrpc.client
from typing import Any, Dict, Optional

from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS

logger = logging.getLogger("odoo_delete_gateway")

ALLOWED_DELETE_MODELS = frozenset({"hr.employee"})


class DeleteGatewayError(RuntimeError):
    """خطأ عام في بوابة الحذف المعزولة."""


class DeleteGatewayEnvironmentGuardError(DeleteGatewayError):
    """خطأ حارس البيئة عند محاولة الحذف في قاعدة غير مصرح بها."""


class DeleteGatewayOdooRejectionError(DeleteGatewayError):
    """خطأ اعتراض ورفض خادم Odoo للحذف بسبب قيود التكامل المرجعي أو الصلاحيات."""


class OdooDeleteGateway:
    """بوابة معزولة ومحمية لحذف السجلات المصرح بها حصرياً عبر كاتب."""

    def __init__(
        self,
        url: str,
        db: str,
        login: str,
        password: str,
        common: Optional[Any] = None,
        models: Optional[Any] = None,
    ) -> None:
        self._check_environment(db)
        self.url = url.rstrip("/")
        self.db = db
        self.login = login
        self._password = password
        self._common = common or xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
        self._models = models or xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)
        self.uid = self._common.authenticate(self.db, login, password, {})
        if not self.uid:
            raise DeleteGatewayError("فشل تسجيل الدخول والمصادقة لبوابة الحذف المعزولة.")

    @staticmethod
    def _check_environment(db: str) -> None:
        all_allowed = ALLOWED_TEST_DBS | ALLOWED_DEV_DBS
        if db not in all_allowed:
            raise DeleteGatewayEnvironmentGuardError(
                f"حارس البيئة: قاعدة البيانات «{db}» غير مصرح بالحذف فيها نهائياً."
            )

    def delete_single_record(self, model: str, record_id: int) -> bool:
        """
        تنفيذ حذف سجل مفرد فقط في Odoo وفق النموذج المصرح به.
        يرفض أي قوائم أو حذف متعدد أو نماذج غير مسموحة.
        """
        if model not in ALLOWED_DELETE_MODELS:
            raise DeleteGatewayError(
                f"النموذج «{model}» غير مدرج ضمن النماذج المصرح بحذف سجلاتها نظامياً."
            )

        if not isinstance(record_id, int) or record_id <= 0:
            raise DeleteGatewayError("معرف السجل يجب أن يكون رقماً صحيحاً موجباً مفرداً.")

        self._check_environment(self.db)

        try:
            result = self._models.execute_kw(
                self.db,
                self.uid,
                self._password,
                model,
                "unlink",
                [[record_id]],
                {},
            )
            if result is not True:
                raise DeleteGatewayError(
                    f"استجابة غير متوقعة من Odoo عند حذف السجل {record_id}: {result!r}"
                )
            return True
        except xmlrpc.client.Fault as fault:
            # اعتراض استثناءات Odoo المرجعية (UserError, ValidationError, foreign key constraint)
            logger.warning("Odoo XML-RPC fault on unlink(%s, %s): %s", model, record_id, fault.faultString)
            raise DeleteGatewayOdooRejectionError(
                f"رفض خادم Odoo الحذف: {fault.faultString}"
            ) from fault
        except Exception as exc:
            if isinstance(exc, (DeleteGatewayError, DeleteGatewayOdooRejectionError)):
                raise
            logger.error("Unexpected error on unlink(%s, %s): %s", model, record_id, exc)
            raise DeleteGatewayOdooRejectionError(f"رفض Odoo العملية بسبب: {exc}") from exc
