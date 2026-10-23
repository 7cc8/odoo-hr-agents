"""Deterministic cleaning stage (cleaning.py) wired into parser.parse_xlsx."""
import openpyxl
import pytest

import dry_run_report
import generate_employee_template as gen
from cleaning import clean_field
from musleh_service import MuslehService
from parser import parse_xlsx
from tests.test_employee_template_routing import (
    COMPANY, DEPT, JOB, Repo, SNAPSHOT, COMPANY_REC, EXISTING, _filled_template, _row,
)


# ---------- the pure functions ----------

@pytest.mark.parametrize("header,raw,expected,rule", [
    ("mobile_phone", "٠٥٠٠٠٠٠٠٠١", "0500000001", "digits_to_latin"),
    ("mobile_phone", "۰۵۰۰۰۰۰۰۰۱", "0500000001", "digits_to_latin"),
    ("mobile_phone", "500000001", "0500000001", "restore_leading_zero"),
    ("mobile_phone", "+966 50 000 0001", "+966500000001", "strip_phone_separators"),
    ("mobile_phone", "0500 000 001", "0500000001", "strip_phone_separators"),
    ("mobile_phone", "00966500000001", "+966500000001", "international_prefix_00_to_plus"),
    ("mobile_phone", "+9660500000001", "+966500000001", "normalize_saudi_country_code"),
    ("work_email", " Ahmed @Example.COM", "ahmed@example.com", "lowercase_email"),
    ("hiring_date", "2026-6-5", "2026-06-05", "zero_pad_iso_date"),
    ("hiring_date", "25-06-2026", "2026-06-25", "day_first_to_iso"),
    ("hiring_date", "06-25-2026", "2026-06-25", "month_first_to_iso"),
    ("hiring_date", "٢٠٢٦-٠٦-٠٥", "2026-06-05", "digits_to_latin"),
    ("hiring_date", "2026.06.05", "2026-06-05", "normalize_date_separators"),
    ("name", "محـمد", "محمد", "remove_tatweel"),
    ("name", "كريم", "كريم", None),
])
def test_cleaning_rules(header, raw, expected, rule):
    if header == "name" and rule is None:
        raw = "کریم"  # Persian kaf and yeh typed by mistake
        rule = "persian_letters_to_arabic"
        expected = "كريم"
    res = clean_field(header, raw)
    assert res.value == expected
    assert rule in res.rules
    assert res.issues == ()


@pytest.mark.parametrize("header,value", [
    ("mobile_phone", "0500000001"), ("mobile_phone", "+966500000001"),
    ("work_phone", "0112345678"), ("work_phone", "011 234 5678"), ("work_phone", "+20 10 1234 5678"),
    ("hiring_date", "2026-06-05"), ("work_email", "a@b.com"),
    ("name", "موسى"), ("name", "أحمد محمد"), ("name", "فاطمة"), ("department", "الإدارة العليا / المالية"),
])
def test_already_acceptable_values_are_never_rewritten(header, value):
    res = clean_field(header, value)
    assert (res.value, res.rules, res.issues) == (value, (), ())


@pytest.mark.parametrize("raw,issue", [
    ("05-06-2026", "ambiguous_date"),          # day/month cannot be told apart: never guess
    ("1447-03-12", "possible_hijri_date"),     # Hijri years are not converted
    ("2026-13-40", "invalid_date"),
    ("30-30-2026", "invalid_date"),
    ("next monday", "unrecognized_date_format"),
])
def test_unsafe_dates_are_left_alone_and_reported(raw, issue):
    res = clean_field("hiring_date", raw)
    assert res.value == raw
    assert issue in res.issues


def test_short_saudi_mobile_is_reported_not_changed():
    res = clean_field("mobile_phone", "05000")
    assert res.value == "05000" and res.issues == ("mobile_phone_not_saudi_format",)
    assert clean_field("work_phone", "05000").issues == ()  # work phones may be anything


def test_date_policy_agrees_with_musleh():
    """cleaning.clean_date and MuslehService.heal_date_format must never disagree on a result."""
    for raw in ["25-06-2026", "06-25-2026", "2026-06-25", "05-06-2026", "2026-13-40"]:
        musleh = MuslehService.heal_date_format(raw)
        cleaned = clean_field("hiring_date", raw)
        converted = cleaned.value if not cleaned.issues else None
        if musleh is not None:
            assert converted == musleh, raw
        else:
            assert converted is None or converted == raw, raw


