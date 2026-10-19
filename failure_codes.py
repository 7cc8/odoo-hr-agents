"""Single source of truth for Path A failure codes and their final status.

Every stage (parser, validator, and later the writer) must import failure
code strings from this module. Never hardcode a failure-code string literal
anywhere else in the codebase — that duplication is exactly what caused
insufficient_duplicate_signal and invalid_work_email to drift out of sync
with the documented failure table.
"""

from __future__ import annotations

# --- Siraj / parser stage ---
TEMPLATE_ERROR = "template_error"
NORMALIZATION_ERROR = "normalization_error"
DUPLICATE_IN_FILE = "duplicate_in_file"

# --- Fahes / live-reference stage ---
REFERENCE_NOT_FOUND = "reference_not_found"
REFERENCE_AMBIGUOUS = "reference_ambiguous"
COMPANY_MEMBERSHIP_ERROR = "company_membership_error"

# --- Mudaqqiq / validator decision stage ---
DUPLICATE_EXISTING_EMPLOYEE = "duplicate_existing_employee"
UNVERIFIED_NO_EMAIL = "unverified_no_email"
INSUFFICIENT_DUPLICATE_SIGNAL = "insufficient_duplicate_signal"
INVALID_WORK_EMAIL = "invalid_work_email"
DUPLICATE_CHECK_UNAVAILABLE = "duplicate_check_unavailable"

# --- Katib / writer stage (reserved; writer.py is not yet built) ---
APPROVAL_STALE = "approval_stale"
REFERENCE_CHANGED = "reference_changed"
ACCESS_ERROR = "access_error"
VALIDATION_ERROR = "validation_error"
MODULE_CONFLICT = "module_conflict"
SYSTEM_ERROR = "system_error"
ENVIRONMENT_GUARD_ERROR = "environment_guard_error"

# أضف مع باقي الثوابت في failure_codes.py:
ARCHIVED_REFERENCE_MATCH = "archived_reference_match"
AMBIGUOUS_DUPLICATE = "ambiguous_duplicate"
POSSIBLE_DUPLICATE_IN_FILE = "possible_duplicate_in_file"


# Maps every known failure code to exactly one final row status. This is
# the enforcement point that prevents a code from silently drifting to a
# different status than what the documentation promises.
STATUS_BY_FAILURE_CODE = {
    ARCHIVED_REFERENCE_MATCH: "needs_review",
    AMBIGUOUS_DUPLICATE: "needs_review",
    POSSIBLE_DUPLICATE_IN_FILE: "needs_review",
    TEMPLATE_ERROR: "rejected",
    NORMALIZATION_ERROR: "rejected",
    DUPLICATE_IN_FILE: "needs_review",
    REFERENCE_NOT_FOUND: "rejected",
    REFERENCE_AMBIGUOUS: "needs_review",
    COMPANY_MEMBERSHIP_ERROR: "rejected",
    DUPLICATE_EXISTING_EMPLOYEE: "needs_review",
    UNVERIFIED_NO_EMAIL: "needs_review",
    INSUFFICIENT_DUPLICATE_SIGNAL: "needs_review",
    INVALID_WORK_EMAIL: "rejected",
    DUPLICATE_CHECK_UNAVAILABLE: "needs_review",
    APPROVAL_STALE: "failed",
    REFERENCE_CHANGED: "failed",
    ACCESS_ERROR: "failed",
    VALIDATION_ERROR: "failed",
    MODULE_CONFLICT: "failed",
    SYSTEM_ERROR: "failed",
    ENVIRONMENT_GUARD_ERROR: "failed",
}

ALL_FAILURE_CODES = frozenset(STATUS_BY_FAILURE_CODE)


def status_for_failure_code(failure_code: str | None) -> str | None:
    """Returns the single allowed final_status for a given failure_code.

    Returns None when failure_code is None (i.e. accepted/created rows
    have no failure code). Raises KeyError for any code not registered
    in STATUS_BY_FAILURE_CODE — this is intentional: an unknown code must
    fail loudly during development, not pass silently into a report.
    """
    if failure_code is None:
        return None
    if failure_code not in STATUS_BY_FAILURE_CODE:
        raise KeyError(
            f"Unknown failure_code: {failure_code!r}. "
            "Register it in failure_codes.py before using it anywhere else."
        )
    return STATUS_BY_FAILURE_CODE[failure_code]