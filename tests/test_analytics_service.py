"""
اختبارات خدمة التحليلات التنفيذية ولوحة المؤشرات الشاملة (Tests for AnalyticsService - Phase 20)
=============================================================================
تغطي الاختبارات كافة وظائف التحليل الإحصائي، مؤشرات القوى العاملة والتوطين،
نطاقات، العمليات، الالتزامات المالية ومحاكي التعيينات.
"""

import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock

from analytics_service import (
    AnalyticsService,
    determine_nitaqat_band,
    detect_employee_nationality,
)


class TestAnalyticsService(unittest.TestCase):
    def setUp(self):
        self.mock_repo = MagicMock()
        self.service = AnalyticsService(readonly_repo=self.mock_repo)

    def test_determine_nitaqat_band(self):
        name, code, _ = determine_nitaqat_band(55.0)
        self.assertEqual(code, "platinum")
        self.assertIn("البلاتيني", name)

        name, code, _ = determine_nitaqat_band(42.0)
        self.assertEqual(code, "green_high")
        self.assertIn("الأخضر المرتفع", name)

        name, code, _ = determine_nitaqat_band(30.0)
        self.assertEqual(code, "green_mid")
        self.assertIn("الأخضر المتوسط", name)

        name, code, _ = determine_nitaqat_band(18.0)
        self.assertEqual(code, "green_low")
        self.assertIn("الأخضر المنخفض", name)

        name, code, _ = determine_nitaqat_band(10.0)
        self.assertEqual(code, "red")
        self.assertIn("الأحمر", name)

    def test_detect_employee_nationality(self):
        # 1. By explicit override
        self.assertTrue(detect_employee_nationality({}, explicit_is_saudi=True))
        self.assertFalse(detect_employee_nationality({}, explicit_is_saudi=False))

        # 2. By identification_id
        self.assertTrue(detect_employee_nationality({"identification_id": "1098765432"}))
        self.assertFalse(detect_employee_nationality({"identification_id": "2098765432"}))

        # 3. By country_id
        self.assertTrue(detect_employee_nationality({"country_id": [1, "Saudi Arabia"]}))
        self.assertTrue(detect_employee_nationality({"country_id": [1, "المملكة العربية السعودية"]}))

    def test_get_workforce_kpis(self):
        self.mock_repo.get_employees.return_value = [
            {"id": 1, "name": "أحمد", "identification_id": "1001", "sex": "male", "department_id": [1, "الهندسة"]},
            {"id": 2, "name": "سارة", "identification_id": "1002", "sex": "female", "department_id": [2, "الموارد البشرية"]},
            {"id": 3, "name": "جون", "identification_id": "2001", "sex": "male", "department_id": [1, "الهندسة"]},
            {"id": 4, "name": "راجيش", "identification_id": "2002", "sex": "male", "department_id": [1, "الهندسة"]},
        ]

        wf = self.service.get_workforce_kpis()
        self.assertEqual(wf.total_employees, 4)
        self.assertEqual(wf.saudi_count, 2)
        self.assertEqual(wf.non_saudi_count, 2)
        self.assertEqual(wf.saudization_rate_pct, 50.0)
        self.assertEqual(wf.nitaqat_code, "platinum")
        self.assertEqual(wf.male_count, 3)
        self.assertEqual(wf.female_count, 1)
        self.assertEqual(wf.departments_count, 2)
        self.assertEqual(wf.top_departments[0]["department"], "الهندسة")
        self.assertEqual(wf.top_departments[0]["count"], 3)

    def test_get_operations_kpis(self):
        today_str = date.today().isoformat()
        self.mock_repo.get_all_leaves.return_value = [
            {"id": 1, "state": "confirm"},
            {"id": 2, "state": "validate1"},
            {"id": 3, "state": "validate"},
            {"id": 4, "state": "refuse"},
        ]
        self.mock_repo.get_all_attendances.return_value = [
            {"id": 10, "date": today_str, "check_in": f"{today_str} 08:00:00", "check_out": False, "overtime_hours": 1.5},
            {"id": 11, "date": today_str, "check_in": f"{today_str} 08:30:00", "check_out": f"{today_str} 17:30:00", "overtime_hours": 2.0},
        ]

        ops = self.service.get_operations_kpis()
        self.assertEqual(ops.pending_leaves_count, 2)
        self.assertEqual(ops.approved_leaves_count, 1)
        self.assertEqual(ops.today_checkins_count, 2)
        self.assertEqual(ops.currently_active_checkins_count, 1)
        self.assertEqual(ops.total_monthly_overtime_hours, 3.5)

    def test_get_financial_kpis(self):
        self.mock_repo.get_all_loans.return_value = [
            {"id": 1, "loan_amount": 10000.0, "installment_amount": 1000.0, "state": "approve"},
            {"id": 2, "loan_amount": 5000.0, "installment_amount": 500.0, "state": "active"},
            {"id": 3, "loan_amount": 2000.0, "installment_amount": 200.0, "state": "draft"},  # draft not counted
        ]
        self.mock_repo.get_all_contracts.return_value = [
            # Saudi employee: wage 8000, housing 2000 -> gross 10000 -> contributory 10000
            # EE GOSI = 9.75% = 975, ER GOSI = 11.75% = 1175
            {"id": 101, "wage": 8000.0, "l10n_sa_housing_allowance": 2000.0, "total": 10000.0, "is_saudi": True},
            # Expat employee: wage 6000, housing 1500 -> gross 7500 -> contributory 7500
            # EE GOSI = 0%, ER GOSI = 2% = 150
            {"id": 102, "wage": 6000.0, "l10n_sa_housing_allowance": 1500.0, "total": 7500.0, "is_saudi": False},
        ]
        self.mock_repo.get_all_eos_records.return_value = [
            {"id": 201, "amount": 25000.0, "state": "approved"},
        ]

        fin = self.service.get_financial_kpis()
        self.assertEqual(fin.active_loans_count, 2)
        self.assertEqual(fin.total_active_loans_balance, 15000.0)
        self.assertEqual(fin.monthly_loan_recovery_run, 1500.0)
        self.assertEqual(fin.estimated_monthly_gross_payroll, 17500.0)
        self.assertEqual(fin.estimated_monthly_gosi_employee_deductions, 975.0)
        self.assertEqual(fin.estimated_monthly_gosi_employer_cost, 1175.0 + 150.0)
        self.assertEqual(fin.total_eosb_settled_amount, 25000.0)

    def test_get_compliance_kpis(self):
        today = date.today()
        d_exp_20 = (today + timedelta(days=20)).isoformat()
        d_exp_50 = (today + timedelta(days=50)).isoformat()

        self.mock_repo.get_employees.return_value = [
            {"id": 1, "identification_id": "1001", "sex": "male", "department_id": [1, "الإدارة"]},
            {"id": 2, "identification_id": "2001", "sex": "male", "department_id": [1, "الإدارة"]},
        ]
        self.mock_repo.get_all_gr_transactions.return_value = [
            {"id": 1, "transaction_date": d_exp_20},
            {"id": 2, "transaction_date": d_exp_50},
        ]
        self.mock_repo.get_employee_disciplinary_actions.return_value = []
        self.mock_repo.get_all_contracts.return_value = [
            {"id": 1, "trial_date_end": (today + timedelta(days=40)).isoformat()}
        ]

        comp = self.service.get_compliance_kpis()
        self.assertLessEqual(comp.health_score, 100)
        self.assertEqual(comp.expiring_iqamas_30d, 1)
        self.assertEqual(comp.expiring_iqamas_60d, 1)
        self.assertEqual(comp.active_probation_count, 1)
        self.assertTrue(any("30 يوماً" in a for a in comp.compliance_alerts))

    def test_get_recruitment_kpis(self):
        self.mock_repo.get_recruitment_jobs.return_value = [
            {"id": 1, "name": "محاسب"},
            {"id": 2, "name": "مهندس نظم"},
        ]
        self.mock_repo.get_applicants.return_value = [
            {"id": 101, "partner_name": "سعد", "is_saudi": True},
            {"id": 102, "partner_name": "علي", "is_saudi": True},
            {"id": 103, "partner_name": "بيتر", "is_saudi": False},
        ]

        rec = self.service.get_recruitment_kpis()
        self.assertEqual(rec.open_jobs_count, 2)
        self.assertEqual(rec.total_applicants_count, 3)
        self.assertEqual(rec.saudi_applicants_count, 2)
        self.assertEqual(rec.expat_applicants_count, 1)
        self.assertAlmostEqual(rec.saudization_pipeline_pct, 66.67, places=1)

    def test_simulate_saudization_impact(self):
        # 10 employees: 3 Saudi (30% -> Green Mid)
        self.mock_repo.get_employees.return_value = [
            {"id": i, "identification_id": "1001" if i <= 3 else "2001"}
            for i in range(1, 11)
        ]

        # Case 1: Hiring 2 Saudis -> total 12, saudi 5 -> 41.67% -> Green High
        sim1 = self.service.simulate_saudization_impact(saudi_hires=2, expat_hires=0)
        self.assertEqual(sim1.simulated_employees, 12)
        self.assertEqual(sim1.simulated_saudi, 5)
        self.assertEqual(sim1.simulated_rate_pct, 41.67)
        self.assertEqual(sim1.simulated_band, "النطاق الأخضر المرتفع (High Green)")
        self.assertTrue(sim1.is_improved)
        self.assertIn("ترقية إيجابية", sim1.status_change_ar)

        # Case 2: Hiring 0 Saudis and 5 Expats -> total 15, saudi 3 -> 20% -> Green Low
        sim2 = self.service.simulate_saudization_impact(saudi_hires=0, expat_hires=5)
        self.assertEqual(sim2.simulated_employees, 15)
        self.assertEqual(sim2.simulated_saudi, 3)
        self.assertEqual(sim2.simulated_rate_pct, 20.0)
        self.assertEqual(sim2.simulated_band, "النطاق الأخضر المنخفض (Low Green)")
        self.assertFalse(sim2.is_improved)
        self.assertIn("تراجع في النطاق", sim2.status_change_ar)

    def test_get_unified_dashboard(self):
        self.mock_repo.get_employees.return_value = []
        self.mock_repo.get_all_leaves.return_value = []
        self.mock_repo.get_all_attendances.return_value = []
        self.mock_repo.get_all_loans.return_value = []
        self.mock_repo.get_all_contracts.return_value = []
        self.mock_repo.get_all_eos_records.return_value = []
        self.mock_repo.get_all_gr_transactions.return_value = []
        self.mock_repo.get_recruitment_jobs.return_value = []
        self.mock_repo.get_applicants.return_value = []

        dash = self.service.get_unified_dashboard()
        self.assertIsNotNone(dash.timestamp)
        self.assertEqual(dash.workforce.total_employees, 0)
        self.assertIn("لوحة المؤشرات التنفيذية", dash.summary_message_ar)


