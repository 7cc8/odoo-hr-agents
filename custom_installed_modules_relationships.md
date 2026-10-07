# الموديولات المخصصة والمثبتة في بيئة Odoo

> تقرير مبني على `installed_modules.csv` و`installed_modules_detailed.csv` و`module_artifacts.csv` ولقطة `field_catalog.csv` المتاحة في المحادثة.

## نطاق التقرير

- عدد الموديولات المصنفة هنا كـ Custom/Extension: **26**.
- يتضمن التقرير الموديولات ذات الـprefix المخصص مثل `prosys_*` و`nthub_*` و`sc_*` وغيرها، إضافة إلى `studio_customization`.
- العلاقات في هذا الملف تعني أساسًا **Dependencies المباشرة** وما يظهر في `module_artifacts.csv` من النماذج/القوائم/التقارير. لا يعني وجود dependency وحده أن الموديول يعدّل كل وظيفة في الموديول الآخر.

## ملخص حسب العائلة

- **prosys**: 10
- **nthub**: 1
- **sharif**: 1
- **sc**: 1
- **rm**: 1
- **bi**: 1
- **dev**: 1
- **petty**: 1
- **custom**: 8
- **studio**: 1

## قائمة الموديولات

| # | Technical Name | Display Name | Category |
|---:|---|---|---|
| 1 | `prosys_advance_recruitment` | Advance Recruitment | Recruitment |
| 2 | `prosys_approval_request` | Prosys Approval Request Customization | hr |
| 3 | `prosys_employee_history_calender` | Employee History Calendar | Human Resources |
| 4 | `prosys_expenses` | Prosys Expenses | Category |
| 5 | `prosys_gr_transaction` | Prosys GR Transaction | Human Resources |
| 6 | `prosys_hr_appraisal` | HR - Employee Evaluation & Appraisal | Human Resources |
| 7 | `prosys_hr_contract_custom` | Prosys HR Contract Custom | hr |
| 8 | `prosys_hr_contract_total` | Prosys HR Contract Total | hr |
| 9 | `prosys_hr_recruitment_custom` | Prosys HR Recruitment Custom | Recruitment |
| 10 | `prosys_warning_letter` | Prosys Warning Letter | hr |
| 11 | `nthub_hr_disciplinary` | Employee Disciplinary Management | Human Resources |
| 12 | `sharif_hr` | Employee Attachments | Human Resources |
| 13 | `sc_hr_mobile_connector` | Prosys HR Mobile App Connector | API |
| 14 | `rm_hr_attendance_sheet` | HR Attendance Sheet And Policies | hr |
| 15 | `bi_hr_overtime_request` | Employee Overtime Request and Payroll in Odoo | Human Resources |
| 16 | `dev_hr_loan` | Employee Loan Management, HR Loan Process Employee | Human Resources |
| 17 | `petty_cash_management` | Petty Cash Management | Accounting |
| 18 | `hr_employee_move` | hr_employee_move | Uncategorized |
| 19 | `hr_employee_profile` | Employee Profile | Extra Tools |
| 20 | `hr_employee_vacation_salary` | HR - Employee Vacation Salary | hr |
| 21 | `hr_employee_working_hours` | Employee Working Hours | Human Resources |
| 22 | `hr_end_service_benefits` | Employee End Of Service Rewards [ESR] | hr |
| 23 | `hr_leaves` | HR Leaves | hr |
| 24 | `hr_timeoff` | HR Holidays | hr |
| 25 | `report_qweb_pdf_watermark` | Pdf watermark | Technical Settings |
| 26 | `studio_customization` | Studio customizations | Studio |

## تفاصيل كل موديول

### 1. `prosys_advance_recruitment`

**Display Name:** Advance Recruitment

**ما هو:** التوظيف المتقدم؛ الدليل المباشر في الـartifacts يشمل `new.hiring.request` ومشاهد applicants/stages وقوائم New Hiring.

**Direct Dependencies:** `base`, `hr`, `hr_recruitment`

