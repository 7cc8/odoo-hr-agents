from __future__ import annotations

import xmlrpc.client
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS

APPLICANT_MODEL = "hr.applicant"
JOB_MODEL = "hr.job"
STAGE_MODEL = "hr.recruitment.stage"
_ALLOWED_MODELS = frozenset({APPLICANT_MODEL, JOB_MODEL, STAGE_MODEL})
_ALLOWED_METHODS = frozenset({"create", "write", "read", "search_read"})


class RecruitmentEnvironmentGuardError(RuntimeError):
    pass


class RecruitmentWriteGatewayError(RuntimeError):
    pass


class OdooRecruitmentWriteGateway:
    """
    بوابة الكتابة الآمنة والمحصورة لإدارة التوظيف والمرشحين (hr.applicant).
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
            raise RecruitmentWriteGatewayError("فشل مصادقة بوابة التوظيف والمرشحين في Odoo.")
        self._version = self._common.version()

    @staticmethod
    def _check_environment(db: str) -> None:
        allowed = ALLOWED_TEST_DBS | ALLOWED_DEV_DBS
        if db not in allowed:
            raise RecruitmentEnvironmentGuardError(
                f"حارس البيئة: قاعدة البيانات '{db}' غير مصرح بها للكتابة."
            )

    def _call(self, model: str, method: str, args: List[Any], kwargs: Optional[Dict[str, Any]] = None):
        if model not in _ALLOWED_MODELS:
            raise RecruitmentWriteGatewayError(f"النموذج '{model}' غير مصرح به عبر بوابة التوظيف.")
        if method not in _ALLOWED_METHODS:
            raise RecruitmentWriteGatewayError(f"الإجراء '{method}' غير مصرح به عبر بوابة التوظيف.")
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

    def get_default_stage_id(self) -> int:
        """
        الحصول على معرّف المرحلة الأولى لخط أنابيب التوظيف (New / مرحلة التقديم الأولي).
        """
        stages = self._call(STAGE_MODEL, "search_read", [[]], {"fields": ["id", "name", "sequence"], "order": "sequence asc", "limit": 1})
        if stages and isinstance(stages, list) and len(stages) > 0:
            return int(stages[0]["id"])
        return 1

    def create_applicant(
        self,
        partner_name: str,
        job_id: int,
        is_saudi: bool,
        email_from: Optional[str] = None,
        partner_phone: Optional[str] = None,
        id_number: Optional[str] = None,
        passport_number: Optional[str] = None,
        nationality_id: Optional[int] = None,
        department_id: Optional[int] = None,
        stage_id: Optional[int] = None,
        salary_expected: float = 0.0,
        salary_proposed: float = 0.0,
        housing_allowance: float = 0.0,
        transportation_allowance: float = 0.0,
        contract_status: str = "single",
        duration_of_contract: int = 1,
        availability: Optional[str] = None,
        applicant_notes: Optional[str] = None,
        approval_status: str = "draft",
        kanban_state: str = "normal",
    ) -> int:
        """
        إنشاء سجل مرشح/متقدم جديد لموديل hr.applicant في Odoo مع التزام التوطين السعودي.
        """
        if not partner_name or not partner_name.strip():
            raise RecruitmentWriteGatewayError("اسم المرشح إلزامي لإنشاء طلب التوظيف.")
        if not job_id:
            raise RecruitmentWriteGatewayError("معرّف الوظيفة الشاغرة (job_id) إلزامي.")

        # تحديد معرّف الجنسية: 192 للمملكة العربية السعودية تلقائياً
        nat_id = nationality_id
        if not nat_id:
            nat_id = 192 if is_saudi else 64  # Fallback: 192=Saudi, 64=Egypt/Other

        stg_id = stage_id or self.get_default_stage_id()
        total_salary = float(salary_proposed) + float(housing_allowance) + float(transportation_allowance)

        vals: Dict[str, Any] = {
            "partner_name": partner_name.strip(),
            "job_id": job_id,
            "is_saudi": bool(is_saudi),
            "nationality_id": nat_id,
            "contract_status": contract_status if contract_status in ("single", "family") else "single",
            "approval_status": approval_status if approval_status in ("draft", "submitted", "approved") else "draft",
            "kanban_state": kanban_state if kanban_state in ("normal", "done", "waiting", "blocked") else "normal",
            "salary_expected": float(salary_expected),
            "salary_proposed": float(salary_proposed),
            "total_salary": float(total_salary),
            "housing_allowance": float(housing_allowance),
            "transportation_allowance": float(transportation_allowance),
            "duration_of_contract": int(duration_of_contract) if duration_of_contract > 0 else 1,
        }

        if email_from:
            vals["email_from"] = email_from.strip()
        if partner_phone:
            vals["partner_phone"] = partner_phone.strip()
        if id_number:
            vals["id_number"] = id_number.strip()
        if passport_number:
            vals["passport_number"] = passport_number.strip()
        if department_id:
            vals["department_id"] = department_id
        if stg_id:
            vals["stage_id"] = stg_id
        if availability:
            vals["availability"] = availability
        if applicant_notes:
            vals["applicant_notes"] = applicant_notes

        created_id = self._call(APPLICANT_MODEL, "create", [vals])
        if isinstance(created_id, list):
            raise RecruitmentWriteGatewayError("أرجعت Odoo قائمة بدلاً من معرّف سجل منفرد.")
        return int(created_id)

    def read_applicant(
        self,
        applicant_id: int,
        fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        قراءة سجل المرشح من Odoo لأغراض التحقق المستقل (Readback Verification).
        """
        if not applicant_id:
            return None
        read_fields = fields or [
            "id", "partner_name", "job_id", "department_id", "is_saudi",
            "nationality_id", "id_number", "passport_number", "email_from",
            "partner_phone", "stage_id", "salary_expected", "salary_proposed",
            "total_salary", "housing_allowance", "transportation_allowance",
            "contract_status", "duration_of_contract", "approval_status",
            "kanban_state", "availability"
        ]
        res = self._call(
            APPLICANT_MODEL,
            "read",
            [[applicant_id]],
            {"fields": read_fields}
        )
        if isinstance(res, list) and res:
            return res[0]
        return None

    def update_applicant_stage(self, applicant_id: int, target_stage_id: int) -> bool:
        """
        نقل المرشح إلى مرحلة تالية في خط أنابيب التوظيف (First Interview, Contract Proposal, etc.).
        """
        if not applicant_id or not target_stage_id:
            return False
        res = self._call(
            APPLICANT_MODEL,
            "write",
            [[applicant_id], {"stage_id": target_stage_id}]
        )
        return bool(res)

    def update_applicant_approval_status(self, applicant_id: int, status: str = "approved") -> bool:
        """
        اعتماد حالة طلب التوظيف (draft, submitted, approved).
        """
        if not applicant_id:
            return False
        res = self._call(
            APPLICANT_MODEL,
            "write",
            [[applicant_id], {"approval_status": status}]
        )
        return bool(res)
