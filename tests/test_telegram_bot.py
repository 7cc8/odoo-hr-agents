import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import telegram_bot
from openpyxl import Workbook


HEADERS = ["name", "work_email", "work_phone", "mobile_phone", "job_title", "company", "department", "job", "hiring_date"]


def create_sample_xlsx(path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Employees"
    ws.append(HEADERS)
    ws.append(["سارة الغامدي", "sara@example.com", "", "0501112233", "مهندس", "شركة النخبة الذكية للتقنية", "تقنية المعلومات", "مهندس برمجيات", "2026-10-06"])
    wb.save(path)


class TelegramBotTests(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        telegram_bot.PENDING_CONFIRMATIONS.clear()

    def test_authorization_whitelist(self):
        with patch.dict("os.environ", {"TELEGRAM_ALLOWED_USERS": "111,222,333"}):
            self.assertTrue(telegram_bot.is_user_authorized("111", "999"))
            self.assertTrue(telegram_bot.is_user_authorized("555", "222"))
            self.assertFalse(telegram_bot.is_user_authorized("444", "888"))

    def test_authorization_empty_whitelist_blocks_all(self):
        with patch.dict("os.environ", {"TELEGRAM_ALLOWED_USERS": "", "TELEGRAM_CHAT_ID": ""}):
            self.assertFalse(telegram_bot.is_user_authorized("111", "999"))

    def test_handle_excel_document_rejects_non_xlsx(self):
        mock_bot = MagicMock()
        telegram_bot.handle_excel_document(
            mock_bot, chat_id=123, user_id=456, user_name="خالد",
            doc={"file_name": "resume.pdf", "file_id": "fid_pdf"}, message_id=10
        )
        mock_bot.send_message.assert_called_once()
        args = mock_bot.send_message.call_args[0]
        self.assertIn("يجب أن يكون الملف بصيغة Excel", args[1])

    @patch("dry_run_report.OdooReadonlyRepository")
    def test_handle_excel_document_runs_dry_run_and_sends_button(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.get_session_info.return_value = {
            "odoo_url": "https://example.odoo.com",
            "odoo_db": "test_db",
            "uid": 1,
            "server_version": "19.0",
        }
        mock_repo.get_live_reference_snapshot.return_value = {
            "companies": [{"id": 15, "name": "شركة النخبة الذكية للتقنية", "active": True}],
            "departments": [{"id": 8, "name": "تقنية المعلومات", "complete_name": "تقنية المعلومات", "company_id": [15, "شركة النخبة الذكية للتقنية"], "active": True}],
            "jobs": [{"id": 22, "name": "مهندس برمجيات", "company_id": [15, "شركة النخبة الذكية للتقنية"], "active": True}],
        }
        mock_repo.search_employees_by_keys.return_value = []
        mock_repo_cls.return_value = mock_repo

        xlsx_path = self.tmpdir / "test.xlsx"
        create_sample_xlsx(xlsx_path)

        mock_bot = MagicMock()
        mock_bot.download_file.side_effect = lambda fid, dst: dst.write_bytes(xlsx_path.read_bytes()) and True

        telegram_bot.handle_excel_document(
            mock_bot, chat_id=123, user_id=456, user_name="خالد",
            doc={"file_name": "test.xlsx", "file_id": "fid_xlsx"}, message_id=10
        )

        calls = mock_bot.send_message.call_args_list
        self.assertTrue(len(calls) >= 2)
        summary_call = calls[-1]
        summary_text = summary_call[0][1]
        reply_markup = summary_call[1].get("reply_markup") or {}

        self.assertIn("نتائج الفحص والتدقيق الاستباقي (Pre-Audit)", summary_text)
        self.assertIn("جاهز للاعتماد", summary_text)
        self.assertIn("inline_keyboard", reply_markup)
        self.assertIn("اعتمد وأنشئ", reply_markup["inline_keyboard"][0][0]["text"])

    def test_handle_approval_callback_cancel(self):
        mock_bot = MagicMock()
        telegram_bot.handle_approval_callback(
            mock_bot, chat_id=123, user_id=456, user_name="خالد",
            message_id=20, callback_query_id="cq_1", data="cancel:run_123"
        )
        mock_bot.answer_callback_query.assert_called_with("cq_1", "تراجعتَ عن العملية.")
        mock_bot.edit_message_text.assert_called_once()
        self.assertIn("تراجعتَ", mock_bot.edit_message_text.call_args[0][2])

    # Section 5.1: Button click requires written confirmation "تأكيد"
    def test_handle_approval_callback_requests_written_confirmation(self):
        mock_bot = MagicMock()
        telegram_bot.handle_approval_callback(
            mock_bot, chat_id=123, user_id=456, user_name="خالد",
            message_id=20, callback_query_id="cq_2", data="approve:run_abc"
        )
        mock_bot.answer_callback_query.assert_called_with("cq_2", "يلزم تأكيد كتابي للمتابعة")
        mock_bot.edit_message_text.assert_called_once()
        self.assertIn("تأكيد", mock_bot.edit_message_text.call_args[0][2])
        self.assertIn("123", telegram_bot.PENDING_CONFIRMATIONS)
        self.assertEqual(telegram_bot.PENDING_CONFIRMATIONS["123"]["run_id"], "run_abc")

    # Section 5.2: Bot calls backend API rather than writer directly
    @patch("urllib.request.urlopen")
    def test_execute_via_backend_api_calls_http(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "status": "success",
            "created_count": 1,
            "created_items": [{"name": "سارة", "odoo_id": 101}],
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        mock_bot = MagicMock()
        telegram_bot.execute_via_backend_api(
            mock_bot, chat_id=123, user_id=456, user_name="خالد",
            run_id="run_abc", reply_to_msg_id=50
        )

        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        self.assertIn("/api/approve-and-execute", req.full_url)
        self.assertEqual(req.headers.get("X-api-key"), telegram_bot.WRITE_API_TOKEN)
    def test_main_menu_keyboard_has_wizard_button(self):
        kb = telegram_bot.get_main_menu_keyboard()
        buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        callbacks = [btn["callback_data"] for btn in buttons]
        self.assertIn("odoo:edit_wizard", callbacks)
        self.assertIn("menu:templates", callbacks)
        self.assertIn("menu:odoo_settings", callbacks)
        self.assertIn("menu:show_companies", callbacks)

    def test_templates_menu_keyboard(self):
        kb = telegram_bot.get_templates_menu_keyboard()
        buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        callbacks = [btn["callback_data"] for btn in buttons]
        self.assertIn("get_tpl:master", callbacks)
        self.assertIn("get_tpl:emp", callbacks)
        self.assertIn("get_tpl:loan", callbacks)
        self.assertIn("menu:main", callbacks)

    @patch("telegram_bot.test_odoo_connection")
    @patch("telegram_bot.save_active_odoo_config")
    def test_config_wizard_full_flow(self, mock_save, mock_test):
        mock_test.return_value = {
            "ok": True,
            "uid": 5,
            "company_count": 2,
            "employee_count": 10,
            "department_count": 4,
        }
        mock_bot = MagicMock()
        chat_id = "test_chat_1"
        user_id = "test_user_1"

        # Initialize wizard
        telegram_bot.ACTIVE_CONFIG_WIZARDS[chat_id] = {"step": "url", "user_id": user_id}

        # Step 1: URL
        handled = telegram_bot.handle_config_wizard_step(mock_bot, chat_id, user_id, "خالد", "https://erp.example.com", 1)
        self.assertTrue(handled)
        self.assertEqual(telegram_bot.ACTIVE_CONFIG_WIZARDS[chat_id]["step"], "db")
        self.assertEqual(telegram_bot.ACTIVE_CONFIG_WIZARDS[chat_id]["url"], "https://erp.example.com")

        # Step 2: DB
        handled = telegram_bot.handle_config_wizard_step(mock_bot, chat_id, user_id, "خالد", "production_db", 2)
        self.assertTrue(handled)
        self.assertEqual(telegram_bot.ACTIVE_CONFIG_WIZARDS[chat_id]["step"], "user")
        self.assertEqual(telegram_bot.ACTIVE_CONFIG_WIZARDS[chat_id]["db"], "production_db")

        # Step 3: User
        handled = telegram_bot.handle_config_wizard_step(mock_bot, chat_id, user_id, "خالد", "admin@example.com", 3)
        self.assertTrue(handled)
        self.assertEqual(telegram_bot.ACTIVE_CONFIG_WIZARDS[chat_id]["step"], "key")
        self.assertEqual(telegram_bot.ACTIVE_CONFIG_WIZARDS[chat_id]["user"], "admin@example.com")

        # Step 4: Key
        handled = telegram_bot.handle_config_wizard_step(mock_bot, chat_id, user_id, "خالد", "secret_api_key_123", 4)
        self.assertTrue(handled)
        self.assertNotIn(chat_id, telegram_bot.ACTIVE_CONFIG_WIZARDS)

        mock_test.assert_called_once_with("https://erp.example.com", "production_db", "admin@example.com", "secret_api_key_123")
        mock_save.assert_called_once_with("https://erp.example.com", "production_db", "admin@example.com", "secret_api_key_123")
        
        # Verify success card sent
        calls = mock_bot.send_message.call_args_list
        last_text = calls[-1][0][1]
        self.assertIn("اتصلتُ بنجاح", last_text)
        self.assertIn("الموظفون المسجلون", last_text)

    def test_config_wizard_invalid_url_and_cancellation(self):
        mock_bot = MagicMock()
        chat_id = "test_chat_2"
        user_id = "test_user_2"

        telegram_bot.ACTIVE_CONFIG_WIZARDS[chat_id] = {"step": "url", "user_id": user_id}

        # Send invalid URL without http/https
        handled = telegram_bot.handle_config_wizard_step(mock_bot, chat_id, user_id, "خالد", "not_a_valid_url", 1)
        self.assertTrue(handled)
        self.assertEqual(telegram_bot.ACTIVE_CONFIG_WIZARDS[chat_id]["step"], "url")
        self.assertIn("تأكد أن الرابط يبدأ", mock_bot.send_message.call_args[0][1])

        # Cancel wizard
        handled = telegram_bot.handle_config_wizard_step(mock_bot, chat_id, user_id, "خالد", "إلغاء", 2)
        self.assertTrue(handled)
        self.assertNotIn(chat_id, telegram_bot.ACTIVE_CONFIG_WIZARDS)

    def test_main_menu_keyboard_has_leaves_button(self):
        kb = telegram_bot.get_main_menu_keyboard()
        buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        leave_btn = next((b for b in buttons if b["callback_data"] == "menu:leaves"), None)
        self.assertIsNotNone(leave_btn)
        self.assertIn("الإجازات", leave_btn["text"])

    def test_show_leaves_menu(self):
        mock_bot = MagicMock()
        telegram_bot.show_leaves_menu(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("إدارة الإجازات ونظام العمل السعودي", text)
        self.assertIn("المادة 109", text)

    def test_show_leaves_law_guide(self):
        mock_bot = MagicMock()
        telegram_bot.show_leaves_law_guide(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("دليل إجازات نظام العمل السعودي", text)
        self.assertIn("المادة 113", text)
        self.assertIn("تعديل 1446هـ", text)
        self.assertIn("12 أسبوعاً بأجر كامل", text)

    @patch("telegram_bot.get_leave_service_for_bot")
    def test_leave_wizard_dates_step_dry_run(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        
        mock_dry_res = MagicMock()
        mock_dry_res.is_valid = True
        mock_dry_res.employee_name = "سعد"
        mock_dry_res.employee_id = 100
        mock_dry_res.leave_type_name = "Paid Time Off"
        mock_dry_res.request_date_from = "2026-10-15"
        mock_dry_res.request_date_to = "2026-10-18"
        mock_dry_res.number_of_days = 4.0
        mock_dry_res.statutory_article = "المادة 109"
        mock_dry_res.statutory_explanation_ar = "رصيد كاف"
        mock_dry_res.balance_before = 20.0
        mock_dry_res.balance_after = 16.0
        mock_dry_res.warnings = []
        mock_dry_res.approval_token = "LEAVE-ABC12345"
        mock_service.dry_run_leave_request.return_value = mock_dry_res

        mock_bot = MagicMock()
        chat_id = "test_chat_leave"
        telegram_bot.ACTIVE_LEAVE_WIZARDS[chat_id] = {
            "mode": "request",
            "step": "dates",
            "employee_id": 100,
            "holiday_status_id": 1
        }

        handled = telegram_bot.handle_leave_wizard_step(
            mock_bot, chat_id, 999, "سعد", "2026-10-15 2026-10-18", 1
        )
        self.assertTrue(handled)
        self.assertNotIn(chat_id, telegram_bot.ACTIVE_LEAVE_WIZARDS)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("LEAVE-ABC12345", text)
        self.assertIn("المادة 109", text)

    def test_main_menu_keyboard_has_attendance_button(self):
        kb = telegram_bot.get_main_menu_keyboard()
        buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        att_btn = next((b for b in buttons if b["callback_data"] == "menu:attendance"), None)
        self.assertIsNotNone(att_btn)
        self.assertIn("الحضور والعمل الإضافي", att_btn["text"])

    def test_show_attendance_menu(self):
        mock_bot = MagicMock()
        telegram_bot.show_attendance_menu(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("إدارة الحضور والعمل الإضافي ونظام العمل السعودي", text)
        self.assertIn("المواد 98 و 101 و 107", text)

    def test_show_attendance_law_guide(self):
        mock_bot = MagicMock()
        telegram_bot.show_attendance_law_guide(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("دليل ساعات العمل والراحة والعمل الإضافي", text)
        self.assertIn("المادة 98", text)
        self.assertIn("المادة 101", text)
        self.assertIn("المادة 107", text)
        self.assertIn("8 ساعات يومياً", text)

    @patch("telegram_bot.get_attendance_service_for_bot")
    def test_show_employee_attendance_card(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_summary = MagicMock()
        mock_summary.employee_name = "ياسر"
        mock_summary.employee_id = 105
        mock_summary.department_name = "المبيعات"
        mock_summary.total_days_worked = 22
        mock_summary.total_worked_hours = 180.0
        mock_summary.total_standard_hours = 176.0
        mock_summary.total_overtime_hours = 4.0
        mock_summary.overtime_compensation_sar = 250.0
        mock_summary.attendances = []
        mock_service.get_attendance_summary.return_value = mock_summary

        mock_bot = MagicMock()
        telegram_bot.show_employee_attendance_card(mock_bot, chat_id=123, employee_id=105)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("ياسر", text)
        self.assertIn("المبيعات", text)
        self.assertIn("180.00 ساعة", text)
        self.assertIn("250.00 ر.س", text)

    def test_handle_attendance_wizard_step_checkin_requires_written_confirm(self):
        mock_bot = MagicMock()
        chat_id = "test_chat_att"
        telegram_bot.ACTIVE_ATTENDANCE_WIZARDS[chat_id] = {
            "mode": "checkin_input",
            "user_id": "u123"
        }

        handled = telegram_bot.handle_attendance_wizard_step(
            mock_bot, chat_id, "u123", "فيصل", "105", 1
        )
        self.assertTrue(handled)
        self.assertNotIn(chat_id, telegram_bot.ACTIVE_ATTENDANCE_WIZARDS)
        self.assertIn(chat_id, telegram_bot.PENDING_ATTENDANCE_CONFIRMATIONS)
        self.assertEqual(telegram_bot.PENDING_ATTENDANCE_CONFIRMATIONS[chat_id]["action"], "check_in")
        self.assertEqual(telegram_bot.PENDING_ATTENDANCE_CONFIRMATIONS[chat_id]["employee_id"], 105)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("تأكيد", text)
        self.assertIn("مبدأ التحقق المزدوج", text)

    @patch("telegram_bot.get_attendance_service_for_bot")
    def test_handle_attendance_wizard_step_overtime_dry_run(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service

        mock_dry_res = MagicMock()
        mock_dry_res.is_valid = True
        mock_dry_res.employee_name = "فيصل"
        mock_dry_res.employee_id = 105
        mock_dry_res.date = "2026-10-06"
        mock_dry_res.check_in = "2026-10-06 08:00"
        mock_dry_res.check_out = "2026-10-06 18:30"
        mock_dry_res.worked_hours = 10.5
        mock_dry_res.standard_hours = 8.0
        mock_dry_res.overtime_hours = 2.5
        mock_dry_res.overtime_pay_sar = 156.25
        mock_dry_res.statutory_article = "المادتان 98 و 107"
        mock_dry_res.statutory_explanation_ar = "ساعات عمل إضافية 2.5 ساعة"
        mock_dry_res.warnings = ["المادة 101: فحص فترات الراحة"]
        mock_dry_res.approval_token = "ATTEND-99887766"
        mock_service.dry_run_attendance_record.return_value = mock_dry_res

        mock_bot = MagicMock()
        chat_id = "test_chat_att_ot"
        telegram_bot.ACTIVE_ATTENDANCE_WIZARDS[chat_id] = {
            "mode": "overtime",
            "step": "times",
            "employee_id": 105,
            "user_id": "u123"
        }

        handled = telegram_bot.handle_attendance_wizard_step(
            mock_bot, chat_id, "u123", "فيصل", "2026-10-06 08:00 18:30", 1
        )
        self.assertTrue(handled)
        self.assertNotIn(chat_id, telegram_bot.ACTIVE_ATTENDANCE_WIZARDS)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("ATTEND-99887766", text)
        self.assertIn("المادتان 98 و 107", text)
        self.assertIn("156.25 ر.س", text)
        self.assertIn("المادة 101: فحص فترات الراحة", text)

    def test_main_menu_keyboard_has_disciplinary_button(self):
        kb = telegram_bot.get_main_menu_keyboard()
        buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        disc_btn = next((b for b in buttons if b["callback_data"] == "menu:disciplinary"), None)
        self.assertIsNotNone(disc_btn)
        self.assertIn("الجزاءات", disc_btn["text"])

    def test_show_disciplinary_menu(self):
        mock_bot = MagicMock()
        telegram_bot.show_disciplinary_menu(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("إدارة الجزاءات والانضباط ونظام العمل السعودي", text)
        self.assertIn("المواد 70 و 71 و 72 و 80", text)

    def test_show_disciplinary_law_guide(self):
        mock_bot = MagicMock()
        telegram_bot.show_disciplinary_law_guide(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("دليل لائحة الجزاءات ونظام العمل السعودي", text)
        self.assertIn("المادة 70", text)
        self.assertIn("المادة 71", text)
        self.assertIn("المادة 80", text)

    @patch("telegram_bot.get_disciplinary_service_for_bot")
    def test_show_employee_disciplinary_card(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_summary = MagicMock()
        mock_summary.employee_name = "طلال الشمري"
        mock_summary.employee_id = 110
        mock_summary.department_name = "الموارد البشرية"
        mock_summary.daily_wage = 350.0
        mock_summary.total_actions_count = 1
        mock_summary.current_month_deductions_days = 1.0
        mock_summary.remaining_month_deduction_allowance_days = 4.0
        mock_summary.active_occurrence_level = "first"
        mock_summary.recent_actions = []
        mock_service.get_employee_disciplinary_summary.return_value = mock_summary

        mock_bot = MagicMock()
        telegram_bot.show_employee_disciplinary_card(mock_bot, chat_id=123, employee_id=110)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("طلال الشمري", text)
        self.assertIn("الموارد البشرية", text)
        self.assertIn("1.0 من 5 أيام", text)

    @patch("telegram_bot.get_disciplinary_service_for_bot")
    def test_handle_disciplinary_wizard_step_dry_run(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service

        mock_dry_res = MagicMock()
        mock_dry_res.is_valid = True
        mock_dry_res.employee_name = "طلال"
        mock_dry_res.employee_id = 110
        mock_dry_res.department_name = "الموارد البشرية"
        mock_dry_res.discipline_date = "2026-10-06"
        mock_dry_res.discipline_reason = "تأخر متكرر"
        mock_dry_res.number_of_days = 1.0
        mock_dry_res.amount_sar = 350.0
        mock_dry_res.occurrence_explanation_ar = "المخالفة الأولى"
        mock_dry_res.statutory_article = "المواد 70 و 71"
        mock_dry_res.statutory_explanation_ar = "سقف الخصم نظامي"
        mock_dry_res.warnings = []
        mock_dry_res.approval_token = "DISC-99881122"
        mock_service.dry_run_disciplinary_action.return_value = mock_dry_res

        mock_bot = MagicMock()
        chat_id = "test_chat_disc_wiz"
        telegram_bot.ACTIVE_DISCIPLINARY_WIZARDS[chat_id] = {
            "mode": "action",
            "step": "details",
            "employee_id": 110,
            "user_id": "u444"
        }

        handled = telegram_bot.handle_disciplinary_wizard_step(
            mock_bot, chat_id, "u444", "طلال", "2026-10-06 1 تأخر متكرر", 1
        )
        self.assertTrue(handled)
        self.assertNotIn(chat_id, telegram_bot.ACTIVE_DISCIPLINARY_WIZARDS)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("DISC-99881122", text)
        self.assertIn("المواد 70 و 71", text)
        self.assertIn("350.00 ر.س", text)


    def test_main_menu_includes_eos_button(self):
        kb = telegram_bot.get_main_menu_keyboard()
        buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        eos_btn = next((b for b in buttons if b["callback_data"] == "menu:eos"), None)
        self.assertIsNotNone(eos_btn)
        self.assertIn("نهاية الخدمة", eos_btn["text"])

    def test_show_eos_menu(self):
        mock_bot = MagicMock()
        telegram_bot.show_eos_menu(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("تسويات مكافأة نهاية الخدمة ونظام العمل السعودي", text)
        self.assertIn("المادة 37", text)
        self.assertIn("م/77", text)

    def test_show_eos_laws_guide(self):
        mock_bot = MagicMock()
        telegram_bot.show_eos_laws_guide(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("دليل تسويات نهاية الخدمة ونظام العمل السعودي", text)
        self.assertIn("المادة 84", text)
        self.assertIn("المادة 85", text)
        self.assertIn("المادة 87", text)
        self.assertIn("المادة 77", text)

    @patch("telegram_bot.get_eos_service_for_bot")
    def test_show_employee_eos_card(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_summary = MagicMock()
        mock_summary.employee_name = "عبدالعزيز السبيعي"
        mock_summary.employee_id = 115
        mock_summary.department_name = "العمليات"
        mock_summary.is_saudi = True
        mock_summary.nationality_text_ar = "مواطن سعودي"
        mock_summary.hiring_date = "2020-01-01"
        mock_summary.years = 6
        mock_summary.months = 9
        mock_summary.days = 5
        mock_summary.service_years = 6.75
        mock_summary.last_gross_wage = 9000.0
        mock_summary.eos_records_count = 0
        mock_summary.recent_records = []
        mock_service.get_employee_eos_summary.return_value = mock_summary

        mock_bot = MagicMock()
        telegram_bot.show_employee_eos_card(mock_bot, chat_id=123, employee_id=115)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("عبدالعزيز السبيعي", text)
        self.assertIn("مواطن سعودي", text)
        self.assertIn("6 سنة و 9 شهر", text)

    @patch("telegram_bot.get_eos_service_for_bot")
    def test_handle_eos_wizard_step_dry_run(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service

        mock_dry_res = MagicMock()
        mock_dry_res.is_valid = True
        mock_dry_res.employee_name = "عبدالعزيز"
        mock_dry_res.employee_id = 115
        mock_dry_res.nationality_text_ar = "مواطن سعودي"
        mock_dry_res.contract_type = "indefinite"
        mock_dry_res.years = 6
        mock_dry_res.months = 0
        mock_dry_res.days = 0
        mock_dry_res.service_period = 6.0
        mock_dry_res.monthly_wage = 9000.0
        mock_dry_res.daily_wage = 300.0
        mock_dry_res.gratuity_net_amount = 31500.0
        mock_dry_res.gratuity_entitlement_ratio = 1.0
        mock_dry_res.gratuity_explanation_ar = "استحقاق كامل بموجب المادة 84"
        mock_dry_res.article_77_amount = 0.0
        mock_dry_res.unused_leave_days = 0.0
        mock_dry_res.leave_compensation_amount = 0.0
        mock_dry_res.net_settlement_amount = 31500.0
        mock_dry_res.warnings = []
        mock_dry_res.approval_token = "EOS-88776655"
        mock_service.dry_run_eos_settlement.return_value = mock_dry_res

        mock_bot = MagicMock()
        chat_id = "test_chat_eos_wiz"
        telegram_bot.ACTIVE_EOS_WIZARDS[chat_id] = {
            "mode": "calc_details",
            "employee_id": 115,
            "user_id": "u555"
        }

        handled = telegram_bot.handle_eos_wizard_step(
            mock_bot, chat_id, "u555", "عبدالعزيز", "9000 إنهاء 0", 1
        )
        self.assertTrue(handled)
        self.assertNotIn(chat_id, telegram_bot.ACTIVE_EOS_WIZARDS)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("EOS-88776655", text)
        self.assertIn("31,500.00 ر.س", text)
        self.assertIn("مواطن سعودي", text)

    def test_main_menu_keyboard_has_gr_button(self):
        kb = telegram_bot.get_main_menu_keyboard()
        buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        gr_btn = next((b for b in buttons if b.get("callback_data") == "menu:gr"), None)
        self.assertIsNotNone(gr_btn)
        self.assertIn("المعاملات ومقيم وقوى", gr_btn["text"])

    def test_show_gr_menu(self):
        mock_bot = MagicMock()
        telegram_bot.show_gr_menu(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("إدارة المعاملات الحكومية والجوازات", text)
        self.assertIn("المادة 40", text)

    def test_show_gr_laws_guide(self):
        mock_bot = MagicMock()
        telegram_bot.show_gr_laws_guide(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("دليل المعاملات الحكومية ونظام العمل السعودي (المادة 40)", text)
        self.assertIn("تجديد إقامة", text)
        self.assertIn("650 ر.س", text)

    @patch("telegram_bot.get_gr_service_for_bot")
    def test_show_employee_gr_card(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_summary = MagicMock()
        mock_summary.employee_name = "ياسر الحربي"
        mock_summary.employee_id = 118
        mock_summary.department_name = "التقنية"
        mock_summary.is_saudi = True
        mock_summary.nationality_text_ar = "مواطن سعودي"
        mock_summary.identification_id = "1099887766"
        mock_summary.total_transactions_count = 1
        mock_summary.recent_transactions = [
            {"transaction_date": "2026-10-06", "transaction": "توثيق عقد عمل في قوى", "amount": 0.0, "state": "confirmed"}
        ]
        mock_service.get_employee_gr_summary.return_value = mock_summary

        mock_bot = MagicMock()
        telegram_bot.show_employee_gr_card(mock_bot, chat_id=123, employee_id=118)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("ياسر الحربي", text)
        self.assertIn("مواطن سعودي", text)
        self.assertIn("توثيق عقد عمل في قوى", text)

    @patch("telegram_bot.get_gr_service_for_bot")
    def test_handle_gr_wizard_step_dry_run(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service

        mock_dry_res = MagicMock()
        mock_dry_res.is_valid = True
        mock_dry_res.employee_name = "طارق ممدوح"
        mock_dry_res.employee_id = 119
        mock_dry_res.nationality_text_ar = "وافد غير سعودي (مقيم)"
        mock_dry_res.transaction = "تجديد إقامة"
        mock_dry_res.amount_sar = 650.0
        mock_dry_res.company_share_sar = 650.0
        mock_dry_res.company_percentage = 100.0
        mock_dry_res.employee_share_sar = 0.0
        mock_dry_res.employee_percentage = 0.0
        mock_dry_res.statutory_article = "المادة 40"
        mock_dry_res.warnings = []
        mock_dry_res.approval_token = "GR-AABBCCDD"
        mock_service.dry_run_gr_transaction.return_value = mock_dry_res

        mock_bot = MagicMock()
        chat_id = "test_chat_gr_wiz"
        telegram_bot.ACTIVE_GR_WIZARDS[chat_id] = {
            "mode": "gr_details",
            "employee_id": 119,
            "user_id": "u666"
        }

        handled = telegram_bot.handle_gr_wizard_step(
            mock_bot, chat_id, "u666", "طارق", "تجديد إقامة", 1
        )
        self.assertTrue(handled)
        self.assertNotIn(chat_id, telegram_bot.ACTIVE_GR_WIZARDS)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("GR-AABBCCDD", text)
        self.assertIn("650.00 ر.س", text)
        self.assertIn("وافد غير سعودي", text)

    @patch("telegram_bot.get_gr_service_for_bot")
    def test_execute_gr_transaction_via_service(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_exec_res = MagicMock()
        mock_exec_res.success = True
        mock_exec_res.employee_name = "طارق ممدوح"
        mock_exec_res.employee_id = 119
        mock_exec_res.reference = "GR-202610-ABCD"
        mock_exec_res.transaction = "تجديد إقامة"
        mock_exec_res.amount_sar = 650.0
        mock_exec_res.transaction_id = 999
        mock_service.apply_gr_transaction.return_value = mock_exec_res

        mock_bot = MagicMock()
        telegram_bot.execute_gr_transaction_via_service(mock_bot, chat_id=123, token="GR-AABBCCDD", msg_id=1)
        self.assertEqual(mock_bot.send_message.call_count, 2)
        success_msg = mock_bot.send_message.call_args_list[1][0][1]
        self.assertIn("تم تسجيل المعاملة الحكومية بنجاح", success_msg)
        self.assertIn("#999", success_msg)

    def test_main_menu_keyboard_has_appraisal_button(self):
        kb = telegram_bot.get_main_menu_keyboard()
        buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        app_btn = next((b for b in buttons if b.get("callback_data") == "menu:appraisal"), None)
        self.assertIsNotNone(app_btn)
        self.assertIn("تقييمات الأداء والموظفين", app_btn["text"])

    def test_show_appraisal_menu(self):
        mock_bot = MagicMock()
        telegram_bot.show_appraisal_menu(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("إدارة تقييمات الأداء والموظفين", text)
        self.assertIn("المادة 53", text)

    def test_show_appraisal_laws_guide(self):
        mock_bot = MagicMock()
        telegram_bot.show_appraisal_laws_guide(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("دليل تقييم الأداء ونظام العمل السعودي (المادة 53 ولائحة العمل)", text)
        self.assertIn("سلم التقديرات المعتمد", text)
        self.assertIn("ممتاز", text)

    @patch("telegram_bot.get_appraisal_service_for_bot")
    def test_show_employee_appraisal_card(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_summary = MagicMock()
        mock_summary.employee_name = "مشعل المطيري"
        mock_summary.employee_id = 125
        mock_summary.department_name = "العمليات"
        mock_summary.job_title = "مشرف عمليات"
        mock_summary.is_saudi = True
        mock_summary.nationality_text_ar = "مواطن سعودي"
        mock_summary.identification_id = "1022334455"
        mock_summary.hiring_date = "2026-08-01"
        mock_summary.days_since_hiring = 65
        mock_summary.in_probation_period = True
        mock_summary.total_appraisals_count = 0
        mock_summary.last_score = None
        mock_summary.last_rating_ar = None
        mock_service.get_employee_appraisal_summary.return_value = mock_summary

        mock_bot = MagicMock()
        telegram_bot.show_employee_appraisal_card(mock_bot, chat_id=123, employee_id=125)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("مشعل المطيري", text)
        self.assertIn("مواطن سعودي", text)
        self.assertIn("داخل فترة التجربة", text)

    @patch("telegram_bot.get_appraisal_service_for_bot")
    def test_handle_appraisal_wizard_step_dry_run(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service

        mock_dry_res = MagicMock()
        mock_dry_res.is_valid = True
        mock_dry_res.employee_name = "سالم الزهراني"
        mock_dry_res.employee_id = 126
        mock_dry_res.nationality_text_ar = "مواطن سعودي"
        mock_dry_res.appraisal_title = "التقييم الدوري السنوي لعام 2026"
        mock_dry_res.kpi_score = 92.0
        mock_dry_res.competency_score = 88.0
        mock_dry_res.final_percentage = 90.8
        mock_dry_res.rating_ar = "ممتاز"
        mock_dry_res.recommendation_ar = "ترشيح للترقية"
        mock_dry_res.statutory_article = "لائحة تنظيم العمل"
        mock_dry_res.warnings = []
        mock_dry_res.approval_token = "APR-AABBCCDD"
        mock_service.dry_run_appraisal.return_value = mock_dry_res

        mock_bot = MagicMock()
        chat_id = "test_chat_app_wiz"
        telegram_bot.ACTIVE_APPRAISAL_WIZARDS[chat_id] = {
            "mode": "appraisal_details",
            "employee_id": 126,
            "user_id": "u777"
        }

        handled = telegram_bot.handle_appraisal_wizard_step(
            mock_bot, chat_id, "u777", "سالم", "92 88 annual", 1
        )
        self.assertTrue(handled)
        self.assertNotIn(chat_id, telegram_bot.ACTIVE_APPRAISAL_WIZARDS)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("APR-AABBCCDD", text)
        self.assertIn("90.8%", text)
        self.assertIn("ممتاز", text)

    @patch("telegram_bot.get_appraisal_service_for_bot")
    def test_execute_appraisal_via_service(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_exec_res = MagicMock()
        mock_exec_res.success = True
        mock_exec_res.employee_name = "سالم الزهراني"
        mock_exec_res.employee_id = 126
        mock_exec_res.appraisal_title = "التقييم الدوري السنوي"
        mock_exec_res.final_percentage = 90.8
        mock_exec_res.rating_ar = "ممتاز"
        mock_exec_res.appraisal_id = 777
        mock_service.apply_appraisal.return_value = mock_exec_res

        mock_bot = MagicMock()
        telegram_bot.execute_appraisal_via_service(mock_bot, chat_id=123, token="APR-AABBCCDD", msg_id=1)
        self.assertEqual(mock_bot.send_message.call_count, 2)
        success_msg = mock_bot.send_message.call_args_list[1][0][1]
        self.assertIn("تم تسجيل واعتماد تقييم الأداء بنجاح", success_msg)
        self.assertIn("#777", success_msg)

    def test_main_menu_keyboard_has_loan_button(self):
        kb = telegram_bot.get_main_menu_keyboard()
        buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        loan_btn = next((b for b in buttons if b.get("callback_data") == "menu:loan"), None)
        self.assertIsNotNone(loan_btn)
        self.assertIn("السلف وقروض الموظفين", loan_btn["text"])

    def test_show_loan_menu(self):
        mock_bot = MagicMock()
        telegram_bot.show_loan_menu(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("إدارة سلف وقروض الموظفين", text)
        self.assertIn("المادة 92", text)
        self.assertIn("25%", text)

    def test_show_loan_laws_guide(self):
        mock_bot = MagicMock()
        telegram_bot.show_loan_laws_guide(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("المادة 92", text)
        self.assertIn("25% من أجر العامل شهرياً", text)
        self.assertIn("نصف أجر العامل (50%)", text)

    @patch("telegram_bot.get_loan_service_for_bot")
    def test_show_employee_loan_card(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_summary = MagicMock()
        mock_summary.employee_name = "طلال الشمري"
        mock_summary.employee_id = 140
        mock_summary.department_name = "المحاسبة"
        mock_summary.job_title = "محاسب أول"
        mock_summary.is_saudi = True
        mock_summary.nationality_text_ar = "مواطن سعودي"
        mock_summary.monthly_wage = 10000.0
        mock_summary.max_allowed_monthly_deduction = 2500.0
        mock_summary.active_loans_count = 0
        mock_summary.total_active_loan_amount = 0.0
        mock_summary.recent_loans = []
        mock_service.get_employee_loan_summary.return_value = mock_summary

        mock_bot = MagicMock()
        telegram_bot.show_employee_loan_card(mock_bot, chat_id=123, employee_id=140)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("طلال الشمري", text)
        self.assertIn("مواطن سعودي", text)
        self.assertIn("2,500.00 ر.س", text)

    @patch("telegram_bot.get_loan_service_for_bot")
    def test_handle_loan_wizard_step_dry_run(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service

        mock_dry_res = MagicMock()
        mock_dry_res.is_valid = True
        mock_dry_res.employee_name = "طلال الشمري"
        mock_dry_res.employee_id = 140
        mock_dry_res.nationality_text_ar = "مواطن سعودي"
        mock_dry_res.loan_amount = 6000.0
        mock_dry_res.term = 6
        mock_dry_res.installment_amount = 1000.0
        mock_dry_res.deduction_percentage_of_wage = 10.0
        mock_dry_res.statutory_article = "المادة 92 من نظام العمل السعودي"
        mock_dry_res.warnings = []
        mock_dry_res.approval_token = "LOAN-112233"
        mock_service.dry_run_loan.return_value = mock_dry_res

        mock_bot = MagicMock()
        chat_id = "test_chat_loan_wiz"
        telegram_bot.ACTIVE_LOAN_WIZARDS[chat_id] = {
            "mode": "loan_details",
            "employee_id": 140,
            "user_id": "u888"
        }

        handled = telegram_bot.handle_loan_wizard_step(
            mock_bot, chat_id, "u888", "طلال", "6000 6 1000", 1
        )
        self.assertTrue(handled)
        self.assertNotIn(chat_id, telegram_bot.ACTIVE_LOAN_WIZARDS)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("LOAN-112233", text)
        self.assertIn("6,000.00 ر.س", text)
        self.assertIn("1,000.00 ر.س", text)

    @patch("telegram_bot.get_loan_service_for_bot")
    def test_execute_loan_via_service(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_exec_res = MagicMock()
        mock_exec_res.success = True
        mock_exec_res.employee_name = "طلال الشمري"
        mock_exec_res.employee_id = 140
        mock_exec_res.loan_amount = 6000.0
        mock_exec_res.installment_amount = 1000.0
        mock_exec_res.term = 6
        mock_exec_res.loan_id = 888
        mock_service.apply_loan.return_value = mock_exec_res

        mock_bot = MagicMock()
        telegram_bot.execute_loan_via_service(mock_bot, chat_id=123, token="LOAN-112233", msg_id=1)
        self.assertEqual(mock_bot.send_message.call_count, 2)
        success_msg = mock_bot.send_message.call_args_list[1][0][1]
        self.assertIn("تم تسجيل واعتماد سلفة الموظف بنجاح", success_msg)
        self.assertIn("#888", success_msg)

    def test_main_menu_keyboard_has_recruitment_button(self):
        kb = telegram_bot.get_main_menu_keyboard()
        buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        rec_btn = next((b for b in buttons if b.get("callback_data") == "menu:recruitment"), None)
        self.assertIsNotNone(rec_btn)
        self.assertIn("شواغر التوظيف والمرشحين", rec_btn["text"])

    def test_show_recruitment_menu(self):
        mock_bot = MagicMock()
        telegram_bot.show_recruitment_menu(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("إدارة التوظيف وشواغر العمل والتوطين", text)
        self.assertIn("المهن المقصورة 100% على المواطنين", text)

    def test_show_saudization_laws_guide(self):
        mock_bot = MagicMock()
        telegram_bot.show_saudization_laws_guide(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("دليل التوطين وقواعد وزارة الموارد البشرية", text)
        self.assertIn("مهن مقصورة 100% على السعوديين", text)
        self.assertIn("مدير / أخصائي / موظف موارد بشرية", text)

    @patch("telegram_bot.get_recruitment_service_for_bot")
    def test_show_recruitment_jobs_list(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_job = MagicMock()
        mock_job.id = 22
        mock_job.name = "أخصائي موارد بشرية"
        mock_job.department_name = "الموارد البشرية"
        mock_job.no_of_recruitment = 2
        mock_job.is_saudi_only = True
        mock_job.compliance_guidance_ar = "سعودة 100%"
        mock_service.get_job_openings.return_value = [mock_job]

        mock_bot = MagicMock()
        telegram_bot.show_recruitment_jobs_list(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("أخصائي موارد بشرية", text)
        self.assertIn("سعودة 100%", text)

    @patch("telegram_bot.get_recruitment_service_for_bot")
    def test_show_applicant_card(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_summary = MagicMock()
        mock_summary.applicant_id = 99
        mock_summary.candidate_name = "ياسر العتيبي"
        mock_summary.job_title = "مطوّر برمجيات"
        mock_summary.department_name = "تقنية المعلومات"
        mock_summary.is_saudi = True
        mock_summary.nationality_text_ar = "مواطن سعودي"
        mock_summary.stage_name = "Initial"
        mock_summary.id_number = "1098765432"
        mock_summary.phone = "0555555555"
        mock_summary.salary_proposed = 12000.0
        mock_summary.salary_expected = 11000.0
        mock_summary.saudization_status_ar = "مطابق لضوابط التوطين والسعودة ✅"
        mock_service.get_applicant_summary.return_value = mock_summary

        mock_bot = MagicMock()
        telegram_bot.show_applicant_card(mock_bot, chat_id=123, applicant_id=99)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("ياسر العتيبي", text)
        self.assertIn("مطوّر برمجيات", text)
        self.assertIn("12,000.00 ر.س", text)

    @patch("telegram_bot.get_recruitment_service_for_bot")
    def test_handle_recruitment_wizard_step_dry_run(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service

        mock_dry_res = MagicMock()
        mock_dry_res.is_valid = True
        mock_dry_res.candidate_name = "ياسر العتيبي"
        mock_dry_res.job_id = 23
        mock_dry_res.job_title = "مطوّر برمجيات"
        mock_dry_res.is_saudi = True
        mock_dry_res.nationality_text_ar = "مواطن سعودي"
        mock_dry_res.total_salary = 12000.0
        mock_dry_res.statutory_article = "نظام العمل السعودي"
        mock_dry_res.warnings = []
        mock_dry_res.approval_token = "APP-YASSER99"
        mock_service.dry_run_applicant.return_value = mock_dry_res

        mock_bot = MagicMock()
        chat_id = "test_chat_recruit_wiz"
        telegram_bot.ACTIVE_RECRUITMENT_WIZARDS[chat_id] = {
            "mode": "recruit_details",
            "job_id": 23,
            "user_id": "u999"
        }

        handled = telegram_bot.handle_recruitment_wizard_step(
            mock_bot, chat_id, "u999", "ياسر", "ياسر_العتيبي saudi 12000 1098765432", 1
        )
        self.assertTrue(handled)
        self.assertNotIn(chat_id, telegram_bot.ACTIVE_RECRUITMENT_WIZARDS)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("APP-YASSER99", text)
        self.assertIn("12,000.00 ر.س", text)
        self.assertIn("مواطن سعودي", text)

    @patch("telegram_bot.get_recruitment_service_for_bot")
    def test_execute_applicant_via_service(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_exec_res = MagicMock()
        mock_exec_res.success = True
        mock_exec_res.candidate_name = "ياسر العتيبي"
        mock_exec_res.job_id = 23
        mock_exec_res.job_title = "مطوّر برمجيات"
        mock_exec_res.is_saudi = True
        mock_exec_res.total_salary = 12000.0
        mock_exec_res.applicant_id = 1234
        mock_service.apply_applicant.return_value = mock_exec_res

        mock_bot = MagicMock()
        telegram_bot.execute_applicant_via_service(mock_bot, chat_id=123, token="APP-YASSER99", msg_id=1)
        self.assertEqual(mock_bot.send_message.call_count, 2)
        success_msg = mock_bot.send_message.call_args_list[1][0][1]
        self.assertIn("تم تسجيل طلب التوظيف والمرشح بنجاح", success_msg)
        self.assertIn("#1234", success_msg)

    def test_main_menu_keyboard_has_contract_button(self):
        kb = telegram_bot.get_main_menu_keyboard()
        buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        ctr_btn = next((b for b in buttons if b.get("callback_data") == "menu:contract"), None)
        self.assertIsNotNone(ctr_btn)
        self.assertIn("عقود العمل وهيكلة الأجور", ctr_btn["text"])

    def test_show_contract_menu(self):
        mock_bot = MagicMock()
        telegram_bot.show_contract_menu(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("إدارة عقود العمل وهيكلة الأجور والبدلات", text)
        self.assertIn("التفريق الحتمي بين المواطن والمقيم", text)

    def test_show_contract_laws_guide(self):
        mock_bot = MagicMock()
        telegram_bot.show_contract_laws_guide(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("الدليل النظامي لعقود العمل والأجور والتأمينات الاجتماعية", text)
        self.assertIn("المادة 37", text)
        self.assertIn("9.75%", text)

    @patch("telegram_bot.get_contract_service_for_bot")
    def test_show_employee_contract_card(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_summary = MagicMock()
        mock_summary.employee_id = 101
        mock_summary.employee_name = "طلال الدوسري"
        mock_summary.job_title = "مطور برمجيات"
        mock_summary.department_name = "تقنية المعلومات"
        mock_summary.is_saudi = True
        mock_summary.nationality_text_ar = "مواطن سعودي"
        mock_summary.contract_type_name = "عقد غير محدد المدة"
        mock_summary.date_start = "2024-01-01"
        mock_summary.date_end = None
        mock_summary.basic_wage = 12000.0
        mock_summary.housing_allowance = 3000.0
        mock_summary.transportation_allowance = 1200.0
        mock_summary.other_allowances = 0.0
        mock_summary.total_package = 16200.0
        mock_summary.gosi_contributory_wage = 15000.0
        mock_summary.gosi_employee_deduction = 1462.5
        mock_summary.net_estimated_salary = 14737.5
        mock_summary.compliance_notes = []
        mock_service.get_employee_contract_summary.return_value = mock_summary

        mock_bot = MagicMock()
        telegram_bot.show_employee_contract_card(mock_bot, chat_id=123, employee_id=101)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("طلال الدوسري", text)
        self.assertIn("12,000.00 ر.س", text)
        self.assertIn("16,200.00 ر.س", text)

    @patch("telegram_bot.get_contract_service_for_bot")
    def test_handle_contract_wizard_step_dry_run(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service

        mock_dry_res = MagicMock()
        mock_dry_res.is_valid = True
        mock_dry_res.employee_id = 101
        mock_dry_res.employee_name = "طلال الدوسري"
        mock_dry_res.is_saudi = True
        mock_dry_res.nationality_text_ar = "مواطن سعودي"
        mock_dry_res.contract_type_name = "عقد غير محدد المدة"
        mock_dry_res.basic_wage = 12000.0
        mock_dry_res.housing_allowance = 3000.0
        mock_dry_res.transportation_allowance = 1200.0
        mock_dry_res.total_package = 16200.0
        mock_dry_res.gosi_contributory_wage = 15000.0
        mock_dry_res.gosi_employee_deduction = 1462.5
        mock_dry_res.net_estimated_salary = 14737.5
        mock_dry_res.statutory_article = "نظام العمل والتأمينات"
        mock_dry_res.warnings = []
        mock_dry_res.approval_token = "CTR-TALAL99"
        mock_service.dry_run_contract.return_value = mock_dry_res

        mock_bot = MagicMock()
        chat_id = "test_chat_contract_wiz"
        telegram_bot.ACTIVE_CONTRACT_WIZARDS[chat_id] = {
            "mode": "contract_details",
            "employee_id": 101,
            "user_id": "u888"
        }

        handled = telegram_bot.handle_contract_wizard_step(
            mock_bot, chat_id, "u888", "طلال", "12000 3000 1200", 1
        )
        self.assertTrue(handled)
        self.assertNotIn(chat_id, telegram_bot.ACTIVE_CONTRACT_WIZARDS)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("CTR-TALAL99", text)
        self.assertIn("16,200.00 ر.س", text)

    @patch("telegram_bot.get_contract_service_for_bot")
    def test_execute_contract_via_service(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_exec_res = MagicMock()
        mock_exec_res.success = True
        mock_exec_res.employee_id = 101
        mock_exec_res.employee_name = "طلال الدوسري"
        mock_exec_res.contract_id = 555
        mock_exec_res.total_package = 16200.0
        mock_exec_res.net_estimated_salary = 14737.5
        mock_service.apply_contract.return_value = mock_exec_res

        mock_bot = MagicMock()
        telegram_bot.execute_contract_via_service(mock_bot, chat_id=123, token="CTR-TALAL99", msg_id=1)
        self.assertEqual(mock_bot.send_message.call_count, 2)
        success_msg = mock_bot.send_message.call_args_list[1][0][1]
        self.assertIn("تم اعتماد وتحديث عقد العمل بنجاح في Odoo", success_msg)
        self.assertIn("#555", success_msg)

    def test_main_menu_keyboard_has_payroll_button(self):
        kb = telegram_bot.get_main_menu_keyboard()
        buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        pay_btn = next((b for b in buttons if b.get("callback_data") == "menu:payroll"), None)
        self.assertIsNotNone(pay_btn)
        self.assertIn("مسير الرواتب وحماية الأجور", pay_btn["text"])

    def test_show_payroll_menu(self):
        mock_bot = MagicMock()
        telegram_bot.show_payroll_menu(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("مسيرات الرواتب ونظام حماية الأجور", text)
        self.assertIn("سقف 50%", text)

    def test_show_payroll_laws_guide(self):
        mock_bot = MagicMock()
        telegram_bot.show_payroll_laws_guide(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("الدليل النظامي لمسيرات الرواتب وحماية الأجور", text)
        self.assertIn("المادة 92", text)
        self.assertIn("80%", text)

    @patch("telegram_bot.get_payroll_service_for_bot")
    def test_show_employee_payslip_card(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_summary = MagicMock()
        mock_summary.employee_id = 101
        mock_summary.employee_name = "طلال الدوسري"
        mock_summary.job_title = "مطور برمجيات"
        mock_summary.department_name = "تقنية المعلومات"
        mock_summary.is_saudi = True
        mock_summary.nationality_text_ar = "مواطن سعودي"
        mock_summary.date_from = "2026-10-01"
        mock_summary.date_to = "2026-10-31"
        mock_summary.basic_wage = 12000.0
        mock_summary.housing_allowance = 3000.0
        mock_summary.transportation_allowance = 1200.0
        mock_summary.other_allowances = 0.0
        mock_summary.gross_wage = 16200.0
        mock_summary.gosi_employee_deduction = 1462.5
        mock_summary.loan_deduction = 0.0
        mock_summary.discipline_deduction = 0.0
        mock_summary.total_deductions = 1462.5
        mock_summary.net_wage = 14737.5
        mock_summary.compliance_notes = []
        mock_service.get_employee_payslip_summary.return_value = mock_summary

        mock_bot = MagicMock()
        telegram_bot.show_employee_payslip_card(mock_bot, chat_id=123, employee_id=101)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("طلال الدوسري", text)
        self.assertIn("16,200.00 ر.س", text)
        self.assertIn("14,737.50 ر.س", text)

    @patch("telegram_bot.get_payroll_service_for_bot")
    def test_handle_payroll_wizard_step_dry_run(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service

        mock_dry_res = MagicMock()
        mock_dry_res.is_valid = True
        mock_dry_res.employee_id = 101
        mock_dry_res.employee_name = "طلال الدوسري"
        mock_dry_res.is_saudi = True
        mock_dry_res.nationality_text_ar = "مواطن سعودي"
        mock_dry_res.gross_wage = 16200.0
        mock_dry_res.gosi_contributory_wage = 15000.0
        mock_dry_res.gosi_employee_deduction = 1462.5
        mock_dry_res.loan_installment = 1000.0
        mock_dry_res.discipline_deduction = 0.0
        mock_dry_res.total_deductions = 2462.5
        mock_dry_res.deduction_pct_of_gross = 15.2
        mock_dry_res.net_wage = 13737.5
        mock_dry_res.statutory_article = "نظام العمل وحماية الأجور"
        mock_dry_res.warnings = []
        mock_dry_res.approval_token = "PAY-TALAL99"
        mock_service.dry_run_payslip.return_value = mock_dry_res

        mock_bot = MagicMock()
        chat_id = "test_chat_payroll_wiz"
        telegram_bot.ACTIVE_PAYROLL_WIZARDS[chat_id] = {
            "mode": "payroll_details",
            "employee_id": 101,
            "user_id": "u777"
        }

        handled = telegram_bot.handle_payroll_wizard_step(
            mock_bot, chat_id, "u777", "طلال", "1000 0", 1
        )
        self.assertTrue(handled)
        self.assertNotIn(chat_id, telegram_bot.ACTIVE_PAYROLL_WIZARDS)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("PAY-TALAL99", text)
        self.assertIn("13,737.50 ر.س", text)
        self.assertIn("مواطن سعودي", text)

    @patch("telegram_bot.get_payroll_service_for_bot")
    def test_execute_payslip_via_service(self, mock_service_getter):
        mock_service = MagicMock()
        mock_service_getter.return_value = mock_service
        mock_exec_res = MagicMock()
        mock_exec_res.success = True
        mock_exec_res.employee_id = 101
        mock_exec_res.employee_name = "طلال الدوسري"
        mock_exec_res.payslip_id = 999
        mock_exec_res.gross_wage = 16200.0
        mock_exec_res.net_wage = 13737.5
        mock_service.apply_payslip.return_value = mock_exec_res

        mock_bot = MagicMock()
        telegram_bot.execute_payslip_via_service(mock_bot, chat_id=123, token="PAY-TALAL99", msg_id=1)
        self.assertEqual(mock_bot.send_message.call_count, 2)
        success_msg = mock_bot.send_message.call_args_list[1][0][1]
        self.assertIn("تم إنشاء واعتماد قسيمة الراتب بنجاح في Odoo", success_msg)
        self.assertIn("#999", success_msg)

    def test_main_menu_keyboard_has_analytics_button(self):
        kb = telegram_bot.get_main_menu_keyboard()
        buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        ana_btn = next((b for b in buttons if b.get("callback_data") == "menu:analytics"), None)
        self.assertIsNotNone(ana_btn)
        self.assertIn("المؤشرات والتحليلات الشاملة", ana_btn["text"])

    @patch("telegram_bot.get_analytics_service_for_bot")
    def test_show_analytics_menu(self, mock_svc_getter):
        mock_svc = MagicMock()
        mock_svc_getter.return_value = mock_svc
        mock_svc.get_unified_dashboard.return_value = MagicMock(
            workforce=MagicMock(total_employees=15, saudi_count=6, non_saudi_count=9, saudization_rate_pct=40.0, nitaqat_band_name="النطاق الأخضر المرتفع"),
            compliance=MagicMock(health_score=95, rating_label_ar="امتثال ممتاز 🏆"),
        )
        mock_bot = MagicMock()
        telegram_bot.show_analytics_menu(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("لوحة المؤشرات والتحليلات التنفيذية", text)
        self.assertIn("40.0%", text)
        self.assertIn("95/100", text)

    @patch("telegram_bot.get_analytics_service_for_bot")
    def test_show_analytics_overview_card(self, mock_svc_getter):
        mock_svc = MagicMock()
        mock_svc_getter.return_value = mock_svc
        mock_dash = MagicMock()
        mock_dash.workforce.total_employees = 25
        mock_dash.workforce.saudi_count = 10
        mock_dash.workforce.non_saudi_count = 15
        mock_dash.workforce.saudization_rate_pct = 40.0
        mock_dash.workforce.nitaqat_band_name = "النطاق الأخضر المرتفع"
        mock_dash.operations.pending_leaves_count = 3
        mock_dash.operations.approved_leaves_count = 12
        mock_dash.operations.today_checkins_count = 20
        mock_dash.operations.currently_active_checkins_count = 18
        mock_dash.operations.total_monthly_overtime_hours = 45.0
        mock_dash.financial.estimated_monthly_gross_payroll = 150000.0
        mock_dash.financial.total_active_loans_balance = 25000.0
        mock_dash.financial.active_loans_count = 4
        mock_dash.financial.estimated_monthly_gosi_employer_cost = 14000.0
        mock_dash.compliance.health_score = 90
        mock_dash.compliance.rating_label_ar = "امتثال ممتاز"
        mock_dash.compliance.expiring_iqamas_30d = 1
        mock_dash.compliance.pending_disciplinary_count = 0
        mock_dash.compliance.active_probation_count = 2
        mock_dash.recruitment.open_jobs_count = 2
        mock_dash.recruitment.total_applicants_count = 8
        mock_dash.generated_at_ar = "2026-10-06 08:00:00"
        mock_svc.get_unified_dashboard.return_value = mock_dash

        mock_bot = MagicMock()
        telegram_bot.show_analytics_overview_card(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("التقرير التنفيذي الشامل", text)
        self.assertIn("150,000.00 ر.س", text)
        self.assertIn("45.0 ساعة", text)

    @patch("telegram_bot.get_analytics_service_for_bot")
    def test_show_analytics_saudization_card(self, mock_svc_getter):
        mock_svc = MagicMock()
        mock_svc_getter.return_value = mock_svc
        mock_wf = MagicMock()
        mock_wf.total_employees = 30
        mock_wf.saudi_count = 15
        mock_wf.non_saudi_count = 15
        mock_wf.saudization_rate_pct = 50.0
        mock_wf.nitaqat_band_name = "النطاق البلاتيني"
        mock_wf.nitaqat_status_ar = "ممتاز"
        mock_wf.male_count = 20
        mock_wf.female_count = 10
        mock_wf.top_departments = [{"department": "التقنية", "count": 12}]
        mock_svc.get_workforce_kpis.return_value = mock_wf

        mock_bot = MagicMock()
        telegram_bot.show_analytics_saudization_card(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("تقرير التوطين ونطاقات الدقيق", text)
        self.assertIn("البلاتيني", text)
        self.assertIn("50.0%", text)

    @patch("telegram_bot.get_analytics_service_for_bot")
    def test_show_analytics_financial_card(self, mock_svc_getter):
        mock_svc = MagicMock()
        mock_svc_getter.return_value = mock_svc
        mock_fin = MagicMock()
        mock_fin.estimated_monthly_gross_payroll = 120000.0
        mock_fin.estimated_monthly_gosi_employer_cost = 11000.0
        mock_fin.estimated_monthly_gosi_employee_deductions = 7000.0
        mock_fin.total_active_loans_balance = 30000.0
        mock_fin.active_loans_count = 3
        mock_fin.monthly_loan_recovery_run = 3500.0
        mock_fin.total_eosb_settled_amount = 50000.0
        mock_svc.get_financial_kpis.return_value = mock_fin

        mock_bot = MagicMock()
        telegram_bot.show_analytics_financial_card(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("تقرير الالتزامات المالية ومسيرات الرواتب", text)
        self.assertIn("120,000.00 ر.س", text)

    @patch("telegram_bot.get_analytics_service_for_bot")
    def test_show_analytics_compliance_card(self, mock_svc_getter):
        mock_svc = MagicMock()
        mock_svc_getter.return_value = mock_svc
        mock_comp = MagicMock()
        mock_comp.health_score = 88
        mock_comp.rating_label_ar = "امتثال جيد جداً 🟢"
        mock_comp.expiring_iqamas_30d = 2
        mock_comp.expiring_iqamas_60d = 1
        mock_comp.expiring_iqamas_90d = 3
        mock_comp.pending_disciplinary_count = 1
        mock_comp.active_probation_count = 2
        mock_comp.compliance_alerts = ["إقامات تنتهي قريباً"]
        mock_comp.actionable_recommendations_ar = ["تجديد عبر مقيم"]
        mock_svc.get_compliance_kpis.return_value = mock_comp

        mock_bot = MagicMock()
        telegram_bot.show_analytics_compliance_card(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("مؤشر الامتثال النظامي ومخاطر العمل", text)
        self.assertIn("88/100", text)

    @patch("telegram_bot.get_analytics_service_for_bot")
    def test_handle_analytics_wizard_step_simulator(self, mock_svc_getter):
        mock_svc = MagicMock()
        mock_svc_getter.return_value = mock_svc
        mock_sim_res = MagicMock()
        mock_sim_res.current_employees = 10
        mock_sim_res.current_saudi = 4
        mock_sim_res.current_rate_pct = 40.0
        mock_sim_res.current_band = "النطاق الأخضر المرتفع"
        mock_sim_res.simulated_employees = 12
        mock_sim_res.simulated_saudi = 6
        mock_sim_res.simulated_rate_pct = 50.0
        mock_sim_res.simulated_band = "النطاق البلاتيني"
        mock_sim_res.status_change_ar = "ترقية إيجابية إلى النطاق البلاتيني"
        mock_sim_res.legal_advice_ar = "الخطة المقترحة ترفع المنشأة لأعلى فئة تسهيلات."
        mock_svc.simulate_saudization_impact.return_value = mock_sim_res

        chat_id = "test_chat_sim_99"
        telegram_bot.ACTIVE_ANALYTICS_WIZARDS[chat_id] = {"mode": "simulate", "user_id": "u888"}
        mock_bot = MagicMock()

        handled = telegram_bot.handle_analytics_wizard_step(
            mock_bot, chat_id, "u888", "عبدالله", "2 0", 10
        )
        self.assertTrue(handled)
        self.assertNotIn(chat_id, telegram_bot.ACTIVE_ANALYTICS_WIZARDS)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("نتائج محاكي التوطين وبرنامج نطاقات", text)
        self.assertIn("البلاتيني", text)
        self.assertIn("50.0%", text)



    def test_main_menu_keyboard_has_sijil_and_laya(self):
        kb = telegram_bot.get_main_menu_keyboard()
        buttons = [btn["callback_data"] for row in kb["inline_keyboard"] for btn in row]
        self.assertIn("audit:pdf", buttons)
        self.assertIn("laya:info", buttons)

    @patch("sijil_audit_service.SijilAuditService")
    def test_send_sijil_audit_pdf(self, mock_sijil_cls):
        mock_svc = MagicMock()
        mock_sijil_cls.return_value = mock_svc
        mock_svc.generate_pdf_report.return_value = ("output/audit_reports/test.pdf", b"%PDF-1.4")
        mock_svc.compile_audit_summary.return_value = {
            "readback_rate": 100.0,
            "four_eyes_tokens_count": 16,
            "total_events": 339,
            "blocked_actions": 44,
            "report_digest": "SIJIL-TEST-HASH",
        }
        mock_bot = MagicMock()
        telegram_bot.send_sijil_audit_pdf(mock_bot, 12345, 99)
        mock_bot.send_document.assert_called_once()
        args = mock_bot.send_document.call_args[0]
        self.assertEqual(args[0], 12345)
        self.assertIn("تقرير الرقابة والتدقيق", mock_bot.send_document.call_args[1]["caption"])

    @patch("laya_service.LayaService")
    def test_show_laya_info_card(self, mock_laya_cls):
        mock_svc = MagicMock()
        mock_laya_cls.return_value = mock_svc
        mock_svc.get_info.return_value = {
            "version": "0.3.28",
            "domains_supported": ["leaves", "attendance", "contracts", "payroll", "audit"],
        }
        mock_bot = MagicMock()
        telegram_bot.show_laya_info_card(mock_bot, 12345)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("وكيلة القرار السريع والتوجيه الذكي: «لايا»", text)
        self.assertIn("v0.3.28", text)


    def test_main_menu_keyboard_has_expenses_and_expiries(self):
        kb = telegram_bot.get_main_menu_keyboard()
        buttons = [btn["callback_data"] for row in kb["inline_keyboard"] for btn in row]
        self.assertIn("menu:expenses", buttons)
        self.assertIn("menu:expiries", buttons)
        self.assertIn("menu:letters", buttons)

    def test_show_expense_menu(self):
        mock_bot = MagicMock()
        telegram_bot.show_expense_menu(mock_bot, chat_id=123)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("إدارة مصروفات الموظفين وانتدابات العمل", text)
        kb = mock_bot.send_message.call_args[1]["reply_markup"]
        cb_datas = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
        self.assertIn("expense:cat:travel", cb_datas)
        self.assertIn("expense:cat:hotel", cb_datas)
        self.assertIn("expense:cat:general", cb_datas)

    @patch("telegram_bot.get_expiry_service_for_bot")
    def test_show_expiry_menu_card(self, mock_getter):
        mock_svc = MagicMock()
        mock_getter.return_value = mock_svc
        mock_scan = MagicMock()
        mock_svc.scan_expiries.return_value = mock_scan
        mock_svc.format_telegram_summary_message.return_value = "تقرير متابعة صلاحيات الوثائق والعقود"

        mock_bot = MagicMock()
        telegram_bot.show_expiry_menu_card(mock_bot, chat_id=456, max_days=90)
        mock_bot.send_message.assert_called_once()
        text = mock_bot.send_message.call_args[0][1]
        self.assertIn("تقرير متابعة صلاحيات الوثائق والعقود", text)
        kb = mock_bot.send_message.call_args[1]["reply_markup"]
        cb_datas = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
        self.assertIn("expiries:filter:7", cb_datas)
        self.assertIn("expiries:pdf", cb_datas)

    @patch("telegram_bot.get_expense_service_for_bot")
    def test_execute_expense_via_service(self, mock_getter):
        mock_svc = MagicMock()
        mock_getter.return_value = mock_svc
        mock_apply_res = MagicMock()
        mock_apply_res.is_success = True
        mock_apply_res.expense_id = 42
        mock_apply_res.employee_name = "سالم القرني"
        mock_apply_res.employee_id = 99
        mock_apply_res.reference_code = "EXP-2026-99-TEST"
        mock_apply_res.total_amount = 750.0
        mock_apply_res.state = "draft"
        mock_apply_res.pdf_path = None
        mock_apply_res.html_path = None
        mock_svc.apply_expense.return_value = mock_apply_res

        mock_bot = MagicMock()
        telegram_bot.execute_expense_via_service(mock_bot, chat_id=789, token="TOK-TEST-77")
        mock_svc.apply_expense.assert_called_once_with(approval_token="TOK-TEST-77", user_confirmation_text="تأكيد")
        self.assertEqual(mock_bot.send_message.call_count, 2)
        success_msg = mock_bot.send_message.call_args_list[1][0][1]
        self.assertIn("تم تسجيل وقيد المصروف بنجاح", success_msg)
        self.assertIn("#42", success_msg)

    def test_autofix_toggle_state_and_persistence(self):
        chat_id = "test_chat_999"
        # Test default is False
        telegram_bot.AUTOFIX_ENABLED_BY_CHAT.pop(chat_id, None)
        self.assertFalse(telegram_bot.is_autofix_enabled(chat_id))

        # Enable autofix
        telegram_bot.set_autofix_enabled(chat_id, True)
        self.assertTrue(telegram_bot.is_autofix_enabled(chat_id))

        # Disable autofix
        telegram_bot.set_autofix_enabled(chat_id, False)
        self.assertFalse(telegram_bot.is_autofix_enabled(chat_id))

    def test_show_musleh_info_card_and_autofix_status_card(self):
        mock_bot = MagicMock()
        chat_id = 12345
        telegram_bot.set_autofix_enabled(chat_id, True)

        # Show info card
        telegram_bot.show_musleh_info_card(mock_bot, chat_id)
        mock_bot.send_message.assert_called_once()
        msg_text = mock_bot.send_message.call_args[0][1]
        self.assertIn("وكيل الإصلاح الذاتي والتعافي: «مصلح»", msg_text)
        self.assertIn("Auto-Fix Active", msg_text)
        self.assertIn("APPLY_AUTO_PATCH", msg_text)

        # Show status card
        mock_bot.reset_mock()
        telegram_bot.show_autofix_status_card(mock_bot, chat_id)
        mock_bot.send_message.assert_called_once()
        status_text = mock_bot.send_message.call_args[0][1]
        self.assertIn("إعدادات الإصلاح التلقائي: «مصلح»", status_text)
        self.assertIn("Auto-Fix Active", status_text)

    def test_autofix_callbacks_dispatch(self):
        mock_bot = MagicMock()
        chat_id = 54321
        user_id = 99
        cq_id = "cq_test_1"

        # Enable via callback
        telegram_bot.handle_callback_dispatch(
            mock_bot, chat_id, user_id, "UserTest", 1, cq_id, "autofix:enable"
        )
        self.assertTrue(telegram_bot.is_autofix_enabled(chat_id))
        mock_bot.answer_callback_query.assert_called_with(cq_id, "تم تفعيل الإصلاح التلقائي 🟢")

        # Disable via callback
        mock_bot.reset_mock()
        telegram_bot.handle_callback_dispatch(
            mock_bot, chat_id, user_id, "UserTest", 1, cq_id, "autofix:disable"
        )
        self.assertFalse(telegram_bot.is_autofix_enabled(chat_id))
        mock_bot.answer_callback_query.assert_called_with(cq_id, "تم تعطيل الإصلاح التلقائي ⏸️")

    @patch("whisper_service.WhisperSTTService.transcribe")
    def test_handle_voice_message_successful_transcription(self, mock_transcribe):
        from whisper_service import TranscriptionResult

        mock_transcribe.return_value = TranscriptionResult(
            text="أريد تقديم إجازة سنوية للموظف أحمد",
            language="ar",
            duration=3.5,
            backend="faster_whisper_tiny",
            is_success=True,
        )

        mock_bot = MagicMock()
        mock_bot.download_file.return_value = True

        voice_obj = {
            "file_id": "voice_file_12345",
            "duration": 4,
            "mime_type": "audio/ogg",
        }

        res = telegram_bot.handle_voice_message(
            bot=mock_bot,
            chat_id=123,
            user_id=456,
            user_name="سالم",
            voice_obj=voice_obj,
            message_id=999,
        )

        self.assertEqual(res, "أريد تقديم إجازة سنوية للموظف أحمد")
        mock_bot.download_file.assert_called_once()
        self.assertEqual(mock_bot.send_message.call_count, 2)
        second_call_text = mock_bot.send_message.call_args_list[1][0][1]
        self.assertIn("النص المستخلص من التسجيل الصوتي", second_call_text)
        self.assertIn("أريد تقديم إجازة سنوية للموظف أحمد", second_call_text)
        self.assertIn("لايا", second_call_text)

    def test_handle_voice_message_download_failure(self):
        mock_bot = MagicMock()
        mock_bot.download_file.return_value = False

        voice_obj = {
            "file_id": "broken_file_id",
            "duration": 2,
        }

        res = telegram_bot.handle_voice_message(
            bot=mock_bot,
            chat_id=123,
            user_id=456,
            user_name="سالم",
            voice_obj=voice_obj,
            message_id=999,
        )

        self.assertIsNone(res)
        self.assertEqual(mock_bot.send_message.call_count, 2)
        err_call_text = mock_bot.send_message.call_args_list[1][0][1]
        self.assertIn("تعذر تحميل التسجيل الصوتي", err_call_text)

    @patch("whisper_service.WhisperSTTService.transcribe")
    def test_handle_voice_message_unclear_or_empty_audio(self, mock_transcribe):
        from whisper_service import TranscriptionResult

        mock_transcribe.return_value = TranscriptionResult(
            text="",
            is_success=True,
        )

        mock_bot = MagicMock()
        mock_bot.download_file.return_value = True

        voice_obj = {
            "file_id": "silent_file_id",
            "duration": 1,
        }

        res = telegram_bot.handle_voice_message(
            bot=mock_bot,
            chat_id=123,
            user_id=456,
            user_name="سالم",
            voice_obj=voice_obj,
            message_id=999,
        )

    @patch("odoo_readonly_repository.OdooReadonlyRepository.search_employee_candidates")
    def test_resolve_employee_input_single_match(self, mock_search):
        mock_search.return_value = [{"id": 147, "name": "ناصر القحطاني", "work_email": "nasser@company.com"}]
        mock_bot = MagicMock()
        res = telegram_bot.resolve_employee_input_for_wizard(
            bot=mock_bot, chat_id=1234, user_input="ناصر القحطاني", wiz_type="leave_bal", cancel_callback="menu:leaves"
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 147)
        self.assertEqual(res["name"], "ناصر القحطاني")
        mock_bot.send_message.assert_not_called()

    @patch("odoo_readonly_repository.OdooReadonlyRepository.search_employee_candidates")
    def test_resolve_employee_input_multiple_matches_shows_buttons(self, mock_search):
        mock_search.return_value = [
            {"id": 147, "name": "ناصر القحطاني", "job_id": [1, "مدير الموارد"]},
            {"id": 13, "name": "نورة القحطاني", "job_id": [2, "محاسب أول"]},
        ]
        mock_bot = MagicMock()
        res = telegram_bot.resolve_employee_input_for_wizard(
            bot=mock_bot, chat_id=1234, user_input="القحطاني", wiz_type="leave_bal", cancel_callback="menu:leaves"
        )
        self.assertIsNone(res)
        mock_bot.send_message.assert_called_once()
        sent_args = mock_bot.send_message.call_args[0]
        sent_kwargs = mock_bot.send_message.call_args[1]
        self.assertIn("وجدنا (2) موظفين يطابقون «القحطاني»", sent_args[1])
        kb = sent_kwargs["reply_markup"]["inline_keyboard"]
        self.assertEqual(len(kb), 3)  # 2 employees + 1 cancel button
        self.assertEqual(kb[0][0]["callback_data"], "wiz_emp:leave_bal:147")
        self.assertEqual(kb[1][0]["callback_data"], "wiz_emp:leave_bal:13")
        self.assertEqual(kb[2][0]["callback_data"], "menu:leaves")

    @patch("odoo_readonly_repository.OdooReadonlyRepository.search_employee_candidates")
    def test_resolve_employee_input_zero_match_shows_guidance(self, mock_search):
        mock_search.return_value = []
        mock_bot = MagicMock()
        res = telegram_bot.resolve_employee_input_for_wizard(
            bot=mock_bot, chat_id=1234, user_input="مجهول_تماماً", wiz_type="leave_bal", cancel_callback="menu:leaves"
        )
        self.assertIsNone(res)
        mock_bot.send_message.assert_called_once()
        sent_text = mock_bot.send_message.call_args[0][1]
        self.assertIn("لم يتم العثور على موظف يطابق «<b>مجهول_تماماً</b>»", sent_text)
        self.assertIn("رقم المعرّف ID مباشرة", sent_text)

    @patch("telegram_bot.show_employee_leaves_balance")
    def test_handle_callback_dispatch_wiz_emp(self, mock_show_bal):
        mock_bot = MagicMock()
        telegram_bot.handle_callback_dispatch(
            bot=mock_bot,
            chat_id=1234,
            user_id=5678,
            user_name="سالم",
            msg_id=10,
            cq_id="cq_99",
            data="wiz_emp:leave_bal:147",
        )
        mock_bot.answer_callback_query.assert_called_with("cq_99")
        mock_show_bal.assert_called_once_with(mock_bot, 1234, 147)


if __name__ == "__main__":
    unittest.main()