**النماذج/الأهداف الظاهرة في الـartifacts:** `hr.applicant`, `hr.recruitment.stage`, `new.hiring.request`

**أهم القوائم (Menus):**
- `New Hiring` — Employees/New Hiring
- `Request` — Employees/New Hiring/Request
- `New Hiring Requests` — Recruitment/New Hiring Requests

**Artifact counts:** dependency=3, menu=3, view=4

### 2. `prosys_approval_request`

**Display Name:** Prosys Approval Request Customization

**ما هو:** تخصيص منظومة الموافقات وربطها بعدة أجزاء HR، مع Employee Fields History وتقارير خطابات الموافقة.

**Direct Dependencies:** `approvals`, `base_address_extended`, `documents`, `hr`, `hr_employee_profile`, `hr_end_service_benefits`, `hr_expense`, `hr_holidays`, `hr_payroll`, `l10n_sa_hr_payroll`, `prosys_gr_transaction`, `prosys_hr_contract_custom`, `report_qweb_pdf_watermark`

**النماذج/الأهداف الظاهرة في الـartifacts:** `approval.category`, `approval.request`, `employee.fields.history`, `employee.fields.history.wizard`, `hr.employee`, `res.country`

**أهم القوائم (Menus):**
- `Employee Fields History Report` — Employees/Reporting/Employee Fields History Report

**التقارير:**
- `Arabic Letter` → `approval.request`
- `Both Letter` → `approval.request`
- `English Letter` → `approval.request`
- `Employee Fields History Report` → `employee.fields.history.wizard`

**Artifact counts:** dependency=13, menu=1, report=4, view=14

### 3. `prosys_employee_history_calender`

**Display Name:** Employee History Calendar

**ما هو:** سجل/تقويم تاريخ الموظف، مع ربط مباشر بـ`hr.employee`.

**Direct Dependencies:** `hr`, `resource`

**النماذج/الأهداف الظاهرة في الـartifacts:** `employee.history.calender`, `hr.employee`

**Artifact counts:** dependency=2, view=2

### 4. `prosys_expenses`

**Display Name:** Prosys Expenses

**ما هو:** تخصيص نموذج المصروفات `hr.expense`.

**Direct Dependencies:** `hr_expense`

**النماذج/الأهداف الظاهرة في الـartifacts:** `hr.expense`

**Artifact counts:** dependency=1, view=1

### 5. `prosys_gr_transaction`

**Display Name:** Prosys GR Transaction

**ما هو:** إدارة GR Transactions وربطها بالموظف، مع تقرير GR Transaction.

**Direct Dependencies:** `base`, `hr`, `hr_payroll`

**النماذج/الأهداف الظاهرة في الـartifacts:** `gr.transaction`, `hr.employee`

**أهم القوائم (Menus):**
- `Transactions` — GR Transactions/Transactions
- `GR Transactions` — GR Transactions

**التقارير:**
- `GR Transaction` → `gr.transaction`

**Artifact counts:** dependency=3, menu=2, report=1, view=4

### 6. `prosys_hr_appraisal`

**Display Name:** HR - Employee Evaluation & Appraisal

**ما هو:** التقييمات السنوية والتقييمات/الأسئلة/المعايير والنتائج.

**Direct Dependencies:** `base`, `hr`, `mail`

**النماذج/الأهداف الظاهرة في الـartifacts:** `annual.evaluation`, `annual.evaluation.result`, `appraisal.request`, `evaluation.answer`, `evaluation.category`, `evaluation.criteria`, `evaluation.question`, `evaluation.template`, `evaluation.wizard`, `hr.department`, `hr.employee`

