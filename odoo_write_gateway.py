from __future__ import annotations

import xmlrpc.client
from typing import Any, Dict, List, Optional

from environment_policy import ALLOWED_TEST_DBS

EMPLOYEE_MODEL = "hr.employee"
ALLOWED_WRITE_MODELS = frozenset({
    "hr.employee",
    "hr.department",
    "hr.job",
    "hr.applicant",
    "hr.leave.type",
    "res.company",
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
        if db not in ALLOWED_TEST_DBS:
            raise EnvironmentGuardError(f"Database is not in ALLOWED_TEST_DBS: {db}")

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

