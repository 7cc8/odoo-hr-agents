"""
اختبارات محرك قواعد نظام العمل السعودي وتعديلات 1446هـ
(Tests for Saudi Labor Law Rules Engine)
"""

import pytest
from saudi_labor_law_rules import (
    calculate_gosi_contributions,
    validate_contract_type_for_nationality,
    calculate_article_77_compensation,
    calculate_end_of_service_benefit,
    validate_loan_installment_cap,
    validate_disciplinary_deduction,
    validate_probation_period,
    calculate_annual_leave_entitlement,
    get_occasion_leave_statutory_days,
    validate_maternity_leave_duration,
    calculate_overtime_pay,
    ContractType,
    ResignationReason,
    OccasionLeaveType,
    GOSI_MIN_CONTRIBUTORY_WAGE,
    GOSI_MAX_CONTRIBUTORY_WAGE
)


# =============================================================================
# 1. اختبارات التأمينات الاجتماعية (GOSI): السعودي والغير سعودي
# =============================================================================

def test_gosi_saudi_standard_wage():
    """اختبار حساب GOSI لموظف سعودي براتب قياسي (أساسي 10,000 + سكن 2,500 = 12,500)"""
    res = calculate_gosi_contributions(basic_wage=10000.0, housing_allowance=2500.0, is_saudi=True)
    
    assert res.is_saudi is True
    assert res.uncapped_contributory_wage == 12500.0
    assert res.capped_contributory_wage == 12500.0
    
    # حصة صاحب العمل: 9% معاشات + 2% أخطار + 0.75% ساند = 11.75%
    assert res.employer_pension == 1125.0  # 12500 * 0.09
    assert res.employer_hazards == 250.0   # 12500 * 0.02
    assert res.employer_saned == 93.75     # 12500 * 0.0075
    assert res.total_employer == 1468.75   # 11.75%
    
    # حصة الموظف: 9% معاشات + 0.75% ساند = 9.75%
    assert res.employee_pension == 1125.0
    assert res.employee_hazards == 0.0
    assert res.employee_saned == 93.75
    assert res.total_employee == 1218.75   # 9.75%
    
    assert res.total_combined == 2687.50   # 21.5%
    assert res.net_wage_after_gosi == 12500.0 - 1218.75


def test_gosi_non_saudi_standard_wage():
    """اختبار حساب GOSI لموظف غير سعودي: 2% أخطار مهنية لصاحب العمل، و0% استقطاع على الموظف"""
    res = calculate_gosi_contributions(basic_wage=10000.0, housing_allowance=2500.0, is_saudi=False)
    
    assert res.is_saudi is False
    assert res.uncapped_contributory_wage == 12500.0
    assert res.capped_contributory_wage == 12500.0
    
    # صاحب العمل: 2% أخطار فقط
    assert res.employer_pension == 0.0
    assert res.employer_hazards == 250.0   # 12500 * 0.02
    assert res.employer_saned == 0.0
    assert res.total_employer == 250.0
    
    # الموظف: 0%
    assert res.employee_pension == 0.0
    assert res.employee_hazards == 0.0
    assert res.employee_saned == 0.0
    assert res.total_employee == 0.0
    
    assert res.total_combined == 250.0
    assert res.net_wage_after_gosi == 12500.0  # لا استقطاع على أجر غير السعودي للتأمينات


def test_gosi_saudi_cap_45k():
    """اختبار تطبيق السقف الأعلى للاشتراك (45,000 ريال) لموظف سعودي براتب مرتفع"""
    res = calculate_gosi_contributions(basic_wage=50000.0, housing_allowance=10000.0, is_saudi=True)
    
    assert res.uncapped_contributory_wage == 60000.0
    assert res.capped_contributory_wage == 45000.0
    
    # الحسبة مبنية على 45,000 كحد أقصى
    assert res.employer_pension == round(45000 * 0.09, 2)
    assert res.total_employer == round(45000 * 0.1175, 2)
    assert res.total_employee == round(45000 * 0.0975, 2)
    assert res.total_combined == round(45000 * 0.215, 2)


def test_gosi_floor_1500():
    """اختبار تطبيق الحد الأدنى للاشتراك (1,500 ريال)"""
    res = calculate_gosi_contributions(basic_wage=1000.0, housing_allowance=200.0, is_saudi=True)
    assert res.uncapped_contributory_wage == 1200.0
    assert res.capped_contributory_wage == 1500.0


