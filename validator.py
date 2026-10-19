from __future__ import annotations

from difflib import get_close_matches
from typing import Any, Dict, List, Optional

from failure_codes import (
    INSUFFICIENT_DUPLICATE_SIGNAL,
    UNVERIFIED_NO_EMAIL,
    POSSIBLE_DUPLICATE_IN_FILE,
    DUPLICATE_EXISTING_EMPLOYEE,
    AMBIGUOUS_DUPLICATE,
    INVALID_WORK_EMAIL,
    DUPLICATE_CHECK_UNAVAILABLE,
    DUPLICATE_IN_FILE,
    REFERENCE_NOT_FOUND,
    REFERENCE_AMBIGUOUS,
    ARCHIVED_REFERENCE_MATCH,
    VALIDATION_ERROR,
)
from employee_lookup import find_employees_by_email
from normalization import reference_match_key, is_valid_email_format

FINAL_ACCEPTED = "accepted"
FINAL_NEEDS_REVIEW = "needs_review"
FINAL_REJECTED = "rejected"


def safe_many2one_id(value) -> Optional[int]:
    if not value:
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 1:
        candidate = value[0]
        if isinstance(candidate, int):
            return candidate
    return None


def safe_many2one_dict(value) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return {"id": value[0], "name": value[1]}
    return None


def normalize_email_exact(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.strip().lower()


def suggest_closest_reference_name(
    requested_value: Optional[str],
    candidate_names: List[str],
) -> Optional[str]:
    requested_key = reference_match_key(requested_value or "")
    normalized_to_original = {
        reference_match_key(name or ""): name
        for name in candidate_names
        if name and reference_match_key(name or "")
    }
    if not requested_key or not normalized_to_original:
        return None

    closest = get_close_matches(requested_key, list(normalized_to_original.keys()), n=1, cutoff=0.6)
    if not closest:
        return None
    return normalized_to_original[closest[0]]


class ValidationResult:
    def __init__(self, excel_row_number, final_status, failure_code, reasons,
                 resolved_references=None, run_id=None, row_hash=None, source_hash=None):
        self.excel_row_number = excel_row_number
        self.final_status = final_status
        self.failure_code = failure_code
        self.reasons = reasons
        self.resolved_references = resolved_references or {}
        self.run_id = run_id
        self.row_hash = row_hash
        self.source_hash = source_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "excel_row_number": self.excel_row_number,
            "final_status": self.final_status,
            "failure_code": self.failure_code,
            "reasons": self.reasons,
            "resolved_references": self.resolved_references,
            "run_id": self.run_id,
            "row_hash": self.row_hash,
            "source_hash": self.source_hash,
        }


