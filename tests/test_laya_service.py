"""
Unit tests for LayaService (Phase 21: Laya Decision Engine Integration).
"""

import unittest
from laya_service import LayaService, LayaDecisionResult


class TestLayaService(unittest.TestCase):
    def setUp(self):
        self.service = LayaService()

    def test_service_info(self):
        info = self.service.get_info()
        self.assertEqual(info["name"], "Laya Decision Engine")
        self.assertIn("leaves", info["domains_supported"])
        self.assertIn("payroll", info["domains_supported"])
        self.assertIn("audit", info["domains_supported"])

    def test_script_analysis_arabic(self):
        res = self.service.analyze_script("أريد طلب إجازة سنوية")
        self.assertTrue(res["is_arabic"])
        self.assertEqual(res["script"], "arabic")

    def test_triage_leave_request(self):
        res = self.service.triage_request("أريد طلب إجازة سنوية لمدة 5 أيام للموظف 100")
        self.assertEqual(res.domain, "leaves")
        self.assertEqual(res.suggested_agent, "leave_service")
        self.assertFalse(res.is_deletion_blocked)
        self.assertEqual(res.extracted_entities.get("employee_id"), 100)

    def test_triage_contract_update_requires_four_eyes(self):
        res = self.service.triage_request("عدل راتب الموظف رقم 100 إلى 8500 ريال")
        self.assertEqual(res.domain, "contracts")
        self.assertEqual(res.action_type, "update")
        self.assertTrue(res.requires_four_eyes)
        self.assertFalse(res.is_deletion_blocked)
        self.assertEqual(res.extracted_entities.get("employee_id"), 100)
        self.assertEqual(res.extracted_entities.get("amount"), 8500.0)

    def test_triage_deletion_blocked(self):
        res = self.service.triage_request("احذف بيانات الموظف رقم 200 من النظام")
        self.assertEqual(res.action_type, "delete")
        self.assertTrue(res.is_deletion_blocked)
        self.assertTrue(res.requires_four_eyes)
        self.assertIn("unlink", res.explanation_ar)

    def test_triage_audit_pdf_request(self):
        res = self.service.triage_request("استخرج لي تقرير الرقابة والتدقيق بصيغة pdf")
        self.assertEqual(res.domain, "audit")
        self.assertEqual(res.suggested_agent, "sijil_service")
        self.assertEqual(res.action_type, "report")

    def test_triage_expenses_request(self):
        res = self.service.triage_request("أريد تسجيل مصروف تذكرة سفر بمبلغ 1200 للموظف 50")
        self.assertEqual(res.domain, "expenses")
        self.assertEqual(res.suggested_agent, "expense_service")
        self.assertEqual(res.extracted_entities.get("employee_id"), 50)
        self.assertEqual(res.extracted_entities.get("amount"), 1200.0)

    def test_triage_expiries_request(self):
        res = self.service.triage_request("هل توجد هويات أو إقامات منتهية الصلاحية هذا الأسبوع؟")
        self.assertEqual(res.domain, "expiries")
        self.assertEqual(res.suggested_agent, "document_expiry_service")


if __name__ == "__main__":
    unittest.main()
