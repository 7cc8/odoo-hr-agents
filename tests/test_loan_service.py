from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from odoo_loan_write_gateway import (
    OdooLoanWriteGateway,
    LoanEnvironmentGuardError,
    LoanWriteGatewayError,
)
from loan_service import (
    LoanService,
    LoanSummary,
    LoanDryRunResult,
    LoanExecutionResult,
    STATUTORY_MAX_LOAN_DEDUCTION_PCT,
    STATUTORY_MAX_TOTAL_DEDUCTION_PCT,
)
from web_service import app


class TestOdooLoanWriteGateway(unittest.TestCase):
    def test_environment_guard_blocks_unauthorized_db(self):
        with self.assertRaises(LoanEnvironmentGuardError):
            OdooLoanWriteGateway(
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

        gateway = OdooLoanWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        with self.assertRaises(LoanWriteGatewayError):
            gateway._call("hr.employee", "create", [{}])

        with self.assertRaises(LoanWriteGatewayError):
            gateway._call("employee.loan", "unlink", [[1]])

    @patch("xmlrpc.client.ServerProxy")
    def test_get_or_create_default_loan_type(self, mock_proxy_cls):
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1
        mock_common.version.return_value = {"server_version": "19.0"}
        mock_models = MagicMock()
        mock_models.execute_kw.return_value = [{"id": 5, "name": "سلفة راتب شخصية"}]

        gateway = OdooLoanWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        lt_id = gateway.get_or_create_default_loan_type()
        self.assertEqual(lt_id, 5)

    @patch("xmlrpc.client.ServerProxy")
    def test_create_and_read_employee_loan(self, mock_proxy_cls):
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1
        mock_common.version.return_value = {"server_version": "19.0"}

        mock_models = MagicMock()
        mock_models.execute_kw.side_effect = [
            [{"id": 1, "name": "Standard Loan"}],  # get_or_create_default_loan_type search_read
            901,  # create returns ID
            [{"id": 901, "name": "LOAN/2026/001", "loan_amount": 6000.0, "installment_amount": 1000.0, "state": "draft"}],  # read
            True,  # approve returns True
        ]

        gateway = OdooLoanWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        created_id = gateway.create_employee_loan(
            employee_id=14,
            loan_amount=6000.0,
            installment_amount=1000.0,
            term=6,
        )
        self.assertEqual(created_id, 901)

        read_res = gateway.read_employee_loan(901)
        self.assertIsNotNone(read_res)
        self.assertEqual(read_res["id"], 901)

        app_res = gateway.approve_employee_loan(901, "dep_approval")
        self.assertTrue(app_res)


class TestLoanService(unittest.TestCase):
    def setUp(self):
        self.mock_repo = MagicMock()
        self.mock_gw = MagicMock()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_log_path = Path(self.temp_dir.name) / "test_loan_audit.jsonl"
        self.service = LoanService(
            readonly_repo=self.mock_repo,
            write_gateway=self.mock_gw,
            audit_log_path=str(self.audit_log_path),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_employee_loan_summary_saudi(self):
        self.mock_repo.get_employee.return_value = {
            "id": 14,
            "name": "محمد العتيبي",
            "department_id": [2, "تقنية المعلومات"],
            "job_id": [5, "مطور برمجيات"],
            "country_id": [192, "Saudi Arabia"],
            "identification_id": "1098765432",
        }
        self.mock_repo.get_employee_contracts.return_value = [
            {"wage": 12000.0, "date_start": "2020-01-01", "date_end": False}
        ]
        self.mock_repo.get_employee_loans.return_value = [
            {"id": 1, "loan_amount": 5000.0, "state": "draft"},
            {"id": 2, "loan_amount": 10000.0, "state": "paid"},
        ]

        summary = self.service.get_employee_loan_summary(14)
        self.assertEqual(summary.employee_id, 14)
        self.assertTrue(summary.is_saudi)
        self.assertEqual(summary.monthly_wage, 12000.0)
        self.assertEqual(summary.max_allowed_monthly_deduction, 3000.0)  # 25% of 12000
        self.assertEqual(summary.active_loans_count, 1)
        self.assertEqual(summary.total_active_loan_amount, 5000.0)

    def test_dry_run_loan_success_within_25_percent(self):
        self.mock_repo.get_employee.return_value = {
            "id": 14,
            "name": "سعد القرني",
            "department_id": [2, "الموارد البشرية"],
            "job_id": [3, "أخصائي توظيف"],
            "country_id": [192, "Saudi Arabia"],
            "identification_id": "1012345678",
        }
        self.mock_repo.get_employee_contracts.return_value = [
            {"wage": 10000.0, "date_start": "2022-01-01"}
        ]
        self.mock_repo.get_employee_loans.return_value = []

        res = self.service.dry_run_loan(
            employee_id=14,
            loan_amount=12000.0,
            term=6,
            installment_amount=2000.0,  # 20% of 10000 <= 25%
        )

        self.assertTrue(res.is_valid)
        self.assertTrue(res.can_proceed)
        self.assertEqual(res.installment_amount, 2000.0)
        self.assertEqual(res.deduction_percentage_of_wage, 20.0)
        self.assertTrue(res.approval_token.startswith("LOAN-"))
        self.assertEqual(len(res.errors), 0)

    def test_dry_run_loan_fails_exceeding_25_percent_article_92(self):
        self.mock_repo.get_employee.return_value = {
            "id": 15,
            "name": "فهد السبيعي",
            "department_id": [2, "المبيعات"],
            "job_id": [4, "مندوب مبيعات"],
            "country_id": [192, "Saudi Arabia"],
            "identification_id": "1087654321",
        }
        self.mock_repo.get_employee_contracts.return_value = [
            {"wage": 6000.0, "date_start": "2023-01-01"}
        ]
        self.mock_repo.get_employee_loans.return_value = []

        # Request 3000 monthly on 6000 wage (50% > 25% ceiling)
        res = self.service.dry_run_loan(
            employee_id=15,
            loan_amount=9000.0,
            term=3,
            installment_amount=3000.0,
        )

        self.assertFalse(res.is_valid)
        self.assertFalse(res.can_proceed)
        self.assertEqual(res.deduction_percentage_of_wage, 50.0)
        self.assertGreater(len(res.errors), 0)
        self.assertIn("المادة 92", res.errors[0])
        self.assertEqual(res.suggested_min_term, 6)  # ceil(9000 / 1500) = 6
        self.assertEqual(res.suggested_max_installment, 1500.0)  # 25% of 6000

    def test_dry_run_loan_expat_remaining_contract_warning(self):
        self.mock_repo.get_employee.return_value = {
            "id": 20,
            "name": "عمر الشامي",
            "department_id": [1, "الهندسة"],
            "job_id": [2, "مهندس معماري"],
            "country_id": [64, "Egypt"],
            "identification_id": "2456789012",
        }
        # Contract ends in 6 months
        self.mock_repo.get_employee_contracts.return_value = [
            {"wage": 8000.0, "date_start": "2024-01-01", "date_end": "2026-12-31"}
        ]
        self.mock_repo.get_employee_loans.return_value = []

        # Request 12 months loan (exceeds contract remaining months)
        res = self.service.dry_run_loan(
            employee_id=20,
            loan_amount=12000.0,
            term=12,
            installment_amount=1000.0,
        )

        self.assertTrue(res.is_valid)  # 1000 <= 2000 (25%), valid but has warning
        self.assertTrue(any("المادة 37" in w for w in res.warnings))

    def test_apply_loan_requires_written_confirmation(self):
        self.mock_repo.get_employee.return_value = {
            "id": 14,
            "name": "سعد القرني",
            "department_id": [2, "الموارد البشرية"],
            "job_id": [3, "أخصائي توظيف"],
            "country_id": [192, "Saudi Arabia"],
            "identification_id": "1012345678",
        }
        self.mock_repo.get_employee_contracts.return_value = [{"wage": 10000.0}]
        self.mock_repo.get_employee_loans.return_value = []

        dry_res = self.service.dry_run_loan(
            employee_id=14,
            loan_amount=6000.0,
            term=6,
            installment_amount=1000.0,
        )

        # Rejection without written "تأكيد"
        exec_fail = self.service.apply_loan(
            approval_token=dry_res.approval_token,
            user_confirmation_text="موافق",
        )
        self.assertFalse(exec_fail.success)
        self.assertIn("تأكيد", exec_fail.message_ar)

        # Success with written "تأكيد"
        self.mock_gw.create_employee_loan.return_value = 999
        self.mock_gw.read_employee_loan.return_value = {
            "id": 999,
            "loan_amount": 6000.0,
            "installment_amount": 1000.0,
            "term": 6,
            "state": "draft",
        }

        exec_succ = self.service.apply_loan(
            approval_token=dry_res.approval_token,
            user_confirmation_text="تأكيد",
        )
        self.assertTrue(exec_succ.success)
        self.assertEqual(exec_succ.loan_id, 999)
        self.assertTrue(exec_succ.readback_verified)
        self.assertTrue(exec_succ.audit_logged)
        self.assertTrue(self.audit_log_path.exists())


class TestLoanAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_get_loan_rules_endpoint(self):
        resp = self.client.get("/api/loans/rules")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["rules"]["max_loan_deduction_percentage"], 25.0)
        self.assertEqual(data["rules"]["max_total_deductions_percentage"], 50.0)

    @patch("web_service.get_loan_service_instance")
    def test_get_loan_summary_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_get_svc.return_value = mock_svc
        mock_svc.get_employee_loan_summary.return_value = LoanSummary(
            employee_id=14,
            employee_name="خالد الدوسري",
            department_name="المالية",
            job_title="محاسب",
            is_saudi=True,
            nationality_text_ar="مواطن سعودي",
            monthly_wage=10000.0,
            max_allowed_monthly_deduction=2500.0,
            active_loans_count=0,
            total_active_loan_amount=0.0,
        )

        resp = self.client.get("/api/loans/summary/14")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["summary"]["max_allowed_monthly_deduction"], 2500.0)

    @patch("web_service.get_loan_service_instance")
    def test_dry_run_loan_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_get_svc.return_value = mock_svc
        mock_svc.dry_run_loan.return_value = LoanDryRunResult(
            is_valid=True,
            employee_id=14,
            employee_name="خالد الدوسري",
            department_id=1,
            department_name="المالية",
            job_id=2,
            job_title="محاسب",
            is_saudi=True,
            nationality_text_ar="مواطن سعودي",
            loan_amount=6000.0,
            monthly_wage=10000.0,
            installment_amount=1000.0,
            term=6,
            start_date="2026-10-06",
            deduction_percentage_of_wage=10.0,
            max_statutory_deduction_percentage=25.0,
            suggested_min_term=6,
            suggested_max_installment=2500.0,
            statutory_article="المادة 92 من نظام العمل السعودي",
            statutory_explanation_ar="مطابق لسقف الـ 25%",
            approval_token="LOAN-123456",
            can_proceed=True,
        )

        payload = {
            "employee_id": 14,
            "loan_amount": 6000.0,
            "term": 6,
            "installment_amount": 1000.0,
        }
        resp = self.client.post("/api/loans/dry-run", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["result"]["approval_token"], "LOAN-123456")

    @patch("web_service.get_loan_service_instance")
    def test_apply_loan_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_get_svc.return_value = mock_svc
        mock_svc.apply_loan.return_value = LoanExecutionResult(
            success=True,
            loan_id=101,
            employee_id=14,
            employee_name="خالد الدوسري",
            loan_amount=6000.0,
            installment_amount=1000.0,
            term=6,
            state="draft",
            readback_verified=True,
            message_ar="تم تسجيل السلفة بنجاح",
            audit_logged=True,
        )

        payload = {
            "approval_token": "LOAN-123456",
            "confirmation_text": "تأكيد",
        }
        resp = self.client.post(
            "/api/loans/apply",
            json=payload,
            headers={"X-API-Key": "hr-write-secret-token"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["loan_id"], 101)


if __name__ == "__main__":
    unittest.main()