# =============================================================================
# 2. اختبارات نوع العقد وجنسية الموظف (المادة 37)
# =============================================================================

def test_article_37_non_saudi_indefinite_contract_fails():
    """المادة 37: حظر إبرام أو تسجيل عقد غير محدد المدة لغير السعودي"""
    res = validate_contract_type_for_nationality(is_saudi=False, contract_type=ContractType.INDEFINITE)
    assert res.is_valid is False
    assert res.code == "NON_SAUDI_INDEFINITE_CONTRACT_PROHIBITED"
    assert "المادة 37" in res.article


def test_article_37_non_saudi_fixed_contract_succeeds():
    """المادة 37: عقد محدد المدة لغير السعودي سليم ونظامي"""
    res = validate_contract_type_for_nationality(is_saudi=False, contract_type=ContractType.FIXED)
    assert res.is_valid is True
    assert res.code == "CONTRACT_TYPE_VALID"


def test_article_37_saudi_both_contracts_succeed():
    """الموظف السعودي يجوز أن يكون عقده محدد المدة أو غير محدد المدة"""
    res_fixed = validate_contract_type_for_nationality(is_saudi=True, contract_type=ContractType.FIXED)
    assert res_fixed.is_valid is True
    
    res_indefinite = validate_contract_type_for_nationality(is_saudi=True, contract_type=ContractType.INDEFINITE)
    assert res_indefinite.is_valid is True


# =============================================================================
# 3. اختبارات التعويض عن الإنهاء غير المشروع (المادة 77)
# =============================================================================

def test_article_77_indefinite_saudi_service_years():
    """المادة 77: عقد غير محدد المدة (للسعودي) - أجر 15 يوماً عن كل سنة مع حد أدنى شهرين"""
    # 4 سنوات خدمة براتب 10,000 = 4 * 5,000 = 20,000 (تساوي شهرين)
    res = calculate_article_77_compensation(
        monthly_wage=10000.0,
        is_saudi=True,
        contract_type=ContractType.INDEFINITE,
        service_years=4.0
    )
    assert res.statutory_calculated_amount == 20000.0
    assert res.statutory_minimum_amount == 20000.0
    assert res.final_compensation_amount == 20000.0

    # سنة خدمة واحدة = 5,000 -> يطبق الحد الأدنى الإلزامي (شهرين = 20,000)
    res_short = calculate_article_77_compensation(
        monthly_wage=10000.0,
        is_saudi=True,
        contract_type=ContractType.INDEFINITE,
        service_years=1.0
    )
    assert res_short.statutory_calculated_amount == 5000.0
    assert res_short.statutory_minimum_amount == 20000.0
    assert res_short.final_compensation_amount == 20000.0


def test_article_77_fixed_contract_remaining_months():
    """المادة 77: عقد محدد المدة (سعودي أو غير سعودي) - أجر المدة المتبقية مع حد أدنى شهرين"""
    # متبقي 6 أشهر براتب 8,000 = 48,000
    res = calculate_article_77_compensation(
        monthly_wage=8000.0,
        is_saudi=False,
        contract_type=ContractType.FIXED,
        service_years=2.0,
        remaining_contract_months=6.0
    )
    assert res.statutory_calculated_amount == 48000.0
    assert res.final_compensation_amount == 48000.0

    # متبقي شهر واحد براتب 8,000 = 8,000 -> يطبق الحد الأدنى النظامي (شهرين = 16,000)
    res_one_month = calculate_article_77_compensation(
        monthly_wage=8000.0,
        is_saudi=False,
        contract_type=ContractType.FIXED,
        service_years=2.0,
        remaining_contract_months=1.0
    )
    assert res_one_month.statutory_calculated_amount == 8000.0
    assert res_one_month.statutory_minimum_amount == 16000.0
    assert res_one_month.final_compensation_amount == 16000.0


# =============================================================================
# 4. اختبارات مكافأة نهاية الخدمة (المواد 84 و 85 و 87)
# =============================================================================

def test_eosb_article_84_full_entitlement():
    """المادة 84: إنهاء الخدمة من صاحب العمل (نصف شهر لأول 5 سنوات وشهر لما زاد)"""
    # 7 سنوات خدمة براتب 10,000
    # أول 5 سنوات = 5 * 5,000 = 25,000
    # السنتان التاليتان = 2 * 10,000 = 20,000
    # الإجمالي = 45,000
    res = calculate_end_of_service_benefit(
        last_gross_wage=10000.0,
        service_years=7.0,
        is_saudi=True,
        is_resignation=False
    )
    assert res.tier1_amount == 25000.0
    assert res.tier2_amount == 20000.0
    assert res.gross_eosb_amount == 45000.0
    assert res.net_eosb_amount == 45000.0
    assert res.entitlement_ratio == 1.0


