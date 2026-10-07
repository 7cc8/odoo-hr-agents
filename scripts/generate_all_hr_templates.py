"""Master and Modular Excel Templates Generator for Odoo HR Suite.

Generates:
1. 13 Modular Standalone Excel Templates in templates/modular/
2. 1 Master All-in-One Client Onboarding Workbook in templates/master/Master_Client_Onboarding_Template.xlsx

Features:
- Live Odoo schema alignment (Companies, Departments, Jobs, Custom models).
- Saudi Labor Law and GOSI compliance (Articles 53, 70, 77, 80, 84, 85, 87, 92, 107, 109, 113).
- Professional Resend/Tailored visual hierarchy (Color-coded headers, example rows, dropdowns).
- Text formatting for Phone, IBAN, National ID, CR, VAT to prevent leading-zero truncation.
- RTL layout and comprehensive Arabic instructions.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

# Setup paths
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

MODULAR_DIR = ROOT_DIR / "templates" / "modular"
MASTER_DIR = ROOT_DIR / "templates" / "master"
MODULAR_DIR.mkdir(parents=True, exist_ok=True)
MASTER_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Visual Styles (Professional Enterprise Palette)
# ---------------------------------------------------------------------------
FILL_REQUIRED = PatternFill("solid", fgColor="1F4E79")      # Dark Navy — Required
FILL_OPTIONAL = PatternFill("solid", fgColor="2E75B6")      # Slate Blue — Optional
FILL_FORMULA  = PatternFill("solid", fgColor="115E59")      # Deep Teal — Auto Calculated
FILL_EXAMPLE  = PatternFill("solid", fgColor="FFF2CC")      # Pale Yellow — Example Row
FILL_REF_HDR  = PatternFill("solid", fgColor="334155")      # Slate Dark — Reference Headers
FILL_INSTR_H  = PatternFill("solid", fgColor="1E293B")      # Slate 800 — Instructions Title

FONT_HEADER   = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
FONT_EXAMPLE  = Font(name="Segoe UI", size=10, italic=True, color="595959")
FONT_DATA     = Font(name="Segoe UI", size=10, color="000000")
FONT_REF_HDR  = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
FONT_INSTR_T  = Font(name="Segoe UI", size=14, bold=True, color="1F4E79")
FONT_INSTR_B  = Font(name="Segoe UI", size=10, color="1E293B")
FONT_INSTR_W  = Font(name="Segoe UI", size=10, bold=True, color="991B1B")

ALIGN_CENTER  = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_RIGHT   = Alignment(horizontal="right", vertical="center")
ALIGN_LEFT    = Alignment(horizontal="left", vertical="center")

BORDER_THIN   = Border(
    left=Side(style="thin", color="CBD5E1"),
    right=Side(style="thin", color="CBD5E1"),
    top=Side(style="thin", color="CBD5E1"),
    bottom=Side(style="thin", color="CBD5E1"),
)

# Reference data constants
BANKS_SAUDI = ["مصرف الراجحي", "البنك الأهلي السعودي", "مصرف الإنماء", "بنك الرياض", "بنك البلاد", "البنك العربي الوطني", "البنك السعودي الأول (ساب)", "بنك الجزيرة", "البنك السعودي للاستثمار", "بنك الخليج الدولي"]
CITIES_SAUDI = ["الرياض", "جدة", "الدمام", "مكة المكرمة", "المدينة المنورة", "الخبر", "الجبيل", "الأحساء", "تبوك", "أبها", "خميس مشيط", "جازان", "نجران", "حائل", "ينبع", "القصيم"]
NATIONALITIES = ["سعودي", "مصري", "يمني", "أردني", "سوري", "لبناني", "سوداني", "هندي", "باكستاني", "فلبيني", "بنجلاديشي", "نيبالي", "أخرى"]
GOSI_TYPES = ["سعودي - مشترك قديم (21.5%)", "سعودي - مشترك جديد نظام 2024 (متدرج)", "غير سعودي - أخطار مهنية فقط (2%)"]
TERMINATION_REASONS = [
    "انتهاء مدة العقد (مادة 84 - مكافأة كاملة)",
    "فسخ العقد باتفاق الطرفين (مادة 84 - مكافأة كاملة)",
    "استقالة العامل - خدمة أقل من سنتين (مادة 85 - لا يستحق)",
    "استقالة العامل - خدمة 2 إلى 5 سنوات (مادة 85 - ثلث المكافأة)",
    "استقالة العامل - خدمة 5 إلى 10 سنوات (مادة 85 - ثلثي المكافأة)",
    "استقالة العامل - خدمة أكثر من 10 سنوات (مادة 85 - مكافأة كاملة)",
    "فصل بموجب المادة 80 (سقوط المكافأة نظاماً)",
    "إنهاء غير مشروع من صاحب العمل مادة 77 (مكافأة + تعويض)",
    "ترك العمل بموجب المادة 81 لخطأ صاحب العمل (مكافأة كاملة)",
    "استقالة العاملة خلال 6 أشهر من الزواج أو 3 أشهر من الوضع (مادة 87 - كاملة)"
]
LEAVE_TYPES = ["إجازة سنوية اعتيادية", "إجازة مرضية", "إجازة زواج (مادة 113 - 5 أيام)", "إجازة وفاة (مادة 113 - 5 أيام)", "إجازة مولود (مادة 113 - 3 أيام)", "إجازة حج (مادة 114)", "إجازة بدون راتب"]
LOAN_TYPES = ["سلفة شخصية قصيرة الأجل", "بدل سكن مقدم", "قرض زواج ميسر", "سلفة طارئة"]
PENALTY_TYPES = ["إنذار كتابي أول", "إنذار كتابي ثانٍ / نهائي", "خصم يوم من الأجر", "خصم يومين من الأجر", "خصم 3 أيام من الأجر", "خصم 5 أيام من الأجر (الحد الأقصى مادة 70)", "إيقاف عن العمل مع حرمان من الأجر"]
OVERTIME_TYPES = ["ساعات عمل عادية (1.5x الأجر الأساسي)", "ساعات عمل في عطلة أسبوعية / جمعة (1.5x)", "ساعات عمل في يوم عيد / عطلة رسمية (1.5x)"]
GR_TYPES = ["تجديد إقامة", "إصدار تأشيرة خروج وعودة", "إصدار تأشيرة نهائية", "تجديد رخصة عمل", "تعديل مهنة في قوى ومقيم", "نقل كفالة", "إصدار إقامة جديدة"]
APPRAISAL_TYPES = ["تقييم سنوي شامل", "تقييم فترة التجربة (90/180 يوماً)", "تقييم نصف سنوي"]

# Fallback reference data if Odoo is unreachable
COMPANIES_DEFAULT = ["شركة النخبة الذكية للتقنية", "شركة توركين للتجزئة", "شركة العقار الموحدة"]
BRANCHES_DEFAULT = ["فرع الرياض - المقر الرئيسي", "فرع جدة", "فرع الدمام", "فرع الخبر"]
DEPTS_DEFAULT = ["الإدارة العامة", "الموارد البشرية", "المالية والمحاسبة", "تقنية المعلومات", "المبيعات والتسويق", "العمليات والتشغيل", "الشؤون القانونية"]
JOBS_DEFAULT = ["مدير تنفيذي", "مدير موارد بشرية", "مسؤول محاسبة", "مطور برمجيات", "مهندس نظم", "أخصائي تسويق", "مشرف مبيعات", "منسق عمليات"]

# ---------------------------------------------------------------------------
# Core Helpers
# ---------------------------------------------------------------------------
def _load_live_reference_data(url: Optional[str] = None, db: Optional[str] = None, user: Optional[str] = None, key: Optional[str] = None) -> Dict[str, List[str]]:
    """Loads live reference data from Odoo repository or uses verified defaults."""
    data = {
        "companies": COMPANIES_DEFAULT,
        "branches": BRANCHES_DEFAULT,
        "departments": DEPTS_DEFAULT,
        "jobs": JOBS_DEFAULT,
    }
    try:
        from odoo_readonly_repository import OdooReadonlyRepository
        repo = OdooReadonlyRepository(url=url, db=db, username=user, api_key=key)
        comps = repo.get_accessible_companies()
        if comps:
            data["companies"] = [c["name"] for c in comps if c.get("name")]
        depts = repo.get_departments()
        if depts:
            data["departments"] = [d["name"] for d in depts if d.get("name")]
        jobs = repo.get_jobs()
        if jobs:
            data["jobs"] = [j["name"] for j in jobs if j.get("name")]
    except Exception as exc:
        print(f"  [Notice] Using default reference data (connection fallback: {exc})")
    return data


def _set_col_width(ws, col_idx: int, width: float) -> None:
    ws.column_dimensions[get_column_letter(col_idx)].width = width


def _apply_sheet_styling(ws, title_text: str, columns_meta: List[Dict[str, Any]], example_row: List[Any]) -> None:
    """Sets up standard headers, widths, formatting, and example row for a data sheet."""
    ws.sheet_view.rightToLeft = True
    ws.views.sheetView[0].showGridLines = True

    # Row 1: Sheet Title banner
    ws.row_dimensions[1].height = 28
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(columns_meta))
    title_cell = ws.cell(row=1, column=1, value=title_text)
    title_cell.fill = FILL_INSTR_H
    title_cell.font = Font(name="Segoe UI", size=13, bold=True, color="FFFFFF")
    title_cell.alignment = ALIGN_CENTER

    # Row 2: Headers
    ws.row_dimensions[2].height = 36
    for idx, col in enumerate(columns_meta, start=1):
        c = ws.cell(row=2, column=idx, value=col["label"])
        c.font = FONT_HEADER
        c.alignment = ALIGN_CENTER
        c.border = BORDER_THIN
        if col.get("formula"):
            c.fill = FILL_FORMULA
        elif col.get("required"):
            c.fill = FILL_REQUIRED
        else:
            c.fill = FILL_OPTIONAL
        _set_col_width(ws, idx, col.get("width", 22))

    # Row 3: Example row
    ws.row_dimensions[3].height = 24
    for idx, val in enumerate(example_row, start=1):
        c = ws.cell(row=3, column=idx, value=val)
        c.font = FONT_EXAMPLE
        c.fill = FILL_EXAMPLE
        c.alignment = ALIGN_CENTER
        c.border = BORDER_THIN
        fmt = columns_meta[idx - 1].get("format")
        if fmt:
            c.number_format = fmt

    # Freeze header rows
    ws.freeze_panes = "A4"


def _build_reference_sheet(wb, ref_catalog: Dict[str, List[str]]) -> openpyxl.worksheet.worksheet.Worksheet:
    """Creates a standardized locked reference sheet with named columns."""
    ws = wb.create_sheet(title="Reference")
    ws.sheet_view.rightToLeft = True
    ws.views.sheetView[0].showGridLines = True

    col_idx = 1
    for group_name, items in ref_catalog.items():
        # Header
        c = ws.cell(row=1, column=col_idx, value=group_name)
        c.font = FONT_REF_HDR
        c.fill = FILL_REF_HDR
        c.alignment = ALIGN_CENTER
        _set_col_width(ws, col_idx, max(24, max((len(str(x)) for x in items), default=15) + 3))

        # Values
        for r_idx, val in enumerate(items, start=2):
            val_c = ws.cell(row=r_idx, column=col_idx, value=val)
            val_c.font = FONT_DATA
            val_c.alignment = ALIGN_RIGHT
            val_c.border = BORDER_THIN

        col_idx += 2  # Leave gap between groups

    # Protect sheet so users cannot tamper with reference lists
    ws.protection.sheet = True
    ws.protection.enable()
    return ws


def _build_instructions_sheet(wb, title: str, rules_list: List[str], law_notes: List[str]) -> None:
    """Builds an informative Arabic instructions tab."""
    ws = wb.create_sheet(title="Instructions", index=0)
    ws.sheet_view.rightToLeft = True
    ws.views.sheetView[0].showGridLines = True

    _set_col_width(ws, 1, 6)
    _set_col_width(ws, 2, 85)

    ws.row_dimensions[2].height = 30
    title_cell = ws.cell(row=2, column=2, value=f"📖 دليل استخدام: {title}")
    title_cell.font = FONT_INSTR_T

    # Subtitle
    ws.cell(row=3, column=2, value=f"تاريخ التوليد: {date.today().strftime('%Y-%m-%d')} | نظام أتمتة الموارد البشرية Odoo").font = Font(name="Segoe UI", size=9, italic=True, color="64748B")

    r = 5
    ws.cell(row=r, column=2, value="📌 شروط وتوجيهات تعبئة البيانات:").font = Font(name="Segoe UI", size=11, bold=True, color="1E293B")
    r += 1

    for idx, rule in enumerate(rules_list, start=1):
        ws.row_dimensions[r].height = 22
        ws.cell(row=r, column=1, value=f"{idx}.").font = Font(name="Segoe UI", size=10, bold=True, color="1F4E79")
        ws.cell(row=r, column=2, value=rule).font = FONT_INSTR_B
        r += 1

    if law_notes:
        r += 1
        ws.cell(row=r, column=2, value="⚖️ الضوابط النظامية المعمول بها (نظام العمل والتأمينات):").font = Font(name="Segoe UI", size=11, bold=True, color="991B1B")
        r += 1
        for note in law_notes:
            ws.row_dimensions[r].height = 24
            ws.cell(row=r, column=1, value="•").font = FONT_INSTR_W
            ws.cell(row=r, column=2, value=note).font = FONT_INSTR_W
            r += 1

    ws.freeze_panes = "A1"


# ---------------------------------------------------------------------------
# Definition of All 12 Functional Modules
# ---------------------------------------------------------------------------
def get_company_setup_spec() -> Dict[str, Any]:
    return {
        "title": "بيانات تأسيس المنشأة والحسابات البنكية (Company Profile)",
        "file_name": "template_company_setup.xlsx",
        "sheet_name": "Company_Setup",
        "columns": [
            {"key": "name_ar", "label": "اسم المنشأة بالعربي *", "required": True, "width": 30},
            {"key": "name_en", "label": "اسم المنشأة بالإنجليزي *", "required": True, "width": 30},
            {"key": "cr_number", "label": "رقم السجل التجاري (10 أرقام) *", "required": True, "format": "@", "width": 26},
            {"key": "vat_number", "label": "الرقم الضريبي (15 رقماً) *", "required": True, "format": "@", "width": 26},
            {"key": "gosi_id", "label": "رقم المنشأة في التأمينات (GOSI) *", "required": True, "format": "@", "width": 26},
            {"key": "labor_office_id", "label": "رقم المنشأة في مكتب العمل / قوى *", "required": True, "format": "@", "width": 28},
            {"key": "bank_name", "label": "اسم البنك الرئيسي *", "required": True, "dropdown": "banks", "width": 24},
            {"key": "iban", "label": "الآيبان البنكي الرئيسي (يبدأ بـ SA) *", "required": True, "format": "@", "width": 32},
            {"key": "city", "label": "المدينة *", "required": True, "dropdown": "cities", "width": 20},
            {"key": "district", "label": "الحي", "required": False, "width": 22},
            {"key": "street", "label": "العنوان الوطني / الشارع", "required": False, "width": 28},
            {"key": "postal_code", "label": "الرمز البريدي (5 أرقام)", "required": False, "format": "@", "width": 18},
            {"key": "phone", "label": "هاتف المنشأة", "required": False, "format": "@", "width": 20},
            {"key": "email", "label": "البريد الإلكتروني الرسمي", "required": False, "width": 28},
            {"key": "is_branch", "label": "نوع الكيان (مقر رئيسي / فرع)", "required": True, "dropdown": "branch_types", "width": 24},
            {"key": "parent_company", "label": "الشركة الأم (في حال كان فرعاً)", "required": False, "width": 28},
        ],
        "example": [
            "شركة النخبة الذكية للتقنية", "Al-Nokhba Smart Tech Co.", "1010998877", "300123456700003", "998877665", "12-345678", "مصرف الراجحي", "SA4480000123456789012345", "الرياض", "العليا", "طريق الملك فهد", "12214", "0112345678", "hr@alnokhba.sa", "مقر رئيسي", ""
        ],
        "rules": [
            "الحقول التي تحمل علامة (*) إلزامية لإنشاء المنشأة في Odoo.",
            "الرقم الضريبي يتكون من 15 رقماً يبدأ وينتهي بالرقم 3 وفق هيئة الزكاة والضريبة والجمارك (ZATCA).",
            "السجل التجاري يتكون من 10 أرقام دقيقة.",
            "الآيبان يبدأ بـ SA ويتكون من 24 خانة لحماية الأجور."
        ],
        "laws": [
            "نظام الشركات وهيئة الزكاة: تطابق الاسم التجاري مع السجل والرقم الضريبي إلزامي.",
            "برنامج حماية الأجور (WPS): يلزم تسجيل الآيبان الصحيح المعتمد لدى البنك المركزي السعودي."
        ]
    }


def get_contracts_spec() -> Dict[str, Any]:
    return {
        "title": "العقود والبدلات (Contracts & Allowances - hr.version)",
        "file_name": "template_contracts_allowances.xlsx",
        "sheet_name": "Contracts",
        "columns": [
            {"key": "emp_id", "label": "رقم هوية / إقامة الموظف *", "required": True, "format": "@", "width": 26},
            {"key": "emp_name", "label": "اسم الموظف الثلاثي *", "required": True, "width": 28},
            {"key": "contract_type", "label": "نوع العقد *", "required": True, "dropdown": "contract_types", "width": 22},
            {"key": "start_date", "label": "تاريخ بداية العقد *", "required": True, "format": "YYYY-MM-DD", "width": 20},
            {"key": "end_date", "label": "تاريخ نهاية العقد (للمحدد)", "required": False, "format": "YYYY-MM-DD", "width": 22},
            {"key": "probation_days", "label": "فترة التجربة بالأيام (حد أقصى 180) *", "required": True, "width": 24},
            {"key": "wage", "label": "الراتب الأساسي (ر.س) *", "required": True, "format": "#,##0.00", "width": 22},
            {"key": "housing", "label": "بدل السكن الشهري (ر.س) *", "required": True, "format": "#,##0.00", "width": 22},
            {"key": "transport", "label": "بدل النقل الشهري (ر.س) *", "required": True, "format": "#,##0.00", "width": 22},
            {"key": "other_allowance", "label": "بدلات أخرى ثابتة (ر.س)", "required": False, "format": "#,##0.00", "width": 22},
            {"key": "total_salary", "label": "إجمالي الراتب الشهري (تلقائي)", "required": False, "formula": True, "format": "#,##0.00", "width": 24},
        ],
        "example": [
            "1088776655", "عبدالله بن محمد الغامدي", "محدد المدة", "2026-01-01", "2027-01-01", 90, 8000.00, 2000.00, 1000.00, 500.00, "=G3+H3+I3+J3"
        ],
        "rules": [
            "رقم هوية أو إقامة الموظف يربط العقد تلقائياً بالموظف المسجل في Odoo.",
            "إجمالي الراتب يتم احتسابه آلياً بصيغة إكسل = الأساسي + السكن + النقل + البدلات الأخرى.",
            "التواريخ يجب أن تكون بتنسيق YYYY-MM-DD."
        ],
        "laws": [
            "المادة 53 من نظام العمل: لا يجوز أن تزيد فترة التجربة على 90 يوماً، ويجوز باتفاق خطي صريح تمديدها بما لا يتجاوز 180 يوماً.",
            "تطابق بنود العقد مع منصة قوى والحد الأدنى للأجور للسعوديين (4,000 ريال لاحتساب نطاقات كامل)."
        ]
    }


def get_payroll_gosi_spec() -> Dict[str, Any]:
    return {
        "title": "الرواتب وتأمينات GOSI وحماية الأجور (Payroll & GOSI)",
        "file_name": "template_payroll_gosi.xlsx",
        "sheet_name": "Payroll_GOSI",
        "columns": [
            {"key": "emp_id", "label": "رقم هوية / إقامة الموظف *", "required": True, "format": "@", "width": 26},
            {"key": "emp_name", "label": "اسم الموظف *", "required": True, "width": 28},
            {"key": "gosi_type", "label": "نوع الاشتراك التأميني *", "required": True, "dropdown": "gosi_types", "width": 32},
            {"key": "gosi_sub_num", "label": "رقم المشترك في التأمينات", "required": False, "format": "@", "width": 24},
            {"key": "bank_name", "label": "بنك الموظف (لتحويل الراتب) *", "required": True, "dropdown": "banks", "width": 24},
            {"key": "iban", "label": "آيبان الموظف (WPS) *", "required": True, "format": "@", "width": 32},
            {"key": "gosi_wage", "label": "الأجر الخاضع للاشتراك (أساسي + سكن) *", "required": True, "format": "#,##0.00", "width": 28},
            {"key": "emp_gosi_ded", "label": "استقطاع الموظف للتأمينات (تلقائي)", "required": False, "formula": True, "format": "#,##0.00", "width": 26},
            {"key": "comp_gosi_share", "label": "حصة الشركة للتأمينات (تلقائي)", "required": False, "formula": True, "format": "#,##0.00", "width": 26},
            {"key": "net_salary", "label": "صافي الراتب المتوقع للتحويل", "required": False, "formula": True, "format": "#,##0.00", "width": 26},
        ],
        "example": [
            "1088776655", "عبدالله بن محمد الغامدي", "سعودي - مشترك قديم (21.5%)", "12345678", "مصرف الراجحي", "SA1280000987654321098765", 10000.00, "=G3*0.0975", "=G3*0.1175", "=G3-H3"
        ],
        "rules": [
            "نوع التأمينات يحدد تلقائياً نسب الحسم وحصة الشركة في مسير الرواتب.",
            "الآيبان البنكي إلزامي لتوليد ملفات نظام حماية الأجور (WPS SIF).",
            "الأجر الخاضع للتأمينات في النظام السعودي يشمل الراتب الأساسي + بدل السكن النقدي فقط بحد أقصى 45,000 ريال."
        ],
        "laws": [
            "نظام التأمينات الاجتماعية: نسبة المشترك السعودي القديم (9% معاشات + 0.75% ساند = 9.75% على الموظف، و 11.75% على صاحب العمل).",
            "نظام التأمينات الجديد 2024: يخضع لنسب متدرجة تبدأ بـ 10% إلى 11% تدريجياً.",
            "غير السعودي: 2% أخطار مهنية فقط تتحملها المنشأة بالكامل ولا يُخصم من أجر العامل أي شيء."
        ]
    }


def get_timeoff_spec() -> Dict[str, Any]:
    return {
        "title": "الإجازات والأرصدة الافتتاحية (Time Off & Balances)",
        "file_name": "template_timeoff.xlsx",
        "sheet_name": "Time_Off",
        "columns": [
            {"key": "emp_id", "label": "رقم هوية / إقامة الموظف *", "required": True, "format": "@", "width": 26},
            {"key": "emp_name", "label": "اسم الموظف *", "required": True, "width": 28},
            {"key": "leave_type", "label": "نوع الإجازة *", "required": True, "dropdown": "leave_types", "width": 26},
            {"key": "start_date", "label": "تاريخ بداية الإجازة *", "required": True, "format": "YYYY-MM-DD", "width": 22},
            {"key": "end_date", "label": "تاريخ نهاية الإجازة *", "required": True, "format": "YYYY-MM-DD", "width": 22},
            {"key": "days_count", "label": "عدد الأيام المطلوبة *", "required": True, "width": 20},
            {"key": "opening_balance", "label": "الرصيد الافتتاحي المتراكم السابق", "required": False, "width": 24},
            {"key": "notes", "label": "ملاحظات وتفاصيل الإجازة", "required": False, "width": 30},
        ],
        "example": [
            "1088776655", "عبدالله بن محمد الغامدي", "إجازة سنوية اعتيادية", "2026-08-01", "2026-08-15", 15, 21, "إجازة سنوية مجدولة"
        ],
        "rules": [
            "التواريخ بصيغة YYYY-MM-DD.",
            "الرصيد الافتتاحي يُسجل عند تهيئة رصيد سابق للموظف في Odoo.",
            "نوع الإجازة يتم اختياره من القائمة المنسدلة."
        ],
        "laws": [
            "المادة 109 من نظام العمل: يستحق العامل إجازة سنوية لا تقل عن 21 يوماً بأجر كامل، تزداد إلى 30 يوماً إذا أمضى 5 سنوات متصلة.",
            "المادة 113: إجازات المناسبات (5 أيام وفاة، 5 أيام زواج، 3 أيام مولود) بأجر كامل."
        ]
    }


def get_attendance_spec() -> Dict[str, Any]:
    return {
        "title": "ساعات الحضور وسجلات الدوام (Attendance Sheets)",
        "file_name": "template_attendance.xlsx",
        "sheet_name": "Attendances",
        "columns": [
            {"key": "emp_id", "label": "رقم هوية / إقامة الموظف *", "required": True, "format": "@", "width": 26},
            {"key": "emp_name", "label": "اسم الموظف *", "required": True, "width": 28},
            {"key": "month", "label": "شهر وسنة الكشف (YYYY-MM) *", "required": True, "format": "@", "width": 24},
            {"key": "branch", "label": "موقع العمل / الفرع *", "required": True, "dropdown": "branches", "width": 24},
            {"key": "expected_days", "label": "أيام العمل المفترضة *", "required": True, "width": 20},
            {"key": "actual_days", "label": "أيام الحضور الفعلية *", "required": True, "width": 20},
            {"key": "worked_hours", "label": "إجمالي ساعات الحضور الفعلية", "required": False, "width": 24},
            {"key": "late_minutes", "label": "دقائق التأخير الإجمالية", "required": False, "width": 22},
            {"key": "absence_days", "label": "أيام الغياب غير المبرر", "required": False, "width": 22},
        ],
        "example": [
            "1088776655", "عبدالله بن محمد الغامدي", "2026-10", "فرع الرياض - المقر الرئيسي", 22, 22, 176.0, 35, 0
        ],
        "rules": [
            "الشهر يُكتب بصيغة YYYY-MM (مثلاً 2026-10).",
            "أيام الغياب غير المبرر تنعكس في مسير الرواتب تلقائياً بعد التحقيق.",
            "ساعات الحضور تقارن بسياسة الدوام المعتمدة في Odoo (rm_hr_attendance_sheet)."
        ],
        "laws": [
            "المادة 98: ساعات العمل الفعلية لا تزيد على 8 ساعات في اليوم أو 48 ساعة في الأسبوع، وتُخفض لـ 6 ساعات يومياً في شهر رمضان للمسلمين."
        ]
    }


def get_overtime_spec() -> Dict[str, Any]:
    return {
        "title": "العمل الإضافي والأوفرتايم (Overtime Requests - مادة 107)",
        "file_name": "template_overtime.xlsx",
        "sheet_name": "Overtime",
        "columns": [
            {"key": "emp_id", "label": "رقم هوية / إقامة الموظف *", "required": True, "format": "@", "width": 26},
            {"key": "emp_name", "label": "اسم الموظف *", "required": True, "width": 28},
            {"key": "date", "label": "تاريخ العمل الإضافي *", "required": True, "format": "YYYY-MM-DD", "width": 22},
            {"key": "overtime_type", "label": "نوع يوم الإضافي *", "required": True, "dropdown": "overtime_types", "width": 30},
            {"key": "hours", "label": "عدد الساعات الإضافية *", "required": True, "width": 22},
            {"key": "hourly_wage", "label": "أجر الساعة المعتاد (الأساسي / 240) *", "required": True, "format": "#,##0.00", "width": 28},
            {"key": "multiplier", "label": "معامل الإضافي (1.5x تلقائي)", "required": False, "formula": True, "width": 24},
            {"key": "total_amount", "label": "المبلغ الإجمالي المستحق (تلقائي)", "required": False, "formula": True, "format": "#,##0.00", "width": 26},
            {"key": "reason", "label": "مبرر التكليف وموافقة الإدارة *", "required": True, "width": 32},
        ],
        "example": [
            "1088776655", "عبدالله بن محمد الغامدي", "2026-10-15", "ساعات عمل عادية (1.5x الأجر الأساسي)", 4.0, 33.33, 1.5, "=E3*F3*G3", "إنجاز الإقفال المالي الشهري"
        ],
        "rules": [
            "يتم حساب أجر الساعة بقسمة الأجر الأساسي على 240 ساعة شهرياً.",
            "مبلغ الأوفرتايم = عدد الساعات * أجر الساعة * 1.5.",
            "إرفاق سبب التكليف إلزامي للموافقة الإدارية."
        ],
        "laws": [
            "المادة 107 من نظام العمل السعودي: يدفع صاحب العمل للعامل عن ساعات العمل الإضافية أجراً يوازي أجر الساعة مضافاً إليه 50% من أجره الأساسي (أجر ساعة ونصف).",
            "المادة 106: لا يجوز تشغيل العامل أكثر من الحد الأقصى السنوي لساعات العمل الإضافية المحدد نظاماً."
        ]
    }


def get_loans_spec() -> Dict[str, Any]:
    return {
        "title": "قروض وسلف الموظفين والأقساط (Loans & Installments - مادة 92)",
        "file_name": "template_loans_installments.xlsx",
        "sheet_name": "Loans",
        "columns": [
            {"key": "emp_id", "label": "رقم هوية / إقامة الموظف *", "required": True, "format": "@", "width": 26},
            {"key": "emp_name", "label": "اسم الموظف *", "required": True, "width": 28},
            {"key": "loan_type", "label": "نوع السلفة / القرض *", "required": True, "dropdown": "loan_types", "width": 26},
            {"key": "loan_amount", "label": "إجمالي مبلغ القرض المطلوب (ر.س) *", "required": True, "format": "#,##0.00", "width": 28},
            {"key": "term_months", "label": "مدة السداد بالأشهر (الأقساط) *", "required": True, "width": 24},
            {"key": "installment_amt", "label": "قيمة القسط الشهري (تلقائي)", "required": False, "formula": True, "format": "#,##0.00", "width": 26},
            {"key": "monthly_salary", "label": "إجمالي راتب الموظف الشهري *", "required": True, "format": "#,##0.00", "width": 26},
            {"key": "installment_ratio", "label": "نسبة الاستقطاع (حد أقصى 25%)", "required": False, "formula": True, "format": "0.0%", "width": 26},
            {"key": "start_date", "label": "تاريخ بداية أول قسط *", "required": True, "format": "YYYY-MM-DD", "width": 22},
            {"key": "payment_method", "label": "طريقة الصرف *", "required": True, "dropdown": "payment_methods", "width": 20},
            {"key": "reason", "label": "سبب طلب القرض / السلفة *", "required": True, "width": 30},
        ],
        "example": [
            "1088776655", "عبدالله بن محمد الغامدي", "سلفة شخصية قصيرة الأجل", 12000.00, 6, "=D3/E3", 11000.00, "=F3/G3", "2026-11-01", "تحويل بنكي", "ظرف عائلي طارئ"
        ],
        "rules": [
            "قيمة القسط الشهري = إجمالي القرض / عدد أشهر السداد.",
            "نسبة الاستقطاع = القسط الشهري / الراتب الشهري.",
            "يجب ألا تزيد نسبة الاستقطاع عن 25% تحت أي ظرف امتثالاً لنظام العمل."
        ],
        "laws": [
            "المادة 92 من نظام العمل السعودي: لا يجوز حسم أي مبلغ من أجر العامل لقاء قروض صاحب العمل بما يزيد على 25% من أجر العامل لحماية كفايته المعيشية.",
            "تخصم الأقساط الشهرية آلياً عبر مسير الرواتب hr.payslip في Odoo."
        ]
    }


def get_disciplinary_spec() -> Dict[str, Any]:
    return {
        "title": "الجزاءات والإنذارات والمخالفات (Disciplinary Management)",
        "file_name": "template_disciplinary.xlsx",
        "sheet_name": "Disciplinary",
        "columns": [
            {"key": "emp_id", "label": "رقم هوية / إقامة الموظف *", "required": True, "format": "@", "width": 26},
            {"key": "emp_name", "label": "اسم الموظف *", "required": True, "width": 28},
            {"key": "violation_date", "label": "تاريخ ارتكاب المخالفة *", "required": True, "format": "YYYY-MM-DD", "width": 22},
            {"key": "penalty_type", "label": "نوع الجزاء الموقع *", "required": True, "dropdown": "penalty_types", "width": 30},
            {"key": "deduction_days", "label": "عدد أيام الخصم (حد أقصى 5 أيام)", "required": False, "width": 26},
            {"key": "investigation_date", "label": "تاريخ التحقيق وسماع الأقوال *", "required": True, "format": "YYYY-MM-DD", "width": 26},
            {"key": "reason", "label": "وصف المخالفة وقرار الإدارة *", "required": True, "width": 34},
        ],
        "example": [
            "1088776655", "عبدالله بن محمد الغامدي", "2026-09-10", "خصم يوم من الأجر", 1, "2026-09-12", "تكرار التأخر الصباحي بدون عذر بعد إنذار أولي"
        ],
        "rules": [
            "يجب إجراء تحقيق كتابي مع الموظف وسماع أقواله قبل توقيع أي جزاء.",
            "الخصم يطبق في مسير راتب نفس الشهر الذي وقع فيه الجزاء.",
            "تدرج العقوبة إلزامي: إنذار ➔ خصم ➔ إيقاف."
        ],
        "laws": [
            "المادة 66 من نظام العمل: حصر الجزاءات التأديبية في (الإنذار، الغرامة، الحرمان من العلاوة، تأجيل الترقية، الإيقاف، الفصل).",
            "المادة 70: لا يجوز توقيع غرامة تزيد على أجر 5 أيام عن المخالفة الواحدة، ولا يجوز أن يقتطع من أجر العامل في الشهر الواحد أكثر من أجر 5 أيام وفاءً للغرامات.",
            "المادة 71: لا يجوز توقيع جزاء تأديبي إلا بعد إبلاغ العامل كتابة والتحقيق معه وسماع دفاعه وتثبيت ذلك في محضر."
        ]
    }


def get_end_of_service_spec() -> Dict[str, Any]:
    return {
        "title": "مكافأة نهاية الخدمة والتسويات (End of Service Rewards - مواد 77, 80, 84, 85)",
        "file_name": "template_end_of_service.xlsx",
        "sheet_name": "End_of_Service",
        "columns": [
            {"key": "emp_id", "label": "رقم هوية / إقامة الموظف *", "required": True, "format": "@", "width": 26},
            {"key": "emp_name", "label": "اسم الموظف *", "required": True, "width": 28},
            {"key": "hire_date", "label": "تاريخ بداية الخدمة *", "required": True, "format": "YYYY-MM-DD", "width": 22},
            {"key": "term_date", "label": "تاريخ انتهاء الخدمة (آخر دوام) *", "required": True, "format": "YYYY-MM-DD", "width": 24},
            {"key": "reason", "label": "سبب انتهاء العلاقة العمالية *", "required": True, "dropdown": "term_reasons", "width": 36},
            {"key": "last_salary", "label": "آخر أجر شهري كامل (أساسي+بدلات) *", "required": True, "format": "#,##0.00", "width": 28},
            {"key": "service_years", "label": "مدة الخدمة بالسنوات (تلقائي)", "required": False, "formula": True, "format": "0.00", "width": 22},
            {"key": "eos_amount", "label": "مكافأة نهاية الخدمة المستحقة (تلقائي)", "required": False, "formula": True, "format": "#,##0.00", "width": 28},
            {"key": "leave_comp", "label": "بدل رصيد الإجازات المتبقية (ر.س)", "required": False, "format": "#,##0.00", "width": 26},
            {"key": "loan_deduct", "label": "خصم السلف والقروض المتبقية (ر.س)", "required": False, "format": "#,##0.00", "width": 26},
            {"key": "net_settlement", "label": "صافي مبلغ المخالصة النهائية", "required": False, "formula": True, "format": "#,##0.00", "width": 26},
        ],
        "example": [
            "1088776655", "عبدالله بن محمد الغامدي", "2020-01-01", "2026-01-01", "انتهاء مدة العقد (مادة 84 - مكافأة كاملة)", 11000.00, "=ROUND((D3-C3)/365.25, 2)", 49500.00, 5500.00, 0.00, "=H3+I3-J3"
        ],
        "rules": [
            "مدة الخدمة تحتسب من تاريخ المباشرة إلى آخر يوم عمل.",
            "مكافأة نهاية الخدمة تحتسب على أساس آخر أجر كامل تقاضاه العامل (الأساسي + البدلات).",
            "صافي المخالصة = مكافأة نهاية الخدمة + بدل الإجازات - السلف المتبقية."
        ],
        "laws": [
            "المادة 84: أجر نصف شهر عن كل سنة من السنوات الخمس الأولى، وأجر شهر عن كل سنة من السنوات التالية.",
            "المادة 85: في حال استقالة العامل يستحق ثلث المكافأة بعد خدمة من سنتين لـ 5 سنوات، وثلثيها من 5 لـ 10 سنوات، وتستحق كاملة إذا بلغت خدمته 10 سنوات فأكثر.",
            "المادة 80: حالات الفصل المشروع دون مكافأة أو إشعار (الاعتداء، التزوير، الخيانة، إفشاء الأسرار).",
            "المادة 88: يجب دفع مكافأة نهاية الخدمة وتصفية حقوق العامل خلال أسبوع من تاريخ انتهاء العقد."
        ]
    }


def get_appraisals_spec() -> Dict[str, Any]:
    return {
        "title": "تقييمات الأداء والموظفين (Employee Appraisals)",
        "file_name": "template_appraisals.xlsx",
        "sheet_name": "Appraisals",
        "columns": [
            {"key": "emp_id", "label": "رقم هوية / إقامة الموظف *", "required": True, "format": "@", "width": 26},
            {"key": "emp_name", "label": "اسم الموظف *", "required": True, "width": 28},
            {"key": "year", "label": "سنة التقييم (YYYY) *", "required": True, "format": "@", "width": 18},
            {"key": "type", "label": "نوع التقييم *", "required": True, "dropdown": "appraisal_types", "width": 26},
            {"key": "manager", "label": "اسم المدير المقيّم *", "required": True, "width": 26},
            {"key": "kpi_score", "label": "درجة الأهداف والمؤشرات (من 100) *", "required": True, "width": 26},
            {"key": "competency_score", "label": "درجة الكفاءات والسلوك (من 100) *", "required": True, "width": 26},
            {"key": "total_score", "label": "المعدل العام النهائي (من 100)", "required": False, "formula": True, "format": "0.0", "width": 24},
            {"key": "rating", "label": "التقدير المعتمد *", "required": True, "dropdown": "ratings", "width": 22},
            {"key": "recommendation", "label": "التوصيات (ترقية / علاوة / تطوير)", "required": False, "width": 32},
        ],
        "example": [
            "1088776655", "عبدالله بن محمد الغامدي", "2026", "تقييم سنوي شامل", "فهد السبيعي", 92.0, 90.0, "=(F3*0.7)+(G3*0.3)", "ممتاز (90 - 100)", "ترقية لمستوى وظيفي أعلى مع علاوة استحقاق"
        ],
        "rules": [
            "المعدل العام يُحسب بوزن نسبي (70% أهداف و 30% كفاءات).",
            "التقدير يطابق معايير تقييم الأداء المعتمدة في Odoo (prosys_hr_appraisal)."
        ],
        "laws": [
            "لائحة تنظيم العمل: تقييم فترة التجربة يحدد تثبيت الموظف أو إنهاء عقده خلال المهلة المحددة نظاماً بموجب المادة 53."
        ]
    }


def get_recruitment_spec() -> Dict[str, Any]:
    return {
        "title": "طلبات التوظيف وشواغر المتقدمين (Recruitment & Applicants)",
        "file_name": "template_recruitment.xlsx",
        "sheet_name": "Recruitment",
        "columns": [
            {"key": "name", "label": "اسم المرشح *", "required": True, "width": 28},
            {"key": "job", "label": "الوظيفة المتقدم لها *", "required": True, "dropdown": "jobs", "width": 24},
            {"key": "dept", "label": "القسم المطلوب *", "required": True, "dropdown": "departments", "width": 24},
            {"key": "branch", "label": "الفرع وموقع العمل *", "required": True, "dropdown": "branches", "width": 24},
            {"key": "nationality", "label": "الجنسية *", "required": True, "dropdown": "nationalities", "width": 20},
            {"key": "mobile", "label": "رقم الجوال *", "required": True, "format": "@", "width": 20},
            {"key": "email", "label": "البريد الإلكتروني", "required": False, "width": 28},
            {"key": "expected_salary", "label": "الراتب المتوقع (ر.س)", "required": False, "format": "#,##0.00", "width": 22},
            {"key": "score", "label": "درجة المقابلة (من 100)", "required": False, "width": 20},
            {"key": "status", "label": "حالة المرشح *", "required": True, "dropdown": "applicant_statuses", "width": 24},
        ],
        "example": [
            "سارة بنت خالد المطيري", "أخصائي تسويق", "المبيعات والتسويق", "فرع الرياض - المقر الرئيسي", "سعودي", "0551234567", "sara@gmail.com", 8500.00, 94, "عرض عمل مرسل"
        ],
        "rules": [
            "المرشح المقبول في حالة 'عرض عمل معتمد' يمكن تحويله مباشرة لموظف في Odoo عبر سراج."
        ],
        "laws": [
            "قرارات التوطين والمهن المقفلة: مراعاة نسب السعودة والمسميات المسعودة حصراً لدى وزارة الموارد البشرية."
        ]
    }


def get_gr_transactions_spec() -> Dict[str, Any]:
    return {
        "title": "المعاملات والتأشيرات الحكومية (GR Transactions - مقيم وقوى)",
        "file_name": "template_gr_transactions.xlsx",
        "sheet_name": "GR_Transactions",
        "columns": [
            {"key": "emp_id", "label": "رقم هوية / إقامة الموظف *", "required": True, "format": "@", "width": 26},
            {"key": "emp_name", "label": "اسم الموظف *", "required": True, "width": 28},
            {"key": "tx_type", "label": "نوع المعاملة الحكومية *", "required": True, "dropdown": "gr_types", "width": 30},
            {"key": "iqama_hijri", "label": "تاريخ انتهاء الإقامة هجري", "required": False, "format": "@", "width": 24},
            {"key": "iqama_greg", "label": "تاريخ انتهاء الإقامة ميلادي", "required": False, "format": "YYYY-MM-DD", "width": 24},
            {"key": "passport_num", "label": "رقم جواز السفر", "required": False, "format": "@", "width": 22},
            {"key": "passport_exp", "label": "تاريخ انتهاء الجواز", "required": False, "format": "YYYY-MM-DD", "width": 22},
            {"key": "border_num", "label": "رقم الحدود (للقادمين الجدد)", "required": False, "format": "@", "width": 24},
            {"key": "gov_fees", "label": "الرسوم الحكومية المقدرة (ر.س)", "required": False, "format": "#,##0.00", "width": 24},
            {"key": "status", "label": "حالة المعاملة *", "required": True, "dropdown": "tx_statuses", "width": 20},
        ],
        "example": [
            "2099887766", "طارق بن أحمد المنصور", "تجديد إقامة", "1448-05-15", "2026-11-20", "A12345678", "2028-06-30", "", 650.00, "تحت الإجراء"
        ],
        "rules": [
            "تواريخ انتهاء الإقامة والجواز تنعكس في ملف الموظف لتفعيل تنبيهات التجديد المبكر في Odoo."
        ],
        "laws": [
            "نظام الإقامة: تجديد الإقامة قبل انتهائها لتفادي الغرامات المالية المقررة من الجوازات."
        ]
    }


def get_employees_spec(ref_data: Dict[str, List[str]]) -> Dict[str, Any]:
    return {
        "title": "بيانات الموظفين الأساسية ومواقع العمل (Employees Master Data)",
        "file_name": "template_employees.xlsx",
        "sheet_name": "Employees",
        "columns": [
            {"key": "name", "label": "اسم الموظف الكامل بالعربي *", "required": True, "width": 30},
            {"key": "name_en", "label": "اسم الموظف بالإنجليزي", "required": False, "width": 28},
            {"key": "id_number", "label": "رقم الهوية الوطنية / الإقامة (10 أرقام) *", "required": True, "format": "@", "width": 28},
            {"key": "nationality", "label": "الجنسية *", "required": True, "dropdown": "nationalities", "width": 20},
            {"key": "gender", "label": "الجنس (ذكر / أنثى) *", "required": True, "dropdown": "genders", "width": 20},
            {"key": "birthday", "label": "تاريخ الميلاد *", "required": True, "format": "YYYY-MM-DD", "width": 20},
            {"key": "marital", "label": "الحالة الاجتماعية", "required": False, "dropdown": "marital_statuses", "width": 20},
            {"key": "mobile", "label": "رقم الجوال (05xxxxxxxx) *", "required": True, "format": "@", "width": 24},
            {"key": "work_email", "label": "البريد الإلكتروني للعمل", "required": False, "width": 28},
            {"key": "company", "label": "المنشأة التابع لها *", "required": True, "dropdown": "companies", "width": 28},
            {"key": "branch", "label": "الفرع / موقع العمل *", "required": True, "dropdown": "branches", "width": 26},
            {"key": "department", "label": "القسم / الإدارة *", "required": True, "dropdown": "departments", "width": 26},
            {"key": "job_title", "label": "المسمى الوظيفي *", "required": True, "dropdown": "jobs", "width": 24},
            {"key": "hiring_date", "label": "تاريخ المباشرة *", "required": True, "format": "YYYY-MM-DD", "width": 20},
        ],
        "example": [
            "عبدالله بن محمد الغامدي", "Abdullah Al-Ghamdi", "1088776655", "سعودي", "ذكر", "1994-05-12", "متزوج", "0501234567", "a.ghamdi@alnokhba.sa", "شركة النخبة الذكية للتقنية", "فرع الرياض - المقر الرئيسي", "المالية والمحاسبة", "مسؤول محاسبة", "2026-01-01"
        ],
        "rules": [
            "رقم الهوية الوطنية أو الإقامة يتكون من 10 أرقام.",
            "رقم الجوال يبدأ بـ 05 ويتكون من 10 خانات.",
            "يتم اختيار الشركة، الفرع، القسم، والوظيفة من القوائم المنسدلة المعتمدة في Odoo."
        ],
        "laws": [
            "نظام العمل السعودي: تسجيل تاريخ المباشرة الفعلي يحدد تاريخ بدء احتساب الحقوق والتأمينات ونهاية الخدمة."
        ]
    }


# ---------------------------------------------------------------------------
# Main Builders
# ---------------------------------------------------------------------------
def _safe_save_workbook(wb: openpyxl.Workbook, out_path: Path) -> Path:
    """Attempts to save the workbook, gracefully falling back if locked by Excel."""
    try:
        wb.save(out_path)
        return out_path
    except PermissionError:
        # File is locked by Excel or another process on Windows
        alt_path = out_path.parent / f"{out_path.stem}_updated{out_path.suffix}"
        try:
            wb.save(alt_path)
            print(f"  ⚠️ [LOCKED] الملف {out_path.name} مفتوح حالياً في Microsoft Excel! تم حفظ النسخة المحدثة في: {alt_path.name}")
            return alt_path
        except Exception:
            raise PermissionError(
                f"الملف {out_path.name} مفتوح حالياً في برنامج Microsoft Excel على جهازك. "
                f"يرجى إغلاق الملف في Excel ثم إعادة المحاولة."
            )


def build_standalone_template(spec: Dict[str, Any], ref_catalog: Dict[str, List[str]], out_path: Path) -> None:
    """Builds a single modular .xlsx template file."""
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # 1. Instructions Sheet (first tab)
    _build_instructions_sheet(wb, spec["title"], spec.get("rules", []), spec.get("laws", []))

    # 2. Data Entry Sheet
    ws_data = wb.create_sheet(title=spec["sheet_name"])
    _apply_sheet_styling(ws_data, spec["title"], spec["columns"], spec["example"])

    # 3. Reference Sheet (locked)
    ws_ref = _build_reference_sheet(wb, ref_catalog)

    # 4. Attach Data Validation Dropdowns
    for col_idx, col_meta in enumerate(spec["columns"], start=1):
        dd_key = col_meta.get("dropdown")
        if dd_key and dd_key in ref_catalog:
            items = ref_catalog[dd_key]
            # Find column in Reference sheet
            ref_col_idx = list(ref_catalog.keys()).index(dd_key) * 2 + 1
            ref_col_letter = get_column_letter(ref_col_idx)
            ref_formula = f"=Reference!${ref_col_letter}$2:${ref_col_letter}${len(items) + 1}"

            dv = DataValidation(type="list", formula1=ref_formula, allow_blank=True)
            dv.error = "الرجاء الاختيار من القائمة المنسدلة المعتمدة فقط."
            dv.errorTitle = "قيمة غير صالحة"
            ws_data.add_data_validation(dv)
            col_letter = get_column_letter(col_idx)
            dv.add(f"{col_letter}4:{col_letter}500")

    saved_path = _safe_save_workbook(wb, out_path)
    print(f"  [OK] Generated Modular: {saved_path.name}")


def build_master_onboarding_workbook(specs: List[Dict[str, Any]], ref_catalog: Dict[str, List[str]], out_path: Path) -> None:
    """Builds the comprehensive multi-tab Master Onboarding Workbook for new clients."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # 1. Master Instructions
    master_rules = [
        "هذا الملف هو القالب الشامل والموحد لتأسيس بيانات منشأتك بالكامل في نظام Odoo HR.",
        "ابدأ بتعبئة تبويب (1_بيانات_المنشأة) ثم انتقل للتبويبات التالية بالترتيب.",
        "تبويب (الموظفون) يمثل المرجع الأساسي، حيث يتم استخدام (رقم الهوية / الإقامة) لربط عقودهم، رواتبهم، إجازاتهم، وقروضهم في بقية التبويبات.",
        "الحقول ذات الخلفية الكحلية الداكنة (*) هي حقول إلزامية لا يمكن استكمال التأسيس بدونها.",
        "الحقول الخضراء تحتوي على معادلات احتساب تلقائية (مثل إجمالي الراتب، خصم التأمينات، القسط الشهري) يرجى عدم مسحها.",
        "التواريخ تعتمد الصيغة القياسية الدولية: YYYY-MM-DD (مثال: 2026-10-01)."
    ]
    master_laws = [
        "نظام العمل السعودي (الملكي م/51): توثيق عقود العمل، الالتزام بالحد الأدنى للأجور، وحدود ساعات العمل والإضافي.",
        "نظام التأمينات الاجتماعية: تطبيق نسب الحسم بدقة للمشتركين السعوديين (القديم 21.5% والجديد المتدرج) وغير السعوديين (2% أخطار مهنية).",
        "المادة 92: حظر تجاوز حسم قروض وصاحب العمل عن 25% من أجر العامل الشهري.",
        "المواد 84 و 85: احتساب مكافأة نهاية الخدمة بدقة وفق أسباب انتهاء العلاقة العمالية."
    ]
    _build_instructions_sheet(wb, "تأسيس المنشأة الشامل (Master Onboarding)", master_rules, master_laws)

    # 2. Add each functional tab
    tab_number = 1
    for spec in specs:
        tab_name = f"{tab_number}_{spec['sheet_name'][:24]}"
        ws_data = wb.create_sheet(title=tab_name)
        _apply_sheet_styling(ws_data, spec["title"], spec["columns"], spec["example"])

        # Attach dropdown validations referencing the Reference tab
        for col_idx, col_meta in enumerate(spec["columns"], start=1):
            dd_key = col_meta.get("dropdown")
            if dd_key and dd_key in ref_catalog:
                items = ref_catalog[dd_key]
                ref_col_idx = list(ref_catalog.keys()).index(dd_key) * 2 + 1
                ref_col_letter = get_column_letter(ref_col_idx)
                ref_formula = f"=Reference!${ref_col_letter}$2:${ref_col_letter}${len(items) + 1}"

                dv = DataValidation(type="list", formula1=ref_formula, allow_blank=True)
                dv.error = "الرجاء الاختيار من القائمة المنسدلة المعتمدة فقط."
                dv.errorTitle = "قيمة غير صالحة"
                ws_data.add_data_validation(dv)
                col_letter = get_column_letter(col_idx)
                dv.add(f"{col_letter}4:{col_letter}500")

        tab_number += 1

    # 3. Add Reference Tab at the end
    _build_reference_sheet(wb, ref_catalog)

    saved_master = _safe_save_workbook(wb, out_path)
    print(f"\n🌟 [MASTER SUCCESS] Generated Master Onboarding Template at:\n   --> {saved_master}\n")