**أهم القوائم (Menus):**
- `Annual Evaluations` — Employee Evaluation/Annual Evaluations
- `Annual Evaluations` — Employee Evaluation/Annual Evaluations/Annual Evaluations
- `Annual Results` — Employee Evaluation/Annual Evaluations/Annual Results
- `Question Categories` — Employee Evaluation/Configuration/Question Categories
- `Evaluation Criteria` — Employee Evaluation/Configuration/Evaluation Criteria
- `Evaluation Questions` — Employee Evaluation/Configuration/Evaluation Questions
- `Evaluation Templates` — Employee Evaluation/Configuration/Evaluation Templates
- `Evaluation Tools` — Employee Evaluation/Appraisals/Evaluation Tools
- `Appraisals` — Employee Evaluation/Appraisals
- `All Appraisals` — Employee Evaluation/Appraisals/All Appraisals
- `Configuration` — Employee Evaluation/Configuration
- `My Appraisals` — Employee Evaluation/Appraisals/My Appraisals
- `Employee Evaluation` — Employee Evaluation

**Artifact counts:** dependency=3, menu=13, view=22

### 7. `prosys_hr_contract_custom`

**Display Name:** Prosys HR Contract Custom

**ما هو:** تخصيص العقد/نسخة العقد وربطه ببيانات التوظيف وContract Total.

**Direct Dependencies:** `hr`, `l10n_sa_hr_payroll`, `prosys_hr_contract_total`, `prosys_hr_recruitment_custom`

**النماذج/الأهداف الظاهرة في الـartifacts:** `hr.employee`, `hr.version`

**Artifact counts:** dependency=4, view=2

### 8. `prosys_hr_contract_total`

**Display Name:** Prosys HR Contract Total

**ما هو:** تخصيص بيانات إجمالي العقد والبدلات على `hr.employee` و`hr.version` و`hr.version.allowance`.

**Direct Dependencies:** `hr`, `hr_payroll`, `l10n_sa_hr_payroll`

**النماذج/الأهداف الظاهرة في الـartifacts:** `hr.employee`, `hr.version`, `hr.version.allowance`

**Artifact counts:** dependency=3, view=3

### 9. `prosys_hr_recruitment_custom`

**Display Name:** Prosys HR Recruitment Custom

**ما هو:** تخصيص التوظيف/المتقدم وربط Job Offer بالمنظومة.

**Direct Dependencies:** `base`, `hr`, `hr_end_service_benefits`, `hr_recruitment`, `prosys_advance_recruitment`

**النماذج/الأهداف الظاهرة في الـartifacts:** `hr.applicant`, `hr.employee`, `res.config.settings`

**التقارير:**
- `Job Offer` → `hr.applicant`

**Artifact counts:** dependency=5, report=1, view=5

### 10. `prosys_warning_letter`

**Display Name:** Prosys Warning Letter

**ما هو:** خطابات الإنذار وأنواعها فوق منظومة Disciplinary.

**Direct Dependencies:** `base`, `hr`, `hr_payroll`, `mail`, `nthub_hr_disciplinary`

**النماذج/الأهداف الظاهرة في الـartifacts:** `warning.letter`, `warning.type`

**أهم القوائم (Menus):**
- `Warning` — Disciplinary/Warning
- `Warning Letters` — Disciplinary/Warning/Warning Letters
- `Warning Types` — Disciplinary/Warning/Warning Types

**التقارير:**
- `Warning Letter` → `warning.letter`

**Artifact counts:** dependency=5, menu=3, report=1, view=7

### 11. `nthub_hr_disciplinary`

**Display Name:** Employee Disciplinary Management

**ما هو:** الإدارة التأديبية، بما في ذلك disciplinary actions/categories وربطها بالموظف وpayslip.

**Direct Dependencies:** `base`, `hr`, `hr_payroll`, `mail`, `prosys_hr_contract_total`, `sharif_hr`

**النماذج/الأهداف الظاهرة في الـartifacts:** `disciplinary.action`, `discipline.category`, `hr.employee`, `hr.payslip`

**أهم القوائم (Menus):**
- `Disciplinary` — Disciplinary
- `Disciplinary Action` — Disciplinary/Disciplinary Action
- `Discipline Category` — Disciplinary/Discipline Category

**Artifact counts:** dependency=6, menu=3, view=8

### 12. `sharif_hr`

**Display Name:** Employee Attachments

**ما هو:** تخصيصات على الموظف/الإجازات/نسخة العقد؛ والـartifacts تتضمن employee attachments وتعديلات على هذه النماذج.

