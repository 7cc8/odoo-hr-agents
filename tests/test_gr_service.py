from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from odoo_gr_write_gateway import (
    OdooGRWriteGateway,
    GREnvironmentGuardError,
    GRWriteGatewayError,
)
from gr_service import (
    GRService,
    GRTransactionSummary,
    GRDryRunResult,
    GRExecutionResult,
    STANDARD_GOV_FEES,
)
from web_service import app


class TestOdooGRWriteGateway(unittest.TestCase):
    def test_environment_guard_blocks_unauthorized_db(self):
        with self.assertRaises(GREnvironmentGuardError):
            OdooGRWriteGateway(
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

        gateway = OdooGRWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        with self.assertRaises(GRWriteGatewayError):
            gateway._call("hr.employee", "create", [{}])

        with self.assertRaises(GRWriteGatewayError):
            gateway._call("gr.transaction", "unlink", [[1]])

    @patch("xmlrpc.client.ServerProxy")
    def test_create_and_read_gr_transaction(self, mock_proxy_cls):
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1
        mock_common.version.return_value = {"server_version": "19.0"}

        mock_models = MagicMock()
        mock_models.execute_kw.side_effect = [
            701,  # create returns ID
            [{"id": 701, "transaction": "تجديد إقامة", "amount": 650.0, "state": "draft"}],  # read
            True,  # confirm returns True
        ]

        gateway = OdooGRWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        created_id = gateway.create_gr_transaction(
            employee_id=12,
            transaction="تجديد إقامة",
            transaction_type="party",
            responsible_party="company",
            amount=650.0,
        )
        self.assertEqual(created_id, 701)

        read_res = gateway.read_gr_transaction(701)
        self.assertIsNotNone(read_res)
        self.assertEqual(read_res["id"], 701)

        conf_res = gateway.confirm_gr_transaction(701)
        self.assertTrue(conf_res)


class TestGRService(unittest.TestCase):
    def setUp(self):
        self.mock_repo = MagicMock()
        self.mock_gw = MagicMock()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_log_path = Path(self.temp_dir.name) / "gr_audit.jsonl"
        self.service = GRService(
            readonly_repo=self.mock_repo,
            write_gateway=self.mock_gw,
            audit_log_path=str(self.audit_log_path),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_summary_returns_employee_history_and_nationality(self):
        self.mock_repo.get_employee.return_value = {
            "id": 10,
            "name": "سعد الشمري",
            "department_id": [2, "الموارد البشرية"],
            "identification_id": "1098765432",
            "country_id": [1, "Saudi Arabia"],
        }
        self.mock_repo.get_employee_gr_transactions.return_value = [
            {"id": 1, "transaction": "توثيق عقد عمل في قوى", "amount": 0.0, "state": "confirmed"}
        ]

        summary = self.service.get_employee_gr_summary(10)
        self.assertEqual(summary.employee_id, 10)
        self.assertEqual(summary.employee_name, "سعد الشمري")
        self.assertTrue(summary.is_saudi)
        self.assertEqual(summary.nationality_text_ar, "مواطن سعودي")
        self.assertEqual(summary.total_transactions_count, 1)

    def test_saudi_blocked_from_expat_only_transactions(self):
        """حظر معاملات الجوازات ومقيم والإقامة للمواطنين السعوديين نظاماً."""
        self.mock_repo.get_employee.return_value = {
            "id": 10,
            "name": "أحمد الشهري",
            "department_id": [2, "التقنية"],
            "country_id": [1, "Saudi Arabia"],
        }

        # Attempting Iqama renewal for a Saudi Citizen
        res = self.service.dry_run_gr_transaction(
            employee_id=10,
            transaction="تجديد إقامة",
            explicit_is_saudi=True,
        )
        self.assertFalse(res.is_valid)
        self.assertFalse(res.can_proceed)
        self.assertTrue(any("حظر نظامي" in e for e in res.errors))

        # Attempting Exit and Re-Entry Visa for a Saudi Citizen
        res_visa = self.service.dry_run_gr_transaction(
            employee_id=10,
            transaction="تأشيرة خروج وعودة",
            explicit_is_saudi=True,
        )
        self.assertFalse(res_visa.is_valid)
        self.assertTrue(any("حظر نظامي" in e for e in res_visa.errors))

    def test_saudi_allowed_general_transactions(self):
        """السماح بالمعاملات النظامية العامة للسعوديين مثل توثيق قوى والتأمينات."""
        self.mock_repo.get_employee.return_value = {
            "id": 10,
            "name": "أحمد الشهري",
            "department_id": [2, "التقنية"],
            "country_id": [1, "Saudi Arabia"],
        }

        res = self.service.dry_run_gr_transaction(
            employee_id=10,
            transaction="توثيق عقد عمل في قوى",
            explicit_is_saudi=True,
        )
        self.assertTrue(res.is_valid)
        self.assertTrue(res.can_proceed)
        self.assertEqual(res.amount_sar, 0.0)
        self.assertTrue(res.approval_token.startswith("GR-"))

    def test_expat_iqama_renewal_article_40_warning_on_employee_charge(self):
        """الوافد: فحص المادة 40 فقرة (1) عند تحميل العامل رسوم الإقامة ورخص العمل."""
        self.mock_repo.get_employee.return_value = {
            "id": 20,
            "name": "محمد كمال",
            "department_id": [3, "المبيعات"],
            "country_id": [64, "Egypt"],
        }

        # Case 1: Company bears the fee (Standard & Compliant)
        res_comp = self.service.dry_run_gr_transaction(
            employee_id=20,
            transaction="تجديد إقامة",
            responsible_party="company",
            explicit_is_saudi=False,
        )
        self.assertTrue(res_comp.is_valid)
        self.assertEqual(res_comp.amount_sar, 650.0)
        self.assertEqual(res_comp.company_share_sar, 650.0)
        self.assertEqual(res_comp.employee_share_sar, 0.0)
        self.assertEqual(len(res_comp.warnings), 0)

        # Case 2: Employee charged fee (Triggers Article 40 warning)
        res_emp = self.service.dry_run_gr_transaction(
            employee_id=20,
            transaction="تجديد إقامة",
            responsible_party="employee",
            explicit_is_saudi=False,
        )
        self.assertTrue(res_emp.is_valid)
        self.assertTrue(any("المادة 40" in w for w in res_emp.warnings))
        self.assertEqual(res_emp.employee_share_sar, 650.0)

    def test_split_percentage_calculation(self):
        """فحص تقسيم الرسوم بنسب مئوية (split)."""
        self.mock_repo.get_employee.return_value = {
            "id": 20,
            "name": "محمد كمال",
            "department_id": [3, "المبيعات"],
            "country_id": [64, "Egypt"],
        }

        res = self.service.dry_run_gr_transaction(
            employee_id=20,
            transaction="تأشيرة خروج وعودة متعددة",
            amount=500.0,
            transaction_type="split",
            company_percentage=60.0,
            employee_percentage=40.0,
            explicit_is_saudi=False,
        )
        self.assertTrue(res.is_valid)
        self.assertEqual(res.company_share_sar, 300.0)
        self.assertEqual(res.employee_share_sar, 200.0)

    def test_apply_requires_explicit_written_confirmation(self):
        """رفض الاعتماد دون كلمة 'تأكيد' صريحة (مبدأ العينين الأربع)."""
        self.mock_repo.get_employee.return_value = {
            "id": 20,
            "name": "محمد كمال",
            "department_id": [3, "المبيعات"],
            "country_id": [64, "Egypt"],
        }
        dry_res = self.service.dry_run_gr_transaction(
            employee_id=20,
            transaction="تجديد إقامة",
            explicit_is_saudi=False,
        )
        token = dry_res.approval_token

        # Without 'تأكيد'
        exec_res = self.service.apply_gr_transaction(token, user_confirmation_text="نعم")
        self.assertFalse(exec_res.success)
        self.assertIn("مرفوض", exec_res.message_ar)

        # With 'تأكيد'
        self.mock_gw.create_gr_transaction.return_value = 888
        self.mock_gw.read_gr_transaction.return_value = {"id": 888, "state": "confirmed"}
        self.mock_gw.confirm_gr_transaction.return_value = True

        exec_succ = self.service.apply_gr_transaction(token, user_confirmation_text="تأكيد")
        self.assertTrue(exec_succ.success)
        self.assertEqual(exec_succ.transaction_id, 888)
        self.assertTrue(exec_succ.readback_verified)
        self.assertTrue(exec_succ.audit_logged)
        self.assertTrue(self.audit_log_path.exists())


class TestGRAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("web_service.get_gr_service_instance")
    def test_api_common_transactions(self, mock_get_srv):
        resp = self.client.get("/api/gr/common-transactions")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("تجديد إقامة", data["transactions"])

    @patch("web_service.get_gr_service_instance")
    def test_api_summary(self, mock_get_srv):
        mock_srv = MagicMock()
        mock_srv.get_employee_gr_summary.return_value = GRTransactionSummary(
            employee_id=15,
            employee_name="خالد العتيبي",
            department_name="المبيعات",
            is_saudi=True,
            nationality_text_ar="مواطن سعودي",
            identification_id="1011122233",
            total_transactions_count=2,
            recent_transactions=[],
        )
        mock_get_srv.return_value = mock_srv

        resp = self.client.get("/api/gr/summary/15")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["summary"]["employee_name"], "خالد العتيبي")
        self.assertTrue(data["summary"]["is_saudi"])

    @patch("web_service.get_gr_service_instance")
    def test_api_dry_run(self, mock_get_srv):
        mock_srv = MagicMock()
        mock_srv.dry_run_gr_transaction.return_value = GRDryRunResult(
            is_valid=True,
            employee_id=22,
            employee_name="جون دو",
            department_id=3,
            department_name="العمليات",
            is_saudi=False,
            nationality_text_ar="وافد غير سعودي (مقيم)",
            transaction="تجديد إقامة",
            transaction_type="party",
            transaction_date="2026-10-06",
            responsible_party="company",
            company_percentage=100.0,
            employee_percentage=0.0,
            amount_sar=650.0,
            company_share_sar=650.0,
            employee_share_sar=0.0,
            statutory_article="المادة 40",
            statutory_explanation_ar="رسوم التجديد",
            approval_token="GR-TEST1234",
            can_proceed=True,
        )
        mock_get_srv.return_value = mock_srv

        resp = self.client.post(
            "/api/gr/dry-run",
            json={"employee_id": 22, "transaction": "تجديد إقامة"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["result"]["approval_token"], "GR-TEST1234")

    @patch("web_service.get_gr_service_instance")
    def test_api_apply(self, mock_get_srv):
        mock_srv = MagicMock()
        mock_srv.apply_gr_transaction.return_value = GRExecutionResult(
            success=True,
            transaction_id=909,
            reference="GR-202610-001",
            employee_id=22,
            employee_name="جون دو",
            transaction="تجديد إقامة",
            amount_sar=650.0,
            state="confirmed",
            readback_verified=True,
            message_ar="تم التسجيل بنجاح",
            audit_logged=True,
        )
        mock_get_srv.return_value = mock_srv

        resp = self.client.post(
            "/api/gr/apply",
            json={"approval_token": "GR-TEST1234", "confirmation_text": "تأكيد"},
            headers={"X-API-Key": "unit-test-write-token"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["transaction_id"], 909)


if __name__ == "__main__":
    unittest.main()
