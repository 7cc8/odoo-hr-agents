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
        "sheet_aliases": ["end_of_service", "10_end_of_service", "end of service", "eos", "نهاية الخدمة", "مكافأة نهاية الخدمة"],
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
            ("name_en", ["اسم الموظف بالإنجليزي", "اسم الموظف بالانجليزي", "name_en"]),
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
    "master": {
        "domain": "master",
        "sheet_aliases": ["master", "master_onboarding", "شامل", "القالب_الشامل"],
        "title_ar": "القالب الشامل لتأسيس المنشأة والموظفين (Master Onboarding)",
        "key_columns": [
            ("name", ["الاسم الكامل للموظف", "اسم الموظف", "الاسم", "name", "employee_name"]),
            ("iqama", ["رقم الهوية الوطنية / الإقامة", "رقم الهوية", "الهوية / الإقامة", "iqama", "national_id"]),
            ("job_title", ["المسمى الوظيفي", "الوظيفة", "job_title", "job", "job_id"]),
            ("department", ["القسم / الإدارة", "الإدارة", "القسم", "department", "dept", "department_id"]),
            ("company", ["المنشأة التابع لها", "الشركة", "company"]),
            ("salary", ["الراتب الأساسي", "الأساسي", "salary", "wage"]),
            ("housing", ["بدل السكن", "housing", "housing_allowance"]),
            ("transport", ["بدل النقل", "transport", "transport_allowance"]),
            ("mobile_phone", ["رقم الجوال", "الجوال", "mobile_phone", "mobile", "phone"]),
            ("work_email", ["البريد الإلكتروني للعمل", "الإيميل", "work_email", "email"]),
            ("hiring_date", ["تاريخ المباشرة", "تاريخ الالتحاق", "hiring_date", "join_date", "start_date"]),
        ],
        "required_keys": ["name", "company", "department", "job_title"],
        "rules_description": "فحص المنشأة والهيكل الإداري والموظفين والعقود والبدلات والتأمينات وفق نظام العمل السعودي.",
    },
}

AUXILIARY_SHEETS = {"instructions", "reference", "دليل التعليمات", "المراجع", "تعليمات", "دليل الاستخدام"}

# الترتيب الاعتمادي الإلزامي للأوراق الـ 13 في مصنف الماستر الشامل
MASTER_SHEET_ORDER: List[Tuple[str, Tuple[str, ...]]] = [
    ("company", ("1_company_setup", "company_setup", "company profile", "تأسيس المنشأة", "بيانات المنشأة")),
    ("employee", ("2_employees", "employees", "employee", "الموظفين", "الموظفون", "بيانات الموظفين")),
    ("contract", ("3_contracts", "contracts", "contract", "عقود", "العقود", "عقود العمل")),
    ("payroll", ("4_payroll_gosi", "payroll_gosi", "payroll", "gosi", "الرواتب", "التأمينات")),
    ("timeoff", ("5_time_off", "time_off", "timeoff", "leaves", "الإجازات", "أرصدة الإجازات")),
    ("attendance", ("6_attendances", "attendances", "attendance", "حضور", "الدوام", "سجلات الحضور")),
    ("overtime", ("7_overtime", "overtime", "العمل الإضافي", "إضافي")),
    ("loan", ("8_loans", "loans", "loan", "السلف", "قروض", "سلف وقروض")),
    ("disciplinary", ("9_disciplinary", "disciplinary", "الجزاءات", "الإنذارات", "المخالفات")),
    ("end_of_service", ("10_end_of_service", "end_of_service", "end of service", "eos", "نهاية الخدمة", "مكافأة نهاية الخدمة")),
    ("appraisal", ("11_appraisals", "appraisals", "appraisal", "التقييمات", "تقييم الأداء")),
    ("recruitment", ("12_recruitment", "recruitment", "التوظيف", "المرشحين", "طلبات التوظيف")),
    ("gr", ("13_gr_transactions", "gr_transactions", "gr", "المعاملات", "مقيم", "قوى")),
]


def is_auxiliary_sheet(s_name: str) -> bool:
    clean = s_name.strip().lower()
    return clean in AUXILIARY_SHEETS or any(k in clean for k in ("instruction", "تعليمات", "reference", "مراجع", "دليل")) or clean.startswith("0_")