from unittest.mock import patch
from fastapi.testclient import TestClient
import web_service
from analytics_service import (
    WorkforceKpis,
    OperationsKpis,
    FinancialKpis,
    ComplianceKpis,
    RecruitmentKpis,
    SaudizationSimResult,
    UnifiedDashboardData,
)


class TestAnalyticsApiEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web_service.app)

    @patch("web_service.get_analytics_service_instance")
    def test_get_unified_dashboard_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_svc.get_unified_dashboard.return_value = UnifiedDashboardData(
            timestamp="2026-10-06T08:00:00Z",
            generated_at_ar="2026-10-06 08:00:00 UTC",
            workforce=WorkforceKpis(
                total_employees=10,
                saudi_count=4,
                non_saudi_count=6,
                saudization_rate_pct=40.0,
                nitaqat_band_name="النطاق الأخضر المرتفع",
                nitaqat_code="green_high",
                nitaqat_status_ar="آمن",
                male_count=8,
                female_count=2,
                unspecified_gender_count=0,
                departments_count=3,
                top_departments=[{"department": "العمليات", "count": 5}],
            ),
            operations=OperationsKpis(
                pending_leaves_count=1,
                approved_leaves_count=4,
                today_checkins_count=8,
                currently_active_checkins_count=3,
                total_monthly_overtime_hours=12.5,
            ),
            financial=FinancialKpis(
                active_loans_count=2,
                total_active_loans_balance=15000.0,
                monthly_loan_recovery_run=1500.0,
                estimated_monthly_gross_payroll=65000.0,
                estimated_monthly_gosi_employer_cost=5500.0,
                estimated_monthly_gosi_employee_deductions=3900.0,
                total_eosb_settled_amount=12000.0,
            ),
            compliance=ComplianceKpis(
                health_score=92,
                rating_label_ar="امتثال ممتاز 🏆",
                expiring_iqamas_30d=0,
                expiring_iqamas_60d=1,
                expiring_iqamas_90d=2,
                pending_disciplinary_count=0,
                active_probation_count=1,
                compliance_alerts=["بيئة العمل ممتثلة تماماً."],
                actionable_recommendations_ar=["المحافظة على التوثيق."],
            ),
            recruitment=RecruitmentKpis(
                open_jobs_count=3,
                total_applicants_count=15,
                saudi_applicants_count=10,
                expat_applicants_count=5,
                saudization_pipeline_pct=66.7,
            ),
            summary_message_ar="لوحة المؤشرات جاهزة ومحدثة.",
        )
        mock_get_svc.return_value = mock_svc

        response = self.client.get("/api/analytics/dashboard")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["workforce"]["total_employees"], 10)
        self.assertEqual(data["workforce"]["saudization_rate_pct"], 40.0)
        self.assertEqual(data["compliance"]["health_score"], 92)

    @patch("web_service.get_analytics_service_instance")
    def test_get_workforce_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_svc.get_workforce_kpis.return_value = WorkforceKpis(
            total_employees=20,
            saudi_count=10,
            non_saudi_count=10,
            saudization_rate_pct=50.0,
            nitaqat_band_name="البلاتيني",
            nitaqat_code="platinum",
            nitaqat_status_ar="ممتاز",
            male_count=15,
            female_count=5,
            unspecified_gender_count=0,
            departments_count=4,
            top_departments=[],
        )
        mock_get_svc.return_value = mock_svc

        response = self.client.get("/api/analytics/workforce")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["workforce"]["saudization_rate_pct"], 50.0)

    @patch("web_service.get_analytics_service_instance")
    def test_simulate_saudization_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_svc.simulate_saudization_impact.return_value = SaudizationSimResult(
            current_employees=10,
            current_saudi=3,
            current_rate_pct=30.0,
            current_band="النطاق الأخضر المتوسط",
            simulated_employees=12,
            simulated_saudi=5,
            simulated_rate_pct=41.67,
            simulated_band="النطاق الأخضر المرتفع",
            is_improved=True,
            status_change_ar="ترقية إيجابية",
            legal_advice_ar="نصيحة قانونية",
        )
        mock_get_svc.return_value = mock_svc

        payload = {"saudi_hires": 2, "expat_hires": 0}
        response = self.client.post("/api/analytics/simulate-saudization", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["simulation"]["simulated_rate_pct"], 41.67)
        self.assertTrue(data["simulation"]["is_improved"])


if __name__ == "__main__":
    unittest.main()