**Direct Dependencies:** `base`, `hr`, `hr_holidays`, `prosys_gr_transaction`

**النماذج/الأهداف الظاهرة في الـartifacts:** `hr.employee`, `hr.leave`, `hr.leave.type`, `hr.version`

**Artifact counts:** dependency=4, view=5

### 13. `sc_hr_mobile_connector`

**Display Name:** Prosys HR Mobile App Connector

**ما هو:** طبقة تكامل للـMobile App تعتمد على عدة موديولات HR مخصصة وموديولات Odoo.

**Direct Dependencies:** `base`, `bi_hr_overtime_request`, `hr_attendance`, `hr_timeoff`, `nthub_hr_disciplinary`, `petty_cash_management`, `prosys_expenses`, `prosys_hr_appraisal`, `prosys_warning_letter`, `rm_hr_attendance_sheet`, `sharif_hr`, `web`

**النماذج/الأهداف الظاهرة في الـartifacts:** `hr.device`, `res.config.settings`

**أهم القوائم (Menus):**
- `Device Information` — Settings/Users & Companies/Device Information

**Artifact counts:** dependency=12, menu=1, view=4

### 14. `rm_hr_attendance_sheet`

**Display Name:** HR Attendance Sheet And Policies

**ما هو:** Attendance Sheets وAttendance Policies وقواعد التأخير/الإضافي/الغياب والتحذيرات.

**Direct Dependencies:** `account`, `base`, `hr`, `hr_attendance`, `hr_holidays`, `hr_payroll`, `prosys_employee_history_calender`, `prosys_hr_contract_total`

**النماذج/الأهداف الظاهرة في الـartifacts:** `account.move`, `attendance.sheet`, `attendance.sheet.batch`, `attendance.sheet.line`, `attendance.sheet.line.change`, `hr.absence.rule`, `hr.attendance`, `hr.attendance.checker`, `hr.attendance.policy`, `hr.attendance.warning`, `hr.diff.rule`, `hr.employee`, `hr.late.rule`, `hr.overtime.rule`, `hr.public.holiday`, `hr.version`

**أهم القوائم (Menus):**
- `Attendance Sheets` — Attendances/Attendance Sheets
- `Public Holidays` — Time Off/Public Holidays/Public Holidays
- `Absence Rules` — Attendances/Attendance Sheet Setting/Attendance Rules/Absence Rules
- `Attendance Checker` — Attendances/Attendance Checker
- `Attendances Policies` — Attendances/Attendance Sheet Setting/Attendances Policies
- `Attendance Rules` — Attendances/Attendance Sheet Setting/Attendance Rules
- `Attendance sheet Batches` — Attendances/Attendance Sheets/Attendance sheet Batches
- `Attendance Sheet Setting` — Attendances/Attendance Sheet Setting
- `Attendance Warnings` — Attendances/Attendance Sheets/Attendance Warnings
- `Difference Time Rules` — Attendances/Attendance Sheet Setting/Attendance Rules/Difference Time Rules
- `Late In Rules` — Attendances/Attendance Sheet Setting/Attendance Rules/Late In Rules
- `OverTime Rules` — Attendances/Attendance Sheet Setting/Attendance Rules/OverTime Rules
- `Public Holidays` — Time Off/Public Holidays
- `Attendance sheets` — Attendances/Attendance Sheets/Attendance sheets

**Artifact counts:** dependency=8, menu=14, view=31

### 15. `bi_hr_overtime_request`

**Display Name:** Employee Overtime Request and Payroll in Odoo

**ما هو:** طلبات العمل الإضافي، بما فيها الطلبات المتعددة وطلبات الاعتماد والإعدادات.

**Direct Dependencies:** `base`, `hr`, `hr_payroll`, `hr_payroll_account`

**النماذج/الأهداف الظاهرة في الـartifacts:** `multiple.overtime.request`, `overtime.config`, `overtime.request`, `reject.reason.wizard`

