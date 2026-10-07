import unittest

from failure_codes import (
    STATUS_BY_FAILURE_CODE,
    ALL_FAILURE_CODES,
    INSUFFICIENT_DUPLICATE_SIGNAL,
    UNVERIFIED_NO_EMAIL,
    DUPLICATE_EXISTING_EMPLOYEE,
    INVALID_WORK_EMAIL,
    DUPLICATE_IN_FILE,
    status_for_failure_code,
)


class FailureCodesTests(unittest.TestCase):
    def test_insufficient_duplicate_signal_is_needs_review(self):
        self.assertEqual(status_for_failure_code(INSUFFICIENT_DUPLICATE_SIGNAL), "needs_review")

    def test_unverified_no_email_is_needs_review(self):
        self.assertEqual(status_for_failure_code(UNVERIFIED_NO_EMAIL), "needs_review")

    def test_duplicate_existing_employee_is_needs_review(self):
        self.assertEqual(status_for_failure_code(DUPLICATE_EXISTING_EMPLOYEE), "needs_review")

    def test_invalid_work_email_is_rejected(self):
        self.assertEqual(status_for_failure_code(INVALID_WORK_EMAIL), "rejected")

    def test_duplicate_in_file_is_needs_review(self):
        self.assertEqual(status_for_failure_code(DUPLICATE_IN_FILE), "needs_review")

    def test_none_failure_code_returns_none(self):
        self.assertIsNone(status_for_failure_code(None))

    def test_unknown_failure_code_raises_key_error(self):
        with self.assertRaises(KeyError):
            status_for_failure_code("this_code_does_not_exist")

    def test_every_status_value_is_one_of_the_three_allowed(self):
        allowed = {"rejected", "needs_review", "failed"}
        for code, status in STATUS_BY_FAILURE_CODE.items():
            self.assertIn(status, allowed, f"{code} maps to invalid status {status}")

    def test_no_duplicate_code_strings(self):
        codes = list(STATUS_BY_FAILURE_CODE.keys())
        self.assertEqual(len(codes), len(set(codes)))

    def test_all_failure_codes_matches_status_map_keys(self):
        self.assertEqual(ALL_FAILURE_CODES, frozenset(STATUS_BY_FAILURE_CODE.keys()))


if __name__ == "__main__":
    unittest.main()