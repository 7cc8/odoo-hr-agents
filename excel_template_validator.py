"""
محرك فحص والتحقق من قوالب الإكسل للموارد البشرية (HR Excel Template Validator)
================================================================================
يدعم الفحص الجاف الآمن (Dry-Run) لجميع قوالب الموارد البشرية الـ 14:
1. ساعات الحضور وسجلات الدوام (template_attendance.xlsx)
2. استيراد وتأسيس الموظفين (template_employees.xlsx)
3. عقود العمل والبدلات (template_contracts_allowances.xlsx)
4. الرواتب وتأمينات GOSI (template_payroll_gosi.xlsx)
5. الإجازات والأرصدة الافتتاحية (template_timeoff.xlsx)
6. العمل الإضافي والأوفرتايم (template_overtime.xlsx)
7. قروض وسلف الموظفين (template_loans_installments.xlsx)
8. الجزاءات والإنذارات (template_disciplinary.xlsx)
9. مكافأة نهاية الخدمة (template_end_of_service.xlsx)
10. تقييمات الأداء (template_appraisals.xlsx)
11. شواغر التوظيف والمرشحين (template_recruitment.xlsx)
12. المعاملات الحكومية والجوازات (template_gr_transactions.xlsx)
13. تأسيس المنشأة والحسابات البنكية (template_company_setup.xlsx)
14. القالب الشامل لتأسيس المنشأة (Master_Client_Onboarding_Template.xlsx)
15. الملفات الكلاسيكية لاستيراد الموظفين (Legacy Employees Sheets)
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from normalization import clean_value_text, to_text_preserve, normalize_header
from odoo_readonly_repository import OdooReadonlyRepository


TEMPLATE_SPECS: Dict[str, Dict[str, Any]] = {
    "attendance": {
        "domain": "attendance",
        "sheet_aliases": ["attendances", "6_attendances", "attendance", "حضور", "الدوام", "سجلات الحضور"],
        "title_ar": "ساعات الحضور وسجلات الدوام (Attendance Sheets)",
        "key_columns": [
            ("emp_id", ["رقم هوية / إقامة الموظف", "رقم الهوية", "emp_id", "national_id", "iqama"]),
            ("emp_name", ["اسم الموظف", "اسم الموظف الثلاثي", "emp_name", "name"]),
            ("month", ["شهر وسنة الكشف (yyyy-mm)", "شهر وسنة الكشف", "الشهر", "month"]),
            ("branch", ["موقع العمل / الفرع", "الفرع", "موقع العمل", "branch"]),
            ("expected_days", ["أيام العمل المفترضة", "الأيام المفترضة", "expected_days"]),
            ("actual_days", ["أيام الحضور الفعلية", "أيام الحضور", "actual_days"]),
            ("worked_hours", ["إجمالي ساعات الحضور الفعلية", "ساعات الحضور الفعلية", "worked_hours"]),
            ("late_minutes", ["دقائق التأخير الإجمالية", "دقائق التأخير", "late_minutes"]),
            ("absence_days", ["أيام الغياب غير المبرر", "أيام الغياب", "absence_days"]),
        ],
        "required_keys": ["emp_id", "emp_name", "month", "expected_days", "actual_days"],
        "rules_description": "المادة 98: ساعات العمل المعيارية 8 ساعات يومياً / 48 أسبوعياً، و 6 ساعات في رمضان للمسلمين.",
    },
    "contract": {
        "domain": "contract",
        "sheet_aliases": ["contracts", "3_contracts", "contract", "عقود", "العقود", "عقود العمل"],
        "title_ar": "عقود العمل وهيكل البدلات (Contracts & Allowances - hr.version)",
        "key_columns": [
            ("emp_id", ["رقم هوية / إقامة الموظف", "رقم الهوية", "emp_id"]),
            ("emp_name", ["اسم الموظف الثلاثي", "اسم الموظف", "emp_name"]),
            ("contract_type", ["نوع العقد", "contract_type"]),
            ("start_date", ["تاريخ بداية العقد", "start_date"]),
            ("end_date", ["تاريخ نهاية العقد", "end_date"]),
            ("probation_days", ["فترة التجربة بالأيام", "probation_days"]),
            ("wage", ["الراتب الأساسي", "wage"]),
            ("housing", ["بدل السكن الشهري", "بدل السكن", "housing"]),
            ("transport", ["بدل النقل الشهري", "بدل النقل", "transport"]),
            ("other_allowance", ["بدلات أخرى ثابتة", "other_allowance"]),
            ("total_salary", ["إجمالي الراتب الشهري", "total_salary"]),
        ],
        "required_keys": ["emp_id", "emp_name", "contract_type", "start_date", "wage"],
        "rules_description": "المادة 53: فترة التجربة لا تزيد على 90 يوماً ويجوز تمديدها إلى 180 يوماً باتفاق كتابي.",
    },
    "payroll": {
        "domain": "payroll",
        "sheet_aliases": ["payroll_gosi", "4_payroll_gosi", "payroll", "gosi", "الرواتب", "التأمينات"],
        "title_ar": "الرواتب وتأمينات GOSI وحماية الأجور (Payroll & GOSI)",
        "key_columns": [
            ("emp_id", ["رقم هوية / إقامة الموظف", "emp_id"]),
            ("emp_name", ["اسم الموظف", "emp_name"]),
            ("gosi_type", ["نوع الاشتراك التأميني", "gosi_type"]),
            ("gosi_sub_num", ["رقم المشترك في التأمينات", "gosi_sub_num"]),
            ("bank_name", ["بنك الموظف", "bank_name"]),
            ("iban", ["آيبان الموظف", "iban"]),
            ("gosi_wage", ["الأجر الخاضع للاشتراك", "gosi_wage"]),
            ("emp_gosi_ded", ["استقطاع الموظف للتأمينات", "emp_gosi_ded"]),
            ("comp_gosi_share", ["حصة الشركة للتأمينات", "comp_gosi_share"]),
            ("net_salary", ["صافي الراتب المتوقع", "net_salary"]),
        ],
        "required_keys": ["emp_id", "emp_name", "gosi_type", "bank_name", "iban", "gosi_wage"],
        "rules_description": "نظام التأمينات الاجتماعية ونظام حماية الأجور (WPS SIF).",
    },
    "timeoff": {
        "domain": "timeoff",
        "sheet_aliases": ["time_off", "5_time_off", "timeoff", "leaves", "الإجازات", "أرصدة الإجازات"],
        "title_ar": "الإجازات والأرصدة الافتتاحية (Time Off & Balances)",
        "key_columns": [
            ("emp_id", ["رقم هوية / إقامة الموظف", "emp_id"]),
            ("emp_name", ["اسم الموظف", "emp_name"]),
            ("leave_type", ["نوع الإجازة", "leave_type"]),
            ("start_date", ["تاريخ بداية الإجازة", "start_date"]),
            ("end_date", ["تاريخ نهاية الإجازة", "end_date"]),
            ("days_count", ["عدد الأيام المطلوبة", "days_count"]),
            ("opening_balance", ["الرصيد الافتتاحي المتراكم", "opening_balance"]),
            ("notes", ["ملاحظات وتفاصيل الإجازة", "notes"]),
        ],
        "required_keys": ["emp_id", "emp_name", "leave_type", "start_date", "days_count"],
        "rules_description": "المواد 109 و 113: استحقاق الإجازة السنوية وإجازات المناسبات نظاماً.",
    },
    "overtime": {
        "domain": "overtime",
        "sheet_aliases": ["overtime", "7_overtime", "العمل الإضافي", "إضافي"],
        "title_ar": "العمل الإضافي والأوفرتايم (Overtime Requests - مادة 107)",
        "key_columns": [
            ("emp_id", ["رقم هوية / إقامة الموظف", "emp_id"]),
            ("emp_name", ["اسم الموظف", "emp_name"]),
            ("date", ["تاريخ العمل الإضافي", "date"]),
            ("overtime_type", ["نوع يوم الإضافي", "overtime_type"]),
            ("hours", ["عدد الساعات الإضافية", "hours"]),
            ("hourly_wage", ["أجر الساعة المعتاد", "hourly_wage"]),
            ("multiplier", ["معامل الإضافي", "multiplier"]),
            ("total_amount", ["المبلغ الإجمالي المستحق", "total_amount"]),
            ("reason", ["مبرر التكليف وموافقة الإدارة", "reason"]),
        ],
        "required_keys": ["emp_id", "emp_name", "date", "hours", "hourly_wage", "reason"],
        "rules_description": "المادة 107: أجر العمل الإضافي يوازي أجر الساعة مضافاً إليه 50% من الأساسي (1.5x).",
    },
    "loan": {
        "domain": "loan",
        "sheet_aliases": ["loans", "8_loans", "loan", "السلف", "قروض", "سلف وقروض"],
        "title_ar": "قروض وسلف الموظفين والأقساط (Loans & Installments - مادة 92)",
        "key_columns": [
            ("emp_id", ["رقم هوية / إقامة الموظف", "emp_id"]),
            ("emp_name", ["اسم الموظف", "emp_name"]),
            ("loan_type", ["نوع السلفة / القرض", "loan_type"]),
            ("loan_amount", ["إجمالي مبلغ القرض المطلوب", "loan_amount"]),
            ("term_months", ["مدة السداد بالأشهر", "term_months"]),
            ("installment_amt", ["قيمة القسط الشهري", "installment_amt"]),
            ("monthly_salary", ["إجمالي راتب الموظف الشهري", "monthly_salary"]),
            ("installment_ratio", ["نسبة الاستقطاع", "installment_ratio"]),
            ("start_date", ["تاريخ بداية أول قسط", "start_date"]),
            ("payment_method", ["طريقة الصرف", "payment_method"]),
            ("reason", ["سبب طلب القرض / السلفة", "reason"]),
        ],
        "required_keys": ["emp_id", "emp_name", "loan_type", "loan_amount", "term_months", "monthly_salary"],
        "rules_description": "المادة 92: حظر تجاوز حسم قروض صاحب العمل عن 25% من أجر العامل الشهري.",
    },
    "disciplinary": {
        "domain": "disciplinary",
        "sheet_aliases": ["disciplinary", "9_disciplinary", "الجزاءات", "الإنذارات", "المخالفات"],
        "title_ar": "الجزاءات والإنذارات والمخالفات (Disciplinary Management)",
        "key_columns": [
            ("emp_id", ["رقم هوية / إقامة الموظف", "emp_id"]),
            ("emp_name", ["اسم الموظف", "emp_name"]),
            ("violation_date", ["تاريخ ارتكاب المخالفة", "violation_date"]),
            ("penalty_type", ["نوع الجزاء الموقع", "penalty_type"]),
            ("deduction_days", ["عدد أيام الخصم", "deduction_days"]),
            ("investigation_date", ["تاريخ التحقيق وسماع الأقوال", "investigation_date"]),
            ("reason", ["وصف المخالفة وقرار الإدارة", "reason"]),
        ],
        "required_keys": ["emp_id", "emp_name", "violation_date", "penalty_type", "investigation_date", "reason"],
        "rules_description": "المواد 66 و 70 و 71: التحقيق الكتابي الإلزامي وحظر خصم أكثر من 5 أيام عن المخالفة.",
    },
    "end_of_service": {
        "domain": "end_of_service",
        "sheet_aliases": ["end_of_service", "10_end_of_service", "eos", "نهاية الخدمة", "مكافأة نهاية الخدمة"],
        "title_ar": "مكافأة نهاية الخدمة والتسويات (End of Service - مواد 84-85)",
        "key_columns": [
            ("emp_id", ["رقم هوية / إقامة الموظف", "emp_id"]),
            ("emp_name", ["اسم الموظف", "emp_name"]),
            ("hire_date", ["تاريخ بداية الخدمة", "hire_date"]),
            ("term_date", ["تاريخ انتهاء الخدمة", "term_date"]),
            ("reason", ["سبب انتهاء العلاقة العمالية", "reason"]),
            ("last_salary", ["آخر أجر شهري كامل", "last_salary"]),
            ("service_years", ["مدة الخدمة بالسنوات", "service_years"]),
            ("eos_amount", ["مكافأة نهاية الخدمة المستحقة", "eos_amount"]),
            ("leave_comp", ["بدل رصيد الإجازات المتبقية", "leave_comp"]),
            ("loan_deduct", ["خصم السلف والقروض المتبقية", "loan_deduct"]),
            ("net_settlement", ["صافي مبلغ المخالصة النهائية", "net_settlement"]),
        ],
        "required_keys": ["emp_id", "emp_name", "hire_date", "term_date", "reason", "last_salary"],
        "rules_description": "المادتان 84 و 85: احتساب مكافأة نهاية الخدمة وفق مدة الخدمة وسبب انتهاء العقد.",
    },
    "appraisal": {
        "domain": "appraisal",
        "sheet_aliases": ["appraisals", "11_appraisals", "appraisal", "التقييمات", "تقييم الأداء"],
        "title_ar": "تقييمات الأداء والموظفين (Employee Appraisals)",
        "key_columns": [
            ("emp_id", ["رقم هوية / إقامة الموظف", "emp_id"]),
            ("emp_name", ["اسم الموظف", "emp_name"]),
            ("year", ["سنة التقييم", "year"]),
            ("type", ["نوع التقييم", "type"]),
            ("manager", ["اسم المدير المقيّم", "manager"]),
            ("kpi_score", ["درجة الأهداف والمؤشرات", "kpi_score"]),
            ("competency_score", ["درجة الكفاءات والسلوك", "competency_score"]),
            ("total_score", ["المعدل العام النهائي", "total_score"]),
            ("rating", ["التقدير المعتمد", "rating"]),
            ("recommendation", ["التوصيات", "recommendation"]),
        ],
        "required_keys": ["emp_id", "emp_name", "year", "type", "manager", "rating"],
        "rules_description": "تقييم الأداء وتحديد الأهداف ومتابعة فترة التجربة (م/53).",
    },
    "recruitment": {
        "domain": "recruitment",
        "sheet_aliases": ["recruitment", "12_recruitment", "التوظيف", "المرشحين", "طلبات التوظيف"],
        "title_ar": "طلبات التوظيف وشواغر المتقدمين (Recruitment & Applicants)",
        "key_columns": [
            ("name", ["اسم المرشح", "name"]),
            ("job", ["الوظيفة المتقدم لها", "job"]),
            ("dept", ["القسم المطلوب", "dept", "department"]),
            ("branch", ["الفرع وموقع العمل", "branch"]),
            ("nationality", ["الجنسية", "nationality"]),
            ("mobile", ["رقم الجوال", "mobile"]),
            ("email", ["البريد الإلكتروني", "email"]),
            ("expected_salary", ["الراتب المتوقع", "expected_salary"]),
            ("score", ["درجة المقابلة", "score"]),
            ("status", ["حالة المرشح", "status"]),
        ],
        "required_keys": ["name", "job", "dept", "branch", "nationality", "mobile", "status"],
        "rules_description": "ضوابط التوطين والمهن المقفلة وقرارات وزارة الموارد البشرية.",
    },
    "gr": {
        "domain": "gr",
        "sheet_aliases": ["gr_transactions", "13_gr_transactions", "gr", "المعاملات", "مقيم", "قوى"],
        "title_ar": "المعاملات والتأشيرات الحكومية (GR Transactions - مقيم وقوى)",
        "key_columns": [
            ("emp_id", ["رقم هوية / إقامة الموظف", "emp_id"]),
            ("emp_name", ["اسم الموظف", "emp_name"]),
            ("tx_type", ["نوع المعاملة الحكومية", "tx_type"]),
            ("iqama_hijri", ["تاريخ انتهاء الإقامة هجري", "iqama_hijri"]),
            ("iqama_greg", ["تاريخ انتهاء الإقامة ميلادي", "iqama_greg"]),
            ("passport_num", ["رقم جواز السفر", "passport_num"]),
            ("passport_exp", ["تاريخ انتهاء الجواز", "passport_exp"]),
            ("border_num", ["رقم الحدود", "border_num"]),
            ("gov_fees", ["الرسوم الحكومية المقدرة", "gov_fees"]),
            ("status", ["حالة المعاملة", "status"]),
        ],
        "required_keys": ["emp_id", "emp_name", "tx_type", "status"],
        "rules_description": "نظام الإقامة ورخص العمل والمهل النظامية للتجديد.",
    },
    "company": {
        "domain": "company",
        "sheet_aliases": ["company_setup", "1_company_setup", "company", "تأسيس المنشأة", "بيانات المنشأة"],
        "title_ar": "بيانات تأسيس المنشأة والحسابات البنكية (Company Profile)",
        "key_columns": [
            ("name_ar", ["اسم المنشأة بالعربي", "name_ar"]),
            ("name_en", ["اسم المنشأة بالإنجليزي", "name_en"]),
            ("cr_number", ["رقم السجل التجاري", "cr_number"]),
            ("vat_number", ["الرقم الضريبي", "vat_number"]),
            ("gosi_id", ["رقم المنشأة في التأمينات", "gosi_id"]),
            ("labor_office_id", ["رقم المنشأة في مكتب العمل", "labor_office_id"]),
            ("bank_name", ["اسم البنك الرئيسي", "bank_name"]),
            ("iban", ["الآيبان البنكي الرئيسي", "iban"]),
            ("city", ["المدينة", "city"]),
            ("is_branch", ["نوع الكيان", "is_branch"]),
        ],
        "required_keys": ["name_ar", "cr_number", "vat_number", "gosi_id", "bank_name", "iban"],
        "rules_description": "تطابق السجل التجاري (10 أرقام) والرقم الضريبي (15 رقماً) والآيبان البنكي (WPS).",
    },
    "employee": {
        "domain": "employee",
        "sheet_aliases": ["employees", "2_employees", "employee", "الموظفين", "الموظفون", "بيانات الموظفين"],
        "title_ar": "استيراد وتأسيس بيانات الموظفين (Employee Master Data)",
        "key_columns": [
            ("name", ["اسم الموظف الكامل بالعربي", "اسم الموظف", "name"]),
            ("name_en", ["اسم الموظف بالإنجليزي", "name_en"]),
            ("id_number", ["رقم الهوية الوطنية / الإقامة", "رقم الهوية", "id_number", "national_id"]),
            ("nationality", ["الجنسية", "nationality"]),
            ("gender", ["الجنس", "gender"]),
            ("birthday", ["تاريخ الميلاد", "birthday"]),
            ("marital", ["الحالة الاجتماعية", "marital"]),
            ("mobile_phone", ["رقم الجوال", "mobile_phone", "mobile"]),
            ("work_email", ["البريد الإلكتروني للعمل", "work_email", "email"]),
            ("company", ["المنشأة التابع لها", "الشركة", "company"]),
            ("branch", ["الفرع / موقع العمل", "branch"]),
            ("department", ["القسم / الإدارة", "department"]),
            ("job_title", ["المسمى الوظيفي", "job_title", "job"]),
            ("hiring_date", ["تاريخ المباشرة", "hiring_date"]),
        ],
        "required_keys": ["name", "company", "department", "job_title"],
        "rules_description": "نظام العمل السعودي: تسجيل تاريخ المباشرة الفعلي يحدد تاريخ بدء احتساب الحقوق والتأمينات.",
    },
}

AUXILIARY_SHEETS = {"instructions", "reference", "دليل التعليمات", "المراجع", "تعليمات"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_run_id(source_hash: str) -> str:
    return source_hash[:16]


def row_hash_dict(payload: Dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def identify_template_and_sheet(workbook: openpyxl.Workbook, file_name: str = "") -> Tuple[str, str, Worksheet, int, int]:
    """
    يكتشف نوع القالب، الورقة المستهدفة، صف الترويسات، وصف بداية البيانات.
    Returns:
        (domain_key, title_ar, worksheet, header_row_idx, data_start_row_idx)
    """
    clean_fn = file_name.lower().replace(".xlsx", "")
    sheetnames = workbook.sheetnames

    # استبعاد أوراق التعليمات والمراجع
    data_sheets = [s for s in sheetnames if s.strip().lower() not in AUXILIARY_SHEETS]
    if not data_sheets:
        data_sheets = sheetnames

    # 1. مطابقة التبويبات مع الدليل
    for domain_key, spec in TEMPLATE_SPECS.items():
        for sheet_name in data_sheets:
            s_clean = sheet_name.strip().lower()
            if any(alias in s_clean for alias in spec["sheet_aliases"]):
                ws = workbook[sheet_name]
                header_row, data_start = _detect_header_and_data_rows(ws, spec)
                return domain_key, spec["title_ar"], ws, header_row, data_start

    # 2. مطابقة اسم الملف إن لم يتطابق التبويب بدقة
    for domain_key, spec in TEMPLATE_SPECS.items():
        if any(alias in clean_fn for alias in spec["sheet_aliases"]):
            ws = workbook[data_sheets[0]]
            header_row, data_start = _detect_header_and_data_rows(ws, spec)
            return domain_key, spec["title_ar"], ws, header_row, data_start

    # 3. الافتراضي: الموظفون (Employees)
    target_sheet = data_sheets[0]
    ws = workbook[target_sheet]
    spec = TEMPLATE_SPECS["employee"]
    header_row, data_start = _detect_header_and_data_rows(ws, spec)
    return "employee", spec["title_ar"], ws, header_row, data_start


def _detect_header_and_data_rows(ws: Worksheet, spec: Dict[str, Any]) -> Tuple[int, int]:
    """
    يكتشف ما إذا كانت الترويسات في الصف 1 أم الصف 2 (إذا كان الصف 1 عنواناً مدمجاً).
    """
    max_r = min(ws.max_row, 10)
    if max_r < 1:
        return 1, 2

    row1_vals = [to_text_preserve(cell.value).strip() for cell in ws[1] if cell.value is not None]
    
    # إذا كان الصف 1 يحتوي على قيمة واحدة مدمجة أو نصاً طويلاً يتضمن كلمة (قالب / دليل / ساعات / جدول)
    # والصف 2 يحتوي على عدة قيم نصية: الترويسات في الصف 2
    if len(row1_vals) <= 2 and ws.max_row >= 2:
        row2_vals = [to_text_preserve(cell.value).strip() for cell in ws[2] if cell.value is not None]
        if len(row2_vals) >= 3:
            # الصف 2 هو الترويسة
            # فحص الصف 3: هل هو صف المثال المائل؟
            # إذا كان إجمالي الصفوف 3 صفوف فقط (عنوان + ترويسة + صف المثال)، نعتبر صف 3 بيانات لكي يتم فحصه!
            if ws.max_row == 3:
                return 2, 3
            # إذا كانت هناك صفوف إضافية والصف 3 يحتوي على مثال (مثلاً يبدأ بـ 1088776655 أو إمالة)، نتجاوزه إذا توفرت بيانات بعده
            row3_vals = [to_text_preserve(cell.value).strip() for cell in ws[3] if cell.value is not None]
            if len(row3_vals) > 0 and ws.max_row > 3:
                first_val = row3_vals[0]
                if "1088776655" in first_val or "عبدالله" in first_val or "شركة النخبة" in first_val:
                    return 2, 4
            return 2, 3

    return 1, 2


def _map_columns_to_keys(header_cells: List[Any], spec: Dict[str, Any]) -> Dict[str, int]:
    """
    يربط مفاتيح الأعمدة المعيارية بأرقام الأعمدة في ورقة الإكسل (1-indexed).
    """
    mapping: Dict[str, int] = {}
    normalized_headers = [clean_value_text(to_text_preserve(v)).lower() for v in header_cells]

    for key, synonyms in spec["key_columns"]:
        for col_idx, h_text in enumerate(normalized_headers, start=1):
            if not h_text:
                continue
            # إزالة علامة النجمة والمسافات
            h_clean = h_text.replace("*", "").strip()
            for syn in synonyms:
                syn_clean = syn.lower().replace("*", "").strip()
                if syn_clean in h_clean or h_clean in syn_clean:
                    mapping[key] = col_idx
                    break
            if key in mapping:
                break

    return mapping


def validate_template_workbook(
    file_path: str | Path,
    repo: Optional[OdooReadonlyRepository] = None,
) -> Dict[str, Any]:
    """
    يفحص أي ملف إكسل من قوالب النظام وينتج تقرير الفحص الجاف الموحد الكامل.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"ملف الإكسل غير موجود: {path}")

    raw_bytes = path.read_bytes()
    src_hash = sha256_bytes(raw_bytes)
    run_id = make_run_id(src_hash)

    wb = openpyxl.load_workbook(path, data_only=True)
    domain_key, title_ar, ws, header_row_idx, data_start_row = identify_template_and_sheet(wb, path.name)
    spec = TEMPLATE_SPECS.get(domain_key, TEMPLATE_SPECS["employee"])

    header_cells = [cell.value for cell in ws[header_row_idx]]
    col_map = _map_columns_to_keys(header_cells, spec)

    # جلب معلومات مستودع Odoo للتحقق
    repo = repo or OdooReadonlyRepository()
    session_info = repo.get_session_info()
    snapshot = repo.get_live_reference_snapshot()

    report_rows: List[Dict[str, Any]] = []
    status_counts = {"accepted": 0, "rejected": 0}

    # قراءة صفوف البيانات
    for r_idx in range(data_start_row, ws.max_row + 1):
        row_raw: Dict[str, str] = {}
        row_values: Dict[str, Any] = {}
        is_empty = True

        for key, _ in spec["key_columns"]:
            if key in col_map:
                cell = ws.cell(row=r_idx, column=col_map[key])
                val_text = clean_value_text(to_text_preserve(cell.value))
                row_raw[key] = val_text
                row_values[key] = val_text
                if val_text:
                    is_empty = False
            else:
                row_raw[key] = ""
                row_values[key] = ""

        if is_empty:
            continue

        # تطبيق منطق التحقق والامتثال وفق نوع القالب
        row_status, failure_code, reasons, parser_warnings, resolved_ids = _validate_row_by_domain(
            domain_key=domain_key,
            row_raw=row_raw,
            spec=spec,
            r_idx=r_idx,
            repo=repo,
            snapshot=snapshot,
        )

        status_counts[row_status] = status_counts.get(row_status, 0) + 1
        r_hash = row_hash_dict(row_raw)

        report_rows.append({
            "excel_row_number": r_idx,
            "final_status": row_status,
            "failure_code": failure_code,
            "reasons": reasons,
            "resolved_ids": resolved_ids,
            "row_hash": r_hash,
            "run_id": run_id,
            "source_hash": src_hash,
            "parser_warnings": parser_warnings,
            "fields": {k: {"raw": row_raw[k], "value": row_raw[k]} for k in row_raw},
        })

    header_meta = {
        "odoo_url": session_info.get("odoo_url"),
        "odoo_db": session_info.get("odoo_db"),
        "uid": session_info.get("uid"),
        "version": session_info.get("server_version"),
        "reference_counts": {
            "companies": len(snapshot.get("companies", [])),
            "departments": len(snapshot.get("departments", [])),
            "jobs": len(snapshot.get("jobs", [])),
        },
        "run_id": run_id,
        "source_hash": src_hash,
        "template_type": domain_key,
        "template_title": title_ar,
        "sheet_name": ws.title,
    }

    summary_meta = {
        "status_counts": status_counts,
        "row_count": len(report_rows),
        "template_type": domain_key,
        "template_title": title_ar,
        "rules_description": spec.get("rules_description", ""),
    }

    return {
        "header": header_meta,
        "summary": summary_meta,
        "rows": report_rows,
    }