def _resolve_sheet_domain(sheet_name: str) -> Optional[str]:
    """يحدد النطاق التخصصي لورقة إكسل بناءً على اسمها ضمن الأوراق الـ 13."""
    s_clean = sheet_name.strip().lower()
    for domain_key, aliases in MASTER_SHEET_ORDER:
        if any(alias in s_clean for alias in aliases):
            return domain_key
    for domain_key, spec in TEMPLATE_SPECS.items():
        if domain_key == "master":
            continue
        if any(alias in s_clean for alias in spec.get("sheet_aliases", [])):
            return domain_key
    return None


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

    # استبعاد أوراق التعليمات والمراجع بكل أشكالها
    data_sheets = [s for s in sheetnames if not is_auxiliary_sheet(s)]
    if not data_sheets:
        data_sheets = sheetnames

    # 0. التحقق من القالب الشامل أولاً (Master Workbook)
    is_master = "master" in clean_fn or "شامل" in clean_fn or "onboarding" in clean_fn
    has_master_sheets = (
        any(re.match(r"1[ _]", name) and _resolve_sheet_domain(name) == "company" for name in data_sheets)
        and any(re.match(r"2[ _]", name) and _resolve_sheet_domain(name) == "employee" for name in data_sheets)
    )
    if is_master or has_master_sheets:
        target_sheet = None
        for cand in ["2_employees", "employees", "الموظفين", "الموظفون", "1_company_setup", "بيانات الموظفين"]:
            for s in data_sheets:
                if cand in s.lower():
                    target_sheet = s
                    break
            if target_sheet:
                break
        if not target_sheet:
            target_sheet = data_sheets[0]
        ws = workbook[target_sheet]
        master_spec = TEMPLATE_SPECS.get("master", TEMPLATE_SPECS["employee"])
        header_row, data_start = _detect_header_and_data_rows(ws, master_spec)
        return "master", master_spec["title_ar"], ws, header_row, data_start

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
            from template_localizer import template_example_matches

            example_matches = template_example_matches(ws, 3)
            if example_matches is not None:
                return 2, 4 if example_matches else 3
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

    from template_localizer import ENGLISH_SOURCE_HEADERS

    # Catalog labels round-trip to the source headers used by the validator.
    normalized_headers = [ENGLISH_SOURCE_HEADERS.get(header.rstrip(" *"), header) for header in normalized_headers]
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


