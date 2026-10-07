"""
خدمة إدارة وتدقيق مسيرات الرواتب وحماية الأجور WPS (Payroll & Wage Protection Service)
=============================================================================
الطبقة التنفيذية لإدارة مسيرات الرواتب (hr.payslip) وحساب صافي الأجور وملفات حماية الأجور (WPS SIF):
1. التفريق الحتمي بين المواطن السعودي والوافد المقيم:
   - المواطن السعودي (Saudi):
     * استقطاع التأمينات الاجتماعية GOSI بنسبة 9.75% من وعاء الاشتراك (الأساسي + السكن).
     * مساهمة صاحب العمل 11.75% (9% معاشات + 0.75% ساند + 2% أخطار).
     * تنبيه نطاقات إذا كان الأساسي أقل من 4,000 ر.س.
   - الوافد المقيم (Non-Saudi Expat):
     * استقطاع الموظف GOSI بنسبة 0.0%.
     * مساهمة صاحب العمل 2.0% (أخطار مهنية فقط).
2. استقطاعات نظام العمل السعودي والحدود القانونية (المادتان 70/71 و 92):
   - أقساط السلف وقروض الموظفين (المادة 92): سقف 25% شهرياً.
   - الجزاءات والخصومات الانضباطية (المادتان 70/71): سقف 5 أيام أجر شهرياً.
   - السقف الإجمالي التراكمي لكافة الاستقطاعات: 50% من إجمالي الأجر (المادة 92).
3. توليد ملف نظام حماية الأجور المعتمد (WPS SIF Format) لمنصة مدد وبوابات البنوك السعودية.
4. مبدأ التحقق المزدوج Four-Eyes والتحقق المستقل بعد الكتابة (Readback Verification).
"""

from __future__ import annotations

import os
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional, Tuple

from odoo_readonly_repository import OdooReadonlyRepository
from odoo_payroll_write_gateway import OdooPayrollWriteGateway
from eos_service import detect_employee_nationality
from contract_service import (
    GOSI_MIN_CONTRIBUTORY_WAGE,
    GOSI_MAX_CONTRIBUTORY_WAGE,
    GOSI_SAUDI_EMPLOYEE_RATE,
    GOSI_SAUDI_EMPLOYER_RATE,
    GOSI_NON_SAUDI_EMPLOYEE_RATE,
    GOSI_NON_SAUDI_EMPLOYER_RATE,
    NITAQAT_MIN_FULL_SAUDIZATION_WAGE,
)
from loan_service import (
    STATUTORY_MAX_LOAN_DEDUCTION_PCT,
    STATUTORY_MAX_TOTAL_DEDUCTION_PCT,
)

PAYROLL_AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "payroll_audit_log.jsonl")


@dataclass
class PayslipSummary:
    payslip_id: int
    employee_id: int
    employee_name: str
    department_name: str
    job_title: str
    is_saudi: bool
    nationality_text_ar: str
    date_from: str
    date_to: str
    basic_wage: float
    housing_allowance: float
    transportation_allowance: float
    other_allowances: float
    gross_wage: float
    gosi_employee_deduction: float
    loan_deduction: float
    discipline_deduction: float
    other_deductions: float
    total_deductions: float
    net_wage: float
    state: str
    compliance_notes: List[str] = field(default_factory=list)


@dataclass
class PayslipDryRunResult:
    is_valid: bool
    employee_id: int
    employee_name: str
    department_id: int
    department_name: str
    is_saudi: bool
    nationality_text_ar: str
    date_from: str
    date_to: str
    basic_wage: float
    housing_allowance: float
    transportation_allowance: float
    other_allowances: float
    gross_wage: float
    gosi_contributory_wage: float
    gosi_employee_deduction: float
    gosi_employer_contribution: float
    loan_installment: float
    discipline_deduction: float
    other_deductions: float
    total_deductions: float
    net_wage: float
    deduction_pct_of_gross: float
    struct_id: Optional[int]
    statutory_article: str
    statutory_explanation_ar: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    approval_token: str = ""
    can_proceed: bool = False


