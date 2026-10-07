#!/usr/bin/env python3
"""Retention management utility for dry-run reports and audit logs.

Complies with docs/data_retention_and_access_policy.md:
- Lists existing output folders with timestamp, age, and type.
- Safely cleans up expired dry-run reports older than a retention threshold (default: 30 days).
- STRICT SAFETY RULE: Never deletes permanent audit logs (writer_results_*.jsonl)
  or folders containing writer results.
- Runs in preview / dry-run mode by default; requires --execute to apply changes.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def is_writer_folder_or_audit(path: Path) -> bool:
    """Check if the given folder contains or is an audit writer result."""
    if not path.exists():
        return False
    if path.is_file():
        return path.name.startswith("writer_results_") and path.name.endswith(".jsonl")
    for item in path.rglob("writer_results_*.jsonl"):
        return True
    return False


def get_folder_info(folder: Path, now_utc: datetime | None = None) -> Dict[str, Any]:
    """Return metadata about an output folder."""
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    # Use modification time in UTC
    mtime = datetime.fromtimestamp(folder.stat().st_mtime, tz=timezone.utc)
    age_days = (now_utc - mtime).total_seconds() / 86400.0

    has_audit = is_writer_folder_or_audit(folder)
    has_dry_run = (folder / "dry_run_report.json").exists() or any(folder.glob("dry_run_report.*"))

    total_size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())

    return {
        "path": folder,
        "name": folder.name,
        "mtime": mtime,
        "age_days": round(age_days, 1),
        "is_audit": has_audit,
        "is_dry_run": has_dry_run,
        "size_bytes": total_size,
    }


def scan_output_directory(output_root: str | Path = "output") -> List[Dict[str, Any]]:
    """Scan output root directory and return sorted list of run directories."""
    root = Path(output_root)
    if not root.exists() or not root.is_dir():
        return []

    results = []
    now = datetime.now(timezone.utc)

    for item in root.iterdir():
        if item.is_dir():
            results.append(get_folder_info(item, now_utc=now))

    return sorted(results, key=lambda x: x["mtime"], reverse=True)


def clean_expired_reports(
    output_root: str | Path = "output",
    days: int = 30,
    execute: bool = False,
) -> Dict[str, Any]:
    """Clean dry-run reports older than the given days threshold.

    Returns summary dictionary with counts of inspected, eligible, deleted, and protected folders.
    """
    entries = scan_output_directory(output_root)
    now = datetime.now(timezone.utc)

    eligible_to_delete: List[Dict[str, Any]] = []
    protected_audit: List[Dict[str, Any]] = []
    retained_active: List[Dict[str, Any]] = []

    for entry in entries:
        if entry["is_audit"]:
            # Permanently preserved per policy
            protected_audit.append(entry)
        elif entry["age_days"] >= days:
            eligible_to_delete.append(entry)
        else:
            retained_active.append(entry)

    deleted_count = 0
    if execute:
        for entry in eligible_to_delete:
            folder_path: Path = entry["path"]
            # Double check audit safety before removal
            if not is_writer_folder_or_audit(folder_path):
                shutil.rmtree(folder_path, ignore_errors=True)
                deleted_count += 1

    return {
        "inspected_total": len(entries),
        "threshold_days": days,
        "eligible_for_deletion": len(eligible_to_delete),
        "deleted_count": deleted_count,
        "retained_active": len(retained_active),
        "protected_audit": len(protected_audit),
        "execute_mode": execute,
        "eligible_entries": eligible_to_delete,
        "protected_entries": protected_audit,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage retention of dry-run reports and audit logs in output/."
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Root output directory (default: 'output')",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Retention threshold in days for dry-run reports (default: 30)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete eligible expired reports (default: False, preview only)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all output runs with age, size, and category",
    )

    args = parser.parse_args(argv)
    output_path = Path(args.output_dir)

    if not output_path.exists():
        print(f"Output directory '{output_path}' does not exist.")
        return 0

    if args.list:
        runs = scan_output_directory(output_path)
        print(f"\n--- Output Runs in '{output_path}' (Total: {len(runs)}) ---")
        if not runs:
            print("No run folders found.")
        for r in runs:
            cat = "AUDIT (Permanent)" if r["is_audit"] else "Dry-Run"
            print(f"- {r['name']} | Category: {cat} | Age: {r['age_days']} days | Size: {r['size_bytes']} bytes")
        print("--------------------------------------------------\n")
        return 0

    summary = clean_expired_reports(
        output_root=output_path,
        days=args.days,
        execute=args.execute,
    )

    print("Retention Policy Check Summary:")
    print(f"- Directory: {output_path}")
    print(f"- Threshold: {args.days} days")
    print(f"- Inspected runs: {summary['inspected_total']}")
    print(f"- Active runs retained (< {args.days} days): {summary['retained_active']}")
    print(f"- Audit records protected (Permanent): {summary['protected_audit']}")
    print(f"- Expired dry-run runs: {summary['eligible_for_deletion']}")

    if summary["eligible_entries"]:
        print("\nExpired dry-run folders:")
        for e in summary["eligible_entries"]:
            print(f"  * {e['name']} (Age: {e['age_days']} days)")

    if not args.execute:
        if summary["eligible_for_deletion"] > 0:
            print("\n[Preview Mode]: No files were deleted. Run with --execute to perform deletion.")
        else:
            print("\n[Preview Mode]: Everything is within retention limits. Nothing to clean.")
    else:
        print(f"\n[Execution Completed]: Successfully removed {summary['deleted_count']} expired folder(s).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
