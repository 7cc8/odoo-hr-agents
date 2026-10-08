from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from odoo_contract_write_gateway import (
    OdooContractWriteGateway,
    ContractEnvironmentGuardError,
    ContractWriteGatewayError,
)
from contract_service import (
    ContractService,
    ContractSummary,
    ContractDryRunResult,
    ContractExecutionResult,
    GOSI_SAUDI_EMPLOYEE_RATE,
    GOSI_MAX_CONTRIBUTORY_WAGE,
    NITAQAT_MIN_FULL_SAUDIZATION_WAGE,
)
from web_service import app


class TestOdooContractWriteGateway(unittest.TestCase):
    def test_environment_guard_blocks_unauthorized_db(self):
        with self.assertRaises(ContractEnvironmentGuardError):
            OdooContractWriteGateway(
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

        gateway = OdooContractWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        with self.assertRaises(ContractWriteGatewayError):
            gateway._call("hr.employee", "create", [{}])

        with self.assertRaises(ContractWriteGatewayError):
            gateway._call("hr.version", "unlink", [[1]])

    @patch("xmlrpc.client.ServerProxy")
    def test_update_or_create_contract(self, mock_proxy_cls):
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1
        mock_common.version.return_value = {"server_version": "19.0"}

        mock_models = MagicMock()
        # 1. search_read for existing -> returns [{'id': 55}]
        # 2. write on existing -> returns True
        # 3. read on existing -> returns [{'id': 55, 'wage': 8000.0}]
        mock_models.execute_kw.side_effect = [
            [{"id": 55}],  # search_read existing contract
            True,  # write update
            [{"id": 55, "wage": 8000.0, "employee_id": [100, "سعود السبيعي"]}],  # read contract
        ]

        gateway = OdooContractWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        cid = gateway.update_or_create_contract(
            employee_id=100,
            wage=8000.0,
            is_saudi=True,
            housing_allowance=2000.0,
            transportation_allowance=800.0,
        )
        self.assertEqual(cid, 55)

        read_data = gateway.read_contract(55)
        self.assertIsNotNone(read_data)
        self.assertEqual(read_data["wage"], 8000.0)


class TestContractService(unittest.TestCase):
    def setUp(self):
        self.mock_repo = MagicMock()
        self.mock_gw = MagicMock()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_log_path = Path(self.temp_dir.name) / "test_contract_audit.jsonl"
        self.service = ContractService(
            readonly_repo=self.mock_repo,
            write_gateway=self.mock_gw,
            audit_log_path=str(self.audit_log_path),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_employee_contract_summary_saudi(self):
        self.mock_repo.get_employee.return_value = {
            "id": 101,
            "name": "عبدالعزيز الشمري",
            "department_id": [2, "الموارد البشرية"],
            "job_id": [10, "أخصائي موارد بشرية"],
            "identification_id": "1098765432",
            "country_id": [192, "Saudi Arabia"],
        }
        self.mock_repo.get_employee_contracts.return_value = [
            {
                "id": 12,
                "wage": 10000.0,
                "l10n_sa_housing_allowance": 2500.0,
                "l10n_sa_transportation_allowance": 1000.0,
                "l10n_sa_other_allowances": 0.0,
                "total": 13500.0,
                "date_start": "2024-01-01",
                "date_end": False,
                "contract_type_id": [1, "عقد موحد"],
            }
        ]

        summary = self.service.get_employee_contract_summary(101)
        self.assertTrue(summary.is_saudi)
        self.assertEqual(summary.employee_name, "عبدالعزيز الشمري")
        self.assertEqual(summary.basic_wage, 10000.0)
        self.assertEqual(summary.housing_allowance, 2500.0)
        self.assertEqual(summary.total_package, 13500.0)
        self.assertEqual(summary.gosi_contributory_wage, 12500.0)
        expected_deduction = round(12500.0 * GOSI_SAUDI_EMPLOYEE_RATE, 2)
        self.assertEqual(summary.gosi_employee_deduction, expected_deduction)
        self.assertEqual(summary.net_estimated_salary, 13500.0 - expected_deduction)
        self.assertTrue(summary.is_indefinite)

    def test_get_employee_contract_summary_expat_missing_date_end(self):
        self.mock_repo.get_employee.return_value = {
            "id": 102,
            "name": "محمود المصري",
            "department_id": [3, "المحاسبة"],
            "job_id": [15, "محاسب عام"],
            "identification_id": "2345678901",
            "country_id": [64, "Egypt"],
        }
        self.mock_repo.get_employee_contracts.return_value = [
            {
                "id": 13,
                "wage": 6000.0,
                "l10n_sa_housing_allowance": 1500.0,
                "l10n_sa_transportation_allowance": 600.0,
                "total": 8100.0,
                "date_start": "2024-05-01",
                "date_end": False,
            }
        ]

        summary = self.service.get_employee_contract_summary(102)
        self.assertFalse(summary.is_saudi)
        self.assertEqual(summary.gosi_employee_deduction, 0.0)
        self.assertTrue(any("المادة 37" in note for note in summary.compliance_notes))

    def test_dry_run_contract_expat_without_date_end_rejected(self):
        self.mock_repo.get_employee.return_value = {
            "id": 201,
            "name": "جون دو",
            "department_id": [4, "تقنية المعلومات"],
            "job_id": [20, "مهندس برمجيات"],
            "identification_id": "2233445566",
        }

        res = self.service.dry_run_contract(
            employee_id=201,
            basic_wage=12000.0,
            date_end=None,  # Missing date_end for expat!
        )
        self.assertFalse(res.is_valid)
        self.assertFalse(res.can_proceed)
        self.assertTrue(any("المادة 37" in err for err in res.errors))

    def test_dry_run_contract_expat_with_valid_date_end(self):
        self.mock_repo.get_employee.return_value = {
            "id": 201,
            "name": "جون دو",
            "department_id": [4, "تقنية المعلومات"],
            "job_id": [20, "مهندس برمجيات"],
            "identification_id": "2233445566",
        }

        res = self.service.dry_run_contract(
            employee_id=201,
            basic_wage=12000.0,
            housing_allowance=3000.0,
            transportation_allowance=1200.0,
            date_start="2026-10-01",
            date_end="2027-10-01",
        )
        self.assertTrue(res.is_valid)
        self.assertTrue(res.can_proceed)
        self.assertEqual(res.gosi_employee_deduction, 0.0)
        self.assertTrue(res.approval_token.startswith("CTR-"))

    def test_dry_run_contract_saudi_indefinite_and_nitaqat_warning(self):
        self.mock_repo.get_employee.return_value = {
            "id": 301,
            "name": "فهد السالم",
            "department_id": [1, "الإدارة"],
            "job_id": [5, "مساعد إداري"],
            "identification_id": "1122334455",
        }

        # Basic wage below 4,000 SAR should trigger Nitaqat warning
        res = self.service.dry_run_contract(
            employee_id=301,
            basic_wage=3500.0,
            housing_allowance=875.0,
            transportation_allowance=350.0,
            date_end=None,  # Saudi indefinite contract is allowed
        )
        self.assertTrue(res.is_valid)
        self.assertTrue(res.is_indefinite)
        self.assertTrue(any("نطاقات" in w for w in res.warnings))

    def test_dry_run_contract_probation_period_article_53(self):
        self.mock_repo.get_employee.return_value = {
            "id": 401,
            "name": "راكان الحربي",
            "department_id": [1, "الإدارة"],
            "job_id": [2, "مدير مشروعات"],
            "identification_id": "1002003004",
        }

        # Probation period > 180 days must be strictly rejected
        res_invalid = self.service.dry_run_contract(
            employee_id=401,
            basic_wage=15000.0,
            date_start="2026-01-01",
            trial_date_end="2026-08-01",  # ~212 days
        )
        self.assertFalse(res_invalid.is_valid)
        self.assertTrue(any("المادة 53" in err and "180" in err for err in res_invalid.errors))

        # Probation period between 91 and 180 days should generate written agreement warning
        res_extended = self.service.dry_run_contract(
            employee_id=401,
            basic_wage=15000.0,
            date_start="2026-01-01",
            trial_date_end="2026-04-20",  # 109 days
        )
        self.assertTrue(res_extended.is_valid)
        self.assertTrue(any("اتفاق مكتوب" in w for w in res_extended.warnings))

    def test_apply_contract_with_four_eyes_and_audit_log(self):
        self.mock_repo.get_employee.return_value = {
            "id": 501,
            "name": "سلطان العتيبي",
            "department_id": [2, "الموارد البشرية"],
            "job_id": [10, "أخصائي"],
            "identification_id": "1987654321",
        }
        self.mock_gw.update_or_create_contract.return_value = 88
        self.mock_gw.read_contract.return_value = {"id": 88, "wage": 9000.0}

        dry_res = self.service.dry_run_contract(
            employee_id=501,
            basic_wage=9000.0,
            housing_allowance=2250.0,
            transportation_allowance=900.0,
        )
        self.assertTrue(dry_res.is_valid)
        token = dry_res.approval_token

        # Attempt apply without 'تأكيد'
        res_bad = self.service.apply_contract(token, user_confirmation_text="موافق")
        self.assertFalse(res_bad.success)
        self.assertIn("تأكيد", res_bad.message_ar)

        # Attempt apply with 'تأكيد'
        res_good = self.service.apply_contract(token, user_confirmation_text="تأكيد")
        self.assertTrue(res_good.success)
        self.assertEqual(res_good.contract_id, 88)
        self.assertTrue(res_good.readback_verified)
        self.assertTrue(res_good.audit_logged)
        self.assertTrue(self.audit_log_path.exists())

        # Consumed token cannot be reused
        res_reused = self.service.apply_contract(token, user_confirmation_text="تأكيد")
        self.assertFalse(res_reused.success)


class TestContractApiEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("web_service.get_contract_service_instance")
    def test_get_contract_types(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_svc.readonly_repo.get_contract_types.return_value = [
            {"id": 1, "name": "عقد محدد المدة"},
            {"id": 2, "name": "عقد غير محدد المدة"},
        ]
        mock_get_svc.return_value = mock_svc

        response = self.client.get("/api/contracts/types")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["count"], 2)

    @patch("web_service.get_contract_service_instance")
    def test_get_employee_contract(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_svc.get_employee_contract_summary.return_value = ContractSummary(
            contract_id=10,
            employee_id=50,
            employee_name="بندر الشايع",
            department_name="المالية",
            job_title="مدير مالي",
            is_saudi=True,
            nationality_text_ar="مواطن سعودي",
            contract_type_name="عقد غير محدد المدة",
            basic_wage=20000.0,
            housing_allowance=5000.0,
            transportation_allowance=2000.0,
            other_allowances=0.0,
            total_package=27000.0,
            gosi_contributory_wage=25000.0,
            gosi_employee_deduction=2437.5,
            gosi_employer_contribution=2937.5,
            net_estimated_salary=24562.5,
            date_start="2023-01-01",
            date_end=None,
            trial_date_end=None,
            is_indefinite=True,
            compliance_notes=[],
        )
        mock_get_svc.return_value = mock_svc

        response = self.client.get("/api/contracts/employee/50")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["contract"]["basic_wage"], 20000.0)
        self.assertTrue(data["contract"]["is_saudi"])

    @patch("web_service.get_contract_service_instance")
    def test_dry_run_contract_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_svc.dry_run_contract.return_value = ContractDryRunResult(
            is_valid=True,
            employee_id=50,
            employee_name="بندر الشايع",
            department_id=1,
            department_name="المالية",
            job_id=2,
            job_title="مدير مالي",
            is_saudi=True,
            nationality_text_ar="مواطن سعودي",
            basic_wage=20000.0,
            housing_allowance=5000.0,
            transportation_allowance=2000.0,
            other_allowances=0.0,
            total_package=27000.0,
            gosi_contributory_wage=25000.0,
            gosi_employee_deduction=2437.5,
            gosi_employer_contribution=2937.5,
            net_estimated_salary=24562.5,
            date_start="2026-10-01",
            date_end=None,
            trial_date_end=None,
            contract_type_id=1,
            contract_type_name="عقد غير محدد المدة",
            is_indefinite=True,
            statutory_article="المادة 55",
            statutory_explanation_ar="مطابق",
            warnings=[],
            errors=[],
            approval_token="CTR-TEST1234",
            can_proceed=True,
        )
        mock_get_svc.return_value = mock_svc

        payload = {
            "employee_id": 50,
            "basic_wage": 20000.0,
            "housing_allowance": 5000.0,
            "transportation_allowance": 2000.0,
        }
        response = self.client.post("/api/contracts/dry-run", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["result"]["approval_token"], "CTR-TEST1234")

    @patch("web_service.get_contract_service_instance")
    def test_apply_contract_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_svc.apply_contract.return_value = ContractExecutionResult(
            success=True,
            contract_id=77,
            employee_id=50,
            employee_name="بندر الشايع",
            total_package=27000.0,
            net_estimated_salary=24562.5,
            readback_verified=True,
            message_ar="تم اعتماد العقد بنجاح.",
            audit_logged=True,
        )
        mock_get_svc.return_value = mock_svc

        payload = {
            "approval_token": "CTR-TEST1234",
            "confirmation_text": "تأكيد",
        }
        headers = {"X-API-Key": "hr-write-secret-token"}
        response = self.client.post("/api/contracts/apply", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["contract_id"], 77)


if __name__ == "__main__":
    unittest.main()
