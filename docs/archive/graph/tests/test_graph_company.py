"""Company-context tests for the LangGraph skeleton (no network, no Odoo)."""
import pytest

pytest.importorskip("langgraph")

from graph import nodes as n  # noqa: E402


def test_wants_all_companies():
    assert n.wants_all_companies("كم موظف في كل الشركات؟")
    assert n.wants_all_companies("أعطني جميع الشركات")
    assert not n.wants_all_companies("كم موظف في توركين؟")


def test_ingest_clears_company_on_all_companies():
    out = n.ingest_user_message({"user_query": "كم موظف في كل الشركات؟", "company_id": 15})
    assert out["company_id"] is None and out["company_name"] is None


def test_ingest_keeps_company_otherwise():
    out = n.ingest_user_message({"user_query": "كم عدد الموظفين؟", "company_id": 15})
    assert "company_id" not in out


def test_collect_companies_walks_nested_results():
    out = {}
    n.collect_companies({"companies": [{"id": 1, "name": "My Company"}, {"id": "15", "name": "النخبة"}]}, out)
    assert out == {"1": "My Company", "15": "النخبة"}


def test_explicit_company_becomes_sticky():
    args, cid = n.resolve_company_args("count_employees", {"company_id": 15}, None, {"count_employees"})
    assert cid == 15


def test_sticky_company_is_injected_into_accepting_tool():
    args, cid = n.resolve_company_args("count_employees", {}, 15, {"count_employees"})
    assert args["company_id"] == 15 and cid == 15


def test_not_injected_into_tool_without_param_or_list_tool():
    args, _ = n.resolve_company_args("search_x", {}, 15, {"count_employees"})
    assert "company_id" not in args
    args, _ = n.resolve_company_args("list_companies", {}, 15, {"list_companies"})
    assert "company_id" not in args


def test_company_suffix():
    assert n.company_suffix("14", 15, "النخبة").endswith("(ضمن شركة النخبة)")
    assert n.company_suffix("في النخبة 13", 15, "النخبة") == "في النخبة 13"
    assert n.company_suffix("14", None, None) == "14"


def test_session_context_mentions_company_and_ambiguity_rule():
    ctx = n.build_session_context(15, "النخبة")
    assert "15" in ctx and "النخبة" in ctx and "غامضة" in ctx
    assert "الشركة المحددة" not in n.build_session_context(None, None)
