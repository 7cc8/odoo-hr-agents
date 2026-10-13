"""Centralized Odoo Configuration and Multi-Database Connection Manager.

Allows dynamic switching between multiple Odoo instances and databases:
1. Manages connection credentials in config/odoo_connection.json with fallback to .env / os.environ.
2. Validates live XML-RPC connections before saving.
3. Provides helper to test connection, retrieve companies, branches, and departments.
"""

from __future__ import annotations

import json
import os
import xmlrpc.client
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = ROOT_DIR / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "odoo_connection.json"


def normalize_odoo_url(url: str) -> str:
    """Cleans and normalizes Odoo base URL by stripping paths like /odoo, /web, etc."""
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        if parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    url = url.split("/odoo")[0].split("/web")[0].rstrip("/")
    return url


def get_active_odoo_config() -> Dict[str, str]:
    """Returns the currently active Odoo credentials (from json or env)."""
    config = {
        "url": "",
        "db": "",
        "username": "",
        "api_key": "",
    }
    # 1. First check config file if exists
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    config.update({k: v for k, v in saved.items() if k in config and v})
        except Exception:
            pass

    # 2. Fall back to os.environ if any field is missing
    if not config["url"]:
        config["url"] = os.environ.get("ODOO_URL", "")
    if not config["db"]:
        config["db"] = os.environ.get("ODOO_DB", "")
    if not config["username"]:
        config["username"] = os.environ.get("ODOO_USER") or os.environ.get("ODOO_USERNAME", "")
    if not config["api_key"]:
        config["api_key"] = os.environ.get("ODOO_API_KEY", "")

    if config["url"]:
        config["url"] = normalize_odoo_url(config["url"])

    return config


def test_odoo_connection(url: str, db: str, username: str, api_key: str, timeout: int = 15) -> Dict[str, Any]:
    """Tests XML-RPC authentication against a specified Odoo instance."""
    url = normalize_odoo_url(url)
    if not url or not db or not username or not api_key:
        return {"ok": False, "error": "جميع الحقول (الرابط، اسم القاعدة، اسم المستخدم، مفتاح API) مطلوبة."}

    try:
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
        uid = common.authenticate(db, username, api_key, {})
        if not uid:
            return {"ok": False, "error": "فشل التحقق: اسم المستخدم أو مفتاح API غير صحيح لقاعدة البيانات المحددة."}

        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
        version = common.version()

        # Query companies & branches
        companies = models.execute_kw(
            db, uid, api_key,
            "res.company", "search_read", [[]],
            {"fields": ["id", "name", "child_ids"], "limit": 20}
        )

        emp_count = 0
        try:
            emp_count = models.execute_kw(db, uid, api_key, "hr.employee", "search_count", [[]])
        except Exception:
            pass

        dept_count = 0
        try:
            dept_count = models.execute_kw(db, uid, api_key, "hr.department", "search_count", [[]])
        except Exception:
            pass

        user_company_id = None
        user_company_name = None
        try:
            u_info = models.execute_kw(db, uid, api_key, "res.users", "read", [[uid]], {"fields": ["company_id"]})
            if u_info and u_info[0].get("company_id"):
                user_company_id = u_info[0]["company_id"][0]
                user_company_name = u_info[0]["company_id"][1]
        except Exception:
            pass

        return {
            "ok": True,
            "uid": uid,
            "server_version": version.get("server_version", "Unknown"),
            "companies": companies or [],
            "company_count": len(companies or []),
            "user_company_id": user_company_id or (companies[0]["id"] if companies else None),
            "user_company_name": user_company_name or (companies[0]["name"] if companies else "الشركة المحددة"),
            "employee_count": emp_count,
            "department_count": dept_count,
        }
    except Exception as exc:
        err_msg = str(exc)
        if "database" in err_msg and ("does not exist" in err_msg or "KeyError" in err_msg):
            return {"ok": False, "error": f"قاعدة البيانات '{db}' غير موجودة على خادم Odoo هذا. في نسخ Odoo Online يكون اسم القاعدة عادة هو البادئة فقط (مثال: 'edu-training1555')."}
        if "Access Denied" in err_msg or "authenticate" in err_msg:
            return {"ok": False, "error": "تم رفض الدخول: يرجى التحقق من اسم المستخدم ومفتاح API."}
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def save_active_odoo_config(url: str, db: str, username: str, api_key: str) -> None:
    """Saves verified credentials to config/odoo_connection.json and updates current process os.environ."""
    data = {
        "url": normalize_odoo_url(url),
        "db": db.strip(),
        "username": username.strip(),
        "api_key": api_key.strip(),
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Sync current runtime environment
    os.environ["ODOO_URL"] = data["url"]
    os.environ["ODOO_DB"] = data["db"]
    os.environ["ODOO_USER"] = data["username"]
    os.environ["ODOO_USERNAME"] = data["username"]
    os.environ["ODOO_API_KEY"] = data["api_key"]


def clear_active_odoo_config() -> None:
    """Completely clears saved Odoo connection credentials from json file and os.environ."""
    if CONFIG_FILE.exists():
        try:
            CONFIG_FILE.unlink()
        except Exception:
            pass
    for var in ["ODOO_URL", "ODOO_DB", "ODOO_USER", "ODOO_USERNAME", "ODOO_API_KEY"]:
        os.environ.pop(var, None)

