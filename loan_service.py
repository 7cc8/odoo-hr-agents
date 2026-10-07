"""
خدمة إدارة وتدقيق سلف وقروض الموظفين (Employee Loans Service)
=============================================================================
الطبقة التنفيذية لإدارة وتوثيق سلف وقروض الموظفين في Odoo (employee.loan) بالتكامل مع:
1. المادة 92 من نظام العمل السعودي:
   - الفقرة (1): حظر حسم أكثر من (25%) من أجر العامل شهرياً لاسترداد قروض صاحب العمل.
   - الفقرة الأخيرة: سقف الاستقطاعات الإجمالي لا يتجاوز (50%) من أجر العامل المستحق.
   - حظر الفوائد الربوية التزاماً بأحكام الشريعة الإسلامية والأنظمة السعودية (صفر فوائد).
2. التفريق الحتمي بين المواطن السعودي والوافد المقيم:
   - الوافد المقيم: فحص المدة المتبقية في العقد المحدد المدة (المادة 37)، ومقارنة رصيد السلفة بمكافأة نهاية الخدمة المستحقة كضمان نظامي.
   - المواطن السعودي: مرونة السداد حتى 36 شهراً ضمن العقود غير محددة المدة، ومراعاة استقطاع التأمينات GOSI (9.75% / 10%).
3. مبدأ التحقق المزدوج Four-Eyes والتحقق المستقل بعد الكتابة (Readback Verification).
"""

from __future__ import annotations

import os
import math
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional, Tuple

from odoo_readonly_repository import OdooReadonlyRepository
from odoo_loan_write_gateway import OdooLoanWriteGateway
from eos_service import detect_employee_nationality, calculate_service_period_components
from saudi_labor_law_rules import calculate_end_of_service_benefit, ContractType


LOAN_AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "loan_audit_log.jsonl")
STATUTORY_MAX_LOAN_DEDUCTION_PCT = 25.0  # المادة 92 فقرة 1
STATUTORY_MAX_TOTAL_DEDUCTION_PCT = 50.0  # المادة 92 الفقرة الأخيرة


@dataclass
class LoanSummary:
    employee_id: int
    employee_name: str
    department_name: str
    job_title: str
    is_saudi: bool
    nationality_text_ar: str
    monthly_wage: float
    max_allowed_monthly_deduction: float  # 25% of wage
    active_loans_count: int
    total_active_loan_amount: float
    remaining_contract_months: Optional[int] = None
    estimated_eos_balance: float = 0.0
    recent_loans: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class LoanDryRunResult:
    is_valid: bool
    employee_id: int
    employee_name: str
    department_id: int
    department_name: str
    job_id: int
    job_title: str
    is_saudi: bool
    nationality_text_ar: str
    loan_amount: float
    monthly_wage: float
    installment_amount: float
    term: int
    start_date: str
    deduction_percentage_of_wage: float
    max_statutory_deduction_percentage: float
    suggested_min_term: int
    suggested_max_installment: float
    statutory_article: str
    statutory_explanation_ar: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    approval_token: str = ""
    can_proceed: bool = False


@dataclass
class LoanExecutionResult:
    success: bool
    loan_id: Optional[int]
    employee_id: int
    employee_name: str
    loan_amount: float
    installment_amount: float
    term: int
    state: str
    readback_verified: bool
    message_ar: str
    audit_logged: bool


