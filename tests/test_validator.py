import unittest
from validator import Validator, safe_many2one_id
from failure_codes import REFERENCE_NOT_FOUND


class FakeRepository:
    def __init__(self, companies, departments, jobs, employee_candidates):
        self._companies = companies
        self._departments = departments
        self._jobs = jobs
        self._employee_candidates = employee_candidates

    def get_live_reference_snapshot(self):
        return {"companies": self._companies, "departments": self._departments, "jobs": self._jobs}

    def search_employee_email_candidates(self, email_fragment, limit=20):
        return self._employee_candidates


def make_row(excel_row_number=2, parser_flags=None, name_value="أحمد محمد", name_match="أحمد محمد",
             work_email_value="ahmed@example.com", work_email_match="ahmed@example.com",
             mobile_value="+966500000001", mobile_match="+966500000001",
             company_value="شركة النخبة الذكية للتقنية", department_value="الإدارة العليا / الموارد البشرية",
             job_value="أخصائي موارد بشرية", run_id="abc123", row_hash="rowhash1", source_hash="srchash1"):
    parser_flags = parser_flags or []
    return {
        "excel_row_number": excel_row_number, "parser_flags": parser_flags,
        "run_id": run_id, "row_hash": row_hash, "source_hash": source_hash,
        "fields": {
            "name": {"raw": name_value, "value": name_value, "match_key": name_match},
            "work_email": {"raw": work_email_value, "value": work_email_value, "match_key": work_email_match},
            "work_phone": {"raw": "", "value": "", "match_key": None},
            "mobile_phone": {"raw": mobile_value, "value": mobile_value, "match_key": mobile_match},
            "job_title": {"raw": "منسق موارد بشرية", "value": "منسق موارد بشرية", "match_key": "منسق موارد بشرية"},
            "company": {"raw": company_value, "value": company_value, "match_key": company_value},
            "department": {"raw": department_value, "value": department_value, "match_key": department_value},
            "job": {"raw": job_value, "value": job_value, "match_key": job_value},
        },
    }


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.company = {"id": 15, "name": "شركة النخبة الذكية للتقنية", "active": True}
        self.department = {
            "id": 8, "name": "الموارد البشرية", "complete_name": "الإدارة العليا / الموارد البشرية",
            "company_id": [15, "شركة النخبة الذكية للتقنية"], "active": True,
        }
        self.job = {
            "id": 22, "name": "أخصائي موارد بشرية",
            "company_id": [15, "شركة النخبة الذكية للتقنية"], "department_id": False, "active": True,
        }

    def test_duplicate_in_file(self):
        repo = FakeRepository([self.company], [self.department], [self.job], [])
        result = Validator(repo).validate_rows([make_row(parser_flags=["duplicate_in_file"])])[0]
        self.assertEqual(result["final_status"], "needs_review")
        self.assertEqual(result["failure_code"], "duplicate_in_file")

    def test_duplicate_existing_employee(self):
        repo = FakeRepository([self.company], [self.department], [self.job], [
            {"id": 91, "name": "أحمد محمد", "work_email": "ahmed@example.com",
             "company_id": [15, "شركة النخبة الذكية للتقنية"], "active": True}])
        result = Validator(repo).validate_rows([make_row()])[0]
        self.assertEqual(result["final_status"], "needs_review")
        self.assertEqual(result["failure_code"], "duplicate_existing_employee")

    def test_ambiguous_duplicate_multiple_matches(self):
        repo = FakeRepository([self.company], [self.department], [self.job], [
            {"id": 91, "name": "أحمد محمد", "work_email": "ahmed@example.com", "company_id": [15, "x"], "active": True},
            {"id": 92, "name": "أحمد محمد ٢", "work_email": "ahmed@example.com", "company_id": [15, "x"], "active": True}])
        result = Validator(repo).validate_rows([make_row()])[0]
        self.assertEqual(result["final_status"], "needs_review")
        self.assertEqual(result["failure_code"], "ambiguous_duplicate")

    def test_reference_not_found(self):
        repo = FakeRepository([self.company], [], [self.job], [])
        result = Validator(repo).validate_rows([make_row(department_value="قسم غير موجود")])[0]
        self.assertEqual(result["final_status"], "rejected")
        self.assertEqual(result["failure_code"], "reference_not_found")

    def test_reference_ambiguous(self):
        job1 = dict(self.job, id=22)
        job2 = dict(self.job, id=23)
        repo = FakeRepository([self.company], [self.department], [job1, job2], [])
        result = Validator(repo).validate_rows([make_row()])[0]
        self.assertEqual(result["final_status"], "needs_review")
        self.assertEqual(result["failure_code"], "reference_ambiguous")

    def test_point1_archived_company_is_needs_review_not_accepted(self):
        archived_company = dict(self.company, active=False)
        repo = FakeRepository([archived_company], [self.department], [self.job], [])
        result = Validator(repo).validate_rows([make_row()])[0]
        self.assertEqual(result["final_status"], "needs_review")
        self.assertEqual(result["failure_code"], "archived_reference_match")

    def test_point1_archived_department_is_needs_review(self):
        archived_department = dict(self.department, active=False)
        repo = FakeRepository([self.company], [archived_department], [self.job], [])
        result = Validator(repo).validate_rows([make_row()])[0]
        self.assertEqual(result["final_status"], "needs_review")
        self.assertEqual(result["failure_code"], "archived_reference_match")

    def test_point1_archived_job_is_needs_review(self):
        archived_job = dict(self.job, active=False)
        repo = FakeRepository([self.company], [self.department], [archived_job], [])
        result = Validator(repo).validate_rows([make_row()])[0]
        self.assertEqual(result["final_status"], "needs_review")
        self.assertEqual(result["failure_code"], "archived_reference_match")

    def test_point2_invalid_email_format_is_rejected(self):
        repo = FakeRepository([self.company], [self.department], [self.job], [])
        result = Validator(repo).validate_rows([make_row(
            work_email_value="ahmed.example.com", work_email_match="ahmed.example.com")])[0]
        self.assertEqual(result["final_status"], "rejected")
        self.assertEqual(result["failure_code"], "invalid_work_email")

    def test_point3_no_email_and_no_mobile_is_needs_review(self):
        repo = FakeRepository([self.company], [self.department], [self.job], [])
        result = Validator(repo).validate_rows([make_row(
            work_email_value="", work_email_match=None, mobile_value="", mobile_match=None)])[0]
        self.assertEqual(result["final_status"], "needs_review")
        self.assertEqual(result["failure_code"], "insufficient_duplicate_signal")

    def test_point4_company_matches_moussa_variants(self):
        company_moussa_ya = dict(self.company, name="مؤسسة موسى")
        repo = FakeRepository([company_moussa_ya], [self.department], [self.job], [])
        result = Validator(repo).validate_rows([make_row(company_value="مؤسسة موسي")])[0]
        self.assertEqual(result["final_status"], "accepted")

    def test_point4_company_ambiguous_variants_needs_review(self):
        company_a = dict(self.company, id=15, name="مؤسسة موسى")
        company_b = dict(self.company, id=16, name="مؤسسة موسي")
        repo = FakeRepository([company_a, company_b], [self.department], [self.job], [])
        result = Validator(repo).validate_rows([make_row(company_value="مؤسسة موسى")])[0]
        self.assertEqual(result["final_status"], "needs_review")
        self.assertEqual(result["failure_code"], "reference_ambiguous")

    def test_point5_possible_duplicate_in_file_signal_drives_decision(self):
        repo = FakeRepository([self.company], [self.department], [self.job], [])
        result = Validator(repo).validate_rows([make_row(
            work_email_value="", work_email_match=None, parser_flags=["possible_duplicate_in_file"])])[0]
        self.assertEqual(result["final_status"], "needs_review")
        self.assertEqual(result["failure_code"], "possible_duplicate_in_file")

    def test_point6_run_id_row_hash_source_hash_present(self):
        repo = FakeRepository([self.company], [self.department], [self.job], [])
        result = Validator(repo).validate_rows([make_row(run_id="run-xyz", row_hash="hash-abc", source_hash="src-def")])[0]
        self.assertEqual(result["run_id"], "run-xyz")
        self.assertEqual(result["row_hash"], "hash-abc")
        self.assertEqual(result["source_hash"], "src-def")

    def test_point7_safe_many2one_id_handles_false(self):
        self.assertIsNone(safe_many2one_id(False))

    def test_point7_safe_many2one_id_handles_none(self):
        self.assertIsNone(safe_many2one_id(None))

    def test_point7_safe_many2one_id_handles_malformed(self):
        self.assertIsNone(safe_many2one_id("not-a-list"))
        self.assertIsNone(safe_many2one_id([]))

    def test_point7_safe_many2one_id_valid(self):
        self.assertEqual(safe_many2one_id([15, "شركة"]), 15)

    def test_point7_validator_does_not_crash_on_malformed_company_id(self):
        broken_department = dict(self.department, company_id=False)
        repo = FakeRepository([self.company], [broken_department], [self.job], [])
        result = Validator(repo).validate_rows([make_row()])[0]
        self.assertEqual(result["final_status"], "rejected")
        self.assertEqual(result["failure_code"], "reference_not_found")

    def test_empty_email_present_mobile_is_unverified_no_email(self):
        repo = FakeRepository([self.company], [self.department], [self.job], [])
        result = Validator(repo).validate_rows([make_row(work_email_value="", work_email_match=None)])[0]
        self.assertEqual(result["final_status"], "needs_review")
        self.assertEqual(result["failure_code"], "unverified_no_email")

    def test_reference_not_found_department_suggests_closest_match(self):
        class FakeRepository:
            def search_employee_email_candidates(self, email_fragment, limit=20):
                return []

        validator = Validator(FakeRepository())

        row = {
            "excel_row_number": 2,
            "fields": {
                "name": {"value": "Sara"},
                "work_email": {"value": "sara@example.com", "match_key": "sara@example.com"},
                "mobile_phone": {"value": "+966500000000", "match_key": "+966500000000"},
                "company": {"value": "Al Nukhba Tech"},
                "department": {"value": "Human Resorces"},
                "job": {"value": ""},
            },
            "parser_flags": [],
            "run_id": "run123",
            "row_hash": "row123",
            "source_hash": "src123",
        }

        companies = [
            {"id": 15, "name": "Al Nukhba Tech", "active": True},
        ]
        departments = [
            {"id": 8, "complete_name": "Human Resources", "company_id": [15, "Al Nukhba Tech"], "active": True},
            {"id": 9, "complete_name": "Finance", "company_id": [15, "Al Nukhba Tech"], "active": True},
        ]
        jobs = []

        result = validator.validate_single_row(row, companies, departments, jobs)

        self.assertEqual(result.final_status, "rejected")
        self.assertEqual(result.failure_code, REFERENCE_NOT_FOUND)
        self.assertIn("Department not found for company", result.reasons[0])
        self.assertIn("Closest match in this company: Human Resources", result.reasons[0])

    def test_reference_not_found_job_suggests_closest_match(self):
        class FakeRepository:
            def search_employee_email_candidates(self, email_fragment, limit=20):
                return []

        validator = Validator(FakeRepository())

        row = {
            "excel_row_number": 2,
            "fields": {
                "name": {"value": "Sara"},
                "work_email": {"value": "sara@example.com", "match_key": "sara@example.com"},
                "mobile_phone": {"value": "+966500000000", "match_key": "+966500000000"},
                "company": {"value": "Al Nukhba Tech"},
                "department": {"value": ""},
                "job": {"value": "Softwre Engineer"},
            },
            "parser_flags": [],
            "run_id": "run123",
            "row_hash": "row123",
            "source_hash": "src123",
        }

        companies = [
            {"id": 15, "name": "Al Nukhba Tech", "active": True},
        ]
        departments = []
        jobs = [
            {"id": 22, "name": "Software Engineer", "company_id": [15, "Al Nukhba Tech"], "active": True},
            {"id": 23, "name": "QA Engineer", "company_id": [15, "Al Nukhba Tech"], "active": True},
        ]

        result = validator.validate_single_row(row, companies, departments, jobs)

        self.assertEqual(result.final_status, "rejected")
        self.assertEqual(result.failure_code, REFERENCE_NOT_FOUND)
        self.assertIn("Job not found for company", result.reasons[0])
        self.assertIn("Closest match in this company: Software Engineer", result.reasons[0])


    def test_reference_not_found_department_arabic_suggests_closest_match(self):
        class FakeRepository:
            def search_employee_email_candidates(self, email_fragment, limit=20):
                return []

        validator = Validator(FakeRepository())

        row = {
            "excel_row_number": 2,
            "fields": {
                "name": {"value": "سارة"},
                "work_email": {"value": "sara@example.com", "match_key": "sara@example.com"},
                "mobile_phone": {"value": "+966500000000", "match_key": "+966500000000"},
                "company": {"value": "النخبة"},
                "department": {"value": "الموارد البشرية"},
                "job": {"value": ""},
            },
            "parser_flags": [],
            "run_id": "run123",
            "row_hash": "row123",
            "source_hash": "src123",
        }

        companies = [
            {"id": 15, "name": "النخبة", "active": True},
            {"id": 1, "name": "My Company", "active": True},
        ]

        departments = [
            {
                "id": 8,
                "complete_name": "الإدارة العليا / الموارد البشرية",
                "company_id": [15, "النخبة"],
                "active": True,
            },
            {
                "id": 9,
                "complete_name": "الإدارة العليا / تقنية المعلومات",
                "company_id": [15, "النخبة"],
                "active": True,
            },
            {
                "id": 10,
                "complete_name": "الإدارة العليا / المبيعات والتسويق",
                "company_id": [15, "النخبة"],
                "active": True,
            },
            {
                "id": 11,
                "complete_name": "الإدارة العليا / المحاسبة والمالية",
                "company_id": [15, "النخبة"],
                "active": True,
            },
            {
                "id": 12,
                "complete_name": "الإدارة العليا",
                "company_id": [15, "النخبة"],
                "active": True,
            },
            {
                "id": 99,
                "complete_name": "الإدارة",
                "company_id": [1, "My Company"],
                "active": True,
            },
        ]

        jobs = []

        result = validator.validate_single_row(row, companies, departments, jobs)

        self.assertEqual(result.final_status, "rejected")
        self.assertEqual(result.failure_code, REFERENCE_NOT_FOUND)
        self.assertIn("Department not found for company", result.reasons[0])
        self.assertIn("الإدارة العليا / الموارد البشرية", result.reasons[0])


if __name__ == "__main__":
    unittest.main()