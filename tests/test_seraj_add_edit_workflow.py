"""
اختبارات مسار الإضافة والتعديل والتحضير والاعتماد والتنفيذ والتحقق الراجع لسراج والوكلاء
========================================================================================
1. تحضير طلب التعديل: فحص فاحص لسجل الموظف الحالي في Odoo، تدقيق البيانات، عرض المسودة وطلب التأكيد.
2. اعتماد وتنفيذ التعديل: استلام «تأكيد» -> تنفيذ كاتب في Odoo -> تحقق راجع عبر فاحص -> توثيق سجل.
3. إلغاء العملية: استلام «إلغاء» -> تفريغ العملية المعلقة دون أي تعديل.
4. موظف غير موجود: إبلاغ المستخدم بوضوح بعدم عثور فاحص عليه في Odoo.
5. حظر الحذف الكلي: رفض طلبات الحذف فورياً بموجب سياسة الحوكمة لحارس.
"""

import unittest
from unittest.mock import MagicMock, patch

from fahas_service import FahasAgent
from katib_service import KatibAgent
from seraj_llm_service import SerajLLMService
from seraj_session_manager import SerajSessionManager


class TestSerajAddEditWorkflow(unittest.TestCase):

    def setUp(self):
        self.session_mgr = SerajSessionManager.get_instance()
        self.chat_id = "test_add_edit_chat_1"
        self.session_mgr.reset_session(self.chat_id)

        self.mock_fahas = MagicMock(spec=FahasAgent)
        self.mock_katib = MagicMock(spec=KatibAgent)

        self.seraj = SerajLLMService(
            api_key="sk-or-test-mock-key",
            fahas_agent=self.mock_fahas,
            katib_agent=self.mock_katib,
        )

    def tearDown(self):
        self.session_mgr.reset_session(self.chat_id)

    def test_edit_workflow_preparation_and_confirmation(self):
        # 1. تهيئة رد فاحص عند البحث عن الموظفة سارة
        self.mock_fahas.search_records.return_value = {
            "records": [
                {
                    "id": 42,
                    "name": "سارة أحمد",
                    "job_title": "أخصائية توظيف",
                    "company_id": [15, "شركة النخبة للحلول التقنية"],
                }
            ],
            "total_count": 1,
        }

        # الخطوة 1: المستخدم يطلب التعديل
        prep_resp = self.seraj.chat_turn(
            "عدل مسمى سارة إلى مديرة توظيف",
            chat_id=self.chat_id,
        )

        # التحقق من أن سراج لم يرفض الطلب بل حضره وطلب الاعتماد
        self.assertIn("في انتظار الاعتماد", prep_resp)
        self.assertIn("سارة أحمد", prep_resp)
        self.assertIn("42", prep_resp)
        self.assertIn("أخصائية توظيف", prep_resp)
        self.assertIn("مديرة توظيف", prep_resp)
        self.assertIn("فاحص", prep_resp)
        self.assertIn("كاتب", prep_resp)

        # التحقق من حفظ العملية المعلقة في الجلسة
        session = self.session_mgr.get_session(self.chat_id)
        self.assertIsNotNone(session.pending_action)
        self.assertEqual(session.pending_action["type"], "update")
        self.assertEqual(session.pending_action["employee_id"], 42)
        self.assertEqual(session.pending_action["new_value"], "مديرة توظيف")

        # الخطوة 2: المستخدم يؤكد العملية
        self.mock_katib.execute_approved_action.return_value = {
            "ok": True,
            "action": "update",
            "employee_id": 42,
        }
        self.mock_fahas.read_records.return_value = {
            "records": [
                {
                    "id": 42,
                    "name": "سارة أحمد",
                    "job_title": "مديرة توظيف",
                }
            ]
        }

        confirm_resp = self.seraj.chat_turn("تأكيد", chat_id=self.chat_id)

        # التحقق من التنفيذ عبر كاتب والتحقق الراجع عبر فاحص
        self.mock_katib.execute_approved_action.assert_called_once()
        self.mock_fahas.read_records.assert_called_once()
        self.assertIn("تم تنفيذ وتأكيد العملية بنجاح عبر «كاتب»", confirm_resp)
        self.assertIn("التحقق الراجع (فاحص)", confirm_resp)
        self.assertIn("مديرة توظيف", confirm_resp)

        # التحقق من تفريغ العملية المعلقة
        self.assertIsNone(session.pending_action)

    def test_edit_workflow_cancellation(self):
        self.mock_fahas.search_records.return_value = {
            "records": [{"id": 10, "name": "أحمد علي", "job_title": "محاسب"}],
            "total_count": 1,
        }

        # تحضير الطلب
        self.seraj.chat_turn("عدل مسمى أحمد إلى مدير حسابات", chat_id=self.chat_id)
        session = self.session_mgr.get_session(self.chat_id)
        self.assertIsNotNone(session.pending_action)

        # إلغاء الطلب
        cancel_resp = self.seraj.chat_turn("إلغاء", chat_id=self.chat_id)

        self.assertIn("تم إلغاء العملية", cancel_resp)
        self.assertIsNone(session.pending_action)
        self.mock_katib.execute_approved_action.assert_not_called()

    def test_edit_when_employee_not_found(self):
        self.mock_fahas.search_records.return_value = {"records": [], "total_count": 0}

        resp = self.seraj.chat_turn("عدل مسمى مجهول إلى مهندس", chat_id=self.chat_id)

        self.assertIn("لم يتمكن «فاحص» من العثور على موظف", resp)
        session = self.session_mgr.get_session(self.chat_id)
        self.assertIsNone(session.pending_action)

    def test_add_workflow_preparation_and_confirmation(self):
        self.mock_fahas.search_records.return_value = {"records": [], "total_count": 0}

        prep_resp = self.seraj.chat_turn("أضف موظف جديد باسم فهد", chat_id=self.chat_id)
        self.assertIn("في انتظار الاعتماد", prep_resp)
        self.assertIn("فهد", prep_resp)

        self.mock_katib.execute_approved_action.return_value = {
            "ok": True,
            "action": "create",
            "employee_id": 99,
        }

        confirm_resp = self.seraj.chat_turn("اعتمد", chat_id=self.chat_id)
        self.assertIn("تم إنشاء الموظف بنجاح عبر «كاتب»", confirm_resp)
        self.assertIn("99", confirm_resp)

    def test_ambiguous_deletion_asks_clarification(self):
        """طلب «احذف» الغامض يجب أن يطلب توضيح الإجراء (أرشفة أم حذف نهائي) ولا يُنفِّذ."""
        resp = self.seraj.chat_turn("احذف الموظف رقم 5", chat_id=self.chat_id)
        # سراج يسأل عن نوع الإجراء بدلاً من رفضه مباشرة
        self.assertIn("توضيح", resp)
        session = self.session_mgr.get_session(self.chat_id)
        # لا يُنفَّذ أي إجراء — لا يوجد pending_action
        self.assertIsNone(session.pending_action)
        # فاحص وكاتب لم يُستدعيا
        self.mock_fahas.search_records.assert_not_called()
        self.mock_katib.execute_approved_action.assert_not_called()
