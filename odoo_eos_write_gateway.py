from __future__ import annotations

import xmlrpc.client
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS

EOS_BENEFIT_MODEL = "hr.end.service.benefit"
EOS_BENEFIT_TYPE_MODEL = "hr.end.service.benefit.type"
_ALLOWED_MODELS = frozenset({EOS_BENEFIT_MODEL, EOS_BENEFIT_TYPE_MODEL})
_ALLOWED_METHODS = frozenset({"create", "write", "read", "search_read"})


class EOSEnvironmentGuardError(RuntimeError):
    pass


class EOSWriteGatewayError(RuntimeError):
    pass


class OdooEOSWriteGateway:
    """
    بوابة الكتابة الآمنة والمحصورة لمكافأة نهاية الخدمة والتسويات (hr_end_of_service_reward).
    تلتزم بحارس البيئة وعزل الصلاحيات وحظر المساس بالنماذج غير المصرح بها.
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
            raise EOSWriteGatewayError("فشل مصادقة بوابة نهاية الخدمة والتسويات في Odoo.")
        self._version = self._common.version()

    @staticmethod
    def _check_environment(db: str) -> None:
        allowed = ALLOWED_TEST_DBS | ALLOWED_DEV_DBS
        if db not in allowed:
            raise EOSEnvironmentGuardError(
                f"حارس البيئة: قاعدة البيانات '{db}' غير مصرح بها للكتابة."
            )

    def _call(self, model: str, method: str, args: List[Any], kwargs: Optional[Dict[str, Any]] = None):
        if model not in _ALLOWED_MODELS:
            raise EOSWriteGatewayError(f"النموذج '{model}' غير مصرح به عبر بوابة نهاية الخدمة والتسويات.")
        if method not in _ALLOWED_METHODS:
            raise EOSWriteGatewayError(f"الإجراء '{method}' غير مصرح به عبر بوابة نهاية الخدمة.")
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

    def create_end_service_benefit(
        self,
        name: str,
        employee_id: int,
        department_id: Optional[int] = None,
        company_id: Optional[int] = None,
        currency_id: int = 1,
        date_str: Optional[str] = None,
        hiring_date: Optional[str] = None,
        reward_type: str = "ending_service",
        payment_type: str = "wage_allowance",
        end_service_benefit_type_id: Optional[int] = None,
        years: int = 0,
        months: int = 0,
        days: int = 0,
        service_period: float = 0.0,
        total_deserved_amount: float = 0.0,
        total_holiday_deserved_amount: float = 0.0,
        total_payslip_deserved_amount: float = 0.0,
        other_amount: float = 0.0,
        other_deduction: float = 0.0,
        total_reward: float = 0.0,
        notes: Optional[str] = None,
        state: str = "draft",
    ) -> int:
        """
        إنشاء سجل تسوية ومكافأة نهاية خدمة جديد في Odoo لموديل hr.end.service.benefit.
        """
        if not employee_id:
            raise EOSWriteGatewayError("معرّف الموظف إلزامي لإنشاء سجل نهاية الخدمة.")
        if not name:
            raise EOSWriteGatewayError("الرقم المرجعي name إلزامي لإنشاء سجل نهاية الخدمة.")

        today_iso = date.today().isoformat()
        settlement_date = date_str or today_iso

        vals: Dict[str, Any] = {
            "name": name,
            "employee_id": employee_id,
            "date": settlement_date,
            "type": reward_type,
            "payment_type": payment_type,
            "currency_id": currency_id,
            "years": int(years),
            "months": int(months),
            "days": int(days),
            "service_period": float(service_period),
            "total_deserved_amount": float(total_deserved_amount),
            "total_holiday_deserved_amount": float(total_holiday_deserved_amount),
            "total_payslip_deserved_amount": float(total_payslip_deserved_amount),
            "other_amount": float(other_amount),
            "other_deduction": float(other_deduction),
            "total_reward": float(total_reward),
            "amount": float(total_reward),
            "state": state,
        }

        if department_id:
            vals["department_id"] = department_id
        if company_id:
            vals["company_id"] = company_id
        if hiring_date:
            vals["hiring_date"] = hiring_date
        if end_service_benefit_type_id:
            vals["end_service_benefit_type_id"] = end_service_benefit_type_id
        if notes:
            vals["notes"] = notes

        created_id = self._call(EOS_BENEFIT_MODEL, "create", [vals])
        if isinstance(created_id, list):
            raise EOSWriteGatewayError("أرجعت Odoo قائمة بدلاً من معرّف سجل منفرد.")
        return int(created_id)

    def read_end_service_benefit(
        self,
        eos_id: int,
        fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        قراءة سجل نهاية الخدمة من Odoo لأغراض التحقق المستقل (Readback Verification).
        """
        if not eos_id:
            return None
        read_fields = fields or [
            "id", "name", "employee_id", "department_id", "date", "hiring_date",
            "type", "payment_type", "years", "months", "days", "service_period",
            "total_deserved_amount", "total_holiday_deserved_amount",
            "total_payslip_deserved_amount", "other_amount", "other_deduction",
            "total_reward", "amount", "state", "notes"
        ]
        res = self._call(
            EOS_BENEFIT_MODEL,
            "read",
            [[eos_id]],
            {"fields": read_fields}
        )
        if isinstance(res, list) and res:
            return res[0]
        return None

    def confirm_end_service_benefit(self, eos_id: int) -> bool:
        """
        تحديث حالة سجل نهاية الخدمة إلى معتمد (confirmed).
        """
        if not eos_id:
            return False
        res = self._call(
            EOS_BENEFIT_MODEL,
            "write",
            [[eos_id], {"state": "confirmed"}]
        )
        return bool(res)
