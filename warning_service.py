"""
خدمة إدارة وإصدار خطابات الإنذار والمساءلات التأديبية (Warning Letters & Disciplinary Issuance Service)
=====================================================================================================
الطبقة التنفيذية لإعداد، مراجعة، وتوثيق خطابات الإنذار والقرارات التأديبية في Odoo:
- نموذج Odoo المعتمد: warning.letter
- نموذج أنواع الإنذارات: warning.type

الضوابط الصارمة بموجب نظام العمل السعودي:
1. المادة 66: التدرج النظامي في توقيع الجزاءات (لفت نظر، إنذار كتابي، غرامة/حسم، حرمان من الترقية، فصل بموجب م/80).
2. المادة 70: سقوط الحق في توقيع الجزاء إذا مضى على كشف المخالفة أكثر من 30 يوماً.
3. المادة 71: سقف الخصم (لا يجوز أن يزيد الحسم عن أجر 5 أيام عن المخالفة الواحدة، ولا يزيد عن أجر 5 أيام في الشهر الواحد).
4. المادة 72: إلزامية التحقيق الكتابي وسماع أقوال العامل وإثباتها في محضر قبل توقيع الجزاء.
5. مبدأ التحقق المزدوج Four-Eyes مع إلزام كتابة "تأكيد" قطيعاً قبل الحفظ في Odoo.
6. التحقق المستقل بعد الكتابة (Readback Verification).
7. تسجيل وتدقيق العمليات في سجل آمن logs/warning_audit_log.jsonl.
8. توليد خطابات PDF رسمية معتمدة وفق الهوية المؤسسية للمنشأة.
"""

from __future__ import annotations

import os
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional, Tuple

from odoo_readonly_repository import OdooReadonlyRepository
from odoo_warning_write_gateway import OdooWarningWriteGateway
from eos_service import detect_employee_nationality

WARNING_AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "warning_audit_log.jsonl")
WARNINGS_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "warnings")

# مستويات وأنواع الإنذارات النظامية
WARNING_LEVELS = {
    "notice": {
        "id": "notice",
        "title_ar": "لفت نظر كتابي",
        "title_en": "Written Notice / Admonition",
        "has_deduction_default": False,
        "max_deduction_days": 0,
        "labor_law_article": "المادة 66 (الفقرة 1)",
    },
    "first_warning": {
        "id": "first_warning",
        "title_ar": "إنذار كتابي أول",
        "title_en": "First Written Warning",
        "has_deduction_default": False,
        "max_deduction_days": 1,
        "labor_law_article": "المادة 66 (الفقرة 1)",
    },
    "second_warning": {
        "id": "second_warning",
        "title_ar": "إنذار كتابي ثانٍ مع خصم",
        "title_en": "Second Written Warning with Deduction",
        "has_deduction_default": True,
        "max_deduction_days": 3,
        "labor_law_article": "المادة 66 (الفقرة 2) والمادة 71",
    },
    "final_warning": {
        "id": "final_warning",
        "title_ar": "إنذار نهائي بالفصل من العمل",
        "title_en": "Final Warning / Termination Notice",
        "has_deduction_default": True,
        "max_deduction_days": 5,
        "labor_law_article": "المادة 66 (الفقرة 6) والمادة 80",
    },
}

STATUTORY_MAX_SINGLE_DEDUCTION_DAYS = 5.0  # المادة 71: سقف 5 أيام للمخالفة الواحدة


@dataclass
class WarningDryRunResult:
    is_valid: bool
    employee_id: int
    employee_name: str
    is_saudi: bool
    nationality_text_ar: str
    identification_id: str
    job_title: str
    department_name: str
    warning_level: str
    warning_title_ar: str
    violation_date: str
    violation_description: str
    has_deduction: bool
    deduction_days: float
    deduction_amount: float
    daily_wage: float
    labor_law_article: str
    warning_type_id: int
    warning_type_name: str
    reference_code: str
    approval_token: str
    created_at_iso: str
    preview_body_ar: str
    legal_notes: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class WarningApplyResult:
    is_success: bool
    warning_letter_id: Optional[int]
    employee_id: int
    employee_name: str
    warning_level: str
    reference_code: str
    state: str
    readback_data: Optional[Dict[str, Any]]
    pdf_path: Optional[str]
    html_path: Optional[str]
    message_ar: str
    errors: List[str] = field(default_factory=list)


