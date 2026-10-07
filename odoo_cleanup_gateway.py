from __future__ import annotations

import xmlrpc.client
from typing import Any, Dict, Optional

from environment_policy import ALLOWED_TEST_DBS

EMPLOYEE_MODEL = "hr.employee"


class CleanupEnvironmentGuardError(RuntimeError):
    pass


class CleanupGatewayError(RuntimeError):
    pass


class OdooCleanupGateway:
    """Test-only gateway for deleting explicitly supplied employee IDs."""

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
            raise CleanupGatewayError("Authentication failed for cleanup gateway.")

    @staticmethod
    def _check_environment(db: str) -> None:
        if db not in ALLOWED_TEST_DBS:
            raise CleanupEnvironmentGuardError(f"Database is not in ALLOWED_TEST_DBS: {db}")

    def get_session_info(self) -> Dict[str, Any]:
        return {
            "odoo_url": self.url,
            "odoo_db": self.db,
            "uid": self.uid,
            "login": self.login,
        }

    def delete_employee_for_test_cleanup(self, employee_id: int) -> bool:
        if not isinstance(employee_id, int) or employee_id <= 0:
            raise CleanupGatewayError(
                "delete_employee_for_test_cleanup requires a positive integer employee ID."
            )

        self._check_environment(self.db)
        deleted = self._models.execute_kw(
            self.db,
            self.uid,
            self._password,
            EMPLOYEE_MODEL,
            "unlink",
            [[employee_id]],
            {},
        )
        if deleted is not True:
            raise CleanupGatewayError(
                f"Unexpected unlink result for employee {employee_id}: {deleted!r}"
            )
        return True
