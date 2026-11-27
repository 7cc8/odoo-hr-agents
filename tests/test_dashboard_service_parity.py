"""Regression coverage for the dashboard's HR actions and real pagination."""
from html.parser import HTMLParser
import json
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
import re

import pytest

from agent_events_service import AgentEventsService
from api.routers import hr_services as hr


class DashboardActions(HTMLParser):
    def __init__(self):
        super().__init__()
        self.calls = set()

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name.startswith("on") and value:
                self.calls.update(re.findall(r"(?<![.\w])([A-Za-z_]\w*)\s*\(", value))


def test_excel_history_opens_only_the_requested_report(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from api.routers import excel
    from web_service import app

    monkeypatch.setattr(excel, "OUTPUT_ROOT", tmp_path)
    for folder, run_id in [("shared_first", "shared"), ("shared_second", "shared"), ("unique_first", "unique")]:
        report_dir = tmp_path / folder
        report_dir.mkdir()
        (report_dir / "dry_run_report.json").write_text(
            json.dumps({"header": {"run_id": run_id}, "summary": {"template_title": folder}}),
            encoding="utf-8",
        )

    with TestClient(app) as client:
        runs = client.get("/api/runs").json()
        assert {run["folder"] for run in runs} == {"shared_first", "shared_second", "unique_first"}
        report = client.get("/api/reports/dry-run/shared_second")
        assert report.json()["summary"]["template_title"] == "shared_second"
        assert client.get("/api/reports/dry-run/unique").status_code == 200
        assert client.get("/api/reports/dry-run/shared").status_code == 409
        assert client.get("/api/reports/dry-run/unknown").status_code == 404


def test_dashboard_controls_have_handlers():
    frontend = Path(__file__).resolve().parents[1] / "frontend"
    page = (frontend / "dashboard.html").read_text("utf-8")
    controls = DashboardActions()
    controls.feed(page)
    scripts = "\n".join((frontend / path).read_text("utf-8")
                        for path in re.findall(r'<script src="/frontend/([^"?]+)', page))
    for call in controls.calls - {"if", "confirm", "alert", "Number"}:
        assert re.search(r"\b" + call + r"\b", scripts), call


def test_service_catalog_includes_every_mounted_hr_domain():
    source = (Path(__file__).resolve().parents[1] / "frontend/js/hr-services.js").read_text("utf-8")
    domains = source.split("const domains = {", 1)[1].split("};", 1)[0]
    listed = set(re.findall(r'(\w+):\s*"', domains))
    assert listed == {route.path.split("/")[2] for route in hr.router.routes}


def test_operations_filter_before_pagination():
    service = object.__new__(AgentEventsService)
    service._lock = RLock()
    service.operations = {
        str(i): {"operation_id": str(i), "status": "completed" if i % 2 else "failed",
                 "active_agent": "fahas", "updated_at": str(i)} for i in range(6)
    }
    rows, count = service.operations_page(1, 1, "فاحص", "critical")
    assert count == 3
    assert [row["operation_id"] for row in rows] == ["2"]
    assert service.operations_page(10, 0, "غير موجود", "all") == ([], 0)


@pytest.mark.parametrize("payload", [hr.LetterApplyPayload, hr.WarningApplyPayload, hr.ExpenseApplyPayload])
def test_operator_confirmation_requires_user_input(payload):
    assert payload(approval_token="draft").user_confirmation_text == ""


def test_document_preview_reused_only_on_same_connection(monkeypatch):
    class Service:
        def __init__(self, repo, gateway):
            self.drafts = {}

    config = {"url": "local", "db": "first", "username": "test", "api_key": "fixture"}
    monkeypatch.setattr(hr, "_document_services", {})
    monkeypatch.setattr(hr, "_document_connection", None)
    monkeypatch.setattr(hr, "get_active_odoo_config", lambda: config)
    monkeypatch.setattr(hr, "OdooReadonlyRepository", lambda: SimpleNamespace(**config))
    first = hr._document_service(Service, SimpleNamespace)
    first.drafts["example"] = 1
    assert hr._document_service(Service, SimpleNamespace).drafts == {"example": 1}
    config["db"] = "second"
    assert hr._document_service(Service, SimpleNamespace).drafts == {}
def test_employee_choices_use_authorized_company_and_minimal_fields(monkeypatch):
    from fastapi import HTTPException
    from api.routers import excel
    import odoo_readonly_repository as odoo

    calls = []
    class Repo:
        def get_company_ids(self):
            return [7]

        def _execute_kw(self, model, method, args, options):
            calls.append((model, method, args, options))
            return [{"id": 4, "name": "مثال"}]

    monkeypatch.setattr(excel, "verify_api_auth", lambda request: None)
    monkeypatch.setattr(odoo, "get_shared_readonly_repository", lambda: Repo())
    with pytest.raises(HTTPException) as denied:
        excel.find_employee_options(8, "مثال", None)
    assert denied.value.status_code == 403
    assert excel.find_employee_options(7, "مثال", None)["employees"][0]["id"] == 4
    model, method, args, options = calls.pop()
    assert (model, method) == ("hr.employee", "search_read")
    assert options["context"]["allowed_company_ids"] == [7]
    assert options["fields"] == ["id", "name"]
    assert ("company_id", "=", 7) in args[0]


def test_shared_odoo_transport_serializes_parallel_reads():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Lock
    from time import sleep
    from odoo_readonly_repository import OdooReadonlyRepository

    transport_lock = Lock()
    class Transport:
        def execute_kw(self, *args):
            assert transport_lock.acquire(blocking=False)
            try:
                sleep(.01)
                return 1
            finally:
                transport_lock.release()

    repo = OdooReadonlyRepository(url="http://localhost", db="fixture", username="test", api_key="fixture")
    repo._models = Transport()
    repo._uid = 1
    with ThreadPoolExecutor(4) as pool:
        assert list(pool.map(lambda _: repo._execute_kw("hr.employee", "search_count", [[]]), range(4))) == [1]*4
