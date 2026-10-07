from __future__ import annotations

import xmlrpc.client
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS

ATTENDANCE_MODEL = "hr.attendance"
_ALLOWED_MODELS = frozenset({ATTENDANCE_MODEL})
_ALLOWED_METHODS = frozenset({"create", "write", "read", "search_read"})


class AttendanceEnvironmentGuardError(RuntimeError):
    pass


class AttendanceWriteGatewayError(RuntimeError):
    pass


class OdooAttendanceWriteGateway:
    """
    بوابة الكتابة الآمنة والمحصورة لموديل الحضور والانصراف (hr.attendance).
    تلتزم بحارس البيئة وعزل الصلاحيات ومنع العمليات غير المصرح بها.
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
            raise AttendanceWriteGatewayError("فشل مصادقة بوابة كتابة الحضور في أودو.")
        self._version = self._common.version()

    @staticmethod
    def _check_environment(db: str) -> None:
        allowed = ALLOWED_TEST_DBS | ALLOWED_DEV_DBS
        if db not in allowed:
            raise AttendanceEnvironmentGuardError(
                f"حارس البيئة: قاعدة البيانات '{db}' غير مصرح بها للكتابة."
            )

    def _call(self, model: str, method: str, args: List[Any], kwargs: Optional[Dict[str, Any]] = None):
        if model not in _ALLOWED_MODELS:
            raise AttendanceWriteGatewayError(f"النموذج '{model}' غير مصرح به عبر بوابة الحضور.")
        if method not in _ALLOWED_METHODS:
            raise AttendanceWriteGatewayError(f"الإجراء '{method}' غير مصرح به عبر بوابة الحضور.")
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

    def check_in(
        self,
        employee_id: int,
        check_in_dt: Optional[datetime] = None,
        in_mode: str = "manual"
    ) -> int:
        """
        تسجيل حركة حضور جديدة (Check-In) لموظف.
        """
        if not employee_id:
            raise AttendanceWriteGatewayError("معرّف الموظف إلزامي لتسجيل الحضور.")

        now_dt = check_in_dt or datetime.utcnow()
        dt_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        date_str = now_dt.strftime("%Y-%m-%d")

        vals = {
            "employee_id": employee_id,
            "check_in": dt_str,
            "date": date_str,
            "in_mode": in_mode,
        }
        created_id = self._call(ATTENDANCE_MODEL, "create", [vals])
        if isinstance(created_id, list):
            raise AttendanceWriteGatewayError("أرجعت أودو قائمة بدلاً من معرّف سجل منفرد.")
        return int(created_id)

    def check_out(
        self,
        attendance_id: int,
        check_out_dt: Optional[datetime] = None,
        out_mode: str = "manual"
    ) -> bool:
        """
        تسجيل حركة انصراف (Check-Out) لسجل حضور مفتوح.
        """
        if not attendance_id:
            raise AttendanceWriteGatewayError("معرّف سجل الحضور إلزامي لتسجيل الانصراف.")

        now_dt = check_out_dt or datetime.utcnow()
        dt_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        vals = {
            "check_out": dt_str,
            "out_mode": out_mode,
        }
        res = self._call(ATTENDANCE_MODEL, "write", [[attendance_id], vals])
        return bool(res)

    def create_attendance_record(self, values: Dict[str, Any]) -> int:
        """
        إنشاء سجل حضور وانصراف مكتمل (Check-In & Check-Out) في Odoo.
        """
        required = ["employee_id", "check_in", "date"]
        for r in required:
            if r not in values or not values[r]:
                raise AttendanceWriteGatewayError(f"الحقل '{r}' مطلوب لإنشاء سجل الحضور.")

        created_id = self._call(ATTENDANCE_MODEL, "create", [values])
        if isinstance(created_id, list):
            raise AttendanceWriteGatewayError("أرجعت أودو قائمة بدلاً من معرّف سجل منفرد.")
        return int(created_id)

    def read_attendance(
        self,
        attendance_id: int,
        fields: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        قراءة تحقق مستقلة (Readback Verification) من سجل الحضور بعد الكتابة.
        """
        rows = self._call(ATTENDANCE_MODEL, "read", [[attendance_id]], {"fields": list(fields)})
        return rows[0] if rows else None
