"""Deterministic, repository-free cleaning of the values read from an Excel upload.

Runs inside parser.parse_xlsx, so the dry-run, the approval and writer.py (which re-parses the
file and compares row hashes) all see exactly the same cleaned values. It must therefore stay
pure: same input -> same output, no I/O, no Odoo, no LLM.

Principles
* Fix only what is unambiguous and mechanical (wrong digit script, separators, case, a missing
  leading zero, an unambiguous date order, decorative characters, Persian letters in Arabic text).
* Never guess. An ambiguous date (05-06-2026) or an unrecognised shape is left untouched and
  reported as an *issue*.
* Never change a value that is already in an accepted form (a valid +9665... or 05... number,
  an ISO date).
* Every change is reported as (field, before, after, rules) so the report can show it.

Spelling of names, and mapping a department/job to Odoo's canonical name, are NOT done here:
the first is a suggestion for a human, the second needs the live Odoo reference snapshot.
"""
from __future__ import annotations

import re
from datetime import date
from typing import NamedTuple, Tuple

from normalization import ARABIC_DIGITS_MAP, EASTERN_ARABIC_DIGITS_MAP

TEXT_HEADERS = frozenset({"name", "job_title", "company", "department", "job"})
PHONE_HEADERS = frozenset({"work_phone", "mobile_phone"})

TATWEEL = "\u0640"
# Persian/Urdu letters that appear in Arabic text typed on the wrong keyboard layout.
# (U+0649 alef maksura is a legitimate Arabic letter and is deliberately NOT touched.)
PERSIAN_TO_ARABIC = {"\u06a9": "\u0643", "\u06cc": "\u064a"}  # ک -> ك , ی -> ي

_PHONE_SEPARATORS_RE = re.compile(r"[\s\-().\u00a0]")
_SAUDI_COUNTRY_RE = re.compile(r"^\+?9660?(5\d{8})$")
_ISO_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_DMY_RE = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")


class CleanResult(NamedTuple):
    value: str
    rules: Tuple[str, ...]
    issues: Tuple[str, ...]


def _digits_to_latin(text: str) -> str:
    return text.translate(ARABIC_DIGITS_MAP).translate(EASTERN_ARABIC_DIGITS_MAP)


def clean_text(value: str) -> CleanResult:
    rules = []
    out = value
    if TATWEEL in out:
        out = re.sub(r"\s+", " ", out.replace(TATWEEL, "")).strip()
        rules.append("remove_tatweel")
    swapped = "".join(PERSIAN_TO_ARABIC.get(ch, ch) for ch in out)
    if swapped != out:
        out = swapped
        rules.append("persian_letters_to_arabic")
    return CleanResult(out, tuple(rules), ())


def clean_email(value: str) -> CleanResult:
    if not value:
        return CleanResult(value, (), ())
    rules = []
    out = value
    if re.search(r"\s", out):
        out = re.sub(r"\s+", "", out)
        rules.append("remove_email_spaces")
    if out != out.lower():
        out = out.lower()
        rules.append("lowercase_email")
    return CleanResult(out, tuple(rules), ())


def _saudi_mobile_form(stripped: str):
    """Canonical Saudi mobile for a separator-free string, plus the rules that were needed.

    Returns (canonical, rules) or None when the string is not recognisably a Saudi mobile.
    The canonical form keeps the style the user typed: +9665xxxxxxxx stays international,
    05xxxxxxxx stays local; nothing valid is rewritten into the other style.
    """
    rules = []
    text = stripped
    if text.startswith("00") and len(text) > 2:
        text = "+" + text[2:]
        rules.append("international_prefix_00_to_plus")
    m = _SAUDI_COUNTRY_RE.match(text)
    if m:
        target = "+966" + m.group(1)
        if target != text:
            rules.append("normalize_saudi_country_code")
        return target, rules
    if re.fullmatch(r"5\d{8}", text):  # Excel drops the leading zero of a numeric cell
        return "0" + text, rules + ["restore_leading_zero"]
    if re.fullmatch(r"05\d{8}", text):
        return text, rules
    return None


def clean_phone(value: str, *, expect_mobile: bool) -> CleanResult:
    if not value:
        return CleanResult(value, (), ())
    rules, issues = [], []
    out = _digits_to_latin(value)
    if out != value:
        rules.append("digits_to_latin")
    stripped = _PHONE_SEPARATORS_RE.sub("", out)

    saudi = _saudi_mobile_form(stripped)
    if saudi is not None:
        canonical, saudi_rules = saudi
        if stripped != out:
            rules.append("strip_phone_separators")
        rules.extend(saudi_rules)
        out = canonical
    elif expect_mobile and stripped.startswith(("05", "+966", "966", "00966")):
        issues.append("mobile_phone_not_saudi_format")
    # Anything else (foreign numbers, landlines) keeps the separators the user typed.
    return CleanResult(out, tuple(rules), tuple(issues))


def clean_date(value: str) -> CleanResult:
    """Expects the value already passed through normalization.normalize_date_text."""
    if not value:
        return CleanResult(value, (), ())
    rules, issues = [], []
    out = _digits_to_latin(value)
    if out != value:
        rules.append("digits_to_latin")
    swapped = re.sub(r"[\\.]", "-", out)
    if swapped != out:
        out = swapped
        rules.append("normalize_date_separators")

    iso = _ISO_RE.match(out)
    dmy = _DMY_RE.match(out)
    if iso:
        year, month, day = (int(g) for g in iso.groups())
    elif dmy:
        first, second, year = (int(g) for g in dmy.groups())
        if first > 12 and second <= 12:
            day, month = first, second
            rules.append("day_first_to_iso")
        elif second > 12 and first <= 12:
            month, day = first, second
            rules.append("month_first_to_iso")
        elif first <= 12 and second <= 12:
            return CleanResult(out, tuple(rules), ("ambiguous_date",))
        else:
            return CleanResult(out, tuple(rules), ("invalid_date",))
    else:
        return CleanResult(out, tuple(rules), ("unrecognized_date_format",))

    try:
        date(year, month, day)
    except ValueError:
        return CleanResult(out, tuple(rules), ("invalid_date",))
    if year < 1900:  # 14xx-15xx are Hijri years: never converted, never treated as Gregorian
        return CleanResult(out, tuple(rules), ("possible_hijri_date",))
    padded = f"{year:04d}-{month:02d}-{day:02d}"
    if padded != out:
        if not any(r.endswith("_to_iso") for r in rules):
            rules.append("zero_pad_iso_date")
        out = padded
    return CleanResult(out, tuple(rules), ())


def clean_field(header: str, value: str) -> CleanResult:
    if header in TEXT_HEADERS:
        return clean_text(value)
    if header == "work_email":
        return clean_email(value)
    if header in PHONE_HEADERS:
        return clean_phone(value, expect_mobile=(header == "mobile_phone"))
    if header == "hiring_date":
        return clean_date(value)
    return CleanResult(value, (), ())
