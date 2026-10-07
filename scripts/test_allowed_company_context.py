"""Probe whether allowed_company_ids constrains an hr.employee create."""

from __future__ import annotations

import os
import sys
import time
import xmlrpc.client
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from environment_policy import ALLOWED_TEST_DBS
from odoo_cleanup_gateway import OdooCleanupGateway
from odoo_readonly_repository import OdooReadonlyRepository

VISIBLE_COMPANY_ID = 15
TARGET_COMPANY_ID = 17


repository = OdooReadonlyRepository()
repository.connect()
if repository.db not in ALLOWED_TEST_DBS:
    raise RuntimeError(f"Database is not in ALLOWED_TEST_DBS: {repository.db}")

accessible_company_ids = {company["id"] for company in repository.get_accessible_companies()}
if not {VISIBLE_COMPANY_ID, TARGET_COMPANY_ID}.issubset(accessible_company_ids):
    raise RuntimeError(
        f"Required companies are not accessible: {accessible_company_ids}"
    )

models = repository._models
cleanup_gateway = OdooCleanupGateway(
    url=repository.url,
    db=repository.db,
    login=repository.username,
    password=repository.api_key,
)
context = {"allowed_company_ids": [VISIBLE_COMPANY_ID]}
values = {
    "name": "ALLOWED COMPANY CONTEXT PROBE",
    "work_email": f"allowed-company-context.{int(time.time())}@example.com",
    "company_id": TARGET_COMPANY_ID,
}
employee_id = None


def printable_error(exc: Exception) -> str:
    return str(exc).encode("ascii", "backslashreplace").decode("ascii")

print("context =", context)
print("values =", values)
try:
    try:
        employee_id = models.execute_kw(
            repository.db,
            repository.uid,
            repository.api_key,
            "hr.employee",
            "create",
            [values],
            {"context": context},
        )
        print("create_result =", {"status": "succeeded", "employee_id": employee_id})

        readback = models.execute_kw(
            repository.db,
            repository.uid,
            repository.api_key,
            "hr.employee",
            "read",
            [[employee_id]],
            {
                "fields": ["id", "name", "work_email", "company_id", "active"],
                "context": context,
            },
        )
        print("readback_with_context =", readback)
    except (xmlrpc.client.Fault, OSError, xmlrpc.client.ProtocolError) as exc:
        print("create_result =", {
            "status": "failed",
            "error": f"{type(exc).__name__}: {printable_error(exc)}",
        })
finally:
    if employee_id:
        print("cleanup_result =", cleanup_gateway.delete_employee_for_test_cleanup(employee_id))
        after = repository._execute_kw(
            "hr.employee",
            "search_read",
            [[["id", "=", employee_id]]],
            {
                "fields": ["id", "name", "work_email", "company_id", "active"],
                "context": {"active_test": False},
            },
        )
        print("read_after_cleanup =", after)
        if after:
            raise RuntimeError(f"Probe employee still exists after cleanup: {after!r}")
