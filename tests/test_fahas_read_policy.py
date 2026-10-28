"""FORBIDDEN_READ_FIELDS was defined in fahas_service.py but never referenced, so the read tools passed
those field names to Odoo. These tests cover the code path only (the policy is purely name-based):
they say nothing about which models or fields exist in a given Odoo installation."""
import pytest

from fahas_service import (
    FahasAgent, FahasSecurityError, assert_read_policy, is_forbidden_read_field, strip_forbidden_keys,
)


class FakeModels:
    def __init__(self):
        self.calls = []

    def execute_kw(self, db, uid, key, model, method, args, kwargs=None):
        self.calls.append((model, method, args, kwargs or {}))
        if method == "search_count":
            return 3
        if method in ("search_read", "read"):
            # Odoo may return more than was asked (computed/related fields): the output filter must catch it
            return [{"id": 1, "name": "x", "wage": 9000, "identification_id": "1088776655"}]
        return []


class FakeRepo:
    db, uid, api_key, url, username = "d", 1, "k", "u", "n"

    def __init__(self):
        self._models = FakeModels()

    def _base_context(self):
        return {}

    def get_company_ids(self):
        return [1]


@pytest.fixture
def fahas():
    agent = FahasAgent()
    repo = FakeRepo()
    agent.get_repository = lambda connection_id=None: repo
    agent.fake_repo = repo
    return agent


def blocked(fahas, task, params):
    with pytest.raises(FahasSecurityError):
        fahas.execute_query_task(task, params)
    assert fahas.fake_repo._models.calls == [], "nothing may reach Odoo when the request is refused"


@pytest.mark.parametrize("field", [
    "password", "password_crypt", "api_key", "access_token", "refresh_token", "bank_account_id", "iban",
    "acc_number", "salary", "wage", "hourly_cost", "identification_id", "passport_id", "iqama_id",
    "contract_id.wage", "wage desc", "wage:sum",
])
def test_every_listed_field_is_recognised_including_in_paths(field):
    assert is_forbidden_read_field(field)


def test_the_policy_is_exactly_the_explicit_list():
    """No guessing: a field is blocked only if the project lists it. Extending the list is a decision for
    the owner (e.g. allowance fields of the installed Odoo), not something inferred from field names."""
    from fahas_service import FORBIDDEN_READ_FIELDS

    assert all(is_forbidden_read_field(f) for f in FORBIDDEN_READ_FIELDS)
    assert not is_forbidden_read_field("l10n_sa_housing_allowance")
    assert not is_forbidden_read_field("salary_expected")


@pytest.mark.parametrize("field", ["name", "work_email", "department_id", "company_id", "job_title", "active", "id",
                                   "create_date:month", "hiring_date", "parent_id"])
def test_ordinary_fields_are_allowed(field):
    assert not is_forbidden_read_field(field)


def test_search_with_forbidden_fields_is_refused(fahas):
    blocked(fahas, "search_records", {"model": "hr.employee", "fields": ["name", "wage", "identification_id"]})


def test_search_sorted_or_filtered_by_salary_is_refused(fahas):
    blocked(fahas, "search_records", {"model": "hr.contract", "order": "wage desc"})
    blocked(fahas, "search_records", {"model": "hr.contract", "domain": [["wage", ">", 20000]]})


def test_read_with_forbidden_fields_is_refused(fahas):
    blocked(fahas, "read_records", {"model": "hr.contract", "ids": [1], "fields": ["wage"]})


def test_count_with_a_salary_filter_is_refused(fahas):
    """count_records(wage > X) would let the model binary-search a salary."""
    blocked(fahas, "count_records", {"model": "hr.contract", "domain": [["wage", ">", 20000]]})
    blocked(fahas, "count_records", {"model": "hr.employee", "domain": [["contract_id.wage", "=", 9000]]})


def test_group_by_salary_or_id_is_refused(fahas):
    blocked(fahas, "group_count", {"model": "hr.contract", "groupby_field": "wage"})
    blocked(fahas, "group_count", {"model": "hr.employee", "groupby_field": "identification_id"})
    blocked(fahas, "group_count", {"model": "hr.contract", "groupby_field": "department_id", "domain": [["wage", ">", 1]]})


def test_read_without_fields_no_longer_asks_odoo_for_everything(fahas):
    out = fahas.execute_query_task("read_records", {"model": "hr.contract", "ids": [1]})
    _, method, _, kwargs = fahas.fake_repo._models.calls[0]
    assert method == "read" and kwargs["fields"] == ["id", "name"]
    assert "wage" not in out["records"][0] and "identification_id" not in out["records"][0]


def test_output_is_filtered_even_if_odoo_returns_extra_fields(fahas):
    out = fahas.execute_query_task("search_records", {"model": "hr.employee"})
    assert out["records"] == [{"id": 1, "name": "x"}]


def test_normal_queries_still_work(fahas):
    assert fahas.execute_query_task("count_records", {"model": "hr.employee", "domain": [["active", "=", True]]})
    assert fahas.execute_query_task("search_records", {"model": "hr.employee", "fields": ["name", "department_id"],
                                                       "domain": [["company_id", "=", 15]], "order": "name asc"})
    assert fahas.execute_query_task("group_count", {"model": "hr.employee", "groupby_field": "department_id"}) is not None
    assert fahas.execute_query_task("read_records", {"model": "hr.employee", "ids": [1], "fields": ["name", "work_email"]})


def test_assert_read_policy_direct():
    assert_read_policy(fields=["name"])
    with pytest.raises(FahasSecurityError):
        assert_read_policy(fields=["name", "salary"])


def test_strip_forbidden_keys():
    assert strip_forbidden_keys([{"id": 1, "wage": 5, "name": "a"}]) == [{"id": 1, "name": "a"}]
    assert strip_forbidden_keys("not a list") == "not a list"
