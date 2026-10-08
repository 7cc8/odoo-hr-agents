"""
اختبارات شاملة لقدرة سراج على فهم الأسئلة واستدعاء أدوات Odoo الحصرية للقراءة (Tool Calling)
========================================================================================
تغطي جميع معايير القبول المحددة:
1. «كم عدد الموظفين؟» -> عدّ فعلي عبر count_records وليس بحثاً بالاسم.
2. «والمؤرشفين؟» -> سؤال متابع يستخدم سياق الموديل السابق ويطلب المؤرشفين.
3. «ما الشركات المتاحة لي؟» -> استعلام حقيقي عبر list_companies بحسب الصلاحيات.
4. «ابحث عن موظف اسمه أحمد» -> بحث بالاسم عبر search_records.
5. سؤال مبهم -> سؤال توضيحي دون تخمين.
6. خطأ اتصال أو صلاحية -> رسالة خطأ واضحة، لا «لم نجد موظفين».
7. طلب إنشاء أو حذف -> رفض صريح ومباشر، لا تنفيذ عبر أدوات القراءة.
8. اختيار اتصال مختلف دون تعديل منطق سراج.
9. فض الالتباس: «الشركة الثانية» بعد سؤال اختيار الشركة تُحل إلى ID المنشأة.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from laya_service import LayaService
from odoo_agent_tools import (
    count_records,
    describe_model,
    execute_tool_call,
    list_companies,
    list_connections,
    read_records,
    search_records,
    OdooToolSecurityError,
    OdooToolExecutionError,
)
from seraj_session_manager import ConversationSession, SerajSessionManager
from seraj_llm_service import SerajLLMService


class TestSerajToolCalling(unittest.TestCase):

    def setUp(self):
        self.session_mgr = SerajSessionManager.get_instance()
        self.chat_id = "test_chat_999"
        self.session_mgr.reset_session(self.chat_id)
        self.seraj = SerajLLMService(api_key="sk-or-test-mock-key")

    def tearDown(self):
        self.session_mgr.reset_session(self.chat_id)

    # -------------------------------------------------------------------------
    # 1. اختبار فرز لايا للرسائل العامة وعدم تحويلها لاسم موظف
    # -------------------------------------------------------------------------
    def test_laya_triage_does_not_extract_employee_name_for_counting_or_general(self):
        laya = LayaService()
        
        # «كم عدد الموظفين» لا يجب أن يُعتبر اسم موظف
        dec1 = laya.triage_request("كم عدد الموظفين")
        self.assertIsNone(dec1.extracted_entities.get("employee_query"))
        
        # «والمؤرشفين؟»
        dec2 = laya.triage_request("والمؤرشفين؟")
        self.assertIsNone(dec2.extracted_entities.get("employee_query"))
        
        # «ما الشركات المتاحة لي؟»
        dec3 = laya.triage_request("ما الشركات المتاحة لي؟")
        self.assertIsNone(dec3.extracted_entities.get("employee_query"))
        
        # «الشركة الثانية»
        dec4 = laya.triage_request("الشركة الثانية")
        self.assertIsNone(dec4.extracted_entities.get("employee_query"))

    def test_laya_triage_extracts_actual_employee_name_when_explicit(self):
        laya = LayaService()
        dec = laya.triage_request("ابحث عن موظف اسمه أحمد")
        self.assertEqual(dec.extracted_entities.get("employee_query"), "أحمد")

    # -------------------------------------------------------------------------
    # 2. اختبار «كم عدد الموظفين؟» -> عدّ فعلي عبر count_records
    # -------------------------------------------------------------------------
    @patch.object(SerajLLMService, "_call_openrouter")
    @patch("odoo_agent_tools._get_repository")
    def test_count_employees_actual_count_not_name_search(self, mock_get_repo, mock_llm_call):
        # محاكاة Odoo Repository
        mock_repo = MagicMock()
        mock_repo.db = "test_db"
        mock_repo.uid = 1
        mock_repo.api_key = "key"
        mock_repo._models.execute_kw.return_value = 15  # 15 موظفاً
        mock_get_repo.return_value = mock_repo

        # محاكاة استجابة OpenRouter: أولاً طلب الأداة count_records، ثم صياغة الجواب
        mock_llm_call.side_effect = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_count_1",
                        "type": "function",
                        "function": {
                            "name": "count_records",
                            "arguments": json.dumps({"model": "hr.employee"}),
                        },
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "يبلغ إجمالي عدد الموظفين في النظام حالياً 15 موظفاً نشطاً.",
            },
        ]

        resp = self.seraj.chat_turn("كم عدد الموظفين؟", chat_id=self.chat_id)
        
        self.assertIn("15", resp)
        self.assertNotIn("لم يتم العثور على أي موظف", resp)
        # التحقق من أن execute_kw استُدعي مع search_count لموديل hr.employee
        mock_repo._models.execute_kw.assert_called_with(
            "test_db", 1, "key", "hr.employee", "search_count", [[]], {}
        )

    # -------------------------------------------------------------------------
    # 3. اختبار «والمؤرشفين؟» -> استخدام سياق الموديل السابق وقراءة غير النشطين
    # -------------------------------------------------------------------------
    @patch.object(SerajLLMService, "_call_openrouter")
    @patch("odoo_agent_tools._get_repository")
    def test_follow_up_archived_employees_uses_context(self, mock_get_repo, mock_llm_call):
        mock_repo = MagicMock()
        mock_repo.db = "test_db"
        mock_repo.uid = 1
        mock_repo.api_key = "key"
        mock_repo._models.execute_kw.return_value = 3  # 3 موظفين مؤرشفين
        mock_get_repo.return_value = mock_repo

        session = self.session_mgr.get_session(self.chat_id)
        session.add_message("user", "كم عدد الموظفين؟")
        session.add_message("assistant", "يوجد 15 موظفاً نشطاً.")

        # النموذج يفهم السؤال المتابع ويطلب المؤرشفين
        mock_llm_call.side_effect = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_count_archived",
                        "type": "function",
                        "function": {
                            "name": "count_records",
                            "arguments": json.dumps({
                                "model": "hr.employee",
                                "include_archived": True,
                                "domain": [["active", "=", False]],
                            }),
                        },
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "عدد الموظفين المؤرشفين (غير النشطين) هو 3 موظفين.",
            },
        ]

        resp = self.seraj.chat_turn("والمؤرشفين؟", chat_id=self.chat_id)
        
        self.assertIn("3", resp)
        # التحقق من تمرير active_test: False في السياق
        call_kwargs = mock_repo._models.execute_kw.call_args[0][6]
        self.assertEqual(call_kwargs.get("context", {}).get("active_test"), False)

    # -------------------------------------------------------------------------
    # 4. اختبار «ما الشركات المتاحة لي؟» -> استعلام فعلي عبر list_companies
    # -------------------------------------------------------------------------
    @patch.object(SerajLLMService, "_call_openrouter")
    @patch("odoo_agent_tools._get_repository")
    def test_list_companies_actual_data(self, mock_get_repo, mock_llm_call):
        mock_repo = MagicMock()
        mock_repo.get_accessible_companies.return_value = [
            {"id": 15, "name": "شركة النخبة الذكية للتقنية"},
            {"id": 16, "name": "شركة توركين للتجزئة"},
        ]
        mock_get_repo.return_value = mock_repo

        mock_llm_call.side_effect = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_companies_1",
                        "type": "function",
                        "function": {
                            "name": "list_companies",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "الشركات المصرح بها لحسابك حالياً هي:\n1. شركة النخبة الذكية للتقنية (معرف 15)\n2. شركة توركين للتجزئة (معرف 16)",
            },
        ]

        resp = self.seraj.chat_turn("ما الشركات المتاحة لي؟", chat_id=self.chat_id)
        
        self.assertIn("شركة النخبة الذكية", resp)
        self.assertIn("شركة توركين", resp)
        mock_repo.get_accessible_companies.assert_called_once()

    # -------------------------------------------------------------------------
    # 5. اختبار «ابحث عن موظف اسمه أحمد» -> بحث بالاسم عبر search_records
    # -------------------------------------------------------------------------
    @patch.object(SerajLLMService, "_call_openrouter")
    @patch("odoo_agent_tools._get_repository")
    def test_search_employee_by_name(self, mock_get_repo, mock_llm_call):
        mock_repo = MagicMock()
        mock_repo.db = "test_db"
        mock_repo.uid = 1
        mock_repo.api_key = "key"
        mock_repo._models.execute_kw.return_value = [
            {"id": 101, "name": "أحمد محمود", "work_email": "ahmed@example.com", "job_title": "مهندس نظم"}
        ]
        mock_get_repo.return_value = mock_repo

        mock_llm_call.side_effect = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_search_1",
                        "type": "function",
                        "function": {
                            "name": "search_records",
                            "arguments": json.dumps({
                                "model": "hr.employee",
                                "domain": [["name", "ilike", "أحمد"]],
                            }),
                        },
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "تم العثور على الموظف «أحمد محمود» (معرف 101)، يعمل بمسمى مهندس نظم.",
            },
        ]

        resp = self.seraj.chat_turn("ابحث عن موظف اسمه أحمد", chat_id=self.chat_id)
        
        self.assertIn("أحمد محمود", resp)
        self.assertIn("101", resp)

    # -------------------------------------------------------------------------
    # 6. اختبار فض الالتباس لسياق الجلسة: «الشركة الثانية»
    # -------------------------------------------------------------------------
    def test_resolve_company_clarification(self):
        session = self.session_mgr.get_session(self.chat_id)
        session.pending_clarification = {
            "type": "select_company",
            "original_query": "كم عدد الموظفين؟",
            "companies": [
                {"id": 1, "name": "My Company"},
                {"id": 15, "name": "شركة النخبة الذكية للتقنية"},
                {"id": 16, "name": "شركة توركين للتجزئة"},
            ],
        }

        resolved, orig = self.session_mgr.resolve_pending_clarification(session, "الشركة الثانية")
        
        self.assertTrue(resolved)
        self.assertEqual(orig, "كم عدد الموظفين؟")
        self.assertEqual(session.company_id, 15)
        self.assertEqual(session.company_name, "شركة النخبة الذكية للتقنية")
        self.assertIsNone(session.pending_clarification)

    # -------------------------------------------------------------------------
    # 7. اختبار رفض طلبات الإنشاء والحذف (Write/Delete Rejected)
    # -------------------------------------------------------------------------
    def test_reject_mutation_requests(self):
        # تغيير السياسة: «احذف» الغامض الآن يطلب توضيحًا (أرشفة أم حذف نهائي) بدلاً من الحظر المباشر
        res_del = self.seraj.chat_turn("احذف الموظف رقم 5", chat_id=self.chat_id)
        self.assertIn("توضيح", res_del)  # يطلب توضيح نوع الإجراء
        session = self.session_mgr.get_session(self.chat_id)
        self.assertIsNone(session.pending_action)  # لا تنفيذ قبل التوضيح
        self.session_mgr.reset_session(self.chat_id)  # تنظيف قبل اختبار الإضافة

        res_add = self.seraj.chat_turn("أضف موظف جديد باسم خالد", chat_id=self.chat_id)
        self.assertIn("في انتظار الاعتماد", res_add)
        self.assertIn("خالد", res_add)

    # -------------------------------------------------------------------------
    # 8. اختبار منع execute_kw المفتوح وأدوات التعديل أمنياً
    # -------------------------------------------------------------------------
    def test_security_barrier_blocks_forbidden_tools_and_models(self):
        with self.assertRaises(OdooToolSecurityError):
            execute_tool_call("unlink_records", {"model": "hr.employee", "ids": [1]})

        with self.assertRaises(OdooToolSecurityError):
            execute_tool_call("create_record", {"model": "hr.employee", "values": {}})

        with self.assertRaises(OdooToolSecurityError):
            execute_tool_call("count_records", {"model": "ir.config_parameter; DROP TABLE users;"})

    # -------------------------------------------------------------------------
    # 9. اختبار معالجة أخطاء الاتصال والصلاحيات بوضوح دون تضليل
    # -------------------------------------------------------------------------
    @patch.object(SerajLLMService, "_call_openrouter")
    @patch("odoo_agent_tools._get_repository")
    def test_connection_error_is_reported_clearly_not_as_missing_employees(self, mock_get_repo, mock_llm_call):
        mock_repo = MagicMock()
        mock_repo._models.execute_kw.side_effect = Exception("Connection refused by Odoo XML-RPC")
        mock_get_repo.return_value = mock_repo

        mock_llm_call.side_effect = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_err_1",
                        "type": "function",
                        "function": {
                            "name": "count_records",
                            "arguments": json.dumps({"model": "hr.employee"}),
                        },
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "⚠️ تعذر إتمام الاستعلام بسبب خطأ في الاتصال بخادم Odoo: Connection refused.",
            },
        ]

        resp = self.seraj.chat_turn("كم عدد الموظفين؟", chat_id=self.chat_id)
        
        self.assertIn("خطأ في الاتصال", resp)
        self.assertNotIn("لم نجد أي موظف", resp)

    # -------------------------------------------------------------------------
    # 10. اختبار إمكانية تحديد اتصال مختلف دون تعديل المنطق
    # -------------------------------------------------------------------------
    @patch("odoo_agent_tools._get_repository")
    def test_can_specify_connection_id(self, mock_get_repo):
        mock_repo = MagicMock()
        mock_repo.db = "custom_db"
        mock_repo.url = "https://custom-odoo.local"
        mock_repo.username = "custom_user"
        mock_repo.uid = 99
        mock_get_repo.return_value = mock_repo

        conns = list_connections()
        self.assertEqual(len(conns), 1)
        self.assertEqual(conns[0]["connection_id"], "default")

    # -------------------------------------------------------------------------
    # 11. اختبار استعانة سراج بلايا كتفسير استشاري مساعد مع الحفاظ على دور المنسق
    # -------------------------------------------------------------------------
    @patch.object(SerajLLMService, "_call_openrouter")
    def test_seraj_consults_laya_as_assistive_triage(self, mock_llm_call):
        mock_llm_call.return_value = {
            "role": "assistant",
            "content": "استحقاق الإجازة السنوية محدد بـ 21 يوماً وفق المادة 109 من نظام العمل.",
        }

        with patch.object(self.seraj, "consult_laya", wraps=self.seraj.consult_laya) as mock_consult:
            resp = self.seraj.chat_turn("ما هي شروط رصيد الإجازات السنوية؟", chat_id=self.chat_id)
            mock_consult.assert_called_once()
            # التحقق من أن الاستدعاء تم للنص الفعلي
            self.assertIn("شروط رصيد الإجازات", mock_consult.call_args[0][0])
            self.assertIn("المادة 109", resp)

    # -------------------------------------------------------------------------
    # 12. اختبار إلزام عمليات الكتابة بضوابط مدقق وحارس وكاتب حتى مع ثقة لايا
    # -------------------------------------------------------------------------
    def test_mutation_strictly_requires_governance_controls(self):
        # محاكاة قرار لايا بثقة 100% لطلب تعديل
        laya_dec = {
            "domain": "contracts",
            "domain_ar": "عقود العمل",
            "action_type": "update",
            "action_type_ar": "تعديل بيانات",
            "confidence": 1.0,
            "requires_four_eyes": True,
            "is_deletion_blocked": False,
        }
        resp = self.seraj.chat_turn(
            "عدل راتب الموظف رقم 10 إلى 15000",
            chat_id=self.chat_id,
            laya_decision=laya_dec,
        )
        self.assertIn("تنسيق طلب التعديل (سراج)", resp)
        self.assertIn("مدقق", resp)
        self.assertIn("حارس", resp)
        self.assertIn("كاتب", resp)

    # -------------------------------------------------------------------------
    # 13. اختبار استبدال الرد المضلل بالخطأ التقني الفعلي عند فشل Odoo
    # -------------------------------------------------------------------------
    @patch.object(SerajLLMService, "_call_openrouter")
    @patch("odoo_agent_tools._get_repository")
    def test_safeguard_prevents_false_employee_not_found_on_connection_error(self, mock_get_repo, mock_llm_call):
        mock_repo = MagicMock()
        mock_repo._models.execute_kw.side_effect = Exception("SSL Handshake Timeout")
        mock_get_repo.return_value = mock_repo

        # نموذج LLM أخطأ وحاول أن يرجع «لم يتم العثور على أي موظف» رغم فشل الاتصال
        mock_llm_call.side_effect = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_err_safe",
                        "type": "function",
                        "function": {
                            "name": "count_records",
                            "arguments": json.dumps({"model": "hr.employee"}),
                        },
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "لم يتم العثور على أي موظف في النظام.",
            },
        ]

        resp = self.seraj.chat_turn("كم عدد الموظفين؟", chat_id=self.chat_id)
        # صمام الأمان يجب أن يكتشف الخطأ ويعرض العطل الحقيقي بدلاً من التضليل
        self.assertIn("تعذر إتمام الاستعلام بسبب", resp)
        self.assertIn("خطأ في الاتصال", resp)
        self.assertNotIn("لم يتم العثور على أي موظف", resp)


if __name__ == "__main__":
    unittest.main()
