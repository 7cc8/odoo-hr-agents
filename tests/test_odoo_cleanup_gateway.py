import unittest

from environment_policy import ALLOWED_TEST_DBS
from odoo_cleanup_gateway import (
    CleanupEnvironmentGuardError,
    CleanupGatewayError,
    OdooCleanupGateway,
)

ALLOWED_DB = sorted(ALLOWED_TEST_DBS)[0]


class FakeCommon:
    def __init__(self, uid=7):
        self.uid = uid
        self.calls = []

    def authenticate(self, db, login, password, ctx):
        self.calls.append(("authenticate", db))
        return self.uid


class FakeModels:
    def __init__(self, result=True):
        self.calls = []
        self.result = result

    def execute_kw(self, db, uid, password, model, method, args, kwargs):
        self.calls.append((db, uid, model, method, args, kwargs))
        return self.result


def make_gateway(db=ALLOWED_DB, common=None, models=None):
    return OdooCleanupGateway(
        "https://example.odoo.com/",
        db,
        "admin",
        "secret",
        common=common or FakeCommon(),
        models=models or FakeModels(),
    )


class OdooCleanupGatewayTests(unittest.TestCase):
    def test_delete_sends_only_unlink_for_one_employee(self):
        models = FakeModels()
        gateway = make_gateway(models=models)

        self.assertTrue(gateway.delete_employee_for_test_cleanup(122))
        self.assertEqual(len(models.calls), 1)
        _, _, model, method, args, kwargs = models.calls[0]
        self.assertEqual((model, method), ("hr.employee", "unlink"))
        self.assertEqual(args, [[122]])
        self.assertEqual(kwargs, {})

    def test_invalid_employee_id_is_rejected_before_network_call(self):
        models = FakeModels()
        gateway = make_gateway(models=models)

        with self.assertRaises(CleanupGatewayError):
            gateway.delete_employee_for_test_cleanup(0)

        self.assertEqual(models.calls, [])

    def test_unexpected_unlink_result_is_rejected(self):
        models = FakeModels(result=False)
        gateway = make_gateway(models=models)

        with self.assertRaises(CleanupGatewayError):
            gateway.delete_employee_for_test_cleanup(122)

        self.assertEqual(len(models.calls), 1)

    def test_disallowed_database_is_rejected_before_authentication(self):
        common, models = FakeCommon(), FakeModels()

        with self.assertRaises(CleanupEnvironmentGuardError):
            make_gateway(db="not-allowed", common=common, models=models)

        self.assertEqual(common.calls, [])
        self.assertEqual(models.calls, [])


if __name__ == "__main__":
    unittest.main()
