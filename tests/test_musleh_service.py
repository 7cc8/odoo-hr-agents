"""
اختبارات شاملة لوكيل الإصلاح الذاتي والتعافي: «مصلح» (Tests for MuslehService)
=============================================================================
يغطي هذا الملف كافة أدوار مصلح:
1. صمام الأمان: عدم التدخل في الصفوف السليمة (accepted).
2. التدخل في صفوف needs_review و rejected حصراً.
3. سلسلة المشاورة التشخيصية (فاحص، موفق، مدقق).
4. القرارات التنفيذية الأربعة:
   - APPLY_AUTO_PATCH (عند توفر auto_repair والثقة >= 90%).
   - ESCALATE_TO_HUMAN (المرفوع حصراً إلى سراج مع خيارات إجرائية).
   - PROPOSE_MISSING_ENTITY (عند غياب كيان بالكامل في Odoo).
   - QUARANTINE_AND_PROCEED (عزل الصف المعطوب وتمرير بقية الدفعة).
5. حظر المساس التلقائي بالهويات الوطنية والإقامات (خط أحمر).
6. علاج التنسيقات (التواريخ، الهواتف، الإيميلات).
7. منع التكرار والتعافي بعد انقطاع الاتصال (Idempotency).
8. كشف الأسباب الجذرية المكررة في الدفعة.
"""

import unittest
from typing import Any, Dict

from failure_codes import (
    DUPLICATE_EXISTING_EMPLOYEE,
    DUPLICATE_IN_FILE,
    REFERENCE_NOT_FOUND,
)
from musleh_service import (
    CONFIDENCE_THRESHOLD_AUTO_REPAIR,
    DECISION_APPLY_AUTO_PATCH,
    DECISION_ESCALATE_TO_HUMAN,
    DECISION_PROPOSE_MISSING_ENTITY,
    DECISION_QUARANTINE_AND_PROCEED,
    MuslehService,
)


class MockRepository:
    """مستودع تجريبي يوفر مراجع Odoo الحية لـ 'فاحص'."""

    def __init__(self, snapshot: Dict[str, Any]):
        self.snapshot = snapshot

    def get_live_reference_snapshot(self) -> Dict[str, Any]:
        return self.snapshot


