from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from odoo_appraisal_write_gateway import (
    OdooAppraisalWriteGateway,
    AppraisalEnvironmentGuardError,
    AppraisalWriteGatewayError,
)
from appraisal_service import (
    AppraisalService,
    AppraisalSummary,
    AppraisalDryRunResult,
    AppraisalExecutionResult,
    APPRAISAL_RATING_TIERS,
    calculate_weighted_score,
    determine_appraisal_rating,
)
from web_service import app


class TestOdooAppraisalWriteGateway(unittest.TestCase):
    def test_environment_guard_blocks_unauthorized_db(self):
        with self.assertRaises(AppraisalEnvironmentGuardError):
            OdooAppraisalWriteGateway(
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

        gateway = OdooAppraisalWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        with self.assertRaises(AppraisalWriteGatewayError):
            gateway._call("hr.employee", "create", [{}])

        with self.assertRaises(AppraisalWriteGatewayError):
            gateway._call("appraisal.request", "unlink", [[1]])

    @patch("xmlrpc.client.ServerProxy")
    def test_create_and_read_appraisal_request(self, mock_proxy_cls):
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1
        mock_common.version.return_value = {"server_version": "19.0"}

        mock_models = MagicMock()
        mock_models.execute_kw.side_effect = [
            801,  # create returns ID
            [{"id": 801, "name": "تقييم سنوي", "final_percentage": 92.0, "state": "draft"}],  # read
            True,  # complete returns True
        ]

        gateway = OdooAppraisalWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        created_id = gateway.create_appraisal_request(
            employee_id=14,
            name="تقييم سنوي",
            final_percentage=92.0,
        )
        self.assertEqual(created_id, 801)

        read_res = gateway.read_appraisal_request(801)
        self.assertIsNotNone(read_res)
        self.assertEqual(read_res["id"], 801)

        comp_res = gateway.complete_appraisal_request(801)
        self.assertTrue(comp_res)


class TestAppraisalService(unittest.TestCase):
    def setUp(self):
        self.mock_repo = MagicMock()
        self.mock_gw = MagicMock()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_log_path = Path(self.temp_dir.name) / "appraisal_audit.jsonl"
        self.service = AppraisalService(
            readonly_repo=self.mock_repo,
            write_gateway=self.mock_gw,
            audit_log_path=str(self.audit_log_path),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_calculate_weighted_score(self):
        # 70% KPI + 30% Competencies
        score = calculate_weighted_score(kpi_score=90.0, competency_score=80.0, kpi_weight=0.70, competency_weight=0.30)
        self.assertEqual(score, 87.0)

        # Clamping
        score_clamped = calculate_weighted_score(kpi_score=120.0, competency_score=-10.0)
        self.assertEqual(score_clamped, 70.0)

    def test_determine_appraisal_rating(self):
        self.assertEqual(determine_appraisal_rating(95.0), ("excellent", "ممتاز"))
        self.assertEqual(determine_appraisal_rating(85.0), ("very_good", "جيد جداً"))
        self.assertEqual(determine_appraisal_rating(75.0), ("good", "جيد"))
        self.assertEqual(determine_appraisal_rating(65.0), ("acceptable", "مقبول"))
        self.assertEqual(determine_appraisal_rating(50.0), ("unsatisfactory", "غير مرضٍ"))

    def test_summary_returns_employee_history_and_probation_status(self):
        self.mock_repo.get_employee.return_value = {
            "id": 10,
            "name": "سعد الشمري",
            "department_id": [2, "الموارد البشرية"],
            "job_id": [5, "أخصائي توظيف"],
            "identification_id": "1098765432",
            "country_id": [1, "Saudi Arabia"],
            "create_date": "2026-09-01",
        }
        self.mock_repo.get_employee_contracts.return_value = [
            {"date_start": "2026-09-01"}
        ]
        self.mock_repo.get_employee_appraisals.return_value = [
            {"id": 1, "name": "تقييم سنوي", "final_percentage": 88.0, "state": "completed"}
        ]

        summary = self.service.get_employee_appraisal_summary(10)
        self.assertEqual(summary.employee_id, 10)
        self.assertEqual(summary.employee_name, "سعد الشمري")
        self.assertTrue(summary.is_saudi)
        self.assertTrue(summary.in_probation_period)  # Less than 180 days since Sept 2026
        self.assertEqual(summary.total_appraisals_count, 1)
        self.assertEqual(summary.last_score, 88.0)
        self.assertEqual(summary.last_rating_ar, "جيد جداً")

    def test_probation_appraisal_pass_confirms_employee_article_53(self):
        """اجتياز فترة التجربة (المادة 53): النتيجة >= 70% توصي بتثبيت الموظف."""
        self.mock_repo.get_employee.return_value = {
            "id": 10,
            "name": "أحمد الشهري",
            "department_id": [2, "التقنية"],
            "country_id": [1, "Saudi Arabia"],
        }
        self.mock_repo.get_employee_contracts.return_value = [{"date_start": "2026-08-01"}]

        res = self.service.dry_run_appraisal(
            employee_id=10,
            appraisal_type="probation",
            kpi_score=85.0,
            competency_score=80.0,
            explicit_is_saudi=True,
        )
        self.assertTrue(res.is_valid)
        self.assertTrue(res.can_proceed)
        self.assertIn("المادة 53", res.statutory_article)
        self.assertIn("تثبيت الموظف", res.recommendation_ar)
        self.assertTrue(res.approval_token.startswith("APR-"))

    def test_probation_appraisal_fail_article_53(self):
        """رسوب فترة التجربة: النتيجة < 70% توصي بإنهاء العقد م/53 أو التمديد حتى 180 يوماً."""
        self.mock_repo.get_employee.return_value = {
            "id": 10,
            "name": "أحمد الشهري",
            "department_id": [2, "التقنية"],
            "country_id": [1, "Saudi Arabia"],
        }
        self.mock_repo.get_employee_contracts.return_value = [{"date_start": "2026-09-01"}]

        res = self.service.dry_run_appraisal(
            employee_id=10,
            appraisal_type="probation",
            kpi_score=50.0,
            competency_score=55.0,
            explicit_is_saudi=True,
        )
        self.assertTrue(res.is_valid)
        self.assertIn("المادة 53", res.statutory_article)
        self.assertIn("إنهاء العقد خلال فترة التجربة", res.recommendation_ar)

    def test_saudi_citizen_annual_appraisal_differentiation(self):
        """المواطن السعودي: أولوية الترقية والتعاقب الوظيفي، وخطة PIP عند التقييم غير المرضي."""
        self.mock_repo.get_employee.return_value = {
            "id": 10,
            "name": "سلطان المطيري",
            "department_id": [2, "التقنية"],
            "country_id": [1, "Saudi Arabia"],
        }
        self.mock_repo.get_employee_contracts.return_value = [{"date_start": "2024-01-01"}]

        # Excellent evaluation
        res_high = self.service.dry_run_appraisal(
            employee_id=10,
            appraisal_type="annual",
            kpi_score=95.0,
            competency_score=92.0,
            explicit_is_saudi=True,
        )
        self.assertTrue(res_high.is_valid)
        self.assertIn("ترشيح للترقية", res_high.recommendation_ar)
        self.assertIn("التعاقب الوظيفي", res_high.recommendation_ar)

        # Unsatisfactory evaluation -> Mandatory PIP for Saudi Citizen
        res_low = self.service.dry_run_appraisal(
            employee_id=10,
            appraisal_type="annual",
            kpi_score=45.0,
            competency_score=50.0,
            explicit_is_saudi=True,
        )
        self.assertTrue(res_low.is_valid)
        self.assertIn("خطة تصحيحية مشددة (PIP)", res_low.recommendation_ar)
        self.assertTrue(any("حماية الكفاءات الوطنية" in w or "خطة تحسين أداء" in w for w in res_low.warnings))

    def test_expat_annual_appraisal_differentiation(self):
        """الوافد غير السعودي: ربط التقييم بتجديد العقد (المادة 37) أو الإشعار بعدم التجديد (المادة 75)."""
        self.mock_repo.get_employee.return_value = {
            "id": 20,
            "name": "جون ديفيد",
            "department_id": [3, "المبيعات"],
            "country_id": [75, "United Kingdom"],
        }
        self.mock_repo.get_employee_contracts.return_value = [{"date_start": "2024-01-01"}]

        # Excellent evaluation -> Contract Renewal
        res_high = self.service.dry_run_appraisal(
            employee_id=20,
            appraisal_type="annual",
            kpi_score=92.0,
            competency_score=90.0,
            explicit_is_saudi=False,
        )
        self.assertTrue(res_high.is_valid)
        self.assertIn("تجديد عقد العمل المحدد المدة (المادة 37)", res_high.recommendation_ar)

        # Unsatisfactory evaluation -> Non-renewal recommendation
        res_low = self.service.dry_run_appraisal(
            employee_id=20,
            appraisal_type="annual",
            kpi_score=50.0,
            competency_score=40.0,
            explicit_is_saudi=False,
        )
        self.assertTrue(res_low.is_valid)
        self.assertIn("إشعار الموظف بعدم الرغبة في تجديد العقد", res_low.recommendation_ar)
        self.assertTrue(any("المادة 75 والمادة 37" in w for w in res_low.warnings))

    def test_apply_requires_explicit_written_confirmation(self):
        """رفض الاعتماد دون كلمة 'تأكيد' صريحة (مبدأ العينين الأربع)."""
        self.mock_repo.get_employee.return_value = {
            "id": 10,
            "name": "فهد السبيعي",
            "department_id": [2, "التقنية"],
            "country_id": [1, "Saudi Arabia"],
        }
        dry_res = self.service.dry_run_appraisal(
            employee_id=10,
            appraisal_type="annual",
            kpi_score=88.0,
            competency_score=85.0,
            explicit_is_saudi=True,
        )
        token = dry_res.approval_token

        # Without 'تأكيد'
        exec_res = self.service.apply_appraisal(token, user_confirmation_text="موافق")
        self.assertFalse(exec_res.success)
        self.assertIn("مرفوض", exec_res.message_ar)

        # With 'تأكيد'
        self.mock_gw.create_appraisal_request.return_value = 555
        self.mock_gw.read_appraisal_request.return_value = {"id": 555, "state": "completed"}
        self.mock_gw.complete_appraisal_request.return_value = True

        exec_succ = self.service.apply_appraisal(token, user_confirmation_text="تأكيد")
        self.assertTrue(exec_succ.success)
        self.assertEqual(exec_succ.appraisal_id, 555)
        self.assertTrue(exec_succ.readback_verified)
        self.assertTrue(exec_succ.audit_logged)
        self.assertTrue(self.audit_log_path.exists())


class TestAppraisalAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("web_service.get_appraisal_service_instance")
    def test_api_ratings_guide(self, mock_get_srv):
        resp = self.client.get("/api/appraisals/ratings-guide")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(len(data["tiers"]) >= 5)

    @patch("web_service.get_appraisal_service_instance")
    def test_api_summary(self, mock_get_srv):
        mock_srv = MagicMock()
        mock_srv.get_employee_appraisal_summary.return_value = AppraisalSummary(
            employee_id=12,
            employee_name="بندر الدوسري",
            department_name="المبيعات",
            job_title="مسؤول مبيعات",
            is_saudi=True,
            nationality_text_ar="مواطن سعودي",
            identification_id="1011122233",
            hiring_date="2025-01-01",
            days_since_hiring=400,
            in_probation_period=False,
            total_appraisals_count=2,
            last_score=89.0,
            last_rating_ar="جيد جداً",
            recent_appraisals=[],
        )
        mock_get_srv.return_value = mock_srv

        resp = self.client.get("/api/appraisals/summary/12")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["summary"]["employee_name"], "بندر الدوسري")
        self.assertEqual(data["summary"]["last_score"], 89.0)

    @patch("web_service.get_appraisal_service_instance")
    def test_api_dry_run(self, mock_get_srv):
        mock_srv = MagicMock()
        mock_srv.dry_run_appraisal.return_value = AppraisalDryRunResult(
            is_valid=True,
            employee_id=12,
            employee_name="بندر الدوسري",
            department_id=2,
            department_name="المبيعات",
            job_id=4,
            job_title="مسؤول مبيعات",
            is_saudi=True,
            nationality_text_ar="مواطن سعودي",
            appraisal_title="تقييم سنوي",
            appraisal_type="annual",
            kpi_score=90.0,
            competency_score=85.0,
            kpi_weight_pct=70.0,
            competency_weight_pct=30.0,
            final_percentage=88.5,
            rating_code="very_good",
            rating_ar="جيد جداً",
            recommendation_ar="ترشيح للترقية",
            statutory_article="لائحة تنظيم العمل",
            statutory_guidance_ar="تطوير الكفاءات",
            warnings=[],
            errors=[],
            approval_token="APR-TEST1234",
            can_proceed=True,
        )
        mock_get_srv.return_value = mock_srv

        resp = self.client.post(
            "/api/appraisals/dry-run",
            json={"employee_id": 12, "kpi_score": 90.0, "competency_score": 85.0},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["result"]["approval_token"], "APR-TEST1234")

    @patch("web_service.get_appraisal_service_instance")
    def test_api_apply(self, mock_get_srv):
        mock_srv = MagicMock()
        mock_srv.apply_appraisal.return_value = AppraisalExecutionResult(
            success=True,
            appraisal_id=303,
            appraisal_title="تقييم سنوي",
            employee_id=12,
            employee_name="بندر الدوسري",
            final_percentage=88.5,
            rating_ar="جيد جداً",
            state="completed",
            readback_verified=True,
            message_ar="تم التسجيل والاعتماد بنجاح",
            audit_logged=True,
        )
        mock_get_srv.return_value = mock_srv

        resp = self.client.post(
            "/api/appraisals/apply",
            json={"approval_token": "APR-TEST1234", "confirmation_text": "تأكيد"},
            headers={"X-API-Key": "hr-write-secret-token"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["appraisal_id"], 303)


if __name__ == "__main__":
    unittest.main()
