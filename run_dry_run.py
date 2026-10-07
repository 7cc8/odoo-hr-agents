from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from dry_run_report import build_full_report, write_report_files


def make_run_folder_name(run_id: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{run_id}_{timestamp}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only dry-run report generator. Never calls create/write/unlink on Odoo."
    )
    parser.add_argument("input_xlsx", help="Path to the source Excel file.")
    parser.add_argument(
        "--output-root",
        default="output",
        help="Root folder for dry-run outputs (default: output). "
        "Each run is written to a NEW timestamped subfolder; existing runs are never overwritten.",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input_xlsx)
    if not input_path.exists():
        samples_path = Path("samples") / input_path.name
        if samples_path.exists():
            input_path = samples_path
        else:
            print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
            return 2

    report_dict = build_full_report(input_path)

    run_id = report_dict["header"]["run_id"]
    folder_name = make_run_folder_name(run_id)
    output_dir = Path(args.output_root) / folder_name

    if output_dir.exists():
        # Timestamp collision is effectively impossible, but we refuse to
        # silently overwrite evidence tied to an approval decision.
        print(f"ERROR: output folder already exists, refusing to overwrite: {output_dir}", file=sys.stderr)
        return 3

    write_report_files(report_dict, output_dir)

    status_counts = report_dict["summary"]["status_counts"]
    row_count = report_dict["summary"]["row_count"]

    # Terminal output is counts and codes only — no names, no emails, no
    # company/department names, no phone numbers.
    print("Dry-run complete.")
    print(f"run_id: {run_id}")
    print(f"source_hash: {report_dict['header']['source_hash']}")
    print(f"total_rows: {row_count}")
    for status in ("accepted", "needs_review", "rejected"):
        print(f"{status}: {status_counts.get(status, 0)}")
    other_statuses = set(status_counts) - {"accepted", "needs_review", "rejected"}
    for status in sorted(other_statuses):
        print(f"{status}: {status_counts[status]}")
    print(f"output_folder: {output_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())