@dataclass
class PayslipExecutionResult:
    success: bool
    payslip_id: Optional[int]
    employee_id: int
    employee_name: str
    gross_wage: float
    net_wage: float
    readback_verified: bool
    message_ar: str
    audit_logged: bool


@dataclass
class WpsSifFileResult:
    filename: str
    content: str
    records_count: int
    total_salaries_sar: float
    compliance_rate_pct: float
    message_ar: str


class PayrollService:
    """
    خدمة إدارة مسيرات الرواتب وحساب الأجور ونظام حماية الأجور WPS.
    """
    _shared_pending_approvals: Dict[str, Dict[str, Any]] = {}

    def __init__(
        self,
        readonly_repo: Optional[OdooReadonlyRepository] = None,
        write_gateway: Optional[OdooPayrollWriteGateway] = None,
        audit_log_path: Optional[str] = None
    ):
        self.readonly_repo = readonly_repo or OdooReadonlyRepository()
        self.write_gateway = write_gateway
        self.audit_log_path = audit_log_path or PAYROLL_AUDIT_LOG_FILE
        self._pending_approvals: Dict[str, Dict[str, Any]] = PayrollService._shared_pending_approvals

    def get_employee_payslip_summary(
        self,
        employee_id: int,
        explicit_is_saudi: Optional[bool] = None,
    ) -> PayslipSummary:
        """
        جلب وتلخيص آخر قسيمة راتب أو بيانات مسير الراتب للموظف.
        """
        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            raise ValueError(f"الموظف برقم المعرف #{employee_id} غير موجود في Odoo.")

        emp_name = emp.get("name", "غير معروف")
        dept_name = emp["department_id"][1] if emp.get("department_id") else "بدون قسم"
        job_title = emp["job_id"][1] if emp.get("job_id") else "بدون مسمى"

        is_saudi = detect_employee_nationality(emp, explicit_is_saudi)
        nat_text = "مواطن سعودي" if is_saudi else "وافد غير سعودي (مقيم)"

        # البحث عن آخر قسيمة مسجلة للموظف
        slips = self.readonly_repo.get_employee_payslips(employee_id, limit=1)
        contracts = self.readonly_repo.get_employee_contracts(employee_id)
        c_data = contracts[0] if contracts else {}

        basic = float(c_data.get("wage") or 0.0)
        housing = float(c_data.get("l10n_sa_housing_allowance") or 0.0)
        transport = float(c_data.get("l10n_sa_transportation_allowance") or 0.0)
        other = float(c_data.get("l10n_sa_other_allowances") or 0.0)
        gross = float(c_data.get("total") or (basic + housing + transport + other))

        slip_id = 0
        date_f = date.today().replace(day=1).isoformat()
        date_t = date.today().isoformat()
        state = "draft"
        loan_ded = 0.0
        disc_ded = 0.0

        if slips:
            s0 = slips[0]
            slip_id = int(s0.get("id") or 0)
            date_f = str(s0.get("date_from") or date_f)
            date_t = str(s0.get("date_to") or date_t)
            state = str(s0.get("state") or "draft")
            if s0.get("basic_wage"):
                basic = float(s0["basic_wage"])
            if s0.get("gross_wage"):
                gross = float(s0["gross_wage"])
            loan_ded = float(s0.get("installment_employee_loan") or 0.0)
            disc_ded = float(s0.get("discipline_amount") or 0.0)

        # حساب التأمينات GOSI
        contributory_wage = min(GOSI_MAX_CONTRIBUTORY_WAGE, max(GOSI_MIN_CONTRIBUTORY_WAGE, basic + housing)) if (basic + housing) > 0 else 0.0
        gosi_ee = round(contributory_wage * GOSI_SAUDI_EMPLOYEE_RATE, 2) if is_saudi else 0.0

        tot_ded = round(gosi_ee + loan_ded + disc_ded, 2)
        net = round(max(0.0, gross - tot_ded), 2)

        notes: List[str] = []
        if is_saudi and basic < NITAQAT_MIN_FULL_SAUDIZATION_WAGE:
            notes.append(f"تنبيه نطاقات: الأجر الأساسي أقل من {NITAQAT_MIN_FULL_SAUDIZATION_WAGE} ر.س.")
        if tot_ded > (gross * 0.50):
            notes.append("⚠️ تجاوز الاستقطاعات لسقف 50% من الأجر بموجب المادة 92 من نظام العمل.")

        return PayslipSummary(
            payslip_id=slip_id,
            employee_id=employee_id,
            employee_name=emp_name,
            department_name=dept_name,
            job_title=job_title,
            is_saudi=is_saudi,
            nationality_text_ar=nat_text,
            date_from=date_f,
            date_to=date_t,
            basic_wage=basic,
            housing_allowance=housing,
            transportation_allowance=transport,
            other_allowances=other,
            gross_wage=gross,
            gosi_employee_deduction=gosi_ee,
            loan_deduction=loan_ded,
            discipline_deduction=disc_ded,
            other_deductions=0.0,
            total_deductions=tot_ded,
            net_wage=net,
            state=state,
            compliance_notes=notes,
        )

    def dry_run_payslip(
        self,
        employee_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        basic_wage: Optional[float] = None,
        housing_allowance: Optional[float] = None,
        transportation_allowance: Optional[float] = None,
        other_allowances: Optional[float] = None,
        loan_installment: Optional[float] = None,
        discipline_amount: Optional[float] = None,
        other_deductions: float = 0.0,
        struct_id: Optional[int] = None,
        explicit_is_saudi: Optional[bool] = None,
    ) -> PayslipDryRunResult:
        """
        تدقيق وفحص مسير وقسيمة الراتب تجريبياً (Dry-Run) والتحقق من سقف الاستقطاعات والتأمينات.
        """
        warnings: List[str] = []
        errors: List[str] = []

        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            return PayslipDryRunResult(
                is_valid=False,
                employee_id=employee_id,
                employee_name="غير معروف",
                department_id=0,
                department_name="",
                is_saudi=True,
                nationality_text_ar="",
                date_from=date_from or "",
                date_to=date_to or "",
                basic_wage=0.0,
                housing_allowance=0.0,
                transportation_allowance=0.0,
                other_allowances=0.0,
                gross_wage=0.0,
                gosi_contributory_wage=0.0,
                gosi_employee_deduction=0.0,
                gosi_employer_contribution=0.0,
                loan_installment=0.0,
                discipline_deduction=0.0,
                other_deductions=0.0,
                total_deductions=0.0,
                net_wage=0.0,
                deduction_pct_of_gross=0.0,
                struct_id=struct_id,
                statutory_article="نظام العمل والتأمينات",
                statutory_explanation_ar="الموظف غير مسجل في Odoo.",
                errors=["الموظف المحدد غير موجود في قاعدة البيانات."],
                can_proceed=False,
            )

        emp_name = emp.get("name", "غير معروف")
        dept_id = emp["department_id"][0] if emp.get("department_id") else 1
        dept_name = emp["department_id"][1] if emp.get("department_id") else "بدون قسم"

        is_saudi = detect_employee_nationality(emp, explicit_is_saudi)
        nat_text = "مواطن سعودي" if is_saudi else "وافد غير سعودي (مقيم)"

        # إذا لم يتم تمرير الأجور، استخرجها من عقد الموظف الحالي في Odoo
        contracts = self.readonly_repo.get_employee_contracts(employee_id)
        c0 = contracts[0] if contracts else {}

        b_wage = float(basic_wage if basic_wage is not None else (c0.get("wage") or 0.0))
        h_allow = float(housing_allowance if housing_allowance is not None else (c0.get("l10n_sa_housing_allowance") or (b_wage * 0.25)))
        t_allow = float(transportation_allowance if transportation_allowance is not None else (c0.get("l10n_sa_transportation_allowance") or (b_wage * 0.10)))
        o_allow = float(other_allowances if other_allowances is not None else (c0.get("l10n_sa_other_allowances") or 0.0))

        gross = round(b_wage + h_allow + t_allow + o_allow, 2)
        if gross <= 0:
            errors.append("إجمالي الراتب (Gross Wage) يجب أن يكون أكبر من الصفر.")

        today = date.today()
        d_from = date_from or today.replace(day=1).isoformat()
        d_to = date_to or today.isoformat()

        # حساب التأمينات الاجتماعية GOSI
        contrib_wage = min(GOSI_MAX_CONTRIBUTORY_WAGE, max(GOSI_MIN_CONTRIBUTORY_WAGE, b_wage + h_allow)) if (b_wage + h_allow) > 0 else 0.0
        if is_saudi:
            ee_gosi = round(contrib_wage * GOSI_SAUDI_EMPLOYEE_RATE, 2)
            er_gosi = round(contrib_wage * GOSI_SAUDI_EMPLOYER_RATE, 2)
            if b_wage < NITAQAT_MIN_FULL_SAUDIZATION_WAGE:
                warnings.append(f"تنبيه نطاقات: الأجر الأساسي ({b_wage:,.2f} ر.س) أقل من 4,000 ر.س ولا يحتسب وزناً كاملاً في التوطين.")
        else:
            ee_gosi = 0.0
            er_gosi = round(contrib_wage * GOSI_NON_SAUDI_EMPLOYER_RATE, 2)

        loan_val = float(loan_installment or 0.0)
        disc_val = float(discipline_amount or 0.0)
        other_ded = float(other_deductions or 0.0)

        # فحص سقف أقساط السلف (المادة 92: 25%)
        max_loan_allowed = gross * (STATUTORY_MAX_LOAN_DEDUCTION_PCT / 100.0)
        if loan_val > max_loan_allowed:
            warnings.append(
                f"قسط السلفة ({loan_val:,.2f} ر.س) يتجاوز سقف 25% من إجمالي الراتب ({max_loan_allowed:,.2f} ر.س) بموجب المادة 92."
            )

        # فحص سقف الجزاءات (المادة 70/71: أجر 5 أيام شهرياً)
        daily_wage = round(gross / 30.0, 2) if gross > 0 else 0.0
        max_disc_allowed = round(daily_wage * 5.0, 2)
        if disc_val > max_disc_allowed:
            warnings.append(
                f"الخصم الانضباطي ({disc_val:,.2f} ر.س) يتجاوز أجر 5 أيام ({max_disc_allowed:,.2f} ر.س) المسموح به شهرياً بالمادة 71."
            )

        tot_ded = round(ee_gosi + loan_val + disc_val + other_ded, 2)
        ded_pct = round((tot_ded / gross * 100.0), 2) if gross > 0 else 0.0

        # فحص سقف الاستقطاعات التراكمي (المادة 92: 50%)
        if tot_ded > (gross * 0.50):
            errors.append(
                f"مخالفة المادة 92: إجمالي الاستقطاعات ({tot_ded:,.2f} ر.س بنسبة {ded_pct}%) يتجاوز نصف راتب العامل (50%)."
            )

        net = round(max(0.0, gross - tot_ded), 2)

        is_valid = len(errors) == 0
        token = f"PAY-{uuid.uuid4().hex[:8].upper()}" if is_valid else ""

        statutory_article = "المواد 90 و 92 من نظام العمل ولوائح التأمينات ونظام حماية الأجور (WPS)"
        statutory_explanation = (
            f"التصنيف: {nat_text} | الإجمالي: {gross:,.2f} ر.س | "
            f"استقطاع التأمينات: {ee_gosi:,.2f} ر.س | قسط السلفة: {loan_val:,.2f} ر.س | "
            f"الجزاءات: {disc_val:,.2f} ر.س | إجمالي الاستقطاعات: {tot_ded:,.2f} ر.س ({ded_pct}%) | "
            f"الصافي المحول: {net:,.2f} ر.س."
        )

        if is_valid:
            self._pending_approvals[token] = {
                "employee_id": employee_id,
                "employee_name": emp_name,
                "date_from": d_from,
                "date_to": d_to,
                "basic_wage": b_wage,
                "housing_allowance": h_allow,
                "transportation_allowance": t_allow,
                "other_allowances": o_allow,
                "gross_wage": gross,
                "loan_installment": loan_val,
                "discipline_amount": disc_val,
                "net_wage": net,
                "struct_id": struct_id,
                "is_saudi": is_saudi,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        return PayslipDryRunResult(
            is_valid=is_valid,
            employee_id=employee_id,
            employee_name=emp_name,
            department_id=dept_id,
            department_name=dept_name,
            is_saudi=is_saudi,
            nationality_text_ar=nat_text,
            date_from=d_from,
            date_to=d_to,
            basic_wage=b_wage,
            housing_allowance=h_allow,
            transportation_allowance=t_allow,
            other_allowances=o_allow,
            gross_wage=gross,
            gosi_contributory_wage=contrib_wage,
            gosi_employee_deduction=ee_gosi,
            gosi_employer_contribution=er_gosi,
            loan_installment=loan_val,
            discipline_deduction=disc_val,
            other_deductions=other_ded,
            total_deductions=tot_ded,
            net_wage=net,
            deduction_pct_of_gross=ded_pct,
            struct_id=struct_id,
            statutory_article=statutory_article,
            statutory_explanation_ar=statutory_explanation,
            warnings=warnings,
            errors=errors,
            approval_token=token,
            can_proceed=is_valid,
        )

    def apply_payslip(
        self,
        approval_token: str,
        user_confirmation_text: str = "تأكيد",
        state: str = "draft",
    ) -> PayslipExecutionResult:
        """
        اعتماد وإنشاء قسيمة الراتب في Odoo بموجب مبدأ التحقق المزدوج Four-Eyes.
        """
        if user_confirmation_text.strip() != "تأكيد":
            return PayslipExecutionResult(
                success=False,
                payslip_id=None,
                employee_id=0,
                employee_name="",
                gross_wage=0.0,
                net_wage=0.0,
                readback_verified=False,
                message_ar="مبدأ التحقق المزدوج: يلزم إدخال كلمة «تأكيد» صراحة لإنشاء قسيمة الراتب في Odoo.",
                audit_logged=False,
            )

        if not self.write_gateway:
            return PayslipExecutionResult(
                success=False,
                payslip_id=None,
                employee_id=0,
                employee_name="",
                gross_wage=0.0,
                net_wage=0.0,
                readback_verified=False,
                message_ar="بوابة الكتابة لمسيرات الرواتب غير مهيأة أو غير متصلة.",
                audit_logged=False,
            )

        pending = self._pending_approvals.pop(approval_token, None)
        if not pending:
            return PayslipExecutionResult(
                success=False,
                payslip_id=None,
                employee_id=0,
                employee_name="",
                gross_wage=0.0,
                net_wage=0.0,
                readback_verified=False,
                message_ar="رمز الموافقة غير صالح أو منتهي الصلاحية؛ يرجى إجراء التدقيق أولاً.",
                audit_logged=False,
            )

        emp_id = pending["employee_id"]
        emp_name = pending["employee_name"]

        try:
            pid = self.write_gateway.create_payslip(
                employee_id=emp_id,
                date_from=pending["date_from"],
                date_to=pending["date_to"],
                basic_wage=pending["basic_wage"],
                gross_wage=pending["gross_wage"],
                net_wage=pending["net_wage"],
                discipline_amount=pending.get("discipline_amount", 0.0),
                installment_employee_loan=pending.get("loan_installment", 0.0),
                struct_id=pending.get("struct_id"),
                state=state,
            )

            # التحقق المستقل بعد الكتابة (Readback Verification)
            read_back = self.write_gateway.read_payslip(pid)
            readback_ok = bool(read_back and read_back.get("id") == pid)

            audit_entry = {
                "event": "payslip_created",
                "payslip_id": pid,
                "employee_id": emp_id,
                "employee_name": emp_name,
                "gross_wage": pending["gross_wage"],
                "net_wage": pending["net_wage"],
                "state": state,
                "readback_verified": readback_ok,
                "approval_token": approval_token,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._write_audit_log(audit_entry)

            return PayslipExecutionResult(
                success=True,
                payslip_id=pid,
                employee_id=emp_id,
                employee_name=emp_name,
                gross_wage=pending["gross_wage"],
                net_wage=pending["net_wage"],
                readback_verified=readback_ok,
                message_ar=f"تم إنشاء واعتماد قسيمة راتب الموظف '{emp_name}' بنجاح في Odoo برقم #{pid}.",
                audit_logged=True,
            )
        except Exception as exc:
            return PayslipExecutionResult(
                success=False,
                payslip_id=None,
                employee_id=emp_id,
                employee_name=emp_name,
                gross_wage=pending.get("gross_wage", 0.0),
                net_wage=pending.get("net_wage", 0.0),
                readback_verified=False,
                message_ar=f"فشل إنشاء قسيمة الراتب في Odoo: {exc}",
                audit_logged=False,
            )

    def generate_wps_sif(
        self,
        employer_cr: str,
        bank_code: str,
        payslips_data: List[Dict[str, Any]],
        batch_reference: Optional[str] = None,
    ) -> WpsSifFileResult:
        """
        توليد ملف نظام حماية الأجور (WPS SIF Format) المعتمد للبنك المركزي ومنصة مدد.
        """
        creation_date = date.today().strftime("%Y%m%d")
        ref = batch_reference or f"PAY{creation_date}"
        filename = f"WPS_{employer_cr}_{creation_date}.sif"

        total_net = sum(float(p.get("net_wage", 0.0)) for p in payslips_data)
        count = len(payslips_data)

        lines: List[str] = []
        # 1. السجل الرأسي (Header Record - SCR)
        # SCR,Employer_CR,Bank_Code,Creation_Date,Total_Salaries,Record_Count,Currency
        lines.append(f"SCR,{employer_cr},{bank_code},{creation_date},{total_net:.2f},{count},SAR")

        # 2. سجلات الموظفين (Employee Records - EDR)
        # EDR,National_ID/Iqama,Bank_Code,IBAN,Basic,Housing,Other,Deductions,Net,Ref
        for p in payslips_data:
            id_num = str(p.get("identification_id") or p.get("id_number") or p.get("employee_id") or "1000000000")
            b_code = str(p.get("bank_code") or bank_code)
            iban = str(p.get("iban") or "SA0000000000000000000000")
            basic = float(p.get("basic_wage", 0.0))
            housing = float(p.get("housing_allowance", 0.0))
            other = float(p.get("transportation_allowance", 0.0)) + float(p.get("other_allowances", 0.0))
            deductions = float(p.get("total_deductions", 0.0))
            net = float(p.get("net_wage", 0.0))
            emp_name = str(p.get("employee_name", "")).replace(",", " ")

            lines.append(
                f"EDR,{id_num},{b_code},{iban},{basic:.2f},{housing:.2f},{other:.2f},{deductions:.2f},{net:.2f},{emp_name}"
            )

        content = "\n".join(lines)
        return WpsSifFileResult(
            filename=filename,
            content=content,
            records_count=count,
            total_salaries_sar=round(total_net, 2),
            compliance_rate_pct=100.0 if count > 0 else 0.0,
            message_ar=f"تم توليد ملف مسير حماية الأجور WPS ({filename}) لعدد {count} موظفاً بإجمالي {total_net:,.2f} ر.س.",
        )

    def _write_audit_log(self, entry: Dict[str, Any]) -> None:
        try:
            os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