class TestMuslehService(unittest.TestCase):

    def setUp(self):
        self.mock_snapshot = {
            "companies": [
                {"id": 15, "name": "شركة النخبة الذكية للتقنية", "active": True},
            ],
            "departments": [
                {"id": 101, "complete_name": "الموارد البشرية", "company_id": [15, "شركة النخبة الذكية للتقنية"], "active": True},
                {"id": 102, "complete_name": "تقنية المعلومات", "company_id": [15, "شركة النخبة الذكية للتقنية"], "active": True},
                {"id": 103, "complete_name": "قسم قديم ملغى", "company_id": [15, "شركة النخبة الذكية للتقنية"], "active": False},
            ],
            "jobs": [
                {"id": 201, "name": "محاسب عام", "company_id": [15, "شركة النخبة الذكية للتقنية"], "active": True},
                {"id": 202, "name": "مهندس برمجيات", "company_id": [15, "شركة النخبة الذكية للتقنية"], "active": True},
            ],
            "existing_employees": [
                {"id": 501, "name": "سارة عبدالله الغامدي", "company_id": [15, "شركة النخبة الذكية للتقنية"]},
            ],
        }
        self.repo = MockRepository(self.mock_snapshot)
        self.musleh = MuslehService(repository=self.repo)

    # =========================================================================
    # 1. صمام الأمان الصارم (Strict Guard)
    # =========================================================================

    def test_musleh_skips_accepted_rows_completely(self):
        """التأكد من أن مصلح لا يتدخل إطلاقاً في الصفوف المقبولة (accepted)."""
        row = {
            "excel_row_number": 2,
            "fields": {
                "name": {"value": "أحمد علي"},
                "company": {"value": "شركة النخبة الذكية للتقنية"},
            },
        }
        val_result = {
            "excel_row_number": 2,
            "final_status": "accepted",
            "failure_code": None,
            "reasons": [],
        }

        # مصلح يجب أن يعيد None فوراً دون أي استهلاك موارد
        res = self.musleh.diagnose_and_heal_row(row, val_result, auto_repair=True)
        self.assertIsNone(res)

    def test_musleh_intervenes_only_on_needs_review_and_rejected(self):
        """التأكد من أن مصلح يتدخل فقط عند وجود needs_review أو rejected."""
        row = {
            "excel_row_number": 3,
            "fields": {
                "name": {"value": "خالد فهد"},
                "company": {"value": "شركة النخبة الذكية للتقنية"},
                "job": {"value": "محاسب مالي"},  # قريب من محاسب عام
            },
        }
        val_result_review = {
            "excel_row_number": 3,
            "final_status": "needs_review",
            "failure_code": "ambiguous_match",
            "reasons": ["تحتاج مراجعة"],
        }
        val_result_rejected = {
            "excel_row_number": 3,
            "final_status": "rejected",
            "failure_code": REFERENCE_NOT_FOUND,
            "reasons": ["المسمى غير موجود"],
        }

        res_review = self.musleh.diagnose_and_heal_row(row, val_result_review, auto_repair=False)
        self.assertIsNotNone(res_review)

        res_rejected = self.musleh.diagnose_and_heal_row(row, val_result_rejected, auto_repair=False)
        self.assertIsNotNone(res_rejected)

    # =========================================================================
    # 2. قرار الإصلاح التلقائي (APPLY_AUTO_PATCH)
    # =========================================================================

    def test_auto_patch_on_high_confidence_date_and_fuzzy_job(self):
        """تطبيق الإصلاح التلقائي الفوري عند تفعيل auto_repair وثقة >= 90%."""
        row = {
            "excel_row_number": 4,
            "fields": {
                "name": {"value": "فيصل ماجد الحربي", "match_key": "فيصل ماجد الحربي"},
                "company": {"value": "شركة النخبة الذكية للتقنية", "match_key": "شركة النخبة الذكية للتقنية"},
                "department": {"value": "الموارد البشرية", "match_key": "الموارد البشرية"},
                "job": {"value": "محاسب عام", "match_key": "محاسب عام"},
                "hiring_date": {"value": "15-05-2026", "match_key": "15-05-2026"},  # صيغة تحتاج تعديل
                "mobile_phone": {"value": "+9660512345678", "match_key": "+9660512345678"},  # صفر مكرر
            },
        }
        val_result = {
            "excel_row_number": 4,
            "final_status": "rejected",
            "failure_code": "date_formatting_error",
            "reasons": ["صيغة التاريخ غير قياسية"],
        }

        res = self.musleh.diagnose_and_heal_row(row, val_result, auto_repair=True)
        self.assertIsNotNone(res)
        self.assertEqual(res.decision, DECISION_APPLY_AUTO_PATCH)
        self.assertEqual(res.final_status, "accepted")
        self.assertTrue(res.is_auto_repaired)
        # التحقق من تصحيح التاريخ والهاتف
        self.assertEqual(res.patched_fields["hiring_date"], "2026-05-15")
        self.assertEqual(res.patched_fields["mobile_phone"], "0512345678")
        self.assertEqual(res.patched_row["fields"]["hiring_date"]["value"], "2026-05-15")

    # =========================================================================
    # 3. خط أحمر: الهويات الوطنية والتكرار لا تُعدل تلقائياً
    # =========================================================================

    def test_identity_duplicates_are_red_line_and_escalate_to_seraj(self):
        """الهويات والتكرار خط أحمر يحال حصراً للمسؤول البشري عبر سراج حتى مع auto_repair."""
        row = {
            "excel_row_number": 5,
            "fields": {
                "name": {"value": "سارة عبدالله الغامدي"},
                "company": {"value": "شركة النخبة الذكية للتقنية"},
            },
        }
        val_result = {
            "excel_row_number": 5,
            "final_status": "needs_review",
            "failure_code": DUPLICATE_EXISTING_EMPLOYEE,
            "reasons": ["يوجد موظف مسجل بنفس الاسم في Odoo"],
        }

        # تشغيل مصلح مع تفعيل auto_repair=True
        res = self.musleh.diagnose_and_heal_row(row, val_result, auto_repair=True)
        self.assertIsNotNone(res)
        # يجب أن يرفض الإصلاح التلقائي ويصدر قرار الإحالة للمسؤول عبر سراج
        self.assertEqual(res.decision, DECISION_ESCALATE_TO_HUMAN)
        self.assertFalse(res.is_auto_repaired)
        self.assertIsNotNone(res.escalation_packet)
        # التأكد الصارم من أن الإحالة مرفوعة إلى سراج
        self.assertEqual(res.escalation_packet.escalated_to, "seraj_orchestrator")
        self.assertIn("الهويات خط أحمر", res.escalation_packet.verdict_ar)
        self.assertTrue(len(res.escalation_packet.actionable_options) >= 2)

    # =========================================================================
    # 4. قرار تأسيس كيان مفقود في Odoo (PROPOSE_MISSING_ENTITY)
    # =========================================================================

    def test_propose_missing_entity_when_no_close_match_exists(self):
        """عند طلب قسم جديد غير مضاف في Odoo ولا يوجد له بديل مقارب."""
        row = {
            "excel_row_number": 6,
            "fields": {
                "name": {"value": "عمر بن سالم"},
                "company": {"value": "شركة النخبة الذكية للتقنية"},
                "department": {"value": "الأمن السيبراني والذكاء الاصطناعي"},  # قسم جديد غير موجود
                "job": {"value": "مهندس برمجيات"},
            },
        }
        val_result = {
            "excel_row_number": 6,
            "final_status": "rejected",
            "failure_code": REFERENCE_NOT_FOUND,
            "reasons": ["القسم غير موجود في Odoo"],
        }

        res = self.musleh.diagnose_and_heal_row(row, val_result, auto_repair=True)
        self.assertIsNotNone(res)
        self.assertEqual(res.decision, DECISION_PROPOSE_MISSING_ENTITY)
        self.assertIn("الأمن السيبراني والذكاء الاصطناعي", res.patched_fields["missing_entity"])
        self.assertIsNotNone(res.escalation_packet)
        self.assertEqual(res.escalation_packet.escalated_to, "seraj_orchestrator")
        # التحقق من وجود خيار تأسيس الكيان للمسؤول
        option_types = [opt.action_type for opt in res.escalation_packet.actionable_options]
        self.assertIn("create_entity", option_types)

    # =========================================================================
    # 5. قرار العزل للدفعة وتفادي التعطيل (QUARANTINE_AND_PROCEED)
    # =========================================================================

    def test_batch_healing_quarantines_broken_rows_and_lets_valid_rows_proceed(self):
        """معالجة دفعة: الصفوف السليمة والجاهزة للإصلاح تمر، والمعطوبة تُعزل."""
        rows = [
            # صف 1: سليم (accepted)
            {"excel_row_number": 2, "fields": {"name": {"value": "موظف سليم"}}},
            # صف 2: خطأ تاريخ قابل للإصلاح (auto-healed)
            {
                "excel_row_number": 3,
                "fields": {
                    "name": {"value": "موظف بتنسيق تاريخ مائل"},
                    "company": {"value": "شركة النخبة الذكية للتقنية"},
                    "hiring_date": {"value": "2026/02/01"},
                },
            },
            # صف 3: تكرار هوية غير قابل للإصلاح التلقائي (quarantined)
            {
                "excel_row_number": 4,
                "fields": {
                    "name": {"value": "سارة عبدالله الغامدي"},
                    "company": {"value": "شركة النخبة الذكية للتقنية"},
                },
            },
        ]
        val_results = [
            {"excel_row_number": 2, "final_status": "accepted", "reasons": []},
            {"excel_row_number": 3, "final_status": "rejected", "failure_code": "date_err", "reasons": []},
            {"excel_row_number": 4, "final_status": "needs_review", "failure_code": DUPLICATE_EXISTING_EMPLOYEE, "reasons": []},
        ]

        batch_res = self.musleh.heal_batch(rows, val_results, auto_repair=True)
        # الإجمالي 3 صفوف: صفان يجب أن يكونا جاهزين للإنشاء (1 سليم + 1 تم إصلاحه)، وصف واحد معزول
        self.assertEqual(batch_res["total_rows"], 3)
        self.assertEqual(batch_res["ready_to_create_count"], 2)
        self.assertEqual(batch_res["quarantined_count"], 1)
        self.assertEqual(len(batch_res["escalated_to_seraj"]), 1)
        self.assertEqual(batch_res["escalated_to_seraj"][0]["escalated_to"], "seraj_orchestrator")

    # =========================================================================
    # 6. وظائف معالجة التنسيقات (Normalization Healing)
    # =========================================================================

    def test_heal_date_formats(self):
        """اختبار تحويل مختلف صيغ التواريخ المعطوبة إلى YYYY-MM-DD."""
        self.assertEqual(MuslehService.heal_date_format("2026-05-15"), "2026-05-15")
        self.assertEqual(MuslehService.heal_date_format("2026/05/15"), "2026-05-15")
        self.assertEqual(MuslehService.heal_date_format("2026.05.15"), "2026-05-15")
        self.assertEqual(MuslehService.heal_date_format("15-05-2026"), "2026-05-15")
        self.assertEqual(MuslehService.heal_date_format("15/05/2026"), "2026-05-15")
        self.assertIsNone(MuslehService.heal_date_format("تاريخ غير صحيح"))

    def test_heal_phone_formats(self):
        """اختبار تصحيح أرقام الهواتف السعودية وتوحيدها."""
        self.assertEqual(MuslehService.heal_phone_format("+9660512345678"), "0512345678")
        self.assertEqual(MuslehService.heal_phone_format("9660512345678"), "0512345678")
        self.assertEqual(MuslehService.heal_phone_format("+966512345678"), "0512345678")
        self.assertEqual(MuslehService.heal_phone_format("512345678"), "0512345678")
        self.assertEqual(MuslehService.heal_phone_format("0512345678"), "0512345678")

    def test_heal_email_formats(self):
        """اختبار تنظيف البريد الإلكتروني وإزالة المسافات المخفية."""
        self.assertEqual(MuslehService.heal_email_format("  User@Example.Com  "), "user@example.com")
        self.assertEqual(MuslehService.heal_email_format("user @example.com"), "user@example.com")
        self.assertIsNone(MuslehService.heal_email_format("بريد معطوب بدون آت"))

    # =========================================================================
    # 7. التعافي ومنع التكرار عند انقطاع الاتصال (Idempotency Guard)
    # =========================================================================

    def test_verify_and_recover_submission_detects_existing_employee(self):
        """فحص Odoo بعد انقطاع الاتصال لكشف هل تم إنشاء الموظف ومنع تكراره."""
        # سارة مسجلة مسبقاً في الـ snapshot
        res = self.musleh.verify_and_recover_submission("سارة عبدالله الغامدي", company_id=15)
        self.assertTrue(res["recovered"])
        self.assertEqual(res["odoo_id"], 501)
        self.assertIn("موجود بالفعل", res["message_ar"])

        # موظف غير موجود: آمن للإعادة
        res_new = self.musleh.verify_and_recover_submission("ماجد عبدالله الشمري", company_id=15)
        self.assertFalse(res_new["recovered"])
        self.assertIn("آمنة للإعادة", res_new["message_ar"])

    # =========================================================================
    # 8. كشف الأسباب الجذرية المكررة في الدفعة (Root Cause Analyzer)
    # =========================================================================

    def test_analyze_batch_root_causes_identifies_repeated_patterns(self):
        """رصد الأخطاء المتكررة للكيانات لتقديم توصية واحدة ذكية لسراج."""
        decisions = [
            MuslehService._make_executive_decision(
                self.musleh,
                row={"excel_row_number": 2, "fields": {"name": {"value": "أ1"}, "department": {"value": "الذكاء الاصطناعي"}}},
                validation_result={"excel_row_number": 2, "final_status": "rejected", "failure_code": REFERENCE_NOT_FOUND},
                consultation={
                    "fahas": {"department_exists": False, "job_exists": True},
                    "muwaffaq": {"suggested_department": None, "department_confidence": 0.2, "suggested_job": None, "job_confidence": 1.0},
                    "mudaqqiq": {"is_statutorily_compliant": True, "labor_law_notes": []},
                    "simple_decision": {"domain": "general", "action_type": "update", "requires_four_eyes": False, "is_deletion_blocked": False},
                },
                auto_repair=True,
            ),
            MuslehService._make_executive_decision(
                self.musleh,
                row={"excel_row_number": 3, "fields": {"name": {"value": "أ2"}, "department": {"value": "الذكاء الاصطناعي"}}},
                validation_result={"excel_row_number": 3, "final_status": "rejected", "failure_code": REFERENCE_NOT_FOUND},
                consultation={
                    "fahas": {"department_exists": False, "job_exists": True},
                    "muwaffaq": {"suggested_department": None, "department_confidence": 0.2, "suggested_job": None, "job_confidence": 1.0},
                    "mudaqqiq": {"is_statutorily_compliant": True, "labor_law_notes": []},
                    "simple_decision": {"domain": "general", "action_type": "update", "requires_four_eyes": False, "is_deletion_blocked": False},
                },
                auto_repair=True,
            ),
        ]

        causes = self.musleh.analyze_batch_root_causes(decisions)
        self.assertTrue(len(causes) >= 1)
        self.assertEqual(causes[0]["pattern"], "repeated_missing_entity")
        self.assertEqual(causes[0]["entity_name"], "الذكاء الاصطناعي")
        self.assertEqual(causes[0]["affected_rows_count"], 2)


if __name__ == "__main__":
    unittest.main()
