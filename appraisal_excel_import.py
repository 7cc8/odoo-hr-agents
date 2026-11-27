from __future__ import annotations

from math import isfinite

from normalization import clean_value_text
from odoo_appraisal_write_gateway import APPRAISAL_REQUEST_MODEL


APPRAISAL_IMPORT_UNAVAILABLE = "قاعدة Odoo المتصلة لا توفر نموذج تقييم الأداء المطلوب للاستيراد."
APPRAISAL_EMPLOYEE_MISSING = (
    "تعذّرت مطابقة رقم الهوية أو الإقامة مع موظف مسجل في المنشأة المختارة. "
    "إذا استخدمت الصف الاسترشادي، استبدله ببيانات موظف مسجل."
)
APPRAISAL_SCORE_INVALID = "أدخل الدرجة النهائية، أو درجتي الأهداف والسلوك، بأرقام من 0 إلى 100."
APPRAISAL_YEAR_INVALID = "أدخل سنة التقييم الميلادية بأربعة أرقام."


def check_appraisal_row(fields, repository):
    """Return plain-language validation issues and the exact employee for a standalone appraisal."""
    issues = []
    if not repository.supports_appraisal_import:
        issues.append(("appraisal_unavailable", APPRAISAL_IMPORT_UNAVAILABLE))

    identity = clean_value_text(str(fields.get("emp_id") or ""))
    employee = None
    if identity:
        matches = [
            candidate for candidate in repository.search_employee_candidates(identity)
            if clean_value_text(str(candidate.get("identification_id") or "")) == identity
        ]
        if len(matches) == 1:
            employee = matches[0]
    if employee is None:
        issues.append(("employee_not_found", APPRAISAL_EMPLOYEE_MISSING))

    year = str(fields.get("year") or "").strip()
    if len(year) != 4 or not year.isdecimal() or int(year) < 1000:
        issues.append(("appraisal_year_invalid", APPRAISAL_YEAR_INVALID))

    score = None
    try:
        total = fields.get("total_score")
        if total not in (None, ""):
            score = _appraisal_score(total)
        else:
            kpi = _appraisal_score(fields.get("kpi_score"))
            behavior = _appraisal_score(fields.get("competency_score"))
            score = round(0.7 * kpi + 0.3 * behavior, 2)
    except (TypeError, ValueError):
        issues.append(("appraisal_score_invalid", APPRAISAL_SCORE_INVALID))
    return issues, employee, score


def _appraisal_score(value):
    score = float(value)
    if not isfinite(score) or not 0 <= score <= 100:
        raise ValueError("Appraisal score must be between 0 and 100")
    return score


def create_excel_appraisal(fields, employee, score, gateway):
    year = int(fields["year"])
    name = f"تقييم الأداء {year} - {employee['name']}"
    notes = "\n".join(
        f"{label}: {fields[key]}"
        for label, key in (("نوع التقييم", "type"), ("المقيّم", "manager"),
                           ("التقدير", "rating"), ("التوصيات", "recommendation"))
        if fields.get(key)
    )
    record_id = gateway.create_appraisal_request(
        employee_id=employee["id"],
        name=name,
        start_date=f"{year:04d}-01-01",
        end_date=f"{year:04d}-12-31",
        final_percentage=score,
        total_points_earned=score,
        notes=notes,
    )
    return {"id": record_id, "model": APPRAISAL_REQUEST_MODEL, "name": name}
