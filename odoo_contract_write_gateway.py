from __future__ import annotations

import xmlrpc.client
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS

CONTRACT_VERSION_MODEL = "hr.version"
CONTRACT_ALLOWANCE_MODEL = "hr.version.allowance"
CONTRACT_TYPE_MODEL = "hr.contract.type"
_ALLOWED_MODELS = frozenset({CONTRACT_VERSION_MODEL, CONTRACT_ALLOWANCE_MODEL, CONTRACT_TYPE_MODEL})
_ALLOWED_METHODS = frozenset({"create", "write", "read", "search_read"})


class ContractEnvironmentGuardError(RuntimeError):
    pass


class ContractWriteGatewayError(RuntimeError):
    pass


class OdooContractWriteGateway:
    """
    بوابة الكتابة الآمنة والمحصورة لعقود العمل وهيكلة الأجور في Odoo (hr.version).
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
            raise ContractWriteGatewayError("فشل مصادقة بوابة عقود العمل في Odoo.")
        self._version = self._common.version()

    @staticmethod
    def _check_environment(db: str) -> None:
        allowed = ALLOWED_TEST_DBS | ALLOWED_DEV_DBS
        if db not in allowed:
            raise ContractEnvironmentGuardError(
                f"حارس البيئة: قاعدة البيانات '{db}' غير مصرح بها للكتابة."
            )

    def _call(self, model: str, method: str, args: List[Any], kwargs: Optional[Dict[str, Any]] = None):
        if model not in _ALLOWED_MODELS:
            raise ContractWriteGatewayError(f"النموذج '{model}' غير مصرح به عبر بوابة العقود.")
        if method not in _ALLOWED_METHODS:
            raise ContractWriteGatewayError(f"الإجراء '{method}' غير مصرح به عبر بوابة العقود.")
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

    def update_or_create_contract(
        self,
        employee_id: int,
        wage: float,
        is_saudi: bool,
        housing_allowance: float = 0.0,
        transportation_allowance: float = 0.0,
        other_allowances: float = 0.0,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        trial_date_end: Optional[str] = None,
        contract_type_id: Optional[int] = None,
        gosi_deduction: bool = True,
        notes: Optional[str] = None,
    ) -> int:
        """
        تحديث أو إنشاء عقد عمل وهيكلة أجور للموظف (hr.version) في Odoo.
        """
        if not employee_id:
            raise ContractWriteGatewayError("معرّف الموظف إلزامي لتوثيق العقد.")
        if wage <= 0:
            raise ContractWriteGatewayError("الأجر الأساسي للعقد يجب أن يكون أكبر من الصفر.")

        total_package = float(wage) + float(housing_allowance) + float(transportation_allowance) + float(other_allowances)
        today_iso = date.today().isoformat()
        start_d = date_start or today_iso

        vals: Dict[str, Any] = {
            "wage": float(wage),
            "l10n_sa_housing_allowance": float(housing_allowance),
            "l10n_sa_transportation_allowance": float(transportation_allowance),
            "l10n_sa_other_allowances": float(other_allowances),
            "total": float(total_package),
            "is_saudi": bool(is_saudi),
            "gosi_deduction": bool(gosi_deduction),
            "date_start": start_d,
        }

        if date_end:
            vals["date_end"] = date_end
        if trial_date_end:
            vals["trial_date_end"] = trial_date_end
        if contract_type_id:
            vals["contract_type_id"] = contract_type_id

        # البحث عن سجل العقد/النسخة الحالي للموظف
        existing_versions = self._call(
            CONTRACT_VERSION_MODEL,
            "search_read",
            [[["employee_id", "=", employee_id]]],
            {"fields": ["id", "employee_id"], "limit": 1}
        )

        if existing_versions and isinstance(existing_versions, list) and len(existing_versions) > 0:
            first_item = existing_versions[0]
            version_id = int(first_item["id"]) if isinstance(first_item, dict) else int(first_item)
            self._call(CONTRACT_VERSION_MODEL, "write", [[version_id], vals])
            return version_id
        else:
            # إنشاء سجل عقد/نسخة جديد للموظف
            vals["employee_id"] = employee_id
            vals["name"] = f"عقد عمل - موظف #{employee_id}"
            created_id = self._call(CONTRACT_VERSION_MODEL, "create", [vals])
            if isinstance(created_id, list):
                raise ContractWriteGatewayError("أرجعت Odoo قائمة بدلاً من معرّف سجل منفرد.")
            return int(created_id)

    def read_contract(
        self,
        contract_id: int,
        fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        قراءة سجل العقد من Odoo لأغراض التحقق المستقل (Readback Verification).
        """
        if not contract_id:
            return None
        read_fields = fields or [
            "id", "name", "employee_id", "department_id", "job_id", "wage",
            "l10n_sa_housing_allowance", "l10n_sa_transportation_allowance",
            "l10n_sa_other_allowances", "total", "is_saudi", "date_start",
            "date_end", "trial_date_end", "contract_type_id", "gosi_deduction",
            "gosi_employee_deduction", "gosi_rate"
        ]
        res = self._call(
            CONTRACT_VERSION_MODEL,
            "read",
            [[contract_id]],
            {"fields": read_fields}
        )
        if isinstance(res, list) and res:
            return res[0]
        return None
