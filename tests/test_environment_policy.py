import re
import unittest
from pathlib import Path

import environment_policy


class EnvironmentPolicyTests(unittest.TestCase):
    def test_allowed_test_dbs_is_non_empty_immutable_set_of_strings(self):
        dbs = environment_policy.ALLOWED_TEST_DBS
        self.assertIsInstance(dbs, frozenset)
        self.assertTrue(dbs)
        self.assertTrue(all(isinstance(d, str) and d.strip() for d in dbs))

    def test_allowed_dev_dbs_is_non_empty_immutable_set_of_strings(self):
        dbs = environment_policy.ALLOWED_DEV_DBS
        self.assertIsInstance(dbs, frozenset)
        self.assertTrue(dbs)
        self.assertTrue(all(isinstance(d, str) and d.strip() for d in dbs))


    def test_allowed_test_dbs_defined_only_in_environment_policy(self):
        pattern = re.compile(r"^\s*ALLOWED_TEST_DBS\s*(:[^=]+)?=", re.MULTILINE)
        owners = []
        for path in Path(".").glob("*.py"):
            if pattern.search(path.read_text(encoding="utf-8")):
                owners.append(path.name)
        self.assertEqual(owners, ["environment_policy.py"])


if __name__ == "__main__":
    unittest.main()