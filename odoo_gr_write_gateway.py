from __future__ import annotations

import xmlrpc.client
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS

GR_TRANSACTION_MODEL = "gr.transaction"
_ALLOWED_MODELS = frozenset({GR_TRANSACTION_MODEL})
_ALLOWED_METHODS = frozenset({"create", "write", "read", "search_read"})


class GREnvironmentGuardError(RuntimeError):
    pass


class GRWriteGatewayError(RuntimeError):
    pass


class OdooGRWriteGateway:
    """
    بوابة الكتابة الآمنة والمحصورة للمعاملات الحكومية والجوازات (gr.transaction).
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
            raise GRWriteGatewayError("فشل مصادقة بوابة المعاملات الحكومية في Odoo.")
        self._version = self._common.version()

    @staticmethod
    def _check_environment(db: str) -> None:
        allowed = ALLOWED_TEST_DBS | ALLOWED_DEV_DBS
        if db not in allowed:
            raise GREnvironmentGuardError(
                f"حارس البيئة: قاعدة البيانات '{db}' غير مصرح بها للكتابة."
            )

    def _call(self, model: str, method: str, args: List[Any], kwargs: Optional[Dict[str, Any]] = None):
        if model not in _ALLOWED_MODELS:
            raise GRWriteGatewayError(f"النموذج '{model}' غير مصرح به عبر بوابة المعاملات الحكومية والجوازات.")
        if method not in _ALLOWED_METHODS:
            raise GRWriteGatewayError(f"الإجراء '{method}' غير مصرح به عبر بوابة المعاملات الحكومية.")
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

    def create_gr_transaction(
        self,
        employee_id: int,
        transaction: str,
        transaction_type: str = "party",  # "party" or "split"
        transaction_date: Optional[str] = None,
        responsible_party: str = "company",  # "company" or "employee"
        company_percentage: float = 100.0,
        employee_percentage: float = 0.0,
        amount: float = 0.0,
        name: Optional[str] = None,
        description: Optional[str] = None,
        state: str = "draft",  # "draft" or "confirmed"
    ) -> int:
        """
        إنشاء سجل معاملة حكومية جديدة في Odoo لموديل gr.transaction.
        """
        if not employee_id:
            raise GRWriteGatewayError("معرّف الموظف إلزامي لإنشاء سجل المعاملة الحكومية.")
        if not transaction:
            raise GRWriteGatewayError("نوع المعاملة الحكومية transaction إلزامي.")

        today_iso = date.today().isoformat()
        t_date = transaction_date or today_iso
        ref_name = name or f"GR/{t_date[:7].replace('-', '')}/{transaction[:10]}"

        vals: Dict[str, Any] = {
            "employee_id": employee_id,
            "transaction": transaction,
            "transaction_type": transaction_type,
            "transaction_date": t_date,
            "responsible_party": responsible_party,
            "company_percentage": float(company_percentage),
            "employee_percentage": float(employee_percentage),
            "amount": float(amount),
            "name": ref_name,
            "state": state,
        }

        if description:
            vals["description"] = description

        created_id = self._call(GR_TRANSACTION_MODEL, "create", [vals])
        if isinstance(created_id, list):
            raise GRWriteGatewayError("أرجعت Odoo قائمة بدلاً من معرّف سجل منفرد.")
        return int(created_id)

    def read_gr_transaction(
        self,
        transaction_id: int,
        fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        قراءة سجل المعاملة الحكومية من Odoo لأغراض التحقق المستقل (Readback Verification).
        """
        if not transaction_id:
            return None
        read_fields = fields or [
            "id", "name", "employee_id", "transaction", "transaction_type",
            "transaction_date", "responsible_party", "company_percentage",
            "employee_percentage", "amount", "state", "description"
        ]
        res = self._call(
            GR_TRANSACTION_MODEL,
            "read",
            [[transaction_id]],
            {"fields": read_fields}
        )
        if isinstance(res, list) and res:
            return res[0]
        return None

    def confirm_gr_transaction(self, transaction_id: int) -> bool:
        """
        تحديث حالة المعاملة الحكومية إلى معتمد (confirmed).
        """
        if not transaction_id:
            return False
        res = self._call(
            GR_TRANSACTION_MODEL,
            "write",
            [[transaction_id], {"state": "confirmed"}]
        )
        return bool(res)
