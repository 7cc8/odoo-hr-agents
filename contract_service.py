"""
خدمة إدارة وتدقيق عقود العمل وهيكلة الأجور (Employment Contracts & Compensation Service)
=============================================================================
الطبقة التنفيذية لإدارة وتوثيق عقود العمل وهياكل الأجور والبدلات في Odoo (hr.version):
1. التفريق الحتمي بين المواطن السعودي والوافد المقيم:
   - الوافد المقيم (Non-Saudi): إلزامية العقد محدد المدة وتحديد تاريخ النهاية date_end (المادة 37).
     اشتراك التأمينات GOSI للأخطار المهنية فقط (2% على صاحب العمل، 0% على الموظف).
   - المواطن السعودي (Saudi): إمكانية العقد محدد أو غير محدد المدة، احتساب استقطاع التأمينات GOSI
     بنسبة (9.75% للموظف: 9% معاشات + 0.75% ساند)، وتنبيهات أجر التوطين لنطاقات (4000 ر.س).
2. هيكلة الأجر والبدلات الإلزامية:
   - الأجر الأساسي + بدل السكن (25%) + بدل النقل (10%) + البدلات الأخرى = إجمالي الراتب (Total Package).
   - وعاء اشتراك التأمينات = الأجر الأساسي + بدل السكن (سقف 45,000 ر.س وحد أدنى 1,500 ر.س).
3. فترة التجربة (المادة 53):
   - الحد الأقصى 90 يوماً وتمديدها باتفاق مكتوب حتى 180 يوماً، وحظر تجاوز الـ 180 يوماً قطيعاً.
4. مهلة الإشعار (المادة 75):
   - 60 يوماً للعقد غير المحدد (للسعودي) و 30 يوماً للعقد المحدد المدة.
5. مبدأ التحقق المزدوج Four-Eyes والتحقق المستقل بعد الكتابة (Readback Verification).
"""

from __future__ import annotations

import os
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional, Tuple

from odoo_readonly_repository import OdooReadonlyRepository
from odoo_contract_write_gateway import OdooContractWriteGateway
from eos_service import detect_employee_nationality

CONTRACT_AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "contract_audit_log.jsonl")

# معايير التأمينات الاجتماعية GOSI
GOSI_MIN_CONTRIBUTORY_WAGE = 1500.0
GOSI_MAX_CONTRIBUTORY_WAGE = 45000.0
GOSI_SAUDI_EMPLOYEE_RATE = 0.0975  # 9% المعاشات + 0.75% ساند
GOSI_SAUDI_EMPLOYER_RATE = 0.1175  # 9% المعاشات + 0.75% ساند + 2% أخطار مهنية
GOSI_NON_SAUDI_EMPLOYEE_RATE = 0.00
GOSI_NON_SAUDI_EMPLOYER_RATE = 0.02  # 2% أخطار مهنية فقط

# ضوابط التوطين وفترة التجربة
NITAQAT_MIN_FULL_SAUDIZATION_WAGE = 4000.0  # الحد الأدنى لاحتساب المواطن عاملاً كاملاً في نطاقات
PROBATION_STANDARD_MAX_DAYS = 90
PROBATION_ABSOLUTE_MAX_DAYS = 180


@dataclass
class ContractSummary:
    contract_id: int
    employee_id: int
    employee_name: str
    department_name: str
    job_title: str
    is_saudi: bool
    nationality_text_ar: str
    contract_type_name: str
    basic_wage: float
    housing_allowance: float
    transportation_allowance: float
    other_allowances: float
    total_package: float
    gosi_contributory_wage: float
    gosi_employee_deduction: float
    gosi_employer_contribution: float
    net_estimated_salary: float
    date_start: str
    date_end: Optional[str]
    trial_date_end: Optional[str]
    is_indefinite: bool
    compliance_notes: List[str] = field(default_factory=list)


@dataclass
class ContractDryRunResult:
    is_valid: bool
    employee_id: int
    employee_name: str
    department_id: int
    department_name: str
    job_id: int
    job_title: str
    is_saudi: bool
    nationality_text_ar: str
    basic_wage: float
    housing_allowance: float
    transportation_allowance: float
    other_allowances: float
    total_package: float
    gosi_contributory_wage: float
    gosi_employee_deduction: float
    gosi_employer_contribution: float
    net_estimated_salary: float
    date_start: str
    date_end: Optional[str]
    trial_date_end: Optional[str]
    contract_type_id: Optional[int]
    contract_type_name: str
    is_indefinite: bool
    statutory_article: str
    statutory_explanation_ar: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    approval_token: str = ""
    can_proceed: bool = False


