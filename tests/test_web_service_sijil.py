"""
Unit tests for Web Service endpoints of Sijil Audit PDF/HTML reports (Phase 21).
"""

import unittest
from fastapi.testclient import TestClient
from web_service import app


class TestWebServiceSijil(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
