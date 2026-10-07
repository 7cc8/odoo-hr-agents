from __future__ import annotations

import xmlrpc.client
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS

LOAN_MODEL = "employee.loan"
LOAN_TYPE_MODEL = "employee.loan.type"
_ALLOWED_MODELS = frozenset({LOAN_MODEL, LOAN_TYPE_MODEL})
_ALLOWED_METHODS = frozenset({"create", "write", "read", "search_read"})


class LoanEnvironmentGuardError(RuntimeError):
    pass


class LoanWriteGatewayError(RuntimeError):
    pass


class OdooLoanWriteGateway:
    """
    بوابة الكتابة الآمنة والمحصورة لسلف وقروض الموظفين (employee.loan).
    تلتزم بحارس البيئة وعزل الصلاحيات وحظر المساس بالنماذج الأخرى في Odoo.
    """
    def __init__(self, url: str, db: str, username: str, password: str, common=None, models=None):
        self._check_environment(db)
        self.url = url.rstrip("/")
        self.db = db
        self.login = username
        self._password = password
        self._common = common or xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
        self._models = models or xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)
        self.uid = self._common.authenticate(self.db, username, password, {})
        if not self.uid:
            raise LoanWriteGatewayError("فشل مصادقة بوابة سلف وقروض الموظفين في Odoo.")
        self._version = self._common.version()

    @staticmethod
    def _check_environment(db: str) -> None:
        allowed = ALLOWED_TEST_DBS | ALLOWED_DEV_DBS
        if db not in allowed:
            raise LoanEnvironmentGuardError(
                f"حارس البيئة: قاعدة البيانات '{db}' غير مصرح بها للكتابة."
            )

    def _call(self, model: str, method: str, args: List[Any], kwargs: Optional[Dict[str, Any]] = None):
        if model not in _ALLOWED_MODELS:
            raise LoanWriteGatewayError(f"النموذج '{model}' غير مصرح به عبر بوابة قروض الموظفين.")
        if method not in _ALLOWED_METHODS:
            raise LoanWriteGatewayError(f"الإجراء '{method}' غير مصرح به عبر بوابة قروض الموظفين.")
        self._check_environment(self.db)
        return self._models.execute_kw(
            self.db, self.uid, self._password, model, method, args, kwargs or {}
        )

    def get_session_info(self) -> Dict[str, Any]:
        return {
            "odoo_url": self.url,
            "odoo_db": self.db,
            "uid": self.uid,
            "login": self.login,
            "server_version": (self._version or {}).get("server_version"),
        }

    def get_or_create_default_loan_type(self) -> int:
        """
        الحصول على معرّف نوع السلفة الافتراضي أو إنشاؤه متوافقاً مع الحسابات المالية (مادة 92).
        """
        types = self._call(LOAN_TYPE_MODEL, "search_read", [[]], {"fields": ["id", "name"], "limit": 1})
        if types and isinstance(types, list) and len(types) > 0:
            return int(types[0]["id"])

        # إنشاء نوع سلفة قياسي خالٍ من الفوائد الربوية متوافق مع نظام العمل السعودي
        vals = {
            "name": "سلفة راتب شخصية (المادة 92)",
            "loan_limit": 100000.0,
            "loan_term": 36,
            "is_apply_interest": False,
            "interest_rate": 0.0,
            "loan_account_payable": 1,
            "loan_account_receivable": 43,
            "interest_account": 1,
            "journal_id": 1,
        }
        created_id = self._call(LOAN_TYPE_MODEL, "create", [vals])
        return int(created_id)

    def create_employee_loan(
        self,
        employee_id: int,
        loan_amount: float,
        installment_amount: float,
        term: int,
        start_date: Optional[str] = None,
        manager_id: Optional[int] = None,
        loan_type_id: Optional[int] = None,
        payment_method: str = "by_payslip",
        notes: Optional[str] = None,
        department_id: Optional[int] = None,
        job_id: Optional[int] = None,
        state: str = "draft",
    ) -> int:
        """
        إنشاء سجل سلفة/قرض جديد لموديل employee.loan في Odoo.
        """
        if not employee_id:
            raise LoanWriteGatewayError("معرّف الموظف إلزامي لإنشاء سجل السلفة.")
        if loan_amount <= 0:
            raise LoanWriteGatewayError("مبلغ السلفة يجب أن يكون أكبر من الصفر.")
        if installment_amount <= 0:
            raise LoanWriteGatewayError("قيمة القسط الشهري يجب أن تكون أكبر من الصفر.")
        if term <= 0:
            raise LoanWriteGatewayError("مدة السداد بالأشهر term يجب أن تكون شهراً واحداً على الأقل.")

        lt_id = loan_type_id or self.get_or_create_default_loan_type()
        m_id = manager_id or employee_id  # Fallback to employee if manager not linked
        today_iso = date.today().isoformat()
        s_date = start_date or today_iso

        reason_note = notes or "سلفة راتب بموجب المادة 92 من نظام العمل السعودي"

        vals: Dict[str, Any] = {
            "employee_id": employee_id,
            "loan_type_id": lt_id,
            "manager_id": m_id,
            "loan_amount": float(loan_amount),
            "installment_amount": float(installment_amount),
            "term": int(term),
            "start_date": s_date,
            "payment_method": payment_method,
            "notes": reason_note,
            "is_apply_interest": False,
            "interest_rate": 0.0,
            "state": state,
        }

        if department_id:
            vals["department_id"] = department_id
        if job_id:
            vals["job_id"] = job_id

        created_id = self._call(LOAN_MODEL, "create", [vals])
        if isinstance(created_id, list):
            raise LoanWriteGatewayError("أرجعت Odoo قائمة بدلاً من معرّف سجل منفرد.")
        return int(created_id)

    def read_employee_loan(
        self,
        loan_id: int,
        fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        قراءة سجل السلفة من Odoo لأغراض التحقق المستقل (Readback Verification).
        """
        if not loan_id:
            return None
        read_fields = fields or [
            "id", "name", "employee_id", "department_id", "job_id",
            "manager_id", "loan_type_id", "payment_method", "loan_amount",
            "installment_amount", "term", "start_date", "end_date",
            "notes", "state"
        ]
        res = self._call(
            LOAN_MODEL,
            "read",
            [[loan_id]],
            {"fields": read_fields}
        )
        if isinstance(res, list) and res:
            return res[0]
        return None

    def approve_employee_loan(self, loan_id: int, target_state: str = "dep_approval") -> bool:
        """
        تحديث حالة السلفة (dep_approval, hr_approval, paid).
        """
        if not loan_id:
            return False
        res = self._call(
            LOAN_MODEL,
            "write",
            [[loan_id], {"state": target_state}]
        )
        return bool(res)
