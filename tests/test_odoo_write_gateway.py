import re
import unittest
from pathlib import Path

from environment_policy import ALLOWED_TEST_DBS
from odoo_write_gateway import (
    EnvironmentGuardError,
    OdooWriteGateway,
    WriteGatewayError,
)

ALLOWED_DB = sorted(ALLOWED_TEST_DBS)[0]


class FakeCommon:
    def __init__(self, uid=7):
        self.uid = uid
        self.calls = []

    def authenticate(self, db, login, password, ctx):
        self.calls.append(("authenticate", db))
        return self.uid

    def version(self):
        self.calls.append(("version",))
        return {"server_version": "19.0"}


class FakeModels:
    def __init__(self):
        self.calls = []
        self.next_id = 501

    def execute_kw(self, db, uid, password, model, method, args, kwargs):
        self.calls.append((db, uid, model, method, args, kwargs))
        if method == "create":
            self.next_id += 1
            return self.next_id
        if method == "read":
            return [{"id": args[0][0], "name": "Sara"}]
        raise AssertionError(method)


def make_gateway(db=ALLOWED_DB, common=None, models=None):
    return OdooWriteGateway(
        "https://example.odoo.com/", db, "admin", "secret",
        common=common or FakeCommon(), models=models or FakeModels(),
    )


class OdooWriteGatewayTests(unittest.TestCase):
    def test_disallowed_db_rejected_before_any_network_call(self):
        common, models = FakeCommon(), FakeModels()
        with self.assertRaises(EnvironmentGuardError):
            make_gateway(db="production_db", common=common, models=models)
        self.assertEqual(common.calls, [])
        self.assertEqual(models.calls, [])

    def test_failed_authentication_raises(self):
        with self.assertRaises(WriteGatewayError):
            make_gateway(common=FakeCommon(uid=False))

    def test_session_info_fields(self):
        info = make_gateway().get_session_info()
        self.assertEqual(info["odoo_url"], "https://example.odoo.com")
        self.assertEqual(info["odoo_db"], ALLOWED_DB)
        self.assertEqual(info["uid"], 7)
        self.assertEqual(info["login"], "admin")
        self.assertEqual(info["server_version"], "19.0")

    def test_create_sends_single_dict_and_returns_id(self):
        models = FakeModels()
        gw = make_gateway(models=models)
        new_id = gw.create_employee({"name": "Sara"})
        self.assertEqual(new_id, 502)
        self.assertEqual(len(models.calls), 1)
        _, _, model, method, args, _ = models.calls[0]
        self.assertEqual((model, method), ("hr.employee", "create"))
        self.assertEqual(args, [{"name": "Sara"}])

    def test_create_rejects_list_and_empty_input(self):
        models = FakeModels()
        gw = make_gateway(models=models)
        for bad in ([{"name": "A"}], {}, None, "x"):
            with self.assertRaises(WriteGatewayError):
                gw.create_employee(bad)
        self.assertEqual(models.calls, [])

    def test_create_rejects_list_result(self):
        models = FakeModels()
        models.execute_kw = lambda *a, **k: [1, 2]
        with self.assertRaises(WriteGatewayError):
            make_gateway(models=models).create_employee({"name": "A"})

    def test_read_employee_passes_fields(self):
        models = FakeModels()
        row = make_gateway(models=models).read_employee(502, ["name"])
        self.assertEqual(row["id"], 502)
        self.assertEqual(models.calls[0][3], "read")
        self.assertEqual(models.calls[0][5], {"fields": ["name"]})

    def test_guard_rechecked_before_each_create(self):
        models = FakeModels()
        gw = make_gateway(models=models)
        gw.db = "production_db"
        with self.assertRaises(EnvironmentGuardError):
            gw.create_employee({"name": "A"})
        self.assertEqual(models.calls, [])

    def test_unlisted_method_is_refused(self):
        gw = make_gateway()
        for method in ("unlink", "write", "search"):
            with self.assertRaises(WriteGatewayError):
                gw._call(method, [[1]])

    def test_source_has_no_unlink_or_write_and_single_create_call_site(self):
        source = Path("odoo_write_gateway.py").read_text(encoding="utf-8")
        self.assertNotIn("unlink", source)
        self.assertNotIn(".write(", source)
        self.assertEqual(len(re.findall(r'self\._call\("create"', source)), 1)

    def test_create_employee_passes_context_dict(self):
        models = FakeModels()
        gw = make_gateway(models=models)
        gw.create_employee({"name": "Sara"}, context={"allowed_company_ids": [15]})
        self.assertEqual(models.calls[0][5], {"context": {"allowed_company_ids": [15]}})

    def test_create_employee_rejects_non_dict_context(self):
        gw = make_gateway()
        for bad in ("bad", [15], 15, True):
            with self.assertRaises(WriteGatewayError):
                gw.create_employee({"name": "Sara"}, context=bad)

    def test_read_employee_passes_context_dict(self):
        models = FakeModels()
        gw = make_gateway(models=models)
        gw.read_employee(502, ["name"], context={"allowed_company_ids": [15]})
        self.assertEqual(
            models.calls[0][5],
            {"fields": ["name"], "context": {"allowed_company_ids": [15]}},
        )

    def test_read_employee_rejects_non_dict_context(self):
        gw = make_gateway()
        for bad in ("bad", [15], 15, True):
            with self.assertRaises(WriteGatewayError):
                gw.read_employee(502, ["name"], context=bad)

    def test_gateway_does_not_define_its_own_db_list(self):
        source = Path("odoo_write_gateway.py").read_text(encoding="utf-8")
        self.assertIn("from environment_policy import ALLOWED_TEST_DBS", source)
        self.assertNotRegex(source, r"(?m)^\s*ALLOWED_TEST_DBS\s*=")

if __name__ == "__main__":
    unittest.main()