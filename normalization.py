import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal

INVISIBLE_CHARS = {
    "\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\u00a0", "\u200c",
}

ARABIC_DIGITS_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
EASTERN_ARABIC_DIGITS_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

ARABIC_DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def remove_invisible_chars(text: str) -> str:
    out = []
    for ch in text:
        if ch == "\u00a0":
            out.append(" ")
        elif ch in INVISIBLE_CHARS:
            continue
        else:
            out.append(ch)
    return "".join(out)


def collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_value_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = remove_invisible_chars(text)
    text = collapse_spaces(text)
    return text


def to_text_preserve(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return format(Decimal(str(value)).normalize(), "f")
    return str(value)


def normalize_date_text(text: str) -> str:
    text = clean_value_text(text)
    if not text:
        return ""
    text = text.replace("/", "-")
    if " " in text:
        text = text.split(" ")[0]
    return text


def normalize_header(text: str) -> str:
    cleaned = clean_value_text(text).lower()
    return cleaned.rstrip(" *").strip()


def generic_match_key(value: str):
    if not value:
        return None
    value = clean_value_text(value)
    value = value.translate(ARABIC_DIGITS_MAP)
    value = value.translate(EASTERN_ARABIC_DIGITS_MAP)
    value = value.replace("ى", "ي").replace("ک", "ك")
    # Unify alef forms and taa marbuta for MATCHING ONLY (never for stored values).
    value = re.sub("[أإآٱ]", "ا", value)
    value = value.replace("ة", "ه")
    value = ARABIC_DIACRITICS_RE.sub("", value)
    value = value.lower()
    value = collapse_spaces(value)
    return value or None


def name_match_key(value: str):
    return generic_match_key(value)


def reference_match_key(value: str):
    return generic_match_key(value)


def email_match_key(value: str):
    if not value:
        return None
    return clean_value_text(value).lower() or None


def is_valid_email_format(value: str) -> bool:
    if not value:
        return False
    return bool(EMAIL_RE.match(value.strip()))


def phone_match_key(value: str):
    if not value:
        return None
    v = clean_value_text(value)
    v = v.translate(ARABIC_DIGITS_MAP)
    v = v.translate(EASTERN_ARABIC_DIGITS_MAP)
    v = re.sub(r"[\s\-\(\)]", "", v)
    if not v:
        return None

    if v.startswith("00"):
        v = "+" + v[2:]

    if v.startswith("0") and not v.startswith("00"):
        v = "+966" + v[1:]
    elif v.startswith("966") and not v.startswith("+"):
        v = "+" + v

    digits_only = re.sub(r"[^0-9+]", "", v)
    return digits_only or None


def safe_excel_text(value: str) -> str:
    if value is None:
        return ""
    value = str(value)
    if value[:1] in {"=", "+", "-", "@"}:
        return "'" + value
    return value