**أهم القوائم (Menus):**
- `Overtime Request` — Employees/Overtime/Overtime Request
- `Configuration` — Employees/Overtime/Configuration
- `Overtime Request To Approve By Department` — Employees/Overtime/Overtime Request To Approve By Department
- `Overtime Request To Approve` — Employees/Overtime/Overtime Request To Approve
- `Multiple Overtime Request` — Employees/Overtime/Multiple Overtime Request
- `Multiple Overtime Request To Approve By Department` — Employees/Overtime/Multiple Overtime Request To Approve By Department
- `Multiple Overtime Request To Approve` — Employees/Overtime/Multiple Overtime Request To Approve
- `Overtime` — Employees/Overtime

**Artifact counts:** dependency=4, menu=8, view=6

### 16. `dev_hr_loan`

**Display Name:** Employee Loan Management, HR Loan Process Employee

**ما هو:** إدارة قروض الموظفين والأقساط والمستندات والاستيراد والتحليلات.

**Direct Dependencies:** `account`, `base`, `hr`, `hr_payroll`, `hr_work_entry`

**النماذج/الأهداف الظاهرة في الـartifacts:** `dev.loan.document`, `dev.skip.installment`, `employee.loan`, `employee.loan.type`, `hr.employee`, `hr.payslip`, `import.loan`, `import.logs`, `installment.analytic.line.view`, `installment.line`, `installment.multiselect.wizard`, `reject.reason.wizard.loan`, `res.company`

**أهم القوائم (Menus):**
- `Loan Dashboard` — Employees/Loans & Advanced Housing/Loan Dashboard
- `Loan Document` — Employees/Loans & Advanced Housing/Loan Document
- `Employee Loan & Advanced Housing` — Employees/Loans & Advanced Housing/Employee Loan & Advanced Housing
- `Loan Type` — Employees/Loans & Advanced Housing/Loan Type
- `Import Loan` — Employees/Loans & Advanced Housing/Import Loan
- `Loan Analysis Report` — Employees/Loans & Advanced Housing/Loan Analysis Report
- `Loans & Advanced Housing` — Employees/Loans & Advanced Housing
- `Skip Installment` — Employees/Skip Installment
- `Skip Installment` — Employees/Skip Installment/Skip Installment

**التقارير:**
- `Loan Report` → `employee.loan`

**Artifact counts:** dependency=5, menu=9, report=1, view=28

### 17. `petty_cash_management`

**Display Name:** Petty Cash Management

**ما هو:** إدارة Petty Cash وربطها بالمصروفات والحركات المحاسبية.

**Direct Dependencies:** `account`, `base`, `base_automation`, `hr`, `hr_expense`, `project`

**النماذج/الأهداف الظاهرة في الـartifacts:** `account.journal`, `account.move`, `account.payment`, `hr.expense`, `petty.cash`, `petty.cash.adj`, `petty.cash.type`, `petty.pay.invoice.wizard`, `petty.pay.wizard`, `petty.reamount.wizard`

**أهم القوائم (Menus):**
- `Petty Cash` — Invoicing/Petty Cash/Petty Cash/Petty Cash
- `Petty Cash Adjustment` — Invoicing/Petty Cash/Petty Cash/Petty Cash Adjustment
- `Petty Cash` — Invoicing/Petty Cash/Petty Cash
- `Petty Cash Types` — Invoicing/Petty Cash/Petty Cash Configuration/Petty Cash Types
- `Petty Cash Configuration` — Invoicing/Petty Cash/Petty Cash Configuration
- `Petty Cash` — Invoicing/Petty Cash

**Artifact counts:** dependency=6, menu=6, view=13

### 18. `hr_employee_move`

**Display Name:** hr_employee_move

**ما هو:** حركات/نقل الموظفين مع شاشة Movement ورفض الطلبات.

**Direct Dependencies:** `base`, `hr`, `prosys_employee_history_calender`

**النماذج/الأهداف الظاهرة في الـartifacts:** `employee.movement`, `hr.employee`, `rejection.wizard`

**أهم القوائم (Menus):**
- `Employee Movement` — Employees/Employee Movement

**Artifact counts:** dependency=3, menu=1, view=5

