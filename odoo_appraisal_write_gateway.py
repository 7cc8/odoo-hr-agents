from __future__ import annotations

import xmlrpc.client
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS

APPRAISAL_REQUEST_MODEL = "appraisal.request"
_ALLOWED_MODELS = frozenset({APPRAISAL_REQUEST_MODEL})
_ALLOWED_METHODS = frozenset({"create", "write", "read", "search_read"})


class AppraisalEnvironmentGuardError(RuntimeError):
    pass


class AppraisalWriteGatewayError(RuntimeError):
    pass


class OdooAppraisalWriteGateway:
    """
    بوابة الكتابة الآمنة والمحصورة لتقييمات الأداء والموظفين (appraisal.request).
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
            raise AppraisalWriteGatewayError("فشل مصادقة بوابة تقييمات الأداء في Odoo.")
        self._version = self._common.version()

    @staticmethod
    def _check_environment(db: str) -> None:
        allowed = ALLOWED_TEST_DBS | ALLOWED_DEV_DBS
        if db not in allowed:
            raise AppraisalEnvironmentGuardError(
                f"حارس البيئة: قاعدة البيانات '{db}' غير مصرح بها للكتابة."
            )

    def _call(self, model: str, method: str, args: List[Any], kwargs: Optional[Dict[str, Any]] = None):
        if model not in _ALLOWED_MODELS:
            raise AppraisalWriteGatewayError(f"النموذج '{model}' غير مصرح به عبر بوابة تقييمات الأداء.")
        if method not in _ALLOWED_METHODS:
            raise AppraisalWriteGatewayError(f"الإجراء '{method}' غير مصرح به عبر بوابة تقييمات الأداء.")
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

    def create_appraisal_request(
        self,
        employee_id: int,
        name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        evaluation_date: Optional[str] = None,
        department_id: Optional[int] = None,
        job_id: Optional[int] = None,
        manager_id: Optional[int] = None,
        final_percentage: float = 0.0,
        total_points_earned: float = 0.0,
        max_possible_points: float = 100.0,
        manager_comments: Optional[str] = None,
        notes: Optional[str] = None,
        state: str = "draft",
    ) -> int:
        """
        إنشاء سجل تقييم أداء جديد لموديل appraisal.request في Odoo.
        """
        if not employee_id:
            raise AppraisalWriteGatewayError("معرّف الموظف إلزامي لإنشاء سجل تقييم الأداء.")
        if not name:
            raise AppraisalWriteGatewayError("عنوان التقييم name إلزامي.")

        today_iso = date.today().isoformat()
        s_date = start_date or today_iso

        vals: Dict[str, Any] = {
            "employee_id": employee_id,
            "name": name,
            "start_date": s_date,
            "final_percentage": float(final_percentage),
            "total_points_earned": float(total_points_earned),
            "max_possible_points": float(max_possible_points),
            "state": state,
        }

        if end_date:
            vals["end_date"] = end_date
        if evaluation_date:
            vals["evaluation_date"] = evaluation_date
        if department_id:
            vals["department_id"] = department_id
        if job_id:
            vals["job_id"] = job_id
        if manager_id:
            vals["manager_id"] = manager_id
        if manager_comments:
            vals["manager_comments"] = manager_comments
        if notes:
            vals["notes"] = notes

        created_id = self._call(APPRAISAL_REQUEST_MODEL, "create", [vals])
        if isinstance(created_id, list):
            raise AppraisalWriteGatewayError("أرجعت Odoo قائمة بدلاً من معرّف سجل منفرد.")
        return int(created_id)

    def read_appraisal_request(
        self,
        appraisal_id: int,
        fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        قراءة سجل التقييم من Odoo لأغراض التحقق المستقل (Readback Verification).
        """
        if not appraisal_id:
            return None
        read_fields = fields or [
            "id", "name", "employee_id", "department_id", "job_id",
            "manager_id", "start_date", "end_date", "evaluation_date",
            "final_percentage", "total_points_earned", "max_possible_points",
            "state", "manager_comments", "notes"
        ]
        res = self._call(
            APPRAISAL_REQUEST_MODEL,
            "read",
            [[appraisal_id]],
            {"fields": read_fields}
        )
        if isinstance(res, list) and res:
            return res[0]
        return None

    def complete_appraisal_request(self, appraisal_id: int) -> bool:
        """
        تحديث حالة تقييم الأداء إلى مكتمل (completed).
        """
        if not appraisal_id:
            return False
        res = self._call(
            APPRAISAL_REQUEST_MODEL,
            "write",
            [[appraisal_id], {"state": "completed"}]
        )
        return bool(res)
