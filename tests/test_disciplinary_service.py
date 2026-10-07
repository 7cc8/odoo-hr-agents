from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from odoo_disciplinary_write_gateway import (
    OdooDisciplinaryWriteGateway,
    DisciplinaryEnvironmentGuardError,
    DisciplinaryWriteGatewayError,
)
from disciplinary_service import (
    DisciplinaryService,
    DisciplinaryActionSummary,
    DisciplinaryDryRunResult,
    DisciplinaryExecutionResult,
)


class TestDisciplinaryWriteGateway(unittest.TestCase):
    def test_environment_guard_blocks_unauthorized_db(self):
        with self.assertRaises(DisciplinaryEnvironmentGuardError):
            OdooDisciplinaryWriteGateway(
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

        gateway = OdooDisciplinaryWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        with self.assertRaises(DisciplinaryWriteGatewayError):
            gateway._call("hr.employee", "create", [{}])

        with self.assertRaises(DisciplinaryWriteGatewayError):
            gateway._call("disciplinary.action", "unlink", [[1]])

    @patch("xmlrpc.client.ServerProxy")
    def test_create_and_read_disciplinary_action(self, mock_proxy_cls):
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1
        mock_common.version.return_value = {"server_version": "19.0"}

        mock_models = MagicMock()
        mock_models.execute_kw.side_effect = [
            101,  # create returns ID
            [{"id": 101, "name": "DISC-001", "number_of_days": 1.0}],  # read returns list
        ]

        gateway = OdooDisciplinaryWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        created_id = gateway.create_disciplinary_action(
            name="DISC-001",
            employee_id=10,
            department_id=2,
            discipline_date="2026-10-06",
            discipline_reason="تأخر غير مبرر",
            number_of_days=1.0,
        )
        self.assertEqual(created_id, 101)

        read_res = gateway.read_disciplinary_action(101)
        self.assertIsNotNone(read_res)
        self.assertEqual(read_res["id"], 101)


class TestDisciplinaryService(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.audit_log_file = str(self.tmpdir / "test_disciplinary_audit.jsonl")
        self.mock_repo = MagicMock()
        self.mock_gateway = MagicMock()
        self.service = DisciplinaryService(
            readonly_repo=self.mock_repo,
            write_gateway=self.mock_gateway,
            audit_log_path=self.audit_log_file,
        )

    def test_get_employee_disciplinary_summary(self):
        self.mock_repo.get_employee.return_value = {
            "id": 15,
            "name": "عمر السالم",
            "department_id": [3, "المبيعات"],
        }
        self.mock_repo.get_employee_disciplinary_actions.return_value = [
            {"id": 1, "discipline_date": "2026-10-02", "number_of_days": 1.0, "state": "action"},
            {"id": 2, "discipline_date": "2026-09-15", "number_of_days": 2.0, "state": "action"},
        ]

        summary = self.service.get_employee_disciplinary_summary(
            employee_id=15,
            reference_date="2026-10-06",
            daily_wage=250.0,
        )

        self.assertEqual(summary.employee_name, "عمر السالم")
        self.assertEqual(summary.department_name, "المبيعات")
        self.assertEqual(summary.current_month_deductions_days, 1.0)
        self.assertEqual(summary.remaining_month_deduction_allowance_days, 4.0)

    def test_dry_run_rejects_exceeding_single_infraction_cap(self):
        """المادة 70: حظر تجاوز الخصم 5 أيام عن المخالفة الواحدة"""
        self.mock_repo.get_employee.return_value = {
            "id": 15,
            "name": "عمر السالم",
            "department_id": [3, "المبيعات"],
        }
        self.mock_repo.get_employee_disciplinary_actions.return_value = []

        res = self.service.dry_run_disciplinary_action(
            employee_id=15,
            discipline_date="2026-10-06",
            discipline_reason="غياب متكرر",
            number_of_days=6.0,  # يتجاوز 5 أيام!
        )

        self.assertFalse(res.is_valid)
        self.assertFalse(res.can_proceed)
        self.assertTrue(any("70" in e for e in res.errors))
        self.assertTrue(any("5 أيام" in e for e in res.errors))

    def test_dry_run_rejects_exceeding_monthly_cumulative_cap(self):
        """المادة 70: حظر تجاوز إجمالي الخصومات 5 أيام في الشهر الواحد"""
        self.mock_repo.get_employee.return_value = {
            "id": 15,
            "name": "عمر السالم",
            "department_id": [3, "المبيعات"],
        }
        # خصم سابق في نفس الشهر 3 أيام
        self.mock_repo.get_employee_disciplinary_actions.return_value = [
            {"id": 1, "discipline_date": "2026-10-02", "number_of_days": 3.0, "state": "action"}
        ]

        # خصم جديد 3 أيام -> الإجمالي 6 أيام في الشهر (تجاوز السقف 5)
        res = self.service.dry_run_disciplinary_action(
            employee_id=15,
            discipline_date="2026-10-08",
            discipline_reason="مخالفة تعليمات",
            number_of_days=3.0,
        )

        self.assertFalse(res.is_valid)
        self.assertTrue(any("70" in e for e in res.errors))

    def test_dry_run_success_and_occurrence_reset_after_180_days(self):
        """المادة 71: سقوط أثر تكرار المخالفة إذا انقضى 180 يوماً"""
        self.mock_repo.get_employee.return_value = {
            "id": 15,
            "name": "عمر السالم",
            "department_id": [3, "المبيعات"],
        }
        # مخالفة سابقة قبل 200 يوم
        self.mock_repo.get_employee_disciplinary_actions.return_value = [
            {"id": 1, "discipline_date": "2026-01-01", "number_of_days": 1.0, "state": "action"}
        ]

        res = self.service.dry_run_disciplinary_action(
            employee_id=15,
            discipline_date="2026-10-06",
            discipline_reason="تأخر بسيط",
            number_of_days=1.0,
        )

        self.assertTrue(res.is_valid)
        self.assertTrue(res.can_proceed)
        self.assertEqual(res.occurrence, "first")
        self.assertIn("180 يوماً", res.occurrence_explanation_ar)
        self.assertTrue(res.approval_token.startswith("DISC-"))

    def test_apply_disciplinary_action_requires_written_confirmation(self):
        """Four-Eyes Principle: اشتراط تأكيد كتابي"""
        res = self.service.apply_disciplinary_action(
            approval_token="DISC-123",
            user_confirmation_text="نعم",  # ليس "تأكيد"
        )
        self.assertFalse(res.success)
        self.assertIn("تأكيد", res.message_ar)

    def test_apply_disciplinary_action_success_flow(self):
        """التنفيذ الناجح مع التحقق المستقل والتوثيق الرقابي"""
        self.mock_repo.get_employee.return_value = {
            "id": 15,
            "name": "عمر السالم",
            "department_id": [3, "المبيعات"],
        }
        self.mock_repo.get_employee_disciplinary_actions.return_value = []

        dry_res = self.service.dry_run_disciplinary_action(
            employee_id=15,
            discipline_date="2026-10-06",
            discipline_reason="إهمال في أداء الواجب",
            number_of_days=2.0,
            daily_wage=300.0,
        )
        self.assertTrue(dry_res.is_valid)
        token = dry_res.approval_token

        self.mock_gateway.create_disciplinary_action.return_value = 999
        self.mock_gateway.read_disciplinary_action.return_value = {
            "id": 999,
            "name": dry_res.name,
            "number_of_days": 2.0,
        }

        exec_res = self.service.apply_disciplinary_action(
            approval_token=token,
            user_confirmation_text="تأكيد",
        )

        self.assertTrue(exec_res.success)
        self.assertEqual(exec_res.action_id, 999)
        self.assertTrue(exec_res.readback_verified)
        self.assertTrue(exec_res.audit_logged)

        # التحقق من كتابة ملف التدقيق
        self.assertTrue(Path(self.audit_log_file).exists())
        log_content = Path(self.audit_log_file).read_text(encoding="utf-8")
        self.assertIn("999", log_content)
        self.assertIn(token, log_content)

    def test_api_disciplinary_endpoints(self):
        """اختبار تكامل نقاط نهاية FastAPI للجزاءات والمخالفات"""
        from fastapi.testclient import TestClient
        from web_service import app
        import web_service

        web_service._global_disciplinary_service = self.service
        client = TestClient(app)

        self.mock_repo.get_discipline_categories.return_value = [
            {"id": 1, "code": "ATTEND", "name": "مخالفات الحضور والانصراف"}
        ]
        self.mock_repo.get_employee.return_value = {
            "id": 15,
            "name": "عمر السالم",
            "department_id": [3, "المبيعات"],
        }
        self.mock_repo.get_employee_disciplinary_actions.return_value = []

        # 1. اختبار التصنيفات
        resp_cat = client.get("/api/disciplinary/categories")
        self.assertEqual(resp_cat.status_code, 200)
        self.assertEqual(resp_cat.json()["categories"][0]["code"], "ATTEND")

        # 2. اختبار ملخص الموظف
        resp_sum = client.get("/api/disciplinary/summary/15")
        self.assertEqual(resp_sum.status_code, 200)
        self.assertEqual(resp_sum.json()["summary"]["employee_name"], "عمر السالم")

        # 3. اختبار الفحص التجريبي Dry Run
        payload_dry = {
            "employee_id": 15,
            "discipline_date": "2026-10-06",
            "discipline_reason": "تأخر متكرر",
            "number_of_days": 1.0,
            "daily_wage": 300.0,
        }
        resp_dry = client.post("/api/disciplinary/dry-run", json=payload_dry)
        self.assertEqual(resp_dry.status_code, 200)
        data_dry = resp_dry.json()
        self.assertEqual(data_dry["status"], "success")
        token = data_dry["result"]["approval_token"]
        self.assertTrue(token.startswith("DISC-"))

        # 4. اختبار الاعتماد النهائي مع مفتاح API وكلمة 'تأكيد'
        self.mock_gateway.create_disciplinary_action.return_value = 555
        self.mock_gateway.read_disciplinary_action.return_value = {"id": 555, "name": "DISC-TEST"}

        headers = {"X-API-Key": web_service.WRITE_API_TOKEN}
        resp_apply = client.post(
            "/api/disciplinary/apply",
            json={"approval_token": token, "confirmation_text": "تأكيد", "state": "action"},
            headers=headers
        )
        self.assertEqual(resp_apply.status_code, 200)
        data_apply = resp_apply.json()
        self.assertEqual(data_apply["status"], "success")
        self.assertEqual(data_apply["action_id"], 555)


if __name__ == "__main__":
    unittest.main()

