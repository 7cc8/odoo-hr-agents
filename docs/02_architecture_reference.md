# المسار B — مرجع معماري (لا يُنفذ الآن)

هذا الملف يوثّق خريطة الموديولات المكتشفة من فحص الكتالوج الفعلي (194 موديول)،
كطبقات هرمية متشابكة (DAG)، لا كحزم متوازية مستقلة.

## عائلات التخصيص المكتشفة (multi-source)

| المصدر (prefix) | عدد الموديولات | أمثلة |
|---|---|---|
| prosys | 10 | contract_total, contract_custom, gr_transaction, warning_letter, hr_appraisal, approval_request |
| nthub | 1 | hr_disciplinary |
| sharif | 1 | hr (attachments) |
| sc | 1 | hr_mobile_connector |
| rm | 1 | hr_attendance_sheet |
| bi | 1 | hr_overtime_request |
| dev | 1 | hr_loan |
| petty | 1 | cash_management |

بالإضافة إلى `studio_customization` و `webstudio` (تعديلات عبر Odoo Studio، غالباً غير موثقة بكود).

**الأثر**: البيئة متراكمة من 7-8 مصادر تخصيص مختلفة عبر فترة زمنية، وليست بيئة Odoo HR نظيفة
عليها موديول إضافي أو اثنين. هذا يرفع احتمالية وجود side effects غير موثقة عند أي `create()`
على `hr.employee`.

## الطبقات الهرمية (تصنيف مصحح)

```
Layer 0 — Core
  hr, hr_holidays, hr_attendance, hr_payroll

Layer 1 — Localization / Mid
  l10n_sa_hr_payroll, prosys_hr_contract_total, sharif_hr, prosys_gr_transaction

Layer 2 — Domain Extensions
  prosys_hr_contract_custom, hr_end_service_benefits, nthub_hr_disciplinary,
  prosys_warning_letter, prosys_hr_appraisal, hr_employee_profile, rm_hr_attendance_sheet

Layer 3 — Aggregators (كثيفة الاعتماديات، أصعب نقطة بداية)
  prosys_approval_request  → يعتمد على: hr, hr_endservice_benefits, hr_expense,
                              hr_holidays, hr_payroll, l10n_sa_hr_payroll,
                              prosys_gr_transaction, prosys_hr_contract_custom
  sc_hr_mobile_connector    → يعتمد على: bi_hr_overtime_request, hr_attendance,
                              hr_timeoff, nthub_hr_disciplinary, petty_cash_management,
                              prosys_expenses, prosys_hr_appraisal, prosys_warning_letter,
                              rm_hr_attendance_sheet, sharif_hr
```

## موديولات ترث مباشرة على hr.employee.form أو hr.payslip.form

هذه الموديولات تضيف/تعدّل حقولاً أو سلوكاً على نماذج HR الأساسية عبر inherit،
وهي مصدر الخطر الرئيسي لأي عملية create() غير محسوبة:

- `nthub_hr_disciplinary` — يرث `hr.employee.form` و`hr.payslip.form`
- `prosys_approval_request` — يرث `hr.employee.form`
- `prosys_employee_history_calender` — يرث `hr.employee.form`
- `hr_employee_profile` — يرث `hr.employee.form`
- `documents_hr` — يرث `hr.employee.form` و`hr.employee.public.form`
- `hr_attendance` — يرث `hr.employee.form`

## توصية لبناء الوكلاء المستقبليين (المسار C)

- ابدأ بالطبقة الأقرب لبيانات الموظف الأساسية (Layer 0/1)، مثل وكيل "العقود" (Contract)
  الذي يقرأ من Payroll مباشرة.
- **لا تبدأ** بالطبقات التجميعية (`sc_hr_mobile_connector`, `prosys_approval_request`)
  لأنها الأعقد تقنياً بسبب كثرة اعتمادياتها المتشابكة.
- كل وكيل يستهدف نموذجاً يرثه موديول مخصص، يجب أن يتضمن خطوة تحقق من fields_get()
  قبل أي كتابة، وليس الاعتماد على قراءة الكتالوج فقط.

## ملاحظة حول حقل exclusions

الكتالوج الأصلي أظهر حقل `exclusions` فارغاً بالكامل لكل الـ 194 موديول. هذا لا يُعتبر
تأكيداً كافياً على غياب أي module exclusions في البيئة. يجب التحقق عبر
`fields_get()` على `ir.module.module` (انظر `scripts/01_test_create_employee.py`،
دالة `inspect_module_exclusions`) قبل اعتماد هذا الحقل كجزء موثوق من أي تحليل مستقبلي.
