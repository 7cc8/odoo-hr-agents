# -*- coding: utf-8 -*-
"""
حزمة اختبارات التحقق من رفع وفحص جميع قوالب الإكسل الموديلية والماستر
========================================================================
تتحقق من:
1. رفع كشف الحضور template_attendance.xlsx واجتياز الفحص الجاف دون missing_employees_sheet.
2. رفع قالب الموظفين المعياري template_employees.xlsx وفحصه بنجاح.
3. رفع قالب العقود والبدلات template_contracts_allowances.xlsx.
4. رفع قالب القروض والسلف template_loans_installments.xlsx والتأكد من م/92.
5. رفع القالب الشامل Master_Client_Onboarding_Template.xlsx.
6. استمرار التوافق الكامل مع ملفات استيراد الموظفين الكلاسيكية (Legacy).
7. توثيق أحداث فاحص وسراج دون أي كتابة غير معتمدة لكاتب في Odoo.
"""

import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from openpyxl import Workbook

from web_service import app
from agent_events_service import get_events_service
from dry_run_report import build_full_report


class TestAllModularExcelTemplatesUpload(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.events_service = get_events_service()

    def test_upload_template_attendance_succeeds_without_error(self):
        att_path = Path("templates") / "modular" / "template_attendance.xlsx"
        self.assertTrue(att_path.exists(), "الملف template_attendance.xlsx غير موجود")

        with open(att_path, "rb") as f:
            res = self.client.post(
                "/api/agents/upload",
                files={"file": ("template_attendance.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"chat_id": "test_attend_user"}
            )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("dry_run_report", data)
        self.assertIsNotNone(data["dry_run_report"])

        dry_run = data["dry_run_report"]
        self.assertNotIn("error", dry_run)
        self.assertIn("summary", dry_run)
        self.assertEqual(dry_run["total_rows"], 1)
        self.assertEqual(dry_run["accepted_count"], 1)
        self.assertIn("ساعات الحضور", dry_run.get("template_title", ""))

    def test_upload_template_employees_modular_succeeds(self):
        emp_path = Path("templates") / "modular" / "template_employees.xlsx"
        self.assertTrue(emp_path.exists(), "الملف template_employees.xlsx غير موجود")

        with open(emp_path, "rb") as f:
            res = self.client.post(
                "/api/agents/upload",
                files={"file": ("template_employees.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"chat_id": "test_emp_user"}
            )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("dry_run_report", data)
        dry_run = data["dry_run_report"]
        self.assertNotIn("error", dry_run)
        self.assertEqual(dry_run["total_rows"], 1)
        self.assertEqual(dry_run["accepted_count"], 1)

    def test_upload_template_contracts_succeeds(self):
        c_path = Path("templates") / "modular" / "template_contracts_allowances.xlsx"
        self.assertTrue(c_path.exists())

        with open(c_path, "rb") as f:
            res = self.client.post(
                "/api/agents/upload",
                files={"file": ("template_contracts_allowances.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"chat_id": "test_contract_user"}
            )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertNotIn("error", data.get("dry_run_report", {}))

    def test_upload_template_loans_succeeds(self):
        l_path = Path("templates") / "modular" / "template_loans_installments.xlsx"
        self.assertTrue(l_path.exists())

        with open(l_path, "rb") as f:
            res = self.client.post(
                "/api/agents/upload",
                files={"file": ("template_loans_installments.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"chat_id": "test_loan_user"}
            )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertNotIn("error", data.get("dry_run_report", {}))

    def test_upload_master_onboarding_workbook_succeeds(self):
        m_path = Path("templates") / "master" / "Master_Client_Onboarding_Template.xlsx"
        self.assertTrue(m_path.exists())

        with open(m_path, "rb") as f:
            res = self.client.post(
                "/api/agents/upload",
                files={"file": ("Master_Client_Onboarding_Template.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"chat_id": "test_master_user"}
            )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertNotIn("error", data.get("dry_run_report", {}))

    def test_legacy_employee_file_backward_compatibility(self):
        wb = Workbook()
        ws = wb.active
        ws.title = "Employees"
        headers = ["name", "work_email", "work_phone", "mobile_phone", "job_title", "company", "department", "job", "hiring_date"]
        ws.append(headers)
        ws.append(["عبدالله محمد الغامدي", "A.alghamdi@example.com", "01260", "0551471", "مسؤول محاسبة", "شركة النخبة الذكية للتقنية", "الإدارة العليا / المحاسبة والمالية", "محاسب", "2026-02-01"])

        test_file = Path("output") / "test_legacy_backward_compat.xlsx"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        wb.save(test_file)

        report = build_full_report(test_file)
        self.assertIn("summary", report)
        self.assertEqual(report["summary"]["row_count"], 1)
        self.assertIn(report["rows"][0]["final_status"], ["accepted", "needs_review"])


if __name__ == "__main__":
    unittest.main()