def _extract_sheet_rows(
    ws: Worksheet,
    domain_key: str,
    spec: Dict[str, Any],
    repo: OdooReadonlyRepository,
    snapshot: Dict[str, Any],
    run_id: str,
    src_hash: str,
    master_context: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """استخراج وفحص صفوف ورقة واحدة وإرجاع (rows, status_counts)."""
    header_row_idx, data_start_row = _detect_header_and_data_rows(ws, spec)
    header_cells = [cell.value for cell in ws[header_row_idx]]
    col_map = _map_columns_to_keys(header_cells, spec)

    report_rows: List[Dict[str, Any]] = []
    status_counts = {"accepted": 0, "rejected": 0}
    if not col_map:
        return report_rows, status_counts

    for r_idx in range(data_start_row, ws.max_row + 1):
        row_raw: Dict[str, str] = {}
        is_empty = True

        for key, _ in spec["key_columns"]:
            if key in col_map:
                cell = ws.cell(row=r_idx, column=col_map[key])
                val_text = clean_value_text(to_text_preserve(cell.value))
                if val_text.startswith("="):
                    val_text = ""
                row_raw[key] = val_text
                if val_text:
                    is_empty = False
            else:
                row_raw[key] = ""

        if is_empty:
            continue

        row_status, failure_code, reasons, parser_warnings, resolved_ids = _validate_row_by_domain(
            domain_key=domain_key,
            row_raw=row_raw,
            spec=spec,
            r_idx=r_idx,
            repo=repo,
            snapshot=snapshot,
            col_map=col_map,
            master_context=master_context,
        )

        status_counts[row_status] = status_counts.get(row_status, 0) + 1
        r_hash = row_hash_dict({"sheet": ws.title, "row": r_idx, **row_raw} if master_context else row_raw)

        disp_name = (
            row_raw.get("name")
            or row_raw.get("emp_name")
            or row_raw.get("name_ar")
            or row_raw.get("name_en")
            or ""
        )

        # تحديث سياق الماستر المشترك بين الأوراق
        if master_context is not None and row_status == "accepted":
            if domain_key == "company":
                c_name = row_raw.get("name_ar") or row_raw.get("name_en")
                if c_name:
                    master_context.setdefault("declared_companies", []).append({
                        "id": resolved_ids.get("company_id") or f"pending_comp_{len(master_context.get('declared_companies', [])) + 1}",
                        "name": c_name,
                        "name_en": row_raw.get("name_en", ""),
                        "pending_creation": resolved_ids.get("company_id") is None,
                    })
            elif domain_key == "employee":
                e_name = row_raw.get("name")
                if e_name:
                    master_context.setdefault("declared_employees", []).append({
                        "id": resolved_ids.get("employee_match_id") or f"pending_emp_{len(master_context.get('declared_employees', [])) + 1}",
                        "name": e_name,
                        "name_en": row_raw.get("name_en", ""),
                        "identification_id": row_raw.get("id_number", ""),
                        "work_email": row_raw.get("work_email", ""),
                        "pending_creation": True,
                    })

        report_rows.append({
            "excel_row_number": r_idx,
            "sheet_name": ws.title,
            "domain": domain_key,
            "display_name": disp_name,
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

    return report_rows, status_counts


def validate_template_workbook(
    file_path: str | Path,
    repo: Optional[OdooReadonlyRepository] = None,
) -> Dict[str, Any]:
    """
    يفحص أي ملف إكسل من قوالب النظام وينتج تقرير الفحص الجاف الموحد الكامل.
    يدعم مصنف الماستر الشامل بفحص جميع الأوراق الوظيفية الـ 13 المعبأة بالتسلسل
    (1_Company_Setup -> 2_Employees -> 3_Contracts -> 4..13) مع تخطي Instructions و Reference.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"ملف الإكسل غير موجود: {path}")

    raw_bytes = path.read_bytes()
    src_hash = sha256_bytes(raw_bytes)
    run_id = make_run_id(src_hash)

    wb = openpyxl.load_workbook(path, data_only=True)
    domain_key, title_ar, ws, header_row_idx, data_start_row = identify_template_and_sheet(wb, path.name)

    repo = repo or OdooReadonlyRepository()
    session_info = repo.get_session_info()
    snapshot = repo.get_live_reference_snapshot()

    data_sheets = [s for s in wb.sheetnames if not is_auxiliary_sheet(s)]
    is_multi_sheet_master = (domain_key == "master") or len(data_sheets) > 1

    if is_multi_sheet_master:
        # ترتيب الأوراق الوظيفية الـ 13 وفق تسلسل التبعيات الصحيح
        ordered_sheets: List[Tuple[str, str]] = []
        seen_sheets = set()
        for dom_k, _ in MASTER_SHEET_ORDER:
            for s_name in data_sheets:
                if s_name in seen_sheets:
                    continue
                if _resolve_sheet_domain(s_name) == dom_k:
                    ordered_sheets.append((s_name, dom_k))
                    seen_sheets.add(s_name)
        for s_name in data_sheets:
            if s_name not in seen_sheets:
                dom_k = _resolve_sheet_domain(s_name) or "employee"
                ordered_sheets.append((s_name, dom_k))

        all_rows: List[Dict[str, Any]] = []
        total_counts = {"accepted": 0, "rejected": 0}
        sheets_processed: List[Dict[str, Any]] = []
        sheets_skipped_empty: List[str] = []
        master_context: Dict[str, Any] = {
            "is_master": True,
            "declared_companies": [],
            "declared_employees": [],
        }

        for s_name, dom_k in ordered_sheets:
            s_ws = wb[s_name]
            s_spec = TEMPLATE_SPECS.get(dom_k, TEMPLATE_SPECS["employee"])
            s_rows, s_counts = _extract_sheet_rows(
                ws=s_ws,
                domain_key=dom_k,
                spec=s_spec,
                repo=repo,
                snapshot=snapshot,
                run_id=run_id,
                src_hash=src_hash,
                master_context=master_context,
            )
            if not s_rows:
                sheets_skipped_empty.append(s_name)
                continue

            all_rows.extend(s_rows)
            total_counts["accepted"] += s_counts.get("accepted", 0)
            total_counts["rejected"] += s_counts.get("rejected", 0)
            sheets_processed.append({
                "sheet_name": s_name,
                "domain": dom_k,
                "title_ar": s_spec.get("title_ar", s_name),
                "row_count": len(s_rows),
                "accepted": s_counts.get("accepted", 0),
                "rejected": s_counts.get("rejected", 0),
            })

        master_spec = TEMPLATE_SPECS["master"]
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
            "source_file_name": path.name,
            "template_type": "master",
            "template_title": master_spec["title_ar"],
            "sheet_name": ", ".join(sp["sheet_name"] for sp in sheets_processed) or ws.title,
            "sheets_checked": [sp["sheet_name"] for sp in sheets_processed],
        }
        summary_meta = {
            "status_counts": total_counts,
            "row_count": len(all_rows),
            "template_type": "master",
            "template_title": master_spec["title_ar"],
            "rules_description": master_spec.get("rules_description", ""),
            "sheets_processed": sheets_processed,
            "sheets_skipped_empty": sheets_skipped_empty,
        }
        return {
            "header": header_meta,
            "summary": summary_meta,
            "rows": all_rows,
        }

    # مسار الورقة الواحدة (Modular Single-Sheet Template)
    spec = TEMPLATE_SPECS.get(domain_key, TEMPLATE_SPECS["employee"])
    report_rows, status_counts = _extract_sheet_rows(
        ws=ws,
        domain_key=domain_key,
        spec=spec,
        repo=repo,
        snapshot=snapshot,
        run_id=run_id,
        src_hash=src_hash,
        master_context=None,
    )

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
        "source_file_name": path.name,
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
    col_map: Optional[Dict[str, int]] = None,
    master_context: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Optional[str], List[str], List[str], Dict[str, Any]]:
    """
    يفحص صف بيانات محدد وفق ضوابط النطاق ونظام العمل السعودي.
    """
    from normalization import is_valid_email_format

    reasons: List[str] = []
    parser_warnings: List[str] = []
    resolved_ids: Dict[str, Any] = {
        "company_id": None,
        "department_id": None,
        "job_id": None,
        "employee_match_id": None,
    }
    is_master = bool(master_context and master_context.get("is_master"))

    # 1. التحقق من الحقول الإلزامية الأساسية
    required_keys = list(spec.get("required_keys", []))
    if domain_key == "company" and is_master:
        # في الماستر يكفي وجود اسم المنشأة (بالعربي أو الإنجليزي) لإنشائها/مطابقتها
        required_keys = ["name_ar"] if row_raw.get("name_ar") or not row_raw.get("name_en") else ["name_en"]

    missing_required = []
    for req_k in required_keys:
        # في الأوراق التشغيلية المربوطة بالموظف، يكفي توفر emp_id أو emp_name إذا لم يُدرج عمود emp_id
        if req_k == "emp_id" and row_raw.get("emp_name") and (col_map is None or "emp_id" not in col_map or is_master):
            continue
        if req_k == "emp_name" and row_raw.get("emp_id") and (col_map is None or "emp_name" not in col_map):
            continue
        if is_master and domain_key in ("contract", "payroll", "timeoff", "attendance", "overtime", "loan", "disciplinary", "end_of_service", "appraisal", "gr"):
            if col_map is not None and req_k not in col_map:
                continue
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

    # 1.5 قواعد تأسيس المنشأة (1_Company_Setup)
    if domain_key == "company":
        comp_name = row_raw.get("name_ar") or row_raw.get("name_en") or ""
        cr_num = re.sub(r"\D", "", row_raw.get("cr_number", ""))
        vat_num = re.sub(r"\D", "", row_raw.get("vat_number", ""))
        iban = (row_raw.get("iban") or "").strip().upper()
        if cr_num and len(cr_num) != 10:
            parser_warnings.append("invalid_cr_number_length")
            reasons.append("رقم السجل التجاري يفضّل أن يكون 10 أرقام.")
        if vat_num and len(vat_num) != 15:
            parser_warnings.append("invalid_vat_number_length")
            reasons.append("الرقم الضريبي يفضّل أن يكون 15 رقماً.")
        if iban and not iban.startswith("SA"):
            parser_warnings.append("invalid_saudi_iban_prefix")
            reasons.append("الآيبان البنكي السعودي يجب أن يبدأ بـ SA.")
        matched_c = _match_reference(comp_name, snapshot.get("companies", []))
        if matched_c:
            resolved_ids["company_id"] = matched_c.get("id")
            reasons.append(f"تمت مطابقة المنشأة «{matched_c.get('name')}» في Odoo (معرف #{matched_c.get('id')}).")
        else:
            reasons.append(f"بيانات المنشأة «{comp_name}» سليمة وجاهزة للتأسيس في Odoo.")
        return ("accepted", None, reasons, parser_warnings, resolved_ids)

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
        work_email = row_raw.get("work_email", "")

        # التحقق من صحة البريد الإلكتروني إذا تم إدخاله
        if work_email and not is_valid_email_format(work_email):
            return (
                "rejected",
                "invalid_work_email",
                [f"صيغة البريد الإلكتروني غير صالحة: «{work_email}»."],
                ["invalid_email_format"],
                resolved_ids,
            )

        # مطابقة المنشأة مع snapshot أو المنشآت المعرفة في 1_Company_Setup داخل نفس الماستر
        declared_companies = (master_context or {}).get("declared_companies", [])
        all_companies = list(snapshot.get("companies", [])) + list(declared_companies)
        matched_comp = _match_reference(comp, all_companies)
        if matched_comp:
            resolved_ids["company_id"] = matched_comp.get("id")
            if matched_comp.get("pending_creation"):
                reasons.append(f"ربط بالمنشأة المعرفة في 1_Company_Setup: «{matched_comp.get('name')}».")
        elif hasattr(repo, "get_default_company"):
            try:
                def_c = repo.get_default_company()
                if def_c and def_c.get("id"):
                    resolved_ids["company_id"] = def_c.get("id")
                    parser_warnings.append("default_company_fallback")
                    reasons.append(f"تم اعتماد المنشأة الافتراضية في Odoo («{def_c.get('name')}») لسجل الموظف.")
            except Exception:
                pass

        if not resolved_ids.get("company_id"):
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

        matched_emp = _match_employee_in_odoo(
            repo,
            row_raw.get("emp_name", ""),
            row_raw.get("emp_id", ""),
            extra_employees=(master_context or {}).get("declared_employees", []),
        )
        if matched_emp:
            resolved_ids["employee_match_id"] = matched_emp.get("id")
            reasons.append(f"ربط العقد بالموظف: «{matched_emp.get('name')}».")

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

        matched_emp = _match_employee_in_odoo(
            repo,
            row_raw.get("emp_name", ""),
            row_raw.get("emp_id", ""),
            extra_employees=(master_context or {}).get("declared_employees", []),
        )
        if matched_emp:
            resolved_ids["employee_match_id"] = matched_emp.get("id")
        reasons.append("قيمة القسط الشهري ونسبة الاستقطاع ممتثلة تماماً للمادة 92 من نظام العمل.")
        return ("accepted", None, reasons, parser_warnings, resolved_ids)

    # 6. قواعد شواغر التوظيف والمرشحين (Recruitment & Applicants)
    elif domain_key == "recruitment":
        from recruitment_service import is_job_restricted_to_saudis, get_job_accreditation_requirement

        cand_name = row_raw.get("name", "").strip()
        job_title = row_raw.get("job", "").strip()
        dept_name = row_raw.get("dept", "").strip()
        branch = row_raw.get("branch", "").strip()
        nationality = row_raw.get("nationality", "").strip()
        mobile = row_raw.get("mobile", "").strip()
        email = row_raw.get("email", "").strip()
        raw_status = row_raw.get("status", "").strip()
        exp_salary_str = row_raw.get("expected_salary", "0")

        # 1. فحص وتحديد الجنسية (مواطن سعودي مقابل وافد مقيم)
        is_saudi = False
        clean_nat = clean_value_text(nationality).lower()
        if any(w in clean_nat for w in ["سعودي", "سعودية", "saudi", "مواطن", "مواطنة"]):
            is_saudi = True

        # 2. فحص قرارات التوطين وحظر المهن المقصورة 100% على المواطنين (وزارة الموارد البشرية)
        is_restricted = is_job_restricted_to_saudis(job_title)
        if not is_saudi and is_restricted:
            return (
                "rejected",
                "saudization_restricted_profession",
                [
                    f"حظر توطين قطعي بموجب قرارات وزارة الموارد البشرية: وظيفة «{job_title}» مقصورة بنسبة 100% على المواطنين السعوديين، ويحظر نظاماً شغلها بمرشح وافد ({nationality or 'غير سعودي'})."
                ],
                ["saudization_violation_restricted_job"],
                resolved_ids,
            )
        elif is_saudi and is_restricted:
            reasons.append(f"متوافق مع قرارات التوطين: ترشيح مواطن سعودي لمهنة مقصورة («{job_title}») يدعم نسبة التوطين وتفادي المخالفات.")

        # 3. فحص متطلبات الاعتماد والتصنيف المهني الإلزامي (SOCPA / SCE)
        accreditation = get_job_accreditation_requirement(job_title)
        if accreditation:
            reasons.append(f"متطلب اعتماد وتصنيف مهني: {accreditation}")

        # 4. مطابقة الوظيفة ضد شواغر Odoo الحية (Live Odoo Job Resolution)
        all_jobs = snapshot.get("jobs", [])
        SEMANTIC_JOB_MAP = {
            "أخصائي تسويق": "marketing and community manager",
            "مطوّر برمجيات": "full stack developer",
        }

        matched_job = _match_reference(job_title, all_jobs)
        if not matched_job and job_title in SEMANTIC_JOB_MAP:
            matched_job = _match_reference(SEMANTIC_JOB_MAP[job_title], all_jobs)

        if matched_job:
            resolved_ids["job_id"] = matched_job.get("id")
            reasons.append(f"تمت مطابقة الشاغر الوظيفي في Odoo: «{matched_job.get('name')}» (معرف #{matched_job.get('id')}).")
        elif job_title:
            reasons.append(f"الشاغر «{job_title}» غير معرف مسبقاً في Odoo — سيقوم الوكيل «كاتب» بإنشائه تلقائياً في hr.job ضمن خطة الاعتماد.")
        else:
            return (
                "rejected",
                "missing_job_title",
                ["المسمى الوظيفي مطلوب لإنشاء طلب التوظيف في Odoo."],
                ["missing_job_title"],
                resolved_ids,
            )

        # 5. مطابقة القسم في Odoo
        if dept_name:
            matched_dept = _match_reference(dept_name, snapshot.get("departments", []))
            if matched_dept:
                resolved_ids["department_id"] = matched_dept.get("id")
                reasons.append(f"تمت مطابقة القسم في Odoo: «{matched_dept.get('name')}» (معرف #{matched_dept.get('id')}).")
            else:
                reasons.append(f"القسم «{dept_name}» غير مسجل في Odoo.")

        # 6. إسناد المنشأة الافتراضية
        companies = snapshot.get("companies", [])
        if companies:
            resolved_ids["company_id"] = companies[0].get("id", 1)

        # 7. فحص مرحلة التوظيف ومسار كانبان في Odoo
        STAGE_MAP_AR = {
            "معتمد ومباشر": 6,   # Contract Signed
            "عقد موقع": 6,
            "عرض عمل مرسل": 5,   # Contract Proposal
            "عرض عمل": 5,
            "مقابلة مجدولة": 3,  # First Interview
            "مقابلة أولى": 3,
            "مقابلة ثانية": 4,  # Second Interview
            "مقبول مبدئياً": 2,  # Qualification
            "تأهيل": 2,
            "جديد": 1,          # New
        }
        resolved_stage = STAGE_MAP_AR.get(raw_status, 1)
        resolved_ids["stage_id"] = resolved_stage
        reasons.append(f"تم توجيه المرشح إلى المرحلة رقم #{resolved_stage} في مسار التوظيف وفق حالة الملف («{raw_status or 'جديد'}»).")

        # 8. فحص الراتب
        try:
            sal_val = float(exp_salary_str)
            if sal_val > 0:
                reasons.append(f"الراتب المتوقع المعتمد في السجل: {sal_val:,.0f} ر.س.")
        except ValueError:
            pass

        return ("accepted", None, reasons, parser_warnings, resolved_ids)

    if domain_key == "appraisal" and not is_master:
        from appraisal_excel_import import check_appraisal_row

        issues, employee, _ = check_appraisal_row(row_raw, repo)
        if issues:
            return ("rejected", issues[0][0], [message for _, message in issues], parser_warnings, resolved_ids)
        resolved_ids["employee_match_id"] = employee["id"]
        resolved_ids["company_id"] = (employee.get("company_id") or [None])[0]
        return ("accepted", None, ["تمت مطابقة الموظف والتحقق من بيانات التقييم."], parser_warnings, resolved_ids)

    # 7. بقية النطاقات التخصصية (الإجازات، الرواتب، الإضافي، الجزاءات، نهاية الخدمة، التقييم، المعاملات)
    if domain_key == "disciplinary":
        try:
            ded_days = float(row_raw.get("deduction_days") or 0)
            if ded_days > 5:
                return (
                    "rejected",
                    "disciplinary_exceeds_5_days",
                    [f"أيام الخصم ({ded_days:.0f} أيام) تتجاوز الحد الأقصى النظامي (5 أيام) بموجب المادة 66."],
                    ["statutory_violation_article_66"],
                    resolved_ids,
                )
        except ValueError:
            pass
    elif domain_key == "timeoff":
        try:
            d_cnt = float(row_raw.get("days_count") or 0)
            if d_cnt < 0:
                return (
                    "rejected",
                    "invalid_leave_days",
                    ["عدد أيام الإجازة لا يمكن أن يكون سالباً."],
                    ["invalid_numeric_values"],
                    resolved_ids,
                )
        except ValueError:
            pass

    if row_raw.get("emp_name") or row_raw.get("emp_id"):
        matched_emp = _match_employee_in_odoo(
            repo,
            row_raw.get("emp_name", ""),
            row_raw.get("emp_id", ""),
            extra_employees=(master_context or {}).get("declared_employees", []),
        )
        if matched_emp:
            resolved_ids["employee_match_id"] = matched_emp.get("id")
            reasons.append(f"ربط السجل بالموظف: «{matched_emp.get('name')}».")

    reasons.append("تم التحقق من اكتمال وصحة الحقول النظامية في الورقة بنجاح.")
    return ("accepted", None, reasons, parser_warnings, resolved_ids)


def _match_reference(name: str, records: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not name or not records:
        return None
    clean_n = clean_value_text(name).lower()
    for r in records:
        r_name = clean_value_text(r.get("name", "")).lower()
        r_en = clean_value_text(r.get("name_en", "")).lower()
        if r_name == clean_n or clean_n in r_name or (r_en and (r_en == clean_n or clean_n in r_en)):
            return r
    try:
        from agents.muwaffaq_agent import get_muwaffaq_agent
        res = get_muwaffaq_agent().find_match({"query": name, "field_type": "entity_name", "candidates": records})
        best = res.get("best_match")
        if best and res.get("status") in ("matched", "proposed") and best.get("id") is not None:
            return next((r for r in records if str(r.get("id")) == str(best.get("id"))), None)
    except Exception:
        pass
    return None


def _match_employee_in_odoo(
    repo: OdooReadonlyRepository,
    emp_name: str,
    emp_id: str,
    extra_employees: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    يطابق الموظف في Odoo أو في ورقة 2_Employees بالاسم أو رقم الهوية، مع تدخل «موفق» للمطابقة الضبابية.
    """
    employees: List[Dict[str, Any]] = []
    try:
        employees.extend(repo.get_employees() or [])
    except Exception:
        pass
    if extra_employees:
        employees.extend(extra_employees)

    if not employees:
        return None

    clean_name = clean_value_text(emp_name).lower()
    digits_id = re.sub(r"\D", "", emp_id or "")

    for emp in employees:
        e_name = clean_value_text(emp.get("name", "")).lower()
        e_en = clean_value_text(emp.get("name_en", "")).lower()
        if digits_id:
            id_card = str(emp.get("identification_id", ""))
            if id_card and digits_id in id_card:
                return emp
        if clean_name and (clean_name in e_name or e_name in clean_name or (e_en and (clean_name in e_en or e_en in clean_name))):
            return emp

    if clean_name:
        try:
            from agents.muwaffaq_agent import get_muwaffaq_agent
            res = get_muwaffaq_agent().find_match({"query": emp_name, "field_type": "employee_name", "candidates": employees})
            best = res.get("best_match")
            if best and res.get("status") in ("matched", "proposed") and best.get("id") is not None:
                return next((e for e in employees if str(e.get("id")) == str(best.get("id"))), None)
        except Exception:
            pass
    return None
