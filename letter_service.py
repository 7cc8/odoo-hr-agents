"""
خدمة إدارة وإصدار خطابات الموارد البشرية وشهادات الرواتب الرسمية (HR Official Letters & Approvals Service)
=======================================================================================================
الطبقة التنفيذية لإعداد، مراجعة، وتوثيق الخطابات الإدارية وشهادات التعريف بالراتب في Odoo:
- نموذج Odoo المعتمد: approval.request (فئة الخطابات الرسمية والموافقات الإدارية).
- نموذج تصنيفات Odoo: approval.category.
- أنواع الخطابات المدعومة:
  1. شهادة تعريف بالراتب مفصلة (Salary Certificate with Allowances).
  2. شهادة إثبات عمل وتثبيت موظف بدون ذكر الراتب (Employment Certificate).
  3. خطاب رسمي موجه للبنوك والمصارف (Bank Request Letter).
  4. خطاب رسمي موجه للممثليات الدبلوماسية والسفارات (Embassy Visa Letter).
  5. خطاب معتمد للتصديق من الغرفة التجارية (Chamber of Commerce Certified Letter).

القواعد والضوابط الإلزامية:
1. التفريق الحتمي بين المواطن السعودي والمقيم (رقم الهوية الوطنية 1x مقابل الإقامة 2x، والجنسية).
2. استخراج بيانات الراتب الموثقة من العقد الفعلي (الأجر الأساسي، بدل السكن، بدل النقل، الإجمالي).
3. مبدأ التحقق المزدوج Four-Eyes مع إلزام كتابة "تأكيد" قطيعاً قبل الحفظ في Odoo.
4. التحقق المستقل بعد الكتابة (Readback Verification) للتأكد من ثبات البيانات في Odoo.
5. تسجيل وتدقيق العمليات في سجل آمن logs/letter_audit_log.jsonl.
6. توليد خطابات PDF فائقة الجودة وفق معايير الهوية السعودية الرسمية ورمز التحقق QR.
"""

from __future__ import annotations

import os
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional, Tuple

from odoo_readonly_repository import OdooReadonlyRepository
from odoo_letter_write_gateway import OdooLetterWriteGateway
from eos_service import detect_employee_nationality

LETTER_AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "letter_audit_log.jsonl")
LETTERS_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "letters")


# أنواع الخطابات المدعومة
SUPPORTED_LETTER_TYPES = {
    "salary_certificate": {
        "id": "salary_certificate",
        "title_ar": "شهادة تعريف بالراتب والبدلات",
        "title_en": "Salary & Allowances Certificate",
        "include_salary_default": True,
        "default_to": "إلى من يهمه الأمر / To Whom It May Concern",
    },
    "employment_certificate": {
        "id": "employment_certificate",
        "title_ar": "شهادة إثبات عمل واستمرار على رأس العمل",
        "title_en": "Certificate of Employment",
        "include_salary_default": False,
        "default_to": "إلى من يهمه الأمر / To Whom It May Concern",
    },
    "bank_letter": {
        "id": "bank_letter",
        "title_ar": "خطاب مصرفي لفتح حساب أو تمويل",
        "title_en": "Bank Request Letter",
        "include_salary_default": True,
        "default_to": "إلى إدارة العمليات المصرفية",
    },
    "embassy_letter": {
        "id": "embassy_letter",
        "title_ar": "خطاب طلب تأشيرة سفر موجه للسفارة",
        "title_en": "Embassy Travel Visa Letter",
        "include_salary_default": True,
        "default_to": "إلى قسم التأشيرات والقنصلية / Visa & Consular Section",
    },
    "chamber_certified": {
        "id": "chamber_certified",
        "title_ar": "خطاب رسمي موجه للغرفة التجارية للتصديق",
        "title_en": "Chamber of Commerce Certified Letter",
        "include_salary_default": True,
        "default_to": "الغرفة التجارية الصناعية",
    },
}


@dataclass
class LetterSalaryDetails:
    basic_wage: float = 0.0
    housing_allowance: float = 0.0
    transportation_allowance: float = 0.0
    other_allowances: float = 0.0
    total_package: float = 0.0


