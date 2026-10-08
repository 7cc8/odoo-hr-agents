"""
مجموعة اختبارات التحقق الشاملة لـ «سراج»: 23 سيناريو واقعي ومنطقي
===================================================================
تختبر هذه المجموعة الجاهزية التشغيلية الكاملة لسراج، وتشمل:
1. استشارات نظام العمل السعودي وتعديلات 1446هـ (المواد 98, 107, 85, 84, 77, 70, 71, 72, 92, 53, 113, 116, 37, والتأمينات).
2. استعلامات موظفي Odoo ومكافحة الهلوسة وفض الالتباس (Disambiguation).
3. مبدأ العينين الأربع (Four-Eyes) وحواجز الأمان الرقابية لـ «لايا».
4. الحسابات الحدية وسقوف التأمينات وانتقال الإجازات السنوية ورصد الوثائق.
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import date, datetime
from typing import Any, Dict, List

# إضافة المسار الحالي
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from saudi_labor_law_rules import (
    calculate_annual_leave_entitlement,
    calculate_article_77_compensation,
    calculate_end_of_service_benefit,
    calculate_gosi_contributions,
    calculate_overtime_pay,
    get_occasion_leave_statutory_days,
    validate_contract_type_for_nationality,
    validate_disciplinary_deduction,
    validate_disciplinary_statute_of_limitations,
    validate_loan_installment_cap,
    validate_maternity_leave_duration,
    validate_probation_period,
    ContractType,
    NationalityType,
    OccasionLeaveType,
    ResignationReason,
    RAMADAN_MUSLIM_DAILY_HOURS,
    RAMADAN_MUSLIM_WEEKLY_HOURS,
)
from laya_service import LayaService
from seraj_llm_service import SerajLLMService
from odoo_readonly_repository import OdooReadonlyRepository
from leave_service import LeaveService
from document_expiry_service import DocumentExpiryService


class TestSeraj20Scenarios(unittest.TestCase):
    """مجموعة اختبارات الـ 23 سيناريو لـ سراج."""

    def setUp(self):
        self.laya = LayaService()
        self.repo = OdooReadonlyRepository()
        self.leave_service = LeaveService(readonly_repo=self.repo)
        self.expiry_service = DocumentExpiryService(repo=self.repo)
        self.seraj_llm = SerajLLMService()

    # =========================================================================
    # المجموعة 1: استشارات نظام العمل السعودي وتعديلات 1446هـ
    # =========================================================================

    def test_scenario_01_ramadan_hours_article_98(self):
        """سيناريو 1: ساعات العمل في رمضان للمسلمين (المادة 98) -> 6 ساعات يومياً / 36 أسبوعياً."""
        query = "كم ساعات العمل الرسمية في رمضان للمسلمين حسب نظام العمل؟"
        decision = self.laya.triage_request(query)
        self.assertFalse(decision.is_deletion_blocked)
        self.assertEqual(RAMADAN_MUSLIM_DAILY_HOURS, 6.0)
        self.assertEqual(RAMADAN_MUSLIM_WEEKLY_HOURS, 36.0)

    def test_scenario_02_overtime_premium_article_107(self):
        """سيناريو 2: أجر ساعات العمل الإضافية (المادة 107) -> أجر الساعة الفعلي + 50% علاوة (1.5x)."""
        res = calculate_overtime_pay(
            basic_wage=10000.0,
            gross_wage=12000.0,
            overtime_hours=10.0,
            monthly_standard_hours=240.0,
        )
        self.assertEqual(res.gross_hourly_rate, 50.0)      # 12,000 / 240
        self.assertEqual(res.basic_hourly_rate, 41.67)     # 10,000 / 240
        self.assertEqual(res.total_overtime_pay, 708.33)
        self.assertIn("المادة 107", res.article_reference)

    def test_scenario_03_resignation_eos_article_85(self):
        """سيناريو 3: مكافأة نهاية الخدمة عند الاستقالة بعد 4 سنوات (المادة 85) -> ثلث المكافأة."""
        res = calculate_end_of_service_benefit(
            last_gross_wage=9000.0,
            service_years=4.0,
            is_saudi=True,
            is_resignation=True,
        )
        self.assertAlmostEqual(res.entitlement_ratio, 1.0 / 3.0, places=2)
        self.assertAlmostEqual(res.net_eosb_amount, 6000.0, places=2)
        self.assertIn("المادة 85", res.article_reference)

    def test_scenario_04_termination_eos_article_84(self):
        """سيناريو 4: إنهاء العقد خدمة 6 سنوات وراتب 12,000 (المادة 84) -> 42,000 ريال."""
        res = calculate_end_of_service_benefit(
            last_gross_wage=12000.0,
            service_years=6.0,
            is_saudi=True,
            is_resignation=False,
        )
        self.assertEqual(res.tier1_amount, 30000.0)  # 5 سنوات × 6,000
        self.assertEqual(res.tier2_amount, 12000.0)  # سنة × 12,000
        self.assertEqual(res.net_eosb_amount, 42000.0)
        self.assertIn("المادة 84", res.article_reference)

    def test_scenario_05_article_77_unlawful_termination(self):
        """سيناريو 5: التعويض عن الإنهاء غير المشروع (المادة 77) -> لا يقل عن أجر شهرين."""
        res = calculate_article_77_compensation(
            monthly_wage=10000.0,
            is_saudi=True,
            contract_type=ContractType.INDEFINITE,
            service_years=2.0,
        )
        self.assertEqual(res.statutory_minimum_amount, 20000.0)
        self.assertEqual(res.final_compensation_amount, 20000.0)  # الحد الأدنى شهرين
        self.assertIn("المادة 77", res.article_reference)

    def test_scenario_06_disciplinary_deduction_ceiling_article_70(self):
        """سيناريو 6: حظر حسم أكثر من 5 أيام كجزاء في الشهر (المادة 70)."""
        val_fail = validate_disciplinary_deduction(
            daily_wage=300.0,
            infraction_deduction_days=8.0,
            month_cumulative_deduction_days=0.0,
        )
        self.assertFalse(val_fail.is_valid)
        self.assertIn("المادة 70", val_fail.article)

        val_pass = validate_disciplinary_deduction(
            daily_wage=300.0,
            infraction_deduction_days=3.0,
            month_cumulative_deduction_days=0.0,
        )
        self.assertTrue(val_pass.is_valid)

    def test_scenario_07_disciplinary_statute_of_limitations_articles_71_72(self):
        """سيناريو 7: تقادم وسقوط المخالفة بعد مضي 30 يوماً على اكتشافها (المادة 72)."""
        val = validate_disciplinary_statute_of_limitations(
            violation_date="2026-08-01",
            discovery_date="2026-08-01",
            action_date="2026-09-15",  # 45 days > 30 days
        )
        self.assertFalse(val.is_valid)
        self.assertIn("المادة 72", val.article)

    def test_scenario_08_loan_deduction_ceiling_article_92(self):
        """سيناريو 8: سقف قسط سلفة صاحب العمل لا يتجاوز 10% من الراتب (المادة 92 المعدلة)."""
        val_fail = validate_loan_installment_cap(
            monthly_wage=8000.0,
            proposed_installment=1200.0,  # 15% > 10%
        )
        self.assertFalse(val_fail.is_valid)
        self.assertIn("المادة 92", val_fail.article)

        val_pass = validate_loan_installment_cap(
            monthly_wage=8000.0,
            proposed_installment=800.0,  # 10% -> OK
        )
        self.assertTrue(val_pass.is_valid)

    def test_scenario_09_probation_period_article_53(self):
        """سيناريو 9: فترة التجربة الأصلية 90 يوماً والتمديد إلى 180 مشروط باتفاق كتابي (المادة 53)."""
        val_fail = validate_probation_period(
            probation_days=150,
            has_written_agreement=False,
            is_extension=True,
        )
        self.assertFalse(val_fail.is_valid)

        val_pass = validate_probation_period(
            probation_days=180,
            has_written_agreement=True,
            is_extension=True,
        )
        self.assertTrue(val_pass.is_valid)
        self.assertIn("المادة 53", val_pass.article)

    def test_scenario_10_occasion_leaves_article_113(self):
        """سيناريو 10: إجازات المناسبات بعد تعديل 1446هـ (المادة 113) -> الأبوة 3 أيام، الأخ 3 أيام، الزواج 5."""
        paternity_days = get_occasion_leave_statutory_days(OccasionLeaveType.PATERNITY)
        sibling_days = get_occasion_leave_statutory_days(OccasionLeaveType.DEATH_SIBLING)
        marriage_days = get_occasion_leave_statutory_days(OccasionLeaveType.MARRIAGE)

        self.assertEqual(paternity_days, 3)
        self.assertEqual(sibling_days, 3)
        self.assertEqual(marriage_days, 5)

    def test_scenario_11_maternity_leave_article_116_151(self):
        """سيناريو 11: إجازة الوضع للأم العاملة (تعديلات 1446هـ) -> 12 أسبوعاً بأجر كامل وما زاد بدون أجر."""
        val = validate_maternity_leave_duration(leave_duration_weeks=12.0)
        self.assertTrue(val.is_valid)
        self.assertEqual(val.code, "MATERNITY_LEAVE_PAID_VALID")
        self.assertEqual(val.details["paid_weeks"], 12)

        val_extended = validate_maternity_leave_duration(leave_duration_weeks=16.0)
        self.assertTrue(val_extended.is_valid)
        self.assertEqual(val_extended.code, "MATERNITY_LEAVE_EXTENDED_UNPAID")
        self.assertEqual(val_extended.details["paid_weeks"], 12)
        self.assertEqual(val_extended.details["unpaid_weeks"], 4.0)

    def test_scenario_12_non_saudi_contract_term_article_37(self):
        """سيناريو 12: اشتراط العقد محدد المدة لغير السعودي وبطلان العقد غير المحدد (المادة 37)."""
        val_fail = validate_contract_type_for_nationality(
            is_saudi=False,
            contract_type=ContractType.INDEFINITE,
        )
        self.assertFalse(val_fail.is_valid)
        self.assertIn("المادة 37", val_fail.article)

        val_pass = validate_contract_type_for_nationality(
            is_saudi=False,
            contract_type=ContractType.FIXED,
        )
        self.assertTrue(val_pass.is_valid)

    def test_scenario_13_gosi_contributions_saudi_vs_non_saudi(self):
        """سيناريو 13: نسب اشتراكات التأمينات الاجتماعية GOSI للسعودي وغير السعودي."""
        gosi_saudi = calculate_gosi_contributions(
            basic_wage=8000.0,
            housing_allowance=2000.0,
            is_saudi=True,
        )
        self.assertEqual(gosi_saudi.capped_contributory_wage, 10000.0)
        self.assertEqual(gosi_saudi.total_employee, 975.0)    # 9.75%
        self.assertEqual(gosi_saudi.total_employer, 1175.0)  # 11.75%

        gosi_expat = calculate_gosi_contributions(
            basic_wage=8000.0,
            housing_allowance=2000.0,
            is_saudi=False,
        )
        self.assertEqual(gosi_expat.total_employee, 0.0)     # 0%
        self.assertEqual(gosi_expat.total_employer, 200.0)   # 2% أخطار مهنية

    # =========================================================================
    # المجموعة 2: استعلامات موظفي Odoo ومكافحة الهلوسة
    # =========================================================================

    def test_scenario_14_disambiguation_multiple_candidates(self):
        """سيناريو 14: فض الالتباس عند البحث بلقب عائلة مشترك ('القحطاني') -> إرجاع خيارات متعددة بأرقام ID."""
        cands = self.repo.search_employee_candidates("القحطاني")
        self.assertGreaterEqual(len(cands), 2)
        names = [c["name"] for c in cands]
        self.assertTrue(any("ناصر" in n for n in names))
        self.assertTrue(any("نورة" in n for n in names))

    def test_scenario_15_exact_employee_lookup(self):
        """سيناريو 15: استعلام دقيق لموظف محدد ('ناصر') -> إرجاع مرشح واحد مطابق مع بياناته."""
        cands = self.repo.search_employee_candidates("ناصر")
        self.assertEqual(len(cands), 1)
        emp = cands[0]
        self.assertEqual(emp["id"], 147)
        self.assertIn("ناصر محمود القحطاني", emp["name"])

    def test_scenario_16_anti_hallucination_zero_matches(self):
        """سيناريو 16: مكافحة الهلوسة لموظف غير موجود إطلاقاً في Odoo -> إرجاع قائمة فارغة بدقة."""
        cands = self.repo.search_employee_candidates("ممدوح الخوارزمي")
        self.assertEqual(len(cands), 0)

    # =========================================================================
    # المجموعة 3: مبدأ العينين الأربع وحواجز الأمان
    # =========================================================================

    def test_scenario_17_laya_blocks_deletion_unlink(self):
        """سيناريو 17: حاجز الأمان الرقابي لـ «لايا» يحظر الحذف الكلي لأي موظف أو سجل."""
        decision = self.laya.triage_request("احذف الموظف رقم 147 نهائياً من النظام")
        self.assertTrue(decision.is_deletion_blocked)
        self.assertEqual(decision.action_type, "delete")
        self.assertIn("محظور أمنياً", decision.action_type_ar)

    def test_scenario_18_dry_run_leave_simulation_generates_token(self):
        """سيناريو 18: محاكاة تقديم إجازة (Dry-run) تولد رمز موافقة مع مدة صلاحية محددة."""
        res = self.leave_service.dry_run_leave_request(
            employee_id=147,
            holiday_status_id=1,
            date_from="2026-11-01",
            date_to="2026-11-03",
        )
        self.assertTrue(res.is_valid)
        self.assertTrue(res.can_proceed)
        token = res.approval_token
        self.assertIsNotNone(token)
        self.assertTrue(token.startswith("LEAVE-"))

    def test_scenario_19_four_eyes_strictly_rejects_casual_words(self):
        """سيناريو 19: مبدأ العينين الأربع يرفض الكلمات غير الرسمية (نعم، تمام) ويلزم بكتابة 'تأكيد'."""
        dry_res = self.leave_service.dry_run_leave_request(
            employee_id=147,
            holiday_status_id=1,
            date_from="2026-11-01",
            date_to="2026-11-03",
        )
        self.assertTrue(dry_res.is_valid)

        # استدعاء بكلمة غير صحيحة "نعم"
        res_fail = self.leave_service.apply_leave_request(
            approval_token=dry_res.approval_token,
            user_confirmation_text="نعم",
        )
        self.assertFalse(res_fail.success)

    def test_scenario_20_expired_or_invalid_approval_token_rejected(self):
        """سيناريو 20: رفض رمز الموافقة غير الموجود أو المنتهي الصلاحية مع رسالة توجيه واضحة."""
        res = self.leave_service.apply_leave_request(
            approval_token="LEAVE-EXPIRED-999999",
            user_confirmation_text="تأكيد",
        )
        self.assertFalse(res.success)
        self.assertIn("رمز الموافقة غير صالح أو منتهي الصلاحية", res.message_ar)

    # =========================================================================
    # المجموعة 4: الحسابات الحدية وسقوف التأمينات ورصد الوثائق
    # =========================================================================

    def test_scenario_21_gosi_ceiling_cap_45000_sar(self):
        """سيناريو 21: الالتزام بسقف الأجر الخاضع للتأمينات (45,000 ريال) حتى للرواتب الأعلى."""
        res = calculate_gosi_contributions(
            basic_wage=50000.0,
            housing_allowance=10000.0,
            is_saudi=True,
        )
        # الراتب الخاضع يجب أن يُقيد بسقف 45,000 ريال
        self.assertEqual(res.capped_contributory_wage, 45000.0)
        self.assertEqual(res.total_employee, 45000.0 * 0.0975)  # 4,387.50 ريال

    def test_scenario_22_annual_leave_seniority_upgrade_article_109(self):
        """سيناريو 22: ترقية رصيد الإجازة السنوية من 21 إلى 30 يوماً عند إتمام 5 سنوات خدمة (المادة 109)."""
        leave_under_5 = calculate_annual_leave_entitlement(continuous_service_years=4.5)
        leave_at_5 = calculate_annual_leave_entitlement(continuous_service_years=5.0)

        self.assertEqual(leave_under_5, 21)
        self.assertEqual(leave_at_5, 30)

    def test_scenario_23_document_expiry_proactive_audit(self):
        """سيناريو 23: الرصد الاستباقي للوثائق المنتهية وفترات التجربة والتنبيهات المجدولة."""
        mock_emps = [{
            "id": 101,
            "name": "أحمد سعيد",
            "id_expiry_date": "2026-10-20",
            "passport_expiration_date": "2026-11-15",
        }]
        scan_res = self.expiry_service.scan_expiries(
            reference_date=date(2026, 10, 1),
            max_days=90,
            employees_data=mock_emps,
        )
        self.assertIsNotNone(scan_res)
        self.assertGreaterEqual(scan_res.total_alerts, 2)
        self.assertGreaterEqual(len(scan_res.items), 2)


def run_comprehensive_scenario_demonstration():
    """تشغيل وطباعة التقرير الشامل لجميع السيناريوهات باللغة العربية."""
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestSeraj20Scenarios)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print(f"\n==================================================")
    print(f"نتيجة الاختبار الشامل: {result.testsRun} سيناريو تم تنفيذها.")
    print(f"الحالة: {'ناجح 100% بنجاح تام' if result.wasSuccessful() else 'توجد أخطاء'}")
    print(f"==================================================")


if __name__ == "__main__":
    run_comprehensive_scenario_demonstration()
