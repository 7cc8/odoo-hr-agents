from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from odoo_payroll_write_gateway import (
    OdooPayrollWriteGateway,
    PayrollEnvironmentGuardError,
    PayrollWriteGatewayError,
)
from payroll_service import (
    PayrollService,
    PayslipSummary,
    PayslipDryRunResult,
    PayslipExecutionResult,
    WpsSifFileResult,
)
from web_service import app


class TestOdooPayrollWriteGateway(unittest.TestCase):
    def test_environment_guard_blocks_unauthorized_db(self):
        with self.assertRaises(PayrollEnvironmentGuardError):
            OdooPayrollWriteGateway(
                url="https://example.odoo.com",
                db="production_real_db",
                username="admin",
                password="pwd",
            )

    @patch("xmlrpc.client.ServerProxy")
    def test_model_isolation_blocks_unauthorized_models(self, mock_proxy_cls):
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1
        mock_common.version.return_value = {"server_version": "19.0"}
        mock_models = MagicMock()

        gateway = OdooPayrollWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        with self.assertRaises(PayrollWriteGatewayError):
            gateway._call("hr.employee", "create", [{}])

        with self.assertRaises(PayrollWriteGatewayError):
            gateway._call("hr.payslip", "unlink", [[1]])

    @patch("xmlrpc.client.ServerProxy")
    def test_create_and_read_payslip(self, mock_proxy_cls):
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1
        mock_common.version.return_value = {"server_version": "19.0"}

        mock_models = MagicMock()
        mock_models.execute_kw.side_effect = [
            701,  # create returns ID
            True,  # write state update
            [{"id": 701, "name": "مسير راتب", "net_wage": 12000.0}],  # read
        ]

        gateway = OdooPayrollWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        pid = gateway.create_payslip(
            employee_id=10,
            date_from="2026-10-01",
            date_to="2026-10-31",
            basic_wage=10000.0,
            gross_wage=13500.0,
            net_wage=12281.25,
        )
        self.assertEqual(pid, 701)

        st_ok = gateway.update_payslip_state(701, "verify")
        self.assertTrue(st_ok)

        slip = gateway.read_payslip(701)
        self.assertIsNotNone(slip)
        self.assertEqual(slip["net_wage"], 12000.0)


