"""
خدمة التحليلات الشاملة ولوحة المؤشرات التنفيذية (HR Executive Analytics & Dashboard Service - Phase 20)
=============================================================================
محرك التحليلات والذكاء التشغيلي الموحد لمنظومة Odoo HR المتوافقة مع نظام العمل السعودي:
1. مؤشرات القوى العاملة ونسب التوطين (Saudization & Nitaqat Engine):
   - احتساب دقيق لنسب التوطين الحالية ونطاق المنشأة (بلاتيني، أخضر مرتفع/متوسط/منخفض، أحمر).
   - التمييز الحتمي بين المواطن السعودي والوافد المقيم مع توزيع الجنس والأقسام.
   - محاكي التوطين (Saudization Simulator) للتنبؤ بأثر التعيينات المستقبلية.
2. مؤشرات العمليات التشغيلية (Operations & Attendance):
   - الإجازات المعلقة والمصادق عليها، الحضور والانصراف، وساعات العمل الإضافي.
3. مؤشرات الالتزامات المالية والرواتب (Financials & Wage Protection):
   - مخصصات نهاية الخدمة، أرصدة السلف والقروض، مسير الرواتب التقديري، واشتراكات GOSI.
4. مؤشرات الامتثال والمخاطر النظامية (Compliance Health Score):
   - تقييم سلامة الامتثال لنظام العمل ولوائح وزارة الموارد البشرية والتأمينات (من 100%).
   - تنبيهات انتهاء الإقامات والعقود، الجزاءات وفترات التجربة.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from odoo_readonly_repository import OdooReadonlyRepository
from contract_service import (
    GOSI_SAUDI_EMPLOYEE_RATE,
    GOSI_SAUDI_EMPLOYER_RATE,
    GOSI_NON_SAUDI_EMPLOYER_RATE,
    GOSI_MIN_CONTRIBUTORY_WAGE,
    GOSI_MAX_CONTRIBUTORY_WAGE,
    NITAQAT_MIN_FULL_SAUDIZATION_WAGE,
)


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

    return True


def determine_nitaqat_band(saudization_pct: float) -> Tuple[str, str, str]:
    """
    تحديد نطاق المنشأة في برنامج نطاقات التابع لوزارة الموارد البشرية والتنمية الاجتماعية:
    يرجع: (اسم النطاق بالعربية, رمز النطاق, الحالة والتقييم)
    """
    if saudization_pct >= 50.0:
        return "النطاق البلاتيني (Platinum)", "platinum", "🟢 ممتاز - الاستفادة الكاملة من كافة تأشيرات وتسهيلات الوزارة"
    elif saudization_pct >= 40.0:
        return "النطاق الأخضر المرتفع (High Green)", "green_high", "🟢 آمن - تسهيلات واسعة في إصدار وتجديد رخص العمل"
    elif saudization_pct >= 25.0:
        return "النطاق الأخضر المتوسط (Mid Green)", "green_mid", "🟢 مقبول - التزام بالحد الأدنى من نسب التوطين للقطاع"
    elif saudization_pct >= 15.0:
        return "النطاق الأخضر المنخفض (Low Green)", "green_low", "🟡 حذر - قريب من منطقة الخطر، ينصح بزيادة التعيينات الوطنية"
    else:
        return "النطاق الأحمر (Red - حرج)", "red", "🔴 خطر حرج - إيقاف خدمات الوزارة وحظر إصدار ونقل التأشيرات"


@dataclass
class WorkforceKpis:
    total_employees: int
    saudi_count: int
    non_saudi_count: int
    saudization_rate_pct: float
    nitaqat_band_name: str
    nitaqat_code: str
    nitaqat_status_ar: str
    male_count: int
    female_count: int
    unspecified_gender_count: int
    departments_count: int
    top_departments: List[Dict[str, Any]]


@dataclass
class OperationsKpis:
    pending_leaves_count: int
    approved_leaves_count: int
    today_checkins_count: int
    currently_active_checkins_count: int
    total_monthly_overtime_hours: float


@dataclass
class FinancialKpis:
    active_loans_count: int
    total_active_loans_balance: float
    monthly_loan_recovery_run: float
    estimated_monthly_gross_payroll: float
    estimated_monthly_gosi_employer_cost: float
    estimated_monthly_gosi_employee_deductions: float
    total_eosb_settled_amount: float


@dataclass
class ComplianceKpis:
    health_score: int
    rating_label_ar: str
    expiring_iqamas_30d: int
    expiring_iqamas_60d: int
    expiring_iqamas_90d: int
    pending_disciplinary_count: int
    active_probation_count: int
    compliance_alerts: List[str]
    actionable_recommendations_ar: List[str]


@dataclass
class RecruitmentKpis:
    open_jobs_count: int
    total_applicants_count: int
    saudi_applicants_count: int
    expat_applicants_count: int
    saudization_pipeline_pct: float


@dataclass
class SaudizationSimResult:
    current_employees: int
    current_saudi: int
    current_rate_pct: float
    current_band: str
    simulated_employees: int
    simulated_saudi: int
    simulated_rate_pct: float
    simulated_band: str
    is_improved: bool
    status_change_ar: str
    legal_advice_ar: str


@dataclass
class UnifiedDashboardData:
    timestamp: str
    generated_at_ar: str
    workforce: WorkforceKpis
    operations: OperationsKpis
    financial: FinancialKpis
    compliance: ComplianceKpis
    recruitment: RecruitmentKpis
    summary_message_ar: str


class AnalyticsService:
    """
    خدمة التحليلات التنفيذية الشاملة لمنظومة إدارة الموارد البشرية Odoo HR.
    """

    def __init__(self, readonly_repo: Optional[OdooReadonlyRepository] = None):
        self.readonly_repo = readonly_repo or OdooReadonlyRepository()

    def get_workforce_kpis(self) -> WorkforceKpis:
        """
        احتساب مؤشرات القوى العاملة والتوطين (Saudization & Demographics).
        """
        employees = self.readonly_repo.get_employees(limit=500, active_only=True)
        total = len(employees)
        saudi = 0
        non_saudi = 0
        male = 0
        female = 0
        unspecified_gender = 0
        dept_counts: Dict[str, int] = {}

        for emp in employees:
            is_s = detect_employee_nationality(emp)
            if is_s:
                saudi += 1
            else:
                non_saudi += 1

            gender = str(emp.get("sex") or "").lower()
            if gender in ("male", "ذكر", "m"):
                male += 1
            elif gender in ("female", "أنثى", "f"):
                female += 1
            else:
                unspecified_gender += 1

            dept = emp.get("department_id")
            dept_name = dept[1] if (dept and isinstance(dept, (list, tuple)) and len(dept) > 1) else "بدون قسم"
            dept_counts[dept_name] = dept_counts.get(dept_name, 0) + 1

        saudization_pct = round((saudi / total * 100.0), 2) if total > 0 else 0.0
        band_name, band_code, band_status = determine_nitaqat_band(saudization_pct)

        sorted_depts = sorted(dept_counts.items(), key=lambda x: x[1], reverse=True)
        top_depts = [{"department": k, "count": v} for k, v in sorted_depts[:5]]

        return WorkforceKpis(
            total_employees=total,
            saudi_count=saudi,
            non_saudi_count=non_saudi,
            saudization_rate_pct=saudization_pct,
            nitaqat_band_name=band_name,
            nitaqat_code=band_code,
            nitaqat_status_ar=band_status,
            male_count=male,
            female_count=female,
            unspecified_gender_count=unspecified_gender,
            departments_count=len(dept_counts),
            top_departments=top_depts,
        )

    def get_operations_kpis(self) -> OperationsKpis:
        """
        احتساب مؤشرات العمليات التشغيلية (الإجازات، الحضور، الإضافي).
        """
        leaves = self.readonly_repo.get_all_leaves(limit=200)
        pending_leaves = sum(1 for l in leaves if str(l.get("state")) in ("confirm", "validate1"))
        approved_leaves = sum(1 for l in leaves if str(l.get("state")) == "validate")

        today_str = date.today().isoformat()
        attendances = self.readonly_repo.get_all_attendances(limit=200)

        today_att = [a for a in attendances if str(a.get("date") or a.get("check_in") or "").startswith(today_str)]
        active_checkins = sum(1 for a in today_att if not a.get("check_out"))

        total_ot = sum(float(a.get("overtime_hours") or 0.0) for a in attendances)

        return OperationsKpis(
            pending_leaves_count=pending_leaves,
            approved_leaves_count=approved_leaves,
            today_checkins_count=len(today_att),
            currently_active_checkins_count=active_checkins,
            total_monthly_overtime_hours=round(total_ot, 2),
        )

    def get_financial_kpis(self) -> FinancialKpis:
        """
        احتساب مؤشرات الالتزامات المالية والرواتب والتأمينات الاجتماعية.
        """
        loans = self.readonly_repo.get_all_loans(limit=200)
        active_loans = [l for l in loans if str(l.get("state")) in ("approve", "active", "paid")]
        loans_bal = sum(float(l.get("loan_amount") or 0.0) for l in active_loans)
        loans_recovery = sum(float(l.get("installment_amount") or 0.0) for l in active_loans)

        contracts = self.readonly_repo.get_all_contracts(limit=200)
        gross_payroll = 0.0
        gosi_er = 0.0
        gosi_ee = 0.0

        for c in contracts:
            basic = float(c.get("wage") or 0.0)
            housing = float(c.get("l10n_sa_housing_allowance") or (basic * 0.25))
            transport = float(c.get("l10n_sa_transportation_allowance") or (basic * 0.10))
            other = float(c.get("l10n_sa_other_allowances") or 0.0)
            gross = float(c.get("total") or (basic + housing + transport + other))
            gross_payroll += gross

            is_s = bool(c.get("is_saudi", True))
            contrib_wage = min(GOSI_MAX_CONTRIBUTORY_WAGE, max(GOSI_MIN_CONTRIBUTORY_WAGE, basic + housing)) if (basic + housing) > 0 else 0.0

            if is_s:
                gosi_ee += (contrib_wage * GOSI_SAUDI_EMPLOYEE_RATE)
                gosi_er += (contrib_wage * GOSI_SAUDI_EMPLOYER_RATE)
            else:
                gosi_er += (contrib_wage * GOSI_NON_SAUDI_EMPLOYER_RATE)

        eos_records = self.readonly_repo.get_all_eos_records(limit=200)
        total_eosb = sum(float(e.get("amount") or e.get("total_reward") or 0.0) for e in eos_records if str(e.get("state")) in ("approved", "done", "paid"))

        return FinancialKpis(
            active_loans_count=len(active_loans),
            total_active_loans_balance=round(loans_bal, 2),
            monthly_loan_recovery_run=round(loans_recovery, 2),
            estimated_monthly_gross_payroll=round(gross_payroll, 2),
            estimated_monthly_gosi_employer_cost=round(gosi_er, 2),
            estimated_monthly_gosi_employee_deductions=round(gosi_ee, 2),
            total_eosb_settled_amount=round(total_eosb, 2),
        )

    def get_compliance_kpis(self) -> ComplianceKpis:
        """
        احتساب مؤشر الصحة والامتثال النظامي ومخاطر انتهاء الإقامات والعقود.
        """
        score = 100
        alerts: List[str] = []
        recs: List[str] = []

        # 1. فحص التوطين ونطاقات
        wf = self.get_workforce_kpis()
        if wf.total_employees > 0:
            if wf.nitaqat_code == "red":
                score -= 30
                alerts.append(f"🚨 المنشأة في {wf.nitaqat_band_name} (نسبة التوطين {wf.saudization_rate_pct}%). هناك خطر إيقاف الخدمات.")
                recs.append("إعطاء الأولوية القصوى لتوظيف الكفاءات الوطنية عبر المنصة الوطنية الموحدة للتوظيف (جدارات).")
            elif wf.nitaqat_code == "green_low":
                score -= 10
                alerts.append(f"⚠️ المنشأة في {wf.nitaqat_band_name} (نسبة التوطين {wf.saudization_rate_pct}%). يرجى الحذر من الهبوط للنطاق الأحمر.")
                recs.append("تعيين موظفين سعوديين إضافيين أو مراجعة عقود الموظفين لضمان بقاء المنشأة في النطاق الأخضر المرتفع.")

        # 2. فحص الإقامات وقرب انتهائها من المعاملات الحكومية
        gr_records = self.readonly_repo.get_all_gr_transactions(limit=200)
        exp_30 = 0
        exp_60 = 0
        exp_90 = 0
        today = date.today()

        for g in gr_records:
            t_date_str = str(g.get("transaction_date") or "")
            if t_date_str:
                try:
                    t_date = date.fromisoformat(t_date_str[:10])
                    delta = (t_date - today).days
                    if 0 <= delta <= 30:
                        exp_30 += 1
                    elif 31 <= delta <= 60:
                        exp_60 += 1
                    elif 61 <= delta <= 90:
                        exp_90 += 1
                except Exception:
                    pass

        if exp_30 > 0:
            score -= 15
            alerts.append(f"⏰ توجد {exp_30} وثيقة/إقامة تنتهي خلال أقل من 30 يوماً وتتطلب التجديد الفوري لتفادي غرامات الجوازات.")
            recs.append("سداد رسوم المقابل المالي ورخص العمل وتجديد الإقامات عبر منصة مقيم وقوى دون تأخير.")

        # 3. فحص الجزاءات والتحقيقات العالقة
        # إذا كانت هناك جزاءات عالقة تتجاوز 30 يوماً بموجب المادة 72
        disc_actions = self.readonly_repo.get_employee_disciplinary_actions(employee_id=0, limit=50) if hasattr(self.readonly_repo, "get_employee_disciplinary_actions") else []
        pending_disc = sum(1 for d in disc_actions if str(d.get("state")) in ("draft", "under_investigation"))
        if pending_disc > 0:
            score -= 5
            alerts.append(f"⚖️ توجد {pending_disc} إجراءات تأديبية وتحقيقات معلقة تتطلب البت النظامي خلال 30 يوماً بموجب المادة 72.")

        # 4. فحص فترات التجربة
        contracts = self.readonly_repo.get_all_contracts(limit=200)
        active_probations = 0
        for c in contracts:
            trial_end_str = str(c.get("trial_date_end") or "")
            if trial_end_str:
                try:
                    trial_end = date.fromisoformat(trial_end_str[:10])
                    if trial_end >= today:
                        active_probations += 1
                except Exception:
                    pass

        score = max(0, min(100, score))
        if score >= 90:
            rating_ar = "امتثال ممتاز 🏆"
        elif score >= 75:
            rating_ar = "امتثال جيد جداً 🟢"
        elif score >= 60:
            rating_ar = "امتثال متوسط 🟡"
        else:
            rating_ar = "مخاطر نظامية حرجة 🔴"

        if not alerts:
            alerts.append("✅ لا توجد مخالفات نظامية رصدت حالياً. بيئة العمل ممتثلة تماماً للأنظمة.")
        if not recs:
            recs.append("المحافظة على وتيرة التدقيق الدوري وتوثيق جميع العقود في منصة قوى وحماية الأجور WPS.")

        return ComplianceKpis(
            health_score=score,
            rating_label_ar=rating_ar,
            expiring_iqamas_30d=exp_30,
            expiring_iqamas_60d=exp_60,
            expiring_iqamas_90d=exp_90,
            pending_disciplinary_count=pending_disc,
            active_probation_count=active_probations,
            compliance_alerts=alerts,
            actionable_recommendations_ar=recs,
        )

    def get_recruitment_kpis(self) -> RecruitmentKpis:
        """
        احتساب مؤشرات التوظيف واستقطاب الكفاءات.
        """
        jobs = self.readonly_repo.get_recruitment_jobs()
        open_jobs = len(jobs)

        applicants = self.readonly_repo.get_applicants(limit=100)
        total_app = len(applicants)
        saudi_app = sum(1 for a in applicants if bool(a.get("is_saudi", False)))
        expat_app = total_app - saudi_app

        pipe_pct = round((saudi_app / total_app * 100.0), 2) if total_app > 0 else 0.0

        return RecruitmentKpis(
            open_jobs_count=open_jobs,
            total_applicants_count=total_app,
            saudi_applicants_count=saudi_app,
            expat_applicants_count=expat_app,
            saudization_pipeline_pct=pipe_pct,
        )

    def simulate_saudization_impact(self, saudi_hires: int = 0, expat_hires: int = 0) -> SaudizationSimResult:
        """
        محاكي أثر التعيينات المستقبلية على نسبة التوطين ونطاق المنشأة (Nitaqat Simulator).
        """
        if saudi_hires < 0 or expat_hires < 0:
            raise ValueError("عدد الموظفين المراد محاكاتهم يجب أن يكون صفراً أو موجباً.")

        wf = self.get_workforce_kpis()
        curr_total = wf.total_employees
        curr_saudi = wf.saudi_count
        curr_rate = wf.saudization_rate_pct
        curr_band = wf.nitaqat_band_name

        sim_total = curr_total + saudi_hires + expat_hires
        sim_saudi = curr_saudi + saudi_hires
        sim_rate = round((sim_saudi / sim_total * 100.0), 2) if sim_total > 0 else 0.0

        sim_band_name, sim_band_code, _ = determine_nitaqat_band(sim_rate)
        is_improved = sim_rate >= curr_rate

        diff = round(sim_rate - curr_rate, 2)
        diff_sign = "+" if diff >= 0 else ""

        if sim_band_name == curr_band:
            status_change = f"ثبات في النطاق ({sim_band_name}) بفارق نسبة {diff_sign}{diff}%"
        elif is_improved:
            status_change = f"ترقية إيجابية من {curr_band} إلى {sim_band_name} (زيادة {diff}%)"
        else:
            status_change = f"تراجع في النطاق من {curr_band} إلى {sim_band_name} (نقصان {diff}%)"

        if sim_rate < 25.0:
            legal_advice = "⚠️ الخطة المقترحة تضع المنشأة في نطاق منخفض أو أحمر، مما قد يترتب عليه حظر التأشيرات وفرض مقابل مالي مرتفع."
        elif is_improved:
            legal_advice = "✅ الخطة المقترحة تدعم مستهدفات التوطين وترفع رصيد المنشأة في تسهيلات وزارة الموارد البشرية."
        else:
            legal_advice = "💡 ينصح بزيادة حصة التعيين للمواطنين لموازنة استقطاب الخبرات الأجنبية والحفاظ على استقرار النطاق."

        return SaudizationSimResult(
            current_employees=curr_total,
            current_saudi=curr_saudi,
            current_rate_pct=curr_rate,
            current_band=curr_band,
            simulated_employees=sim_total,
            simulated_saudi=sim_saudi,
            simulated_rate_pct=sim_rate,
            simulated_band=sim_band_name,
            is_improved=is_improved,
            status_change_ar=status_change,
            legal_advice_ar=legal_advice,
        )

    def get_unified_dashboard(self) -> UnifiedDashboardData:
        """
        توليد مخرجات لوحة المؤشرات الشاملة التي تجمع كل المجالات في شاشة تنفيذية واحدة.
        """
        now = datetime.now(timezone.utc)
        now_ar = now.strftime("%Y-%m-%d %H:%M:%S UTC")

        wf = self.get_workforce_kpis()
        ops = self.get_operations_kpis()
        fin = self.get_financial_kpis()
        comp = self.get_compliance_kpis()
        rec = self.get_recruitment_kpis()

        summary = (
            f"لوحة المؤشرات التنفيذية محدثة: إجمالي القوى العاملة {wf.total_employees} موظف "
            f"(توطين: {wf.saudization_rate_pct}% - {wf.nitaqat_band_name}). "
            f"مؤشر الامتثال النظامي: {comp.health_score}/100 ({comp.rating_label_ar})."
        )

        return UnifiedDashboardData(
            timestamp=now.isoformat(),
            generated_at_ar=now_ar,
            workforce=wf,
            operations=ops,
            financial=fin,
            compliance=comp,
            recruitment=rec,
            summary_message_ar=summary,
        )
