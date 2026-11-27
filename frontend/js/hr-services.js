(() => {
  "use strict";
  const domains = {
    leaves: "الإجازات", attendance: "الحضور والانصراف", contracts: "العقود",
    payroll: "الرواتب وحماية الأجور", recruitment: "التوظيف", appraisals: "تقييم الأداء",
    loans: "السلف", expenses: "المصروفات", letters: "الخطابات", warnings: "الإنذارات",
    disciplinary: "الجزاءات", eos: "نهاية الخدمة", gr: "المعاملات الحكومية",
    analytics: "المؤشرات", alerts: "الوثائق المنتهية", musleh: "معالجة ملفات الاستيراد"
  };
  const actions = {
    types: "الأنواع المتاحة", summary: "ملخص الموظف", employee: "سجل الموظف",
    "dry-run": "فحص طلب جديد", categories: "التصنيفات", rules: "قواعد الاستحقاق",
    "check-in": "تسجيل دخول الآن", "check-out": "تسجيل خروج الآن", reasons: "أسباب انتهاء الخدمة",
    "common-transactions": "المعاملات الشائعة", "ratings-guide": "درجات التقييم", jobs: "الوظائف",
    stages: "مراحل التوظيف", applicants: "المتقدمون", structures: "هياكل الرواتب",
    "wps-sif": "توليد ملف حماية الأجور", dashboard: "ملخص المؤشرات", workforce: "القوى العاملة",
    operations: "العمليات", financial: "المؤشرات المالية", compliance: "الامتثال",
    recruitment: "مؤشرات التوظيف", "simulate-saudization": "محاكاة التوطين", levels: "درجات الإنذار",
    expiries: "الوثائق المشمولة", scan: "فحص تواريخ الانتهاء", html: "تنزيل نسخة HTML", pdf: "تنزيل التقرير",
    "diagnose-row": "فحص صف من الملف", "heal-batch": "فحص دفعة مستوردة", "recover-submission": "التحقق من تسجيل موظف"
  };
  const labels = {
    employee_id:"رقم الموظف",company_id:"رقم المنشأة",employee_name:"اسم الموظف",applicant_id:"رقم المتقدم",
    holiday_status_id:"رقم نوع الإجازة",request_date_from:"بداية الإجازة",request_date_to:"نهاية الإجازة",
    reason:"السبب",occasion_type:"نوع المناسبة",date:"التاريخ",check_in:"وقت الدخول",check_out:"وقت الخروج",
    is_ramadan:"خلال رمضان",is_muslim:"الموظف مسلم",basic_wage:"الراتب الأساسي",gross_wage:"الأجر الإجمالي",
    discipline_date:"تاريخ الجزاء",discipline_reason:"سبب الجزاء",number_of_days:"عدد الأيام",amount:"المبلغ",
    category_type:"نوع التصنيف",discovery_date:"تاريخ اكتشاف المخالفة",investigation_end_date:"تاريخ انتهاء التحقيق",
    daily_wage:"الأجر اليومي",explanation:"التوضيح",manager_response:"رد المدير",action_type_id:"رقم نوع الإجراء",
    monthly_wage:"الأجر الشهري",settlement_date:"تاريخ التسوية",hiring_date:"تاريخ التعيين",service_years:"سنوات الخدمة",
    contract_type:"نوع العقد",is_resignation:"استقالة",resignation_reason:"سبب الاستقالة",is_unlawful_termination:"إنهاء غير مشروع",
    remaining_contract_months:"الأشهر المتبقية",agreed_compensation:"التعويض المتفق عليه",unused_leave_days:"رصيد الإجازات",
    unpaid_salary_days:"أيام الأجر المستحقة",other_deductions_amount:"الاستقطاعات الأخرى",explicit_is_saudi:"سعودي الجنسية",
    transaction:"المعاملة",transaction_type:"نوع المعاملة",responsible_party:"الطرف المسؤول",company_percentage:"نسبة الشركة",
    employee_percentage:"نسبة الموظف",transaction_date:"تاريخ المعاملة",description:"الوصف",appraisal_type:"نوع التقييم",
    year:"السنة",kpi_score:"درجة المؤشرات",competency_score:"درجة الكفاءات",kpi_weight:"وزن المؤشرات",
    competency_weight:"وزن الكفاءات",manager_id:"رقم المدير",manager_name:"اسم المدير",evaluation_date:"تاريخ التقييم",
    notes:"ملاحظات",loan_amount:"مبلغ السلفة",term:"المدة",installment_amount:"قيمة القسط",start_date:"تاريخ البدء",
    explicit_wage:"الأجر",candidate_name:"اسم المتقدم",job_id:"رقم الوظيفة",is_saudi:"سعودي الجنسية",
    id_number:"رقم الهوية",passport_number:"رقم الجواز",email:"البريد الإلكتروني",phone:"الهاتف",
    salary_expected:"الراتب المتوقع",salary_proposed:"الراتب المقترح",housing_allowance:"بدل السكن",
    transportation_allowance:"بدل النقل",contract_status:"حالة العقد",duration_of_contract:"مدة العقد",
    availability:"موعد التوفر",applicant_notes:"ملاحظات المتقدم",job_title_override:"المسمى الوظيفي",
    stage_id:"رقم المرحلة",state:"الحالة",other_allowances:"البدلات الأخرى",date_start:"تاريخ البداية",date_end:"تاريخ النهاية",
    trial_date_end:"نهاية التجربة",contract_type_id:"رقم نوع العقد",gosi_deduction:"استقطاع التأمينات",
    date_from:"من تاريخ",date_to:"إلى تاريخ",loan_installment:"قسط السلفة",discipline_amount:"قيمة الجزاء",
    other_deductions:"استقطاعات أخرى",struct_id:"رقم هيكل الراتب",employer_cr:"السجل التجاري",bank_code:"رمز البنك",
    payslips_data:"ملف بيانات المسيرات (JSON)",batch_reference:"مرجع الدفعة",saudi_hires:"التعيينات السعودية",
    expat_hires:"التعيينات غير السعودية",letter_type:"نوع الخطاب",recipient:"المستلم",purpose:"الغرض",language:"اللغة",
    include_salary:"تضمين الراتب",chamber_of_commerce_stamp:"تصديق الغرفة التجارية",bank_name:"اسم البنك",
    bank_account_number:"رقم الحساب",category_id:"رقم التصنيف",warning_level:"درجة الإنذار",
    violation_description:"وصف المخالفة",violation_date:"تاريخ المخالفة",has_deduction:"يشمل خصماً",
    deduction_days:"أيام الخصم",deduction_amount:"مبلغ الخصم",expense_category:"فئة المصروف",total_amount:"المبلغ الإجمالي",
    expense_date:"تاريخ المصروف",includes_vat:"يشمل الضريبة",product_id:"رقم المنتج",max_days:"المدة بالأيام",
    category:"الفئة",severity:"الأولوية",department:"القسم",limit:"عدد النتائج",request_id:"رقم الطلب",
    letter_id:"رقم الإنذار",expense_id:"رقم المطالبة",row:"ملف بيانات الصف (JSON)",rows:"ملف الصفوف (JSON)",
    validation_result:"ملف نتيجة الفحص (JSON)",validation_results:"ملف نتائج الفحص (JSON)",auto_repair:"اقتراح تصحيح تلقائي",
    run_id:"رقم عملية الاستيراد",executor:"اسم المنفذ",confirmation_text:"اكتب تأكيد لاعتماد التنفيذ",
    user_confirmation_text:"اكتب تأكيد لاعتماد التنفيذ",name:"الاسم",id:"الرقم",summary:"الملخص",result:"النتيجة",
    count:"العدد",errors:"الأخطاء",warnings:"التنبيهات",types:"الأنواع",message_ar:"النتيجة",status:"الحالة",
    department_name:"القسم",remaining_days:"الأيام المتبقية",consumed_days:"الأيام المستخدمة",dry_run:"نتيجة الفحص",
    is_valid:"اجتاز الفحص",can_proceed:"متاح للاعتماد",name_ar:"الاسم بالعربية",name_en:"الاسم بالإنجليزية"
  };
  const resultLabels = {
    action:"الإجراء", action_id:"رقم الإجراء", active:"نشط", active_loans_count:"السلف القائمة",
    active_occurrence_level:"درجة التكرار", allocated_days:"الأيام المخصصة", amount_sar:"المبلغ بالريال",
    applicant:"المتقدم", appraisal_id:"رقم التقييم", appraisal_title:"التقييم", approval_status:"حالة الاعتماد",
    article_77_amount:"تعويض المادة 77", article_77_explanation_ar:"تفاصيل التعويض", article_77_formula:"طريقة الحساب",
    attendance_id:"رقم سجل الحضور", attendances:"سجلات الحضور", authority:"الجهة", balance_after:"الرصيد بعد الطلب",
    balance_before:"الرصيد قبل الطلب", batch_result:"نتيجة الدفعة", by_category:"حسب الفئة", by_department:"حسب القسم",
    category_name:"الفئة", company_share_sar:"حصة المنشأة بالريال", competency_weight_pct:"وزن الكفاءات بالمئة",
    compliance_guidance_ar:"إرشادات الامتثال", compliance_notes:"ملاحظات الامتثال", compliance_rate_pct:"نسبة الامتثال",
    contract:"العقد", contract_id:"رقم العقد", contract_type_name:"نوع العقد", contract_types:"أنواع العقود",
    critical:"حرج", critical_count:"التنبيهات الحرجة", current_month_deductions_days:"أيام الخصم لهذا الشهر",
    days:"الأيام", days_remaining:"الأيام المتبقية", days_since_hiring:"الأيام منذ التعيين",
    deduction_pct_of_gross:"نسبة الاستقطاع من الإجمالي", deduction_percentage_of_wage:"نسبة الخصم من الأجر",
    department_id:"رقم القسم", discipline_deduction:"خصم الجزاءات", employee_share_sar:"حصة الموظف بالريال",
    eos_id:"رقم التسوية", eos_records_count:"عدد التسويات", estimated_eos_balance:"الرصيد التقديري لنهاية الخدمة",
    excel_row_number:"صف الملف", expat_contract_alignment:"توافق عقد غير السعودي", expired:"منتهي",
    expired_count:"عدد الوثائق المنتهية", expiry_date:"تاريخ الانتهاء", fields:"الحقول", filename:"اسم الملف",
    final_percentage:"النسبة النهائية", gender:"الجنس", generated_at_ar:"تاريخ الإصدار",
    gosi_contributory_wage:"الأجر الخاضع للاشتراك", gosi_employee_deduction:"حصة الموظف في التأمينات",
    gosi_employer_contribution:"حصة المنشأة في التأمينات", gratuity_base_amount:"المكافأة قبل تعديل الاستحقاق",
    gratuity_entitlement_ratio:"نسبة الاستحقاق", gratuity_explanation_ar:"طريقة احتساب المكافأة",
    gratuity_net_amount:"المكافأة المستحقة", in_probation_period:"ضمن فترة التجربة", is_indefinite:"غير محدد المدة",
    is_open:"مفتوح", is_saudi_only:"للسعوديين فقط", is_saudi_restricted_job:"وظيفة مقصورة على السعوديين",
    items:"النتائج", items_count:"عدد النتائج", job_title:"المسمى الوظيفي", kanban_state:"حالة المتابعة",
    kpi_weight_pct:"وزن المؤشرات بالمئة", last_gross_wage:"آخر أجر إجمالي", last_rating_ar:"آخر تقييم",
    last_score:"آخر درجة", leave_compensation_amount:"تعويض الإجازات", leave_id:"رقم الإجازة",
    leave_type_name:"نوع الإجازة", legal_article:"المادة النظامية", letter_types:"أنواع الخطابات",
    loan_deduction:"خصم السلفة", loan_id:"رقم السلفة", max_allowed_monthly_deduction:"الحد الشهري للاستقطاع",
    max_loan_deduction_percentage:"الحد الأقصى لنسبة استقطاع السلفة", max_statutory_deduction_percentage:"الحد النظامي لنسبة الخصم",
    max_total_deductions_percentage:"الحد الأقصى لنسبة الاستقطاعات", message:"الرسالة", months:"الأشهر",
    nationality:"الجنسية", nationality_text_ar:"الجنسية", net_estimated_salary:"صافي الراتب التقديري",
    net_settlement_amount:"صافي التسوية", no_of_recruitment:"الشواغر", notice:"إشعار", notice_count:"عدد الإشعارات",
    occurrence:"رقم التكرار", occurrence_explanation_ar:"تفاصيل التكرار", overtime_compensation_sar:"تعويض الساعات الإضافية",
    overtime_hours:"الساعات الإضافية", overtime_pay_sar:"أجر الساعات الإضافية", payslip:"قسيمة الراتب",
    payslip_id:"رقم القسيمة", rating_ar:"التقدير", rating_code:"رمز التقدير", readback_verified:"التحقق بعد التنفيذ",
    recent_actions:"آخر الإجراءات", recent_appraisals:"آخر التقييمات", recent_leaves:"آخر الإجازات",
    recent_loans:"آخر السلف", recent_records:"أحدث السجلات", recent_transactions:"آخر المعاملات",
    recommendation_ar:"التوصية", records:"السجلات", records_count:"عدد السجلات", recovery:"نتيجة التحقق",
    reference:"المرجع", remaining_month_deduction_allowance_days:"أيام الخصم المتاحة هذا الشهر", request_unit:"وحدة الطلب",
    requires_allocation:"يتطلب تخصيص رصيد", saudization_status_ar:"حالة التوطين", scan_date:"تاريخ الفحص",
    service_period:"مدة الخدمة", severity_label:"الأولوية", sharia_compliance:"الضوابط الشرعية", simulation:"نتيجة المحاكاة",
    stage_name:"المرحلة", standard_hours:"ساعات العمل المعتادة", statutory_annual_entitlement:"الاستحقاق السنوي النظامي",
    statutory_article:"المادة النظامية", statutory_explanation_ar:"التوضيح النظامي", statutory_guidance_ar:"الإرشادات النظامية",
    statutory_summary_ar:"الملخص النظامي", suggested_max_installment:"أعلى قسط مقترح", suggested_min_term:"أقصر مدة مقترحة",
    summary_message_ar:"الملخص", tiers:"الشرائح", timestamp:"الوقت", total_actions_count:"إجمالي الإجراءات",
    total_active_loan_amount:"إجمالي السلف القائمة", total_alerts:"إجمالي التنبيهات", total_appraisals_count:"عدد التقييمات",
    total_days_worked:"أيام العمل", total_employees_scanned:"الموظفون المشمولون بالفحص", total_overtime_hours:"إجمالي الساعات الإضافية",
    total_package:"إجمالي الأجر والبدلات", total_salaries_sar:"إجمالي الرواتب بالريال", total_salary:"إجمالي الراتب",
    total_settlement_amount:"إجمالي التسوية", total_standard_hours:"إجمالي الساعات المعتادة", total_transactions_count:"إجمالي المعاملات",
    total_worked_hours:"إجمالي ساعات العمل", transaction_id:"رقم المعاملة", unpaid_salary_amount:"الأجر غير المدفوع",
    warning:"تحذير", warning_count:"عدد التحذيرات", warning_levels:"درجات الإنذار", worked_hours:"ساعات العمل", years:"السنوات"
  };
  const el = id => document.getElementById(id);
  const domain = el("hrDomain"), action = el("hrAction"), form = el("hrServiceForm");
  const approval = el("hrApproval"), notice = el("hrNotice"), output = el("hrResult");
  let spec, routes = [], pending, revision = 0;
  function node(tag, text) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    return element;
  }
  function reset() {
    revision++;
    pending = null;
    approval.hidden = true;
    output.replaceChildren();
    notice.textContent = "";
    el("hrRun").disabled = !spec;
    approval.querySelector("button").disabled = false;
  }
  function bodySchema(route) {
    const body = route.operation.requestBody?.content["application/json"]?.schema;
    return spec.components.schemas[body?.$ref?.split("/").pop()] || {};
  }
  function payslipRows(container) {
    const rows = node("div");
    rows.dataset.payslips = "";
    const add = node("button", "إضافة موظف");
    add.type = "button"; add.className = "btn btn-secondary";
    function appendRow() {
      const record = node("fieldset"), inputs = node("div");
      record.append(node("legend", "مسير موظف"));
      inputs.className = "hr-service-fields";
      for (const [key, caption] of Object.entries({
        employee_name:"اسم الموظف", identification_id:"رقم الهوية أو الإقامة", iban:"الآيبان",
        basic_wage:"الراتب الأساسي", housing_allowance:"بدل السكن", transportation_allowance:"بدل النقل",
        other_allowances:"بدلات أخرى", total_deductions:"إجمالي الاستقطاعات", net_wage:"صافي الراتب"
      })) {
        const label = node("label", caption), input = node("input");
        input.dataset.payField = key;
        input.required = ["employee_name","identification_id","iban","basic_wage","net_wage"].includes(key);
        if (!["employee_name","identification_id","iban"].includes(key)) {
          input.type = "number"; input.step = ".01"; input.min = "0";
        }
        if (key === "iban") { input.pattern = "[Ss][Aa][0-9]{22}"; input.dir = "ltr"; }
        label.append(input); inputs.append(label);
      }
      const remove = node("button","إزالة الموظف");
      remove.type = "button"; remove.className = "btn btn-secondary";
      remove.onclick = () => {
        if (rows.childElementCount > 1) record.remove();
        rows.firstElementChild.querySelector("button").disabled = rows.childElementCount === 1;
        reset();
      };
      record.append(inputs, remove); rows.append(record);
      rows.firstElementChild.querySelector("button").disabled = rows.childElementCount === 1;
      reset();
    }
    add.onclick = appendRow;
    container.append(rows, add);
    appendRow();
  }
  const references = {
    holiday_status_id: ["leaves/types","types"], contract_type_id: ["contracts/types","contract_types"],
    job_id: ["recruitment/jobs","jobs"], stage_id: ["recruitment/stages","stages"], struct_id: ["payroll/structures","structures"],
    letter_type: ["letters/types","letter_types"], warning_level: ["warnings/levels","warning_levels"],
    expense_category: ["expenses/categories","categories"], category_id: ["letters/categories","categories"]
  };
  function attachChoices(label, input, key) {
    const employee = ["employee_id","manager_id"].includes(key);
    if (!employee && !references[key]) return;
    const list = node("datalist");
    list.id = "hr-choices-" + input.closest("form").id + "-" + key;
    input.setAttribute("list", list.id);
    label.append(list);
    if (employee) {
      input.type = "text"; input.pattern = "[0-9]+";
      input.placeholder = "رقم الموظف أو ابحث بالاسم";
    }
    let timeout, series = 0;
    const hint = node("small");
    label.append(hint);
    function refresh() {
      const query = input.value.trim();
      const current = ++series;
      clearTimeout(timeout);
      if (employee && (query.length < 2 || /^\d+$/.test(query))) {
        hint.textContent = ""; list.replaceChildren(); return;
      }
      if (!employee && list.childElementCount) return;
      timeout = setTimeout(async () => {
        try {
          const params = new URLSearchParams({company_id:selectedCompanyId, q:query});
          const path = employee ? "/api/reference/employees?" + params : "/api/" + references[key][0];
          const response = await apiFetch(path);
          if (!response.ok) throw Error();
          const data = await response.json();
          const records = data[employee ? "employees" : references[key][1]];
          if (current !== series || !input.isConnected) return;
          list.replaceChildren(...records.map(record => new Option(record.name_ar || record.title_ar || record.name, record.id)));
          hint.textContent = records.length ? "" : "لا توجد خيارات مطابقة.";
        } catch {
          if (current === series && input.isConnected) hint.textContent = "تعذر تحميل الخيارات. يمكنك إدخال القيمة مباشرة.";
        }
      }, employee ? 250 : 0);
    }
    input.addEventListener(employee ? "input" : "focus", refresh);
  }
  function fields(container, route) {
    container.replaceChildren();
    const body = bodySchema(route);
    const items = [...(route.operation.parameters || []), ...Object.entries(body.properties || {})
      .map(([name, schema]) => ({name, schema, required: body.required?.includes(name)}))];
    const advanced = node("details");
    advanced.append(node("summary", "حقول اختيارية"));
    const optional = node("div");
    optional.className = "hr-service-fields";
    advanced.append(optional);
    for (const {name, schema, required} of items) {
      if (name === "approval_token") continue;
      if (name === "payslips_data") { payslipRows(container); continue; }
      const type = schema.type || schema.anyOf?.find(x => x.type !== "null")?.type;
      const confirm = name.endsWith("confirmation_text");
      const label = node("label", labels[name] || schema.title);
      let input;
      if (type === "boolean") {
        input = node("select");
        input.add(new Option("اختر", ""));
        input.add(new Option("نعم", "true"));
        input.add(new Option("لا", "false"));
      } else {
        input = node("input");
        if (type === "number" || type === "integer") {
          input.type = "number";
          input.step = type === "integer" ? "1" : "any";
        } else if (type === "array" || type === "object") {
          input.type = "file";
          input.accept = ".json,application/json";
        } else if (/(^date$|^date_|_date$|_date_)/.test(name)) {
          input.type = "date";
        } else if (name === "email") input.type = "email";
      }
      input.name = name;
      input.dataset.kind = type;
      input.required = !!required || confirm;
      if (confirm) input.pattern = "تأكيد";
      else if (schema.default != null && input.type !== "file") input.value = String(schema.default);
      if (name === "company_id" && selectedCompanyId) input.value = selectedCompanyId;
      label.append(input);
      const primary = required || confirm || name === "run_id";
      (primary ? container : optional).append(label);
    }
    if (optional.childElementCount) container.append(advanced);
    for (const input of container.querySelectorAll("input[name]")) attachChoices(input.parentElement, input, input.name);
  }
  function title(path) {
    const parts = path.split("/").slice(3);
    if (parts[0] === "applicants" && parts.length === 2) return "بيانات متقدم";
    const key = parts.at(-1).startsWith("{") ? parts[0] : parts.at(-1);
    return actions[key] || key;
  }
  function refreshAction() {
    reset();
    const route = routes.find(item => item.path === action.value);
    if (!route) return;
    fields(el("hrInputs"), route);
    el("hrRun").textContent = title(route.path);
  }
  function refreshDomain() {
    action.replaceChildren();
    for (const route of routes.filter(item => item.group === domain.value && !item.path.endsWith("/apply"))) {
      action.add(new Option(title(route.path), route.path));
    }
    refreshAction();
  }
  async function load() {
    if (spec) return;
    el("hrRun").disabled = true;
    try {
      const res = await fetch("/openapi.json");
      if (!res.ok) throw Error();
      spec = await res.json();
      for (const [path, methods] of Object.entries(spec.paths)) {
        const group = path.split("/")[2];
        if (!path.startsWith("/api/") || !Object.hasOwn(domains, group)) continue;
        for (const method of ["get","post"]) {
          if (methods[method]) routes.push({path, group, method, operation:methods[method]});
        }
      }
      for (const [key, label] of Object.entries(domains)) domain.add(new Option(label, key));
      refreshDomain();
    } catch {
      notice.textContent = "تعذر تحميل الخدمات. أعد فتح التبويب للمحاولة.";
    }
  }
  function render(value) {
    if (value == null) return node("span", "—");
    if (typeof value === "boolean") return node("span", value ? "نعم" : "لا");
    if (typeof value !== "object") return node("span", String(value));
    if (Array.isArray(value)) {
      if (!value.length) return node("span", "لا توجد سجلات");
      const list = node("ul");
      for (const item of value) {
        const li = node("li"); li.append(render(item)); list.append(li);
      }
      return list;
    }
    const list = node("dl");
    for (const [key, item] of Object.entries(value)) {
      if (["approval_token","token","status","content"].includes(key) || item == null || (Array.isArray(item) && !item.length)) continue;
      const dt = node("dt", labels[key] || resultLabels[key] || actions[key] || key.replaceAll("_"," "));
      const dd = node("dd"); dd.append(render(item)); list.append(dt, dd);
    }
    if (!list.childElementCount) return node("span", "لا توجد بيانات للعرض");
    return list;
  }
  async function readValues(container) {
    const values = {};
    const payslips = container.querySelector("[data-payslips]");
    if (payslips) values.payslips_data = Array.from(payslips.children, record =>
      Object.fromEntries(Array.from(record.querySelectorAll("input")).filter(input => input.value)
        .map(input => [input.dataset.payField, input.type === "number" ? input.valueAsNumber : input.value.trim()])));
    for (const input of container.querySelectorAll("input[name],select[name]")) {
      if (!input.value) continue;
      if (input.type === "file") {
        let data;
        try { data = JSON.parse(await input.files[0].text()); } catch { throw Error("تعذرت قراءة ملف البيانات."); }
        const array = input.dataset.kind === "array";
        if (array ? !Array.isArray(data) : !data || typeof data !== "object" || Array.isArray(data)) throw Error("صيغة بيانات الملف غير مناسبة لهذا الحقل.");
        values[input.name] = data;
      } else if (["integer","number"].includes(input.dataset.kind)) values[input.name] = Number(input.value);
      else if (input.dataset.kind === "boolean") values[input.name] = input.value === "true";
      else values[input.name] = input.value.trim();
    }
    return values;
  }
  let fileUrl;
  function download(blob, name) {
    if (fileUrl) URL.revokeObjectURL(fileUrl);
    fileUrl = URL.createObjectURL(blob);
    const link = node("a","تنزيل الملف");
    link.href = fileUrl; link.download = name; link.className = "btn btn-secondary";
    output.append(link);
  }
  async function submit(event) {
    event.preventDefault();
    const approving = event.currentTarget === approval;
    const route = approving ? pending?.route : routes.find(item => item.path === action.value);
    if (!route) return;
    const token = pending?.token;
    const scope = selectedCompanyId;
    if (!approving) reset();
    const current = ++revision;
    const submitButton = event.currentTarget.querySelector("button");
    submitButton.disabled = true;
    notice.textContent = "جارٍ تنفيذ الطلب…";
    try {
      const data = await readValues(approving ? el("hrApprovalInputs") : el("hrInputs"));
      if (current !== revision || scope !== selectedCompanyId) return;
      if (route.path.endsWith("/heal-batch") && !data.run_id && !(data.rows?.length && data.validation_results?.length))
        throw Error("أدخل رقم عملية الاستيراد أو اختر ملف الصفوف ونتائج الفحص.");
      if (approving) data.approval_token = token;
      const path = route.path.replace(/\{(\w+)\}/g, (_, key) => {
        const value = data[key]; delete data[key]; return encodeURIComponent(value);
      });
      const url = new URL(path, location.origin);
      const options = {method: route.method.toUpperCase()};
      if (route.method === "get") url.search = new URLSearchParams(data);
      else { options.headers = {"Content-Type":"application/json"}; options.body = JSON.stringify(data); }
      const response = await apiFetch(url, options);
      if (current !== revision || selectedCompanyId !== scope) return;
      if (!response.ok) {
        const detail = (await response.json().catch(() => ({}))).detail;
        throw Error(typeof detail === "string" ? detail : "تعذّر إتمام الطلب (" + response.status + ").");
      }
      if (/\/(html|pdf)$/.test(path)) {
        const blob = await response.blob();
        if (current !== revision) return;
        output.replaceChildren();
        download(blob, domain.value + "." + path.split("/").pop());
      } else {
        const result = await response.json();
        if (current !== revision) return;
        output.replaceChildren(render(result));
        if (result.content && result.filename) download(new Blob([result.content]), result.filename);
        const draft = result.result || result.dry_run;
        if (path.endsWith("/dry-run") && result.status === "success" && draft?.approval_token && draft.is_valid !== false && draft.can_proceed !== false) {
          const next = routes.find(item => item.path === "/api/" + route.group + "/apply");
          if (next) {
            pending = {route:next, token:draft.approval_token};
            fields(el("hrApprovalInputs"), next); approval.hidden = false;
          }
        }
        if (approving) { pending = null; approval.hidden = true; }
        if (["error","invalid","failed","warning"].includes(result.status)) {
          notice.textContent = "تعذر إتمام الفحص. راجع التفاصيل."; return;
        }
      }
      notice.textContent = approving ? "اكتمل التنفيذ." : "";
    } catch (error) {
      if (current === revision) notice.textContent = error.message;
    } finally {
      if (current === revision) submitButton.disabled = false;
    }
  }
  domain.onchange = refreshDomain;
  action.onchange = refreshAction;
  form.addEventListener("input", reset);
  form.onsubmit = approval.onsubmit = submit;
  el("companySelector").addEventListener("change", () => spec && refreshAction());
  const section = el("view-services");
  new MutationObserver(() => {
    if (section.classList.contains("is-visible")) load();
    else if (spec) refreshAction();
  }).observe(section, {attributes:true, attributeFilter:["class"]});
  if (section.classList.contains("is-visible")) load();
})();