### 19. `hr_employee_profile`

**Display Name:** Employee Profile

**ما هو:** تخصيص نموذج وبحث الموظف.

**Direct Dependencies:** `account`, `base`, `hr`, `hr_expense`

**النماذج/الأهداف الظاهرة في الـartifacts:** `hr.employee`

**Artifact counts:** dependency=4, view=2

### 20. `hr_employee_vacation_salary`

**Display Name:** HR - Employee Vacation Salary

**ما هو:** طلبات Vacation Salary وإعدادات طرق الدفع وتقرير Vacation Salary.

**Direct Dependencies:** `hr_holidays`, `hr_payroll`, `hr_work_entry_enterprise`, `prosys_hr_contract_total`

**النماذج/الأهداف الظاهرة في الـartifacts:** `employee.vacation.salary`, `employee.vacation.salary.config`, `hr.leave.type`

**أهم القوائم (Menus):**
- `Vacation Salary` — Payroll/Vacation Salary
- `Payment Method` — Payroll/Vacation Salary/Configuration/Payment Method
- `Configuration` — Payroll/Vacation Salary/Configuration
- `Requests` — Payroll/Vacation Salary/Requests

**التقارير:**
- `Vacation Salary Report` → `employee.vacation.salary`

**Artifact counts:** dependency=4, menu=4, report=1, view=8

### 21. `hr_employee_working_hours`

**Display Name:** Employee Working Hours

**ما هو:** إدارة Employee Working Hours.

**Direct Dependencies:** `base`, `hr`, `prosys_employee_history_calender`

**النماذج/الأهداف الظاهرة في الـartifacts:** `employee.working.hours`, `hr.employee`

**أهم القوائم (Menus):**
- `Employee Working Hours` — Employees/Employee Working Hours

**Artifact counts:** dependency=3, menu=1, view=3

### 22. `hr_end_service_benefits`

**Display Name:** Employee End Of Service Rewards [ESR]

**ما هو:** حساب/طلبات مكافأة نهاية الخدمة، التسويات والتقارير.

**Direct Dependencies:** `account`, `account_accountant`, `hr_holidays`, `hr_payroll`, `l10n_sa_hr_payroll`, `portal`, `prosys_hr_contract_total`, `web`

**النماذج/الأهداف الظاهرة في الـartifacts:** `hr.benefit.settlement`, `hr.employee`, `hr.end.service.benefit`, `hr.end.service.benefit.type`, `hr.leave.type`, `mn.end.service.report`, `res.company`, `res.config.settings`

**أهم القوائم (Menus):**
- `End Of Service Reward Requests` — Employees/End Of Service Rewards/End Of Service Reward Requests
- `End Of Service Rewards` — Employees/End Of Service Rewards
- `ES Settings` — Employees/Configuration/ES Settings
- `End of Service Reward Reasons` — Employees/Configuration/End of Service Reward Reasons
- `EOS Report` — Employees/End Of Service Rewards/EOS Report

**التقارير:**
- `End of Service Settlement` → `hr.end.service.benefit`
- `End of Service Statement` → `hr.end.service.benefit`
- `EOS Report` → `mn.end.service.report`

**Artifact counts:** dependency=8, menu=5, report=3, view=18

### 23. `hr_leaves`

**Display Name:** HR Leaves

**ما هو:** تخصيص نماذج الإجازات وتخصيصات الإجازات.

**Direct Dependencies:** `calendar`, `hr_holidays`, `hr_payroll`

**النماذج/الأهداف الظاهرة في الـartifacts:** `hr.leave`, `hr.leave.allocation`

**Artifact counts:** dependency=3, view=2

### 24. `hr_timeoff`

**Display Name:** HR Holidays

**ما هو:** Delegation/Delegate Approvals في منظومة Time Off.

**Direct Dependencies:** `hr_holidays`

**النماذج/الأهداف الظاهرة في الـartifacts:** `employee.delegate.approval`, `hr.leave`, `hr.leave.type`

