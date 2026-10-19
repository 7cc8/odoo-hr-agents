"""Fail-closed employee lookup used by the validator's duplicate check.

Why this exists
---------------
``OdooReadonlyRepository.search_employee_candidates`` swallows every exception
and returns ``[]``.  For the validator that means "Odoo failed" and "no such
employee" look identical, so a broken lookup (access rights, network, bad
domain) silently disables duplicate detection and rows become ``accepted``.

This helper raises on failure instead, so the caller can mark the row
``needs_review`` rather than accepting it unchecked.

Behaviour
---------
* Repository exposing ``_execute_kw`` / ``_base_context`` (the real Odoo
  repository): runs one strict ``hr.employee`` search by work_email and lets
  any exception propagate.
* Any other object (test doubles): falls back to
  ``search_employee_email_candidates`` unchanged.

TODO: once ``odoo_readonly_repository.py`` gets a ``raise_on_error`` option on
``search_employee_candidates``, delete the private-attribute path here.
"""
from __future__ import annotations

from typing import Any, Dict, List

EMPLOYEE_LOOKUP_FIELDS = [
    "id", "name", "work_email", "mobile_phone", "work_phone", "company_id",
    "department_id", "job_id", "identification_id", "active",
]


def find_employees_by_email(repository: Any, email: str, limit: int = 20) -> List[Dict[str, Any]]:
    email = (email or "").strip()
    if not email:
        return []

    execute = getattr(repository, "_execute_kw", None)
    base_context = getattr(repository, "_base_context", None)
    if not callable(execute) or not callable(base_context):
        return repository.search_employee_email_candidates(email_fragment=email, limit=limit)

    company_ids = repository.get_company_ids()
    condition = ["work_email", "ilike", email]
    domain: List[Any] = ["&", ["company_id", "in", company_ids], condition] if company_ids else [condition]
    return execute(
        "hr.employee", "search_read", [domain],
        {"fields": EMPLOYEE_LOOKUP_FIELDS, "context": base_context(),
         "limit": limit, "order": "name asc, id asc"},
    )