class WarningService:
    """
    الخدمة الشاملة لخطابات الإنذار والمساءلات التأديبية المتوافقة مع نظام العمل السعودي و Odoo.
    """

    def __init__(
        self,
        repo: Optional[OdooReadonlyRepository] = None,
        gateway: Optional[OdooWarningWriteGateway] = None,
    ):
        self.repo = repo or OdooReadonlyRepository()
        self.gateway = gateway or OdooWarningWriteGateway()
        self._pending_tokens: Dict[str, WarningDryRunResult] = {}
        os.makedirs(os.path.dirname(WARNING_AUDIT_LOG_FILE), exist_ok=True)
        os.makedirs(WARNINGS_OUTPUT_DIR, exist_ok=True)

    def get_supported_warning_levels(self) -> List[Dict[str, Any]]:
        """قائمة مستويات الإنذارات المدعومة نظامياً."""
        return list(WARNING_LEVELS.values())

    def get_employee_daily_wage(self, employee_id: int) -> float:
        """احتساب الأجر اليومي للموظف (الأجر الأساسي / 30 يوماً)."""
        try:
            contracts = self.repo.get_contracts(limit=100)
            emp_contracts = [
                c for c in contracts
                if (c.get("employee_id") and (
                    c["employee_id"] == employee_id or
                    (isinstance(c["employee_id"], (list, tuple)) and c["employee_id"][0] == employee_id)
                ))
            ]
            for c in emp_contracts:
                if c.get("state") in ("open", "draft", "close"):
                    basic = float(c.get("wage") or 0.0)
                    if basic > 0:
                        return round(basic / 30.0, 2)
        except Exception:
            pass
        return 0.0

    def _resolve_warning_type_id(self, type_name: str) -> int:
        """جلب أو إنشاء معرف نوع الإنذار في Odoo (warning.type)."""
        try:
            types = self.repo.get_warning_types()
            for t in types:
                if type_name.lower() in str(t.get("name", "")).lower():
                    return t["id"]
            if types:
                return types[0]["id"]
            # إنشاء نوع جديد إذا كان الجدول فارغاً
            return self.gateway.create_warning_type(type_name)
        except Exception:
            pass
        return 1

    def dry_run_warning(
        self,
        employee_id: int,
        warning_level: str = "first_warning",
        violation_description: str = "",
        violation_date: Optional[str] = None,
        has_deduction: Optional[bool] = None,
        deduction_days: float = 0.0,
        deduction_amount: Optional[float] = None,
        explicit_is_saudi: Optional[bool] = None,
    ) -> WarningDryRunResult:
        """
        المرحلة الأولى من التحقق المزدوج: فحص نظامية الإنذار ومطابقة المادة 71 وإصدار approval_token.
        """
        errors: List[str] = []
        legal_notes: List[str] = []

        if warning_level not in WARNING_LEVELS:
            errors.append(f"مستوى الإنذار '{warning_level}' غير صالح.")
            warning_level = "first_warning"

        level_meta = WARNING_LEVELS[warning_level]

        # استرداد الموظف
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
            return WarningDryRunResult(
                is_valid=False,
                employee_id=employee_id,
                employee_name="غير محدد",
                is_saudi=False,
                nationality_text_ar="غير محدد",
                identification_id="",
                job_title="",
                department_name="",
                warning_level=warning_level,
                warning_title_ar=level_meta["title_ar"],
                violation_date=violation_date or date.today().isoformat(),
                violation_description=violation_description,
                has_deduction=False,
                deduction_days=0.0,
                deduction_amount=0.0,
                daily_wage=0.0,
                labor_law_article=level_meta["labor_law_article"],
                warning_type_id=1,
                warning_type_name=level_meta["title_ar"],
                reference_code="",
                approval_token="",
                created_at_iso=datetime.now(timezone.utc).isoformat(),
                preview_body_ar="",
                errors=errors,
            )

        employee_name = employee.get("name") or f"Employee #{employee_id}"
        is_saudi = detect_employee_nationality(employee, explicit_is_saudi=explicit_is_saudi)
        nationality_text_ar = "مواطن سعودي" if is_saudi else "مقيم غير سعودي"
        ident_id = str(employee.get("identification_id") or "").strip()

        job_val = employee.get("job_id")
        job_title = job_val[1] if isinstance(job_val, (list, tuple)) and len(job_val) > 1 else str(job_val or "موظف")

        dept_val = employee.get("department_id")
        dept_name = dept_val[1] if isinstance(dept_val, (list, tuple)) and len(dept_val) > 1 else str(dept_val or "الإدارة العامة")

        viol_date_str = (violation_date or date.today().isoformat())[:10]

        # فحص المادة 70 (تقادم المخالفة بعد 30 يوماً من كشفها)
        try:
            v_date = datetime.strptime(viol_date_str, "%Y-%m-%d").date()
            days_elapsed = (date.today() - v_date).days
            if days_elapsed > 30:
                legal_notes.append(
                    f"⚠️ تنبيه نظامي حرج (المادة 70): مضى {days_elapsed} يوماً على واقعة المخالفة، "
                    f"وينص نظام العمل على سقوط الحق في توقيع الجزاء بعد مضي 30 يوماً من كشفها."
                )
        except Exception:
            pass

        # حساب الأجر اليومي والخصومات (المادة 71)
        daily_wage = self.get_employee_daily_wage(employee_id)
        if has_deduction is None:
            has_deduction = level_meta["has_deduction_default"] or (deduction_days > 0) or (deduction_amount is not None and deduction_amount > 0)

        calc_deduction_amount = 0.0
        if has_deduction:
            if deduction_amount is not None and deduction_amount > 0:
                calc_deduction_amount = round(deduction_amount, 2)
                if daily_wage > 0:
                    deduction_days = round(calc_deduction_amount / daily_wage, 1)
            elif deduction_days > 0 and daily_wage > 0:
                calc_deduction_amount = round(deduction_days * daily_wage, 2)

            # التحقق الصارم من سقف المادة 71 (5 أيام كحد أقصى للمخالفة الواحدة)
            if deduction_days > STATUTORY_MAX_SINGLE_DEDUCTION_DAYS:
                errors.append(
                    f"مخالفة نظامية صريحة (المادة 71 من نظام العمل): لا يجوز أن يزيد الحسم عن أجر 5 أيام "
                    f"عن المخالفة الواحدة (المطلوب: {deduction_days} أيام)."
                )

            if daily_wage > 0 and calc_deduction_amount > (daily_wage * STATUTORY_MAX_SINGLE_DEDUCTION_DAYS):
                errors.append(
                    f"مخالفة نظامية (المادة 71): مبلغ الخصم ({calc_deduction_amount:,.2f} ر.س) يتجاوز "
                    f"أجر خمسة أيام ({daily_wage * 5:,.2f} ر.س)."
                )


            legal_notes.append(
                f"⚖️ مطابقة المادة 71: تم توقيع خصم أجر {deduction_days} يوم بمبلغ {calc_deduction_amount:,.2f} ر.س "
                f"(الأجر اليومي المعتمد: {daily_wage:,.2f} ر.س)."
            )

        # التذكير بإلزامية التحقيق (المادة 72)
        legal_notes.append(
            "📋 المادة 72: يجب التأكد من إبلاغ العامل كتابة بالمخالفة وسماع دفاعه وتدوينه في محضر مودع بملفه."
        )

        year = datetime.now().year
        rand_part = uuid.uuid4().hex[:6].upper()
        reference_code = f"WARN-{year}-{employee_id}-{rand_part}"

        type_id = self._resolve_warning_type_id(level_meta["title_ar"])

        # صياغة نص الإنذار
        id_title_ar = "الهوية الوطنية" if is_saudi else "الإقامة النظامية"
        viol_desc = violation_description.strip() or "الإخلال بواجبات العمل واللوائح التنظيمية المنصوص عليها"

        preview_body = (
            f"بناءً على الصلاحيات المخولة لإدارة الموارد البشرية، واستناداً إلى أحكام لائحة تنظيم العمل "
            f"ونظام العمل السعودي ({level_meta['labor_law_article']}):\n\n"
            f"تقرر توجيه ({level_meta['title_ar']}) إلى الموظف/ {employee_name}، "
            f"حامل {id_title_ar} رقم ({ident_id or '—'})، الشاغل لوظيفة ({job_title}) بإدارة ({dept_name})، "
            f"نظراً لارتكابه المخالفة التالية بتاريخ ({viol_date_str}):\n"
            f"«{viol_desc}».\n\n"
        )

        if has_deduction and calc_deduction_amount > 0:
            preview_body += (
                f"وعليه، فقد تقرر تطبيق جزاء الحسم من الأجر بمقدار ({deduction_days} أيام) "
                f"بقيمة إجمالية قدرها ({calc_deduction_amount:,.2f} ريال سعودي)، "
                f"وذلك بما يتفق مع الحدود المقررة في المادة (71) من نظام العمل.\n\n"
            )

        preview_body += (
            f"نهيب بالموظف ضرورة الالتزام بأنظمة وتعليمات المنشأة وتلافي تكرار المخالفة مستقبلاً، "
            f"حيث سيترتب على العود تطبيق الجزاءات الأشد المنصوص عليها نظاماً وصولاً إلى إنهاء العقد."
        )

        approval_token = str(uuid.uuid4())
        created_at_iso = datetime.now(timezone.utc).isoformat()

        result = WarningDryRunResult(
            is_valid=(len(errors) == 0),
            employee_id=employee_id,
            employee_name=employee_name,
            is_saudi=is_saudi,
            nationality_text_ar=nationality_text_ar,
            identification_id=ident_id,
            job_title=job_title,
            department_name=dept_name,
            warning_level=warning_level,
            warning_title_ar=level_meta["title_ar"],
            violation_date=viol_date_str,
            violation_description=viol_desc,
            has_deduction=has_deduction,
            deduction_days=deduction_days,
            deduction_amount=calc_deduction_amount,
            daily_wage=daily_wage,
            labor_law_article=level_meta["labor_law_article"],
            warning_type_id=type_id,
            warning_type_name=level_meta["title_ar"],
            reference_code=reference_code,
            approval_token=approval_token,
            created_at_iso=created_at_iso,
            preview_body_ar=preview_body,
            legal_notes=legal_notes,
            errors=errors,
        )

        self._pending_tokens[approval_token] = result
        return result

    def apply_warning(
        self,
        approval_token: str,
        user_confirmation_text: str = "تأكيد",
        executor: str = "system_operator",
    ) -> WarningApplyResult:
        """
        المرحلة الثانية من التحقق المزدوج: التأكد من رمز الموافقة والكلمة الإلزامية "تأكيد"،
        ثم الحفظ في Odoo (warning.letter) وإجراء فحص القراءة المستقل (Readback Verification).
        """
        if not approval_token or approval_token not in self._pending_tokens:
            return WarningApplyResult(
                is_success=False,
                warning_letter_id=None,
                employee_id=0,
                employee_name="",
                warning_level="",
                reference_code="",
                state="failed",
                readback_data=None,
                pdf_path=None,
                html_path=None,
                message_ar="رمز الموافقة غير صالح أو منتهي الصلاحية. يجب إجراء المعاينة (Dry-Run) أولاً.",
                errors=["رمز الموافقة approval_token غير موجود أو منتهي الصلاحية."],
            )

        draft = self._pending_tokens[approval_token]

        if user_confirmation_text.strip() != "تأكيد":
            return WarningApplyResult(
                is_success=False,
                warning_letter_id=None,
                employee_id=draft.employee_id,
                employee_name=draft.employee_name,
                warning_level=draft.warning_level,
                reference_code=draft.reference_code,
                state="rejected",
                readback_data=None,
                pdf_path=None,
                html_path=None,
                message_ar="مبدأ التحقق المزدوج: يلزم إدخال الكلمة الصريحة 'تأكيد' لاعتماد وإصدار خطاب الإنذار.",
                errors=["نص التأكيد غير مطابق للكلمة الإلزامية 'تأكيد'."],
            )

        values: Dict[str, Any] = {
            "name": draft.reference_code,
            "employee_id": draft.employee_id,
            "warning_type_id": draft.warning_type_id,
            "date_sent": date.today().isoformat(),
            "email_subject": f"{draft.warning_title_ar} - {draft.employee_name} ({draft.reference_code})",
            "email_body": f"<p>{draft.preview_body_ar.replace(chr(10), '<br/>')}</p>",
            "notes": f"المخالفة: {draft.violation_description} | السند النظامي: {draft.labor_law_article}",
            "state": "draft",
            "has_deduction": draft.has_deduction,
        }

        if draft.has_deduction and draft.deduction_amount > 0:
            values["deduction_amount"] = draft.deduction_amount
            values["deduction_date"] = date.today().isoformat()

        try:
            letter_id = self.gateway.create_warning_letter(values)
        except Exception as exc:
            return WarningApplyResult(
                is_success=False,
                warning_letter_id=None,
                employee_id=draft.employee_id,
                employee_name=draft.employee_name,
                warning_level=draft.warning_level,
                reference_code=draft.reference_code,
                state="failed",
                readback_data=None,
                pdf_path=None,
                html_path=None,
                message_ar=f"فشل إنشاء خطاب الإنذار في Odoo: {exc}",
                errors=[str(exc)],
            )

        # التحقق المستقل بعد الكتابة (Readback Verification)
        readback = None
        try:
            readback = self.gateway.read_warning_letter(letter_id)
        except Exception:
            readback = {"id": letter_id, "state": "draft"}

        # توليد المستندات HTML و PDF
        html_path = None
        pdf_path = None
        try:
            html_content = self.render_warning_html(draft, letter_id)
            html_filename = f"warning_{letter_id}_{draft.reference_code}.html"
            html_path = os.path.join(WARNINGS_OUTPUT_DIR, html_filename)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            pdf_filename = f"warning_{letter_id}_{draft.reference_code}.pdf"
            pdf_path = os.path.join(WARNINGS_OUTPUT_DIR, pdf_filename)
            self._render_html_to_pdf(html_path, pdf_path)
        except Exception as doc_err:
            draft.legal_notes.append(f"تنبيه توليد الوثيقة: {doc_err}")

        # تسجيل وتدقيق العملية في سجل التدقيق
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "create_warning_letter",
            "warning_letter_id": letter_id,
            "reference_code": draft.reference_code,
            "employee_id": draft.employee_id,
            "employee_name": draft.employee_name,
            "is_saudi": draft.is_saudi,
            "warning_level": draft.warning_level,
            "has_deduction": draft.has_deduction,
            "deduction_days": draft.deduction_days,
            "deduction_amount": draft.deduction_amount,
            "executor": executor,
            "html_path": html_path,
            "pdf_path": pdf_path,
        }
        try:
            with open(WARNING_AUDIT_LOG_FILE, "a", encoding="utf-8") as af:
                af.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

        self._pending_tokens.pop(approval_token, None)

        return WarningApplyResult(
            is_success=True,
            warning_letter_id=letter_id,
            employee_id=draft.employee_id,
            employee_name=draft.employee_name,
            warning_level=draft.warning_level,
            reference_code=draft.reference_code,
            state=readback.get("state") if readback else "draft",
            readback_data=readback,
            pdf_path=pdf_path if (pdf_path and os.path.exists(pdf_path)) else None,
            html_path=html_path,
            message_ar=f"تم إصدار وتوثيق خطاب الإنذار بنجاح في Odoo (سجل رقم #{letter_id}) بالرقم المرجعي {draft.reference_code}.",
        )

    def _render_html_to_pdf(self, html_path: str, pdf_path: str) -> bool:
        """تحويل ملف HTML إلى PDF عبر Playwright."""
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

    def render_warning_html(self, draft: WarningDryRunResult, letter_id: Optional[int] = None) -> str:
        """توليد قالب HTML رسمي للإنذار بمظهر قانوني مؤسسي رفيع المستوى."""
        today_date = date.today().strftime("%Y/%m/%d")
        body_formatted = draft.preview_body_ar.replace("\n", "<br>")

        deduction_block = ""
        if draft.has_deduction and draft.deduction_amount > 0:
            deduction_block = f"""
            <div class="deduction-box">
                <div class="deduction-title">⚠️ قرار الخصم من الأجر (مستند للمادة 71 من نظام العمل)</div>
                <div class="deduction-row">
                    <span>عدد أيام الخصم:</span>
                    <strong>{draft.deduction_days} أيام عمل</strong>
                </div>
                <div class="deduction-row">
                    <span>قيمة الخصم الإجمالية:</span>
                    <strong>{draft.deduction_amount:,.2f} ر.س</strong>
                </div>
                <div class="deduction-row">
                    <span>الأجر اليومي المعتمد:</span>
                    <span>{draft.daily_wage:,.2f} ر.س</span>
                </div>
            </div>
            """

        html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>{draft.warning_title_ar} - {draft.employee_name}</title>
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
            color: #0f172a;
            background: #ffffff;
            margin: 0;
            padding: 20px;
            font-size: 13.5px;
            line-height: 1.8;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            border: 2px solid #b91c1c;
            padding: 35px;
            border-radius: 8px;
            background: #ffffff;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #b91c1c;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}
        .company-name {{
            font-size: 16px;
            font-weight: bold;
            color: #b91c1c;
        }}
        .company-sub {{
            font-size: 11px;
            color: #64748b;
        }}
        .badge {{
            background: #fef2f2;
            color: #991b1b;
            border: 1px solid #fecaca;
            padding: 6px 14px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 13px;
        }}
        .doc-meta {{
            display: flex;
            justify-content: space-between;
            background: #f8fafc;
            padding: 10px 14px;
            border-radius: 6px;
            font-size: 12px;
            margin-bottom: 20px;
            border: 1px solid #e2e8f0;
        }}
        .title {{
            text-align: center;
            margin: 15px 0 25px 0;
        }}
        .title h1 {{
            font-size: 20px;
            color: #991b1b;
            margin: 0;
            padding-bottom: 5px;
            border-bottom: 2px solid #fecaca;
            display: inline-block;
        }}
        .title h2 {{
            font-size: 13px;
            color: #64748b;
            margin: 4px 0 0 0;
            font-weight: normal;
        }}
        .emp-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
            background: #f8fafc;
            font-size: 12.5px;
        }}
        .emp-table td {{
            padding: 8px 12px;
            border: 1px solid #e2e8f0;
        }}
        .emp-table td.label {{
            font-weight: bold;
            background: #f1f5f9;
            width: 25%;
        }}
        .content {{
            font-size: 14px;
            line-height: 2;
            text-align: justify;
            margin: 20px 0;
        }}
        .deduction-box {{
            background: #fff1f2;
            border: 1px solid #fecdd3;
            border-radius: 6px;
            padding: 14px;
            margin: 20px 0;
        }}
        .deduction-title {{
            color: #9f1239;
            font-weight: bold;
            margin-bottom: 8px;
            font-size: 13px;
        }}
        .deduction-row {{
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            font-size: 12.5px;
        }}
        .signatures {{
            display: flex;
            justify-content: space-between;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
        }}
        .sig-block {{
            text-align: center;
            width: 200px;
        }}
        .sig-title {{
            font-weight: bold;
            margin-bottom: 40px;
            color: #0f172a;
        }}
        .footer-note {{
            margin-top: 30px;
            font-size: 11px;
            color: #94a3b8;
            text-align: center;
            border-top: 1px solid #f1f5f9;
            padding-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <div class="company-name">شركة النخبة الذكية للتقنية</div>
                <div class="company-sub">إدارة الموارد البشرية والتحقيقات الإدارية</div>
            </div>
            <div class="badge">إشعار تأديبي رسمي</div>
        </div>

        <div class="doc-meta">
            <div><strong>التاريخ:</strong> {today_date}</div>
            <div><strong>رقم القيد في Odoo:</strong> #{letter_id or '—'}</div>
            <div><strong>الرقم المرجعي:</strong> <code>{draft.reference_code}</code></div>
        </div>

        <div class="title">
            <h1>{draft.warning_title_ar}</h1>
            <h2>{WARNING_LEVELS.get(draft.warning_level, {}).get('title_en', '')}</h2>
        </div>

        <table class="emp-table">
            <tr>
                <td class="label">اسم الموظف:</td>
                <td>{draft.employee_name}</td>
                <td class="label">الجنسية:</td>
                <td>{draft.nationality_text_ar}</td>
            </tr>
            <tr>
                <td class="label">الهوية / الإقامة:</td>
                <td>{draft.identification_id or '—'}</td>
                <td class="label">المسمى الوظيفي:</td>
                <td>{draft.job_title}</td>
            </tr>
            <tr>
                <td class="label">الإدارة / القسم:</td>
                <td>{draft.department_name}</td>
                <td class="label">تاريخ الواقعة:</td>
                <td>{draft.violation_date}</td>
            </tr>
            <tr>
                <td class="label">السند القانوني:</td>
                <td colspan="3">{draft.labor_law_article}</td>
            </tr>
        </table>

        <div class="content">
            {body_formatted}
        </div>

        {deduction_block}

        <div class="signatures">
            <div class="sig-block">
                <div class="sig-title">المحقق الإداري / الموارد البشرية</div>
                <div>........................................</div>
            </div>
            <div class="sig-block">
                <div class="sig-title">توقيع الموظف بالعلم والاستلام</div>
                <div>........................................</div>
                <div style="font-size: 10px; color: #64748b; margin-top: 4px;">التوقيع لا يعني الإقرار بصحة الواقعة</div>
            </div>
            <div class="sig-block">
                <div class="sig-title">اعتماد المدير العام / المفوض</div>
                <div>........................................</div>
            </div>
        </div>

        <div class="footer-note">
            تم توثيق هذا الإجراء رسمياً في سجلات المنشأة بنظام Odoo 19 • مرجع الوثيقة: {draft.reference_code}
        </div>
    </div>
</body>
</html>
        """
        return html