class Validator:
    def __init__(self, repository):
        self.repository = repository

    def validate_rows(self, parsed_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        live_snapshot = self.repository.get_live_reference_snapshot()
        companies = live_snapshot["companies"]
        departments = live_snapshot["departments"]
        jobs = live_snapshot["jobs"]
        return [self.validate_single_row(row, companies, departments, jobs).to_dict() for row in parsed_rows]

    def validate_single_row(self, row, companies, departments, jobs) -> ValidationResult:
        fields = row["fields"]
        flags = set(row.get("parser_flags", []))
        run_id = row.get("run_id")
        r_hash = row.get("row_hash")
        s_hash = row.get("source_hash")

        def result(status, code, reasons, refs=None):
            return ValidationResult(row["excel_row_number"], status, code, reasons, refs, run_id, r_hash, s_hash)

        if "duplicate_in_file" in flags:
            return result(FINAL_NEEDS_REVIEW, DUPLICATE_IN_FILE,
                           ["Duplicate row detected within the same normalized file."])

        name_value = fields["name"]["value"]
        work_email_value = fields["work_email"]["value"]
        work_email_match = fields["work_email"]["match_key"]
        mobile_match = fields["mobile_phone"]["match_key"]
        company_value = fields["company"]["value"]
        department_value = fields["department"]["value"]
        job_value = fields["job"]["value"]

        if not name_value:
            return result(FINAL_REJECTED, VALIDATION_ERROR, ["Employee name is required."])

        if work_email_value and not is_valid_email_format(work_email_value):
            return result(FINAL_REJECTED, INVALID_WORK_EMAIL,
                           [f"work_email does not match a valid format: {work_email_value}"])

        company_key = reference_match_key(company_value)
        company_matches = [c for c in companies if reference_match_key(c.get("name") or "") == company_key]

        if not company_matches:
            return result(FINAL_REJECTED, REFERENCE_NOT_FOUND, [f"Company not found: {company_value}"])
        if len(company_matches) > 1:
            return result(FINAL_NEEDS_REVIEW, REFERENCE_AMBIGUOUS, [f"Company is ambiguous: {company_value}"])

        company = company_matches[0]
        company_id = company["id"]

        if company.get("active") is False:
            return result(FINAL_NEEDS_REVIEW, ARCHIVED_REFERENCE_MATCH,
                           [f"Company matched but is archived: {company_value}"], refs={"company": company})

        resolved_department = None
        if department_value:
            department_key = reference_match_key(department_value)
            company_departments = [
                d for d in departments
                if safe_many2one_id(d.get("company_id")) == company_id
            ]
            department_matches = [
                d for d in company_departments
                if reference_match_key(d.get("complete_name") or "") == department_key
            ]
            if not department_matches:
                closest_department = suggest_closest_reference_name(
                    department_value,
                    [d.get("complete_name") or "" for d in company_departments],
                )
                if closest_department:
                    return result(
                        FINAL_REJECTED,
                        REFERENCE_NOT_FOUND,
                        [
                            f"Department not found for company: {department_value}. "
                            f"Closest match in this company: {closest_department}"
                        ],
                        refs={"company": company},
                    )
                return result(
                    FINAL_REJECTED,
                    REFERENCE_NOT_FOUND,
                    [f"Department not found for company: {department_value}"],
                    refs={"company": company},
                )
            if len(department_matches) > 1:
                return result(FINAL_NEEDS_REVIEW, REFERENCE_AMBIGUOUS,
                               [f"Department is ambiguous for company: {department_value}"], refs={"company": company})
            resolved_department = department_matches[0]
            if resolved_department.get("active") is False:
                return result(FINAL_NEEDS_REVIEW, ARCHIVED_REFERENCE_MATCH,
                               [f"Department matched but is archived: {department_value}"],
                               refs={"company": company, "department": resolved_department})

        resolved_job = None
        if job_value:
            job_key = reference_match_key(job_value)
            company_jobs = [
                j for j in jobs
                if safe_many2one_id(j.get("company_id")) == company_id
            ]
            job_matches = [
                j for j in company_jobs
                if reference_match_key(j.get("name") or "") == job_key
            ]
            if not job_matches:
                closest_job = suggest_closest_reference_name(
                    job_value,
                    [j.get("name") or "" for j in company_jobs],
                )
                if closest_job:
                    return result(
                        FINAL_REJECTED,
                        REFERENCE_NOT_FOUND,
                        [
                            f"Job not found for company: {job_value}. "
                            f"Closest match in this company: {closest_job}"
                        ],
                        refs={"company": company},
                    )
                return result(
                    FINAL_REJECTED,
                    REFERENCE_NOT_FOUND,
                    [f"Job not found for company: {job_value}"],
                    refs={"company": company},
                )
            if len(job_matches) > 1:
                return result(FINAL_NEEDS_REVIEW, REFERENCE_AMBIGUOUS,
                               [f"Job is ambiguous for company: {job_value}"], refs={"company": company})
            resolved_job = job_matches[0]
            if resolved_job.get("active") is False:
                return result(FINAL_NEEDS_REVIEW, ARCHIVED_REFERENCE_MATCH,
                               [f"Job matched but is archived: {job_value}"],
                               refs={"company": company, "job": resolved_job})

        refs_base = {"company": company, "department": resolved_department, "job": resolved_job}

        if work_email_match:
            try:
                candidates = find_employees_by_email(self.repository, work_email_value, limit=20)
            except Exception as exc:  # fail closed: never accept a row whose duplicate check did not run
                return result(FINAL_NEEDS_REVIEW, DUPLICATE_CHECK_UNAVAILABLE,
                               [f"Duplicate check against Odoo failed ({type(exc).__name__}); "
                                "row was not checked for existing employees."],
                               refs=refs_base)
            exact_matches = [c for c in candidates
                              if normalize_email_exact(c.get("work_email")) == normalize_email_exact(work_email_value)]
            if len(exact_matches) == 1:
                return result(FINAL_NEEDS_REVIEW, DUPLICATE_EXISTING_EMPLOYEE,
                               [f"Existing employee found by work_email: {work_email_value}"],
                               refs={**refs_base, "employee_match": exact_matches[0]})
            if len(exact_matches) > 1:
                return result(FINAL_NEEDS_REVIEW, AMBIGUOUS_DUPLICATE,
                               [f"Multiple employees found by work_email: {work_email_value}"],
                               refs={**refs_base, "employee_matches": exact_matches})

        if not work_email_match and not mobile_match:
            return result(FINAL_NEEDS_REVIEW, INSUFFICIENT_DUPLICATE_SIGNAL,
                           ["Row has neither work_email nor mobile_phone; cannot establish a reliable duplicate key."],
                           refs=refs_base)

        if "possible_duplicate_in_file" in flags:
            return result(FINAL_NEEDS_REVIEW, POSSIBLE_DUPLICATE_IN_FILE,
                           ["Rows share the same normalized name+mobile_phone combination within the file; manual review required."],
                           refs=refs_base)

        if not work_email_match and mobile_match:
            return result(
                FINAL_NEEDS_REVIEW,
                UNVERIFIED_NO_EMAIL,
                [
                    "work_email is empty; duplicate checking against Odoo by email "
                    "was not performed. No duplicate was established by this result."
                ],
                refs=refs_base,
            )

        return result(FINAL_ACCEPTED, None, ["Row passed validator checks."], refs=refs_base)