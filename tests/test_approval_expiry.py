"""Approval files written by the web endpoints and make_approval.py carried no expires_at, and
Approval.from_dict then gave them 2099-12-31, so a web approval never expired."""
import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import approval_schema
import make_approval
import web_service
from approval_schema import Approval, ApprovalSchemaError, new_approval_timestamps

TOKEN = "approval-expiry-test-token"


def _base(**extra):
    data = {
        "run_id": "run1", "source_hash": "h", "source_file_name": "f.xlsx", "approved_by": "tester",
        "approved_row_hashes": ["a"],
    }
    data.update(extra)
    return data


def _iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_ttl_defaults_to_five_minutes_and_is_configurable(monkeypatch):
    monkeypatch.delenv("APPROVAL_TTL_MINUTES", raising=False)
    assert approval_schema.approval_ttl_minutes() == 5
    monkeypatch.setenv("APPROVAL_TTL_MINUTES", "12")
    assert approval_schema.approval_ttl_minutes() == 12
    for bad in ("0", "-3", "abc", ""):
        monkeypatch.setenv("APPROVAL_TTL_MINUTES", bad)
        assert approval_schema.approval_ttl_minutes() == 5


def test_new_timestamps_are_consistent(monkeypatch):
    monkeypatch.setenv("APPROVAL_TTL_MINUTES", "7")
    now = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    assert new_approval_timestamps(now) == {
        "approved_at": "2026-01-01T10:00:00Z", "expires_at": "2026-01-01T10:07:00Z", "is_consumed": False}


def test_missing_expiry_is_derived_from_approved_at_not_2099():
    recent = datetime.now(timezone.utc) - timedelta(minutes=1)
    ok = Approval.from_dict(_base(approved_at=_iso(recent)))
    assert ok.expires_at.startswith(str(recent.year)) and not ok.expires_at.startswith("2099")


def test_an_old_approval_without_expiry_is_now_expired():
    old = datetime.now(timezone.utc) - timedelta(hours=3)
    with pytest.raises(ApprovalSchemaError, match="expired"):
        Approval.from_dict(_base(approved_at=_iso(old)))


def test_explicit_expiry_is_still_honoured():
    now = datetime.now(timezone.utc)
    assert Approval.from_dict(_base(approved_at=_iso(now), expires_at=_iso(now + timedelta(minutes=30)), is_consumed=False))
    with pytest.raises(ApprovalSchemaError, match="expired"):
        Approval.from_dict(_base(approved_at=_iso(now), expires_at=_iso(now - timedelta(seconds=1)), is_consumed=False))


def test_naive_timestamps_are_utc_not_the_machine_time_zone(monkeypatch):
    """A naive expiry used to be compared with the machine's local time (wrong by hours outside UTC)."""
    if hasattr(time, "tzset"):
        monkeypatch.setenv("TZ", "Asia/Riyadh")
        time.tzset()
        try:
            soon = (datetime.now(timezone.utc) + timedelta(minutes=3)).replace(tzinfo=None).isoformat()
            assert Approval.from_dict(_base(approved_at=_iso(datetime.now(timezone.utc)), expires_at=soon, is_consumed=False))
        finally:
            monkeypatch.delenv("TZ")
            time.tzset()
    else:
        soon = (datetime.now(timezone.utc) + timedelta(minutes=3)).replace(tzinfo=None).isoformat()
        assert Approval.from_dict(_base(approved_at=_iso(datetime.now(timezone.utc)), expires_at=soon, is_consumed=False))


def test_consumed_approval_is_still_rejected():
    now = datetime.now(timezone.utc)
    with pytest.raises(ApprovalSchemaError, match="consumed"):
        Approval.from_dict(_base(approved_at=_iso(now), expires_at=_iso(now + timedelta(minutes=3)), is_consumed=True))


# ---- the writers ----

def _report(tmp_path):
    report = {"header": {"run_id": "run1", "source_hash": "h", "source_file_name": "f.xlsx"},
              "rows": [{"excel_row_number": 3, "final_status": "accepted", "row_hash": "hash3"}]}
    path = tmp_path / "dry_run_report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def test_make_approval_cli_writes_an_expiry(tmp_path):
    out = tmp_path / "approval.json"
    code = make_approval.main(["--report", str(_report(tmp_path)), "--input", "f.xlsx", "--approved-by", "khaled",
                               "--rows", "3", "--out", str(out)])
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    approved = datetime.strptime(data["approved_at"], "%Y-%m-%dT%H:%M:%SZ")
    assert datetime.strptime(data["expires_at"], "%Y-%m-%dT%H:%M:%SZ") - approved == timedelta(minutes=5)
    assert data["is_consumed"] is False
    assert Approval.load(out).approved_row_hashes == ["hash3"]


