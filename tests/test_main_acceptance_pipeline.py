# -*- coding: utf-8 -*-
"""Comprehensive Main Acceptance Test Flow:
متابعة → محادثتها الصحيحة → حالتها وخطها → سجلها → البحث بمعرفها → PDF لنفس العملية.
"""

import sys
import unittest
from fastapi.testclient import TestClient

from web_service import app
from agent_events_service import get_events_service

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


class TestMainAcceptancePipeline(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.events_service = get_events_service()
        self.auth_headers = {"X-API-Key": "unit-test-write-token"}

    def test_complete_main_acceptance_workflow(self):
        # Step 0: Ensure an active/completed operation exists in the system
        res_recent = self.client.get("/api/sijil/recent?limit=5", headers=self.auth_headers)
        self.assertEqual(res_recent.status_code, 200)
        recent_ops = res_recent.json().get("operations", [])
        self.assertGreater(len(recent_ops), 0, "يجب وجود عملية واحدة على الأقل في السجل")

        chosen_op = recent_ops[0]
        chosen_id = chosen_op["identifier"]
        print(f"\n[اختبار القبول الرئيسي] العملية المختارة: {chosen_id} ({chosen_op.get('type')})")

        # Step 1: متابعة -> محادثتها الصحيحة
        res_op = self.client.get(f"/api/agents/operations/{chosen_id}")
        if res_op.status_code == 404:
            # Sijil operation might have del_ prefix; check via sijil detail
            res_sijil = self.client.get(f"/api/sijil/operation/{chosen_id}")
            self.assertEqual(res_sijil.status_code, 200)
            op_data = res_sijil.json()["operation"]
        else:
            self.assertEqual(res_op.status_code, 200)
            op_data = res_op.json()["operation"]

        self.assertIsNotNone(op_data)
        self.assertIn("user_query", op_data)
        print(f"  ✓ 1. متابعة ومحادثتها: الطلب الأصلي = «{op_data.get('user_query', '')[:40]}...»")

        # Step 2: حالتها وخطها (Timeline & Process Steps)
        res_detail = self.client.get(f"/api/sijil/operation/{chosen_id}")
        self.assertEqual(res_detail.status_code, 200)
        sijil_data = res_detail.json()["operation"]

        self.assertIn("timeline", sijil_data)
        timeline = sijil_data["timeline"]
        self.assertGreater(len(timeline), 0)
        self.assertIn("stage", timeline[0])
        print(f"  ✓ 2. حالتها وخطها: الحالة = {sijil_data.get('final_status')} | عدد مراحل الخط = {len(timeline)}")

        # Step 3: سجلها (Audit Ledger & Fingerprint)
        self.assertIn("technical_details", sijil_data)
        sha256 = sijil_data["technical_details"].get("sha256_digest")
        self.assertIsNotNone(sha256)
        print(f"  ✓ 3. سجلها وتوثيقها: البصمة = {sha256}")

        # Step 4: البحث بمعرفها (Search by Operation/Plan ID)
        res_search = self.client.get(f"/api/sijil/search?q={chosen_id}")
        self.assertEqual(res_search.status_code, 200)
        search_data = res_search.json()
        self.assertEqual(search_data["status"], "success")
        self.assertEqual(search_data["match_type"], "single")
        self.assertEqual(search_data["operation"]["operation_id"], sijil_data["operation_id"])
        print(f"  ✓ 4. البحث بمعرفها: تم استرجاع نفس السجل بنجاح (match_type=single)")

        # Step 5: PDF لنفس العملية (A4 Arabic PDF Export)
        res_pdf = self.client.get(f"/api/sijil/operation/{chosen_id}/pdf")
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf.headers.get("content-type"), "application/pdf")
        self.assertGreater(len(res_pdf.content), 1000)
        self.assertTrue(res_pdf.content.startswith(b"%PDF"))
        print(f"  ✓ 5. PDF لنفس العملية: تم توليد تقرير A4 أبيض عربي بحجم {len(res_pdf.content):,} بايت")


if __name__ == "__main__":
    unittest.main()
