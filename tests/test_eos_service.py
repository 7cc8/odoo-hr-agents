from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from odoo_eos_write_gateway import (
    OdooEOSWriteGateway,
    EOSEnvironmentGuardError,
    EOSWriteGatewayError,
)
from eos_service import (
    EOSService,
    EOSCalculationSummary,
    EOSDryRunResult,
    EOSExecutionResult,
    detect_employee_nationality,
    calculate_service_period_components,
)
from web_service import app


class TestOdooEOSWriteGateway(unittest.TestCase):
    def test_environment_guard_blocks_unauthorized_db(self):
        with self.assertRaises(EOSEnvironmentGuardError):
            OdooEOSWriteGateway(
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

        gateway = OdooEOSWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        with self.assertRaises(EOSWriteGatewayError):
            gateway._call("hr.employee", "create", [{}])

        with self.assertRaises(EOSWriteGatewayError):
            gateway._call("hr.end.service.benefit", "unlink", [[1]])

    @patch("xmlrpc.client.ServerProxy")
    def test_create_and_read_eos_benefit(self, mock_proxy_cls):
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1
        mock_common.version.return_value = {"server_version": "19.0"}

        mock_models = MagicMock()
        mock_models.execute_kw.side_effect = [
            501,  # create returns ID
            [{"id": 501, "name": "EOS-001", "total_reward": 25000.0}],  # read returns list
            True,  # confirm returns True
        ]

        gateway = OdooEOSWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        created_id = gateway.create_end_service_benefit(
            name="EOS-001",
            employee_id=10,
            department_id=2,
            total_deserved_amount=20000.0,
            total_holiday_deserved_amount=5000.0,
            total_reward=25000.0,
        )
        self.assertEqual(created_id, 501)

        read_res = gateway.read_end_service_benefit(501)
        self.assertIsNotNone(read_res)
        self.assertEqual(read_res["id"], 501)

        conf_res = gateway.confirm_end_service_benefit(501)
        self.assertTrue(conf_res)


class TestEOSService(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.audit_log_file = str(self.tmpdir / "test_eos_audit.jsonl")
        self.mock_repo = MagicMock()
        self.mock_gateway = MagicMock()
        self.service = EOSService(
            readonly_repo=self.mock_repo,
            write_gateway=self.mock_gateway,
            audit_log_path=self.audit_log_file,
        )

    def test_nationality_detection(self):
        # 1. Saudi national ID starting with 1
        emp_saudi_id = {"identification_id": "1083920194", "country_id": [1, "Any"]}
        self.assertTrue(detect_employee_nationality(emp_saudi_id))

        # 2. Non-Saudi Iqama starting with 2
        emp_muqeem_id = {"identification_id": "2491029481", "country_id": [1, "Any"]}
        self.assertFalse(detect_employee_nationality(emp_muqeem_id))

        # 3. Country Saudi Arabia
        emp_country_sa = {"identification_id": "", "country_id": [1, "Saudi Arabia"]}
        self.assertTrue(detect_employee_nationality(emp_country_sa))

        # 4. Explicit override
        self.assertTrue(detect_employee_nationality(emp_muqeem_id, explicit_is_saudi=True))
        self.assertFalse(detect_employee_nationality(emp_saudi_id, explicit_is_saudi=False))

    def test_service_period_components(self):
        y, m, d, total_y = calculate_service_period_components("2020-01-01", "2024-01-01")
        self.assertEqual(y, 4)
        self.assertAlmostEqual(total_y, 4.0, delta=0.1)

    def test_get_employee_eos_summary(self):
        self.mock_repo.get_employee.return_value = {
            "id": 100,
            "name": "سعد الدوسري",
            "department_id": [2, "الموارد البشرية"],
            "hiring_date": "2020-01-01",
            "identification_id": "1098234512",
        }
        self.mock_repo.get_employee_eos_records.return_value = []

        summary = self.service.get_employee_eos_summary(100)
        self.assertEqual(summary.employee_id, 100)
        self.assertTrue(summary.is_saudi)
        self.assertEqual(summary.nationality_text_ar, "مواطن سعودي")
        self.assertGreaterEqual(summary.years, 6)

    def test_dry_run_saudi_employer_termination(self):
        # Termination by employer under Article 84: 100% full gratuity
        # 6 years service, 10,000 monthly wage:
        # Tier 1 (first 5 yrs): 5 * (10,000 / 2) = 25,000
        # Tier 2 (year 6): 1 * 10,000 = 10,000
        # Gratuity = 35,000
        self.mock_repo.get_employee.return_value = {
            "id": 101,
            "name": "فيصل العتيبي",
            "department_id": [3, "المبيعات"],
            "hiring_date": "2020-01-01",
            "identification_id": "1029384756",
        }

        res = self.service.dry_run_eos_settlement(
            employee_id=101,
            monthly_wage=10000.0,
            service_years=6.0,
            contract_type="indefinite",
            is_resignation=False,
            unused_leave_days=10.0,  # 10 days * (10,000 / 30) = 3,333.33
        )

        self.assertTrue(res.is_valid)
        self.assertTrue(res.can_proceed)
        self.assertTrue(res.is_saudi)
        self.assertEqual(res.gratuity_entitlement_ratio, 1.0)
        self.assertEqual(res.gratuity_net_amount, 35000.0)
        self.assertAlmostEqual(res.leave_compensation_amount, 3333.33, delta=0.1)
        self.assertAlmostEqual(res.net_settlement_amount, 38333.33, delta=0.2)
        self.assertTrue(res.approval_token.startswith("EOS-"))

    def test_dry_run_resignation_tiers_article_85(self):
        # Test resignation tiers under Article 85
        self.mock_repo.get_employee.return_value = {
            "id": 102,
            "name": "أحمد الشمري",
            "identification_id": "1011223344",
        }

        # 1. Under 2 years: 0%
        res_under2 = self.service.dry_run_eos_settlement(
            employee_id=102,
            monthly_wage=6000.0,
            service_years=1.5,
            is_resignation=True,
        )
        self.assertEqual(res_under2.gratuity_entitlement_ratio, 0.0)
        self.assertEqual(res_under2.gratuity_net_amount, 0.0)

        # 2. 3 years (between 2 and 5): 1/3
        # Gross = 3 * 3,000 = 9,000 -> 1/3 = 3,000
        res_3yr = self.service.dry_run_eos_settlement(
            employee_id=102,
            monthly_wage=6000.0,
            service_years=3.0,
            is_resignation=True,
        )
        self.assertAlmostEqual(res_3yr.gratuity_entitlement_ratio, 1.0 / 3.0, places=3)
        self.assertEqual(res_3yr.gratuity_net_amount, 3000.0)

        # 3. 6 years (between 5 and 10): 2/3
        # Gross = (5 * 3,000) + (1 * 6,000) = 21,000 -> 2/3 = 14,000
        res_6yr = self.service.dry_run_eos_settlement(
            employee_id=102,
            monthly_wage=6000.0,
            service_years=6.0,
            is_resignation=True,
        )
        self.assertAlmostEqual(res_6yr.gratuity_entitlement_ratio, 2.0 / 3.0, places=3)
        self.assertEqual(res_6yr.gratuity_net_amount, 14000.0)

        # 4. 11 years (10+): 100%
        # Gross = (5 * 3,000) + (6 * 6,000) = 51,000 -> 100% = 51,000
        res_11yr = self.service.dry_run_eos_settlement(
            employee_id=102,
            monthly_wage=6000.0,
            service_years=11.0,
            is_resignation=True,
        )
        self.assertEqual(res_11yr.gratuity_entitlement_ratio, 1.0)
        self.assertEqual(res_11yr.gratuity_net_amount, 51000.0)

    def test_dry_run_article_87_female_marriage_and_childbirth(self):
        # Female worker resigning within 6 months of marriage gets 100% even if under 2 years!
        self.mock_repo.get_employee.return_value = {
            "id": 103,
            "name": "نورة القحطاني",
            "identification_id": "1099887766",
        }

        res_marriage = self.service.dry_run_eos_settlement(
            employee_id=103,
            monthly_wage=8000.0,
            service_years=1.5,
            is_resignation=True,
            resignation_reason="marriage_female",
        )
        self.assertEqual(res_marriage.gratuity_entitlement_ratio, 1.0)
        # Gross = 1.5 * 4,000 = 6,000 -> 100% = 6,000
        self.assertEqual(res_marriage.gratuity_net_amount, 6000.0)

        # Female worker resigning within 3 months of childbirth
        res_childbirth = self.service.dry_run_eos_settlement(
            employee_id=103,
            monthly_wage=8000.0,
            service_years=3.0,
            is_resignation=True,
            resignation_reason="childbirth_female",
        )
        self.assertEqual(res_childbirth.gratuity_entitlement_ratio, 1.0)
        # Gross = 3.0 * 4,000 = 12,000 -> 100% = 12,000 (instead of 1/3 = 4,000)
        self.assertEqual(res_childbirth.gratuity_net_amount, 12000.0)

    def test_article_77_unlawful_termination_saudi_vs_non_saudi(self):
        # 1. Saudi with indefinite contract: 15 days/year (half month/year), min 2 months wage
        self.mock_repo.get_employee.return_value = {
            "id": 104,
            "name": "خالد المطيري",
            "identification_id": "1077665544",
        }
        res_saudi = self.service.dry_run_eos_settlement(
            employee_id=104,
            monthly_wage=10000.0,
            service_years=5.0,
            contract_type="indefinite",
            is_unlawful_termination=True,
        )
        # 5 years * (10,000 / 2) = 25,000 Article 77 compensation (higher than 2 months min 20,000)
        self.assertEqual(res_saudi.article_77_amount, 25000.0)

        # 2. Non-Saudi: contract is fixed under Article 37.
        # If 4 months remaining in contract: 4 * 10,000 = 40,000
        self.mock_repo.get_employee.return_value = {
            "id": 105,
            "name": "محمد رضوان",
            "identification_id": "2088776655",  # Starts with 2 -> Non-Saudi
        }
        res_non_saudi = self.service.dry_run_eos_settlement(
            employee_id=105,
            monthly_wage=10000.0,
            service_years=3.0,
            contract_type="fixed",
            is_unlawful_termination=True,
            remaining_contract_months=4.0,
        )
        self.assertFalse(res_non_saudi.is_saudi)
        self.assertEqual(res_non_saudi.nationality_text_ar, "وافد غير سعودي (مقيم)")
        self.assertEqual(res_non_saudi.article_77_amount, 40000.0)

        # 3. Minimum 2 months wage check:
        # If remaining months is 1 month (1 * 10,000 = 10,000), minimum is 2 months (20,000)
        res_min = self.service.dry_run_eos_settlement(
            employee_id=105,
            monthly_wage=10000.0,
            service_years=3.0,
            contract_type="fixed",
            is_unlawful_termination=True,
            remaining_contract_months=1.0,
        )
        self.assertEqual(res_min.article_77_amount, 20000.0)

    def test_apply_eos_settlement_four_eyes_and_audit(self):
        self.mock_repo.get_employee.return_value = {
            "id": 106,
            "name": "سلطان الغامدي",
            "department_id": [2, "العمليات"],
            "identification_id": "1066554433",
        }
        self.mock_gateway.create_end_service_benefit.return_value = 888
        self.mock_gateway.read_end_service_benefit.return_value = {"id": 888, "name": "EOS-202610-001"}

        dry = self.service.dry_run_eos_settlement(
            employee_id=106,
            monthly_wage=9000.0,
            service_years=4.0,
        )
        token = dry.approval_token
        self.assertTrue(token)

        # 1. Rejection without "تأكيد"
        exec_fail = self.service.apply_eos_settlement(approval_token=token, user_confirmation_text="نعم")
        self.assertFalse(exec_fail.success)
        self.assertIn("تأكيد", exec_fail.message_ar)

        # 2. Execution with exact "تأكيد"
        exec_success = self.service.apply_eos_settlement(approval_token=token, user_confirmation_text="تأكيد")
        self.assertTrue(exec_success.success)
        self.assertEqual(exec_success.eos_id, 888)
        self.assertTrue(exec_success.readback_verified)
        self.assertTrue(exec_success.audit_logged)

        # Check audit log written to file
        self.assertTrue(Path(self.audit_log_file).exists())
        with open(self.audit_log_file, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f]
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["eos_id"], 888)
            self.assertEqual(lines[0]["employee_id"], 106)


class TestEOSAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("web_service.get_eos_service_instance")
    def test_get_eos_summary_api(self, mock_service_fn):
        mock_srv = MagicMock()
        mock_srv.get_employee_eos_summary.return_value = EOSCalculationSummary(
            employee_id=100,
            employee_name="سعد الدوسري",
            department_name="الموارد البشرية",
            is_saudi=True,
            nationality_text_ar="مواطن سعودي",
            hiring_date="2020-01-01",
            settlement_date="2026-10-06",
            years=6,
            months=9,
            days=5,
            service_years=6.75,
            last_gross_wage=8000.0,
            eos_records_count=0,
            recent_records=[],
        )
        mock_service_fn.return_value = mock_srv

        resp = self.client.get("/api/eos/summary/100")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["summary"]["employee_name"], "سعد الدوسري")
        self.assertTrue(data["summary"]["is_saudi"])

    @patch("web_service.get_eos_service_instance")
    def test_post_eos_dry_run_api(self, mock_service_fn):
        mock_srv = MagicMock()
        mock_srv.dry_run_eos_settlement.return_value = EOSDryRunResult(
            is_valid=True,
            employee_id=100,
            employee_name="سعد الدوسري",
            department_id=2,
            department_name="الموارد البشرية",
            is_saudi=True,
            nationality_text_ar="مواطن سعودي",
            contract_type="indefinite",
            hiring_date="2020-01-01",
            settlement_date="2026-10-06",
            years=6,
            months=9,
            days=5,
            service_period=6.75,
            monthly_wage=8000.0,
            daily_wage=266.67,
            is_resignation=False,
            resignation_reason="standard",
            gratuity_entitlement_ratio=1.0,
            gratuity_base_amount=34000.0,
            gratuity_net_amount=34000.0,
            gratuity_explanation_ar="المادة 84 استحقاق كامل",
            is_unlawful_termination=False,
            remaining_contract_months=0.0,
            article_77_amount=0.0,
            article_77_formula="",
            article_77_explanation_ar="",
            unused_leave_days=5.0,
            leave_compensation_amount=1333.35,
            unpaid_salary_days=0.0,
            unpaid_salary_amount=0.0,
            other_deductions_amount=0.0,
            net_settlement_amount=35333.35,
            statutory_summary_ar="تسوية معتمدة",
            approval_token="EOS-TESTTOKEN1",
            can_proceed=True,
        )
        mock_service_fn.return_value = mock_srv

        payload = {
            "employee_id": 100,
            "monthly_wage": 8000.0,
            "contract_type": "indefinite",
            "is_resignation": False,
            "unused_leave_days": 5.0,
        }
        resp = self.client.post("/api/eos/dry-run", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["result"]["approval_token"], "EOS-TESTTOKEN1")
        self.assertEqual(data["result"]["net_settlement_amount"], 35333.35)

    @patch("web_service.get_eos_service_instance")
    def test_post_eos_apply_api(self, mock_service_fn):
        mock_srv = MagicMock()
        mock_srv.apply_eos_settlement.return_value = EOSExecutionResult(
            success=True,
            eos_id=999,
            reference="EOS-202610-ABCD",
            employee_id=100,
            employee_name="سعد الدوسري",
            is_saudi=True,
            total_settlement_amount=35333.35,
            state="confirmed",
            readback_verified=True,
            message_ar="تم اعتماد التسوية بنجاح",
            audit_logged=True,
        )
        mock_service_fn.return_value = mock_srv

        payload = {
            "approval_token": "EOS-TESTTOKEN1",
            "confirmation_text": "تأكيد",
            "state": "confirmed",
        }
        headers = {"Authorization": "Bearer unit-test-write-token"}
        resp = self.client.post("/api/eos/apply", json=payload, headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["eos_id"], 999)
        self.assertTrue(data["readback_verified"])


if __name__ == "__main__":
    unittest.main()
