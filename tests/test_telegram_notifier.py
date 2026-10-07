import json
import unittest
from unittest.mock import patch, MagicMock
import urllib.error

import telegram_notifier


class TelegramNotifierTests(unittest.TestCase):

    def test_is_telegram_configured(self):
        self.assertFalse(telegram_notifier.is_telegram_configured("", ""))
        self.assertFalse(telegram_notifier.is_telegram_configured("token123", ""))
        self.assertFalse(telegram_notifier.is_telegram_configured("", "chat123"))
        self.assertTrue(telegram_notifier.is_telegram_configured("token123", "chat123"))

    def test_send_telegram_skipped_when_unconfigured(self):
        res = telegram_notifier.send_telegram_notification("test message", token="", chat_id="")
        self.assertFalse(res["sent"])
        self.assertEqual(res["status"], "skipped")

    @patch("urllib.request.urlopen")
    def test_send_telegram_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"ok": True, "result": {"message_id": 999}}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        res = telegram_notifier.send_telegram_notification(
            "Hello test", token="bot123:ABC", chat_id="123456"
        )
        self.assertTrue(res["sent"])
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["message_id"], 999)

    @patch("urllib.request.urlopen")
    def test_send_telegram_network_error_fails_safe(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection timed out")

        res = telegram_notifier.send_telegram_notification(
            "Hello test", token="bot123:ABC", chat_id="123456"
        )
        self.assertFalse(res["sent"])
        self.assertEqual(res["status"], "error")
        self.assertIn("Connection timed out", res["reason"])

    def test_format_writer_notification(self):
        fake_result = {
            "header": {
                "source_file_name": "employees.xlsx",
                "approved_by": "خالد",
                "target_company_id": 15,
            },
            "footer": {
                "status_counts": {"created": 2, "failed": 0},
                "finished_at": "2026-10-05T00:30:00Z",
            },
            "rows": [
                {
                    "status": "created",
                    "odoo_employee_id": 151,
                    "attempted_name": "سارة الغامدي",
                    "verified": True,
                },
                {
                    "status": "created",
                    "odoo_employee_id": 152,
                    "attempted_name": "خالد الزهراني",
                    "verified": True,
                },
            ],
        }
        msg = telegram_notifier.format_writer_notification(fake_result)
        self.assertIn("employees.xlsx", msg)
        self.assertIn("خالد", msg)
        self.assertIn("151", msg)
        self.assertIn("سارة الغامدي", msg)
        self.assertIn("خالد الزهراني", msg)
        self.assertIn("شركة النخبة", msg or "")  # target company id is 15


if __name__ == "__main__":
    unittest.main()
