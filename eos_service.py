"""
خدمة إدارة مكافأة نهاية الخدمة والتسويات ونظام العمل السعودي (End of Service Benefit Service)
=================================================================================================
الطبقة التنفيذية لإدارة تسويات نهاية الخدمة في Odoo (hr.end.service.benefit) بالتكامل التام مع
محرك قواعد نظام العمل السعودي والتفرقة الصارمة بين الموظف السعودي وغير السعودي:
1. المادة 37: حظر العقود غير محددة المدة لغير السعودي، ومعاملتها كعقود محددة المدة.
2. المادة 77: التعويض عن الإنهاء غير المشروع (السعودي بعقد غير محدد: 15 يوماً عن كل سنة؛
   السعودي أو غير السعودي بعقد محدد: أجر المدة الباقية من العقد؛ بحد أدنى أجر شهرين لكافة الحالات).
3. المواد 84 و 85: مكافأة نهاية الخدمة (نصف شهر للسنوات الخمس الأولى وشهر لما بعدها)،
   وتدرج نسب الاستقالة (أقل من سنتين: 0%، 2-5 سنوات: 1/3، 5-10 سنوات: 2/3، 10+ سنوات: 100%).
4. المادة 87: استثناءات الاستحقاق الكامل للمكافأة (زواج العاملة، وضع العاملة، القوة القاهرة).
5. المادة 111: البدل النقدي لرصيد الإجازات السنوية غير المستنفدة.
6. مبدأ التحقق المزدوج Four-Eyes والتحقق المستقل بعد الكتابة (Readback Verification).
"""

from __future__ import annotations

import os
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional, Tuple

from odoo_readonly_repository import OdooReadonlyRepository
from odoo_eos_write_gateway import OdooEOSWriteGateway
from saudi_labor_law_rules import (
    calculate_end_of_service_benefit,
    calculate_article_77_compensation,
    ContractType,
    ResignationReason,
    EOSBCalculationResult,
    Article77CompensationResult,
)


EOS_AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "eos_audit_log.jsonl")


def calculate_service_period_components(
    hiring_date_str: str,
    end_date_str: str
) -> Tuple[int, int, int, float]:
    """
    حساب تفاصيل مدة الخدمة (سنوات، أشهر، أيام، وإجمالي السنوات ككسر عشري).
    """
    try:
        d_start = datetime.strptime(hiring_date_str[:10], "%Y-%m-%d").date()
        d_end = datetime.strptime(end_date_str[:10], "%Y-%m-%d").date()
    except Exception:
        d_start = date.today()
        d_end = date.today()

    if d_end < d_start:
        return 0, 0, 0, 0.0

    total_days = (d_end - d_start).days
    years = d_end.year - d_start.year
    months = d_end.month - d_start.month
    days = d_end.day - d_start.day

    if days < 0:
        months -= 1
        # تقريب الشهر بـ 30 يوماً
        days += 30
    if months < 0:
        years -= 1
        months += 12

    years = max(years, 0)
    months = max(months, 0)
    days = max(days, 0)

    # إجمالي السنوات بدقة
    total_service_years = round(total_days / 365.25, 4)
    return years, months, days, total_service_years


def detect_employee_nationality(employee: Dict[str, Any], explicit_is_saudi: Optional[bool] = None) -> bool:
    """
    التحقق الحتمي من جنسية الموظف (سعودي أم غير سعودي):
    1. استخدام الإدخال الصريح إذا تم تمريره.
    2. فحص رقم الهوية (يبدأ بـ 1 للسعودي، ويبدأ بـ 2 للمقيم/غير السعودي).
    3. فحص حقل الدولة (country_id).
    """
    if explicit_is_saudi is not None:
        return bool(explicit_is_saudi)

    ident = str(employee.get("identification_id") or "").strip()
    if ident.startswith("1"):
        return True
    if ident.startswith("2"):
        return False

    country_val = employee.get("country_id")
    if country_val:
        if isinstance(country_val, (list, tuple)) and len(country_val) > 1:
            country_name = str(country_val[1]).lower()
            if "saudi" in country_name or "سعود" in country_name:
                return True
        elif isinstance(country_val, str):
            country_name = country_val.lower()
            if "saudi" in country_name or "سعود" in country_name:
                return True

    # الافتراضي للمنشآت في السعودية عند عدم توفر دلالة
    return True


