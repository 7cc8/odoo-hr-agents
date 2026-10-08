"""
Unit and integration tests for Sijil Agent Web Interface, Unified Search,
Operation Detail Pipeline, Privacy Masking, and PDF Export.
"""

import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from web_service import app
from sijil_audit_service import SijilAuditService


class TestSijilPageAndExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.service = SijilAuditService()

    def test_sijil_page_loads_arabic_html(self):
        """Test GET /sijil loads the complete Arabic RTL interface with no Odoo write controls."""
        res = self.client.get("/sijil")
        self.assertEqual(res.status_code, 200)
        self.assertIn("<!DOCTYPE html>", res.text)
        self.assertIn('dir="rtl"', res.text)
        self.assertIn("الوكيل", res.text)
        self.assertIn("سجل", res.text)
        self.assertIn("مراجعة وتوثيق العمليات", res.text)
        # Ensure read-only role: no action/execute/delete buttons for Odoo
        self.assertNotIn("حذف من أودو", res.text)
        self.assertNotIn("اعتماد العملية", res.text)
        self.assertNotIn("إعادة تنفيذ", res.text)

    def test_search_by_plan_id(self):
        """Test searching by plan_id returns a direct match or candidate."""
        res = self.client.get("/api/sijil/search?q=7afe1140644c")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn(data["match_type"], ["single", "multiple"])
        if data["match_type"] == "single":
            self.assertEqual(data["operation"]["plan_id"], "7afe1140644c")
        else:
            self.assertTrue(any(c.get("plan_id") == "7afe1140644c" for c in data["candidates"]))

    def test_search_by_arabic_numerals(self):
        """Test searching with Arabic-Indic numerals like '١٤' normalizes to '14'."""
        res = self.client.get("/api/sijil/search?q=١٤")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn(data["status"], ["success", "multiple_matches"])
        self.assertIn(data["match_type"], ["single", "multiple"])
        if data["match_type"] == "multiple":
            candidates = data.get("candidates", [])
            self.assertGreater(len(candidates), 0)
            self.assertTrue(any(
                "14" in str(c.get("target", "")) or
                "14" in str(c.get("operation_id", "")) or
                "14" in str(c.get("plan_id", ""))
                for c in candidates
            ))

    def test_search_not_found(self):
        """Test searching for an unknown ID returns not_found with Arabic message."""
        res = self.client.get("/api/sijil/search?q=non_existent_id_99999999")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "not_found")
        self.assertEqual(data["match_type"], "none")
        self.assertIn("لم يُعثر على سجل مطابق", data["message"])

    def test_get_operation_detail_structure(self):
        """Test operation detail endpoint returns complete audit contract."""
        res = self.client.get("/api/sijil/operation/del_7afe1140644c")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        op = data["operation"]

        # 1. Top-level core fields (flat structure — no 'summary' wrapper)
        self.assertEqual(op["plan_id"], "7afe1140644c")
        self.assertIn("operation_type", op)
        self.assertIn("final_status", op)
        self.assertIn("scope", op)

        # 2. Actors differentiation (actual keys: requester / approver / executor)
        self.assertIn("actors", op)
        actors = op["actors"]
        self.assertIn("requester", actors)
        self.assertIn("approver", actors)
        self.assertIn("executor", actors)

        # 3. Execution vs Verification — separate top-level fields
        self.assertIn("execution_result", op)
        self.assertIn("verification_result", op)
        self.assertIn("success", op["execution_result"])
        self.assertIn("label", op["execution_result"])
        self.assertIsInstance(op["verification_result"], dict)

        # 4. Timeline
        self.assertIn("timeline", op)
        self.assertIsInstance(op["timeline"], list)
        self.assertGreater(len(op["timeline"]), 0)
        for event in op["timeline"]:
            self.assertIn("stage", event)   # actual key is 'stage' not 'phase'
            self.assertIn("agent", event)
            self.assertIn("status", event)

        # 5. Conversation — available flag, notice if missing
        self.assertIn("conversation", op)
        conv = op["conversation"]
        self.assertIn("available", conv)   # actual key is 'available'
        if not conv["available"]:
            notice = conv.get("unavailable_notice") or conv.get("notice") or ""
            self.assertTrue(len(notice) > 0, "No unavailability notice provided")

        # 6. Technical Details & Privacy Masking
        self.assertIn("technical_details", op)
        tech_json_str = str(op["technical_details"])
        self.assertNotIn("Bearer secret", tech_json_str)
        self.assertNotIn("password123", tech_json_str)

    def test_export_pdf_endpoint(self):
        """Test PDF export endpoint generates a valid A4 Arabic PDF report."""
        res = self.client.get("/api/sijil/operation/del_7afe1140644c/pdf?include_conversation=false")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("content-type"), "application/pdf")
        self.assertGreater(len(res.content), 1000)
        self.assertTrue(res.content.startswith(b"%PDF"))

    def test_recent_operations_endpoint(self):
        """Test recent operations list endpoint enforces authentication and serves data when authenticated."""
        # Unauthenticated request -> must be rejected with 401
        unauth_res = self.client.get("/api/sijil/recent?limit=5")
        self.assertEqual(unauth_res.status_code, 401)
        self.assertIn("غير مصرّح", unauth_res.json().get("detail", ""))

        # Authenticated request -> must succeed with 200
        res = self.client.get("/api/sijil/recent?limit=5", headers={"X-API-Key": "hr-write-secret-token"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("operations", data)
        self.assertIsInstance(data["operations"], list)
        self.assertGreater(len(data["operations"]), 0)
        self.assertIn("total", data)
        self.assertIn("page", data)


if __name__ == "__main__":
    unittest.main()
