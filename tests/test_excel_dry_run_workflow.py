# -*- coding: utf-8 -*-
"""Acceptance test for Excel Upload -> Real Dry-Run Report workflow without unauthorized write."""

import os
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from openpyxl import Workbook

from web_service import app
from agent_events_service import get_events_service


class TestExcelDryRunWorkflow(unittest.TestCase):
    API_HEADERS = {"X-API-Key": "test-secret"}

    def setUp(self):
        self._previous_write_token = os.environ.get("WRITE_API_TOKEN")
        os.environ["WRITE_API_TOKEN"] = "test-secret"
        self.client = TestClient(app)
        self.events_service = get_events_service()

    def tearDown(self):
        if self._previous_write_token is None:
            os.environ.pop("WRITE_API_TOKEN", None)
        else:
            os.environ["WRITE_API_TOKEN"] = self._previous_write_token

    def test_excel_upload_produces_real_dry_run_report(self):
        # 1. Create a test Excel workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Employees"
        headers = ["name", "work_email", "work_phone", "mobile_phone", "job_title", "company", "department", "job", "hiring_date"]
        ws.append(headers)
        ws.append(["ياسر القحطاني", "yasser@example.com", "", "0505551234", "مدير موارد بشرية", "شركة النخبة الذكية للتقنية", "الموارد البشرية", "مدير الموارد", "2026-10-01"])
        ws.append(["هند الشهري", "hind@example.com", "", "0505555678", "أخصائية توظيف", "شركة النخبة الذكية للتقنية", "الموارد البشرية", "أخصائي توظيف", "2026-10-02"])

        test_file = Path("output") / "test_sample_upload.xlsx"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        wb.save(test_file)

        # 2. Upload via /api/agents/upload
        with open(test_file, "rb") as f:
            res = self.client.post(
                "/api/agents/upload",
                files={"file": ("test_sample_upload.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"chat_id": "test_excel_user"},
                headers=self.API_HEADERS,
            )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("dry_run_report", data)
        self.assertIsNotNone(data["dry_run_report"])

        dry_run = data["dry_run_report"]
        self.assertIn("summary", dry_run)
        self.assertGreater(dry_run["total_rows"], 0)
        self.assertIn("accepted_count", dry_run)

        # 3. Verify operation events recorded for Fahas and Seraj
        op_id = data["operation_id"]
        op = self.events_service.get_operation(op_id)
        self.assertIsNotNone(op)
        agents = {e["agent"] for e in op.get("events", [])}
        self.assertIn("seraj", agents)
        self.assertIn("fahas", agents)

        # 4. Verify no write happened (no writer events or odoo mutations)
        self.assertNotIn("katib", agents)
        event_types = [e.get("event_type") for e in op.get("events", [])]
        self.assertIn("dry_run_completed", event_types)


if __name__ == "__main__":
    unittest.main()