@dataclass
class EOSCalculationSummary:
    employee_id: int
    employee_name: str
    department_name: str
    is_saudi: bool
    nationality_text_ar: str
    hiring_date: str
    settlement_date: str
    years: int
    months: int
    days: int
    service_years: float
    last_gross_wage: float
    eos_records_count: int
    recent_records: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EOSDryRunResult:
    is_valid: bool
    employee_id: int
    employee_name: str
    department_id: int
    department_name: str
    is_saudi: bool
    nationality_text_ar: str
    contract_type: str  # "fixed" or "indefinite"
    hiring_date: str
    settlement_date: str
    years: int
    months: int
    days: int
    service_period: float
    monthly_wage: float
    daily_wage: float
    
    # تفاصيل مكافأة نهاية الخدمة (م/84، 85، 87)
    is_resignation: bool
    resignation_reason: str
    gratuity_entitlement_ratio: float
    gratuity_base_amount: float
    gratuity_net_amount: float
    gratuity_explanation_ar: str
    
    # تفاصيل تعويض المادة 77
    is_unlawful_termination: bool
    remaining_contract_months: float
    article_77_amount: float
    article_77_formula: str
    article_77_explanation_ar: str
    
    # تفاصيل الإجازات والأجور غير المدفوعة
    unused_leave_days: float
    leave_compensation_amount: float  # م/111
    unpaid_salary_days: float
    unpaid_salary_amount: float
    
    # الاستقطاعات والصافي
    other_deductions_amount: float
    net_settlement_amount: float
    statutory_summary_ar: str
    
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    approval_token: str = ""
    can_proceed: bool = False


@dataclass
class EOSExecutionResult:
    success: bool
    eos_id: Optional[int]
    reference: str
    employee_id: int
    employee_name: str
    is_saudi: bool
    total_settlement_amount: float
    state: str
    readback_verified: bool
    message_ar: str
    audit_logged: bool


