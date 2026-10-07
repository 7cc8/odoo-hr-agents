"""Verify current .env credentials against Odoo (read-only, changes nothing).

Usage:
    python scripts/rotate_api_key.py --verify   # Test that the current API key works
    python scripts/rotate_api_key.py --info      # Show connection info (without the key itself)
"""

from __future__ import annotations

import argparse
import os
import sys
import xmlrpc.client
from pathlib import Path

# Load .env from project root if python-dotenv is available, otherwise rely on
# environment variables already being set.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"


def _load_dotenv() -> None:
    """Best-effort .env loading without requiring python-dotenv as a dependency."""
    if not _ENV_PATH.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore[import-untyped]

        load_dotenv(_ENV_PATH)
    except ImportError:
        # Fall back: parse .env manually (simple KEY=VALUE lines)
        with open(_ENV_PATH, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def _get_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        print(f"ERROR: Missing environment variable: {key}", file=sys.stderr)
        print(f"  Make sure {_ENV_PATH} exists and contains {key}=...", file=sys.stderr)
        sys.exit(2)
    return value


def _mask_key(key: str) -> str:
    """Show first 6 and last 4 characters, mask the rest."""
    if len(key) <= 12:
        return key[:3] + "***" + key[-3:]
    return key[:6] + "***" + key[-4:]


def cmd_info() -> int:
    """Print connection info without revealing the full API key."""
    url = _get_env("ODOO_URL")
    db = _get_env("ODOO_DB")
    username = _get_env("ODOO_USERNAME")
    api_key = _get_env("ODOO_API_KEY")

    print("=== Odoo Connection Info ===")
    print(f"  URL:      {url}")
    print(f"  Database: {db}")
    print(f"  Username: {username}")
    print(f"  API Key:  {_mask_key(api_key)}")
    print(f"  .env:     {_ENV_PATH}")
    print()
    return 0


def cmd_verify() -> int:
    """Test that the current API key authenticates and can read hr.employee."""
    url = _get_env("ODOO_URL").rstrip("/")
    db = _get_env("ODOO_DB")
    username = _get_env("ODOO_USERNAME")
    api_key = _get_env("ODOO_API_KEY")

    print(f"Connecting to {url} (db={db}, user={username})...")

    # Step 1: Authenticate
    try:
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        uid = common.authenticate(db, username, api_key, {})
    except Exception as exc:
        print(f"FAILED: Could not connect to Odoo: {exc}", file=sys.stderr)
        return 1

    if not uid:
        print("FAILED: Authentication failed — API key is invalid or expired.", file=sys.stderr)
        print("  → Generate a new API key in Odoo (see docs/env_management.md)", file=sys.stderr)
        return 1

    print(f"  ✓ Authenticated as uid={uid}")

    # Step 2: Check server version
    try:
        version_info = common.version()
        server_version = version_info.get("server_version", "unknown")
        print(f"  ✓ Server version: {server_version}")
    except Exception as exc:
        print(f"  ⚠ Could not read server version: {exc}")

    # Step 3: Test read access on hr.employee (count only, no personal data)
    try:
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        count = models.execute_kw(
            db, uid, api_key, "hr.employee", "search_count", [[]]
        )
        print(f"  ✓ Read access to hr.employee: {count} records found")
    except Exception as exc:
        print(f"  ⚠ Could not read hr.employee: {exc}", file=sys.stderr)
        print("    (API key works for auth but may lack hr.employee permissions)", file=sys.stderr)

    # Step 4: Test read access on hr.department
    try:
        dept_count = models.execute_kw(
            db, uid, api_key, "hr.department", "search_count", [[]]
        )
        print(f"  ✓ Read access to hr.department: {dept_count} records found")
    except Exception as exc:
        print(f"  ⚠ Could not read hr.department: {exc}", file=sys.stderr)

    # Step 5: Test read access on hr.job
    try:
        job_count = models.execute_kw(
            db, uid, api_key, "hr.job", "search_count", [[]]
        )
        print(f"  ✓ Read access to hr.job: {job_count} records found")
    except Exception as exc:
        print(f"  ⚠ Could not read hr.job: {exc}", file=sys.stderr)

    print()
    print("API key verification: PASSED ✓")
    print(f"  Key (masked): {_mask_key(api_key)}")
    print()
    print("If you've just rotated the key, remember to:")
    print("  1. Delete the OLD key from Odoo (Settings → Users → API Keys)")
    print("  2. Run: python -m pytest tests/ -v")
    return 0


def main(argv=None) -> int:
    _load_dotenv()

    parser = argparse.ArgumentParser(
        description="Verify or display Odoo API key configuration (read-only, changes nothing)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--verify",
        action="store_true",
        help="Test that the current API key authenticates and can read hr.employee.",
    )
    group.add_argument(
        "--info",
        action="store_true",
        help="Show connection info without revealing the full API key.",
    )

    args = parser.parse_args(argv)

    if args.verify:
        return cmd_verify()
    elif args.info:
        return cmd_info()
    return 0


if __name__ == "__main__":
    sys.exit(main())
