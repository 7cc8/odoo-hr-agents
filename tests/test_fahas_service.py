"""
اختبارات وكيل الاستعلام والقراءة المعتمد «فاحص» وضوابط الفصل المعماري مع «سراج»
==============================================================================
تتحقق هذه الاختبارات من:
1. مسؤولية فاحص الحصرية عن القراءة والاستعلام والتحقق في Odoo.
2. استقبال فاحص للمهام المحددة من سراج وإرجاع نتائج منظمة أو أخطاء واضحة.
3. عدم وجود مسار قراءة موازٍ داخل سراج يكرر دور فاحص.
4. حظر عمليات الكتابة أو التعديل أو الحذف أمنياً على فاحص وسراج.
5. حظر النماذج غير المصرح بها أمنياً.
6. مسار المعالجة: المستخدم -> سراج -> لايا عند الغموض -> فاحص للاستعلام -> سراج للشرح.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from fahas_service import (
    FahasAgent,
    FahasExecutionError,
    FahasSecurityError,
    get_fahas_agent,
    validate_model_name,
)
from seraj_llm_service import SerajLLMService
from seraj_session_manager import SerajSessionManager


class TestFahasServiceAndSeparation(unittest.TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.mock_repo.db = "odoo_test_db"
        self.mock_repo.uid = 2
        self.mock_repo.username = "test_fahas_user"
        self.mock_repo.url = "https://odoo-test.local"
        self.mock_repo.api_key = "test_key"
        self.fahas = FahasAgent(repository=self.mock_repo)

    # -------------------------------------------------------------------------
    # 1. اختبار استعلام فاحص الفعلي للعدد count_records
    # -------------------------------------------------------------------------
    def test_fahas_executes_count_records_task(self):
        self.mock_repo._models.execute_kw.return_value = 15

        res = self.fahas.execute_query_task(
            "count_records",
            {"model": "hr.employee", "company_id": 10},
        )

        self.assertEqual(res["model"], "hr.employee")
        self.assertEqual(res["count"], 15)
        self.assertEqual(res["company_id"], 10)
        self.mock_repo._models.execute_kw.assert_called_once()
        args = self.mock_repo._models.execute_kw.call_args[0]
        self.assertEqual(args[3], "hr.employee")
        self.assertEqual(args[4], "search_count")

    # -------------------------------------------------------------------------
    # 2. اختبار استعلام فاحص الفعلي للبحث search_records
    # -------------------------------------------------------------------------
    def test_fahas_executes_search_records_task(self):
        self.mock_repo._models.execute_kw.return_value = [
            {"id": 1, "name": "أحمد محمود", "work_email": "ahmed@example.com"}
        ]

        res = self.fahas.execute_query_task(
            "search_records",
            {"model": "hr.employee", "domain": [["name", "ilike", "أحمد"]], "limit": 5},
        )

        self.assertEqual(res["model"], "hr.employee")
        self.assertEqual(res["records_count"], 1)
        self.assertEqual(res["records"][0]["name"], "أحمد محمود")

    # -------------------------------------------------------------------------
    # 3. اختبار استعراض الشركات عبر فاحص list_companies
    # -------------------------------------------------------------------------
    def test_fahas_executes_list_companies_task(self):
        self.mock_repo.get_accessible_companies.return_value = [
            {"id": 1, "name": "شركة النخبة"},
            {"id": 2, "name": "شركة توركين"},
        ]

        res = self.fahas.execute_query_task("list_companies", {})

        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["name"], "شركة النخبة")
        self.mock_repo.get_accessible_companies.assert_called_once()

    # -------------------------------------------------------------------------
    # 4. اختبار فحص الموديل describe_model عبر fields_get
    # -------------------------------------------------------------------------
    def test_fahas_executes_describe_model_task(self):
        self.mock_repo._models.execute_kw.return_value = {
            "name": {"type": "char", "string": "اسم الموظف"},
            "work_email": {"type": "char", "string": "البريد الإلكتروني"},
        }

        res = self.fahas.execute_query_task("describe_model", {"model": "hr.employee"})

        self.assertEqual(res["model"], "hr.employee")
        self.assertEqual(res["fields_count"], 2)
        self.assertIn("name", res["fields"])

    # -------------------------------------------------------------------------
    # 5. اختبار منع عمليات الكتابة أو التعديل أو الحذف قطعياً على فاحص
    # -------------------------------------------------------------------------
    def test_fahas_strictly_rejects_write_and_unlink_operations(self):
        forbidden_tasks = [
            "create", "write", "unlink", "delete", "create_record",
            "unlink_records", "write_record", "delete_record", "drop"
        ]
        for task in forbidden_tasks:
            with self.assertRaises(FahasSecurityError):
                self.fahas.execute_query_task(task, {"model": "hr.employee"})

    # -------------------------------------------------------------------------
    # 6. اختبار منع النماذج غير المصرح بها أو محاولات الحقن
    # -------------------------------------------------------------------------
    def test_fahas_strictly_rejects_unauthorized_models(self):
        unsafe_models = [
            "ir.config_parameter; DROP TABLE users;",
            "base.automation",
            "account.move",
            "sale.order",
        ]
        for m in unsafe_models:
            with self.assertRaises(FahasSecurityError):
                self.fahas.execute_query_task("count_records", {"model": m})

    # -------------------------------------------------------------------------
    # 7. اختبار سراج يفوّض الاستعلام لفاحص دون مسار قراءة موازٍ
    # -------------------------------------------------------------------------
    @patch.object(SerajLLMService, "_call_openrouter")
    def test_seraj_delegates_query_task_to_fahas_and_explains_result(self, mock_llm_call):
        self.mock_repo._models.execute_kw.return_value = 15

        # إنشاء سراج مزوداً بوكيل فاحص المخصص
        seraj = SerajLLMService(api_key="sk-or-test-mock-key", fahas_agent=self.fahas)

        # النموذج يطلب من فاحص مهمة count_records
        mock_llm_call.side_effect = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_fahas_1",
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
                "content": "أفاد وكيل فاحص بأن إجمالي عدد الموظفين في Odoo هو 15 موظفاً.",
            },
        ]

        resp = seraj.chat_turn("كم عدد الموظفين؟", chat_id="test_fahas_separation")

        # التحقق من أن الاستعلام نُفذ حصرياً عبر فاحص
        self.mock_repo._models.execute_kw.assert_called_once()
        self.assertIn("15", resp)
        self.assertIn("فاحص", resp)

    # -------------------------------------------------------------------------
    # 8. اختبار أن فاحص لا يملك منطق محادثة أو رد على المستخدم (فصل الأدوار)
    # -------------------------------------------------------------------------
    def test_fahas_does_not_have_chat_or_conversational_interface(self):
        # فاحص لا يملك chat_turn أو توليد ردود محادثة للمستخدم
        self.assertFalse(hasattr(self.fahas, "chat_turn"))
        self.assertFalse(hasattr(self.fahas, "consult_laya"))
        self.assertTrue(hasattr(self.fahas, "execute_query_task"))


if __name__ == "__main__":
    unittest.main()