def test_eosb_article_85_resignation_tiers():
    """المادة 85: استقالة العامل وتدرج الاستحقاق (0، الثلث، الثلثين، كامل)"""
    gross_wage = 12000.0

    # 1. أقل من سنتين (1.5 سنة): 0%
    res1 = calculate_end_of_service_benefit(gross_wage, 1.5, is_saudi=False, is_resignation=True)
    assert res1.entitlement_ratio == 0.0
    assert res1.net_eosb_amount == 0.0

    # 2. بين سنتين و5 سنوات (3 سنوات): الثلث (1/3)
    # المبلغ الإجمالي: 3 * 6,000 = 18,000 -> الثلث = 6,000
    res2 = calculate_end_of_service_benefit(gross_wage, 3.0, is_saudi=True, is_resignation=True)
    assert pytest.approx(res2.entitlement_ratio, 0.01) == 0.3333
    assert res2.net_eosb_amount == 6000.0

    # 3. بين 5 و10 سنوات (6 سنوات): الثلثين (2/3)
    # أول 5 سنوات = 5 * 6,000 = 30,000
    # سنة سادسة = 1 * 12,000 = 12,000
    # الإجمالي = 42,000 -> الثلثين = 28,000
    res3 = calculate_end_of_service_benefit(gross_wage, 6.0, is_saudi=False, is_resignation=True)
    assert pytest.approx(res3.entitlement_ratio, 0.01) == 0.6667
    assert res3.net_eosb_amount == 28000.0

    # 4. 10 سنوات فأكثر (10 سنوات): 100% كاملة
    # أول 5 سنوات = 30,000 + 5 سنوات تالية = 60,000 = 90,000
    res4 = calculate_end_of_service_benefit(gross_wage, 10.0, is_saudi=True, is_resignation=True)
    assert res4.entitlement_ratio == 1.0
    assert res4.net_eosb_amount == 90000.0


def test_eosb_article_87_female_resignation_exceptions():
    """المادة 87: استثناءات استقالة العاملة خلال 6 أشهر من الزواج أو 3 أشهر من الوضع (كاملة 100%)"""
    gross_wage = 10000.0
    service_years = 1.0  # سنة واحدة فقط (في العادي لا تستحق شيئاً في الاستقالة)

    # زواج العاملة
    res_marriage = calculate_end_of_service_benefit(
        last_gross_wage=gross_wage,
        service_years=service_years,
        is_saudi=True,
        is_resignation=True,
        resignation_reason=ResignationReason.MARRIAGE_FEMALE
    )
    assert res_marriage.entitlement_ratio == 1.0
    assert res_marriage.net_eosb_amount == 5000.0  # نصف شهر كاملة بموجب المادة 87

    # وضع العاملة
    res_childbirth = calculate_end_of_service_benefit(
        last_gross_wage=gross_wage,
        service_years=service_years,
        is_saudi=False,
        is_resignation=True,
        resignation_reason=ResignationReason.CHILDBIRTH_FEMALE
    )
    assert res_childbirth.entitlement_ratio == 1.0
    assert res_childbirth.net_eosb_amount == 5000.0


# =============================================================================
# 5. اختبارات سقف القروض والجزاءات (المادتان 92 و 70)
# =============================================================================

def test_article_92_loan_cap_10_percent():
    """المادة 92: حظر تجاوز استقطاع قروض صاحب العمل لسقف 10% من الأجر (محدث)"""
    monthly_wage = 10000.0  # السقف 10% = 1,000 ريال
    
    # قسط 800 ريال -> مقبول
    res_valid = validate_loan_installment_cap(monthly_wage, 800.0)
    assert res_valid.is_valid is True
    assert res_valid.code == "LOAN_INSTALLMENT_WITHIN_STATUTORY_CAP"

    # قسط 1,200 ريال -> مرفوض لتجاوز السقف
    res_invalid = validate_loan_installment_cap(monthly_wage, 1200.0)
    assert res_invalid.is_valid is False
    assert res_invalid.code == "LOAN_DEDUCTION_EXCEEDS_STATUTORY_CAP"

    # قسط 600 مع وجود أقساط سابقة 500 = 1,100 -> مرفوض
    res_combined = validate_loan_installment_cap(monthly_wage, 600.0, current_active_installments=500.0)
    assert res_combined.is_valid is False


