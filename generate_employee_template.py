"""Generate the official employee import template from live Odoo reference data.

Produces an .xlsx file with three sheets:
  - Employees : editable data-entry sheet with dropdown validation and one example row.
  - Reference  : locked, auto-populated list of companies / departments / jobs from Odoo.
  - Instructions: Arabic usage guide for non-technical HR staff.

Usage (from project root):
    python generate_employee_template.py [--output-dir DIR]

Output file name: employee_import_template_YYYYMMDD.xlsx
Default output directory: samples/
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.protection import SheetProtection
except ImportError:
    print(
        "ERROR: openpyxl is required. Install it with:\n"
        "  pip install openpyxl",
        file=sys.stderr,
    )
    sys.exit(2)

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Column definitions (matches excel_template_spec.json + next_phase_plan 2.1)
# ---------------------------------------------------------------------------

EMPLOYEE_COLUMNS: List[Dict[str, Any]] = [
    {"key": "name",         "label": "name",         "required": True,  "format": None,  "width": 28},
    {"key": "work_email",   "label": "work_email",   "required": False, "format": None,  "width": 32},
    {"key": "work_phone",   "label": "work_phone",   "required": False, "format": "@",   "width": 18},
    {"key": "mobile_phone", "label": "mobile_phone", "required": False, "format": "@",   "width": 18},
    {"key": "job_title",    "label": "job_title",    "required": False, "format": None,  "width": 22},
    {"key": "hiring_date",  "label": "hiring_date",  "required": False, "format": "YYYY-MM-DD", "width": 16},
    {"key": "company",      "label": "company",      "required": True,  "format": None,  "width": 28},
    {"key": "department",   "label": "department",   "required": False, "format": None,  "width": 32},
    {"key": "job",          "label": "job",          "required": False, "format": None,  "width": 22},
]

# Columns that receive dropdown validation (by key → reference section header)
DROPDOWN_COLUMNS = {
    "company":    "companies",
    "department": "departments",
    "job":        "jobs",
}

# Arabic and Bilingual labels for employee columns
AR_COLUMN_LABELS = {
    "name": "اسم الموظف الكامل بالعربي",
    "work_email": "البريد الإلكتروني للعمل",
    "work_phone": "هاتف العمل",
    "mobile_phone": "رقم الجوال (05xxxxxxxx)",
    "job_title": "المسمى الوظيفي",
    "hiring_date": "تاريخ المباشرة",
    "company": "المنشأة التابع لها",
    "department": "القسم / الإدارة",
    "job": "الوظيفة",
}

BILINGUAL_COLUMN_LABELS = {
    "name": "اسم الموظف / Employee Name",
    "work_email": "البريد الإلكتروني / Work Email",
    "work_phone": "هاتف العمل / Work Phone",
    "mobile_phone": "رقم الجوال / Mobile Phone",
    "job_title": "المسمى الوظيفي / Job Title",
    "hiring_date": "تاريخ المباشرة / Hiring Date",
    "company": "المنشأة / Company",
    "department": "القسم / Department",
    "job": "الوظيفة / Job",
}

# Styles
_HEADER_FILL_REQUIRED   = PatternFill("solid", fgColor="1F4E79")   # dark blue — required
_HEADER_FILL_OPTIONAL   = PatternFill("solid", fgColor="2E75B6")   # lighter blue — optional
_HEADER_FONT            = Font(color="FFFFFF", bold=True, size=11)
_EXAMPLE_FILL           = PatternFill("solid", fgColor="FFF2CC")   # pale yellow
_EXAMPLE_FONT           = Font(italic=True, color="595959", size=10)
_REF_HEADER_FILL        = PatternFill("solid", fgColor="404040")
_REF_HEADER_FONT        = Font(color="FFFFFF", bold=True, size=10)
_REF_META_FONT          = Font(bold=True, size=10)
_SECTION_FILL           = PatternFill("solid", fgColor="D6E4F0")   # light blue section header
_SECTION_FONT           = Font(bold=True, size=10)
_INSTR_TITLE_FONT       = Font(bold=True, size=14, color="1F4E79")
_INSTR_HEADER_FONT      = Font(bold=True, size=11, color="1F4E79")
_INSTR_BODY_FONT        = Font(size=10)
_INSTR_WARN_FONT        = Font(size=10, color="C00000")
_WRAP                   = Alignment(wrap_text=True, vertical="top")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generated_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _today_yyyymmdd() -> str:
    return date.today().strftime("%Y%m%d")


def _set_col_width(ws, col_idx: int, width: float) -> None:
    ws.column_dimensions[get_column_letter(col_idx)].width = width


def _write_cell(ws, row: int, col: int, value, font=None, fill=None, alignment=None, number_format=None) -> None:
    cell = ws.cell(row=row, column=col, value=value)
    if isinstance(value, str):
        cell.data_type = "s"
    if font:
        cell.font = font
    if fill:
        cell.fill = fill
    if alignment:
        cell.alignment = alignment
    if number_format:
        cell.number_format = number_format


# ---------------------------------------------------------------------------
# Sheet 1: Employees
# ---------------------------------------------------------------------------

def _build_employees_sheet(wb: openpyxl.Workbook, snapshot: Dict[str, Any], language: Optional[str] = None) -> None:
    ws = wb.create_sheet("Employees", 0)
    lang = (language or "").lower().strip()
    is_rtl = lang in ("ar", "arabic", "bilingual", "bi")
    ws.sheet_view.rightToLeft = is_rtl

    # --- Header row (row 1) ---
    for col_idx, col in enumerate(EMPLOYEE_COLUMNS, start=1):
        key = col["key"]
        if lang in ("ar", "arabic"):
            label = AR_COLUMN_LABELS.get(key, col["label"])
        elif lang in ("bilingual", "bi"):
            label = BILINGUAL_COLUMN_LABELS.get(key, f"{AR_COLUMN_LABELS.get(key, col['label'])} / {col['label']}")
        else:
            label = col["label"]

        if col["required"]:
            display = f"{label} *"
            fill = _HEADER_FILL_REQUIRED
        else:
            display = label
            fill = _HEADER_FILL_OPTIONAL
        _write_cell(ws, 1, col_idx, display, font=_HEADER_FONT, fill=fill,
                    alignment=Alignment(horizontal="center", vertical="center"))
        _set_col_width(ws, col_idx, max(col["width"], len(display) + 4))

        # Force text format for phone columns
        if col.get("format") == "@":
            ws.column_dimensions[get_column_letter(col_idx)].number_format = "@"

    ws.row_dimensions[1].height = 22

    # --- Example row (row 2) — highlighted with note to delete ---
    examples = {
        "name":         "أحمد محمد العتيبي",
        "work_email":   "ahmed@company.com",
        "work_phone":   "0112345678",
        "mobile_phone": "0512345678",
        "job_title":    "مدير تشغيل",
        "hiring_date":  "2026-01-15",
        "company":      _first_active_company_name(snapshot),
        "department":   _first_active_dept_name(snapshot),
        "job":          _first_active_job_name(snapshot),
    }
    for col_idx, col in enumerate(EMPLOYEE_COLUMNS, start=1):
        val = examples.get(col["key"], "")
        _write_cell(ws, 2, col_idx, val, font=_EXAMPLE_FONT, fill=_EXAMPLE_FILL,
                    alignment=Alignment(vertical="center"))
        if col.get("format") == "@":
            ws.cell(row=2, column=col_idx).number_format = "@"

    ws.row_dimensions[2].height = 18

    # Mark row 2 as example via a comment on column A
    from openpyxl.comments import Comment
    comment = Comment("احذف هذا الصف — هو مثال توضيحي فقط", "النظام")
    comment.width = 200
    comment.height = 60
    ws.cell(row=2, column=1).comment = comment

    # --- Dropdowns (rows 2 through 1001) ---
    _add_dropdowns(ws, snapshot)

    # --- Freeze header row ---
    ws.freeze_panes = "A3"

    # Data rows start at 3; apply text format to phone columns for data area
    for col_idx, col in enumerate(EMPLOYEE_COLUMNS, start=1):
        if col.get("format") == "@":
            letter = get_column_letter(col_idx)
            for row in range(3, 1002):
                ws.cell(row=row, column=col_idx).number_format = "@"


def _first_active_company_name(snapshot: Dict[str, Any]) -> str:
    for c in snapshot.get("companies", []):
        if c.get("active", True):
            return c["name"]
    return ""


def _first_active_dept_name(snapshot: Dict[str, Any]) -> str:
    for d in snapshot.get("departments", []):
        if d.get("active", True):
            return d.get("complete_name") or d.get("name") or ""
    return ""


def _first_active_job_name(snapshot: Dict[str, Any]) -> str:
    for j in snapshot.get("jobs", []):
        if j.get("active", True):
            return j.get("name") or ""
    return ""


def _add_dropdowns(ws, snapshot: Dict[str, Any]) -> None:
    """Add Excel Data Validation dropdowns for company / department / job."""
    company_names = [c["name"] for c in snapshot.get("companies", []) if c.get("name")]
    dept_names = [
        d.get("complete_name") or d.get("name") or ""
        for d in snapshot.get("departments", [])
        if d.get("complete_name") or d.get("name")
    ]
    job_names = [j["name"] for j in snapshot.get("jobs", []) if j.get("name")]

    # Map column key → values list
    dropdown_values = {
        "company":    company_names,
        "department": dept_names,
        "job":        job_names,
    }

    for col_idx, col in enumerate(EMPLOYEE_COLUMNS, start=1):
        key = col["key"]
        if key not in DROPDOWN_COLUMNS:
            continue
        values = dropdown_values.get(key, [])
        if not values:
            continue

        # Excel inline list formula: "\"A,B,C\""
        quoted = ",".join(v.replace(",", " ") for v in values)
        formula = f'"{quoted}"'

        col_letter = get_column_letter(col_idx)
        dv = DataValidation(
            type="list",
            formula1=formula,
            showDropDown=False,  # False = dropdown arrow visible
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="قيمة غير صحيحة",
            error=(
                "يُرجى الاختيار من القائمة المنسدلة. "
                "التحقق الفعلي يحصل مقابل Odoo عند رفع الملف."
            ),
        )
        dv.sqref = f"{col_letter}3:{col_letter}1001"
        ws.add_data_validation(dv)


# ---------------------------------------------------------------------------
# Sheet 2: Reference (locked)
# ---------------------------------------------------------------------------

def _build_reference_sheet(wb: openpyxl.Workbook, snapshot: Dict[str, Any], generated_at: str) -> None:
    ws = wb.create_sheet("Reference", 1)
    ws.sheet_view.rightToLeft = False

    row = 1

    # --- Meta header ---
    _write_cell(ws, row, 1, "reference_generated_at", font=_REF_META_FONT)
    _write_cell(ws, row, 2, generated_at, font=_REF_META_FONT)
    row += 1
    row += 1  # blank separator

    # --- Section: Companies ---
    row = _write_reference_section(
        ws, row,
        section_title="الشركات (Companies)",
        headers=["entity_type", "id", "name", "active"],
        rows=[
            ["company", c["id"], c["name"], "نعم" if c.get("active", True) else "مؤرشف"]
            for c in snapshot.get("companies", [])
        ],
    )
    row += 1  # blank separator

    # --- Section: Departments ---
    row = _write_reference_section(
        ws, row,
        section_title="الأقسام (Departments) — أدخل complete_name في العمود department",
        headers=["entity_type", "id", "name", "complete_name", "company_id", "company_name", "active"],
        rows=[
            [
                "department",
                d["id"],
                d.get("name", ""),
                d.get("complete_name") or d.get("name") or "",
                _id_of(d.get("company_id")),
                _name_of(d.get("company_id")),
                "نعم" if d.get("active", True) else "مؤرشف",
            ]
            for d in snapshot.get("departments", [])
        ],
    )
    row += 1

    # --- Section: Jobs ---
    _write_reference_section(
        ws, row,
        section_title="الوظائف (Jobs)",
        headers=["entity_type", "id", "name", "company_id", "company_name", "active"],
        rows=[
            [
                "job",
                j["id"],
                j.get("name", ""),
                _id_of(j.get("company_id")),
                _name_of(j.get("company_id")),
                "نعم" if j.get("active", True) else "مؤرشف",
            ]
            for j in snapshot.get("jobs", [])
        ],
    )

    # --- Column widths ---
    widths = [26, 6, 28, 36, 10, 28, 10]
    for i, w in enumerate(widths, start=1):
        _set_col_width(ws, i, w)

    # --- Lock sheet ---
    ws.protection = SheetProtection(
        sheet=True,
        password="readonly",
        selectLockedCells=True,
        selectUnlockedCells=True,
    )


def _write_reference_section(ws, start_row: int, section_title: str,
                               headers: List[str], rows: List[List[Any]]) -> int:
    """Writes a section header + column headers + data rows. Returns next free row."""
    # Section title
    _write_cell(ws, start_row, 1, section_title,
                font=_SECTION_FONT, fill=_SECTION_FILL,
                alignment=Alignment(horizontal="left", vertical="center"))
    ws.row_dimensions[start_row].height = 18
    start_row += 1

    # Column headers
    for col_idx, h in enumerate(headers, start=1):
        _write_cell(ws, start_row, col_idx, h,
                    font=_REF_HEADER_FONT, fill=_REF_HEADER_FILL,
                    alignment=Alignment(horizontal="center", vertical="center"))
    ws.row_dimensions[start_row].height = 18
    start_row += 1

    # Data rows
    for data_row in rows:
        for col_idx, val in enumerate(data_row, start=1):
            _write_cell(ws, start_row, col_idx, val,
                        alignment=Alignment(vertical="center"))
        start_row += 1

    return start_row


def _id_of(many2one: Any) -> Optional[int]:
    if isinstance(many2one, (list, tuple)) and many2one:
        return many2one[0]
    if isinstance(many2one, int):
        return many2one
    return None


def _name_of(many2one: Any) -> str:
    if isinstance(many2one, (list, tuple)) and len(many2one) >= 2:
        return str(many2one[1])
    return ""


# ---------------------------------------------------------------------------
# Sheet 3: Instructions (Arabic / English / Bilingual)
# ---------------------------------------------------------------------------

def _build_instructions_sheet(wb: openpyxl.Workbook, language: Optional[str] = None) -> None:
    ws = wb.create_sheet("Instructions", 2)
    lang = (language or "ar").lower().strip()
    is_ar = lang in ("ar", "arabic")
    is_bi = lang in ("bilingual", "bi")
    ws.sheet_view.rightToLeft = is_ar  # RTL for Arabic only

    _set_col_width(ws, 1, 24)
    _set_col_width(ws, 2, 74)

    row = 1

    def title(text: str) -> int:
        nonlocal row
        align_h = "right" if is_ar else "left"
        _write_cell(ws, row, 1, text, font=_INSTR_TITLE_FONT,
                    alignment=Alignment(horizontal=align_h, vertical="center"))
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        ws.row_dimensions[row].height = 26
        row += 1
        return row

    def section(text: str) -> None:
        nonlocal row
        row += 1
        align_h = "right" if is_ar else "left"
        _write_cell(ws, row, 1, text, font=_INSTR_HEADER_FONT,
                    fill=_SECTION_FILL,
                    alignment=Alignment(horizontal=align_h, vertical="center"))
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        ws.row_dimensions[row].height = 20
        row += 1

    def field(name: str, desc: str, example_ok: str = "", example_bad: str = "",
              required: bool = False) -> None:
        nonlocal row
        align_h = "right" if is_ar else "left"
        req_marker = " *" if required else ""
        _write_cell(ws, row, 1, f"{name}{req_marker}",
                    font=Font(bold=True, size=10),
                    alignment=Alignment(horizontal=align_h, vertical="top", wrap_text=True))
        body = desc
        if example_ok:
            body += f"\n{'✓ مثال صحيح:' if is_ar else '✓ Valid example:'} {example_ok}"
        if example_bad:
            body += f"\n{'✗ مثال خاطئ:' if is_ar else '✗ Invalid example:'} {example_bad}"
        _write_cell(ws, row, 2, body, font=_INSTR_BODY_FONT, alignment=_WRAP)
        ws.row_dimensions[row].height = max(40, 14 * (body.count("\n") + 1))
        row += 1

    def note(text: str, warn: bool = False) -> None:
        nonlocal row
        align_h = "right" if is_ar else "left"
        font = _INSTR_WARN_FONT if warn else _INSTR_BODY_FONT
        lbl = ("⚠ ملاحظة:" if is_ar else "⚠ Notice:") if warn else "ℹ"
        _write_cell(ws, row, 1, lbl, font=font,
                    alignment=Alignment(horizontal=align_h, vertical="top"))
        _write_cell(ws, row, 2, text, font=font, alignment=_WRAP)
        ws.row_dimensions[row].height = max(30, 14 * (text.count("\n") + 1))
        row += 1

    def blank() -> None:
        nonlocal row
        row += 1

    # ---- Content based on language ----
    if is_ar:
        title("📋 دليل استخدام قالب استيراد الموظفين")
        section("1. كيف تملأ ورقة Employees")
        note(
            "ابدأ من الصف رقم 3. الصف رقم 2 هو مثال توضيحي — احذفه قبل رفع الملف.",
            warn=True,
        )
        blank()
        field(
            "name", "الاسم الكامل للموظف كما سيظهر في Odoo.",
            example_ok="أحمد محمد العتيبي",
            example_bad="أحمد (اسم ناقص)",
            required=True,
        )
        field(
            "work_email",
            "البريد الإلكتروني المهني. يُستخدم للكشف عن التكرار — إن وُجد موظف بنفس البريد سيظهر تحذير.",
            example_ok="ahmed@company.com",
            example_bad="ahmed@ (بريد غير مكتمل)",
        )
        field(
            "work_phone",
            "رقم هاتف العمل. أدخله كنص بدون فراغات. اتركه فارغاً إن لم يكن متوفراً.",
            example_ok="0112345678",
            example_bad="011-234-5678 (الشرطات تُزال تلقائياً لكن يُفضَّل إدخالها بدونها)",
        )
        field(
            "mobile_phone",
            "رقم الجوال. نفس قواعد work_phone.",
            example_ok="0512345678",
        )
        field(
            "job_title",
            "المسمى الوظيفي النصي الحر. لا يرتبط بقائمة Odoo — يُكتب كما تريد.",
            example_ok="مدير تشغيل",
        )
        field(
            "hiring_date",
            "تاريخ التوظيف (اختياري). يُملأ يدوياً من واجهة Odoo عند الحاجة. "
            "إن أدخلته هنا استخدم الصيغة YYYY-MM-DD.",
            example_ok="2026-01-15",
            example_bad="15/01/2026 (صيغة خاطئة)",
        )
        field(
            "company",
            "اسم الشركة كما هو في ورقة Reference. استخدم القائمة المنسدلة.",
            example_ok="شركة النخبة الذكية للتقنية",
            example_bad="النخبة (اسم مختصر — قد لا يُطابَق)",
            required=True,
        )
        field(
            "department",
            "اسم القسم. استخدم القيمة من عمود complete_name في ورقة Reference "
            "(مثلاً: شركة X / قسم Y). القائمة المنسدلة تعرض الخيارات المتاحة.",
            example_ok="شركة النخبة الذكية للتقنية / تقنية المعلومات",
            example_bad="تقنية المعلومات (بدون اسم الشركة — قد يكون غامضاً)",
        )
        field(
            "job",
            "الوظيفة من قائمة Odoo. استخدم القائمة المنسدلة واختر من الخيارات المتاحة.",
            example_ok="مطور برمجيات",
        )
        section("2. القوائم المنسدلة — تنبيه مهم")
        note(
            "القوائم المنسدلة مساعدة فقط وتعكس بيانات Odoo وقت إنشاء هذا القالب.\n"
            "التحقق الفعلي يحصل مقابل Odoo الحي عند رفع الملف.\n"
            "لو تغيّرت الأقسام أو الوظائف في Odoo بعد إنشاء القالب، أنشئ نسخة جديدة منه.",
            warn=True,
        )
        section("3. ماذا تعني نتائج التقرير")
        for st, meaning in [
            ("accepted ✓",         "الصف جاهز للإنشاء — بانتظار موافقتك الصريحة."),
            ("needs_review ⚠",     "يحتاج مراجعة يدوية — مثلاً: موظف مشابه موجود مسبقاً، أو اسم القسم غامض."),
            ("rejected ✗",         "لن يُنشأ — صحّح الخطأ المذكور في التقرير وأعد المحاولة."),
            ("outcome_uncertain !", "حصل خطأ غير متوقع أثناء الإنشاء. تواصل مع الدعم التقني أولاً."),
        ]:
            _write_cell(ws, row, 1, st, font=Font(bold=True, size=10),
                        alignment=Alignment(horizontal="right", vertical="top"))
            _write_cell(ws, row, 2, meaning, font=_INSTR_BODY_FONT, alignment=_WRAP)
            ws.row_dimensions[row].height = max(28, 14 * (meaning.count("\n") + 1))
            row += 1
    else:
        # English or Bilingual
        title("📋 Employee Import Template Guide" if not is_bi else "📋 دليل استخدام قالب استيراد الموظفين / Employee Import Guide")
        section("1. How to Fill the Employees Sheet" if not is_bi else "1. تعبئة البيانات / How to Fill the Employees Sheet")
        note(
            "Start from row 3. Row 2 is an illustrative example — clear it before upload."
            if not is_bi else
            "ابدأ من الصف رقم 3. الصف رقم 2 هو مثال توضيحي.\nStart from row 3. Row 2 is an illustrative example — clear it before upload.",
            warn=True,
        )
        blank()
        field(
            "name",
            "Full employee name as it should appear in Odoo."
            if not is_bi else "اسم الموظف الكامل كما يظهر في Odoo.\nFull employee name as it should appear in Odoo.",
            example_ok="Ahmed Mohammed Al-Otaibi",
            example_bad="Ahmed (Incomplete name)",
            required=True,
        )
        field(
            "work_email",
            "Professional work email. Used for duplicate detection — a warning appears if an employee exists with the same email."
            if not is_bi else "البريد الإلكتروني المهني للكشف عن التكرار.\nProfessional work email for duplicate detection.",
            example_ok="ahmed@company.com",
            example_bad="ahmed@ (Incomplete email)",
        )
        field(
            "work_phone",
            "Work phone number. Enter as text without spaces. Leave empty if unavailable."
            if not is_bi else "رقم هاتف العمل (كنص بدون فراغات).\nWork phone number without spaces.",
            example_ok="0112345678",
            example_bad="011-234-5678 (Hyphens will be removed automatically)",
        )
        field(
            "mobile_phone",
            "Mobile phone number. Follows the same rules as work_phone."
            if not is_bi else "رقم الجوال.\nMobile phone number.",
            example_ok="0512345678",
        )
        field(
            "job_title",
            "Free-form job title text. Does not restrict to Odoo list."
            if not is_bi else "المسمى الوظيفي النصي الحر.\nFree-form job title text.",
            example_ok="Operations Manager",
        )
        field(
            "hiring_date",
            "Hiring date (optional). Must use ISO format: YYYY-MM-DD."
            if not is_bi else "تاريخ التوظيف بصيغة YYYY-MM-DD.\nHiring date in YYYY-MM-DD format.",
            example_ok="2026-01-15",
            example_bad="15/01/2026 (Invalid format)",
        )
        field(
            "company",
            "Company name as listed in the Reference sheet. Use the dropdown list."
            if not is_bi else "اسم الشركة من ورقة Reference.\nCompany name from Reference sheet.",
            example_ok="Smart Elite Tech Co.",
            example_bad="Elite (Shortened — may not match)",
            required=True,
        )
        field(
            "department",
            "Department name. Use value from complete_name in the Reference sheet."
            if not is_bi else "اسم القسم من عمود complete_name.\nDepartment name from complete_name column.",
            example_ok="Smart Elite Tech Co. / Information Technology",
            example_bad="IT (Ambiguous without company prefix)",
        )
        field(
            "job",
            "Job position from Odoo catalog. Choose from dropdown."
            if not is_bi else "الوظيفة من قائمة Odoo.\nJob position from Odoo catalog.",
            example_ok="Software Developer",
        )
        section("2. Dropdown Lists — Important Notice" if not is_bi else "2. القوائم المنسدلة / Dropdown Lists Notice")
        note(
            "Dropdown lists are helpers reflecting Odoo reference data at template generation time.\n"
            "Actual validation occurs against live Odoo data upon upload.\n"
            "If departments or jobs change in Odoo after generation, export a fresh template."
            if not is_bi else
            "القوائم المنسدلة مساعدة فقط وتعكس بيانات Odoo وقت التوليد.\nDropdown lists reflect Odoo snapshot at template generation time.",
            warn=True,
        )
        section("3. Understanding Audit Report Statuses" if not is_bi else "3. حالات التقرير / Report Statuses")
        for st, meaning in [
            ("accepted ✓",         "Row is validated and ready for creation — awaiting explicit approval."),
            ("needs_review ⚠",     "Requires manual review — e.g. similar employee exists or department is ambiguous."),
            ("rejected ✗",         "Will not be created — fix the indicated error in the report and retry."),
            ("outcome_uncertain !", "Unexpected error occurred during execution. Contact technical support before retrying."),
        ]:
            _write_cell(ws, row, 1, st, font=Font(bold=True, size=10),
                        alignment=Alignment(horizontal="left", vertical="top"))
            _write_cell(ws, row, 2, meaning, font=_INSTR_BODY_FONT, alignment=_WRAP)
            ws.row_dimensions[row].height = max(28, 14 * (meaning.count("\n") + 1))
            row += 1

    section("4. متى تتواصل مع الدعم التقني")
    for item in [
        'ظهر outcome_uncertain في أي صف من الصفوف.',
        'رسالة خطأ غير مفهومة أثناء تشغيل أي خطوة.',
        'أردت تعديل موظف تم إنشاؤه مسبقاً (التعديل يحصل يدوياً من واجهة Odoo، لا عبر هذه الأداة).',
        'انتهت صلاحية مفتاح الـ API (ستظهر رسالة خطأ عند بدء التشغيل).',
    ]:
        _write_cell(ws, row, 1, "•", font=_INSTR_BODY_FONT,
                    alignment=Alignment(horizontal="right", vertical="top"))
        _write_cell(ws, row, 2, item, font=_INSTR_BODY_FONT, alignment=_WRAP)
        ws.row_dimensions[row].height = max(20, 14 * (item.count("\n") + 1))
        row += 1

    blank()
    note("هذا القالب أُنشئ تلقائياً — لا تعدّل ورقة Reference ولا ورقة Instructions.")


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def generate_template(
    snapshot: Dict[str, Any],
    output_dir: str = "samples",
    language: Optional[str] = None,
) -> Path:
    """Build and save the Excel template. Returns the output path."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    filename = f"employee_import_template_{_today_yyyymmdd()}.xlsx"
    dest = output_path / filename

    generated_at = _generated_at()

    wb = openpyxl.Workbook()
    # Remove default sheet
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    _build_employees_sheet(wb, snapshot, language=language)
    _build_reference_sheet(wb, snapshot, generated_at)
    _build_instructions_sheet(wb, language=language)

    wb.active = wb["Employees"]
    wb.save(dest)
    return dest


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the official employee import Excel template from live Odoo data."
    )
    parser.add_argument(
        "--output-dir",
        default="samples",
        help="Directory to save the generated .xlsx file (default: samples/)",
    )
    args = parser.parse_args(argv)

    from odoo_readonly_repository import OdooReadonlyRepository, OdooReadonlyRepositoryError

    if not (os.environ.get("ODOO_URL") or os.environ.get("ODOO_DB") or os.environ.get("ODOO_API_KEY") or os.environ.get("ODOO_USER") or os.environ.get("ODOO_USERNAME")):
        print("ABORT: Missing Odoo connection settings: ODOO_URL, ODOO_DB, ODOO_USER, ODOO_API_KEY", file=sys.stderr)
        print("  Make sure .env contains ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY", file=sys.stderr)
        return 2

    try:
        repo = OdooReadonlyRepository()
    except OdooReadonlyRepositoryError as exc:
        print(f"ABORT: {exc}", file=sys.stderr)
        print("  Make sure .env contains ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY", file=sys.stderr)
        return 2

    print("Connecting to Odoo and fetching reference data...")
    try:
        snapshot = repo.get_live_reference_snapshot()
    except Exception as exc:
        print(f"ABORT: Failed to fetch reference data: {exc}", file=sys.stderr)
        return 1

    companies = snapshot.get("companies", [])
    departments = snapshot.get("departments", [])
    jobs = snapshot.get("jobs", [])
    print(f"  [OK] {len(companies)} companies, {len(departments)} departments, {len(jobs)} jobs")

    dest = generate_template(snapshot, output_dir=args.output_dir)
    print(f"  [OK] Template generated: {dest}")
    print()
    print("Next steps:")
    print("  1. Open the file in Excel and delete the example row (row 2) before use.")
    print("  2. Fill in employee data starting from row 3.")
    print("  3. Run: python run_dry_run.py <file.xlsx>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
