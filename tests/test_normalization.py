import unittest
from datetime import date, datetime
from normalization import (
    phone_match_key, name_match_key, reference_match_key,
    email_match_key, is_valid_email_format,
    normalize_date_text, to_text_preserve,
)


class NormalizationTests(unittest.TestCase):

    def test_phone_spaces_normalized_to_saudi_intl(self):
        self.assertEqual(phone_match_key("+966 50 000 0000"), "+966500000000")

    def test_phone_local_zero_prefix_normalized(self):
        self.assertEqual(phone_match_key("0500000000"), "+966500000000")

    def test_phone_dashes_and_parens_removed(self):
        self.assertEqual(phone_match_key("(050) 000-0000"), "+966500000000")

    def test_phone_00_prefix_becomes_plus(self):
        self.assertEqual(phone_match_key("00966500000000"), "+966500000000")

    def test_phone_bare_country_code_no_plus(self):
        self.assertEqual(phone_match_key("966599887766"), "+966599887766")

    def test_phone_bare_country_code_matches_plus_variant(self):
        self.assertEqual(phone_match_key("966599887766"), phone_match_key("+966599887766"))

    def test_name_lowercase_latin(self):
        self.assertEqual(name_match_key("Ahmed"), "ahmed")

    def test_name_moussa_variants_equal(self):
        self.assertEqual(name_match_key("موسى"), name_match_key("موسي"))

    def test_name_diacritics_removed(self):
        self.assertEqual(name_match_key("مُحَمَّد"), name_match_key("محمد"))

    def test_reference_match_key_same_function_both_sides(self):
        self.assertEqual(reference_match_key("قسم تقنية المعلومات"), reference_match_key("قسم تقنية المعلومات"))

    def test_email_match_key_lowercases(self):
        self.assertEqual(email_match_key("Ahmed@Example.COM"), "ahmed@example.com")

    def test_valid_email_format_true(self):
        self.assertTrue(is_valid_email_format("ahmed@example.com"))

    def test_valid_email_format_false_missing_at(self):
        self.assertFalse(is_valid_email_format("ahmed.example.com"))

    def test_valid_email_format_false_missing_domain_dot(self):
        self.assertFalse(is_valid_email_format("ahmed@examplecom"))

    def test_normalize_date_text_slashes_and_time(self):
        self.assertEqual(normalize_date_text("2026/10/06"), "2026-10-06")
        self.assertEqual(normalize_date_text("2026-10-06 00:00:00"), "2026-10-06")
        self.assertEqual(normalize_date_text(""), "")
        self.assertEqual(normalize_date_text("   "), "")

    def test_to_text_preserve_date_and_datetime(self):
        self.assertEqual(to_text_preserve(date(2026, 10, 6)), "2026-10-06")
        self.assertEqual(to_text_preserve(datetime(2026, 10, 6, 15, 30)), "2026-10-06")


if __name__ == "__main__":
    unittest.main()