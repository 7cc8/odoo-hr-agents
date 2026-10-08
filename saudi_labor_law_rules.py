"""
محرك قواعد نظام العمل السعودي وتعديلات 1446هـ (Saudi Labor Law Rule Engine)
=============================================================================
محرك حتمي (Deterministic)، دقيق ومطابق بنسبة 100% لنظام العمل السعودي
الصادر بالمرسوم الملكي رقم (م/51) وتعديلاته الصادرة بالمرسوم الملكي رقم (م/44)
بتاريخ 1446/02/08هـ، ولوائح المؤسسة العامة للتأمينات الاجتماعية (GOSI).

يراعي المحرك بدقة وحزم:
1. الفوارق النظامية بين الموظف السعودي وغير السعودي (GOSI، المادة 37، المادة 77).
2. تعديلات 1446هـ (إجازات المناسبات م/113، إجازة الوضع م/116، التجربة م/53).
3. سقوف الاستقطاعات القانونية (القروض م/92، الجزاءات م/70).
4. معادلات نهاية الخدمة (م/84، م/85، م/87) والأوفرتايم (م/98، م/107).
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
import math


# =============================================================================
# 1. الثوابت والمعايير النظامية (Statutory Constants)
# =============================================================================

# GOSI: التأمينات الاجتماعية
GOSI_MIN_CONTRIBUTORY_WAGE = 1500.0   # الحد الأدنى للأجر الخاضع للاشتراك
GOSI_MAX_CONTRIBUTORY_WAGE = 45000.0  # الحد الأقصى للأجر الخاضع للاشتراك (السقف)

# نسب السعودي
GOSI_SAUDI_PENSION_EMPLOYER = 0.09      # المعاشات - صاحب العمل (9%)
GOSI_SAUDI_PENSION_EMPLOYEE = 0.09      # المعاشات - الموظف (9%)
GOSI_SAUDI_HAZARDS_EMPLOYER = 0.02      # الأخطار المهنية - صاحب العمل (2%)
GOSI_SAUDI_HAZARDS_EMPLOYEE = 0.00      # الأخطار المهنية - الموظف (0%)
GOSI_SAUDI_SANED_EMPLOYER = 0.0075      # ساند (التعطل) - صاحب العمل (0.75%)
GOSI_SAUDI_SANED_EMPLOYEE = 0.0075      # ساند (التعطل) - الموظف (0.75%)

# نسب غير السعودي
GOSI_NON_SAUDI_PENSION_EMPLOYER = 0.00  # المعاشات غير مشمولة لغير السعودي
GOSI_NON_SAUDI_PENSION_EMPLOYEE = 0.00
GOSI_NON_SAUDI_HAZARDS_EMPLOYER = 0.02  # الأخطار المهنية فقط - صاحب العمل (2%)
GOSI_NON_SAUDI_HAZARDS_EMPLOYEE = 0.00
GOSI_NON_SAUDI_SANED_EMPLOYER = 0.00    # ساند غير مشمول لغير السعودي
GOSI_NON_SAUDI_SANED_EMPLOYEE = 0.00

# المادة 53: فترة التجربة
PROBATION_STANDARD_DAYS_MAX = 90
PROBATION_EXTENDED_DAYS_MAX = 180

# المادة 70: الجزاءات
DISCIPLINARY_MAX_DAYS_PER_INFRACTION = 5.0
DISCIPLINARY_MAX_DAYS_PER_MONTH = 5.0
DISCIPLINARY_MAX_SUSPENSION_DAYS_PER_MONTH = 5.0

# المواد 71 و 72: تقادم وتكرار المخالفات
DISCIPLINARY_REPETITION_EXPIRY_DAYS = 180  # المادة 71: سقوط أثر تكرار المخالفة بعد مضي 180 يوماً
DISCIPLINARY_DISCOVERY_LIMIT_DAYS = 30     # المادة 72: عدم جواز اتهام العامل بعد مضي 30 يوماً على كشف المخالفة
DISCIPLINARY_DECISION_LIMIT_DAYS = 30      # المادة 72: عدم جواز توقيع الجزاء بعد مضي 30 يوماً على انتهاء التحقيق

# المادة 92: القروض
LOAN_DEDUCTION_MAX_PERCENTAGE = 0.10  # سقف استقطاع قروض صاحب العمل 10% من الأجر (محدث بموجب تعديل المادة 92 المعلن)

# المادة 98: ساعات العمل
STANDARD_DAILY_WORKING_HOURS = 8.0
STANDARD_WEEKLY_WORKING_HOURS = 48.0
RAMADAN_MUSLIM_DAILY_HOURS = 6.0
RAMADAN_MUSLIM_WEEKLY_HOURS = 36.0

# المادة 107: العمل الإضافي
OVERTIME_PREMIUM_RATE = 0.50  # 50% علاوة إضافية على أجر الساعة الفعلي (إجمالي 1.5x)

# المادة 109: الإجازة السنوية
ANNUAL_LEAVE_INITIAL_DAYS = 21
ANNUAL_LEAVE_SENIOR_DAYS = 30
ANNUAL_LEAVE_SENIORITY_THRESHOLD_YEARS = 5.0

# المادة 113: إجازات المناسبات (تعديلات 1446هـ)
OCCASION_LEAVE_MARRIAGE_DAYS = 5
OCCASION_LEAVE_BEREAVEMENT_DIRECT_DAYS = 5   # وفاة الزوج / الأصول / الفروع
OCCASION_LEAVE_BEREAVEMENT_SIBLING_DAYS = 3  # وفاة الأخ أو الأخت (تعديل 1446هـ)
OCCASION_LEAVE_PATERNITY_DAYS = 3           # ولادة مولود (أبوة - تعديل 1446هـ)

# المادة 116: إجازة الوضع (تعديلات 1446هـ)
MATERNITY_LEAVE_WEEKS = 12                  # 12 أسبوعاً بأجر كامل (تعديل 1446هـ)
MATERNITY_LEAVE_POST_DELIVERY_MANDATORY_WEEKS = 6  # 6 أسابيع إلزامية بعد الوضع


# =============================================================================
# 2. الهياكل البيانية (Data Classes)
# =============================================================================

class NationalityType(str, Enum):
    SAUDI = "saudi"
    NON_SAUDI = "non_saudi"


class ContractType(str, Enum):
    FIXED = "fixed"            # محدد المدة
    INDEFINITE = "indefinite"  # غير محدد المدة


class ResignationReason(str, Enum):
    STANDARD = "standard"                  # استقالة عادية
    MARRIAGE_FEMALE = "marriage_female"    # استقالة العاملة خلال 6 أشهر من الزواج (م/87)
    CHILDBIRTH_FEMALE = "childbirth_female"# استقالة العاملة خلال 3 أشهر من الوضع (م/87)
    FORCE_MAJEURE = "force_majeure"        # قوة قاهرة خارجة عن إرادة العامل (م/87)


class OccasionLeaveType(str, Enum):
    MARRIAGE = "marriage"                                # زواج العامل
    DEATH_SPOUSE_PARENT_CHILD = "death_direct"           # وفاة الزوج أو أصل أو فرع
    DEATH_SIBLING = "death_sibling"                      # وفاة أخ أو أخت (1446هـ)
    PATERNITY = "paternity"                              # ولادة مولود للموظف (1446هـ)


@dataclass(frozen=True)
class RuleValidationResult:
    """نتيجة التحقق من أي قاعدة نظامية"""
    is_valid: bool
    article: str
    message_ar: str
    code: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GOSIContributionResult:
    """تفصيل اشتراكات التأمينات الاجتماعية (GOSI)"""
    is_saudi: bool
    basic_wage: float
    housing_allowance: float
    uncapped_contributory_wage: float
    capped_contributory_wage: float
    
    # حصة صاحب العمل
    employer_pension: float
    employer_hazards: float
    employer_saned: float
    total_employer: float
    
    # حصة الموظف (المشترك)
    employee_pension: float
    employee_hazards: float
    employee_saned: float
    total_employee: float
    
    # الإجمالي المشترك
    total_combined: float
    net_wage_after_gosi: float  # الراتب الأساسي والبدل مخصوماً منه استقطاع التأمينات
    article_reference: str
    notes_ar: str


@dataclass(frozen=True)
class EOSBCalculationResult:
    """تفصيل حساب مكافأة نهاية الخدمة (End of Service Benefit)"""
    is_saudi: bool
    service_years: float
    last_gross_wage: float
    is_resignation: bool
    resignation_reason: ResignationReason
    entitlement_ratio: float      # نسبة الاستحقاق (0.0 إلى 1.0)
    tier1_amount: float           # السنوات الخمس الأولى (أجر نصف شهر)
    tier2_amount: float           # ما زاد عن 5 سنوات (أجر شهر كامل)
    gross_eosb_amount: float      # المبلغ المستحق قبل نسبة الاستقالة
    net_eosb_amount: float        # المكافأة النهائية المستحقة للصرف
    article_reference: str
    explanation_ar: str


@dataclass(frozen=True)
class Article77CompensationResult:
    """نتيجة حساب تعويض الإنهاء غير المشروع (المادة 77)"""
    is_saudi: bool
    contract_type: ContractType
    monthly_wage: float
    service_years: float
    remaining_contract_months: float
    formula_used: str
    statutory_calculated_amount: float
    statutory_minimum_amount: float    # أجر شهرين على الأقل
    final_compensation_amount: float
    article_reference: str
    explanation_ar: str


@dataclass(frozen=True)
class OvertimeCalculationResult:
    """نتيجة حساب أجر ساعات العمل الإضافية (المادة 107)"""
    basic_hourly_rate: float
    gross_hourly_rate: float
    overtime_hours: float
    standard_hourly_amount: float
    premium_amount: float         # علاوة الـ 50%
    total_overtime_pay: float
    article_reference: str
    explanation_ar: str


# =============================================================================
# 3. دوال الحساب والتحقق النظامية (Deterministic Functions)
# =============================================================================

def calculate_gosi_contributions(
    basic_wage: float,
    housing_allowance: float,
    is_saudi: bool
) -> GOSIContributionResult:
    """
    حساب اشتراكات التأمينات الاجتماعية (GOSI) للسعودي وغير السعودي بدقة تامة.
    
    الأجر الخاضع للاشتراك = الأجر الأساسي + بدل السكن.
    السقف النظامي: 45,000 ريال، والحد الأدنى: 1,500 ريال.
    
    - للسعودي:
      * صاحب العمل: 9% معاشات + 2% أخطار مهنية + 0.75% ساند = 11.75%
      * الموظف: 9% معاشات + 0.75% ساند = 9.75%
      * الإجمالي: 21.5%
    - لغير السعودي:
      * صاحب العمل: 2% أخطار مهنية فقط.
      * الموظف: 0% (لا يُستقطع شيء من أجر غير السعودي للتأمينات).
      * الإجمالي: 2.0%
    """
    if basic_wage < 0 or housing_allowance < 0:
        raise ValueError("الراتب الأساسي وبدل السكن يجب ألا يكونا بالسالب.")
        
    uncapped = round(basic_wage + housing_allowance, 2)
    # تطبيق السقف والحد الأدنى
    capped = min(max(uncapped, GOSI_MIN_CONTRIBUTORY_WAGE), GOSI_MAX_CONTRIBUTORY_WAGE)

    if is_saudi:
        emp_pension = round(capped * GOSI_SAUDI_PENSION_EMPLOYER, 2)
        emp_hazards = round(capped * GOSI_SAUDI_HAZARDS_EMPLOYER, 2)
        emp_saned = round(capped * GOSI_SAUDI_SANED_EMPLOYER, 2)
        total_emp = round(emp_pension + emp_hazards + emp_saned, 2)
        
        sub_pension = round(capped * GOSI_SAUDI_PENSION_EMPLOYEE, 2)
        sub_hazards = round(capped * GOSI_SAUDI_HAZARDS_EMPLOYEE, 2)
        sub_saned = round(capped * GOSI_SAUDI_SANED_EMPLOYEE, 2)
        total_sub = round(sub_pension + sub_hazards + sub_saned, 2)
        
        notes = (
            f"مشترك سعودي: نسبة صاحب العمل 11.75% ({total_emp:,.2f} ر.س)، "
            f"نسبة الموظف 9.75% ({total_sub:,.2f} ر.س) تشمل المعاشات والأخطار وساند. "
            f"الأجر الخاضع بعد السقف: {capped:,.2f} ر.س."
        )
    else:
        emp_pension = 0.0
        emp_hazards = round(capped * GOSI_NON_SAUDI_HAZARDS_EMPLOYER, 2)
        emp_saned = 0.0
        total_emp = emp_hazards
        
        sub_pension = 0.0
        sub_hazards = 0.0
        sub_saned = 0.0
        total_sub = 0.0
        
        notes = (
            f"مشترك غير سعودي: نسبة صاحب العمل 2.0% أخطار مهنية فقط ({total_emp:,.2f} ر.س)، "
            f"واستقطاع الموظف 0.00 ر.س (لا يستقطع منه تأمينات). "
            f"الأجر الخاضع بعد السقف: {capped:,.2f} ر.س."
        )

    total_combined = round(total_emp + total_sub, 2)
    net_wage = round((basic_wage + housing_allowance) - total_sub, 2)

    return GOSIContributionResult(
        is_saudi=is_saudi,
        basic_wage=basic_wage,
        housing_allowance=housing_allowance,
        uncapped_contributory_wage=uncapped,
        capped_contributory_wage=capped,
        employer_pension=emp_pension,
        employer_hazards=emp_hazards,
        employer_saned=emp_saned,
        total_employer=total_emp,
        employee_pension=sub_pension,
        employee_hazards=sub_hazards,
        employee_saned=sub_saned,
        total_employee=total_sub,
        total_combined=total_combined,
        net_wage_after_gosi=net_wage,
        article_reference="نظام التأمينات الاجتماعية ونظام ساند ولوائحهما التنفيذية",
        notes_ar=notes
    )


def validate_contract_type_for_nationality(
    is_saudi: bool,
    contract_type: ContractType
) -> RuleValidationResult:
    """
    التحقق من نوع العقد وفق المادة 37 من نظام العمل:
    عقد عمل غير السعودي يجب أن يكون حتماً محدد المدة. حظر عقود غير محددة المدة لغير السعودي.
    """
    if not is_saudi and contract_type == ContractType.INDEFINITE:
        return RuleValidationResult(
            is_valid=False,
            article="المادة 37",
            code="NON_SAUDI_INDEFINITE_CONTRACT_PROHIBITED",
            message_ar=(
                "مخالفة للمادة 37 من نظام العمل: يجب أن يكون عقد عمل غير السعودي مكتوباً "
                "ومحدد المدة، ولا يجوز إبرام أو تسجيل عقد غير محدد المدة لعامل غير سعودي."
            ),
            details={"is_saudi": False, "contract_type": contract_type.value}
        )

    return RuleValidationResult(
        is_valid=True,
        article="المادة 37 و 55",
        code="CONTRACT_TYPE_VALID",
        message_ar="نوع العقد متوافق مع نظام العمل وجنسية الموظف.",
        details={"is_saudi": is_saudi, "contract_type": contract_type.value}
    )


def calculate_article_77_compensation(
    monthly_wage: float,
    is_saudi: bool,
    contract_type: ContractType,
    service_years: float,
    remaining_contract_months: float = 0.0,
    agreed_compensation: Optional[float] = None
) -> Article77CompensationResult:
    """
    حساب التعويض عن الإنهاء غير المشروع وفق المادة 77 من نظام العمل:
    1. إذا نص العقد على تعويض محدد، يؤخذ به.
    2. إذا خلا العقد من تعويض محدد:
       - عقد غير محدد المدة (ينطبق على السعودي فقط): أجر 15 يوماً عن كل سنة خدمة.
       - عقد محدد المدة (ينطبق على غير السعودي دائماً أو السعودي بعقد محدد): أجر المدة الباقية من العقد.
    3. الحد الأدنى الإلزامي للتعويض: أجر شهرين على الأقل في جميع الحالات.
    """
    if monthly_wage <= 0:
        raise ValueError("الأجر الشهري يجب أن يكون أكبر من الصفر.")

    statutory_minimum = round(monthly_wage * 2.0, 2)

    # إذا كان غير سعودي وعقده غير محدد، هذا وضع غير نظامي لكن إن حسب، يعامل كمحدد المدة
    effective_contract_type = contract_type
    if not is_saudi and contract_type == ContractType.INDEFINITE:
        effective_contract_type = ContractType.FIXED

    if agreed_compensation is not None and agreed_compensation > 0:
        formula = "تعويض متفق عليه في العقد"
        calculated = round(agreed_compensation, 2)
    elif effective_contract_type == ContractType.INDEFINITE:
        # أجر 15 يوماً عن كل سنة خدمة = (monthly_wage / 2) * service_years
        formula = "أجر 15 يوماً عن كل سنة خدمة (عقد غير محدد المدة)"
        calculated = round((monthly_wage / 2.0) * service_years, 2)
    else:
        # أجر المدة المتبقية من العقد
        formula = "أجر المدة المتبقية من العقد (عقد محدد المدة)"
        calculated = round(monthly_wage * max(remaining_contract_months, 0.0), 2)

    # تطبيق الحد الأدنى الإلزامي (أجر شهرين)
    final_amount = max(calculated, statutory_minimum)

    explanation = (
        f"المادة 77: استحقاق التعويض بموجب ({formula}) هو {calculated:,.2f} ر.س. "
        f"ونظراً لأن الحد الأدنى النظامي الإلزامي هو أجر شهرين ({statutory_minimum:,.2f} ر.س)، "
        f"فإن التعويض النهائي المستحق هو {final_amount:,.2f} ر.س."
    )

    return Article77CompensationResult(
        is_saudi=is_saudi,
        contract_type=effective_contract_type,
        monthly_wage=monthly_wage,
        service_years=service_years,
        remaining_contract_months=remaining_contract_months,
        formula_used=formula,
        statutory_calculated_amount=calculated,
        statutory_minimum_amount=statutory_minimum,
        final_compensation_amount=final_amount,
        article_reference="المادة 77 من نظام العمل",
        explanation_ar=explanation
    )


def calculate_end_of_service_benefit(
    last_gross_wage: float,
    service_years: float,
    is_saudi: bool,
    is_resignation: bool = False,
    resignation_reason: ResignationReason = ResignationReason.STANDARD
) -> EOSBCalculationResult:
    """
    حساب مكافأة نهاية الخدمة (EOSB) وفق المواد 84 و 85 و 87 من نظام العمل:
    - المادة 84:
      * أجر نصف شهر (15 يوماً) عن كل سنة من السنوات الخمس الأولى.
      * أجر شهر كامل (30 يوماً) عن كل سنة تالية.
      * احتساب أجزاء السنة بنسبة ما قضي منها.
    - المادة 85 (في حال استقالة العامل):
      * أقل من سنتين: 0 (لا يستحق مكافأة).
      * من سنتين إلى أقل من 5 سنوات: يستحق ثلث المكافأة (1/3).
      * من 5 سنوات إلى أقل من 10 سنوات: يستحق ثلثي المكافأة (2/3).
      * 10 سنوات فأكثر: يستحق المكافأة كاملة (100%).
    - المادة 87 (استثناءات الاستقالة - استحقاق المكافأة كاملة 100%):
      * استقالة العاملة خلال 6 أشهر من تاريخ زواجها.
      * استقالة العاملة خلال 3 أشهر من تاريخ وضعها.
      * ترك العامل العمل لقوة قاهرة خارجة عن إرادته.
    """
    if last_gross_wage <= 0 or service_years < 0:
        raise ValueError("الأجر وسنوات الخدمة يجب أن تكون قيماً صحيحة موجبة.")

    # الشريحة الأولى: أول 5 سنوات (أجر نصف شهر عن كل سنة)
    years_tier1 = min(service_years, 5.0)
    tier1_amount = round(years_tier1 * (last_gross_wage / 2.0), 2)

    # الشريحة الثانية: ما زاد عن 5 سنوات (أجر شهر كامل عن كل سنة)
    years_tier2 = max(service_years - 5.0, 0.0)
    tier2_amount = round(years_tier2 * last_gross_wage, 2)

    gross_eosb = round(tier1_amount + tier2_amount, 2)

    # تحديد نسبة الاستحقاق
    if not is_resignation:
        # إنهاء من صاحب العمل أو انتهاء عقد أو اتفاق = استحقاق كامل (المادة 84)
        ratio = 1.0
        ref = "المادة 84 من نظام العمل"
        explanation = (
            f"إنهاء خدمة بموجب المادة 84: يستحق الموظف المكافأة كاملة (100%). "
            f"أول 5 سنوات: {tier1_amount:,.2f} ر.س، والسنوات اللاحقة: {tier2_amount:,.2f} ر.س. "
            f"الإجمالي: {gross_eosb:,.2f} ر.س."
        )
    else:
        # استقالة
        if resignation_reason in (
            ResignationReason.MARRIAGE_FEMALE,
            ResignationReason.CHILDBIRTH_FEMALE,
            ResignationReason.FORCE_MAJEURE
        ):
            # استثناء المادة 87: استحقاق كامل بغض النظر عن المدة
            ratio = 1.0
            ref = "المادة 87 من نظام العمل"
            reason_text = {
                ResignationReason.MARRIAGE_FEMALE: "زواج العاملة خلال 6 أشهر",
                ResignationReason.CHILDBIRTH_FEMALE: "وضع العاملة خلال 3 أشهر",
                ResignationReason.FORCE_MAJEURE: "قوة قاهرة خارجة عن الإرادة"
            }.get(resignation_reason, "")
            explanation = (
                f"استثناء المادة 87 ({reason_text}): تستحق المكافأة كاملة بنسبة 100% "
                f"بمبلغ {gross_eosb:,.2f} ر.س."
            )
        else:
            # تدرج المادة 85
            ref = "المادة 85 من نظام العمل"
            if service_years < 2.0:
                ratio = 0.0
                explanation = (
                    "المادة 85: استقالة بخدمة أقل من سنتين متصلتين، لا يستحق الموظف أي مكافأة (0.00 ر.س)."
                )
            elif service_years < 5.0:
                ratio = 1.0 / 3.0
                explanation = (
                    f"المادة 85: استقالة بخدمة بين سنتين و5 سنوات، يستحق ثلث المكافأة (1/3). "
                    f"المبلغ الإجمالي {gross_eosb:,.2f} ر.س × 1/3 = {round(gross_eosb * ratio, 2):,.2f} ر.س."
                )
            elif service_years < 10.0:
                ratio = 2.0 / 3.0
                explanation = (
                    f"المادة 85: استقالة بخدمة بين 5 و10 سنوات، يستحق ثلثي المكافأة (2/3). "
                    f"المبلغ الإجمالي {gross_eosb:,.2f} ر.س × 2/3 = {round(gross_eosb * ratio, 2):,.2f} ر.س."
                )
            else:
                ratio = 1.0
                explanation = (
                    f"المادة 85: استقالة بخدمة بلغت 10 سنوات أو أكثر، يستحق المكافأة كاملة (100%) "
                    f"بمبلغ {gross_eosb:,.2f} ر.س."
                )

    net_eosb = round(gross_eosb * ratio, 2)

    return EOSBCalculationResult(
        is_saudi=is_saudi,
        service_years=service_years,
        last_gross_wage=last_gross_wage,
        is_resignation=is_resignation,
        resignation_reason=resignation_reason,
        entitlement_ratio=round(ratio, 4),
        tier1_amount=tier1_amount,
        tier2_amount=tier2_amount,
        gross_eosb_amount=gross_eosb,
        net_eosb_amount=net_eosb,
        article_reference=ref,
        explanation_ar=explanation
    )


def validate_loan_installment_cap(
    monthly_wage: float,
    proposed_installment: float,
    current_active_installments: float = 0.0
) -> RuleValidationResult:
    """
    التحقق من سقف استقطاع أقساط قروض صاحب العمل وفق المادة 92 (فقرة 1):
    لا يجوز أن يزيد ما يحسم من العامل وفاءً لقروض صاحب العمل على 10% من أجره الشهري (معدلة).
    """
    if monthly_wage <= 0:
        return RuleValidationResult(
            is_valid=False,
            article="المادة 92",
            code="INVALID_WAGE",
            message_ar="الأجر الشهري يجب أن يكون أكبر من الصفر لحساب سقف القرض.",
            details={"monthly_wage": monthly_wage}
        )

    max_allowed = round(monthly_wage * LOAN_DEDUCTION_MAX_PERCENTAGE, 2)
    total_after_installment = round(current_active_installments + proposed_installment, 2)
    cap_pct = int(round(LOAN_DEDUCTION_MAX_PERCENTAGE * 100))

    if total_after_installment > max_allowed:
        pct = round((total_after_installment / monthly_wage) * 100, 1)
        return RuleValidationResult(
            is_valid=False,
            article="المادة 92 فقرة (1)",
            code="LOAN_DEDUCTION_EXCEEDS_STATUTORY_CAP",
            message_ar=(
                f"مخالفة للمادة 92: القسط المقترح ({proposed_installment:,.2f} ر.س) مع الأقساط القائمة "
                f"يمثل {pct}% من الأجر، متجاوزاً السقف النظامي الإلزامي البالغ {cap_pct}% ({max_allowed:,.2f} ر.س)."
            ),
            details={
                "monthly_wage": monthly_wage,
                "proposed_installment": proposed_installment,
                "current_active_installments": current_active_installments,
                "max_allowed_deduction": max_allowed,
                "requested_percentage": pct,
                "cap_percentage": cap_pct,
            }
        )

    return RuleValidationResult(
        is_valid=True,
        article="المادة 92 فقرة (1)",
        code="LOAN_INSTALLMENT_WITHIN_STATUTORY_CAP",
        message_ar=(
            f"القسط المقترح ضمن السقف النظامي المسموح به (الحد الأقصى {cap_pct}% = {max_allowed:,.2f} ر.س)."
        ),
        details={
            "monthly_wage": monthly_wage,
            "max_allowed_deduction": max_allowed,
            "total_deduction": total_after_installment,
            "cap_percentage": cap_pct,
        }
    )


def validate_disciplinary_deduction(
    daily_wage: float,
    infraction_deduction_days: float,
    month_cumulative_deduction_days: float = 0.0,
    suspension_days: float = 0.0
) -> RuleValidationResult:
    """
    التحقق من قيود الجزاءات التأديبية وفق المادة 70 من نظام العمل:
    1. حظر اقتطاع أكثر من أجر 5 أيام عن المخالفة الواحدة.
    2. حظر اقتطاع أكثر من أجر 5 أيام في الشهر الواحد وفاءً للجزاءات.
    3. حظر زيادة مدة الإيقاف عن العمل بدون أجر على 5 أيام في الشهر.
    """
    if infraction_deduction_days > DISCIPLINARY_MAX_DAYS_PER_INFRACTION:
        return RuleValidationResult(
            is_valid=False,
            article="المادة 70",
            code="DISCIPLINARY_SINGLE_INFRACTION_EXCEEDS_5_DAYS",
            message_ar=(
                f"مخالفة للمادة 70: لا يجوز اقتطاع أكثر من أجر 5 أيام عن المخالفة الواحدة "
                f"(المطلوب: {infraction_deduction_days} أيام)."
            ),
            details={"requested_days": infraction_deduction_days, "limit": 5.0}
        )

    total_month = month_cumulative_deduction_days + infraction_deduction_days
    if total_month > DISCIPLINARY_MAX_DAYS_PER_MONTH:
        return RuleValidationResult(
            is_valid=False,
            article="المادة 70",
            code="DISCIPLINARY_MONTHLY_TOTAL_EXCEEDS_5_DAYS",
            message_ar=(
                f"مخالفة للمادة 70: إجمالي الخصومات التأديبية في الشهر الواحد سيتجاوز 5 أيام "
                f"(الإجمالي مع المخالفة الحالية: {total_month} أيام، والسقف: 5 أيام)."
            ),
            details={"total_month_days": total_month, "limit": 5.0}
        )

    if suspension_days > DISCIPLINARY_MAX_SUSPENSION_DAYS_PER_MONTH:
        return RuleValidationResult(
            is_valid=False,
            article="المادة 70",
            code="DISCIPLINARY_SUSPENSION_EXCEEDS_5_DAYS",
            message_ar=(
                f"مخالفة للمادة 70: لا يجوز أن تزيد مدة الإيقاف عن العمل بدون أجر على 5 أيام في الشهر "
                f"(المطلوب: {suspension_days} أيام)."
            ),
            details={"suspension_days": suspension_days, "limit": 5.0}
        )

    return RuleValidationResult(
        is_valid=True,
        article="المادة 70",
        code="DISCIPLINARY_SANCTION_VALID",
        message_ar="الجزاء التأديبي متوافق مع قيود وسقوف المادة 70 من نظام العمل.",
        details={
            "infraction_days": infraction_deduction_days,
            "month_total_days": total_month,
            "daily_wage": daily_wage,
            "deduction_amount": round(infraction_deduction_days * daily_wage, 2)
        }
    )


def determine_disciplinary_occurrence(
    prior_infraction_dates: List[date | str],
    current_infraction_date: date | str,
) -> Tuple[str, str]:
    """
    تحديد درجة تكرار المخالفة (Occurrence: first, second, third, fourth)
    وفق المادة 71 من نظام العمل:
    سقوط أثر تكرار المخالفة إذا انقضى على المخالفة السابقة 180 يوماً من إبلاغ العامل.
    ترجع (occurrence_key, explanation_ar).
    """
    def parse_dt(d: date | str) -> date:
        if isinstance(d, date):
            return d
        return datetime.strptime(str(d).split()[0], "%Y-%m-%d").date()

    curr_dt = parse_dt(current_infraction_date)
    if not prior_infraction_dates:
        return ("first", "المخالفة الأولى: لا توجد سوابق مسجلة على العامل.")

    sorted_priors = sorted([parse_dt(p) for p in prior_infraction_dates if parse_dt(p) <= curr_dt], reverse=True)
    if not sorted_priors:
        return ("first", "المخالفة الأولى: لا توجد سوابق قبل هذا التاريخ.")

    last_prior = sorted_priors[0]
    days_diff = (curr_dt - last_prior).days

    if days_diff > DISCIPLINARY_REPETITION_EXPIRY_DAYS:
        return (
            "first",
            f"المخالفة الأولى (إعادة تعيين بموجب المادة 71): انقضى {days_diff} يوماً (أكثر من 180 يوماً) على آخر مخالفة مسجلة في {last_prior}."
        )

    active_count = 1
    prev_dt = curr_dt
    for p in sorted_priors:
        if (prev_dt - p).days <= DISCIPLINARY_REPETITION_EXPIRY_DAYS:
            active_count += 1
            prev_dt = p
        else:
            break

    occ_map = {1: "first", 2: "second", 3: "third", 4: "fourth"}
    level = occ_map.get(min(active_count, 4), "fourth")
    level_names = {"first": "الأولى", "second": "الثانية", "third": "الثالثة", "fourth": "الرابعة (أو أكثر)"}
    return (
        level,
        f"المخالفة {level_names[level]} (سارية خلال فترة التكرار بموجب المادة 71): آخر مخالفة كانت منذ {days_diff} يوماً."
    )


def validate_disciplinary_statute_of_limitations(
    violation_date: date | str,
    discovery_date: date | str,
    action_date: date | str,
    investigation_end_date: Optional[date | str] = None,
) -> RuleValidationResult:
    """
    التحقق من مواعيد التقادم وسقوط الدعوى التأديبية وفق المادة 72:
    1. لا يجوز اتهام العامل بمخالفة مضى على كشفها أكثر من 30 يوماً.
    2. لا يجوز توقيع الجزاء بعد تاريخ انتهاء التحقيق وثبوت المخالفة بأكثر من 30 يوماً.
    """
    def parse_dt(d: date | str) -> date:
        if isinstance(d, date):
            return d
        return datetime.strptime(str(d).split()[0], "%Y-%m-%d").date()

    v_dt = parse_dt(violation_date)
    disc_dt = parse_dt(discovery_date)
    act_dt = parse_dt(action_date)

    days_since_discovery = (act_dt - disc_dt).days
    if days_since_discovery > DISCIPLINARY_DISCOVERY_LIMIT_DAYS and not investigation_end_date:
        return RuleValidationResult(
            is_valid=False,
            article="المادة 72",
            code="DISCIPLINARY_DISCOVERY_PERIOD_EXCEEDED",
            message_ar=(
                f"سقوط الحق التأديبي بموجب المادة 72: مضى {days_since_discovery} يوماً على كشف المخالفة "
                f"دون توقيع الجزاء أو فتح تحقيق رسمي (الحد النظامي: 30 يوماً)."
            ),
            details={"days_since_discovery": days_since_discovery, "limit": 30}
        )

    if investigation_end_date:
        inv_dt = parse_dt(investigation_end_date)
        days_since_inv = (act_dt - inv_dt).days
        if days_since_inv > DISCIPLINARY_DECISION_LIMIT_DAYS:
            return RuleValidationResult(
                is_valid=False,
                article="المادة 72",
                code="DISCIPLINARY_INVESTIGATION_DECISION_PERIOD_EXCEEDED",
                message_ar=(
                    f"سقوط الحق التأديبي بموجب المادة 72: مضى {days_since_inv} يوماً على تاريخ انتهاء التحقيق "
                    f"وثبوت المخالفة (الحد النظامي لتوقيع الجزاء: 30 يوماً من انتهاء التحقيق)."
                ),
                details={"days_since_investigation": days_since_inv, "limit": 30}
            )

    return RuleValidationResult(
        is_valid=True,
        article="المادة 72",
        code="DISCIPLINARY_LIMITATION_VALID",
        message_ar="إجراءات التحقيق وتوقيع الجزاء مطابقة لمواعيد السقوط والتقادم في المادة 72.",
        details={
            "days_since_discovery": days_since_discovery,
            "days_since_investigation": (act_dt - parse_dt(investigation_end_date)).days if investigation_end_date else None
        }
    )


def validate_article_80_termination(
    ground_code: str,
    worker_given_hearing: bool,
    has_prior_written_warning: bool = False,
    absence_unjustified_days: int = 0,
    is_absence_consecutive: bool = False,
    reported_to_authorities_within_24h: bool = False,
) -> RuleValidationResult:
    """
    التحقق من ضوابط وإجراءات إنهاء الخدمة دون مكافأة أو إشعار أو تعويض بموجب المادة 80:
    يشترط نظاماً إتاحة الفرصة للعامل لإبداء أسباب معارضته للفسخ وسماع دفاعه،
    بالإضافة إلى الشروط الخاصة بكل فقرة من فقرات المادة 80.
    """
    if not worker_given_hearing:
        return RuleValidationResult(
            is_valid=False,
            article="المادة 80",
            code="ARTICLE_80_NO_HEARING_PROVIDED",
            message_ar=(
                "بطلان الفسخ بموجب المادة 80: يشترط النظام وجوب إتاحة الفرصة للعامل لإبداء "
                "أسباب معارضته للفسخ والتحقيق معه وسماع دفاعه كتابياً."
            ),
            details={"worker_given_hearing": False}
        )

    if ground_code == "ESSENTIAL_OBLIGATIONS_BREACH":
        if not has_prior_written_warning:
            return RuleValidationResult(
                is_valid=False,
                article="المادة 80 (الفقرة 2)",
                code="ARTICLE_80_MISSING_WRITTEN_WARNING",
                message_ar=(
                    "لا يجوز الفسخ بموجب الفقرة 2 من المادة 80 (عدم أداء الالتزامات الجوهرية) "
                    "دون توجيه إنذار كتابي مسبق للعامل."
                ),
                details={"has_prior_written_warning": False}
            )

    elif ground_code == "MATERIAL_LOSS_INTENTIONAL":
        if not reported_to_authorities_within_24h:
            return RuleValidationResult(
                is_valid=False,
                article="المادة 80 (الفقرة 4)",
                code="ARTICLE_80_REPORT_24H_REQUIRED",
                message_ar=(
                    "لا يجوز الفسخ بموجب الفقرة 4 من المادة 80 (إلحاق خسارة مادية جسيمة) "
                    "إلا إذا أبلغ صاحب العمل الجهات المختصة بالحادث خلال 24 ساعة من وقت علمه به."
                ),
                details={"reported_to_authorities_within_24h": False}
            )

    elif ground_code == "UNJUSTIFIED_ABSENCE":
        if is_absence_consecutive:
            if absence_unjustified_days < 15:
                return RuleValidationResult(
                    is_valid=False,
                    article="المادة 80 (الفقرة 7)",
                    code="ARTICLE_80_CONSECUTIVE_ABSENCE_DAYS_INSUFFICIENT",
                    message_ar=(
                        f"يشترط للفسخ بسبب الغياب المتصل ألا تقل مدته عن 15 يوماً متصلة (المسجل: {absence_unjustified_days} يوماً)."
                    ),
                    details={"absence_days": absence_unjustified_days, "required": 15}
                )
            if not has_prior_written_warning:
                return RuleValidationResult(
                    is_valid=False,
                    article="المادة 80 (الفقرة 7)",
                    code="ARTICLE_80_ABSENCE_WARNING_REQUIRED",
                    message_ar="يشترط في الغياب المتصل توجيه إنذار كتابي للعامل بعد غيابه 10 أيام.",
                    details={"has_prior_written_warning": False}
                )
        else:
            if absence_unjustified_days < 30:
                return RuleValidationResult(
                    is_valid=False,
                    article="المادة 80 (الفقرة 7)",
                    code="ARTICLE_80_INTERMITTENT_ABSENCE_DAYS_INSUFFICIENT",
                    message_ar=(
                        f"يشترط للفسخ بسبب الغياب المتقطع ألا يقل عن 30 يوماً خلال السنة الواحدة (المسجل: {absence_unjustified_days} يوماً)."
                    ),
                    details={"absence_days": absence_unjustified_days, "required": 30}
                )
            if not has_prior_written_warning:
                return RuleValidationResult(
                    is_valid=False,
                    article="المادة 80 (الفقرة 7)",
                    code="ARTICLE_80_ABSENCE_WARNING_REQUIRED",
                    message_ar="يشترط في الغياب المتقطع توجيه إنذار كتابي للعامل بعد غيابه 20 يوماً.",
                    details={"has_prior_written_warning": False}
                )

    return RuleValidationResult(
        is_valid=True,
        article="المادة 80",
        code="ARTICLE_80_TERMINATION_VALID",
        message_ar="شروط وضمانات الفسخ التأديبي بموجب المادة 80 مستوفاة نظامياً.",
        details={"ground_code": ground_code, "worker_given_hearing": True}
    )


def validate_probation_period(
    probation_days: int,
    has_written_agreement: bool = False,
    is_extension: bool = False,
    is_rehire_same_employer: bool = False,
    is_different_profession: bool = False,
    days_since_prior_termination: int = 0
) -> RuleValidationResult:
    """
    التحقق من ضوابط فترة التجربة وفق المادة 53 وتعديلات 1446هـ:
    1. المدة القياسية بحد أقصى 90 يوماً.
    2. التمديد حتى 180 يوماً كحد أقصى يشترط اتفاقاً مكتوباً صريحاً.
    3. لا يجوز وضع العامل تحت التجربة لدى صاحب العمل نفسه أكثر من مرة إلا في مهنة أخرى
       أو بمضي 180 يوماً على الأقل من انتهاء العلاقة السابقة وبموافقة الطرفين.
    """
    if probation_days <= 0:
        return RuleValidationResult(
            is_valid=False,
            article="المادة 53",
            code="INVALID_PROBATION_DAYS",
            message_ar="أيام فترة التجربة يجب أن تكون رقماً موجباً.",
            details={"probation_days": probation_days}
        )

    # التحقق من حالة إعادة التعيين لدى صاحب العمل نفسه
    if is_rehire_same_employer:
        valid_rehire = is_different_profession or (days_since_prior_termination >= 180 and has_written_agreement)
        if not valid_rehire:
            return RuleValidationResult(
                is_valid=False,
                article="المادة 53 (تعديل 1446هـ)",
                code="PROBATION_REHIRE_PROHIBITED",
                message_ar=(
                    "مخالفة للمادة 53: لا يجوز وضع العامل تحت التجربة أكثر من مرة لدى صاحب العمل نفسه "
                    "إلا في مهنة أخرى، أو بعد مضي 180 يوماً على الأقل من انتهاء العلاقة السابقة وباتفاق كتابي."
                ),
                details={
                    "is_different_profession": is_different_profession,
                    "days_since_prior_termination": days_since_prior_termination
                }
            )

    # التحقق من السقف
    if probation_days > PROBATION_EXTENDED_DAYS_MAX:
        return RuleValidationResult(
            is_valid=False,
            article="المادة 53",
            code="PROBATION_EXCEEDS_180_DAYS_CAP",
            message_ar=(
                f"مخالفة للمادة 53: لا يجوز أن تزيد فترة التجربة في جميع الأحوال على 180 يوماً "
                f"(المطلوب: {probation_days} يوماً)."
            ),
            details={"probation_days": probation_days, "cap": 180}
        )

    if probation_days > PROBATION_STANDARD_DAYS_MAX and not has_written_agreement:
        return RuleValidationResult(
            is_valid=False,
            article="المادة 53 (تعديل 1446هـ)",
            code="PROBATION_EXTENSION_REQUIRES_WRITTEN_AGREEMENT",
            message_ar=(
                f"مخالفة للمادة 53: تجاوز فترة التجربة لـ 90 يوماً (المطلوب: {probation_days} يوماً) "
                "يشترط نظاماً وجود اتفاق مكتوب وصريح بين العامل وصاحب العمل."
            ),
            details={"probation_days": probation_days, "has_written_agreement": False}
        )

    return RuleValidationResult(
        is_valid=True,
        article="المادة 53",
        code="PROBATION_PERIOD_VALID",
        message_ar=f"فترة التجربة ({probation_days} يوماً) نظامية وصحيحة.",
        details={"probation_days": probation_days}
    )


def calculate_annual_leave_entitlement(
    continuous_service_years: float
) -> int:
    """
    استحقاق الإجازة السنوية وفق المادة 109 من نظام العمل:
    - 21 يوماً مدفوعة الأجر لمن أمضى خدمة أقل من 5 سنوات.
    - 30 يوماً مدفوعة الأجر لمن أمضى 5 سنوات خدمة متصلة فأكثر.
    """
    if continuous_service_years >= ANNUAL_LEAVE_SENIORITY_THRESHOLD_YEARS:
        return ANNUAL_LEAVE_SENIOR_DAYS
    return ANNUAL_LEAVE_INITIAL_DAYS


def get_occasion_leave_statutory_days(
    leave_type: OccasionLeaveType
) -> int:
    """
    أيام إجازات المناسبات مدفوعة الأجر وفق المادة 113 وتعديلات المرسوم الملكي (م/44 لعام 1446هـ):
    - زواج العامل: 5 أيام.
    - وفاة الزوج أو أحد الأصول أو الفروع: 5 أيام.
    - وفاة الأخ أو الأخت (تعديل 1446هـ): 3 أيام.
    - ولادة مولود للعامل (أبوة - تعديل 1446هـ): 3 أيام.
    """
    mapping = {
        OccasionLeaveType.MARRIAGE: OCCASION_LEAVE_MARRIAGE_DAYS,
        OccasionLeaveType.DEATH_SPOUSE_PARENT_CHILD: OCCASION_LEAVE_BEREAVEMENT_DIRECT_DAYS,
        OccasionLeaveType.DEATH_SIBLING: OCCASION_LEAVE_BEREAVEMENT_SIBLING_DAYS,
        OccasionLeaveType.PATERNITY: OCCASION_LEAVE_PATERNITY_DAYS,
    }
    return mapping[leave_type]


def validate_maternity_leave_duration(
    leave_duration_weeks: float
) -> RuleValidationResult:
    """
    التحقق من إجازة الوضع وفق المادة 116 وتعديلات المرسوم الملكي (م/44 لعام 1446هـ):
    - حق المرأة العاملة في إجازة وضع مدتها 12 أسبوعاً بأجر كامل (منها 6 أسابيع إلزامية بعد الوضع).
    """
    if leave_duration_weeks > MATERNITY_LEAVE_WEEKS:
        return RuleValidationResult(
            is_valid=True,
            article="المادة 116 (تعديل 1446هـ)",
            code="MATERNITY_LEAVE_EXTENDED_UNPAID",
            message_ar=(
                f"إجازة الوضع النظامية بأجر كامل هي 12 أسبوعاً (تعديل 1446هـ). "
                f"المدة الزائدة ({leave_duration_weeks - 12:.1f} أسبوعاً) تعد تمديداً بدون أجر بموجب المادة 116."
            ),
            details={"paid_weeks": 12, "unpaid_weeks": leave_duration_weeks - 12}
        )

    return RuleValidationResult(
        is_valid=True,
        article="المادة 116 (تعديل 1446هـ)",
        code="MATERNITY_LEAVE_PAID_VALID",
        message_ar=f"إجازة الوضع مدتها ({leave_duration_weeks} أسبوعاً) مدفوعة الأجر بالكامل بموجب تعديلات 1446هـ.",
        details={"paid_weeks": leave_duration_weeks}
    )


def calculate_overtime_pay(
    basic_wage: float,
    gross_wage: float,
    overtime_hours: float,
    monthly_standard_hours: float = 240.0
) -> OvertimeCalculationResult:
    """
    حساب أجر ساعات العمل الإضافية وفق المادة 107 من نظام العمل:
    أجر ساعة العمل الإضافية = أجر الساعة الفعلي (Gross/Hours) + 50% من الأجر الأساسي (Basic/Hours).
    """
    if overtime_hours <= 0:
        return OvertimeCalculationResult(
            basic_hourly_rate=round(basic_wage / monthly_standard_hours, 2),
            gross_hourly_rate=round(gross_wage / monthly_standard_hours, 2),
            overtime_hours=0.0,
            standard_hourly_amount=0.0,
            premium_amount=0.0,
            total_overtime_pay=0.0,
            article_reference="المادة 107 من نظام العمل",
            explanation_ar="لا توجد ساعات عمل إضافية مستحقة."
        )

    basic_rate = basic_wage / monthly_standard_hours
    gross_rate = gross_wage / monthly_standard_hours

    # حسب المادة 107: أجر الساعة الفعلي + 50% من الأجر الأساسي
    standard_portion = round(gross_rate * overtime_hours, 2)
    premium_portion = round((basic_rate * OVERTIME_PREMIUM_RATE) * overtime_hours, 2)
    total_pay = round(standard_portion + premium_portion, 2)

    return OvertimeCalculationResult(
        basic_hourly_rate=round(basic_rate, 2),
        gross_hourly_rate=round(gross_rate, 2),
        overtime_hours=overtime_hours,
        standard_hourly_amount=standard_portion,
        premium_amount=premium_portion,
        total_overtime_pay=total_pay,
        article_reference="المادة 107 من نظام العمل",
        explanation_ar=(
            f"المادة 107: أجر {overtime_hours} ساعات إضافية يتكون من أجر الساعة الفعلي "
            f"({standard_portion:,.2f} ر.س) + علاوة 50% من الأساسي ({premium_portion:,.2f} ر.س) "
            f"= الإجمالي {total_pay:,.2f} ر.س."
        )
    )
