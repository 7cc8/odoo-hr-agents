from __future__ import annotations

import xmlrpc.client
from typing import Any, Dict, List, Optional

from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS

LEAVE_MODEL = "hr.leave"
ALLOCATION_MODEL = "hr.leave.allocation"
_ALLOWED_MODELS = frozenset({LEAVE_MODEL, ALLOCATION_MODEL})
_ALLOWED_METHODS = frozenset({"create", "read", "search_read", "action_confirm", "action_validate"})


class LeaveEnvironmentGuardError(RuntimeError):
    pass


class LeaveWriteGatewayError(RuntimeError):
    pass


class OdooLeaveWriteGateway:
    """
    بوابة الكتابة الآمنة والمحصورة لموديل الإجازات (hr.leave) ومخصصات الإجازات (hr.leave.allocation).
    تلتزم تماماً بحارس البيئة وعزل الصلاحيات وحظر التعديل العشوائي.
    """
    def __init__(self, url: str, db: str, login: str, password: str, common=None, models=None):
        self._check_environment(db)
        self.url = url.rstrip("/")
        self.db = db
        self.login = login
        self._password = password
        self._common = common or xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
        self._models = models or xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)
        self.uid = self._common.authenticate(self.db, login, password, {})
        if not self.uid:
            raise LeaveWriteGatewayError("فشل مصادقة بوابة كتابة الإجازات في أودو.")
        self._version = self._common.version()

    @staticmethod
    def _check_environment(db: str) -> None:
        allowed = ALLOWED_TEST_DBS | ALLOWED_DEV_DBS
        if db not in allowed:
            raise LeaveEnvironmentGuardError(
                f"حارس البيئة: قاعدة البيانات '{db}' غير مدرجة ضمن قواعد الاختبار المصرح بها للكتابة."
            )

    def _call(self, model: str, method: str, args: List[Any], kwargs: Optional[Dict[str, Any]] = None):
        if model not in _ALLOWED_MODELS:
            raise LeaveWriteGatewayError(f"النموذج '{model}' غير مصرح به عبر بوابة كتابة الإجازات.")
        if method not in _ALLOWED_METHODS:
            raise LeaveWriteGatewayError(f"الإجراء '{method}' غير مصرح به عبر بوابة كتابة الإجازات.")
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

    def create_leave(self, values: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> int:
        """
        إنشاء طلب إجازة في hr.leave مع التحقق المسبق من الحقول الإلزامية.
        """
        if not isinstance(values, dict) or not values:
            raise LeaveWriteGatewayError("قيم طلب الإجازة يجب أن تكون قاموساً غير فارغ.")
        
        required_fields = ["employee_id", "holiday_status_id"]
        for rf in required_fields:
            if rf not in values or not values[rf]:
                raise LeaveWriteGatewayError(f"حقل إلزامي مفقود في طلب الإجازة: {rf}")

        kwargs: Dict[str, Any] = {}
        if context is not None:
            if not isinstance(context, dict):
                raise LeaveWriteGatewayError("السياق context يجب أن يكون قاموساً.")
            kwargs["context"] = context

        created_id = self._call(LEAVE_MODEL, "create", [values], kwargs)
        if isinstance(created_id, list):
            raise LeaveWriteGatewayError("أرجعت أودو قائمة بدلاً من معرّف سجل منفرد.")
        return int(created_id)

    def read_leave(
        self, leave_id: int, fields: List[str], context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        قراءة تحقق من سجل الإجازة بعد إنشائه للتأكد من نجاح الكتابة ومطابقة القيم.
        """
        kwargs: Dict[str, Any] = {"fields": list(fields)}
        if context is not None:
            if not isinstance(context, dict):
                raise LeaveWriteGatewayError("context must be a dict.")
            kwargs["context"] = context
        rows = self._call(LEAVE_MODEL, "read", [[leave_id]], kwargs)
        return rows[0] if rows else None

    def create_allocation(self, values: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> int:
        """
        إنشاء رصيد إجازة (allocation) لموظف عند الحاجة وفق الضوابط النظامية.
        """
        if not isinstance(values, dict) or not values:
            raise LeaveWriteGatewayError("قيم رصيد الإجازة يجب أن تكون قاموساً غير فارغ.")
        
        required_fields = ["employee_id", "holiday_status_id", "number_of_days"]
        for rf in required_fields:
            if rf not in values or not values[rf]:
                raise LeaveWriteGatewayError(f"حقل إلزامي مفقود في رصيد الإجازة: {rf}")

        kwargs: Dict[str, Any] = {}
        if context is not None:
            kwargs["context"] = context

        created_id = self._call(ALLOCATION_MODEL, "create", [values], kwargs)
        if isinstance(created_id, list):
            raise LeaveWriteGatewayError("أرجعت أودو قائمة بدلاً من معرّف رصيد منفرد.")
        return int(created_id)