**أهم القوائم (Menus):**
- `Delegate Approvals` — Time Off/Delegate Approvals

**Artifact counts:** dependency=1, menu=1, view=3

### 25. `report_qweb_pdf_watermark`

**Display Name:** Pdf watermark

**ما هو:** إضافة Watermark إلى إعدادات/تقارير PDF.

**Direct Dependencies:** `web`

**النماذج/الأهداف الظاهرة في الـartifacts:** `ir.actions.report`, `res.company`

**Artifact counts:** dependency=1, view=2

### 26. `studio_customization`

**Display Name:** Studio customizations

**ما هو:** تخصيص Studio فعلي على قائمة `hr.employee`.

**Direct Dependencies:** `web_studio`

**النماذج/الأهداف الظاهرة في الـartifacts:** `hr.employee`

**Artifact counts:** dependency=1, view=1

## شبكة الاعتماد بين الموديولات المخصصة

الأسهم التالية تعني: **الموديول على اليسار يعتمد مباشرة على الموديول على اليمين**.

- `prosys_approval_request` → `hr_employee_profile`
- `prosys_approval_request` → `hr_end_service_benefits`
- `prosys_approval_request` → `prosys_gr_transaction`
- `prosys_approval_request` → `prosys_hr_contract_custom`
- `prosys_approval_request` → `report_qweb_pdf_watermark`
- `prosys_hr_contract_custom` → `prosys_hr_contract_total`
- `prosys_hr_contract_custom` → `prosys_hr_recruitment_custom`
- `prosys_hr_recruitment_custom` → `hr_end_service_benefits`
- `prosys_hr_recruitment_custom` → `prosys_advance_recruitment`
- `prosys_warning_letter` → `nthub_hr_disciplinary`
- `nthub_hr_disciplinary` → `prosys_hr_contract_total`
- `nthub_hr_disciplinary` → `sharif_hr`
- `sharif_hr` → `prosys_gr_transaction`
- `sc_hr_mobile_connector` → `bi_hr_overtime_request`
- `sc_hr_mobile_connector` → `hr_timeoff`
- `sc_hr_mobile_connector` → `nthub_hr_disciplinary`
- `sc_hr_mobile_connector` → `petty_cash_management`
- `sc_hr_mobile_connector` → `prosys_expenses`
- `sc_hr_mobile_connector` → `prosys_hr_appraisal`
- `sc_hr_mobile_connector` → `prosys_warning_letter`
- `sc_hr_mobile_connector` → `rm_hr_attendance_sheet`
- `sc_hr_mobile_connector` → `sharif_hr`
- `rm_hr_attendance_sheet` → `prosys_employee_history_calender`
- `rm_hr_attendance_sheet` → `prosys_hr_contract_total`
- `hr_employee_move` → `prosys_employee_history_calender`
- `hr_employee_vacation_salary` → `prosys_hr_contract_total`
- `hr_employee_working_hours` → `prosys_employee_history_calender`
- `hr_end_service_benefits` → `prosys_hr_contract_total`

### رسم مبسط

```text
prosys_advance_recruitment
        ↑
prosys_hr_recruitment_custom
        ↑
prosys_hr_contract_custom
        ↑
prosys_hr_contract_total
        ↑
  ┌─────┼───────────────┬────────────────┐
  │     │               │                │
  │     │               │                └─ hr_end_service_benefits
  │     │               └────────────────── rm_hr_attendance_sheet
  │     └───────────────────────────────── nthub_hr_disciplinary
  │
  └─ hr_employee_vacation_salary

sharif_hr → prosys_gr_transaction
nthub_hr_disciplinary → sharif_hr
prosys_warning_letter → nthub_hr_disciplinary

prosys_approval_request
   ├─ hr_employee_profile
   ├─ hr_end_service_benefits
   ├─ prosys_gr_transaction
   ├─ prosys_hr_contract_custom
   └─ report_qweb_pdf_watermark

sc_hr_mobile_connector
   ├─ bi_hr_overtime_request
   ├─ hr_timeoff
   ├─ nthub_hr_disciplinary
   ├─ petty_cash_management
   ├─ prosys_expenses
   ├─ prosys_hr_appraisal
   ├─ prosys_warning_letter
   ├─ rm_hr_attendance_sheet
   └─ sharif_hr

prosys_employee_history_calender
        ↑
   ┌────┴───────────────┐
   │                    │
hr_employee_move   hr_employee_working_hours
   │
   └──────────────→ rm_hr_attendance_sheet
```