def test_web_approve_endpoint_writes_an_expiry(tmp_path, monkeypatch):
    monkeypatch.setenv("WRITE_API_TOKEN", TOKEN)
    monkeypatch.setattr(web_service, "OUTPUT_ROOT", tmp_path.resolve())
    report = _report(tmp_path)
    r = TestClient(web_service.app).post(
        "/api/approve", headers={"X-API-Key": TOKEN},
        json={"report_path": str(report), "rows": [3], "approved_by": "khaled"})
    assert r.status_code == 200, r.text
    data = json.loads((tmp_path / "approval.json").read_text(encoding="utf-8"))
    assert data["expires_at"] > data["approved_at"] and data["is_consumed"] is False
    assert r.json()["approval"]["expires_at"] == data["expires_at"]
    assert not data["expires_at"].startswith("2099")


def test_approve_and_execute_writes_an_expiry_before_calling_the_writer(tmp_path, monkeypatch):
    """The endpoint builds its own approval.json; capture it at the moment writer.run_writer is called."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WRITE_API_TOKEN", TOKEN)
    for key, value in {"ODOO_URL": "http://odoo.invalid", "ODOO_DB": "db", "ODOO_USERNAME": "u", "ODOO_API_KEY": "k"}.items():
        monkeypatch.setenv(key, value)
    run_dir = tmp_path / "output" / "runabc_20260101"
    run_dir.mkdir(parents=True)
    source = tmp_path / "employees.xlsx"
    source.write_bytes(b"x")
    (run_dir / "telegram_session.json").write_text(json.dumps({"input_path": str(source)}), encoding="utf-8")
    (run_dir / "dry_run_report.json").write_text(json.dumps({
        "header": {"run_id": "runabc", "source_hash": "h", "source_file_name": "employees.xlsx"},
        "rows": [{"excel_row_number": 3, "final_status": "accepted", "row_hash": "hash3"}]}), encoding="utf-8")

    seen = {}

    def fake_run_writer(input_path, report_path, approval_path, out_dir, repo, gateway, **kwargs):
        seen["approval"] = json.loads(open(approval_path, encoding="utf-8").read())
        return {"footer": {"status_counts": {"created": 0}}, "rows": []}

    monkeypatch.setattr(web_service.writer, "run_writer", fake_run_writer)
    monkeypatch.setattr(web_service, "OdooWriteGateway", lambda *a, **k: object())
    monkeypatch.setattr(web_service, "OdooReadonlyRepository", lambda *a, **k: type("R", (), {"get_default_company": lambda s: {"id": 1}})())
    r = TestClient(web_service.app).post("/api/approve-and-execute", headers={"X-API-Key": TOKEN}, json={"run_id": "runabc"})
    assert r.status_code == 200, r.text
    approval = seen["approval"]
    assert approval["is_consumed"] is False and not approval["expires_at"].startswith("2099")
    approved = datetime.strptime(approval["approved_at"], "%Y-%m-%dT%H:%M:%SZ")
    assert datetime.strptime(approval["expires_at"], "%Y-%m-%dT%H:%M:%SZ") - approved == timedelta(minutes=5)


def test_specific_error_types_raised():
    now = datetime.now(timezone.utc)
    # Expired
    with pytest.raises(approval_schema.ApprovalExpiredError) as exc_exp:
        Approval.from_dict(_base(approved_at=_iso(now - timedelta(minutes=10)), expires_at=_iso(now - timedelta(minutes=5)), is_consumed=False))
    assert "expired" in str(exc_exp.value).lower()

    # Consumed
    with pytest.raises(approval_schema.ApprovalAlreadyConsumedError) as exc_con:
        Approval.from_dict(_base(approved_at=_iso(now), expires_at=_iso(now + timedelta(minutes=5)), is_consumed=True))
    assert "consumed" in str(exc_con.value).lower()


def test_write_endpoint_returns_arabic_expiry_message(tmp_path, monkeypatch):
    monkeypatch.setenv("WRITE_API_TOKEN", TOKEN)
    monkeypatch.setattr(web_service, "UPLOAD_DIR", tmp_path)
    run_dir = tmp_path / "output" / "runexp_20260101"
    run_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    now = datetime.now(timezone.utc)
    expired_approval = _base(
        approved_at=_iso(now - timedelta(minutes=10)),
        expires_at=_iso(now - timedelta(minutes=5)),
        is_consumed=False,
    )
    (run_dir / "approval.json").write_text(json.dumps(expired_approval), encoding="utf-8")
    (run_dir / "dry_run_report.json").write_text(json.dumps({
        "header": {"run_id": "runexp", "source_hash": "h", "source_file_name": "employees.xlsx"},
        "rows": [{"excel_row_number": 2, "final_status": "accepted", "row_hash": "hash1"}]
    }), encoding="utf-8")
    (tmp_path / "employees.xlsx").write_bytes(b"x")

    r = TestClient(web_service.app).post(
        "/api/write",
        headers={"X-API-Key": TOKEN},
        json={"run_id": "runexp", "company_id": 1, "max_rows": 10}
    )
    assert r.status_code == 400
    assert "انتهت المهلة الزمنية للاعتماد (5 دقائق)" in r.json()["detail"]

