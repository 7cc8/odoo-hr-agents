from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from odoo_recruitment_write_gateway import (
    OdooRecruitmentWriteGateway,
    RecruitmentEnvironmentGuardError,
    RecruitmentWriteGatewayError,
)
from recruitment_service import (
    RecruitmentService,
    JobOpeningSummary,
    ApplicantSummary,
    ApplicantDryRunResult,
    ApplicantExecutionResult,
    is_job_restricted_to_saudis,
    get_job_accreditation_requirement,
)
from web_service import app


class TestOdooRecruitmentWriteGateway(unittest.TestCase):
    def test_environment_guard_blocks_unauthorized_db(self):
        with self.assertRaises(RecruitmentEnvironmentGuardError):
            OdooRecruitmentWriteGateway(
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

        gateway = OdooRecruitmentWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        with self.assertRaises(RecruitmentWriteGatewayError):
            gateway._call("hr.employee", "create", [{}])

        with self.assertRaises(RecruitmentWriteGatewayError):
            gateway._call("hr.applicant", "unlink", [[1]])

    @patch("xmlrpc.client.ServerProxy")
    def test_create_and_read_applicant(self, mock_proxy_cls):
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1
        mock_common.version.return_value = {"server_version": "19.0"}

        mock_models = MagicMock()
        mock_models.execute_kw.side_effect = [
            [{"id": 1, "name": "New", "sequence": 0}],  # get_default_stage_id
            1001,  # create returns ID
            [{"id": 1001, "partner_name": "سعد المطيري", "job_id": [22, "أخصائي موارد بشرية"], "is_saudi": True}],  # read
            True,  # update stage
            True,  # update approval
        ]

        gateway = OdooRecruitmentWriteGateway(
            url="https://example.odoo.com",
            db="odooprosys-hr19-main-37916265",
            username="admin",
            password="pwd",
            common=mock_common,
            models=mock_models,
        )

        created_id = gateway.create_applicant(
            partner_name="سعد المطيري",
            job_id=22,
            is_saudi=True,
            salary_proposed=9000.0,
        )
        self.assertEqual(created_id, 1001)

        read_res = gateway.read_applicant(1001)
        self.assertIsNotNone(read_res)
        self.assertEqual(read_res["id"], 1001)

        stg_res = gateway.update_applicant_stage(1001, 2)
        self.assertTrue(stg_res)

        appr_res = gateway.update_applicant_approval_status(1001, "approved")
        self.assertTrue(appr_res)


class TestRecruitmentService(unittest.TestCase):
    def setUp(self):
        self.mock_repo = MagicMock()
        self.mock_gw = MagicMock()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_log_path = Path(self.temp_dir.name) / "test_recruit_audit.jsonl"
        self.service = RecruitmentService(
            readonly_repo=self.mock_repo,
            write_gateway=self.mock_gw,
            audit_log_path=str(self.audit_log_path),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_saudization_rules_helpers(self):
        self.assertTrue(is_job_restricted_to_saudis("أخصائي موارد بشرية"))
        self.assertTrue(is_job_restricted_to_saudis("مدير شؤون موظفين"))
        self.assertTrue(is_job_restricted_to_saudis("مسؤول علاقات حكومية"))
        self.assertTrue(is_job_restricted_to_saudis("موظف استقبال"))
        self.assertFalse(is_job_restricted_to_saudis("مطوّر برمجيات"))
        self.assertFalse(is_job_restricted_to_saudis("مهندس شبكات"))

        self.assertIn("SOCPA", get_job_accreditation_requirement("محاسب عام"))
        self.assertIn("SCE", get_job_accreditation_requirement("مهندس معماري"))
        self.assertIsNone(get_job_accreditation_requirement("مندوب مبيعات"))

    def test_get_job_openings_with_compliance_guidance(self):
        self.mock_repo.get_recruitment_jobs.return_value = [
            {"id": 22, "name": "أخصائي موارد بشرية", "department_id": [1, "الموارد البشرية"], "no_of_recruitment": 2},
            {"id": 23, "name": "مطوّر برمجيات", "department_id": [2, "تقنية المعلومات"], "no_of_recruitment": 3},
            {"id": 25, "name": "محاسب مالي", "department_id": [3, "المالية"], "no_of_recruitment": 1},
        ]

        jobs = self.service.get_job_openings()
        self.assertEqual(len(jobs), 3)

        hr_job = next(j for j in jobs if j.id == 22)
        self.assertTrue(hr_job.is_saudi_only)
        self.assertIn("100%", hr_job.compliance_guidance_ar)

        dev_job = next(j for j in jobs if j.id == 23)
        self.assertFalse(dev_job.is_saudi_only)

        acc_job = next(j for j in jobs if j.id == 25)
        self.assertIn("SOCPA", acc_job.compliance_guidance_ar)

    def test_dry_run_saudi_candidate_on_restricted_hr_job(self):
        self.mock_repo.get_recruitment_jobs.return_value = [
            {"id": 22, "name": "أخصائي موارد بشرية"}
        ]

        res = self.service.dry_run_applicant(
            candidate_name="فيصل الشمري",
            job_id=22,
            is_saudi=True,
            id_number="1012345678",
            salary_proposed=9000.0,
        )

        self.assertTrue(res.is_valid)
        self.assertTrue(res.can_proceed)
        self.assertTrue(res.is_saudi_restricted_job)
        self.assertTrue(res.approval_token.startswith("APP-"))
        self.assertEqual(len(res.errors), 0)
        self.assertTrue(any("متوافق مع التوطين" in w for w in res.warnings))

    def test_dry_run_expat_candidate_on_restricted_hr_job_blocked(self):
        self.mock_repo.get_recruitment_jobs.return_value = [
            {"id": 22, "name": "أخصائي موارد بشرية"}
        ]

        res = self.service.dry_run_applicant(
            candidate_name="جون سميث",
            job_id=22,
            is_saudi=False,
            id_number="2456789012",
            salary_proposed=8000.0,
        )

        self.assertFalse(res.is_valid)
        self.assertFalse(res.can_proceed)
        self.assertGreater(len(res.errors), 0)
        self.assertIn("حظر توطين قطعي", res.errors[0])
        self.assertEqual(res.approval_token, "")

    def test_dry_run_expat_candidate_on_general_tech_job_allowed(self):
        self.mock_repo.get_recruitment_jobs.return_value = [
            {"id": 23, "name": "مطوّر برمجيات"}
        ]

        res = self.service.dry_run_applicant(
            candidate_name="طارق منصور",
            job_id=23,
            is_saudi=False,
            id_number="2098765432",
            salary_proposed=12000.0,
            duration_of_contract=2,
        )

        self.assertTrue(res.is_valid)
        self.assertTrue(res.can_proceed)
        self.assertEqual(len(res.errors), 0)
        self.assertTrue(res.approval_token.startswith("APP-"))

    def test_apply_applicant_requires_written_confirmation(self):
        self.mock_repo.get_recruitment_jobs.return_value = [
            {"id": 23, "name": "مطوّر برمجيات"}
        ]

        dry_res = self.service.dry_run_applicant(
            candidate_name="عادل البلوي",
            job_id=23,
            is_saudi=True,
            id_number="1098765432",
            salary_proposed=10000.0,
        )

        # Rejection without written "تأكيد"
        exec_fail = self.service.apply_applicant(
            approval_token=dry_res.approval_token,
            user_confirmation_text="نعم اعتمد",
        )
        self.assertFalse(exec_fail.success)
        self.assertIn("تأكيد", exec_fail.message_ar)

        # Success with written "تأكيد"
        self.mock_gw.create_applicant.return_value = 555
        self.mock_gw.read_applicant.return_value = {"id": 555, "partner_name": "عادل البلوي"}

        exec_succ = self.service.apply_applicant(
            approval_token=dry_res.approval_token,
            user_confirmation_text="تأكيد",
        )
        self.assertTrue(exec_succ.success)
        self.assertEqual(exec_succ.applicant_id, 555)
        self.assertTrue(exec_succ.readback_verified)
        self.assertTrue(exec_succ.audit_logged)
        self.assertTrue(self.audit_log_path.exists())


class TestRecruitmentAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("web_service.get_recruitment_service_instance")
    def test_get_recruitment_jobs_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_get_svc.return_value = mock_svc
        mock_svc.get_job_openings.return_value = [
            JobOpeningSummary(
                id=22,
                name="أخصائي موارد بشرية",
                department_name="الموارد البشرية",
                no_of_recruitment=1,
                is_saudi_only=True,
                compliance_guidance_ar="مقصورة حصراً على المواطنين",
            )
        ]

        resp = self.client.get("/api/recruitment/jobs")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["jobs"]), 1)
        self.assertTrue(data["jobs"][0]["is_saudi_only"])

    @patch("web_service.get_recruitment_service_instance")
    def test_get_recruitment_stages_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_get_svc.return_value = mock_svc
        mock_svc.readonly_repo.get_recruitment_stages.return_value = [
            {"id": 1, "name": "New", "sequence": 0},
            {"id": 2, "name": "Qualification", "sequence": 1},
        ]

        resp = self.client.get("/api/recruitment/stages")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["stages"]), 2)

    @patch("web_service.get_recruitment_service_instance")
    def test_dry_run_applicant_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_get_svc.return_value = mock_svc
        mock_svc.dry_run_applicant.return_value = ApplicantDryRunResult(
            is_valid=True,
            candidate_name="سالم السبيعي",
            job_id=23,
            job_title="مطوّر برمجيات",
            is_saudi=True,
            nationality_text_ar="مواطن سعودي",
            id_number="1023456789",
            passport_number="",
            email="salem@example.com",
            phone="0501234567",
            salary_expected=10000.0,
            salary_proposed=11000.0,
            housing_allowance=2000.0,
            transportation_allowance=1000.0,
            total_salary=14000.0,
            contract_status="single",
            duration_of_contract=1,
            is_saudi_restricted_job=False,
            statutory_article="المواد 37 و 53",
            statutory_explanation_ar="مطابق للنظام",
            approval_token="APP-TEST1234",
            can_proceed=True,
        )

        payload = {
            "candidate_name": "سالم السبيعي",
            "job_id": 23,
            "is_saudi": True,
            "salary_proposed": 11000.0,
        }
        resp = self.client.post("/api/recruitment/dry-run", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["result"]["approval_token"], "APP-TEST1234")

    @patch("web_service.get_recruitment_service_instance")
    def test_apply_applicant_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_get_svc.return_value = mock_svc
        mock_svc.apply_applicant.return_value = ApplicantExecutionResult(
            success=True,
            applicant_id=701,
            candidate_name="سالم السبيعي",
            job_id=23,
            job_title="مطوّر برمجيات",
            is_saudi=True,
            total_salary=14000.0,
            approval_status="draft",
            readback_verified=True,
            message_ar="تم تسجيل المرشح بنجاح",
            audit_logged=True,
        )

        payload = {
            "approval_token": "APP-TEST1234",
            "confirmation_text": "تأكيد",
        }
        resp = self.client.post(
            "/api/recruitment/apply",
            json=payload,
            headers={"X-API-Key": "hr-write-secret-token"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["applicant_id"], 701)


if __name__ == "__main__":
    unittest.main()
