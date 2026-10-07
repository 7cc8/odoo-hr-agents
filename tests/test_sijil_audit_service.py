"""
Unit tests for SijilAuditService (Phase 21: Sijil Audit PDF Generator).
"""

import unittest
from pathlib import Path
from sijil_audit_service import SijilAuditService


class TestSijilAuditService(unittest.TestCase):
    def setUp(self):
        self.service = SijilAuditService()

    def test_collect_audit_logs(self):
        records = self.service.collect_audit_logs()
        self.assertIsInstance(records, list)
        self.assertGreater(len(records), 0)

    def test_compile_audit_summary(self):
        summary = self.service.compile_audit_summary()
        self.assertIn("total_events", summary)
        self.assertIn("readback_rate", summary)
        self.assertIn("domain_counts", summary)
        self.assertIn("report_digest", summary)
        self.assertGreater(summary["total_events"], 0)
        self.assertEqual(summary["readback_rate"], 100.0)

    def test_generate_html_report(self):
        html = self.service.generate_html_report()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("تقرير الحوكمة والتدقيق الرقابي المستمر", html)
        self.assertIn("Resend Black Velvet", html)
        self.assertIn("IBM Plex Sans Arabic", html)
        self.assertIn("JetBrains Mono", html)
        self.assertIn("مطابق 100%", html)

    def test_generate_pdf_report(self):
        pdf_path, pdf_bytes = self.service.generate_pdf_report(output_filename="test_sijil_report.pdf")
        self.assertTrue(Path(pdf_path).exists())
        self.assertGreater(len(pdf_bytes), 1000)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