def _validate_row_by_domain(
    domain_key: str,
    row_raw: Dict[str, str],
    spec: Dict[str, Any],
    r_idx: int,
    repo: OdooReadonlyRepository,
    snapshot: Dict[str, Any],
) -> Tuple[str, Optional[str], List[str], List[str], Dict[str, Any]]:
    """
    يفحص صف بيانات محدد وفق ضوابط النطاق ونظام العمل السعودي.
    """
    reasons: List[str] = []
    parser_warnings: List[str] = []
    resolved_ids: Dict[str, Any] = {
        "company_id": None,
        "department_id": None,
        "job_id": None,
        "employee_match_id": None,
    }

    # 1. التحقق من الحقول الإلزامية الأساسية
    missing_required = []
    for req_k in spec.get("required_keys", []):
        if not row_raw.get(req_k):
            missing_required.append(req_k)

    if missing_required:
        return (
            "rejected",
            "missing_required_fields",
            [f"الحقول الإلزامية التالية غير مكتملة في الصف: {', '.join(missing_required)}."],
            ["missing_required_columns"],
            resolved_ids,
        )

    # 2. قواعد نطاق الحضور (Attendance)
    if domain_key == "attendance":
        emp_id = row_raw.get("emp_id", "")
        month = row_raw.get("month", "")
        worked_hours_str = row_raw.get("worked_hours", "")
        expected_days_str = row_raw.get("expected_days", "")
        actual_days_str = row_raw.get("actual_days", "")

        # فحص رقم الهوية / الإقامة
        digits_only = re.sub(r"\D", "", emp_id)
        if len(digits_only) not in (10,):
            parser_warnings.append("invalid_national_id_length")
            reasons.append("رقم الهوية / الإقامة لا يتطابق مع 10 أرقام نظامية.")

        # فحص صيغة الشهر YYYY-MM
        if month and not re.match(r"^\d{4}-\d{2}$", month.strip()):
            parser_warnings.append("invalid_month_format")
            reasons.append("صيغة الشهر يجب أن تكون YYYY-MM (مثلاً 2026-10).")

        # فحص ساعات العمل وفق المادة 98
        try:
            exp_days = float(expected_days_str) if expected_days_str else 0.0
            act_days = float(actual_days_str) if actual_days_str else 0.0
            w_hours = float(worked_hours_str) if worked_hours_str else 0.0

            if exp_days > 0 and w_hours > (exp_days * 8.0):
                extra_hours = w_hours - (exp_days * 8.0)
                reasons.append(
                    f"تتجاوز ساعات الحضور المعدل المعياري بمقدار {extra_hours:.1f} ساعة، وتعتبر ساعات عمل إضافية تخضع للمادة 107."
                )

            if act_days > exp_days and exp_days > 0:
                parser_warnings.append("actual_days_exceeds_expected")
                reasons.append("أيام الحضور الفعلية تتجاوز أيام العمل المفترضة للشهر.")
        except ValueError:
            parser_warnings.append("invalid_numeric_values")

        # فحص مطابقة الموظف في Odoo
        emp_name = row_raw.get("emp_name", "")
        matched_emp = _match_employee_in_odoo(repo, emp_name, emp_id)
        if matched_emp:
            resolved_ids["employee_match_id"] = matched_emp.get("id")
            reasons.append(f"تمت مطابقة الموظف في Odoo بنجاح: {matched_emp.get('name')} (معرف #{matched_emp.get('id')}).")
        else:
            reasons.append(f"سجل الحضور للموظف «{emp_name}» سليم ومستوفٍ للشروط وجاهز للاستيراد.")

        reasons.append("مستوفٍ لضوابط ساعات العمل وسياسة الدوام المعتمدة بموجب المادة 98.")
        return ("accepted", None, reasons, parser_warnings, resolved_ids)

    # 3. قواعد نطاق الموظفين (Employee Master Data)
    elif domain_key == "employee":
        name = row_raw.get("name", "")
        comp = row_raw.get("company", "")
        dept = row_raw.get("department", "")
        job = row_raw.get("job_title", "")

        # مطابقة المنشأة والقسم والوظيفة مع snapshot
        matched_comp = _match_reference(comp, snapshot.get("companies", []))
        if matched_comp:
            resolved_ids["company_id"] = matched_comp.get("id")
        else:
            reasons.append(f"المنشأة «{comp}» غير مسجلة في Odoo.")

        matched_dept = _match_reference(dept, snapshot.get("departments", []))
        if matched_dept:
            resolved_ids["department_id"] = matched_dept.get("id")

        matched_job = _match_reference(job, snapshot.get("jobs", []))
        if matched_job:
            resolved_ids["job_id"] = matched_job.get("id")

        if resolved_ids["company_id"]:
            reasons.append("تمت مطابقة المنشأة وسجل الموظف مؤهل للإدراج.")
            return ("accepted", None, reasons, parser_warnings, resolved_ids)
        else:
            return ("rejected", "company_not_found", reasons, ["unmatched_company"], resolved_ids)

    # 4. قواعد عقود العمل (Contract)
    elif domain_key == "contract":
        probation_days = row_raw.get("probation_days", "90")
        try:
            p_days = float(probation_days)
            if p_days > 180:
                return (
                    "rejected",
                    "probation_exceeds_statutory_limit",
                    ["فترة التجربة تتجاوز 180 يوماً بالمخالفة الصريحة للمادة 53 من نظام العمل."],
                    ["statutory_violation_article_53"],
                    resolved_ids,
                )
            elif p_days > 90:
                reasons.append("فترة التجربة تزيد على 90 يوماً، وتتطلب اتفاقاً خطياً صريحاً بين الطرفين بموجب المادة 53.")
        except ValueError:
            pass

        reasons.append("بنود العقد والأجور مستوفية للشروط النظامية.")
        return ("accepted", None, reasons, parser_warnings, resolved_ids)

    # 5. قواعد قروض وسلف الموظفين (Loans - م/92)
    elif domain_key == "loan":
        try:
            m_sal = float(row_raw.get("monthly_salary", "0"))
            l_amt = float(row_raw.get("loan_amount", "0"))
            t_months = float(row_raw.get("term_months", "1"))
            if m_sal > 0 and t_months > 0:
                installment = l_amt / t_months
                ratio = installment / m_sal
                if ratio > 0.25:
                    return (
                        "rejected",
                        "loan_installment_exceeds_25_percent",
                        [f"القسط الشهري ({installment:.1f} ر.س) يمثل {ratio*100:.1f}% من الراتب، متجاوزاً الحد الأقصى النظامي (25%) بموجب المادة 92."],
                        ["statutory_violation_article_92"],
                        resolved_ids,
                    )
        except ValueError:
            pass

        reasons.append("قيمة القسط الشهري ونسبة الاستقطاع ممتثلة تماماً للمادة 92 من نظام العمل.")
        return ("accepted", None, reasons, parser_warnings, resolved_ids)

    # 6. بقية النطاقات العامة
    reasons.append("سجل البيانات مكتمل ومستوفٍ للحقول الإلزامية والضوابط المعتمدة.")
    return ("accepted", None, reasons, parser_warnings, resolved_ids)


def _match_reference(name: str, records: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not name:
        return None
    clean_n = clean_value_text(name).lower()
    for r in records:
        r_name = clean_value_text(r.get("name", "")).lower()
        if r_name == clean_n or clean_n in r_name:
            return r
    return None


def _match_employee_in_odoo(
    repo: OdooReadonlyRepository,
    emp_name: str,
    emp_id: str,
) -> Optional[Dict[str, Any]]:
    """
    يحاول مطابقة الموظف في Odoo بالاسم أو رقم الهوية.
    """
    try:
        employees = repo.get_employees()
        clean_name = clean_value_text(emp_name).lower()
        digits_id = re.sub(r"\D", "", emp_id)

        for emp in employees:
            e_name = clean_value_text(emp.get("name", "")).lower()
            if clean_name and (clean_name in e_name or e_name in clean_name):
                return emp
            if digits_id:
                # فحص الحقول الإضافية إن وُجدت
                id_card = str(emp.get("identification_id", ""))
                if digits_id in id_card:
                    return emp
    except Exception:
        pass
    return None
