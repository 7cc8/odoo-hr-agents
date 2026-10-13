"""
اختبارات تكاملية وتحقق لوكيل التدقيق «مدقق» وتوجيه استشارات نظام العمل السعودي عبر «سراج».
"""

import unittest
from agent_events_service import get_events_service
from seraj_llm_service import SerajLLMService
from labor_law_knowledge import is_labor_law_query, LaborLawKnowledgeBase
from agents.mudaqqiq_agent import get_mudaqqiq_agent


class TestLaborLawMudaqqiqRouting(unittest.TestCase):
    def setUp(self):
        self.seraj = SerajLLMService()
        self.events_service = get_events_service()

    def test_is_labor_law_query_detection(self):
        # أسئلة نظام العمل
        self.assertTrue(is_labor_law_query("كم ساعات العمل الرسمية في رمضان للمسلمين؟"))
        self.assertTrue(is_labor_law_query("ما هو دوام رمضان وفق نظام العمل؟"))
        self.assertTrue(is_labor_law_query("كم مدة فترة التجربة في نظام العمل السعودي؟"))
        self.assertTrue(is_labor_law_query("ما هي ضوابط مكافأة نهاية الخدمة؟"))
        self.assertTrue(is_labor_law_query("ما نص المادة 98؟"))

        # أسئلة موظفين في Odoo (لا تطابق نظام العمل)
        self.assertFalse(is_labor_law_query("كم عدد الموظفين؟"))
        self.assertFalse(is_labor_law_query("ابحث عن الموظف أحمد علي"))
        self.assertFalse(is_labor_law_query("أضف موظف جديد اسمه سالم"))

    def test_mudaqqiq_consult_ramadan_hours(self):
        mudaqqiq = get_mudaqqiq_agent()
        res = mudaqqiq.consult_labor_law("كم ساعات العمل الرسمية في رمضان للمسلمين؟")

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["agent"], "mudaqqiq")
        self.assertEqual(res["primary_article_number"], 98)
        self.assertIn("ست (6) ساعات", res["explanation_ar"])
        self.assertIn("ست وثلاثين (36) ساعة", res["explanation_ar"])
        self.assertIn("المادة 98", res["primary_article_title"])

    def test_seraj_chat_turn_ramadan_hours_routing_and_events(self):
        op_id = self.events_service.start_operation(
            user_query="كم ساعات العمل الرسمية في رمضان للمسلمين؟",
            operation_type="conversation",
            chat_id="test_ramadan_chat",
        )

        reply = self.seraj.chat_turn(
            user_query="كم ساعات العمل الرسمية في رمضان للمسلمين؟",
            chat_id="test_ramadan_chat",
            operation_id=op_id,
        )

        # التحقق من محتوى الرد
        self.assertIn("المادة 98", reply)
        self.assertIn("ست (6) ساعات", reply)
        self.assertIn("ست وثلاثين (36) ساعة", reply)
        self.assertIn("مدقق", reply)
        self.assertIn("نظام العمل السعودي", reply)

        # التحقق من أحداث الوكلاء
        events = self.events_service.get_operation_events(op_id)
        agents_involved = [e.get("agent") for e in events]

        # يجب أن يظهر مدقق وسراج (ولا يظهر سجل لأن الاستشارة ليست عملية كتابة أو تعديل أو حذف في Odoo)
        self.assertIn("modaqeq", agents_involved)
        self.assertIn("seraj", agents_involved)
        self.assertNotIn("sijil", agents_involved)

        # لا يجب استدعاء فاحص لقراءة Odoo في هذا الاستفسار النظامي
        self.assertNotIn("fahas", agents_involved)
        # ولا موفق لمطابقة الأسماء
        self.assertNotIn("mowafaq", agents_involved)

    def test_seraj_probation_period_article_53(self):
        reply = self.seraj.chat_turn("كم فترة التجربة في نظام العمل السعودي؟")
        self.assertIn("المادة 53", reply)
        self.assertIn("تسعين (90) يوماً", reply)
        self.assertIn("مدقق", reply)

    def test_seraj_end_of_service_article_84(self):
        reply = self.seraj.chat_turn("ما هي ضوابط مكافأة نهاية الخدمة؟")
        self.assertTrue("المادة 84" in reply or "المادتين (84 و 85)" in reply or "84" in reply)
        self.assertIn("نصف شهر", reply)
        self.assertIn("مدقق", reply)

    def test_seraj_maternity_leave_article_151(self):
        reply = self.seraj.chat_turn("ما هي مدة إجازة الوضع للمرأة العاملة في نظام العمل؟")
        self.assertIn("المادة 151", reply)
        self.assertIn("إجازة وضع", reply)
        self.assertIn("مدقق", reply)


if __name__ == "__main__":
    unittest.main()
