from __future__ import annotations

import xmlrpc.client
from typing import Any, Dict, List, Optional

from environment_policy import ALLOWED_TEST_DBS, ALLOWED_DEV_DBS

# P5-S10: Environment guard consistency - allow both TEST and DEV
ALLOWED_WRITE_DBS = ALLOWED_TEST_DBS | ALLOWED_DEV_DBS

EMPLOYEE_MODEL = "hr.employee"
ALLOWED_WRITE_MODELS = frozenset({
    "hr.employee",
    "hr.department",
    "hr.job",
    "hr.applicant",
    "hr.leave.type",
    "res.company",
})

# P5-S11: Safe fields whitelist - prevent writing sensitive/system fields
SAFE_WRITE_FIELDS = frozenset({
    # hr.employee safe fields
    "name", "work_email", "work_phone", "mobile_phone", "job_id", "department_id",
    "company_id", "parent_id", "coach_id", "work_location_id", "address_id",
    "barcode", "badge", "pin", "work_permit_no", "visa_no", "visa_expire",
    "work_permit_expiration_date", "certificate", "study_field", "study_school",
    "emergency_contact", "emergency_phone", "km_home_work", "gender", "birthday",
    "place_of_birth", "country_of_birth", "marital", "children", "notes",
    "color", "image_1920", "image_1024", "image_512", "image_256", "image_128",
    "active",  # for archive/unarchive
    
    # hr.department safe fields
    "department_id", "manager_id", "parent_id", "note", "color",
    
    # hr.job safe fields
    "job_title", "expected_employees", "no_of_employee", "description",
    
    # Common safe fields
    "note", "description", "sequence", "color",
})

# P5-S11: Sensitive fields - require special approval (not in safe list)
SENSITIVE_FIELDS = frozenset({
    "identification_id", "passport_id", "iqama_id", "bank_account_id",
    "salary", "hourly_cost", "attendance_ids", "leave_ids", "contract_ids",
    "user_id", "resource_id", "resource_calendar_id",  # system fields
})

_ALLOWED_METHODS = frozenset({"create", "read", "write"})


class EnvironmentGuardError(RuntimeError):
    pass


class WriteGatewayError(RuntimeError):
    pass


class OdooWriteGateway:
    def __init__(self, url: str, db: str, login: str, password: str, common=None, models=None):
        self._check_environment(db)
        self.url = url.rstrip("/")
        self.db = db
        self.login = login
        self._password = password
        self._common = common or xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
        self._models = models or xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
        self.uid = self._common.authenticate(self.db, login, password, {})
        if not self.uid:
            raise WriteGatewayError("Authentication failed for write gateway.")
        self._version = self._common.version()

    @staticmethod
    def _check_environment(db: str) -> None:
        # P5-S10: Consistent environment guard - allow TEST and DEV
        if db not in ALLOWED_WRITE_DBS:
            raise EnvironmentGuardError(
                f"Database '{db}' is not in ALLOWED_WRITE_DBS (TEST or DEV). "
                f"Allowed: {sorted(ALLOWED_WRITE_DBS)}"
            )

    def _call(
        self,
        method: str,
        args: List[Any],
        kwargs: Optional[Dict[str, Any]] = None,
        model: str = EMPLOYEE_MODEL,
    ):
        if method not in _ALLOWED_METHODS:
            raise WriteGatewayError(f"Method not permitted by gateway: {method}")
        if model not in ALLOWED_WRITE_MODELS:
            raise WriteGatewayError(f"Model not permitted by write gateway: {model}")
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

    def create_employee(self, values: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> int:
        if not isinstance(values, dict) or not values:
            raise WriteGatewayError("create_employee requires a single non-empty dict.")
        kwargs: Dict[str, Any] = {}
        if context is not None:
            if not isinstance(context, dict):
                raise WriteGatewayError("context must be a dict when provided.")
            kwargs["context"] = context
        created = self._call("create", [values], kwargs)
        if isinstance(created, list):
            raise WriteGatewayError("Gateway received a list result; single-record create expected.")
        return created

    def read_employee(
        self, employee_id: int, fields: List[str], context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {"fields": list(fields)}
        if context is not None:
            if not isinstance(context, dict):
                raise WriteGatewayError("context must be a dict when provided.")
            kwargs["context"] = context
        rows = self._call("read", [[employee_id]], kwargs)
        return rows[0] if rows else None

    def write_record(
        self,
        model: str,
        record_id: int,
        values: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if model not in ALLOWED_WRITE_MODELS:
            raise WriteGatewayError(f"Model not permitted by write gateway: {model}")
        if not isinstance(record_id, int) or record_id <= 0:
            raise WriteGatewayError("write_record requires a positive integer record_id.")
        if not isinstance(values, dict) or not values:
            raise WriteGatewayError("write_record requires a non-empty values dict.")
        
        # P5-S11: Validate fields against whitelist
        unsafe_fields = set(values.keys()) - SAFE_WRITE_FIELDS
        if unsafe_fields:
            # Check if any are sensitive (requires special handling)
            sensitive_found = unsafe_fields & SENSITIVE_FIELDS
            if sensitive_found:
                raise WriteGatewayError(
                    f"P5-S11: Cannot write sensitive fields without approval: {sorted(sensitive_found)}"
                )
            # Unknown fields (not in safe or sensitive lists)
            raise WriteGatewayError(
                f"P5-S11: Fields not in safe whitelist: {sorted(unsafe_fields)}. "
                f"Add to SAFE_WRITE_FIELDS if safe."
            )
        
        kwargs: Dict[str, Any] = {}
        if context is not None:
            if not isinstance(context, dict):
                raise WriteGatewayError("context must be a dict when provided.")
            kwargs["context"] = context
        result = self._call("write", [[record_id], values], kwargs, model=model)
        return bool(result)

    def write_employee(
        self, employee_id: int, values: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> bool:
        return self.write_record(EMPLOYEE_MODEL, employee_id, values, context=context)