def generate_all(url: Optional[str] = None, db: Optional[str] = None, user: Optional[str] = None, key: Optional[str] = None):
    """Generates the full suite of modular and master templates."""
    print("=" * 70)
    print("🚀 Odoo HR Multi-Module & Master Templates Suite Generator")
    print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    if url or db:
        print(f"Target Odoo Instance: {url} | DB: {db} | User: {user}")
    else:
        print("Target: Using Active Odoo Configuration")
    print("=" * 70)

    # 1. Prepare reference catalog
    live_data = _load_live_reference_data(url=url, db=db, user=user, key=key)
    ref_catalog: Dict[str, List[str]] = {
        "companies": live_data["companies"],
        "branches": live_data["branches"],
        "departments": live_data["departments"],
        "jobs": live_data["jobs"],
        "banks": BANKS_SAUDI,
        "cities": CITIES_SAUDI,
        "nationalities": NATIONALITIES,
        "genders": ["ذكر", "أنثى"],
        "marital_statuses": ["أعزب", "متزوج", "مطلق", "أرمل"],
        "branch_types": ["مقر رئيسي", "فرع تابع"],
        "contract_types": ["محدد المدة", "غير محدد المدة"],
        "gosi_types": GOSI_TYPES,
        "leave_types": LEAVE_TYPES,
        "loan_types": LOAN_TYPES,
        "payment_methods": ["تحويل بنكي", "نقدي (كاش)", "شيك مصرفي"],
        "penalty_types": PENALTY_TYPES,
        "overtime_types": OVERTIME_TYPES,
        "term_reasons": TERMINATION_REASONS,
        "appraisal_types": APPRAISAL_TYPES,
        "ratings": ["ممتاز (90 - 100)", "جيد جداً (80 - 89)", "جيد (70 - 79)", "مرضي (60 - 69)", "غير مرضي (أقل من 60)"],
        "applicant_statuses": ["مقبول مبدئياً", "مقابلة مجدولة", "عرض عمل مرسل", "معتمد ومباشر", "مرفوض"],
        "gr_types": GR_TYPES,
        "tx_statuses": ["جديدة", "تحت الإجراء", "مكتملة ومعتمدة", "ملغاة"],
    }

    # 2. Gather all 12 functional specs
    all_specs = [
        get_company_setup_spec(),
        get_employees_spec(live_data),
        get_contracts_spec(),
        get_payroll_gosi_spec(),
        get_timeoff_spec(),
        get_attendance_spec(),
        get_overtime_spec(),
        get_loans_spec(),
        get_disciplinary_spec(),
        get_end_of_service_spec(),
        get_appraisals_spec(),
        get_recruitment_spec(),
        get_gr_transactions_spec(),
    ]

    # 3. Generate Modular standalone templates
    print("\n--- Generating 13 Modular Standalone Templates ---")
    for spec in all_specs:
        out_file = MODULAR_DIR / spec["file_name"]
        build_standalone_template(spec, ref_catalog, out_file)

    # 4. Generate Master Workbook
    print("\n--- Generating Master Client Onboarding Workbook ---")
    master_file = MASTER_DIR / "Master_Client_Onboarding_Template.xlsx"
    build_master_onboarding_workbook(all_specs, ref_catalog, master_file)

    print("=" * 70)
    print("✅ All templates generated successfully!")
    print(f"Modular: {len(all_specs)} files in {MODULAR_DIR}")
    print(f"Master:  1 multi-tab file in {MASTER_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate Odoo HR Templates dynamically")
    parser.add_argument("--url", help="Odoo Server URL", default=None)
    parser.add_argument("--db", help="Odoo Database Name", default=None)
    parser.add_argument("--user", help="Odoo Username / Email", default=None)
    parser.add_argument("--key", help="Odoo API Key", default=None)
    args = parser.parse_args()

    generate_all(url=args.url, db=args.db, user=args.user, key=args.key)