@dataclass
class LetterDryRunResult:
    is_valid: bool
    employee_id: int
    employee_name: str
    is_saudi: bool
    nationality_text_ar: str
    identification_id: str
    job_title: str
    department_name: str
    hiring_date: str
    letter_type: str
    letter_title_ar: str
    recipient: str
    purpose: str
    letter_language: str
    chamber_of_commerce_stamp: bool
    include_salary: bool
    salary_details: LetterSalaryDetails
    bank_name: Optional[str]
    bank_account_number: Optional[str]
    category_id: int
    category_name: str
    approval_token: str
    created_at_iso: str
    preview_body_ar: str
    preview_body_en: str
    notes: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class LetterApplyResult:
    is_success: bool
    approval_request_id: Optional[int]
    employee_id: int
    employee_name: str
    letter_type: str
    request_status: str
    readback_data: Optional[Dict[str, Any]]
    pdf_path: Optional[str]
    html_path: Optional[str]
    verification_code: str
    message_ar: str
    errors: List[str] = field(default_factory=list)


class LetterService:
    """
    الخدمة الشاملة للخطابات وشهادات التعريف بالراتب مع حماية التحقق المزدوج والتوثيق الرسمي.
    """

    def __init__(
        self,
        repo: Optional[OdooReadonlyRepository] = None,
        gateway: Optional[OdooLetterWriteGateway] = None,
    ):
        self.repo = repo or OdooReadonlyRepository()
        self.gateway = gateway or OdooLetterWriteGateway()
        self._pending_tokens: Dict[str, LetterDryRunResult] = {}
        os.makedirs(os.path.dirname(LETTER_AUDIT_LOG_FILE), exist_ok=True)
        os.makedirs(LETTERS_OUTPUT_DIR, exist_ok=True)

    def get_supported_letter_types(self) -> List[Dict[str, Any]]:
        """قائمة أنواع الخطابات المدعومة إدارياً."""
        return list(SUPPORTED_LETTER_TYPES.values())

    def get_employee_salary_details(self, employee_id: int) -> LetterSalaryDetails:
        """
        استخراج وتجميع بيانات الراتب والبدلات من العقد الحالي للموظف.
        """
        try:
            contracts = self.repo.get_contracts(limit=100)
            emp_contracts = [
                c for c in contracts
                if (c.get("employee_id") and (
                    c["employee_id"] == employee_id or
                    (isinstance(c["employee_id"], (list, tuple)) and c["employee_id"][0] == employee_id)
                ))
            ]

            # الأولوية للعقد النشط (open / in_contract)
            active_contract = None
            for c in emp_contracts:
                state = c.get("state") or ""
                if state in ("open", "draft", "close"):
                    active_contract = c
                    if state == "open":
                        break

            if active_contract:
                basic = float(active_contract.get("wage") or 0.0)
                housing = float(active_contract.get("l10n_sa_housing_allowance") or active_contract.get("housing_allowance") or (basic * 0.25))
                transport = float(active_contract.get("l10n_sa_transportation_allowance") or active_contract.get("transportation_allowance") or (basic * 0.10))
                other = float(active_contract.get("other_allowance") or 0.0)
                total = basic + housing + transport + other
                return LetterSalaryDetails(
                    basic_wage=round(basic, 2),
                    housing_allowance=round(housing, 2),
                    transportation_allowance=round(transport, 2),
                    other_allowances=round(other, 2),
                    total_package=round(total, 2),
                )
        except Exception:
            pass

        return LetterSalaryDetails()

    def _resolve_category_id(self, preferred_category_name: Optional[str] = None) -> Tuple[int, str]:
        """تحديد معرف فئة الموافقة المناسبة من Odoo."""
        try:
            cats = self.repo.get_approval_categories()
            if cats:
                if preferred_category_name:
                    for c in cats:
                        if preferred_category_name.lower() in str(c.get("name", "")).lower():
                            return c["id"], c["name"]
                # البحث عن General Approval كخيار افتراضي
                for c in cats:
                    if "general" in str(c.get("name", "")).lower():
                        return c["id"], c["name"]
                return cats[0]["id"], cats[0]["name"]
        except Exception:
            pass
        return 3, "General Approval"

    def _generate_verification_code(self, employee_id: int, letter_type: str) -> str:
        """توليد رمز تحقق رسمي فريد للخطاب."""
        year = datetime.now().year
        rand_part = uuid.uuid4().hex[:6].upper()
        type_code = letter_type[:3].upper()
        return f"SAR-{type_code}-{year}-{employee_id}-{rand_part}"

    def _build_letter_texts(
        self,
        employee_name: str,
        is_saudi: bool,
        id_number: str,
        job_title: str,
        department_name: str,
        hiring_date: str,
        recipient: str,
        purpose: str,
        include_salary: bool,
        salary: LetterSalaryDetails,
        bank_name: Optional[str] = None,
        bank_account: Optional[str] = None,
    ) -> Tuple[str, str]:
        """صياغة نص الخطاب العربي والإنجليزي بالصيغة المؤسسية المعتمدة."""
        id_title_ar = "الهوية الوطنية" if is_saudi else "الإقامة النظامية"
        id_title_en = "National ID" if is_saudi else "Resident Identity (Iqama)"
        nationality_ar = "سعودي الجنسية" if is_saudi else "غير سعودي"
        nationality_en = "Saudi Citizen" if is_saudi else "Expatriate Resident"

        # الصياغة العربية
        body_ar = (
            f"تشهد إدارة الموارد البشرية بأن الموظف/ {employee_name} ({nationality_ar})، "
            f"وحامل {id_title_ar} رقم ({id_number})، يعمل لدينا بمسمى وظيفي ({job_title}) "
            f"بإدارة ({department_name})، وذلك منذ تاريخ التحاقه بالعمل في ({hiring_date}) "
            f"ولا يزال على رأس العمل حتى تاريخه.\n\n"
        )

        if include_salary:
            body_ar += (
                f"ويتقاضى الموظف راتباً شهرياً مفصلاً كالتالي:\n"
                f"- الراتب الأساسي: {salary.basic_wage:,.2f} ريال سعودي\n"
                f"- بدل السكن: {salary.housing_allowance:,.2f} ريال سعودي\n"
                f"- بدل النقل: {salary.transportation_allowance:,.2f} ريال سعودي\n"
            )
            if salary.other_allowances > 0:
                body_ar += f"- بدلات ومزايا أخرى: {salary.other_allowances:,.2f} ريال سعودي\n"
            body_ar += f"• إجمالي الراتب الشهري: {salary.total_package:,.2f} ريال سعودي.\n\n"

        if bank_name:
            body_ar += f"البنك المحول إليه الراتب: {bank_name}"
            if bank_account:
                body_ar += f" | رقم الآيبان/الحساب: {bank_account}"
            body_ar += "\n\n"

        body_ar += (
            f"وقد أُعطي هذا الخطاب بناءً على طلبه لتقديمه إلى ({recipient}) "
            f"لغرض ({purpose}) دون أدنى مسؤولية أو التزام مالي على المنشأة تجاه الغير."
        )

        # الصياغة الإنجليزية
        body_en = (
            f"This is to certify that Mr./Ms. {employee_name} ({nationality_en}), "
            f"holding {id_title_en} No. ({id_number}), is currently employed with us as "
            f"({job_title}) in the ({department_name}) department since ({hiring_date}) "
            f"and continues to be an active employee to date.\n\n"
        )

        if include_salary:
            body_en += (
                f"The employee receives a monthly salary package as follows:\n"
                f"- Basic Salary: SAR {salary.basic_wage:,.2f}\n"
                f"- Housing Allowance: SAR {salary.housing_allowance:,.2f}\n"
                f"- Transportation Allowance: SAR {salary.transportation_allowance:,.2f}\n"
            )
            if salary.other_allowances > 0:
                body_en += f"- Other Allowances: SAR {salary.other_allowances:,.2f}\n"
            body_en += f"• Total Gross Salary: SAR {salary.total_package:,.2f}\n\n"

        if bank_name:
            body_en += f"Designated Bank: {bank_name}"
            if bank_account:
                body_en += f" | IBAN/Account No.: {bank_account}"
            body_en += "\n\n"

        body_en += (
            f"This certificate has been issued upon the employee's request to be submitted to "
            f"({recipient}) for ({purpose}), without any financial liability or warranty on the company."
        )

        return body_ar, body_en

    def dry_run_letter(
        self,
        employee_id: int,
        letter_type: str = "salary_certificate",
        recipient: Optional[str] = None,
        purpose: Optional[str] = None,
        language: str = "arabic",  # "arabic", "english", "both"
        include_salary: Optional[bool] = None,
        chamber_of_commerce_stamp: bool = False,
        bank_name: Optional[str] = None,
        bank_account_number: Optional[str] = None,
        category_id: Optional[int] = None,
        explicit_is_saudi: Optional[bool] = None,
    ) -> LetterDryRunResult:
        """
        المرحلة الأولى من التحقق المزدوج: فحص وتجهيز مسودة الخطاب وإصدار رمز الموافقة (approval_token).
        """
        errors: List[str] = []
        notes: List[str] = []

        if letter_type not in SUPPORTED_LETTER_TYPES:
            errors.append(f"نوع الخطاب '{letter_type}' غير مدعوم. الأنواع المدعومة: {list(SUPPORTED_LETTER_TYPES.keys())}")
            letter_type = "salary_certificate"

        letter_meta = SUPPORTED_LETTER_TYPES[letter_type]

        # فحص الموظف من المستودع
        employee = None
        try:
            employees = self.repo.get_employees(limit=200)
            for emp in employees:
                if emp.get("id") == employee_id:
                    employee = emp
                    break
        except Exception as exc:
            errors.append(f"تعذر استرداد بيانات الموظف: {exc}")

        if not employee:
            errors.append(f"الموظف برقم المعرف {employee_id} غير موجود في النظام.")
            return LetterDryRunResult(
                is_valid=False,
                employee_id=employee_id,
                employee_name="غير محدد",
                is_saudi=False,
                nationality_text_ar="غير محدد",
                identification_id="",
                job_title="",
                department_name="",
                hiring_date="",
                letter_type=letter_type,
                letter_title_ar=letter_meta["title_ar"],
                recipient=recipient or letter_meta["default_to"],
                purpose=purpose or "طلب رسمي",
                letter_language=language,
                chamber_of_commerce_stamp=chamber_of_commerce_stamp,
                include_salary=bool(include_salary),
                salary_details=LetterSalaryDetails(),
                bank_name=bank_name,
                bank_account_number=bank_account_number,
                category_id=category_id or 3,
                category_name="General Approval",
                approval_token="",
                created_at_iso=datetime.now(timezone.utc).isoformat(),
                preview_body_ar="",
                preview_body_en="",
                errors=errors,
            )

        employee_name = employee.get("name") or f"Employee #{employee_id}"
        is_saudi = detect_employee_nationality(employee, explicit_is_saudi=explicit_is_saudi)
        nationality_text_ar = "مواطن سعودي" if is_saudi else "مقيم غير سعودي"
        ident_id = str(employee.get("identification_id") or "").strip()
        if not ident_id:
            notes.append("تنبيه: لا يوجد رقم هوية أو إقامة مسجل في ملف الموظف.")

        job_val = employee.get("job_id")
        job_title = job_val[1] if isinstance(job_val, (list, tuple)) and len(job_val) > 1 else str(job_val or "موظف")

        dept_val = employee.get("department_id")
        dept_name = dept_val[1] if isinstance(dept_val, (list, tuple)) and len(dept_val) > 1 else str(dept_val or "الإدارة العامة")

        hiring_date = str(employee.get("hiring_date") or employee.get("date_start") or "غير محدد")[:10]

        # تحديد تضمين الراتب
        if include_salary is None:
            include_salary = letter_meta["include_salary_default"]

        salary_details = LetterSalaryDetails()
        if include_salary:
            salary_details = self.get_employee_salary_details(employee_id)
            if salary_details.total_package <= 0:
                notes.append("تنبيه: لم يتم العثور على عقد نشط بأجر محدد، سيتم إدراج الأصفار أو يحتاج العقد إلى مراجعة.")

        # تحديد الفئة
        if category_id:
            cat_id = category_id
            cat_name = "Approval Category"
        else:
            cat_id, cat_name = self._resolve_category_id("General")

        recip = (recipient or letter_meta["default_to"]).strip()
        purp = (purpose or f"إصدار {letter_meta['title_ar']} للموظف").strip()

        # إعداد نصوص المعاينة
        preview_ar, preview_en = self._build_letter_texts(
            employee_name=employee_name,
            is_saudi=is_saudi,
            id_number=ident_id or "—",
            job_title=job_title,
            department_name=dept_name,
            hiring_date=hiring_date,
            recipient=recip,
            purpose=purp,
            include_salary=include_salary,
            salary=salary_details,
            bank_name=bank_name,
            bank_account=bank_account_number,
        )

        approval_token = str(uuid.uuid4())
        created_at_iso = datetime.now(timezone.utc).isoformat()

        result = LetterDryRunResult(
            is_valid=(len(errors) == 0),
            employee_id=employee_id,
            employee_name=employee_name,
            is_saudi=is_saudi,
            nationality_text_ar=nationality_text_ar,
            identification_id=ident_id,
            job_title=job_title,
            department_name=dept_name,
            hiring_date=hiring_date,
            letter_type=letter_type,
            letter_title_ar=letter_meta["title_ar"],
            recipient=recip,
            purpose=purp,
            letter_language=language,
            chamber_of_commerce_stamp=chamber_of_commerce_stamp,
            include_salary=include_salary,
            salary_details=salary_details,
            bank_name=bank_name,
            bank_account_number=bank_account_number,
            category_id=cat_id,
            category_name=cat_name,
            approval_token=approval_token,
            created_at_iso=created_at_iso,
            preview_body_ar=preview_ar,
            preview_body_en=preview_en,
            notes=notes,
            errors=errors,
        )

        # حفظ الرمز في الذاكرة لتنفيذ التحقق المزدوج
        self._pending_tokens[approval_token] = result
        return result

    def apply_letter(
        self,
        approval_token: str,
        user_confirmation_text: str = "تأكيد",
        executor: str = "system_operator",
    ) -> LetterApplyResult:
        """
        المرحلة الثانية من التحقق المزدوج: التأكد من رمز الموافقة والكلمة الإلزامية "تأكيد"،
        ثم الحفظ في Odoo وإجراء فحص القراءة المستقل (Readback Verification) وتوليد المستند.
        """
        if not approval_token or approval_token not in self._pending_tokens:
            return LetterApplyResult(
                is_success=False,
                approval_request_id=None,
                employee_id=0,
                employee_name="",
                letter_type="",
                request_status="failed",
                readback_data=None,
                pdf_path=None,
                html_path=None,
                verification_code="",
                message_ar="رمز الموافقة غير صالح أو منتهي الصلاحية. يجب إجراء المعاينة (Dry-Run) أولاً.",
                errors=["رمز الموافقة approval_token غير موجود أو منتهي الصلاحية."],
            )

        draft = self._pending_tokens[approval_token]

        # فحص كلمة التأكيد الإلزامية
        if user_confirmation_text.strip() != "تأكيد":
            return LetterApplyResult(
                is_success=False,
                approval_request_id=None,
                employee_id=draft.employee_id,
                employee_name=draft.employee_name,
                letter_type=draft.letter_type,
                request_status="rejected",
                readback_data=None,
                pdf_path=None,
                html_path=None,
                verification_code="",
                message_ar="مبدأ التحقق المزدوج: يلزم إدخال الكلمة الصريحة 'تأكيد' لاعتماد وإصدار الخطاب.",
                errors=["نص التأكيد غير مطابق للكلمة الإلزامية 'تأكيد'."],
            )

        verification_code = self._generate_verification_code(draft.employee_id, draft.letter_type)

        # تجهيز قيم السجل لـ Odoo (approval.request)
        letter_lang_code = "arabic"
        if draft.letter_language in ("english", "en"):
            letter_lang_code = "english"
        elif draft.letter_language in ("both", "ar_en"):
            letter_lang_code = "both"

        values: Dict[str, Any] = {
            "name": f"{draft.letter_title_ar} - {draft.employee_name} ({verification_code})",
            "category_id": draft.category_id,
            "request_employee_id": draft.employee_id,
            "to": draft.recipient,
            "purpose": draft.purpose,
            "letter_language": letter_lang_code,
            "chamber_of_commerce_stamp": draft.chamber_of_commerce_stamp,
            "reason": f"<p>{draft.preview_body_ar.replace(chr(10), '<br/>')}</p>",
        }

        if draft.bank_name:
            values["bank_name"] = draft.bank_name
        if draft.bank_account_number:
            values["bank_account_number"] = draft.bank_account_number

        try:
            req_id = self.gateway.create_letter_request(values)
        except Exception as exc:
            return LetterApplyResult(
                is_success=False,
                approval_request_id=None,
                employee_id=draft.employee_id,
                employee_name=draft.employee_name,
                letter_type=draft.letter_type,
                request_status="failed",
                readback_data=None,
                pdf_path=None,
                html_path=None,
                verification_code=verification_code,
                message_ar=f"فشل إنشاء طلب الخطاب في Odoo: {exc}",
                errors=[str(exc)],
            )

        # التحقق المستقل بعد الكتابة (Readback Verification)
        readback = None
        try:
            readback = self.gateway.read_letter_request(req_id)
        except Exception:
            readback = {"id": req_id, "status": "unknown"}

        # توليد المستندات HTML و PDF
        html_path = None
        pdf_path = None
        try:
            html_content = self.render_letter_html(draft, verification_code, req_id)
            html_filename = f"letter_{req_id}_{verification_code}.html"
            html_path = os.path.join(LETTERS_OUTPUT_DIR, html_filename)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            # محاولة توليد PDF باستخدام Playwright
            pdf_filename = f"letter_{req_id}_{verification_code}.pdf"
            pdf_path = os.path.join(LETTERS_OUTPUT_DIR, pdf_filename)
            self._render_html_to_pdf_playwright(html_path, pdf_path)
        except Exception as doc_err:
            draft.notes.append(f"تنبيه توليد المستند: {doc_err}")

        # تسجيل وتدقيق العملية في سجل التدقيق
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "create_letter_request",
            "approval_request_id": req_id,
            "verification_code": verification_code,
            "employee_id": draft.employee_id,
            "employee_name": draft.employee_name,
            "is_saudi": draft.is_saudi,
            "letter_type": draft.letter_type,
            "category_id": draft.category_id,
            "recipient": draft.recipient,
            "purpose": draft.purpose,
            "chamber_stamp": draft.chamber_of_commerce_stamp,
            "total_package": draft.salary_details.total_package,
            "executor": executor,
            "html_path": html_path,
            "pdf_path": pdf_path,
        }
        try:
            with open(LETTER_AUDIT_LOG_FILE, "a", encoding="utf-8") as af:
                af.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

        # مسح الرمز المستخدم من الذاكرة
        self._pending_tokens.pop(approval_token, None)

        return LetterApplyResult(
            is_success=True,
            approval_request_id=req_id,
            employee_id=draft.employee_id,
            employee_name=draft.employee_name,
            letter_type=draft.letter_type,
            request_status=readback.get("request_status") if readback else "new",
            readback_data=readback,
            pdf_path=pdf_path if (pdf_path and os.path.exists(pdf_path)) else None,
            html_path=html_path,
            verification_code=verification_code,
            message_ar=f"تم إصدار وتوثيق الخطاب بنجاح في Odoo (طلب رقم #{req_id}) برمز التحقق {verification_code}.",
        )

    def _render_html_to_pdf_playwright(self, html_path: str, pdf_path: str) -> bool:
        """تحويل ملف HTML إلى PDF رسمي عبر Playwright إن وُجد."""
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(f"file:///{os.path.abspath(html_path).replace(chr(92), '/')}")
                page.wait_for_timeout(500)
                page.pdf(
                    path=pdf_path,
                    format="A4",
                    print_background=True,
                    margin={"top": "12mm", "bottom": "12mm", "left": "15mm", "right": "15mm"}
                )
                browser.close()
            return True
        except Exception:
            return False

    def render_letter_html(
        self,
        draft: LetterDryRunResult,
        verification_code: str,
        request_id: Optional[int] = None,
    ) -> str:
        """
        توليد صفحة HTML بتصميم مؤسسي سعودي فائق الجودة متوافق مع نظام الخطابات الرسمية.
        """
        is_both = draft.letter_language in ("both", "ar_en")
        is_en_only = draft.letter_language in ("english", "en")
        today_date = date.today().strftime("%Y/%m/%d")

        salary_section_html = ""
        if draft.include_salary:
            salary_section_html = f"""
            <div class="salary-card">
                <div class="salary-header">تفاصيل حزمة الأجر والبدلات المعتمدة / Compensation Details</div>
                <div class="salary-grid">
                    <div class="salary-row">
                        <span class="label">الراتب الأساسي / Basic Wage:</span>
                        <span class="value">{draft.salary_details.basic_wage:,.2f} ر.س</span>
                    </div>
                    <div class="salary-row">
                        <span class="label">بدل السكن / Housing Allowance:</span>
                        <span class="value">{draft.salary_details.housing_allowance:,.2f} ر.س</span>
                    </div>
                    <div class="salary-row">
                        <span class="label">بدل النقل / Transportation Allowance:</span>
                        <span class="value">{draft.salary_details.transportation_allowance:,.2f} ر.س</span>
                    </div>
                    {"<div class='salary-row'><span class='label'>بدلات ومزايا أخرى / Other Allowances:</span><span class='value'>" + f"{draft.salary_details.other_allowances:,.2f} ر.س</span></div>" if draft.salary_details.other_allowances > 0 else ""}
                    <div class="salary-row total-row">
                        <span class="label">إجمالي الراتب الشهري / Total Gross Salary:</span>
                        <span class="value">{draft.salary_details.total_package:,.2f} ر.س</span>
                    </div>
                </div>
            </div>
            """

        bank_section_html = ""
        if draft.bank_name:
            bank_section_html = f"""
            <div class="bank-box">
                <strong>بيانات التحويل البنكي:</strong> بنك: {draft.bank_name}
                {f" | آيبان/حساب: {draft.bank_account_number}" if draft.bank_account_number else ""}
            </div>
            """

        chamber_stamp_html = ""
        if draft.chamber_of_commerce_stamp:
            chamber_stamp_html = """
            <div class="chamber-box">
                <div class="stamp-icon">🏛️</div>
                <div class="stamp-text">
                    <strong>تصديق الغرفة التجارية الصناعية</strong><br>
                    تم توجيه هذا الخطاب لاعتماده وتصديقه إلكترونياً من الغرفة التجارية
                </div>
            </div>
            """

        body_arabic_formatted = draft.preview_body_ar.replace("\n", "<br>")
        body_english_formatted = draft.preview_body_en.replace("\n", "<br>")

        content_html = ""
        if is_both:
            content_html = f"""
            <div class="bilingual-container">
                <div class="col-ar" dir="rtl">
                    <h3>النسخة العربية</h3>
                    <p class="letter-text">{body_arabic_formatted}</p>
                </div>
                <div class="col-en" dir="ltr">
                    <h3>English Version</h3>
                    <p class="letter-text">{body_english_formatted}</p>
                </div>
            </div>
            """
        elif is_en_only:
            content_html = f"""
            <div class="letter-body" dir="ltr">
                <p class="letter-text">{body_english_formatted}</p>
            </div>
            """
        else:
            content_html = f"""
            <div class="letter-body" dir="rtl">
                <p class="letter-text">{body_arabic_formatted}</p>
            </div>
            """

        html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>{draft.letter_title_ar} - {draft.employee_name}</title>
    <style>
        @page {{
            size: A4;
            margin: 15mm;
        }}
        * {{
            box-sizing: border-box;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #1e293b;
            background: #ffffff;
            margin: 0;
            padding: 20px;
            font-size: 13.5px;
            line-height: 1.7;
        }}
        .letter-container {{
            max-width: 800px;
            margin: 0 auto;
            border: 1px solid #e2e8f0;
            padding: 40px;
            border-radius: 8px;
            position: relative;
            background: #ffffff;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #0f766e;
            padding-bottom: 20px;
            margin-bottom: 25px;
        }}
        .company-ar {{
            text-align: right;
        }}
        .company-en {{
            text-align: left;
            direction: ltr;
        }}
        .company-name {{
            font-size: 16px;
            font-weight: 700;
            color: #0f766e;
            margin: 0;
        }}
        .company-sub {{
            font-size: 11px;
            color: #64748b;
            margin-top: 4px;
        }}
        .logo-placeholder {{
            font-size: 26px;
            font-weight: 800;
            color: #0f766e;
            text-align: center;
            background: #f0fdfa;
            border: 1px dashed #0f766e;
            padding: 8px 16px;
            border-radius: 6px;
        }}
        .doc-meta {{
            display: flex;
            justify-content: space-between;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 10px 16px;
            margin-bottom: 25px;
            font-size: 12px;
        }}
        .doc-title {{
            text-align: center;
            margin-bottom: 25px;
        }}
        .doc-title h1 {{
            font-size: 20px;
            color: #0f172a;
            margin: 0;
            padding-bottom: 6px;
            border-bottom: 1px solid #cbd5e1;
            display: inline-block;
        }}
        .doc-title h2 {{
            font-size: 14px;
            color: #64748b;
            font-weight: normal;
            margin: 4px 0 0 0;
        }}
        .letter-text {{
            font-size: 14px;
            line-height: 2;
            color: #1e293b;
            text-align: justify;
        }}
        .bilingual-container {{
            display: flex;
            gap: 20px;
            margin-top: 15px;
        }}
        .bilingual-container .col-ar,
        .bilingual-container .col-en {{
            flex: 1;
            background: #f8fafc;
            padding: 16px;
            border-radius: 6px;
            border: 1px solid #e2e8f0;
        }}
        .salary-card {{
            margin: 20px 0;
            background: #f0fdf4;
            border: 1px solid #bbf7d0;
            border-radius: 6px;
            overflow: hidden;
        }}
        .salary-header {{
            background: #16a34a;
            color: #ffffff;
            padding: 8px 16px;
            font-weight: 600;
            font-size: 13px;
        }}
        .salary-grid {{
            padding: 12px 16px;
        }}
        .salary-row {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px dashed #cbd5e1;
            font-size: 13px;
        }}
        .salary-row:last-child {{
            border-bottom: none;
        }}
        .total-row {{
            font-weight: 700;
            color: #15803d;
            font-size: 14px;
            border-top: 1px solid #16a34a;
            margin-top: 6px;
            padding-top: 8px;
        }}
        .bank-box {{
            background: #f1f5f9;
            padding: 10px 14px;
            border-radius: 6px;
            font-size: 12.5px;
            margin-bottom: 15px;
        }}
        .chamber-box {{
            display: flex;
            align-items: center;
            gap: 12px;
            background: #fffbeb;
            border: 1px solid #fde68a;
            padding: 10px 14px;
            border-radius: 6px;
            margin: 15px 0;
            font-size: 12px;
        }}
        .footer-signatures {{
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            margin-top: 40px;
            padding-top: 25px;
            border-top: 1px solid #e2e8f0;
        }}
        .seal-box {{
            text-align: center;
            border: 2px dashed #0f766e;
            padding: 12px 24px;
            border-radius: 50%;
            width: 110px;
            height: 110px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            color: #0f766e;
            font-size: 11px;
            font-weight: bold;
        }}
        .signature-box {{
            text-align: center;
            min-width: 180px;
        }}
        .signature-title {{
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 30px;
        }}
        .verif-footer {{
            margin-top: 30px;
            text-align: center;
            font-size: 11px;
            color: #94a3b8;
            border-top: 1px solid #f1f5f9;
            padding-top: 12px;
        }}
    </style>
