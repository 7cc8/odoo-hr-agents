from __future__ import annotations

import xmlrpc.client
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS

DISCIPLINARY_ACTION_MODEL = "disciplinary.action"
DISCIPLINE_CATEGORY_MODEL = "discipline.category"
_ALLOWED_MODELS = frozenset({DISCIPLINARY_ACTION_MODEL, DISCIPLINE_CATEGORY_MODEL})
_ALLOWED_METHODS = frozenset({"create", "write", "read", "search_read"})


class DisciplinaryEnvironmentGuardError(RuntimeError):
    pass


class DisciplinaryWriteGatewayError(RuntimeError):
    pass


class OdooDisciplinaryWriteGateway:
    """
    بوابة الكتابة الآمنة والمحصورة لمنظومة الجزاءات والمخالفات (nthub_hr_disciplinary).
    تلتزم بحارس البيئة وعزل الصلاحيات ومنع العمليات غير المصرح بها على النماذج الأخرى.
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
            raise DisciplinaryWriteGatewayError("فشل مصادقة بوابة كتابة الجزاءات في Odoo.")
        self._version = self._common.version()

    @staticmethod
    def _check_environment(db: str) -> None:
        allowed = ALLOWED_TEST_DBS | ALLOWED_DEV_DBS
        if db not in allowed:
            raise DisciplinaryEnvironmentGuardError(
                f"حارس البيئة: قاعدة البيانات '{db}' غير مصرح بها للكتابة."
            )

    def _call(self, model: str, method: str, args: List[Any], kwargs: Optional[Dict[str, Any]] = None):
        if model not in _ALLOWED_MODELS:
            raise DisciplinaryWriteGatewayError(f"النموذج '{model}' غير مصرح به عبر بوابة الجزاءات والانضباط.")
        if method not in _ALLOWED_METHODS:
            raise DisciplinaryWriteGatewayError(f"الإجراء '{method}' غير مصرح به عبر بوابة الجزاءات.")
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

    def create_disciplinary_action(
        self,
        name: str,
        employee_id: int,
        department_id: int,
        discipline_date: str,
        discipline_reason: str,
        category_type: str = "action",  # "action" (by days) or "disciplinary" (by amount)
        number_of_days: float = 0.0,
        amount: float = 0.0,
        occurrence: str = "first",  # "first", "second", "third", "fourth"
        explanation: Optional[str] = None,
        manager_response: Optional[str] = None,
        action_details: Optional[str] = None,
        action_type_id: Optional[int] = None,
        state: str = "draft",  # "draft", "explain", "submitted", "action"
    ) -> int:
        """
        إنشاء سجل جزاء تأديبي جديد في Odoo لموديل disciplinary.action.
        """
        if not employee_id:
            raise DisciplinaryWriteGatewayError("معرّف الموظف إلزامي لإنشاء سجل الجزاء التأديبي.")
        if not name:
            raise DisciplinaryWriteGatewayError("الرقم المرجعي name إلزامي لإنشاء الجزاء التأديبي.")
        if not discipline_date:
            raise DisciplinaryWriteGatewayError("تاريخ المخالفة discipline_date إلزامي.")

        vals: Dict[str, Any] = {
            "name": name,
            "employee_name": employee_id,
            "department_name": department_id,
            "discipline_date": discipline_date,
            "discipline_reason": discipline_reason or "",
            "category_type": category_type,
            "number_of_days": float(number_of_days or 0.0),
            "amount": float(amount or 0.0),
            "occurrence": occurrence,
            "state": state,
        }
        if explanation:
            vals["explanation"] = explanation
        if manager_response:
            vals["manager_response"] = manager_response
        if action_details:
            vals["action_details"] = action_details
        if action_type_id:
            vals["action_type_id"] = action_type_id

        created_id = self._call(DISCIPLINARY_ACTION_MODEL, "create", [vals])
        if isinstance(created_id, list):
            raise DisciplinaryWriteGatewayError("أرجعت Odoo قائمة بدلاً من معرّف سجل منفرد.")
        return int(created_id)

    def read_disciplinary_action(
        self,
        action_id: int,
        fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        قراءة سجل جزاء تأديبي من Odoo لأغراض التحقق المستقل (Readback Verification).
        """
        if not action_id:
            return None
        read_fields = fields or [
            "id", "name", "employee_name", "department_name", "discipline_date",
            "discipline_reason", "category_type", "number_of_days", "amount",
            "occurrence", "state", "explanation"
        ]
        res = self._call(
            DISCIPLINARY_ACTION_MODEL,
            "read",
            [[action_id]],
            {"fields": read_fields}
        )
        if res and isinstance(res, list) and len(res) > 0:
            return res[0]
        return None

    def update_disciplinary_action_state(
        self,
        action_id: int,
        state: str
    ) -> bool:
        """
        تحديث حالة الجزاء التأديبي (e.g. draft -> submitted -> action).
        """
        if not action_id:
            raise DisciplinaryWriteGatewayError("معرّف سجل الجزاء إلزامي لتحديث الحالة.")
        return bool(self._call(
            DISCIPLINARY_ACTION_MODEL,
            "write",
            [[action_id], {"state": state}]
        ))

    def create_discipline_category(
        self,
        code: str,
        name: str
    ) -> int:
        """
        إنشاء تصنيف مخالفة/جزاء في discipline.category.
        """
        if not code or not name:
            raise DisciplinaryWriteGatewayError("الكود والاسم إلزاميان لتصنيف المخالفة.")
        vals = {"code": code, "name": name}
        created_id = self._call(DISCIPLINE_CATEGORY_MODEL, "create", [vals])
        return int(created_id)