## نقاط التقاطع داخل `hr.employee`

وفق `field_catalog.csv`، نموذج `hr.employee` يحتوي روابط مباشرة مع أجزاء متعددة من هذه المنظومة، منها:

- `version_id`, `current_version_id`, `version_ids`
- `attendance_ids`, `overtime_ids`, `ruleset_id`
- `appraisal_request_ids`
- `slip_ids`
- `history_calendar_ids`
- `gr_transaction_ids`
- `employee_attachment_ids`
- `discipline_count`
- `termination_approval_count`
- `leave_ids`

كما توجد حقول مخصصة سعودية/مالية مثل:

- `l10n_sa_employee_code`
- `l10n_sa_housing_allowance`
- `l10n_sa_transportation_allowance`
- `l10n_sa_other_allowances`
- `gosi_deduction`
- `gosi_type`
- `gosi_rate`

هذا يجعل `hr.employee` نقطة تقاطع مركزية بين الموظف والعقد والـPayroll والحضور والإجازات والتقييم والانضباط وGR Transactions والمرفقات.

## أهم الموديولات من ناحية التشابك

### الأعلى تأثيرًا/ترابطًا

- `prosys_hr_contract_total` — 3 dependency مباشرة، و3 نموذج/هدف ظاهر في الـartifacts.
- `prosys_hr_contract_custom` — 4 dependency مباشرة، و2 نموذج/هدف ظاهر في الـartifacts.
- `prosys_hr_recruitment_custom` — 5 dependency مباشرة، و3 نموذج/هدف ظاهر في الـartifacts.
- `prosys_approval_request` — 13 dependency مباشرة، و6 نموذج/هدف ظاهر في الـartifacts.
- `rm_hr_attendance_sheet` — 8 dependency مباشرة، و16 نموذج/هدف ظاهر في الـartifacts.
- `sc_hr_mobile_connector` — 12 dependency مباشرة، و2 نموذج/هدف ظاهر في الـartifacts.

### موديولات أعمال HR الرئيسية

- `nthub_hr_disciplinary`
- `prosys_hr_appraisal`
- `prosys_gr_transaction`
- `prosys_warning_letter`
- `bi_hr_overtime_request`
- `dev_hr_loan`
- `hr_employee_vacation_salary`
- `hr_end_service_benefits`

## ملاحظات منهجية مهمة

1. **مخصص** هنا تعني موديولًا إضافيًا/Extension كما ظهر في قائمة البيئة المخصصة التي تم تحليلها؛ `studio_customization` حالة مختلفة لأنه تخصيص Odoo Studio.
2. بعض الموديولات المخصصة تعتمد على موديولات Odoo القياسية، بينما بعضها يعتمد أيضًا على موديولات Custom أخرى.
3. وجود موديول في هذه القائمة لا يعني وحده أنه يجب أن يدخل في أول Agent أو أول عملية أتمتة.
4. لا يجوز اعتبار `hr.employee` ككيان معزول في هذه البيئة؛ الـfield catalog يثبت وجود نقاط ربط مع العقد والحضور والرواتب والإجازات والتقييم والانضباط وغيرها.
5. العلاقات الواردة هنا هي علاقات مثبتة من البيانات المتاحة، وليست افتراضًا معماريًا عن كيفية تصميم Odoo.

## المصادر

- `installed_modules.csv` — قائمة الموديولات المثبتة وبياناتها الأساسية.
- `installed_modules_detailed.csv` — Dependencies + Menus + Views + Reports.
- `module_artifacts.csv` — تفاصيل الـartifacts لكل موديول.
- `field_catalog.csv` — الحقول والنماذج وخصائصها.