class TestPayrollService(unittest.TestCase):
    def setUp(self):
        self.mock_repo = MagicMock()
        self.mock_repo.get_employee_contracts.return_value = []
        self.mock_repo.get_employee_payslips.return_value = []
        self.mock_gw = MagicMock()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_log_path = Path(self.temp_dir.name) / "test_payroll_audit.jsonl"
        self.service = PayrollService(
            readonly_repo=self.mock_repo,
            write_gateway=self.mock_gw,
            audit_log_path=str(self.audit_log_path),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_employee_payslip_summary_saudi(self):
        self.mock_repo.get_employee.return_value = {
            "id": 101,
            "name": "عبدالرحمن القحطاني",
            "department_id": [2, "الموارد البشرية"],
            "job_id": [10, "أخصائي موارد بشرية"],
            "identification_id": "1087654321",
        }
        self.mock_repo.get_employee_contracts.return_value = [
            {
                "wage": 8000.0,
                "l10n_sa_housing_allowance": 2000.0,
                "l10n_sa_transportation_allowance": 800.0,
                "total": 10800.0,
            }
        ]
        self.mock_repo.get_employee_payslips.return_value = []

        summary = self.service.get_employee_payslip_summary(101)
        self.assertTrue(summary.is_saudi)
        self.assertEqual(summary.employee_name, "عبدالرحمن القحطاني")
        self.assertEqual(summary.gross_wage, 10800.0)
        # GOSI: 9.75% of (8000 + 2000) = 975.0 SAR
        self.assertEqual(summary.gosi_employee_deduction, 975.0)
        self.assertEqual(summary.net_wage, 10800.0 - 975.0)

    def test_get_employee_payslip_summary_expat(self):
        self.mock_repo.get_employee.return_value = {
            "id": 102,
            "name": "كمال حسن",
            "department_id": [3, "المحاسبة"],
            "job_id": [15, "محاسب"],
            "identification_id": "2345678901",
        }
        self.mock_repo.get_employee_contracts.return_value = [
            {
                "wage": 7000.0,
                "l10n_sa_housing_allowance": 1750.0,
                "l10n_sa_transportation_allowance": 700.0,
                "total": 9450.0,
            }
        ]
        self.mock_repo.get_employee_payslips.return_value = []

        summary = self.service.get_employee_payslip_summary(102)
        self.assertFalse(summary.is_saudi)
        self.assertEqual(summary.gosi_employee_deduction, 0.0)
        self.assertEqual(summary.net_wage, 9450.0)

    def test_dry_run_payslip_saudi_deductions_within_limits(self):
        self.mock_repo.get_employee.return_value = {
            "id": 201,
            "name": "سعد الدوسري",
            "department_id": [1, "الإدارة"],
            "identification_id": "1001001001",
        }

        res = self.service.dry_run_payslip(
            employee_id=201,
            basic_wage=10000.0,
            housing_allowance=2500.0,
            transportation_allowance=1000.0,
            loan_installment=2000.0,  # ~14.8% of gross (allowed < 25%)
            discipline_amount=400.0,
        )
        self.assertTrue(res.is_valid)
        self.assertTrue(res.can_proceed)
        self.assertEqual(res.gross_wage, 13500.0)
        # GOSI = 9.75% of (10000 + 2500) = 1218.75 SAR
        self.assertEqual(res.gosi_employee_deduction, 1218.75)
        self.assertEqual(res.total_deductions, 1218.75 + 2000.0 + 400.0)
        self.assertTrue(res.approval_token.startswith("PAY-"))

    def test_dry_run_payslip_cumulative_deductions_exceed_50_pct_rejected(self):
        self.mock_repo.get_employee.return_value = {
            "id": 202,
            "name": "ماجد العنزي",
            "department_id": [1, "الإدارة"],
            "identification_id": "1002003004",
        }

        # Gross = 10,000 + 2,500 = 12,500. 50% = 6,250 SAR.
        # Deductions: GOSI 1,218.75 + Loan 4,000 + Disc 2,000 = 7,218.75 (>50%)
        res = self.service.dry_run_payslip(
            employee_id=202,
            basic_wage=10000.0,
            housing_allowance=2500.0,
            loan_installment=4000.0,
            discipline_amount=2000.0,
        )
        self.assertFalse(res.is_valid)
        self.assertFalse(res.can_proceed)
        self.assertTrue(any("المادة 92" in err and "50%" in err for err in res.errors))

    def test_apply_payslip_with_four_eyes_and_audit_log(self):
        self.mock_repo.get_employee.return_value = {
            "id": 301,
            "name": "مشاري المطيري",
            "department_id": [2, "الموارد البشرية"],
            "identification_id": "1011121314",
        }
        self.mock_gw.create_payslip.return_value = 801
        self.mock_gw.read_payslip.return_value = {"id": 801, "net_wage": 11000.0}

        dry_res = self.service.dry_run_payslip(
            employee_id=301,
            basic_wage=10000.0,
            housing_allowance=2500.0,
            transportation_allowance=1000.0,
        )
        self.assertTrue(dry_res.is_valid)
        token = dry_res.approval_token

        # Without 'تأكيد'
        res_bad = self.service.apply_payslip(token, user_confirmation_text="موافق")
        self.assertFalse(res_bad.success)
        self.assertIn("تأكيد", res_bad.message_ar)

        # With 'تأكيد'
        res_good = self.service.apply_payslip(token, user_confirmation_text="تأكيد")
        self.assertTrue(res_good.success)
        self.assertEqual(res_good.payslip_id, 801)
        self.assertTrue(res_good.readback_verified)
        self.assertTrue(res_good.audit_logged)
        self.assertTrue(self.audit_log_path.exists())

    def test_generate_wps_sif_format(self):
        records = [
            {
                "employee_id": 1,
                "identification_id": "1087654321",
                "employee_name": "سعد المطيري",
                "bank_code": "RJHI",
                "iban": "SA0380000000608010167519",
                "basic_wage": 8000.0,
                "housing_allowance": 2000.0,
                "transportation_allowance": 800.0,
                "other_allowances": 0.0,
                "total_deductions": 975.0,
                "net_wage": 9825.0,
            },
            {
                "employee_id": 2,
                "identification_id": "2345678901",
                "employee_name": "محمود إبراهيم",
                "bank_code": "NCBK",
                "iban": "SA0310000000608010167520",
                "basic_wage": 6000.0,
                "housing_allowance": 1500.0,
                "transportation_allowance": 600.0,
                "other_allowances": 0.0,
                "total_deductions": 0.0,
                "net_wage": 8100.0,
            }
        ]

        res = self.service.generate_wps_sif(
            employer_cr="1010123456",
            bank_code="RJHI",
            payslips_data=records,
        )
        self.assertEqual(res.records_count, 2)
        self.assertEqual(res.total_salaries_sar, 17925.0)
        self.assertTrue(res.filename.startswith("WPS_1010123456_"))
        self.assertTrue(res.filename.endswith(".sif"))

        # Verify SIF contents
        lines = res.content.split("\n")
        self.assertEqual(len(lines), 3)  # 1 Header + 2 Employees
        self.assertTrue(lines[0].startswith("SCR,1010123456,RJHI,"))
        self.assertTrue(lines[1].startswith("EDR,1087654321,RJHI,SA0380000000608010167519,"))
        self.assertTrue(lines[2].startswith("EDR,2345678901,NCBK,SA0310000000608010167520,"))


class TestPayrollApiEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("web_service.get_payroll_service_instance")
    def test_get_payroll_structures(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_svc.readonly_repo.get_payroll_structures.return_value = [
            {"id": 1, "name": "Regular Pay", "code": "REG"},
        ]
        mock_get_svc.return_value = mock_svc

        response = self.client.get("/api/payroll/structures")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["count"], 1)

    @patch("web_service.get_payroll_service_instance")
    def test_get_employee_payslip(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_svc.get_employee_payslip_summary.return_value = PayslipSummary(
            payslip_id=1,
            employee_id=10,
            employee_name="نايف الدوسري",
            department_name="المبيعات",
            job_title="مدير مبيعات",
            is_saudi=True,
            nationality_text_ar="مواطن سعودي",
            date_from="2026-10-01",
            date_to="2026-10-31",
            basic_wage=15000.0,
            housing_allowance=3750.0,
            transportation_allowance=1500.0,
            other_allowances=0.0,
            gross_wage=20250.0,
            gosi_employee_deduction=1828.13,
            loan_deduction=0.0,
            discipline_deduction=0.0,
            other_deductions=0.0,
            total_deductions=1828.13,
            net_wage=18421.87,
            state="draft",
            compliance_notes=[],
        )
        mock_get_svc.return_value = mock_svc

        response = self.client.get("/api/payroll/employee/10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["payslip"]["gross_wage"], 20250.0)

    @patch("web_service.get_payroll_service_instance")
    def test_dry_run_payslip_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_svc.dry_run_payslip.return_value = PayslipDryRunResult(
            is_valid=True,
            employee_id=10,
            employee_name="نايف الدوسري",
            department_id=1,
            department_name="المبيعات",
            is_saudi=True,
            nationality_text_ar="مواطن سعودي",
            date_from="2026-10-01",
            date_to="2026-10-31",
            basic_wage=15000.0,
            housing_allowance=3750.0,
            transportation_allowance=1500.0,
            other_allowances=0.0,
            gross_wage=20250.0,
            gosi_contributory_wage=18750.0,
            gosi_employee_deduction=1828.13,
            gosi_employer_contribution=2203.13,
            loan_installment=0.0,
            discipline_deduction=0.0,
            other_deductions=0.0,
            total_deductions=1828.13,
            net_wage=18421.87,
            deduction_pct_of_gross=9.03,
            struct_id=1,
            statutory_article="نظام العمل",
            statutory_explanation_ar="مطابق",
            warnings=[],
            errors=[],
            approval_token="PAY-TEST999",
            can_proceed=True,
        )
        mock_get_svc.return_value = mock_svc

        payload = {"employee_id": 10, "basic_wage": 15000.0}
        response = self.client.post("/api/payroll/dry-run", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["result"]["approval_token"], "PAY-TEST999")

    @patch("web_service.get_payroll_service_instance")
    def test_apply_payslip_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_svc.apply_payslip.return_value = PayslipExecutionResult(
            success=True,
            payslip_id=909,
            employee_id=10,
            employee_name="نايف الدوسري",
            gross_wage=20250.0,
            net_wage=18421.87,
            readback_verified=True,
            message_ar="تم إنشاء القسيمة بنجاح.",
            audit_logged=True,
        )
        mock_get_svc.return_value = mock_svc

        payload = {
            "approval_token": "PAY-TEST999",
            "confirmation_text": "تأكيد",
        }
        headers = {"X-API-Key": "unit-test-write-token"}
        response = self.client.post("/api/payroll/apply", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["payslip_id"], 909)

    @patch("web_service.get_payroll_service_instance")
    def test_generate_wps_sif_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_svc.generate_wps_sif.return_value = WpsSifFileResult(
            filename="WPS_1010123456_20261001.sif",
            content="SCR,1010123456,RJHI,20261001,18421.87,1,SAR\nEDR,1087654321,RJHI,SA0380,15000,3750,1500,1828.13,18421.87,نايف",
            records_count=1,
            total_salaries_sar=18421.87,
            compliance_rate_pct=100.0,
            message_ar="تم توليد ملف WPS بنجاح.",
        )
        mock_get_svc.return_value = mock_svc

        payload = {
            "employer_cr": "1010123456",
            "bank_code": "RJHI",
            "payslips_data": [{"employee_id": 10, "net_wage": 18421.87}],
        }
        response = self.client.post("/api/payroll/wps-sif", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["records_count"], 1)


if __name__ == "__main__":
    unittest.main()
    unittest.main()