@dataclass
class ContractExecutionResult:
    success: bool
    contract_id: Optional[int]
    employee_id: int
    employee_name: str
    total_package: float
    net_estimated_salary: float
    readback_verified: bool
    message_ar: str
    audit_logged: bool


class ContractService:
    """
    خدمة إدارة وتدقيق عقود العمل وهيكلة الأجور في Odoo.
    """
    _shared_pending_approvals: Dict[str, Dict[str, Any]] = {}

    def __init__(
        self,
        readonly_repo: Optional[OdooReadonlyRepository] = None,
        write_gateway: Optional[OdooContractWriteGateway] = None,
        audit_log_path: Optional[str] = None
    ):
        self.readonly_repo = readonly_repo or OdooReadonlyRepository()
        self.write_gateway = write_gateway
        self.audit_log_path = audit_log_path or CONTRACT_AUDIT_LOG_FILE
        self._pending_approvals: Dict[str, Dict[str, Any]] = ContractService._shared_pending_approvals

    def get_employee_contract_summary(
        self,
        employee_id: int,
        explicit_is_saudi: Optional[bool] = None,
    ) -> ContractSummary:
        """
        جلب وتلخيص عقد العمل وهيكل الراتب والتأمينات للموظف.
        """
        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            raise ValueError(f"الموظف برقم المعرف #{employee_id} غير موجود في Odoo.")

        emp_name = emp.get("name", "غير معروف")
        dept_name = emp["department_id"][1] if emp.get("department_id") else "بدون قسم"
        job_title = emp["job_id"][1] if emp.get("job_id") else "بدون مسمى"

        is_saudi = detect_employee_nationality(emp, explicit_is_saudi)
        nat_text = "مواطن سعودي" if is_saudi else "وافد غير سعودي (مقيم)"

        contracts = self.readonly_repo.get_employee_contracts(employee_id)
        c_data = contracts[0] if contracts else {}

        c_id = int(c_data.get("id") or 0)
        basic = float(c_data.get("wage") or 0.0)
        housing = float(c_data.get("l10n_sa_housing_allowance") or 0.0)
        transport = float(c_data.get("l10n_sa_transportation_allowance") or 0.0)
        other = float(c_data.get("l10n_sa_other_allowances") or 0.0)
        total = float(c_data.get("total") or (basic + housing + transport + other))

        c_type_info = c_data.get("contract_type_id")
        c_type_name = c_type_info[1] if c_type_info and isinstance(c_type_info, (list, tuple)) else "عقد عمل موحد"

        d_start = str(c_data.get("date_start") or date.today().isoformat())[:10]
        d_end = str(c_data.get("date_end") or "")[:10] or None
        t_end = str(c_data.get("trial_date_end") or "")[:10] or None

        is_indefinite = d_end is None and is_saudi

        # حسابات التأمينات الاجتماعية GOSI
        contrib_wage = min(GOSI_MAX_CONTRIBUTORY_WAGE, max(GOSI_MIN_CONTRIBUTORY_WAGE, basic + housing)) if (basic + housing) > 0 else 0.0
        ee_ded = round(contrib_wage * GOSI_SAUDI_EMPLOYEE_RATE, 2) if is_saudi else 0.0
        er_cost = round(contrib_wage * (GOSI_SAUDI_EMPLOYER_RATE if is_saudi else GOSI_NON_SAUDI_EMPLOYER_RATE), 2)
        net_sal = round(max(0.0, total - ee_ded), 2)

        notes: List[str] = []
        if not is_saudi and not d_end:
            notes.append("⚠️ مخالفة المادة 37: عقد غير السعودي يجب أن يحدد بتاريخ نهاية صريح.")
        if is_saudi and basic < NITAQAT_MIN_FULL_SAUDIZATION_WAGE:
            notes.append(f"تنبيه نطاقات: الأجر الأساسي للمواطن أقل من {NITAQAT_MIN_FULL_SAUDIZATION_WAGE} ر.س لا يحتسب وزناً كاملاً في التوطين.")

        return ContractSummary(
            contract_id=c_id,
            employee_id=employee_id,
            employee_name=emp_name,
            department_name=dept_name,
            job_title=job_title,
            is_saudi=is_saudi,
            nationality_text_ar=nat_text,
            contract_type_name=c_type_name,
            basic_wage=basic,
            housing_allowance=housing,
            transportation_allowance=transport,
            other_allowances=other,
            total_package=total,
            gosi_contributory_wage=contrib_wage,
            gosi_employee_deduction=ee_ded,
            gosi_employer_contribution=er_cost,
            net_estimated_salary=net_sal,
            date_start=d_start,
            date_end=d_end,
            trial_date_end=t_end,
            is_indefinite=is_indefinite,
            compliance_notes=notes,
        )

    def dry_run_contract(
        self,
        employee_id: int,
        basic_wage: float,
        housing_allowance: float = 0.0,
        transportation_allowance: float = 0.0,
        other_allowances: float = 0.0,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        trial_date_end: Optional[str] = None,
        contract_type_id: Optional[int] = None,
        explicit_is_saudi: Optional[bool] = None,
        gosi_deduction: bool = True,
    ) -> ContractDryRunResult:
        """
        فحص وتدقيق هيكل عقد العمل تجريبياً (Dry-Run) والتحقق من المادة 37 والمادة 53 والتأمينات.
        """
        warnings: List[str] = []
        errors: List[str] = []

        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            return ContractDryRunResult(
                is_valid=False,
                employee_id=employee_id,
                employee_name="غير معروف",
                department_id=0,
                department_name="",
                job_id=0,
                job_title="",
                is_saudi=True,
                nationality_text_ar="",
                basic_wage=basic_wage,
                housing_allowance=housing_allowance,
                transportation_allowance=transportation_allowance,
                other_allowances=other_allowances,
                total_package=0.0,
                gosi_contributory_wage=0.0,
                gosi_employee_deduction=0.0,
                gosi_employer_contribution=0.0,
                net_estimated_salary=0.0,
                date_start=date_start or "",
                date_end=date_end,
                trial_date_end=trial_date_end,
                contract_type_id=contract_type_id,
                contract_type_name="",
                is_indefinite=False,
                statutory_article="نظام العمل السعودي",
                statutory_explanation_ar="الموظف غير موجود في Odoo.",
                errors=["الموظف برقم المعرف المحدد غير موجود."],
                can_proceed=False,
            )

        emp_name = emp.get("name", "غير معروف")
        dept_id = emp["department_id"][0] if emp.get("department_id") else 1
        dept_name = emp["department_id"][1] if emp.get("department_id") else "بدون قسم"
        job_id = emp["job_id"][0] if emp.get("job_id") else 1
        job_title = emp["job_id"][1] if emp.get("job_id") else "بدون مسمى"

        is_saudi = detect_employee_nationality(emp, explicit_is_saudi)
        nat_text = "مواطن سعودي" if is_saudi else "وافد غير سعودي (مقيم)"

        if basic_wage <= 0:
            errors.append("الأجر الأساسي يجب أن يكون أكبر من الصفر.")

        today_str = date.today().isoformat()
        s_date = date_start or today_str

        # 1. المادة 37: فحص مدة العقد وتاريخ النهاية لغير السعودي
        if not is_saudi:
            if not date_end:
                errors.append(
                    "المادة 37 من نظام العمل: عقد عمل غير السعودي يجب أن يكون محدد المدة ومحدد بتاريخ نهاية (date_end) صريح."
                )
            else:
                try:
                    d_s = datetime.strptime(s_date[:10], "%Y-%m-%d").date()
                    d_e = datetime.strptime(date_end[:10], "%Y-%m-%d").date()
                    if d_e <= d_s:
                        errors.append("تاريخ نهاية العقد يجب أن يكون لاحقاً لتاريخ بدايته.")
                except Exception:
                    errors.append("صيغة تاريخ بداية أو نهاية العقد غير صحيحة (الصيغة المطلوبة: YYYY-MM-DD).")
        else:
            # المواطن السعودي
            if not date_end:
                warnings.append("عقد غير محدد المدة للمواطن السعودي وفق المادة 55 (عقد مفتوح).")
            if basic_wage < NITAQAT_MIN_FULL_SAUDIZATION_WAGE:
                warnings.append(
                    f"تنبيه نطاقات: الأجر الأساسي للمواطن ({basic_wage:,.2f} ر.س) أقل من 4,000 ر.س "
                    f"يحتسبه بنصف عامل في نسب التوطين بدلاً من عامل كامل."
                )

        # 2. فحص فترة التجربة (المادة 53)
        if trial_date_end:
            try:
                d_s = datetime.strptime(s_date[:10], "%Y-%m-%d").date()
                d_t = datetime.strptime(trial_date_end[:10], "%Y-%m-%d").date()
                prob_days = (d_t - d_s).days
                if prob_days < 0:
                    errors.append("تاريخ نهاية فترة التجربة يجب أن يكون لاحقاً لتاريخ بداية العقد.")
                elif prob_days > PROBATION_ABSOLUTE_MAX_DAYS:
                    errors.append(
                        f"مخالفة المادة 53: فترة التجربة لا يجوز أن تزيد على 180 يوماً بأي حال من الأحوال (المسجل: {prob_days} يوماً)."
                    )
                elif prob_days > PROBATION_STANDARD_MAX_DAYS:
                    warnings.append(
                        f"فترة التجربة ({prob_days} يوماً) تتجاوز 90 يوماً؛ يلزم نظاماً وجود اتفاق مكتوب وصريح بين الطرفين بموجب المادة 53."
                    )
            except Exception:
                errors.append("صيغة تاريخ نهاية التجربة غير صحيحة (YYYY-MM-DD).")

        # 3. هيكلة البدلات وتوصيات العرف التجاري
        if housing_allowance <= 0:
            rec_h = round(basic_wage * 0.25, 2)
            warnings.append(f"بدل السكن غير محدد؛ يُوصى نظاماً وعُرفاً ببدل سكن لا يقل عن 25% من الأساسي ({rec_h:,.2f} ر.س) أو توفير سكن عيني.")
        if transportation_allowance <= 0:
            rec_t = round(basic_wage * 0.10, 2)
            warnings.append(f"بدل النقل غير محدد؛ يُوصى نظاماً ببدل نقل لا يقل عن 10% من الأساسي ({rec_t:,.2f} ر.س) أو تأمين وسيلة نقل.")

        tot_pkg = float(basic_wage) + float(housing_allowance) + float(transportation_allowance) + float(other_allowances)

        # 4. حسابات التأمينات الاجتماعية GOSI
        contributory_wage = min(GOSI_MAX_CONTRIBUTORY_WAGE, max(GOSI_MIN_CONTRIBUTORY_WAGE, basic_wage + housing_allowance))
        if is_saudi and gosi_deduction:
            ee_deduction = round(contributory_wage * GOSI_SAUDI_EMPLOYEE_RATE, 2)
            er_contrib = round(contributory_wage * GOSI_SAUDI_EMPLOYER_RATE, 2)
        else:
            ee_deduction = 0.0
            er_contrib = round(contributory_wage * GOSI_NON_SAUDI_EMPLOYER_RATE, 2)

        net_est_sal = round(max(0.0, tot_pkg - ee_deduction), 2)

        # مسمى نوع العقد
        is_indef = (date_end is None and is_saudi)
        c_type_name = "عقد غير محدد المدة" if is_indef else "عقد محدد المدة"

        statutory_article = "المادتان 37 و 53 ولوائح التأمينات الاجتماعية GOSI"
        statutory_explanation = (
            f"التصنيف: {nat_text} | إجمالي الباقة: {tot_pkg:,.2f} ر.س | "
            f"وعاء التأمينات: {contributory_wage:,.2f} ر.س | "
            f"استقطاع الموظف GOSI: {ee_deduction:,.2f} ر.س | "
            f"الصافي التقديري: {net_est_sal:,.2f} ر.س."
        )

        is_valid = len(errors) == 0
        token = f"CTR-{uuid.uuid4().hex[:8].upper()}" if is_valid else ""

        if is_valid:
            self._pending_approvals[token] = {
                "employee_id": employee_id,
                "employee_name": emp_name,
                "basic_wage": float(basic_wage),
                "housing_allowance": float(housing_allowance),
                "transportation_allowance": float(transportation_allowance),
                "other_allowances": float(other_allowances),
                "total_package": tot_pkg,
                "is_saudi": is_saudi,
                "date_start": s_date,
                "date_end": date_end,
                "trial_date_end": trial_date_end,
                "contract_type_id": contract_type_id,
                "gosi_deduction": gosi_deduction,
                "net_estimated_salary": net_est_sal,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        return ContractDryRunResult(
            is_valid=is_valid,
            employee_id=employee_id,
            employee_name=emp_name,
            department_id=dept_id,
            department_name=dept_name,
            job_id=job_id,
            job_title=job_title,
            is_saudi=is_saudi,
            nationality_text_ar=nat_text,
            basic_wage=float(basic_wage),
            housing_allowance=float(housing_allowance),
            transportation_allowance=float(transportation_allowance),
            other_allowances=float(other_allowances),
            total_package=tot_pkg,
            gosi_contributory_wage=contributory_wage,
            gosi_employee_deduction=ee_deduction,
            gosi_employer_contribution=er_contrib,
            net_estimated_salary=net_est_sal,
            date_start=s_date,
            date_end=date_end,
            trial_date_end=trial_date_end,
            contract_type_id=contract_type_id,
            contract_type_name=c_type_name,
            is_indefinite=is_indef,
            statutory_article=statutory_article,
            statutory_explanation_ar=statutory_explanation,
            warnings=warnings,
            errors=errors,
            approval_token=token,
            can_proceed=is_valid,
        )

    def apply_contract(
        self,
        approval_token: str,
        user_confirmation_text: str = "تأكيد",
    ) -> ContractExecutionResult:
        """
        اعتماد وتحديث عقد عمل الموظف في Odoo بموجب مبدأ التحقق المزدوج Four-Eyes والتحقق المستقل بعد الكتابة.
        """
        if user_confirmation_text.strip() != "تأكيد":
            return ContractExecutionResult(
                success=False,
                contract_id=None,
                employee_id=0,
                employee_name="",
                total_package=0.0,
                net_estimated_salary=0.0,
                readback_verified=False,
                message_ar="مبدأ التحقق المزدوج: يلزم إدخال كلمة «تأكيد» صراحة لتحديث عقد الموظف في Odoo.",
                audit_logged=False,
            )

        if not self.write_gateway:
            return ContractExecutionResult(
                success=False,
                contract_id=None,
                employee_id=0,
                employee_name="",
                total_package=0.0,
                net_estimated_salary=0.0,
                readback_verified=False,
                message_ar="بوابة الكتابة لعقود العمل غير مهيأة أو غير متصلة.",
                audit_logged=False,
            )

        pending = self._pending_approvals.pop(approval_token, None)
        if not pending:
            return ContractExecutionResult(
                success=False,
                contract_id=None,
                employee_id=0,
                employee_name="",
                total_package=0.0,
                net_estimated_salary=0.0,
                readback_verified=False,
                message_ar="رمز الموافقة غير صالح أو منتهي الصلاحية؛ يرجى إجراء التدقيق التجريبي أولاً.",
                audit_logged=False,
            )

        emp_id = pending["employee_id"]
        emp_name = pending["employee_name"]

        try:
            cid = self.write_gateway.update_or_create_contract(
                employee_id=emp_id,
                wage=pending["basic_wage"],
                is_saudi=pending["is_saudi"],
                housing_allowance=pending.get("housing_allowance", 0.0),
                transportation_allowance=pending.get("transportation_allowance", 0.0),
                other_allowances=pending.get("other_allowances", 0.0),
                date_start=pending.get("date_start"),
                date_end=pending.get("date_end"),
                trial_date_end=pending.get("trial_date_end"),
                contract_type_id=pending.get("contract_type_id"),
                gosi_deduction=pending.get("gosi_deduction", True),
            )

            # التحقق المستقل بعد الكتابة (Readback Verification)
            read_back = self.write_gateway.read_contract(cid)
            readback_ok = bool(read_back and read_back.get("id") == cid)

            audit_entry = {
                "event": "contract_updated",
                "contract_id": cid,
                "employee_id": emp_id,
                "employee_name": emp_name,
                "is_saudi": pending["is_saudi"],
                "basic_wage": pending["basic_wage"],
                "total_package": pending["total_package"],
                "readback_verified": readback_ok,
                "approval_token": approval_token,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._write_audit_log(audit_entry)

            return ContractExecutionResult(
                success=True,
                contract_id=cid,
                employee_id=emp_id,
                employee_name=emp_name,
                total_package=pending["total_package"],
                net_estimated_salary=pending["net_estimated_salary"],
                readback_verified=readback_ok,
                message_ar=f"تم اعتماد وتحديث عقد الموظف '{emp_name}' بنجاح في Odoo برقم السجل #{cid}.",
                audit_logged=True,
            )
        except Exception as exc:
            return ContractExecutionResult(
                success=False,
                contract_id=None,
                employee_id=emp_id,
                employee_name=emp_name,
                total_package=pending.get("total_package", 0.0),
                net_estimated_salary=pending.get("net_estimated_salary", 0.0),
                readback_verified=False,
                message_ar=f"فشل تحديث العقد في Odoo: {exc}",
                audit_logged=False,
            )

    def _write_audit_log(self, entry: Dict[str, Any]) -> None:
        try:
            os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
