"""
Template Localizer - توطين وترجمة قوالب الإكسل المعتمدة
======================================================
يدعم توليد وتحويل كافة قوالب الإكسل الـ 13 وقالب الماستر إلى:
1. اللغة الإنجليزية فقط (en)
2. ثنائي اللغة عربي / إنجليزي (bilingual)
3. اللغة العربية فقط (ar)
مع التحكم في تضمين أو إزالة الصف الاسترشادي (include_example_row).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import openpyxl
from openpyxl.packaging.custom import StringProperty

logger = logging.getLogger("template_localizer")

TAB_LABELS = {
    "Instructions": ("التعليمات", "Instructions"),
    "Reference": ("المراجع", "Reference"),
    "Company_Setup": ("تأسيس المنشأة", "Company Setup"),
    "Employees": ("الموظفون", "Employees"),
    "Contracts": ("العقود", "Contracts"),
    "Payroll_GOSI": ("الرواتب", "Payroll"),
    "Time_Off": ("الإجازات", "Leaves"),
    "Attendances": ("الحضور", "Attendance"),
    "Overtime": ("العمل الإضافي", "Overtime"),
    "Loans": ("السلف والقروض", "Loans"),
    "Disciplinary": ("الجزاءات", "Disciplinary"),
    "End_of_Service": ("نهاية الخدمة", "End of Service"),
    "Appraisals": ("تقييم الأداء", "Appraisals"),
    "Recruitment": ("التوظيف", "Recruitment"),
    "GR_Transactions": ("المعاملات الحكومية", "GR"),
}

ADDITIONAL_HEADERS_EN = {
    "آخر أجر شهري كامل (أساسي+بدلات)": "Last Full Monthly Wage (Base + Allowances)",
    "آيبان الموظف (WPS)": "Employee IBAN (Wage Protection)",
    "أجر الساعة المعتاد (الأساسي / 240)": "Regular Hourly Wage (Base / 240)",
    "إجمالي الراتب الشهري (تلقائي)": "Total Monthly Salary (Calculated)",
    "إجمالي مبلغ القرض المطلوب (ر.س)": "Total Loan Amount Requested (SAR)",
    "استقطاع الموظف للتأمينات (تلقائي)": "Employee Social Insurance Deduction (Calculated)",
    "اسم البنك الرئيسي": "Primary Bank Name",
    "اسم المدير المقيّم": "Reviewing Manager Name",
    "الآيبان البنكي الرئيسي (يبدأ بـ SA)": "Primary Bank IBAN (Starts with SA)",
    "الأجر الخاضع للاشتراك (أساسي + سكن)": "Contributory Wage (Base + Housing)",
    "البريد الإلكتروني الرسمي": "Official Email",
    "التقدير المعتمد": "Approved Rating",
    "التوصيات (ترقية / علاوة / تطوير)": "Recommendations (Promotion / Raise / Development)",
    "الحي": "District",
    "الراتب الأساسي (ر.س)": "Basic Salary (SAR)",
    "الراتب المتوقع (ر.س)": "Expected Salary (SAR)",
    "الرسوم الحكومية المقدرة (ر.س)": "Estimated Government Fees (SAR)",
    "الرصيد الافتتاحي المتراكم السابق": "Accrued Opening Balance",
    "الرقم الضريبي (15 رقماً)": "Tax Number (15 Digits)",
    "الرمز البريدي (5 أرقام)": "Postal Code (5 Digits)",
    "الشركة الأم (في حال كان فرعاً)": "Parent Company (For a Branch)",
    "العنوان الوطني / الشارع": "National Address / Street",
    "الفرع وموقع العمل": "Branch and Work Location",
    "القسم المطلوب": "Requested Department",
    "المبلغ الإجمالي المستحق (تلقائي)": "Total Amount Due (Calculated)",
    "المدينة": "City",
    "المعدل العام النهائي (من 100)": "Final Overall Score (Out of 100)",
    "بدل السكن الشهري (ر.س)": "Monthly Housing Allowance (SAR)",
    "بدل النقل الشهري (ر.س)": "Monthly Transport Allowance (SAR)",
    "بدل رصيد الإجازات المتبقية (ر.س)": "Unused Leave Payout (SAR)",
    "بدلات أخرى ثابتة (ر.س)": "Other Fixed Allowances (SAR)",
    "بنك الموظف (لتحويل الراتب)": "Employee Bank (Salary Transfer)",
    "تاريخ ارتكاب المخالفة": "Violation Date",
    "تاريخ التحقيق وسماع الأقوال": "Investigation and Hearing Date",
    "تاريخ انتهاء الإقامة ميلادي": "Iqama Expiry Date (Gregorian)",
    "تاريخ انتهاء الإقامة هجري": "Iqama Expiry Date (Hijri)",
    "تاريخ انتهاء الجواز": "Passport Expiry Date",
    "تاريخ انتهاء الخدمة (آخر دوام)": "End Date (Last Working Day)",
    "تاريخ بداية الخدمة": "Service Start Date",
    "تاريخ نهاية العقد (للمحدد)": "Contract End Date (Fixed Term)",
    "حالة المرشح": "Applicant Status",
    "حصة الشركة للتأمينات (تلقائي)": "Employer Social Insurance Contribution (Calculated)",
    "خصم السلف والقروض المتبقية (ر.س)": "Outstanding Advance and Loan Deductions (SAR)",
    "درجة الأهداف والمؤشرات (من 100)": "Goals and Indicators Score (Out of 100)",
    "درجة الكفاءات والسلوك (من 100)": "Competency and Behavior Score (Out of 100)",
    "درجة المقابلة (من 100)": "Interview Score (Out of 100)",
    "رقم الحدود (للقادمين الجدد)": "Border Number (New Arrivals)",
    "رقم السجل التجاري (10 أرقام)": "Commercial Registration Number (10 Digits)",
    "رقم المنشأة في التأمينات (GOSI)": "Social Insurance Establishment Number",
    "رقم المنشأة في مكتب العمل / قوى": "Labor Office / Qiwa Establishment Number",
    "رقم جواز السفر": "Passport Number",
    "سبب انتهاء العلاقة العمالية": "Termination Reason",
    "سنة التقييم (YYYY)": "Appraisal Year (YYYY)",
    "صافي الراتب المتوقع للتحويل": "Expected Net Salary Transfer",
    "صافي مبلغ المخالصة النهائية": "Net Final Settlement Amount",
    "عدد أيام الخصم (حد أقصى 5 أيام)": "Deduction Days (Up to 5 Days)",
    "فترة التجربة بالأيام (حد أقصى 180)": "Probation in Days (Up to 180)",
    "قيمة القسط الشهري (تلقائي)": "Monthly Installment Amount (Calculated)",
    "مدة الخدمة بالسنوات (تلقائي)": "Years of Service (Calculated)",
    "مدة السداد بالأشهر (الأقساط)": "Repayment Period in Months (Installments)",
    "معامل الإضافي (1.5x تلقائي)": "Overtime Multiplier (Calculated at 1.5×)",
    "مكافأة نهاية الخدمة المستحقة (تلقائي)": "End-of-Service Gratuity Due (Calculated)",
    "موقع العمل / الفرع": "Work Location / Branch",
    "نسبة الاستقطاع (حد أقصى 25%)": "Deduction Rate (Up to 25%)",
    "نوع التقييم": "Appraisal Type",
    "نوع الجزاء الموقع": "Penalty Type",
    "نوع الكيان (مقر رئيسي / فرع)": "Entity Type (Head Office / Branch)",
    "وصف المخالفة وقرار الإدارة": "Violation Description and Management Decision",
}

EXAMPLE_TEXT_EN = {
    "أخصائي تسويق": "Marketing Specialist",
    "إجازة سنوية مجدولة": "Scheduled Annual Leave",
    "إنجاز الإقفال المالي الشهري": "Complete the Monthly Financial Close",
    "العليا": "Al Olaya",
    "المالية والمحاسبة": "Finance and Accounting",
    "ترقية لمستوى وظيفي أعلى مع علاوة استحقاق": "Promotion to a Higher Grade with a Merit Raise",
    "تكرار التأخر الصباحي بدون عذر بعد إنذار أولي": "Repeated Unexcused Morning Tardiness after an Initial Warning",
    "سارة بنت خالد المطيري": "Sarah bint Khalid Al-Mutairi",
    "طارق بن أحمد المنصور": "Tariq bin Ahmed Al-Mansour",
    "طريق الملك فهد": "King Fahd Road",
    "ظرف عائلي طارئ": "Family Emergency",
    "عبدالله بن محمد الغامدي": "Abdullah bin Mohammed Al-Ghamdi",
    "فهد السبيعي": "Fahad Al-Subaie",
    "مسؤول محاسبة": "Accounting Officer",
}

REFERENCE_HEADINGS = dict(zip(
    "companies branches departments jobs banks cities nationalities genders marital_statuses branch_types contract_types gosi_types leave_types loan_types payment_methods penalty_types overtime_types term_reasons appraisal_types ratings applicant_statuses gr_types tx_statuses".split(),
    "المنشآت|الفروع|الأقسام|الوظائف|البنوك|المدن|الجنسيات|الجنس|الحالة الاجتماعية|أنواع الفروع|أنواع العقود|فئات التأمينات|أنواع الإجازات|أنواع السلف|طرق السداد|أنواع الجزاءات|أنواع الإضافي|أسباب انتهاء الخدمة|أنواع التقييم|التقديرات|حالات المرشحين|أنواع المعاملات|حالات المعاملات".split("|"),
    strict=True,
))

# قاموس الترويسات: (English, Bilingual)
HEADER_DICTIONARY: Dict[str, Tuple[str, str]] = {
    # 2_Employees / Modular Employees
    "اسم الموظف الكامل بالعربي": ("Employee Full Name (Arabic)", "اسم الموظف / Employee Name"),
    "اسم الموظف بالإنجليزي": ("Employee Name (English)", "الاسم بالإنجليزي / English Name"),
    "اسم الموظف بالانجليزي": ("Employee Name (English)", "الاسم بالإنجليزي / English Name"),
    "رقم الهوية الوطنية / الإقامة (10 أرقام)": ("National ID / Iqama Number (10 Digits)", "رقم الهوية/الإقامة / National ID"),
    "رقم الهوية الوطنية / الإقامة": ("National ID / Iqama", "الهوية/الإقامة / National ID"),
    "رقم الهوية / الإقامة": ("National ID / Iqama", "الهوية/الإقامة / National ID"),
    "رقم هوية / إقامة الموظف": ("Employee National ID / Iqama", "رقم الهوية/الإقامة / Employee ID"),
    "الجنسية": ("Nationality", "الجنسية / Nationality"),
    "الجنس (ذكر / أنثى)": ("Gender (Male / Female)", "الجنس / Gender"),
    "تاريخ الميلاد": ("Date of Birth (YYYY-MM-DD)", "تاريخ الميلاد / Date of Birth"),
    "الحالة الاجتماعية": ("Marital Status", "الحالة الاجتماعية / Marital Status"),
    "رقم الجوال (05xxxxxxxx)": ("Mobile Phone (05xxxxxxxx)", "رقم الجوال / Mobile Phone"),
    "رقم الجوال": ("Mobile Phone", "رقم الجوال / Mobile Phone"),
    "البريد الإلكتروني للعمل": ("Work Email", "البريد الإلكتروني / Work Email"),
    "المنشأة التابع لها": ("Company / Entity", "المنشأة / Company"),
    "الفرع / موقع العمل": ("Branch / Work Location", "الفرع / Branch"),
    "القسم / الإدارة": ("Department", "القسم / Department"),
    "المسمى الوظيفي": ("Job Title / Position", "المسمى الوظيفي / Job Title"),
    "تاريخ المباشرة": ("Hire / Joining Date", "تاريخ المباشرة / Joining Date"),

    # 6_Attendances / Modular Attendance
    "اسم الموظف": ("Employee Name", "اسم الموظف / Employee Name"),
    "شهر وسنة الكشف (YYYY-MM)": ("Sheet Month & Year (YYYY-MM)", "شهر وسنة الكشف / Month (YYYY-MM)"),
    "شهر وسنة الكشف (yyyy-mm)": ("Sheet Month & Year (YYYY-MM)", "شهر وسنة الكشف / Month (YYYY-MM)"),
    "أيام العمل المفترضة": ("Expected Working Days", "أيام العمل المفترضة / Expected Days"),
    "أيام الحضور الفعلية": ("Actual Present Days", "أيام الحضور / Actual Days"),
    "إجمالي ساعات الحضور الفعلية": ("Total Worked Hours", "ساعات الحضور / Worked Hours"),
    "دقائق التأخير الإجمالية": ("Total Delay Minutes", "دقائق التأخير / Late Minutes"),
    "أيام الغياب غير المبرر": ("Unexcused Absence Days", "أيام الغياب / Absence Days"),

    # 3_Contracts / Modular Contracts
    "اسم الموظف الثلاثي": ("Employee Full Name", "اسم الموظف / Employee Name"),
    "نوع العقد": ("Contract Type", "نوع العقد / Contract Type"),
    "تاريخ بداية العقد": ("Contract Start Date", "تاريخ بداية العقد / Start Date"),
    "تاريخ نهاية العقد": ("Contract End Date", "تاريخ نهاية العقد / End Date"),
    "فترة التجربة بالأيام": ("Probation Period (Days)", "فترة التجربة / Probation (Days)"),
    "الراتب الأساسي": ("Basic Wage", "الراتب الأساسي / Basic Wage"),
    "بدل السكن الشهري": ("Monthly Housing Allowance", "بدل السكن / Housing Allowance"),
    "بدل النقل الشهري": ("Monthly Transport Allowance", "بدل النقل / Transport Allowance"),
    "بدلات أخرى ثابتة": ("Other Fixed Allowances", "بدلات أخرى / Other Allowances"),
    "إجمالي الراتب الشهري": ("Total Gross Monthly Salary", "إجمالي الراتب / Total Salary"),

    # 4_Payroll_GOSI / Modular Payroll
    "نوع الاشتراك التأميني": ("GOSI Subscription Type", "نوع الاشتراك / GOSI Type"),
    "رقم المشترك في التأمينات": ("GOSI Subscriber Number", "رقم التأمينات / GOSI Number"),
    "بنك الموظف": ("Employee Bank Name", "البنك / Bank Name"),
    "آيبان الموظف": ("IBAN Number", "الآيبان / IBAN"),
    "الأجر الخاضع للاشتراك": ("GOSI Contributory Wage", "الأجر الخاضع للتأمينات / GOSI Wage"),
    "استقطاع الموظف للتأمينات": ("Employee GOSI Deduction", "استقطاع التأمينات / Employee GOSI"),
    "حصة الشركة للتأمينات": ("Company GOSI Share", "حصة الشركة / Company GOSI"),
    "صافي الراتب المتوقع": ("Net Salary", "صافي الراتب / Net Salary"),

    # 5_Time_Off / Modular Timeoff
    "نوع الإجازة": ("Leave / Time Off Type", "نوع الإجازة / Leave Type"),
    "تاريخ بداية الإجازة": ("Leave Start Date", "بداية الإجازة / Start Date"),
    "تاريخ نهاية الإجازة": ("Leave End Date", "نهاية الإجازة / End Date"),
    "عدد الأيام المطلوبة": ("Days Count", "عدد الأيام / Days Count"),
    "الرصيد الافتتاحي المتراكم": ("Opening Balance", "الرصيد الافتتاحي / Opening Balance"),
    "ملاحظات وتفاصيل الإجازة": ("Leave Notes", "ملاحظات / Notes"),

    # 7_Overtime / Modular Overtime
    "تاريخ العمل الإضافي": ("Overtime Date", "تاريخ الإضافي / Overtime Date"),
    "نوع يوم الإضافي": ("Day Type (Regular/Weekend/Holiday)", "نوع اليوم / Day Type"),
    "عدد الساعات الإضافية": ("Overtime Hours", "الساعات الإضافية / Overtime Hours"),
    "أجر الساعة المعتاد": ("Normal Hourly Rate", "أجر الساعة / Hourly Rate"),
    "معامل الإضافي": ("Multiplier Rate", "معامل الإضافي / Multiplier"),
    "المبلغ الإجمالي المستحق": ("Total Overtime Amount", "المبلغ الإجمالي / Total Amount"),
    "مبرر التكليف وموافقة الإدارة": ("Assignment Justification", "مبرر التكليف / Reason"),

    # 8_Loans / Modular Loans
    "نوع السلفة / القرض": ("Loan / Advance Type", "نوع السلفة / Loan Type"),
    "إجمالي مبلغ القرض المطلوب": ("Requested Loan Amount", "مبلغ القرض / Loan Amount"),
    "مدة السداد بالأشهر": ("Term in Months", "مدة السداد / Term (Months)"),
    "قيمة القسط الشهري": ("Monthly Installment", "القسط الشهري / Monthly Installment"),
    "إجمالي راتب الموظف الشهري": ("Total Monthly Salary", "راتب الموظف / Monthly Salary"),
    "نسبة الاستقطاع": ("Deduction Ratio (%)", "نسبة الاستقطاع / Deduction Ratio"),
    "تاريخ بداية أول قسط": ("First Installment Date", "تاريخ أول قسط / First Installment Date"),
    "طريقة الصرف": ("Disbursement Method", "طريقة الصرف / Disbursement Method"),
    "سبب طلب القرض / السلفة": ("Loan Purpose / Reason", "سبب الطلب / Reason"),

    # 9_Disciplinary / Modular Disciplinary
    "تاريخ الواقعة / المخالفة": ("Infraction Date", "تاريخ المخالفة / Infraction Date"),
    "نوع المخالفة": ("Infraction Type", "نوع المخالفة / Infraction Type"),
    "نوع العقوبة / الجزاء": ("Penalty Type", "نوع الجزاء / Penalty Type"),
    "رقم قرار التحقيق / الجزاء": ("Decision Number", "رقم القرار / Decision Number"),
    "تاريخ القرار": ("Decision Date", "تاريخ القرار / Decision Date"),
    "أيام الحسم": ("Deduction Days", "أيام الحسم / Deduction Days"),
    "ملاحظات": ("Notes", "ملاحظات / Notes"),

    # 10_End_of_Service / Modular EOS
    "تاريخ التعيين": ("Joining Date", "تاريخ التعيين / Joining Date"),
    "تاريخ انتهاء الخدمة": ("End of Service Date", "تاريخ نهاية الخدمة / EOS Date"),
    "سبب انتهاء العلاقة": ("Termination Reason", "سبب انتهاء الخدمة / Reason"),
    "آخر أجر شامل": ("Last Gross Wage", "آخر أجر شامل / Last Gross Wage"),
    "مدة الخدمة بالسنوات": ("Service Duration (Years)", "مدة الخدمة / Service (Years)"),
    "مكافأة نهاية الخدمة": ("EOS Gratuity Reward", "مكافأة نهاية الخدمة / Gratuity Reward"),
    "بدل رصيد الإجازات": ("Leave Encashment", "بدل الإجازات / Leave Encashment"),
    "صافي المستحقات النهائية": ("Net Final Settlement", "صافي المستحقات / Net Dues"),

    # 11_Appraisals / Modular Appraisals
    "فترة التقييم": ("Evaluation Period", "فترة التقييم / Period"),
    "اسم المقيم": ("Evaluator Name", "اسم المقيم / Evaluator"),
    "درجة الأهداف (KPIs)": ("KPIs Score", "درجة الأهداف / KPIs Score"),
    "درجة الكفاءات والسلوكيات": ("Behavior Score", "درجة السلوكيات / Behavior Score"),
    "التقدير النهائي": ("Final Rating", "التقدير النهائي / Final Rating"),
    "توصية الترقية أو التطوير": ("Recommendation", "التوصية / Recommendation"),

    # 12_Recruitment / Modular Recruitment
    "اسم المرشح": ("Candidate Name", "اسم المرشح / Candidate Name"),
    "الوظيفة المتقدم لها": ("Applied Position", "الوظيفة المتقدم لها / Applied Job"),
    "البريد الإلكتروني": ("Email Address", "البريد الإلكتروني / Email"),
    "رقم الجوال": ("Phone Number", "رقم الجوال / Phone"),
    "الراتب المتوقع": ("Expected Salary", "الراتب المتوقع / Expected Salary"),
    "المرحلة الحالية": ("Application Stage", "المرحلة / Stage"),
    "حالة الطلب": ("Application Status", "الحالة / Status"),
    "ملاحظات المقابلة والتقييم": ("Interview Notes", "ملاحظات المقابلة / Interview Notes"),

    # 13_GR_Transactions / Modular GR
    "نوع المعاملة الحكومية": ("Government Transaction Type", "نوع المعاملة / Transaction Type"),
    "تاريخ المعاملة": ("Transaction Date", "تاريخ المعاملة / Date"),
    "المنصة الحكومية": ("Government Portal", "المنصة / Portal"),
    "الرسوم الحكومية": ("Government Fees", "الرسوم / Fees"),
    "حالة المعاملة": ("Transaction Status", "الحالة / Status"),
    "تاريخ انتهاء الوثيقة الجديد": ("New Expiry Date", "تاريخ الانتهاء الجديد / Expiry Date"),
    "رقم الطلب / المرجع": ("Reference / Request Number", "رقم المرجع / Reference Number"),

    # 1_Company_Setup / Modular Company
    "اسم المنشأة بالعربي": ("Company Arabic Name", "اسم المنشأة / Company Name"),
    "اسم المنشأة بالإنجليزي": ("Company English Name", "اسم المنشأة بالإنجليزي / Company EN Name"),
    "رقم السجل التجاري": ("Commercial Registration (CR)", "السجل التجاري / CR Number"),
    "الرقم الضريبي": ("Tax Number (VAT)", "الرقم الضريبي / VAT Number"),
    "الرقم الموحد للمنشأة (700)": ("Unified 700 Number", "الرقم الموحد / 700 Number"),
    "رقم ملف مكتب العمل": ("Labor Office ID", "ملف العمل / Labor Office ID"),
    "رقم المنشأة في التأمينات": ("GOSI Entity Number", "رقم التأمينات / GOSI Entity ID"),
    "المدينة / المقر": ("City / Headquarter", "المدينة / City"),
    "هاتف المنشأة": ("Company Phone", "هاتف المنشأة / Phone"),
    "بريد المنشأة": ("Company Email", "بريد المنشأة / Email"),
}

BANNER_TITLES_EN: Dict[str, str] = {
    "بيانات الموظفين الأساسية ومواقع العمل": "Employees Master Data & Work Locations",
    "ساعات الحضور وسجلات الدوام": "Attendance Sheets & Working Hours",
    "عقود العمل وهيكل البدلات": "Employment Contracts & Allowances Structure",
    "الرواتب وتأمينات GOSI وحماية الأجور": "Payroll, GOSI & Wage Protection System",
    "الإجازات والأرصدة الافتتاحية": "Time Off & Opening Leave Balances",
    "العمل الإضافي والأوفرتايم": "Overtime Requests & Compensation (Labor Law Art. 107)",
    "قروض وسلف الموظفين والأقساط": "Employee Loans & Monthly Installments (Labor Law Art. 92)",
    "الجزاءات ومخالفات لائحة العمل": "Disciplinary Actions & Company Bylaws Penalties",
    "مستحقات نهاية الخدمة والمخالصة": "End of Service Settlement & Gratuity (EOS)",
    "تقييم الأداء والمكافآت": "Performance Appraisals & Periodic Ratings",
    "سجل التوظيف وطلبات التعيين": "Recruitment Pipeline & Job Applications",
    "معاملات العلاقات الحكومية": "Government Relations Transactions (GR & Portals)",
    "تأسيس المنشأة الشامل": "Comprehensive Enterprise Onboarding (Master Setup)",
    "تأسيس المنشأة والفروع ومراكز العمل": "Enterprise, Branches & Work Centers Setup",
}

# نصوص وتعليمات ورقة دليل الاستخدام (Instructions Sheet)
INSTRUCTION_TEXTS_EN: Dict[str, str] = {
    "📖 دليل استخدام: تأسيس المنشأة الشامل (Master Onboarding)": "📖 User Guide: Comprehensive Enterprise Setup (Master Onboarding)",
    "تاريخ التوليد: 2026-10-06 | نظام أتمتة الموارد البشرية Odoo": "Generation Date: 2026-10-06 | Odoo HR Automation System",
    "📌 شروط وتوجيهات تعبئة البيانات:": "📌 Data Entry Guidelines & Requirements:",
    "هذا الملف هو القالب الشامل والموحد لتأسيس بيانات منشأتك بالكامل في نظام Odoo HR.": "This file is the unified master template for onboarding your enterprise data completely into Odoo HR.",
    "ابدأ بتعبئة تبويب (1_بيانات_المنشأة) ثم انتقل للتبويبات التالية بالترتيب.": "Start by filling the (1_Company_Setup) sheet, then proceed with the remaining sheets in order.",
    "تبويب (الموظفون) يمثل المرجع الأساسي، حيث يتم استخدام (رقم الهوية / الإقامة) لربط عقودهم، رواتبهم، إجازاتهم، وقروضهم في بقية التبويبات.": "The (Employees) sheet serves as the primary reference, using (National ID / Iqama) to link contracts, payroll, time off, and loans across sheets.",
    "الحقول ذات الخلفية الكحلية الداكنة (*) هي حقول إلزامية لا يمكن استكمال التأسيس بدونها.": "Fields with dark navy headers (*) are mandatory and required to complete setup.",
    "الحقول الخضراء تحتوي على معادلات احتساب تلقائية (مثل إجمالي الراتب، خصم التأمينات، القسط الشهري) يرجى عدم مسحها.": "Green-shaded fields contain automated calculation formulas (e.g. gross salary, GOSI, installments). Please do not overwrite them.",
    "التواريخ تعتمد الصيغة القياسية الدولية: YYYY-MM-DD (مثال: 2026-10-01).": "Dates must adhere to the ISO standard: YYYY-MM-DD (e.g. 2026-10-01).",
    "⚖️ الضوابط النظامية المعمول بها (نظام العمل والتأمينات):": "⚖️ Applicable Statutory Controls (Saudi Labor Law & GOSI):",
    "نظام العمل السعودي (الملكي م/51): توثيق عقود العمل، الالتزام بالحد الأدنى للأجور، وحدود ساعات العمل والإضافي.": "Saudi Labor Law (Art. 51): Mandatory contract documentation, minimum wage compliance, and working hour limits.",
    "نظام التأمينات الاجتماعية: تطبيق نسب الحسم بدقة للمشتركين السعوديين (القديم 21.5% والجديد المتدرج) وغير السعوديين (2% أخطار مهنية).": "Social Insurance Law: Accurate deduction rates for Saudi contributors (21.5%) and non-Saudis (2% occupational hazards).",
    "المادة 92: حظر تجاوز حسم قروض وصاحب العمل عن 25% من أجر العامل الشهري.": "Article 92: Loan and employer deductions must not exceed 25% of the worker's monthly wage.",
    "المواد 84 و 85: احتساب مكافأة نهاية الخدمة بدقة وفق أسباب انتهاء العلاقة العمالية.": "Articles 84 & 85: End of Service Gratuity calculated according to service length and termination reason.",
    
    # Modular templates instructions headers
    "📖 دليل استخدام: الإجازات والأرصدة الافتتاحية (Time Off & Balances)": "📖 User Guide: Time Off & Opening Balances",
    "📖 دليل استخدام: الجزاءات والإنذارات والمخالفات (Disciplinary Management)": "📖 User Guide: Disciplinary Management & Penalties",
    "📖 دليل استخدام: الرواتب وتأمينات GOSI وحماية الأجور (Payroll & GOSI)": "📖 User Guide: Payroll, GOSI & Wage Protection",
    "📖 دليل استخدام: العقود والبدلات (Contracts & Allowances - hr.version)": "📖 User Guide: Contracts & Allowances Structure",
    "📖 دليل استخدام: العمل الإضافي والأوفرتايم (Overtime Requests - مادة 107)": "📖 User Guide: Overtime Requests (Labor Law Art. 107)",
    "📖 دليل استخدام: المعاملات والتأشيرات الحكومية (GR Transactions - مقيم وقوى)": "📖 User Guide: Government Relations & Visas (GR Transactions)",
    "📖 دليل استخدام: بيانات الموظفين الأساسية ومواقع العمل (Employees Master Data)": "📖 User Guide: Employees Master Data & Work Locations",
    "📖 دليل استخدام: بيانات تأسيس المنشأة والحسابات البنكية (Company Profile)": "📖 User Guide: Enterprise Setup & Bank Accounts",
    "📖 دليل استخدام: تقييمات الأداء والموظفين (Employee Appraisals)": "📖 User Guide: Performance Appraisals & Ratings",
    "📖 دليل استخدام: ساعات الحضور وسجلات الدوام (Attendance Sheets)": "📖 User Guide: Attendance Sheets & Working Hours",
    "📖 دليل استخدام: طلبات التوظيف وشواغر المتقدمين (Recruitment & Applicants)": "📖 User Guide: Recruitment & Job Applicants",
    "📖 دليل استخدام: قروض وسلف الموظفين والأقساط (Loans & Installments - مادة 92)": "📖 User Guide: Employee Loans & Installments (Labor Law Art. 92)",
    "📖 دليل استخدام: مكافأة نهاية الخدمة والتسويات (End of Service Rewards - مواد 77, 80, 84, 85)": "📖 User Guide: End of Service Gratuity & Settlement (EOS)",

    # Modular instructions body and legal rules
    "أيام الغياب غير المبرر تنعكس في مسير الرواتب تلقائياً بعد التحقيق.": "Unexcused absence days are reflected automatically in payroll following investigation.",
    "إجمالي الراتب يتم احتسابه آلياً بصيغة إكسل = الأساسي + السكن + النقل + البدلات الأخرى.": "Total gross salary is calculated automatically: Basic + Housing + Transport + Other Allowances.",
    "إرفاق سبب التكليف إلزامي للموافقة الإدارية.": "Attaching the assignment justification is mandatory for administrative approval.",
    "الآيبان البنكي إلزامي لتوليد ملفات نظام حماية الأجور (WPS SIF).": "Bank IBAN is mandatory for generating Wage Protection System files (WPS SIF).",
    "الآيبان يبدأ بـ SA ويتكون من 24 خانة لحماية الأجور.": "IBAN must begin with SA and contain 24 characters for Wage Protection compliance.",
    "الأجر الخاضع للتأمينات في النظام السعودي يشمل الراتب الأساسي + بدل السكن النقدي فقط بحد أقصى 45,000 ريال.": "Contributory wage under Saudi GOSI includes Basic Salary + Cash Housing Allowance only, capped at SAR 45,000.",
    "التقدير يطابق معايير تقييم الأداء المعتمدة في Odoo (prosys_hr_appraisal).": "Rating matches performance appraisal criteria in Odoo.",
    "التواريخ بصيغة YYYY-MM-DD.": "Dates must adhere to ISO format: YYYY-MM-DD.",
    "التواريخ يجب أن تكون بتنسيق YYYY-MM-DD.": "Dates must be formatted as YYYY-MM-DD.",
    "الحقول التي تحمل علامة (*) إلزامية لإنشاء المنشأة في Odoo.": "Fields marked with (*) are required for establishing the entity in Odoo.",
    "الخصم يطبق في مسير راتب نفس الشهر الذي وقع فيه الجزاء.": "Deductions are applied in the payroll of the same month the penalty occurred.",
    "الرصيد الافتتاحي يُسجل عند تهيئة رصيد سابق للموظف في Odoo.": "Opening balance is recorded when initializing previous employee leave balance in Odoo.",
    "الرقم الضريبي يتكون من 15 رقماً يبدأ وينتهي بالرقم 3 وفق هيئة الزكاة والضريبة والجمارك (ZATCA).": "VAT number must consist of 15 digits starting and ending with 3 per ZATCA regulations.",
    "السجل التجاري يتكون من 10 أرقام دقيقة.": "Commercial Registration (CR) must consist of exactly 10 digits.",
    "الشهر يُكتب بصيغة YYYY-MM (مثلاً 2026-10).": "Month must be entered in YYYY-MM format (e.g. 2026-10).",
    "المادة 106: لا يجوز تشغيل العامل أكثر من الحد الأقصى السنوي لساعات العمل الإضافية المحدد نظاماً.": "Article 106: Workers must not be employed beyond the statutory maximum annual overtime hours.",
    "المادة 107 من نظام العمل السعودي: يدفع صاحب العمل للعامل عن ساعات العمل الإضافية أجراً يوازي أجر الساعة مضافاً إليه 50% من أجره الأساسي (أجر ساعة ونصف).": "Article 107: Overtime hours are compensated at 100% hourly rate plus 50% of the basic wage (1.5x).",
    "المادة 109 من نظام العمل: يستحق العامل إجازة سنوية لا تقل عن 21 يوماً بأجر كامل، تزداد إلى 30 يوماً إذا أمضى 5 سنوات متصلة.": "Article 109: Worker is entitled to annual leave of at least 21 days with full pay, increasing to 30 days after 5 continuous years.",
    "المادة 113: إجازات المناسبات (5 أيام وفاة، 5 أيام زواج، 3 أيام مولود) بأجر كامل.": "Article 113: Special leave (5 days bereavement, 5 days marriage, 3 days paternity) with full pay.",
    "المادة 53 من نظام العمل: لا يجوز أن تزيد فترة التجربة على 90 يوماً، ويجوز باتفاق خطي صريح تمديدها بما لا يتجاوز 180 يوماً.": "Article 53: Probation period must not exceed 90 days, extendable by explicit written agreement up to 180 days.",
    "المادة 66 من نظام العمل: حصر الجزاءات التأديبية في (الإنذار، الغرامة، الحرمان من العلاوة، تأجيل الترقية، الإيقاف، الفصل).": "Article 66: Disciplinary penalties are limited to warning, fine, withholding allowance, deferring promotion, suspension, and dismissal.",
    "المادة 70: لا يجوز توقيع غرامة تزيد على أجر 5 أيام عن المخالفة الواحدة، ولا يجوز أن يقتطع من أجر العامل في الشهر الواحد أكثر من أجر 5 أيام وفاءً للغرامات.": "Article 70: A single fine must not exceed 5 days' pay, and monthly deduction for fines must not exceed 5 days' pay.",
    "المادة 71: لا يجوز توقيع جزاء تأديبي إلا بعد إبلاغ العامل كتابة والتحقيق معه وسماع دفاعه وتثبيت ذلك في محضر.": "Article 71: Disciplinary penalties require written notification, formal investigation, and recorded defense.",
    "المادة 80: حالات الفصل المشروع دون مكافأة أو إشعار (الاعتداء، التزوير، الخيانة، إفشاء الأسرار).": "Article 80: Lawful dismissal without gratuity or notice (assault, forgery, breach of trust, trade secret disclosure).",
    "المادة 84: أجر نصف شهر عن كل سنة من السنوات الخمس الأولى، وأجر شهر عن كل سنة من السنوات التالية.": "Article 84: Half-month wage for each of the first 5 years, and one month wage for each subsequent year.",
    "المادة 85: في حال استقالة العامل يستحق ثلث المكافأة بعد خدمة من سنتين لـ 5 سنوات، وثلثيها من 5 لـ 10 سنوات، وتستحق كاملة إذا بلغت خدمته 10 سنوات فأكثر.": "Article 85: Upon resignation, worker is entitled to 1/3 gratuity for 2-5 years, 2/3 for 5-10 years, and full gratuity for 10+ years.",
    "المادة 88: يجب دفع مكافأة نهاية الخدمة وتصفية حقوق العامل خلال أسبوع من تاريخ انتهاء العقد.": "Article 88: End of service gratuity and entitlements must be settled within one week of contract termination.",
    "المادة 92 من نظام العمل السعودي: لا يجوز حسم أي مبلغ من أجر العامل لقاء قروض صاحب العمل بما يزيد على 25% من أجر العامل لحماية كفايته المعيشية.": "Article 92: Deductions for employer loans must not exceed 25% of the worker's monthly wage.",
    "المادة 98: ساعات العمل الفعلية لا تزيد على 8 ساعات في اليوم أو 48 ساعة في الأسبوع، وتُخفض لـ 6 ساعات يومياً في شهر رمضان للمسلمين.": "Article 98: Actual working hours must not exceed 8 hours per day or 48 hours per week (reduced to 6 hours daily during Ramadan for Muslim workers).",
    "المرشح المقبول في حالة 'عرض عمل معتمد' يمكن تحويله مباشرة لموظف في Odoo عبر سراج.": "Candidates in 'Approved Job Offer' status can be converted directly to employee in Odoo via Seraj.",
    "المعدل العام يُحسب بوزن نسبي (70% أهداف و 30% كفاءات).": "Overall score is calculated with weighted ratio: 70% KPIs and 30% Competencies.",
    "برنامج حماية الأجور (WPS): تطابق صافي الراتب المحول مع المسير المعتمد إلزامي لتفادي إيقاف الخدمات من وزارة الموارد البشرية.": "Wage Protection System (WPS): Transferred net salary must strictly match approved payroll to avoid service suspension.",
    "تاريخ انتهاء الوثيقة الجديد ينعكس في ملف الموظف لتفعيل تنبيهات التجديد المبكر في Odoo.": "New expiry date updates the employee profile to trigger early renewal alerts in Odoo.",
    "رقم الجوال يبدأ بـ 05 ويتكون من 10 خانات.": "Mobile number must start with 05 and consist of 10 digits.",
    "رقم الهوية الوطنية أو الإقامة يتكون من 10 أرقام.": "National ID or Iqama must consist of 10 digits.",
    "رقم هوية أو إقامة الموظف يربط العقد تلقائياً بالموظف المسجل في Odoo.": "National ID / Iqama links the contract automatically to the registered employee in Odoo.",
    "ساعات الحضور تقارن بسياسة الدوام المعتمدة في Odoo (rm_hr_attendance_sheet).": "Attendance hours are evaluated against approved working schedule policy in Odoo.",
    "صافي المخالصة = مكافأة نهاية الخدمة + بدل الإجازات - السلف المتبقية.": "Net settlement = End of Service Gratuity + Leave Encashment - Outstanding Loans.",
    "غير السعودي: 2% أخطار مهنية فقط تتحملها المنشأة بالكامل ولا يُخصم من أجر العامل أي شيء.": "Non-Saudi contributors: 2% occupational hazards borne entirely by employer; no deduction from employee wage.",
    "قرارات التوطين والمهن المقفلة: مراعاة نسب السعودة والمسميات المسعودة حصراً لدى وزارة الموارد البشرية.": "Saudization Regulations: Strict adherence to Saudization ratios and reserved professions by Ministry of Human Resources.",
    "قيمة القسط الشهري = إجمالي القرض / عدد أشهر السداد.": "Monthly installment = Total loan amount / Repayment months.",
    "لائحة تنظيم العمل: تقييم فترة التجربة يحدد تثبيت الموظف أو إنهاء عقده خلال المهلة المحددة نظاماً بموجب المادة 53.": "Work Bylaws: Probation evaluation determines employee confirmation or termination within statutory limit (Art. 53).",
    "مبلغ الأوفرتايم = عدد الساعات * أجر الساعة * 1.5.": "Overtime amount = Worked hours * Hourly rate * 1.5.",
    "مدة الخدمة تحتسب من تاريخ المباشرة إلى آخر يوم عمل.": "Service duration is calculated from hiring date to the last working day.",
    "مكافأة نهاية الخدمة تحتسب على أساس آخر أجر كامل تقاضاه العامل (الأساسي + البدلات).": "End of service gratuity is calculated based on the last gross wage received (Basic + Allowances).",
    "نسبة الاستقطاع = القسط الشهري / الراتب الشهري.": "Deduction ratio = Monthly installment / Monthly salary.",
    "نظام الإقامة: تجديد الإقامة قبل انتهائها لتفادي الغرامات المالية المقررة من الجوازات.": "Residency Law: Renew Iqama before expiration to prevent financial penalties from Jawazat.",
    "نظام التأمينات الاجتماعية: نسبة المشترك السعودي القديم (9% معاشات + 0.75% ساند = 9.75% على الموظف، و 11.75% على صاحب العمل).": "Social Insurance: Standard Saudi contributor (9% pension + 0.75% SANED = 9.75% employee, 11.75% employer).",
    "نظام التأمينات الجديد 2024: يخضع لنسب متدرجة تبدأ بـ 10% إلى 11% تدريجياً.": "New GOSI 2024: Subject to graduated rates starting at 10% up to 11%.",
    "نظام الشركات وهيئة الزكاة: تطابق الاسم التجاري مع السجل والرقم الضريبي إلزامي.": "Corporate & ZATCA Regulations: Commercial name must strictly match CR and VAT number.",
    "نظام العمل السعودي: تسجيل تاريخ المباشرة الفعلي يحدد تاريخ بدء احتساب الحقوق والتأمينات ونهاية الخدمة.": "Saudi Labor Law: Registering the actual hire date establishes the start of rights, GOSI, and gratuity.",
    "نوع الإجازة يتم اختياره من القائمة المنسدلة.": "Leave type must be chosen from the dropdown list.",
    "نوع التأمينات يحدد تلقائياً نسب الحسم وحصة الشركة في مسير الرواتب.": "GOSI type determines deduction percentages and employer share in payroll.",
    "يتم اختيار الشركة، الفرع، القسم، والوظيفة من القوائم المنسدلة المعتمدة في Odoo.": "Company, branch, department, and job position are selected from approved dropdown lists in Odoo.",
    "يتم حساب أجر الساعة بقسمة الأجر الأساسي على 240 ساعة شهرياً.": "Hourly rate is calculated by dividing basic salary by 240 hours per month.",
    "يجب ألا تزيد نسبة الاستقطاع عن 25% تحت أي ظرف امتثالاً لنظام العمل.": "Deduction ratio must not exceed 25% under any circumstances in compliance with Labor Law.",
    "يجب إجراء تحقيق كتابي مع الموظف وسماع أقواله قبل توقيع أي جزاء.": "Written formal investigation and hearing defense are mandatory prior to imposing any penalty.",
    "برنامج حماية الأجور (WPS): يلزم تسجيل الآيبان الصحيح المعتمد لدى البنك المركزي السعودي.": "Wage Protection System (WPS): Valid approved bank IBAN from Saudi Central Bank (SAMA) is required.",
    "تطابق بنود العقد مع منصة قوى والحد الأدنى للأجور للسعوديين (4,000 ريال لاحتساب نطاقات كامل).": "Contract terms must match Qiwa platform with minimum wage of SAR 4,000 for Saudis for full Nitaqat credit.",
    "تدرج العقوبة إلزامي: إنذار ➔ خصم ➔ إيقاف.": "Penalty gradation is mandatory: Warning ➔ Deduction ➔ Suspension.",
    "تواريخ انتهاء الإقامة والجواز تنعكس في ملف الموظف لتفعيل تنبيهات التجديد المبكر في Odoo.": "Iqama and passport expiry dates update the employee profile to trigger early renewal alerts in Odoo.",
    "تخصم الأقساط الشهرية آلياً عبر مسير الرواتب hr.payslip في Odoo.": "Monthly installments are automatically deducted via payroll payslips (hr.payslip) in Odoo.",
    
    # Modular templates instructions
    "📋 دليل استخدام قالب استيراد الموظفين": "📋 Employee Import Template Guide",
    "دليل استخدام قالب استيراد الموظفين": "Employee Import Template Guide",
    "1. كيف تملأ ورقة Employees": "1. How to Fill the Employees Sheet",
    "ابدأ من الصف رقم 3. الصف رقم 2 هو مثال توضيحي — احذفه قبل رفع الملف.": "Start from row 3. Row 2 is an illustrative example — clear it before upload.",
    "الاسم الكامل للموظف كما سيظهر في Odoo.": "Full employee name as it will appear in Odoo.",
    "أحمد محمد العتيبي": "Ahmed Mohammed Al-Otaibi",
    "أحمد (اسم ناقص)": "Ahmed (Incomplete name)",
    "البريد الإلكتروني المهني. يُستخدم للكشف عن التكرار — إن وُجد موظف بنفس البريد سيظهر تحذير.": "Professional work email. Used for duplicate detection — a warning appears if an employee exists with the same email.",
    "ahmed@company.com": "ahmed@company.com",
    "ahmed@ (بريد غير مكتمل)": "ahmed@ (Incomplete email)",
    "رقم هاتف العمل. أدخله كنص بدون فراغات. اتركه فارغاً إن لم يكن متوفراً.": "Work phone number. Enter as text without spaces. Leave empty if unavailable.",
    "011-234-5678 (الشرطات تُزال تلقائياً لكن يُفضَّل إدخالها بدونها)": "011-234-5678 (Hyphens stripped automatically; prefer raw digits)",
    "رقم الجوال. نفس قواعد work_phone.": "Mobile phone number. Follows the same rules as work_phone.",
    "المسمى الوظيفي النصي الحر. لا يرتبط بقائمة Odoo — يُكتب كما تريد.": "Free-form job title. Does not restrict to Odoo list.",
    "تاريخ التوظيف (اختياري). يُملأ يدوياً من واجهة Odoo عند الحاجة. إن أدخلته هنا استخدم الصيغة YYYY-MM-DD.": "Hiring date (optional). Use YYYY-MM-DD format.",
    "15/01/2026 (صيغة خاطئة)": "15/01/2026 (Invalid format)",
    "اسم الشركة كما هو في ورقة Reference. استخدم القائمة المنسدلة.": "Company name as listed in the Reference sheet. Use the dropdown list.",
    "النخبة (اسم مختصر — قد لا يُطابَق)": "Al-Nukhba (Short name — might not match)",
    "اسم القسم. استخدم القيمة من عمود complete_name في ورقة Reference (مثلاً: شركة X / قسم Y). القائمة المنسدلة تعرض الخيارات المتاحة.": "Department name. Use value from complete_name in the Reference sheet. Dropdown displays available choices.",
    "تقنية المعلومات (بدون اسم الشركة — قد يكون غامضاً)": "Information Technology (Without company name — may be ambiguous)",
    "الوظيفة من قائمة Odoo. استخدم القائمة المنسدلة واختر من الخيارات المتاحة.": "Job position from Odoo catalog. Choose from dropdown.",
    "2. القوائم المنسدلة — تنبيه مهم": "2. Dropdown Lists — Important Notice",
    "القوائم المنسدلة مساعدة فقط وتعكس بيانات Odoo وقت إنشاء هذا القالب.\nالتحقق الفعلي يحصل مقابل Odoo الحي عند رفع الملف.\nلو تغيّرت الأقسام أو الوظائف في Odoo بعد إنشاء القالب، أنشئ نسخة جديدة منه.": "Dropdown lists are helpers reflecting Odoo reference data at template generation time.\nActual validation occurs against live Odoo data upon upload.\nIf departments or jobs change in Odoo after generation, export a fresh template.",
    "3. ماذا تعني نتائج التقرير": "3. Understanding Audit Report Statuses",
    "الصف جاهز للإنشاء — بانتظار موافقتك الصريحة.": "Row is ready for creation — awaiting your explicit approval.",
    "يحتاج مراجعة يدوية — مثلاً: موظف مشابه موجود مسبقاً، أو اسم القسم غامض. لا يُنشأ تلقائياً.": "Requires manual review — e.g. similar employee exists or department is ambiguous.",
    "لن يُنشأ — صحّح الخطأ المذكور في التقرير وأعد المحاولة.": "Will not be created — fix the indicated error in the report and retry.",
    "حصل خطأ غير متوقع أثناء الإنشاء. لا تُعد المحاولة بنفسك — تواصل مع الدعم التقني أولاً.": "Unexpected error occurred during execution. Contact technical support before retrying.",
    "4. متى تتواصل مع الدعم التقني": "4. When to Contact Technical Support",
    "ظهر outcome_uncertain في أي صف من الصفوف.": "An outcome_uncertain status appears for any row.",
    "رسالة خطأ غير مفهومة أثناء تشغيل أي خطوة.": "Unclear error message occurs during any step.",
    "أردت تعديل موظف تم إنشاؤه مسبقاً (التعديل يحصل يدوياً من واجهة Odoo، لا عبر هذه الأداة).": "You wish to modify an existing employee (edits are performed in Odoo directly).",
    "انتهت صلاحية مفتاح الـ API (ستظهر رسالة خطأ عند بدء التشغيل).": "API credentials expired (error message appears at start).",
    "⚠ ملاحظة:": "⚠ Notice:",
    "✓ مثال صحيح:": "✓ Valid Example:",
    "✗ مثال خاطئ:": "✗ Invalid Example:",
}

# قيم الجداول المرجعية (Reference Sheet Data & Dropdowns)
REFERENCE_VALUES_EN: Dict[str, str] = {
    # Genders
    "ذكر": "Male",
    "أنثى": "Female",

    # Marital Statuses
    "أعزب": "Single",
    "متزوج": "Married",
    "مطلق": "Divorced",
    "أرمل": "Widowed",

    # Branch Types
    "مقر رئيسي": "Headquarter",
    "فرع تابع": "Branch",

    # Contract Types
    "محدد المدة": "Fixed-Term",
    "غير محدد المدة": "Indefinite-Term",

    # GOSI Types
    "سعودي - مشترك قديم (21.5%)": "Saudi - Standard Contributor (21.5%)",
    "سعودي - مشترك جديد نظام 2024 (متدرج)": "Saudi - New System 2024 (Graduated)",
    "غير سعودي - أخطار مهنية فقط (2%)": "Non-Saudi - Occupational Hazards Only (2%)",

    # Leave Types
    "إجازة سنوية اعتيادية": "Annual Regular Leave",
    "إجازة مرضية": "Sick Leave",
    "إجازة زواج (مادة 113 - 5 أيام)": "Marriage Leave (Art. 113 - 5 Days)",
    "إجازة وفاة (مادة 113 - 5 أيام)": "Bereavement Leave (Art. 113 - 5 Days)",
    "إجازة مولود (مادة 113 - 3 أيام)": "Paternity Leave (Art. 113 - 3 Days)",
    "إجازة حج (مادة 114 - 10-15 يوماً)": "Hajj Leave (Art. 114 - 10-15 Days)",
    "إجازة بدون راتب (مادة 116)": "Unpaid Leave (Art. 116)",

    # Loan Types
    "سلفة شخصية قصيرة الأجل": "Short-term Personal Advance",
    "بدل سكن مقدم": "Advance Housing Allowance",
    "قرض زواج ميسر": "Soft Marriage Loan",
    "سلفة طارئة": "Emergency Advance",

    # Payment Methods
    "تحويل بنكي": "Bank Transfer",
    "نقدي (كاش)": "Cash",
    "شيك مصرفي": "Bank Cheque",

    # Penalties
    "إنذار كتابي أول": "First Written Warning",
    "إنذار كتابي ثانٍ / نهائي": "Second / Final Written Warning",
    "خصم يوم من الأجر": "1-Day Wage Deduction",
    "خصم يومين من الأجر": "2-Day Wage Deduction",
    "خصم ثلاثة أيام من الأجر": "3-Day Wage Deduction",
    "إيقاف مؤقت عن العمل": "Temporary Suspension",
    "فصل تأديبي بمكافأة": "Disciplinary Dismissal with EOS",
    "فصل بموجب المادة 80 (بدون مكافأة)": "Dismissal under Art. 80 (Without EOS)",

    # Overtime Types
    "ساعات عمل عادية (1.5x الأجر الأساسي)": "Regular Workday Overtime (1.5x Hourly Rate)",
    "ساعات عمل في عطلة أسبوعية / جمعة (1.5x)": "Weekend / Friday Overtime (1.5x Hourly Rate)",
    "ساعات عمل في يوم عيد / عطلة رسمية (1.5x)": "Public Holiday / Eid Overtime (1.5x Hourly Rate)",

    # Termination Reasons (EOS)
    "انتهاء مدة العقد (مادة 84 - مكافأة كاملة)": "Contract Expiration (Art. 84 - Full Gratuity)",
    "فسخ العقد باتفاق الطرفين (مادة 84 - مكافأة كاملة)": "Mutual Agreement Termination (Art. 84 - Full Gratuity)",
    "استقالة العامل - خدمة أقل من سنتين (مادة 85 - لا يستحق)": "Resignation - Under 2 Years (Art. 85 - No Gratuity)",
    "استقالة العامل - خدمة 2 إلى 5 سنوات (مادة 85 - ثلث المكافأة)": "Resignation - 2 to 5 Years (Art. 85 - 1/3 Gratuity)",
    "استقالة العامل - خدمة 5 إلى 10 سنوات (مادة 85 - ثلثا المكافأة)": "Resignation - 5 to 10 Years (Art. 85 - 2/3 Gratuity)",
    "استقالة العامل - خدمة أكثر من 10 سنوات (مادة 85 - مكافأة كاملة)": "Resignation - Over 10 Years (Art. 85 - Full Gratuity)",
    "إنهاء من صاحب العمل بموجب المادة 77": "Termination by Employer (Art. 77)",
    "فسخ العامل بموجب المادة 81 (مكافأة كاملة)": "Termination by Worker (Art. 81 - Full Gratuity)",
    "بلوغ سن التقاعد (مادة 84 - مكافأة كاملة)": "Retirement Age (Art. 84 - Full Gratuity)",
    "وفاة العامل أو العجز الكلي (مكافأة كاملة)": "Death or Total Disability (Full Gratuity)",

    # Appraisals & Ratings
    "تقييم سنوي شامل": "Annual Comprehensive Appraisal",
    "تقييم فترة التجربة (90/180 يوماً)": "Probation Period Review (90/180 Days)",
    "تقييم نصف سنوي": "Semi-Annual Review",
    "تقييم ربع سنوي": "Quarterly Review",
    "ممتاز (90 - 100)": "Excellent (90 - 100)",
    "جيد جداً (80 - 89)": "Very Good (80 - 89)",
    "جيد (70 - 79)": "Good (70 - 79)",
    "مرضي (60 - 69)": "Satisfactory (60 - 69)",
    "يحتاج تحسين (أقل من 60)": "Needs Improvement (Under 60)",

    # Recruitment
    "مقبول مبدئياً": "Shortlisted",
    "مقابلة مجدولة": "Interview Scheduled",
    "عرض عمل مرسل": "Job Offer Sent",
    "معتمد ومباشر": "Hired & Onboarded",
    "مرفوض / غير مطابق": "Rejected / Unmatched",

    # Government Relations (GR)
    "تجديد إقامة": "Iqama Renewal",
    "إصدار تأشيرة خروج وعودة": "Exit & Re-entry Visa",
    "إصدار تأشيرة نهائية": "Final Exit Visa",
    "تجديد رخصة عمل": "Work Permit Renewal",
    "نقل كفالة / خدمات": "Sponsorship Transfer",
    "تعديل مهنة": "Profession Change",
    "إضافة تابعين": "Dependents Addition",
    "بلاغ هروب / انقطاع عن العمل": "Absence / Runaway Notice",
    "جديدة": "New",
    "تحت الإجراء": "In Progress",
    "مكتملة ومعتمدة": "Completed & Approved",
    "ملغاة": "Cancelled",
    "مرفوضة من المنصة": "Rejected by Portal",

    # Nationalities
    "سعودي": "Saudi",
    "مصري": "Egyptian",
    "يمني": "Yemeni",
    "أردني": "Jordanian",
    "سوري": "Syrian",
    "لبناني": "Lebanese",
    "سوداني": "Sudanese",
    "هندي": "Indian",
    "باكستاني": "Pakistani",
    "فلبيني": "Filipino",
    "بنجلاديشي": "Bangladeshi",
    "نيبالي": "Nepali",
    "أخرى": "Other",

    # Companies
    "شركة النخبة الذكية للتقنية": "Smart Elite Tech Co.",
    "شركة توركين للتجزئة": "Turkeen Retail Co.",
    "شركة العقار الموحدة": "Unified Real Estate Co.",

    # Cities
    "الرياض": "Riyadh",
    "جدة": "Jeddah",
    "الدمام": "Dammam",
    "مكة المكرمة": "Makkah",
    "المدينة المنورة": "Madinah",
    "الخبر": "Khobar",
    "الجبيل": "Jubail",
    "الأحساء": "Al-Ahsa",
    "تبوك": "Tabuk",
    "أبها": "Abha",
    "خميس مشيط": "Khamis Mushait",
    "جازان": "Jazan",
    "نجران": "Najran",
    "حائل": "Hail",
    "ينبع": "Yanbu",
    "القصيم": "Al-Qassim",

    # Penalties
    "خصم 3 أيام من الأجر": "3-Day Wage Deduction",
    "خصم 5 أيام من الأجر (الحد الأقصى مادة 70)": "5-Day Wage Deduction (Maximum per Art. 70)",
    "إيقاف عن العمل مع حرمان من الأجر": "Suspension from Work Without Pay",

    # Additional Leaves
    "إجازة حج (مادة 114)": "Hajj Leave (Art. 114)",
    "إجازة بدون راتب": "Unpaid Leave",

    # Additional EOS Reasons
    "استقالة العامل - خدمة 5 إلى 10 سنوات (مادة 85 - ثلثي المكافأة)": "Resignation - 5 to 10 Years (Art. 85 - 2/3 Gratuity)",
    "فصل بموجب المادة 80 (سقوط المكافأة نظاماً)": "Dismissal under Art. 80 (Loss of Gratuity)",
    "إنهاء غير مشروع من صاحب العمل مادة 77 (مكافأة + تعويض)": "Unlawful Termination by Employer Art. 77 (Gratuity + Compensation)",
    "ترك العمل بموجب المادة 81 لخطأ صاحب العمل (مكافأة كاملة)": "Worker Leaving under Art. 81 due to Employer Fault (Full Gratuity)",
    "استقالة العاملة خلال 6 أشهر من الزواج أو 3 أشهر من الوضع (مادة 87 - كاملة)": "Female Worker Resignation within 6 Months of Marriage or 3 Months of Delivery (Art. 87 - Full Gratuity)",

    # Additional Ratings & Recruitment
    "غير مرضي (أقل من 60)": "Unsatisfactory (Under 60)",
    "مرفوض": "Rejected",

    # Additional GR
    "تعديل مهنة في قوى ومقيم": "Profession Change (Qiwa & Muqeem)",
    "نقل كفالة": "Sponsorship Transfer",
    "إصدار إقامة جديدة": "Issue New Iqama",

    # Banks
    "مصرف الراجحي": "Al Rajhi Bank",
    "البنك الأهلي السعودي": "Saudi National Bank (SNB)",
    "مصرف الإنماء": "Alinma Bank",
    "بنك الرياض": "Riyad Bank",
    "بنك البلاد": "Bank Albilad",
    "البنك العربي الوطني": "Arab National Bank (ANB)",
    "البنك السعودي الأول (ساب)": "Saudi Awwal Bank (SAB)",
    "بنك الجزيرة": "Bank AlJazira",
    "البنك السعودي للاستثمار": "Saudi Investment Bank (SAIB)",
    "بنك الخليج الدولي": "Gulf International Bank (GIB)",

    # Departments
    "الإدارة العليا": "Executive Management",
    "المبيعات والتسويق": "Sales & Marketing",
    "المحاسبة والمالية": "Accounting & Finance",
    "الموارد البشرية": "Human Resources",
    "تقنية المعلومات": "Information Technology",

    # Jobs
    "أخصائي موارد بشرية": "HR Specialist",
    "المدير العام": "General Manager",
    "محاسب": "Accountant",
    "مطوّر برمجيات": "Software Developer",
    "مندوب مبيعات": "Sales Representative",

    # Branches
    "فرع الرياض - المقر الرئيسي": "Riyadh Branch - Headquarter",
    "فرع جدة": "Jeddah Branch",
    "فرع الدمام": "Dammam Branch",
    "فرع الخبر": "Khobar Branch",
}


ARABIC_TERMS = {
    "GOSI": "التأمينات الاجتماعية",
    "WPS": "نظام حماية الأجور",
    "My Company": "منشأتي",
    "Administration": "الإدارة",
    "Abdullah Al-Ghamdi": "عبدالله الغامدي",
    "Al-Nokhba Smart Tech Co.": "شركة النخبة للتقنية الذكية",
}

DATE_TEXT = "تاريخ التوليد:"
EXAMPLE_PROPERTY = "HRTemplateExampleRows"
REFERENCE_TEXT_EN = {**REFERENCE_VALUES_EN, **EXAMPLE_TEXT_EN}
ENGLISH_SOURCE_HEADERS = {
    en.casefold(): ar.casefold()
    for ar, en in {**{ar: labels[0] for ar, labels in HEADER_DICTIONARY.items()}, **ADDITIONAL_HEADERS_EN}.items()
}


def _localized_text(ar: str, en: str, language: str) -> str:
    if language == "en":
        return en
    if language == "ar" or ar == en:
        return ar
    return f"{ar} / {en}"


def _arabic_text(text: str) -> str:
    text = re.sub(r"\s*\([^()]*[A-Za-z]{2,}[^()]*\)$", "", text) if text.startswith("📖") else text
    for en, ar in ARABIC_TERMS.items():
        text = text.replace(en, ar)
    return text


def translate_header_cell(val: str, language: str) -> str:
    if not isinstance(val, str) or not val.strip():
        return val
    clean = val.strip().rstrip(" *")
    translation = ADDITIONAL_HEADERS_EN.get(clean) or HEADER_DICTIONARY.get(clean, (clean,))[0]
    label = _localized_text(_arabic_text(clean), translation, language)
    return f"{label} *" if val.strip().endswith("*") else label


def _sheet_title(title: str, language: str) -> str:
    prefix, _, name = title.partition("_")
    number = f"{prefix} " if prefix.isdecimal() else ""
    ar, en = TAB_LABELS.get(name if number else title, (title, title))
    return f"{number}{_localized_text(ar, en, language).replace(' / ', '-')}"


def _translate_example(cell, language: str) -> None:
    text = cell.value
    if not isinstance(text, str) or cell.data_type == "f":
        return
    cell.value = _localized_text(_arabic_text(text), REFERENCE_TEXT_EN.get(text, text), language)


def _translate_instructions(ws, language: str, include_example: bool) -> None:
    for row in ws.iter_rows():
        for cell in row:
            text = cell.value
            if not isinstance(text, str):
                continue
            if text.startswith(DATE_TEXT):
                date = text.removeprefix(DATE_TEXT).split("|", 1)[0].strip()
                en = f"Generated on {date} | Odoo HR"
            else:
                en = INSTRUCTION_TEXTS_EN.get(text, text)
            ar = _arabic_text(text).replace("1_بيانات_المنشأة", "1 تأسيس المنشأة")
            en = en.replace("1_Company_Setup", "1 Company Setup")
            cell.value = _localized_text(ar, en, language)
    if include_example:
        ws.append([None, _localized_text(
            "الصف الاسترشادي للتوضيح. احذفه قبل إدخال بياناتك.",
            "The sample row is for guidance. Delete it before entering your own data.",
            language,
        )])


def _example_digest(ws, row: int, formula_columns: list[int]) -> str:
    values = [
        (cell.column, str(cell.value))
        for cell in ws[row]
        if cell.column not in formula_columns and cell.value not in (None, "")
    ]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode("utf-8")).hexdigest()


def template_example_matches(ws, row: int) -> Optional[bool]:
    """Recognize an unchanged catalog example even after Excel recalculates its formulas."""
    properties = ws.parent.custom_doc_props
    if EXAMPLE_PROPERTY not in properties.names:
        return None
    try:
        example = json.loads(properties[EXAMPLE_PROPERTY].value).get(ws.title)
        if example is not None:
            return _example_digest(ws, row, example["formulas"]) == example["digest"]
    except (TypeError, ValueError, KeyError):
        pass
    return None


def localize_workbook(
    src_path: Path,
    dest_path: Path,
    language: str = "bilingual",
    include_example: bool = True,
    company_name: Optional[str] = None,
) -> Path:
    """Localize the catalog workbook while retaining its layout and dropdowns."""
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    lang = language.lower() if language and language.lower() in {"ar", "en", "bilingual"} else "ar"

    with Path(src_path).open("rb") as source:
        wb = openpyxl.load_workbook(source)
    reference_title = _sheet_title("Reference", lang)
    examples = {}

    for ws in wb:
        source_title = ws.title
        ws.title = _sheet_title(source_title, lang)
        ws.sheet_view.rightToLeft = lang == "ar"
        if source_title == "Instructions":
            _translate_instructions(ws, lang, include_example)
            continue
        if source_title == "Reference":
            for cell in ws[1]:
                label = REFERENCE_HEADINGS.get(cell.value)
                if label:
                    cell.value = _localized_text(label, cell.value.replace("_", " ").title(), lang)
            for row in ws.iter_rows(min_row=2):
                for cell in row:
                    _translate_example(cell, lang)
            continue

        has_banner = len([c for c in ws[1] if c.value is not None]) <= 2 and ws.max_row >= 2
        header_row = 2 if has_banner else 1
        if has_banner and isinstance(ws["A1"].value, str):
            title = ws["A1"].value
            ar = _arabic_text(title.split(" (", 1)[0])
            en = INSTRUCTION_TEXTS_EN.get(f"📖 دليل استخدام: {title}", "").removeprefix("📖 User Guide: ")
            ws["A1"] = _localized_text(ar, en or title, lang)

        for cell in ws[header_row]:
            if isinstance(cell.value, str):
                cell.value = translate_header_cell(cell.value, lang)

        for rule in ws.data_validations.dataValidation:
            if rule.formula1 and "Reference!" in rule.formula1:
                rule.formula1 = rule.formula1.replace("Reference!", f"'{reference_title}'!")
            if rule.error:
                rule.error = _localized_text(
                    "اختر قيمة من القائمة المنسدلة.", "Select a value from the dropdown.", lang
                )
            if rule.errorTitle:
                rule.errorTitle = _localized_text("قيمة غير صالحة", "Invalid value", lang)

        if has_banner and ws.max_row > header_row:
            for cell in ws[header_row + 1]:
                if include_example:
                    _translate_example(cell, lang)
                elif cell.data_type == "f":
                    cell.value = f'=IF(COUNTA(A{cell.row})=0,"",{cell.value[1:]})'
                else:
                    cell.value = None

            if include_example:
                row = header_row + 1
                formula_columns = [c.column for c in ws[row] if c.data_type == "f"]
                examples[ws.title] = {"formulas": formula_columns, "digest": _example_digest(ws, row, formula_columns)}

    if examples:
        wb.custom_doc_props.append(StringProperty(name=EXAMPLE_PROPERTY, value=json.dumps(examples, ensure_ascii=False)))
    wb.save(dest_path)
    logger.info("Localized workbook saved to %s (lang=%s, include_example=%s)", dest_path, lang, include_example)
    return dest_path