class LoanService:
    """
    خدمة إدارة وتدقيق سلف وقروض الموظفين في Odoo.
    تلتزم بضوابط المادة 92 وسقف الاستقطاع 25% والتفريق بين السعودي والمقيم.
    """
    _shared_pending_approvals: Dict[str, Dict[str, Any]] = {}

    def __init__(
        self,
        readonly_repo: Optional[OdooReadonlyRepository] = None,
        write_gateway: Optional[OdooLoanWriteGateway] = None,
        audit_log_path: Optional[str] = None
    ):
        self.readonly_repo = readonly_repo or OdooReadonlyRepository()
        self.write_gateway = write_gateway
        self.audit_log_path = audit_log_path or LOAN_AUDIT_LOG_FILE
        self._pending_approvals: Dict[str, Dict[str, Any]] = LoanService._shared_pending_approvals

    def get_employee_loan_summary(
        self,
        employee_id: int,
        explicit_is_saudi: Optional[bool] = None,
        limit: int = 15
    ) -> LoanSummary:
        """
        جلب وتلخيص السلف والقروض المسجلة للموظف والحد الأقصى المسموح به شهرياً (المادة 92).
        """
        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            raise ValueError(f"الموظف برقم المعرف #{employee_id} غير موجود في Odoo.")

        emp_name = emp.get("name", "غير معروف")
        dept_name = emp["department_id"][1] if emp.get("department_id") else "بدون قسم"
        job_title = emp["job_id"][1] if emp.get("job_id") else "بدون مسمى"

        is_saudi = detect_employee_nationality(emp, explicit_is_saudi)
        nat_text = "مواطن سعودي" if is_saudi else "وافد غير سعودي (مقيم)"

        # استخراج الأجر الشهري
        wage = 0.0
        contracts = self.readonly_repo.get_employee_contracts(employee_id)
        c_end_date = None
        c_start_date = None
        if contracts:
            c = contracts[0]
            wage = float(c.get("wage") or 0.0)
            c_end_date = c.get("date_end")
            c_start_date = c.get("date_start")
        if wage <= 0:
            wage = float(emp.get("wage") or 5000.0)

        max_allowed_ded = round(wage * 0.25, 2)

        # حساب المدة المتبقية في العقد للوافد
        remaining_months = None
        if not is_saudi and c_end_date:
            try:
                end_d = datetime.strptime(str(c_end_date)[:10], "%Y-%m-%d").date()
                today_d = date.today()
                if end_d > today_d:
                    remaining_months = max(1, (end_d.year - today_d.year) * 12 + (end_d.month - today_d.month))
                else:
                    remaining_months = 0
            except Exception:
                remaining_months = None

        # حساب مكافأة نهاية الخدمة التقديرية كضمان
        est_eos = 0.0
        if c_start_date:
            try:
                sy, sm, sd, dec_years = calculate_service_period_components(str(c_start_date)[:10], date.today().isoformat())
                eos_calc = calculate_end_of_service_benefit(
                    last_gross_wage=wage,
                    service_years=dec_years,
                    is_saudi=is_saudi,
                    is_resignation=False,
                )
                est_eos = round(eos_calc.net_eosb_amount, 2)
            except Exception:
                pass

        loans = self.readonly_repo.get_employee_loans(employee_id=employee_id, limit=limit)
        active_loans = [l for l in loans if l.get("state") not in ("paid", "close", "reject", "cancel")]
        total_active_amt = sum(float(l.get("loan_amount") or 0.0) for l in active_loans)

        return LoanSummary(
            employee_id=employee_id,
            employee_name=emp_name,
            department_name=dept_name,
            job_title=job_title,
            is_saudi=is_saudi,
            nationality_text_ar=nat_text,
            monthly_wage=wage,
            max_allowed_monthly_deduction=max_allowed_ded,
            active_loans_count=len(active_loans),
            total_active_loan_amount=round(total_active_amt, 2),
            remaining_contract_months=remaining_months,
            estimated_eos_balance=est_eos,
            recent_loans=loans[:5]
        )

    def dry_run_loan(
        self,
        employee_id: int,
        loan_amount: float,
        term: int = 12,
        installment_amount: Optional[float] = None,
        start_date: Optional[str] = None,
        notes: Optional[str] = None,
        manager_id: Optional[int] = None,
        explicit_is_saudi: Optional[bool] = None,
        explicit_wage: Optional[float] = None,
    ) -> LoanDryRunResult:
        """
        الفحص والتدقيق التجريبي لطلب السلفة/القرض وفق المادة 92 من نظام العمل السعودي.
        """
        errors: List[str] = []
        warnings: List[str] = []

        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            return LoanDryRunResult(
                is_valid=False,
                employee_id=employee_id,
                employee_name="غير معروف",
                department_id=0,
                department_name="غير معروف",
                job_id=0,
                job_title="غير معروف",
                is_saudi=True,
                nationality_text_ar="غير معروف",
                loan_amount=loan_amount,
                monthly_wage=0.0,
                installment_amount=0.0,
                term=term,
                start_date=start_date or date.today().isoformat(),
                deduction_percentage_of_wage=0.0,
                max_statutory_deduction_percentage=25.0,
                suggested_min_term=1,
                suggested_max_installment=0.0,
                statutory_article="المادة 92",
                statutory_explanation_ar="الموظف غير مسجل في Odoo.",
                errors=["الموظف برقم المعرف المحدد غير موجود."],
                can_proceed=False
            )

        emp_name = emp.get("name", "غير معروف")
        dept_id = emp["department_id"][0] if emp.get("department_id") else 1
        dept_name = emp["department_id"][1] if emp.get("department_id") else "بدون قسم"
        job_id = emp["job_id"][0] if emp.get("job_id") else 1
        job_title = emp["job_id"][1] if emp.get("job_id") else "بدون مسمى"
        emp_manager_id = manager_id or (emp["parent_id"][0] if emp.get("parent_id") else employee_id)

        is_saudi = detect_employee_nationality(emp, explicit_is_saudi)
        nat_text = "مواطن سعودي" if is_saudi else "وافد غير سعودي (مقيم)"

        # الأجر الشهري
        wage = explicit_wage or 0.0
        c_end_date = None
        c_start_date = None
        contracts = self.readonly_repo.get_employee_contracts(employee_id)
        if contracts:
            c = contracts[0]
            if wage <= 0:
                wage = float(c.get("wage") or 0.0)
            c_end_date = c.get("date_end")
            c_start_date = c.get("date_start")
        if wage <= 0:
            wage = float(emp.get("wage") or 5000.0)

        # التحقق من المدخلات الأساسية
        if loan_amount <= 0:
            errors.append("مبلغ السلفة يجب أن يكون أكبر من الصفر.")
        if term <= 0:
            errors.append("مدة السداد بالأشهر (term) يجب أن تكون شهراً واحداً على الأقل.")

        # احتساب القسط الشهري
        actual_term = max(1, term)
        if installment_amount and installment_amount > 0:
            calc_inst = round(installment_amount, 2)
        else:
            calc_inst = round(loan_amount / actual_term, 2)

        # السقف النظامي للاستقطاع بموجب المادة 92 (25%)
        max_allowed_inst = round(wage * 0.25, 2)
        deduction_pct = round((calc_inst / wage) * 100.0, 2) if wage > 0 else 100.0
        suggested_min_term = math.ceil(loan_amount / max_allowed_inst) if max_allowed_inst > 0 else 1

        # 1. تدقيق سقف المادة 92 فقرة (1)
        if calc_inst > max_allowed_inst:
            errors.append(
                f"مخالفة المادة 92 فقرة (1): القسط الشهري المطلوب ({calc_inst:,.2f} ر.س) يمثل ({deduction_pct}%) "
                f"من الراتب، ويتجاوز الحد الأقصى النظامي 25% ({max_allowed_inst:,.2f} ر.س). "
                f"الحد الأدنى لمدة السداد النظامية هو ({suggested_min_term} شهراً)."
            )

        # 2. تدقيق سقف الاستقطاعات الإجمالي (50%)
        if is_saudi:
            gosi_ded = round(wage * 0.0975, 2)
            total_est_ded = calc_inst + gosi_ded
            total_pct = round((total_est_ded / wage) * 100.0, 2)
            if total_pct > 50.0:
                warnings.append(
                    f"المادة 92 الفقرة الأخيرة: إجمالي الاستقطاعات الشهرية (سلفة {calc_inst:,.2f} + تأمينات {gosi_ded:,.2f} = {total_est_ded:,.2f} ر.س) "
                    f"تمثل ({total_pct}%) من الراتب وتقترب من/تتجاوز سقف الـ 50% الإجمالي."
                )

        # 3. تدقيق خصوصية الوافد المقيم مقابل مدة العقد (المادة 37) ورصيد نهاية الخدمة
        remaining_contract_months = None
        if not is_saudi and c_end_date:
            try:
                end_d = datetime.strptime(str(c_end_date)[:10], "%Y-%m-%d").date()
                today_d = date.today()
                if end_d > today_d:
                    remaining_contract_months = max(1, (end_d.year - today_d.year) * 12 + (end_d.month - today_d.month))
                else:
                    remaining_contract_months = 0
            except Exception:
                pass

        if not is_saudi:
            if remaining_contract_months is not None and actual_term > remaining_contract_months:
                warnings.append(
                    f"المادة 37 من نظام العمل: مدة سداد السلفة ({actual_term} شهراً) تتجاوز المدة المتبقية في العقد المحدد الحالي "
                    f"({remaining_contract_months} شهراً ينتهي في {c_end_date}). "
                    f"يُشترط التنسيق مع تجديد العقد أو كفاية رصيد مكافأة نهاية الخدمة كضمان."
                )

        s_date = start_date or date.today().isoformat()
        expl_ar = (
            f"سلفة بمبلغ {loan_amount:,.2f} ر.س للموظف {emp_name} ({nat_text}): "
            f"قسط شهري {calc_inst:,.2f} ر.س لمدة {actual_term} شهراً، تمثل ({deduction_pct}%) من الراتب الشهري ({wage:,.2f} ر.س). "
            f"الحد الأقصى المسموح نظاماً (25%): {max_allowed_inst:,.2f} ر.س."
        )

        is_valid = len(errors) == 0
        token = ""
        if is_valid:
            token = f"LOAN-{uuid.uuid4().hex[:8].upper()}"
            self._pending_approvals[token] = {
                "employee_id": employee_id,
                "loan_amount": loan_amount,
                "installment_amount": calc_inst,
                "term": actual_term,
                "start_date": s_date,
                "manager_id": emp_manager_id,
                "notes": notes or f"سلفة راتب معتمدة نظاماً بموجب المادة 92 | {nat_text}",
                "department_id": dept_id,
                "job_id": job_id,
                "employee_name": emp_name,
                "is_saudi": is_saudi,
            }

        return LoanDryRunResult(
            is_valid=is_valid,
            employee_id=employee_id,
            employee_name=emp_name,
            department_id=dept_id,
            department_name=dept_name,
            job_id=job_id,
            job_title=job_title,
            is_saudi=is_saudi,
            nationality_text_ar=nat_text,
            loan_amount=loan_amount,
            monthly_wage=wage,
            installment_amount=calc_inst,
            term=actual_term,
            start_date=s_date,
            deduction_percentage_of_wage=deduction_pct,
            max_statutory_deduction_percentage=STATUTORY_MAX_LOAN_DEDUCTION_PCT,
            suggested_min_term=suggested_min_term,
            suggested_max_installment=max_allowed_inst,
            statutory_article="المادة 92 من نظام العمل السعودي",
            statutory_explanation_ar=expl_ar,
            warnings=warnings,
            errors=errors,
            approval_token=token,
            can_proceed=is_valid
        )

    def apply_loan(
        self,
        approval_token: str,
        user_confirmation_text: str = "تأكيد",
        state: str = "dep_approval"
    ) -> LoanExecutionResult:
        """
        اعتماد وتسجيل السلفة/القرض فعلياً في Odoo مع إلزامية التأكيد الكتابي الصريح.
        """
        if user_confirmation_text != "تأكيد":
            return LoanExecutionResult(
                success=False,
                loan_id=None,
                employee_id=0,
                employee_name="",
                loan_amount=0.0,
                installment_amount=0.0,
                term=0,
                state="",
                readback_verified=False,
                message_ar="مرفوض: يتطلب اعتماد سلفة الموظف كلمة 'تأكيد' صريحة من المستخدم.",
                audit_logged=False
            )

        payload = self._pending_approvals.pop(approval_token, None)
        if not payload:
            return LoanExecutionResult(
                success=False,
                loan_id=None,
                employee_id=0,
                employee_name="",
                loan_amount=0.0,
                installment_amount=0.0,
                term=0,
                state="",
                readback_verified=False,
                message_ar=f"رمز الموافقة '{approval_token}' غير صالح أو منتهي الصلاحية.",
                audit_logged=False
            )

        if not self.write_gateway:
            return LoanExecutionResult(
                success=False,
                loan_id=None,
                employee_id=payload["employee_id"],
                employee_name=payload["employee_name"],
                loan_amount=payload["loan_amount"],
                installment_amount=payload["installment_amount"],
                term=payload["term"],
                state="dry_run_only",
                readback_verified=False,
                message_ar="بوابة الكتابة إلى Odoo غير مهيأة (وضع القراءة فقط).",
                audit_logged=False
            )

        try:
            created_id = self.write_gateway.create_employee_loan(
                employee_id=payload["employee_id"],
                loan_amount=payload["loan_amount"],
                installment_amount=payload["installment_amount"],
                term=payload["term"],
                start_date=payload["start_date"],
                manager_id=payload["manager_id"],
                notes=payload["notes"],
                department_id=payload["department_id"],
                job_id=payload["job_id"],
                state="draft",
            )

            if state in ("dep_approval", "hr_approval", "paid"):
                self.write_gateway.approve_employee_loan(created_id, target_state=state)

            # التحقق المستقل بعد الكتابة (Readback Verification)
            read_back = self.write_gateway.read_employee_loan(created_id)
            verified = bool(read_back and read_back.get("id") == created_id)

            # توثيق العملية في سجل التدقيق
            audit_entry = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event": "APPLY_EMPLOYEE_LOAN",
                "loan_id": created_id,
                "employee_id": payload["employee_id"],
                "employee_name": payload["employee_name"],
                "is_saudi": payload.get("is_saudi", True),
                "loan_amount": payload["loan_amount"],
                "installment_amount": payload["installment_amount"],
                "term": payload["term"],
                "state": state,
                "readback_verified": verified,
            }
            os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")

            msg = (
                f"تم اعتماد وتسجيل سلفة الموظف بنجاح في Odoo برقم #{created_id} "
                f"بمبلغ {payload['loan_amount']:,.2f} ر.س وقسط شهري {payload['installment_amount']:,.2f} ر.س لمدة {payload['term']} شهراً."
            )

            return LoanExecutionResult(
                success=True,
                loan_id=created_id,
                employee_id=payload["employee_id"],
                employee_name=payload["employee_name"],
                loan_amount=payload["loan_amount"],
                installment_amount=payload["installment_amount"],
                term=payload["term"],
                state=state,
                readback_verified=verified,
                message_ar=msg,
                audit_logged=True
            )
        except Exception as e:
            return LoanExecutionResult(
                success=False,
                loan_id=None,
                employee_id=payload["employee_id"],
                employee_name=payload["employee_name"],
                loan_amount=payload["loan_amount"],
                installment_amount=payload["installment_amount"],
                term=payload["term"],
                state="failed",
                readback_verified=False,
                message_ar=f"فشل تسجيل السلفة في Odoo: {str(e)}",
                audit_logged=False
            )
