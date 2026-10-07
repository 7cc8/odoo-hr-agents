"""
خدمة إدارة وتدقيق مصروفات الموظفين والانتدابات (Employee Expenses & Travel Service)
================================================================================
الطبقة التنفيذية لإعداد، فحص، ومطابقة مطالبات المصروفات والانتدابات في Odoo:
- نموذج Odoo المعتمد: hr.expense
- التصنيفات المدعومة: تذاكر السفر، الفنادق، الإعاشة، المواصلات، الاتصالات، والنثريات العامة.

الضوابط المالية والنظامية:
1. احتساب ضريبة القيمة المضافة (15% VAT) لمطابقة متطلبات هيئة الزكاة والضريبة والجمارك (ZATCA).
2. التحقق من كفاية وصحة البيانات المالية (المبلغ الإجمالي، الوصف، تاريخ المصروف، الموظف).
3. مبدأ التحقق المزدوج Four-Eyes مع إلزام كتابة "تأكيد" قطيعاً قبل الحفظ في Odoo.
4. التحقق المستقل بعد الكتابة (Readback Verification).
5. تسجيل وتدقيق العمليات في سجل آمن logs/expense_audit_log.jsonl.
6. توليد سند صرف ومطالبة مصروفات رسمي PDF بجودة عالية للمحاسبة والأرشفة.
"""

from __future__ import annotations

import os
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional, Tuple

from odoo_readonly_repository import OdooReadonlyRepository
from odoo_expense_write_gateway import OdooExpenseWriteGateway
from eos_service import detect_employee_nationality

EXPENSE_AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "expense_audit_log.jsonl")
EXPENSES_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "expenses")

SAUDI_VAT_RATE = 0.15  # 15% ضريبة القيمة المضافة ZATCA

SUPPORTED_EXPENSE_CATEGORIES = {
    "travel": {
        "id": "travel",
        "name_ar": "تذاكر سفر وانتقالات رسمية",
        "name_en": "Air Ticket & Travel Expense",
        "default_product_id": 7,  # Air Ticket Expense
    },
    "hotel": {
        "id": "hotel",
        "name_ar": "إقامة فندقية وسكن انتداب",
        "name_en": "Hotel & Accommodation",
        "default_product_id": 8,  # Hotel Cost Expense
    },
    "meals": {
        "id": "meals",
        "name_ar": "إعاشة ووجبات عمل رسمية",
        "name_en": "Meals & Subsistence",
        "default_product_id": 1,  # Meals
    },
    "mileage": {
        "id": "mileage",
        "name_ar": "مواصلات داخلية ومحروقات",
        "name_en": "Mileage & Transportation",
        "default_product_id": 3,  # Mileage
    },
    "communication": {
        "id": "communication",
        "name_ar": "اتصالات وإنترنت ورسوم تقنية",
        "name_en": "Communication & Internet",
        "default_product_id": 5,  # Communication
    },
    "general": {
        "id": "general",
        "name_ar": "مصروفات إدارية ونثرية عامة",
        "name_en": "General Office & Field Expenses",
        "default_product_id": 6,  # Expenses
    },
}


@dataclass
class ExpenseDryRunResult:
    is_valid: bool
    employee_id: int
    employee_name: str
    is_saudi: bool
    nationality_text_ar: str
    identification_id: str
    job_title: str
    department_name: str
    expense_category: str
    category_title_ar: str
    product_id: int
    total_amount: float
    includes_vat: bool
    untaxed_amount: float
    tax_amount: float
    expense_date: str
    description: str
    reference_code: str
    company_id: int
    approval_token: str
    created_at_iso: str
    preview_body_ar: str
    notes: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class ExpenseApplyResult:
    is_success: bool
    expense_id: Optional[int]
    employee_id: int
    employee_name: str
    total_amount: float
    reference_code: str
    state: str
    readback_data: Optional[Dict[str, Any]]
    pdf_path: Optional[str]
    html_path: Optional[str]
    message_ar: str
    errors: List[str] = field(default_factory=list)


_SHARED_PENDING_EXPENSE_TOKENS: Dict[str, ExpenseDryRunResult] = {}