# ---------- through the real template and the strict pipeline ----------

DIRTY = _row("محـمد کریم", " Sara@Example.COM", "٠٥٠٠٠٠٠٠٠٩")
DIRTY[5] = "25-06-2026"  # hiring_date


@pytest.fixture
def repo(monkeypatch):
    r = Repo([COMPANY_REC], [DEPT], [JOB], [EXISTING])
    monkeypatch.setattr(dry_run_report, "OdooReadonlyRepository", lambda *a, **k: r)
    return r


def test_parsed_row_carries_cleaned_values_and_a_change_log(tmp_path):
    path = _filled_template(tmp_path, [DIRTY])
    row = parse_xlsx(path)["rows"][0]
    values = {k: v["value"] for k, v in row["fields"].items()}
    assert values["name"] == "محمد كريم"
    assert values["work_email"] == "sara@example.com"
    assert values["mobile_phone"] == "0500000009"
    assert values["hiring_date"] == "2026-06-25"
    assert row["fields"]["mobile_phone"]["raw"] == "٠٥٠٠٠٠٠٠٠٩"          # what the user typed is kept
    by_field = {c["field"]: c for c in row["corrections"]}
    assert set(by_field) == {"name", "work_email", "mobile_phone", "hiring_date"}
    assert by_field["mobile_phone"]["before"] == "٠٥٠٠٠٠٠٠٠٩" and by_field["mobile_phone"]["after"] == "0500000009"
    assert row["cleaning_issues"] == []


def test_clean_rows_keep_their_hash_and_have_no_corrections(tmp_path):
    path = _filled_template(tmp_path, [_row("سارة الحربي", "sara@example.com", "0500000001")])
    row = parse_xlsx(path)["rows"][0]
    assert row["corrections"] == []
    # nothing was changed, so raw == value for every field (and so the hash is the pre-cleaning one)
    assert all(f["raw"] == f["value"] for f in row["fields"].values())


def test_cleaning_is_deterministic_so_writer_py_sees_the_same_hashes(tmp_path):
    path = _filled_template(tmp_path, [DIRTY, _row("نورة", "n@example.com", "500000003")])
    first, second = parse_xlsx(path), parse_xlsx(path)
    assert [r["row_hash"] for r in first["rows"]] == [r["row_hash"] for r in second["rows"]]


def test_work_phone_alias_is_not_reported_twice(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Employees"
    ws.append(["name", "work_email", "mobile_phone", "job_title", "company", "department", "job"])
    ws.append(["سارة", "s@example.com", "٠٥٠٠٠٠٠٠٠١", "محاسبة", COMPANY, DEPT["complete_name"], JOB["name"]])
    path = tmp_path / "alias.xlsx"
    wb.save(path)
    row = parse_xlsx(path)["rows"][0]
    assert [c["field"] for c in row["corrections"]] == ["mobile_phone"]


def test_report_exposes_corrections_issues_and_a_summary(tmp_path, repo):
    ambiguous = _row("خالد", "k@example.com", "0500000002")
    ambiguous[5] = "05-06-2026"
    path = _filled_template(tmp_path, [DIRTY, ambiguous])
    report = dry_run_report.build_full_report(path)
    by_row = {r["excel_row_number"]: r for r in report["rows"]}
    assert {c["field"] for c in by_row[3]["corrections"]} == {"name", "work_email", "mobile_phone", "hiring_date"}
    assert [i["code"] for i in by_row[4]["cleaning_issues"]] == ["ambiguous_date"]
    assert report["summary"]["cleaning"] == {"rows_with_corrections": 1, "corrections_count": 4, "issues_count": 1}


def test_cleaned_email_is_what_the_duplicate_check_sees(tmp_path, repo):
    """'  DUP@Example.com ' used to look different to a person but the match key already folded it;
    the value written to Odoo is now the cleaned one too."""
    path = _filled_template(tmp_path, [_row("نورة", " DUP@Example.com", "0500000003")])
    report = dry_run_report.build_full_report(path)
    assert report["rows"][0]["failure_code"] == "duplicate_existing_employee"
    assert parse_xlsx(path)["rows"][0]["fields"]["work_email"]["value"] == "dup@example.com"