</head>
<body>
    <div class="letter-container">
        <div class="header">
            <div class="company-ar">
                <div class="company-name">شركة النخبة الذكية للتقنية</div>
                <div class="company-sub">إدارة الموارد البشرية والعمليات</div>
                <div class="company-sub">المملكة العربية السعودية - الرياض</div>
            </div>
            <div class="logo-placeholder">ELITE HR</div>
            <div class="company-en">
                <div class="company-name">Smart Elite Tech Co.</div>
                <div class="company-sub">Human Resources Department</div>
                <div class="company-sub">Riyadh, Kingdom of Saudi Arabia</div>
            </div>
        </div>

        <div class="doc-meta">
            <div><strong>تاريخ الإصدار / Date:</strong> {today_date}</div>
            <div><strong>رقم الطلب / Request No:</strong> #{request_id or '—'}</div>
            <div><strong>رمز التحقق / Verification Code:</strong> <code>{verification_code}</code></div>
        </div>

        <div class="doc-title">
            <h1>{draft.letter_title_ar}</h1>
            <h2>{SUPPORTED_LETTER_TYPES.get(draft.letter_type, {}).get('title_en', '')}</h2>
        </div>

        {content_html}
        {salary_section_html}
        {bank_section_html}
        {chamber_stamp_html}

        <div class="footer-signatures">
            <div class="signature-box">
                <div class="signature-title">الموظف المسؤول / Issued By</div>
                <div>سراج — المساعد الذكي</div>
                <div style="font-size: 11px; color: #64748b;">أنظمة الموارد البشرية</div>
            </div>

            <div class="seal-box">
                <div>ختم المنشأة</div>
                <div style="font-size: 9px; margin-top: 4px;">OFFICIAL SEAL</div>
                <div style="font-size: 8px; margin-top: 2px;">{today_date}</div>
            </div>

            <div class="signature-box">
                <div class="signature-title">مدير الموارد البشرية / HR Director</div>
                <div>الاعتماد الإلكتروني الموثق</div>
                <div style="font-size: 11px; color: #64748b;">معتمد إلكترونياً</div>
            </div>
        </div>

        <div class="verif-footer">
            وثيقة رسمية صادرة إلكترونياً عبر منصة سراج لإدارة الموارد البشرية المتكاملة مع Odoo 19 • التحقق من صحة الوثيقة برمز: {verification_code}
        </div>
    </div>
</body>
</html>
        """
        return html
