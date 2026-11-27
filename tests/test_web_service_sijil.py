"""
Unit tests for Web Service endpoints of Sijil Audit PDF/HTML reports (Phase 21).
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
from fastapi.testclient import TestClient
from web_service import app


class TestWebServiceSijil(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_sijil_summary_api(self):
        with TemporaryDirectory() as folder, patch("sijil_audit_service.LOGS_DIR", Path(folder)):
            empty = self.client.get("/api/sijil/summary").json()["summary"]
            self.assertIsNone(empty["readback_rate"])
            events = [{"status": "success"}, {"readback_verified": True}, {"readback_verified": False}]
            (Path(folder) / "leave_audit_log.jsonl").write_text("\n".join(map(json.dumps, events)), encoding="utf8")
            res = self.client.get("/api/sijil/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("summary", data)
        self.assertEqual(data["summary"]["total_events"], 3)
        self.assertEqual(data["summary"]["readback_rate"], 50)

    def test_sijil_report_html_api(self):
        res = self.client.get("/api/sijil/report/html")
        self.assertEqual(res.status_code, 200)
        self.assertIn("<!DOCTYPE html>", res.text)
        self.assertIn("تقرير الحوكمة والتدقيق الرقابي المستمر", res.text)


if __name__ == "__main__":
    unittest.main()