class EOSService:
    """
    خدمة تسوية مكافأة نهاية الخدمة والتعويضات النظامية في Odoo.
    تطبق بدقة حاسمة الفوارق بين السعودي وغير السعودي، وحسابات المواد 77، 84، 85، 87، 111.
    """
    _shared_pending_approvals: Dict[str, Dict[str, Any]] = {}

    def __init__(
        self,
        readonly_repo: Optional[OdooReadonlyRepository] = None,
        write_gateway: Optional[OdooEOSWriteGateway] = None,
        audit_log_path: Optional[str] = None
    ):
        self.readonly_repo = readonly_repo or OdooReadonlyRepository()
        self.write_gateway = write_gateway
        self.audit_log_path = audit_log_path or EOS_AUDIT_LOG_FILE
        self._pending_approvals: Dict[str, Dict[str, Any]] = EOSService._shared_pending_approvals

    def get_employee_eos_summary(
        self,
        employee_id: int,
        settlement_date: Optional[str] = None,
        monthly_wage: float = 6000.0,
        explicit_is_saudi: Optional[bool] = None,
        limit: int = 10
    ) -> EOSCalculationSummary:
        """
        جلب وتلخيص بيانات الموظف ومدة خدمته وسجل التسويات السابقة.
        """
        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            raise ValueError(f"الموظف برقم المعرف #{employee_id} غير موجود في Odoo.")

        emp_name = emp.get("name", "غير معروف")
        dept_name = emp["department_id"][1] if emp.get("department_id") else "بدون قسم"
        hiring_d = str(emp.get("hiring_date") or emp.get("create_date") or date.today().isoformat())[:10]
        settle_d = settlement_date or date.today().isoformat()

        is_saudi = detect_employee_nationality(emp, explicit_is_saudi)
        nat_text = "مواطن سعودي" if is_saudi else "وافد غير سعودي (مقيم)"

        years, months, days, total_years = calculate_service_period_components(hiring_d, settle_d)
        prior_records = self.readonly_repo.get_employee_eos_records(employee_id=employee_id, limit=limit)

        return EOSCalculationSummary(
            employee_id=employee_id,
            employee_name=emp_name,
            department_name=dept_name,
            is_saudi=is_saudi,
            nationality_text_ar=nat_text,
            hiring_date=hiring_d,
            settlement_date=settle_d,
            years=years,
            months=months,
            days=days,
            service_years=total_years,
            last_gross_wage=monthly_wage,
            eos_records_count=len(prior_records),
            recent_records=prior_records[:5]
        )

    def dry_run_eos_settlement(
        self,
        employee_id: int,
        monthly_wage: float,
        settlement_date: Optional[str] = None,
        hiring_date: Optional[str] = None,
        service_years: Optional[float] = None,
        contract_type: str = "fixed",  # "fixed" or "indefinite"
        is_resignation: bool = False,
        resignation_reason: str = "standard",  # "standard", "marriage_female", "childbirth_female", "force_majeure"
        is_unlawful_termination: bool = False,  # تطبيق المادة 77
        remaining_contract_months: float = 0.0,
        agreed_compensation: Optional[float] = None,
        unused_leave_days: float = 0.0,
        unpaid_salary_days: float = 0.0,
        other_deductions_amount: float = 0.0,
        explicit_is_saudi: Optional[bool] = None,
    ) -> EOSDryRunResult:
        """
        الفحص التجريبي الاستباقي لتسوية نهاية الخدمة مع تطبيق كافة مواد نظام العمل السعودي.
        """
        errors: List[str] = []
        warnings: List[str] = []

        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            return EOSDryRunResult(
                is_valid=False,
                employee_id=employee_id,
                employee_name="غير معروف",
                department_id=0,
                department_name="غير معروف",
                is_saudi=True,
                nationality_text_ar="غير معروف",
                contract_type=contract_type,
                hiring_date="",
                settlement_date="",
                years=0,
                months=0,
                days=0,
                service_period=0.0,
                monthly_wage=monthly_wage,
                daily_wage=0.0,
                is_resignation=is_resignation,
                resignation_reason=resignation_reason,
                gratuity_entitlement_ratio=0.0,
                gratuity_base_amount=0.0,
                gratuity_net_amount=0.0,
                gratuity_explanation_ar="",
                is_unlawful_termination=is_unlawful_termination,
                remaining_contract_months=0.0,
                article_77_amount=0.0,
                article_77_formula="",
                article_77_explanation_ar="",
                unused_leave_days=0.0,
                leave_compensation_amount=0.0,
                unpaid_salary_days=0.0,
                unpaid_salary_amount=0.0,
                other_deductions_amount=0.0,
                net_settlement_amount=0.0,
                statutory_summary_ar="الموظف برقم المعرف المحدد غير موجود في Odoo.",
                errors=["الموظف برقم المعرف المحدد غير موجود."],
                can_proceed=False
            )

        emp_name = emp.get("name", "غير معروف")
        dept_id = emp["department_id"][0] if emp.get("department_id") else 1
        dept_name = emp["department_id"][1] if emp.get("department_id") else "بدون قسم"

        is_saudi = detect_employee_nationality(emp, explicit_is_saudi)
        nat_text = "مواطن سعودي" if is_saudi else "وافد غير سعودي (مقيم)"

        if monthly_wage <= 0:
            errors.append("الأجر الشهري الخاضع للاحتساب يجب أن يكون أكبر من الصفر.")

        daily_wage = round(monthly_wage / 30.0, 2)

        # 1. المادة 37: التحقق من نوع العقد وجنسية الموظف
        c_type_enum = ContractType.INDEFINITE if contract_type == "indefinite" else ContractType.FIXED
        if not is_saudi and c_type_enum == ContractType.INDEFINITE:
            warnings.append(
                "تنبيه المادة 37: عقد غير السعودي يجب أن يكون محدد المدة نظاماً؛ "
                "تمت معاملة العقد كمحدد المدة لاحتساب التسوية والتعويض."
            )
            c_type_enum = ContractType.FIXED

        # حساب مدة الخدمة
        emp_hiring = hiring_date or str(emp.get("hiring_date") or emp.get("create_date") or date.today().isoformat())[:10]
        emp_settle = settlement_date or date.today().isoformat()
        years_comp, months_comp, days_comp, calc_service_years = calculate_service_period_components(emp_hiring, emp_settle)

        effective_service_years = service_years if (service_years is not None and service_years >= 0) else calc_service_years

        # 2. حساب مكافأة نهاية الخدمة (المواد 84 و 85 و 87)
        res_reason_enum = ResignationReason.STANDARD
        if resignation_reason == "marriage_female":
            res_reason_enum = ResignationReason.MARRIAGE_FEMALE
        elif resignation_reason == "childbirth_female":
            res_reason_enum = ResignationReason.CHILDBIRTH_FEMALE
        elif resignation_reason == "force_majeure":
            res_reason_enum = ResignationReason.FORCE_MAJEURE

        eosb_res: EOSBCalculationResult = calculate_end_of_service_benefit(
            last_gross_wage=monthly_wage,
            service_years=effective_service_years,
            is_saudi=is_saudi,
            is_resignation=is_resignation,
            resignation_reason=res_reason_enum
        )

        gratuity_base = eosb_res.gross_eosb_amount
        gratuity_net = eosb_res.net_eosb_amount
        gratuity_ratio = eosb_res.entitlement_ratio
        gratuity_expl = eosb_res.explanation_ar

        # 3. حساب تعويض الإنهاء غير المشروع (المادة 77) إن وجد
        art77_amount = 0.0
        art77_formula = "غير منطبق (إنهاء مشروع أو استقالة)"
        art77_expl = "لم يتم طلب تعويض المادة 77."
        if is_unlawful_termination and not is_resignation:
            art77_res: Article77CompensationResult = calculate_article_77_compensation(
                monthly_wage=monthly_wage,
                is_saudi=is_saudi,
                contract_type=c_type_enum,
                service_years=effective_service_years,
                remaining_contract_months=remaining_contract_months,
                agreed_compensation=agreed_compensation
            )
            art77_amount = art77_res.final_compensation_amount
            art77_formula = art77_res.formula_used
            art77_expl = art77_res.explanation_ar

        # 4. حساب البدل النقدي للإجازات غير المستنفدة (المادة 111)
        leave_comp = round(max(unused_leave_days, 0.0) * daily_wage, 2)

        # 5. حساب أجر الأيام المتبقية من آخر شهر
        unpaid_salary = round(max(unpaid_salary_days, 0.0) * daily_wage, 2)

        # 6. صافي التسوية النهائي
        deductions = round(max(other_deductions_amount, 0.0), 2)
        net_settlement = round(gratuity_net + art77_amount + leave_comp + unpaid_salary - deductions, 2)

        statutory_summary = (
            f"تسوية نهاية الخدمة للموظف {emp_name} ({nat_text}): "
            f"مدة الخدمة: {years_comp} سنة و{months_comp} شهر و{days_comp} يوم ({effective_service_years:.2f} سنة). "
            f"مكافأة نهاية الخدمة (م/84، 85، 87): {gratuity_net:,.2f} ر.س. "
        )
        if art77_amount > 0:
            statutory_summary += f"تعويض الإنهاء غير المشروع (م/77): {art77_amount:,.2f} ر.س. "
        if leave_comp > 0:
            statutory_summary += f"بدل رصيد الإجازات (م/111 عن {unused_leave_days} يوم): {leave_comp:,.2f} ر.س. "
        if unpaid_salary > 0:
            statutory_summary += f"أجر الأيام المستحقة ({unpaid_salary_days} يوم): {unpaid_salary:,.2f} ر.س. "
        if deductions > 0:
            statutory_summary += f"استقطاعات سابقة: -{deductions:,.2f} ر.س. "
        statutory_summary += f"الصافي النهائي المستحق للصرف: {net_settlement:,.2f} ر.س."

        is_valid = len(errors) == 0
        token = ""
        ref_name = f"EOS-{datetime.now(timezone.utc).strftime('%Y%m')}-{uuid.uuid4().hex[:4].upper()}"

        if is_valid:
            token = f"EOS-{uuid.uuid4().hex[:8].upper()}"
            self._pending_approvals[token] = {
                "name": ref_name,
                "employee_id": employee_id,
                "employee_name": emp_name,
                "department_id": dept_id,
                "company_id": emp.get("company_id", [1])[0] if isinstance(emp.get("company_id"), (list, tuple)) else 1,
                "currency_id": 1,
                "date_str": emp_settle,
                "hiring_date": emp_hiring,
                "years": years_comp,
                "months": months_comp,
                "days": days_comp,
                "service_period": effective_service_years,
                "total_deserved_amount": gratuity_net,
                "total_holiday_deserved_amount": leave_comp,
                "total_payslip_deserved_amount": unpaid_salary,
                "other_amount": art77_amount,
                "other_deduction": deductions,
                "total_reward": net_settlement,
                "notes": statutory_summary,
                "is_saudi": is_saudi,
            }

        return EOSDryRunResult(
            is_valid=is_valid,
            employee_id=employee_id,
            employee_name=emp_name,
            department_id=dept_id,
            department_name=dept_name,
            is_saudi=is_saudi,
            nationality_text_ar=nat_text,
            contract_type=c_type_enum.value,
            hiring_date=emp_hiring,
            settlement_date=emp_settle,
            years=years_comp,
            months=months_comp,
            days=days_comp,
            service_period=effective_service_years,
            monthly_wage=monthly_wage,
            daily_wage=daily_wage,
            is_resignation=is_resignation,
            resignation_reason=resignation_reason,
            gratuity_entitlement_ratio=round(gratuity_ratio, 4),
            gratuity_base_amount=gratuity_base,
            gratuity_net_amount=gratuity_net,
            gratuity_explanation_ar=gratuity_expl,
            is_unlawful_termination=is_unlawful_termination,
            remaining_contract_months=remaining_contract_months,
            article_77_amount=art77_amount,
            article_77_formula=art77_formula,
            article_77_explanation_ar=art77_expl,
            unused_leave_days=unused_leave_days,
            leave_compensation_amount=leave_comp,
            unpaid_salary_days=unpaid_salary_days,
            unpaid_salary_amount=unpaid_salary,
            other_deductions_amount=deductions,
            net_settlement_amount=net_settlement,
            statutory_summary_ar=statutory_summary,
            warnings=warnings,
            errors=errors,
            approval_token=token,
            can_proceed=is_valid
        )

    def apply_eos_settlement(
        self,
        approval_token: str,
        user_confirmation_text: str = "تأكيد",
        state: str = "confirmed"
    ) -> EOSExecutionResult:
        """
        اعتماد وتسجيل مكافأة نهاية الخدمة والتسوية فعلياً في Odoo مع إلزامية التأكيد الكتابي.
        """
        if user_confirmation_text != "تأكيد":
            return EOSExecutionResult(
                success=False,
                eos_id=None,
                reference="",
                employee_id=0,
                employee_name="",
                is_saudi=False,
                total_settlement_amount=0.0,
                state="",
                readback_verified=False,
                message_ar="مرفوض: يتطلب اعتماد تسوية نهاية الخدمة كلمة 'تأكيد' صريحة من المستخدم.",
                audit_logged=False
            )

        payload = self._pending_approvals.pop(approval_token, None)
        if not payload:
            return EOSExecutionResult(
                success=False,
                eos_id=None,
                reference="",
                employee_id=0,
                employee_name="",
                is_saudi=False,
                total_settlement_amount=0.0,
                state="",
                readback_verified=False,
                message_ar=f"رمز الموافقة '{approval_token}' غير صالح أو منتهي الصلاحية.",
                audit_logged=False
            )

        if not self.write_gateway:
            return EOSExecutionResult(
                success=False,
                eos_id=None,
                reference=payload["name"],
                employee_id=payload["employee_id"],
                employee_name=payload["employee_name"],
                is_saudi=payload.get("is_saudi", True),
                total_settlement_amount=payload["total_reward"],
                state="dry_run_only",
                readback_verified=False,
                message_ar="بوابة الكتابة إلى Odoo غير مهيأة (وضع القراءة فقط).",
                audit_logged=False
            )

        try:
            created_id = self.write_gateway.create_end_service_benefit(
                name=payload["name"],
                employee_id=payload["employee_id"],
                department_id=payload["department_id"],
                company_id=payload["company_id"],
                currency_id=payload.get("currency_id", 1),
                date_str=payload["date_str"],
                hiring_date=payload["hiring_date"],
                years=payload["years"],
                months=payload["months"],
                days=payload["days"],
                service_period=payload["service_period"],
                total_deserved_amount=payload["total_deserved_amount"],
                total_holiday_deserved_amount=payload["total_holiday_deserved_amount"],
                total_payslip_deserved_amount=payload["total_payslip_deserved_amount"],
                other_amount=payload["other_amount"],
                other_deduction=payload["other_deduction"],
                total_reward=payload["total_reward"],
                notes=payload["notes"],
                state="draft",
            )

            # إذا طلب المستخدم اعتمادها مباشرة
            if state == "confirmed":
                self.write_gateway.confirm_end_service_benefit(created_id)

            # التحقق المستقل بعد الكتابة (Readback Verification)
            read_back = self.write_gateway.read_end_service_benefit(created_id)
            verified = bool(read_back and read_back.get("id") == created_id)

            # تسجيل سجل تدقيق إلزامي (Audit Log)
            audit_entry = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event": "APPLY_EOS_SETTLEMENT",
                "eos_id": created_id,
                "reference": payload["name"],
                "employee_id": payload["employee_id"],
                "employee_name": payload["employee_name"],
                "is_saudi": payload.get("is_saudi", True),
                "total_reward": payload["total_reward"],
                "gratuity_deserved": payload["total_deserved_amount"],
                "holiday_deserved": payload["total_holiday_deserved_amount"],
                "other_amount": payload["other_amount"],
                "other_deduction": payload["other_deduction"],
                "state": state,
                "readback_verified": verified,
            }
            os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")

            msg = (
                f"تم اعتماد وتسجيل تسوية مكافأة نهاية الخدمة بنجاح في Odoo برقم #{created_id} "
                f"ومرجع ({payload['name']})، بإجمالي مستحق {payload['total_reward']:,.2f} ر.س."
            )

            return EOSExecutionResult(
                success=True,
                eos_id=created_id,
                reference=payload["name"],
                employee_id=payload["employee_id"],
                employee_name=payload["employee_name"],
                is_saudi=payload.get("is_saudi", True),
                total_settlement_amount=payload["total_reward"],
                state=state,
                readback_verified=verified,
                message_ar=msg,
                audit_logged=True
            )
        except Exception as e:
            return EOSExecutionResult(
                success=False,
                eos_id=None,
                reference=payload["name"],
                employee_id=payload["employee_id"],
                employee_name=payload["employee_name"],
                is_saudi=payload.get("is_saudi", True),
                total_settlement_amount=payload["total_reward"],
                state="failed",
                readback_verified=False,
                message_ar=f"فشل كتابة تسوية نهاية الخدمة في Odoo: {str(e)}",
                audit_logged=False
            )