def test_article_70_disciplinary_deduction_caps():
    """المادة 70: سقوف الجزاءات التأديبية (5 أيام كحد أقصى للمخالفة وفي الشهر)"""
    daily_wage = 200.0

    # مخالفة بخصم 6 أيام -> مرفوضة
    res_exceed_single = validate_disciplinary_deduction(daily_wage, infraction_deduction_days=6.0)
    assert res_exceed_single.is_valid is False
    assert res_exceed_single.code == "DISCIPLINARY_SINGLE_INFRACTION_EXCEEDS_5_DAYS"

    # مخالفة بخصم 3 أيام، مع وجود خصم سابق 3 أيام في نفس الشهر = 6 أيام -> مرفوضة
    res_exceed_month = validate_disciplinary_deduction(
        daily_wage,
        infraction_deduction_days=3.0,
        month_cumulative_deduction_days=3.0
    )
    assert res_exceed_month.is_valid is False
    assert res_exceed_month.code == "DISCIPLINARY_MONTHLY_TOTAL_EXCEEDS_5_DAYS"

    # مخالفة بخصم 2 أيام، مع وجود خصم سابق 2 أيام في الشهر = 4 أيام -> مقبولة
    res_ok = validate_disciplinary_deduction(
        daily_wage,
        infraction_deduction_days=2.0,
        month_cumulative_deduction_days=2.0
    )
    assert res_ok.is_valid is True
    assert res_ok.code == "DISCIPLINARY_SANCTION_VALID"


# =============================================================================
# 6. اختبارات فترة التجربة والإجازات وتعديلات 1446هـ
# =============================================================================

def test_article_53_probation_period_rules():
    """المادة 53 وتعديل 1446هـ: ضوابط الـ 90 يوماً والـ 180 يوماً"""
    # 90 يوماً بدون اتفاق تمديد -> مقبولة
    res_90 = validate_probation_period(probation_days=90)
    assert res_90.is_valid is True

    # 120 يوماً بدون اتفاق مكتوب -> مرفوضة
    res_120_no_agreement = validate_probation_period(probation_days=120, has_written_agreement=False)
    assert res_120_no_agreement.is_valid is False
    assert res_120_no_agreement.code == "PROBATION_EXTENSION_REQUIRES_WRITTEN_AGREEMENT"

    # 120 يوماً باتفاق مكتوب صريح -> مقبولة
    res_120_ok = validate_probation_period(probation_days=120, has_written_agreement=True)
    assert res_120_ok.is_valid is True

    # 190 يوماً -> مرفوضة لتجاوز سقف الـ 180 يوماً في جميع الأحوال
    res_190 = validate_probation_period(probation_days=190, has_written_agreement=True)
    assert res_190.is_valid is False
    assert res_190.code == "PROBATION_EXCEEDS_180_DAYS_CAP"


def test_article_109_annual_leave():
    """المادة 109: 21 يوماً ترتفع إلى 30 يوماً بعد 5 سنوات خدمة متصلة"""
    assert calculate_annual_leave_entitlement(continuous_service_years=2.0) == 21
    assert calculate_annual_leave_entitlement(continuous_service_years=4.9) == 21
    assert calculate_annual_leave_entitlement(continuous_service_years=5.0) == 30
    assert calculate_annual_leave_entitlement(continuous_service_years=8.0) == 30


def test_article_113_occasion_leaves_1446h():
    """المادة 113 وتعديلات 1446هـ بالمرسوم الملكي م/44"""
    assert get_occasion_leave_statutory_days(OccasionLeaveType.MARRIAGE) == 5
    assert get_occasion_leave_statutory_days(OccasionLeaveType.DEATH_SPOUSE_PARENT_CHILD) == 5
    assert get_occasion_leave_statutory_days(OccasionLeaveType.DEATH_SIBLING) == 3  # تعديل 1446هـ
    assert get_occasion_leave_statutory_days(OccasionLeaveType.PATERNITY) == 3       # تعديل 1446هـ