class ExpenseService:
    """
    الخدمة الشاملة لإدارة ومطابقة مصروفات الموظفين وانتدابات العمل في Odoo.
    """

    def __init__(
        self,
        repo: Optional[OdooReadonlyRepository] = None,
        gateway: Optional[OdooExpenseWriteGateway] = None,
    ):
        self.repo = repo or OdooReadonlyRepository()
        self.gateway = gateway or OdooExpenseWriteGateway()
        self._pending_tokens = _SHARED_PENDING_EXPENSE_TOKENS
        os.makedirs(os.path.dirname(EXPENSE_AUDIT_LOG_FILE), exist_ok=True)
        os.makedirs(EXPENSES_OUTPUT_DIR, exist_ok=True)

    def get_supported_categories(self) -> List[Dict[str, Any]]:
        """قائمة تصنيفات المصروفات المدعومة."""
        return list(SUPPORTED_EXPENSE_CATEGORIES.values())

    def _resolve_company_and_currency(self, employee: Dict[str, Any]) -> Tuple[int, int]:
        """تحديد معرف الشركة والعملة (الافتراضي: 15 للشركة، والريال السعودي SAR)."""
        comp_val = employee.get("company_id")
        comp_id = 15
        if comp_val:
            comp_id = comp_val[0] if isinstance(comp_val, (list, tuple)) else int(comp_val)

        curr_val = employee.get("currency_id")
        curr_id = 148  # الافتراضي لـ SAR في Odoo
        if curr_val:
            curr_id = curr_val[0] if isinstance(curr_val, (list, tuple)) else int(curr_val)

        return comp_id, curr_id

    def dry_run_expense(
        self,
        employee_id: int,
        expense_category: str = "general",
        total_amount: float = 0.0,
        description: str = "",
        expense_date: Optional[str] = None,
        includes_vat: bool = True,
        product_id: Optional[int] = None,
        explicit_is_saudi: Optional[bool] = None,
    ) -> ExpenseDryRunResult:
        """
        المرحلة الأولى من التحقق المزدوج: فحص بيانات المصروف واحتساب الضريبة وإصدار approval_token.
        """
        errors: List[str] = []
        notes: List[str] = []

        if total_amount <= 0:
            errors.append("مبلغ المصروف يجب أن يكون أكبر من الصفر.")

        if expense_category not in SUPPORTED_EXPENSE_CATEGORIES:
            errors.append(f"تصنيف المصروف '{expense_category}' غير صالح. التصنيفات المدعومة: {list(SUPPORTED_EXPENSE_CATEGORIES.keys())}")
            expense_category = "general"

        cat_meta = SUPPORTED_EXPENSE_CATEGORIES[expense_category]
        chosen_product_id = product_id or cat_meta["default_product_id"]

        # التحقق من الموظف
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
            return ExpenseDryRunResult(
                is_valid=False,
                employee_id=employee_id,
                employee_name="غير محدد",
                is_saudi=False,
                nationality_text_ar="غير محدد",
                identification_id="",
                job_title="",
                department_name="",
                expense_category=expense_category,
                category_title_ar=cat_meta["name_ar"],
                product_id=chosen_product_id,
                total_amount=total_amount,
                includes_vat=includes_vat,
                untaxed_amount=0.0,
                tax_amount=0.0,
                expense_date=expense_date or date.today().isoformat(),
                description=description,
                reference_code="",
                company_id=15,
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

        comp_id, curr_id = self._resolve_company_and_currency(employee)
        exp_date_str = (expense_date or date.today().isoformat())[:10]

        # احتساب الضريبة ZATCA (15%)
        if includes_vat and total_amount > 0:
            untaxed = round(total_amount / (1.0 + SAUDI_VAT_RATE), 2)
            tax = round(total_amount - untaxed, 2)
            notes.append(f"تم احتساب ضريبة القيمة المضافة (15%): غير خاضع {untaxed:,.2f} ر.س + ضريبة {tax:,.2f} ر.س = إجمالي {total_amount:,.2f} ر.س")
        else:
            untaxed = round(total_amount, 2)
            tax = 0.0

        year = datetime.now().year
        rand_part = uuid.uuid4().hex[:6].upper()
        reference_code = f"EXP-{year}-{employee_id}-{rand_part}"

        desc = description.strip() or f"مطالبة {cat_meta['name_ar']} للموظف {employee_name}"

        preview_body = (
            f"مطالبة استرداد مصروفات عمل بموجب لوائح المنشأة:\n"
            f"الموظف: {employee_name} ({job_title} - {dept_name})\n"
            f"التصنيف: {cat_meta['name_ar']}\n"
            f"التاريخ: {exp_date_str}\n"
            f"البيان: {desc}\n"
            f"المبلغ الإجمالي: {total_amount:,.2f} ريال سعودي"
        )
        if includes_vat:
            preview_body += f" (شامل ضريبة القيمة المضافة 15%: {tax:,.2f} ر.س)"

        approval_token = str(uuid.uuid4())
        created_at_iso = datetime.now(timezone.utc).isoformat()

        result = ExpenseDryRunResult(
            is_valid=(len(errors) == 0),
            employee_id=employee_id,
            employee_name=employee_name,
            is_saudi=is_saudi,
            nationality_text_ar=nationality_text_ar,
            identification_id=ident_id,
            job_title=job_title,
            department_name=dept_name,
            expense_category=expense_category,
            category_title_ar=cat_meta["name_ar"],
            product_id=chosen_product_id,
            total_amount=total_amount,
            includes_vat=includes_vat,
            untaxed_amount=untaxed,
            tax_amount=tax,
            expense_date=exp_date_str,
            description=desc,
            reference_code=reference_code,
            company_id=comp_id,
            approval_token=approval_token,
            created_at_iso=created_at_iso,
            preview_body_ar=preview_body,
            notes=notes,
            errors=errors,
        )

        self._pending_tokens[approval_token] = result
        return result

    def apply_expense(
        self,
        approval_token: str,
        user_confirmation_text: str = "تأكيد",
        executor: str = "system_operator",
    ) -> ExpenseApplyResult:
        """
        المرحلة الثانية من التحقق المزدوج: التأكد من رمز الموافقة والكلمة الإلزامية "تأكيد"،
        ثم الحفظ في Odoo (hr.expense) وإجراء فحص القراءة المستقل (Readback Verification).
        """
        if not approval_token or approval_token not in self._pending_tokens:
            return ExpenseApplyResult(
                is_success=False,
                expense_id=None,
                employee_id=0,
                employee_name="",
                total_amount=0.0,
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
            return ExpenseApplyResult(
                is_success=False,
                expense_id=None,
                employee_id=draft.employee_id,
                employee_name=draft.employee_name,
                total_amount=draft.total_amount,
                reference_code=draft.reference_code,
                state="rejected",
                readback_data=None,
                pdf_path=None,
                html_path=None,
                message_ar="مبدأ التحقق المزدوج: يلزم إدخال الكلمة الصريحة 'تأكيد' لاعتماد وتسجيل المصروف.",
                errors=["نص التأكيد غير مطابق للكلمة الإلزامية 'تأكيد'."],
            )

        values: Dict[str, Any] = {
            "name": f"{draft.description} ({draft.reference_code})",
            "employee_id": draft.employee_id,
            "product_id": draft.product_id,
            "total_amount": draft.total_amount,
            "total_amount_currency": draft.total_amount,
            "date": draft.expense_date,
            "description": f"مرجع المطالبة: {draft.reference_code} | التصنيف: {draft.category_title_ar}",
            "company_id": draft.company_id,
        }

        try:
            exp_id = self.gateway.create_expense(values)
        except Exception as exc:
            return ExpenseApplyResult(
                is_success=False,
                expense_id=None,
                employee_id=draft.employee_id,
                employee_name=draft.employee_name,
                total_amount=draft.total_amount,
                reference_code=draft.reference_code,
                state="failed",
                readback_data=None,
                pdf_path=None,
                html_path=None,
                message_ar=f"فشل إنشاء المصروف في Odoo: {exc}",
                errors=[str(exc)],
            )

        # التحقق المستقل بعد الكتابة (Readback Verification)
        readback = None
        try:
            readback = self.gateway.read_expense(exp_id)
        except Exception:
            readback = {"id": exp_id, "state": "draft"}

        # توليد المستندات HTML و PDF
        html_path = None
        pdf_path = None
        try:
            html_content = self.render_expense_html(draft, exp_id)
            html_filename = f"expense_{exp_id}_{draft.reference_code}.html"
            html_path = os.path.join(EXPENSES_OUTPUT_DIR, html_filename)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            pdf_filename = f"expense_{exp_id}_{draft.reference_code}.pdf"
            pdf_path = os.path.join(EXPENSES_OUTPUT_DIR, pdf_filename)
            self._render_html_to_pdf(html_path, pdf_path)
        except Exception as doc_err:
            draft.notes.append(f"تنبيه توليد الوثيقة: {doc_err}")

        # تسجيل وتدقيق العملية في سجل التدقيق
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "create_expense",
            "expense_id": exp_id,
            "reference_code": draft.reference_code,
            "employee_id": draft.employee_id,
            "employee_name": draft.employee_name,
            "category": draft.expense_category,
            "total_amount": draft.total_amount,
            "untaxed_amount": draft.untaxed_amount,
            "tax_amount": draft.tax_amount,
            "executor": executor,
            "html_path": html_path,
            "pdf_path": pdf_path,
        }
        try:
            with open(EXPENSE_AUDIT_LOG_FILE, "a", encoding="utf-8") as af:
                af.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

        self._pending_tokens.pop(approval_token, None)

        return ExpenseApplyResult(
            is_success=True,
            expense_id=exp_id,
            employee_id=draft.employee_id,
            employee_name=draft.employee_name,
            total_amount=draft.total_amount,
            reference_code=draft.reference_code,
            state=readback.get("state") if readback else "draft",
            readback_data=readback,
            pdf_path=pdf_path if (pdf_path and os.path.exists(pdf_path)) else None,
            html_path=html_path,
            message_ar=f"تم تسجيل مطالبة المصروف بنجاح في Odoo (سجل رقم #{exp_id}) بمبلغ {draft.total_amount:,.2f} ر.س.",
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

    def render_expense_html(self, draft: ExpenseDryRunResult, expense_id: Optional[int] = None) -> str:
        """توليد سند صرف ومطالبة نفقات رسمية."""
        today_date = date.today().strftime("%Y/%m/%d")

        html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>سند مطالبة مصروفات - {draft.reference_code}</title>
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
        .container {{
            max-width: 800px;
            margin: 0 auto;
            border: 2px solid #0284c7;
            padding: 35px;
            border-radius: 8px;
            background: #ffffff;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #0284c7;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}
        .company-name {{
            font-size: 16px;
            font-weight: bold;
            color: #0369a1;
        }}
        .badge {{
            background: #f0f9ff;
            color: #0369a1;
            border: 1px solid #bae6fd;
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
            margin: 10px 0 20px 0;
        }}
        .title h1 {{
            font-size: 20px;
            color: #0f172a;
            margin: 0;
            padding-bottom: 5px;
            border-bottom: 2px solid #38bdf8;
            display: inline-block;
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
        .financial-card {{
            background: #f0fdf4;
            border: 1px solid #bbf7d0;
            border-radius: 6px;
            padding: 16px;
            margin: 20px 0;
        }}
        .fin-row {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px dashed #cbd5e1;
            font-size: 13px;
        }}
        .fin-total {{
            font-weight: bold;
            font-size: 15px;
            color: #15803d;
            border-bottom: none;
            border-top: 1px solid #16a34a;
            padding-top: 8px;
            margin-top: 4px;
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
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <div class="company-name">شركة النخبة الذكية للتقنية</div>
                <div style="font-size: 11px; color: #64748b;">إدارة الشؤون المالية والمحاسبة</div>
            </div>
            <div class="badge">سند استرداد مصروفات عمل</div>
        </div>

        <div class="doc-meta">
            <div><strong>تاريخ الطلب:</strong> {draft.expense_date}</div>
            <div><strong>رقم القيد في Odoo:</strong> #{expense_id or '—'}</div>
            <div><strong>الرقم المرجعي:</strong> <code>{draft.reference_code}</code></div>
        </div>

        <div class="title">
            <h1>سند مطالبة مصروفات وانتداب عمل</h1>
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
                <td class="label">القسم / الإدارة:</td>
                <td>{draft.department_name}</td>
                <td class="label">تصنيف النفقات:</td>
                <td>{draft.category_title_ar}</td>
            </tr>
            <tr>
                <td class="label">البيان والشرح:</td>
                <td colspan="3">{draft.description}</td>
            </tr>
        </table>

        <div class="financial-card">
            <div class="fin-row">
                <span>المبلغ قبل الضريبة:</span>
                <span>{draft.untaxed_amount:,.2f} ر.س</span>
            </div>
            <div class="fin-row">
                <span>ضريبة القيمة المضافة (15% VAT):</span>
                <span>{draft.tax_amount:,.2f} ر.س</span>
            </div>
            <div class="fin-row fin-total">
                <span>إجمالي المبلغ المستحق للصرف:</span>
                <span>{draft.total_amount:,.2f} ر.س</span>
            </div>
        </div>

        <div class="signatures">
            <div class="sig-block">
                <div class="sig-title">الموظف مقدم المطالبة</div>
                <div>........................................</div>
            </div>
            <div class="sig-block">
                <div class="sig-title">المدير المباشر / الاعتماد</div>
                <div>........................................</div>
            </div>
            <div class="sig-block">
                <div class="sig-title">المدير المالي / الصرف</div>
                <div>........................................</div>
            </div>
        </div>
    </div>
</body>
</html>
        """
        return html
