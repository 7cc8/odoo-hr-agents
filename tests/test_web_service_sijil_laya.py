"""
Unit tests for Web Service endpoints of Sijil Audit PDF and Laya Decision Engine (Phase 21).
"""

import unittest
from fastapi.testclient import TestClient
from web_service import app


class TestWebServiceSijilAndLaya(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_sijil_summary_api(self):
        res = self.client.get("/api/sijil/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("summary", data)
        self.assertGreater(data["summary"]["total_events"], 0)

    def test_sijil_report_html_api(self):
        res = self.client.get("/api/sijil/report/html")
        self.assertEqual(res.status_code, 200)
        self.assertIn("<!DOCTYPE html>", res.text)
        self.assertIn("تقرير الحوكمة والتدقيق الرقابي المستمر", res.text)

    def test_laya_triage_api(self):
        payload = {"text": "أريد تسجيل حضور للموظف 100 الآن"}
        res = self.client.post("/api/laya/triage", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["decision"]["domain"], "attendance")
        self.assertEqual(data["decision"]["suggested_agent"], "attendance_service")

    def test_laya_triage_delete_blocked_api(self):
        payload = {"text": "احذف مسير رواتب الموظف"}
        res = self.client.post("/api/laya/triage", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["decision"]["is_deletion_blocked"], True)


if __name__ == "__main__":
    unittest.main()