def test_article_116_maternity_leave_1446h():
    """المادة 116 وتعديل 1446هـ: إجازة الوضع 12 أسبوعاً بأجر كامل"""
    res = validate_maternity_leave_duration(leave_duration_weeks=12.0)
    assert res.is_valid is True
    assert res.code == "MATERNITY_LEAVE_PAID_VALID"


def test_article_107_overtime_pay():
    """المادة 107: أجر ساعات العمل الإضافية (أجر الساعة الفعلي + 50% من الأساسي)"""
    basic = 4800.0  # 20 ريال/ساعة
    gross = 7200.0  # 30 ريال/ساعة
    hours = 10.0
    # أجر الساعة الفعلي = 30 * 10 = 300 ريال
    # علاوة 50% من الأساسي = 10 * 10 = 100 ريال
    # الإجمالي = 400 ريال
    res = calculate_overtime_pay(basic_wage=basic, gross_wage=gross, overtime_hours=hours, monthly_standard_hours=240.0)
    assert res.standard_hourly_amount == 300.0
    assert res.premium_amount == 100.0
    assert res.total_overtime_pay == 400.0


def test_article_71_disciplinary_repetition_reset():
    """المادة 71: سقوط أثر تكرار المخالفة إذا انقضى عليها 180 يوماً"""
    from saudi_labor_law_rules import determine_disciplinary_occurrence

    # مخالفة أولى
    level, _ = determine_disciplinary_occurrence([], "2026-10-06")
    assert level == "first"

    # مخالفة ثانية خلال 60 يوماً (< 180 يوماً)
    level2, _ = determine_disciplinary_occurrence(["2026-08-01"], "2026-10-06")
    assert level2 == "second"

    # مخالفة بعد مضي 200 يوم (> 180 يوماً) -> يعاد التعيين إلى first بموجب المادة 71
    level_reset, _ = determine_disciplinary_occurrence(["2026-01-01"], "2026-10-06")
    assert level_reset == "first"


def test_article_72_statute_of_limitations():
    """المادة 72: سقوط الدعوى التأديبية بمضي أكثر من 30 يوماً على الكشف أو انتهاء التحقيق"""
    from saudi_labor_law_rules import validate_disciplinary_statute_of_limitations

    # كشف المخالفة وتوقيع الجزاء خلال 15 يوماً -> صحيح
    res_ok = validate_disciplinary_statute_of_limitations(
        violation_date="2026-09-01",
        discovery_date="2026-09-10",
        action_date="2026-09-25"
    )
    assert res_ok.is_valid is True
    assert res_ok.code == "DISCIPLINARY_LIMITATION_VALID"

    # مضي 40 يوماً على الكشف دون تحقيق رسمي -> سقوط بالتقادم
    res_expired = validate_disciplinary_statute_of_limitations(
        violation_date="2026-08-01",
        discovery_date="2026-08-10",
        action_date="2026-09-25"
    )
    assert res_expired.is_valid is False
    assert res_expired.code == "DISCIPLINARY_DISCOVERY_PERIOD_EXCEEDED"


def test_article_80_termination_grounds():
    """المادة 80: الفسخ التأديبي مع التحقق من سماع الدفاع والإنذار الكتابي المسبق"""
    from saudi_labor_law_rules import validate_article_80_termination

    # بدون سماع أقوال العامل -> باطل حتماً
    res_no_hearing = validate_article_80_termination(
        ground_code="ESSENTIAL_OBLIGATIONS_BREACH",
        worker_given_hearing=False
    )
    assert res_no_hearing.is_valid is False
    assert res_no_hearing.code == "ARTICLE_80_NO_HEARING_PROVIDED"

    # إخلال بالتزامات جوهرية بدون إنذار كتابي -> باطل
    res_no_warn = validate_article_80_termination(
        ground_code="ESSENTIAL_OBLIGATIONS_BREACH",
        worker_given_hearing=True,
        has_prior_written_warning=False
    )
    assert res_no_warn.is_valid is False
    assert res_no_warn.code == "ARTICLE_80_MISSING_WRITTEN_WARNING"

    # غياب متصل 16 يوماً مع إنذار بعد 10 أيام وسماع أقوال -> مستوف للشروط
    res_valid_absence = validate_article_80_termination(
        ground_code="UNJUSTIFIED_ABSENCE",
        worker_given_hearing=True,
        has_prior_written_warning=True,
        absence_unjustified_days=16,
        is_absence_consecutive=True
    )
    assert res_valid_absence.is_valid is True
    assert res_valid_absence.code == "ARTICLE_80_TERMINATION_VALID"

