"""
بوابة الكتابة الآمنة لمسيرات الرواتب (Odoo Payroll Write Gateway - Phase 19)
=============================================================================
بوابة معزولة ومحمية ومخصصة حصرياً لكتابة وإدارة مسيرات الرواتب وقسائم الأجور
في نماذج Odoo:
- hr.payslip
- hr.payslip.line
- hr.payslip.run
- hr.payslip.input

تطبق القواعد الصارمة التالية:
1. فحص بيئة العمل (Environment Guard): الحظر القطعي لقواعد الإنتاج الحية ما لم تكن مصرحاً بها.
2. حظر النماذج غير المصرح بها (Model Isolation): رفض أي استدعاء خارج النماذج المحددة.
3. حظر الحذف (No Unlink): حظر عمليات unlink لحماية السجلات المالية والمحاسبية.
4. إرجاع معرّف السجل المنشأ للتحقق المستقل بعد الكتابة (Readback Verification).
"""

from __future__ import annotations

import os
import xmlrpc.client
from datetime import date
from typing import Any, Dict, List, Optional

PAYSLIP_MODEL = "hr.payslip"
PAYSLIP_LINE_MODEL = "hr.payslip.line"
PAYSLIP_RUN_MODEL = "hr.payslip.run"
PAYSLIP_INPUT_MODEL = "hr.payslip.input"

ALLOWED_PAYROLL_MODELS = {
    PAYSLIP_MODEL,
    PAYSLIP_LINE_MODEL,
    PAYSLIP_RUN_MODEL,
    PAYSLIP_INPUT_MODEL,
}

from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS


class PayrollEnvironmentGuardError(Exception):
    """خطأ يطلق عند محاولة الكتابة في قاعدة بيانات غير مصرح بها."""
    pass


class PayrollWriteGatewayError(Exception):
    """خطأ يطلق عند فشل تنفيذ عملية الكتابة في Odoo."""
    pass


class OdooPayrollWriteGateway:
    """
    بوابة كتابة معزولة ومخصصة لمسيرات الرواتب في Odoo (hr.payslip).
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
        db_clean = (self.db or "").strip().lower()
        if not db_clean:
            raise PayrollEnvironmentGuardError("لم يتم تحديد اسم قاعدة بيانات Odoo.")

        if db_clean in ALLOWED_TEST_DBS:
            return

        for prefix in ALLOWED_DEV_DBS:
            if prefix in db_clean:
                return

        raise PayrollEnvironmentGuardError(
            f"قاعدة البيانات '{self.db}' غير مصرح بالكتابة فيها. "
            f"يقتصر التعديل على القواعد التجريبية المعتمدة."
        )

    def _get_connection(self) -> tuple[int, Any]:
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
                raise PayrollWriteGatewayError("فشل تسجيل الدخول والتوثيق مع Odoo لمسيرات الرواتب.")
            self._uid = uid

            if self._models is None:
                self._models = xmlrpc.client.ServerProxy(
                    f"{self.url}/xmlrpc/2/object",
                    allow_none=True
                )

            return self._uid, self._models
        except Exception as exc:
            if isinstance(exc, (PayrollEnvironmentGuardError, PayrollWriteGatewayError)):
                raise
            raise PayrollWriteGatewayError(f"خطأ في الاتصال مع Odoo: {exc}") from exc

    def _call(self, model: str, method: str, args: List[Any], kwargs: Optional[Dict[str, Any]] = None) -> Any:
        if model not in ALLOWED_PAYROLL_MODELS:
            raise PayrollWriteGatewayError(
                f"النموذج '{model}' غير مصرح به في بوابة مسيرات الرواتب. "
                f"النماذج المسموح بها: {list(ALLOWED_PAYROLL_MODELS)}"
            )

        if method in ("unlink", "unlink_all"):
            raise PayrollWriteGatewayError(
                f"العملية '{method}' محظورة قطعياً في بوابة الرواتب لحماية السجلات المالية والمحاسبية."
            )

        uid, models = self._get_connection()
        kwargs = kwargs or {}

        try:
            return models.execute_kw(self.db, uid, self.password, model, method, args, kwargs)
        except Exception as exc:
            raise PayrollWriteGatewayError(f"فشل استدعاء {model}.{method}: {exc}") from exc

    def create_payslip(
        self,
        employee_id: int,
        date_from: str,
        date_to: str,
        name: Optional[str] = None,
        struct_id: Optional[int] = None,
        basic_wage: float = 0.0,
        gross_wage: float = 0.0,
        net_wage: float = 0.0,
        discipline_amount: float = 0.0,
        installment_employee_loan: float = 0.0,
        state: str = "draft",
    ) -> int:
        """
        إنشاء قسيمة راتب (hr.payslip) جديدة لموظف في Odoo.
        """
        if not employee_id:
            raise PayrollWriteGatewayError("معرّف الموظف إلزامي لإنشاء قسيمة الراتب.")
        if not date_from or not date_to:
            raise PayrollWriteGatewayError("تاريخ بداية ونهاية مسير الراتب إلزاميان.")

        slip_name = name or f"مسير راتب - موظف #{employee_id} ({date_from} إلى {date_to})"

        vals: Dict[str, Any] = {
            "employee_id": employee_id,
            "name": slip_name,
            "date_from": date_from,
            "date_to": date_to,
            "basic_wage": float(basic_wage),
            "gross_wage": float(gross_wage),
            "net_wage": float(net_wage),
            "discipline_amount": float(discipline_amount),
            "installment_employee_loan": float(installment_employee_loan),
            "state": state,
        }

        if struct_id:
            vals["struct_id"] = struct_id

        created_id = self._call(PAYSLIP_MODEL, "create", [vals])
        if isinstance(created_id, list):
            raise PayrollWriteGatewayError("أرجعت Odoo قائمة بدلاً من معرّف سجل قسيمة منفرد.")
        return int(created_id)

    def update_payslip_state(self, payslip_id: int, state: str) -> bool:
        """
        تحديث حالة قسيمة الراتب (draft, verify, done, cancel).
        """
        if not payslip_id:
            raise PayrollWriteGatewayError("معرّف قسيمة الراتب إلزامي.")
        res = self._call(PAYSLIP_MODEL, "write", [[payslip_id], {"state": state}])
        return bool(res)

    def read_payslip(
        self,
        payslip_id: int,
        fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        قراءة سجل قسيمة الراتب من Odoo لأغراض التحقق المستقل (Readback Verification).
        """
        if not payslip_id:
            return None
        read_fields = fields or [
            "id", "name", "employee_id", "date_from", "date_to",
            "basic_wage", "gross_wage", "net_wage", "discipline_amount",
            "installment_employee_loan", "state", "struct_id"
        ]
        res = self._call(PAYSLIP_MODEL, "read", [[payslip_id]], {"fields": read_fields})
        if res and isinstance(res, list) and len(res) > 0:
            return res[0]
        return None
