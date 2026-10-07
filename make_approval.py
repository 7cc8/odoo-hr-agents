"""Builds approval.json from an existing dry-run report. Offline; never touches Odoo.

Usage:
  py make_approval.py --report out/dry_run_report.json --list
  py make_approval.py --report out/dry_run_report.json --input test_employees_10.xlsx --approved-by khaled --rows 2 3 4
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--input")
    ap.add_argument("--approved-by")
    ap.add_argument("--rows", nargs="+", type=int, help="excel_row_number values to approve")
    ap.add_argument("--out", default="approval.json")
    args = ap.parse_args(argv)

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    rows = report["rows"]

    if args.list:
        print("excel_row  status         failure_code                 row_hash")
        for r in rows:
            print(f"{r['excel_row_number']:<10} {r['final_status']:<14} {str(r.get('failure_code') or ''):<28} {r['row_hash']}")
        return 0

    if not (args.input and args.approved_by and args.rows):
        print("ERROR: --input, --approved-by and --rows are required.", file=sys.stderr)
        return 2

    by_number = {r["excel_row_number"]: r for r in rows}
    unknown = [n for n in args.rows if n not in by_number]
    not_accepted = [n for n in args.rows if n in by_number and by_number[n]["final_status"] != "accepted"]
    duplicates = len(set(args.rows)) != len(args.rows)
    if unknown or not_accepted or duplicates:
        print(f"ERROR: unknown={unknown} not_accepted={not_accepted} duplicates={duplicates}", file=sys.stderr)
        return 2

    approval = {
        "run_id": report["header"]["run_id"],
        "source_hash": report["header"]["source_hash"],
        "source_file_name": Path(args.input).name,
        "approved_by": args.approved_by,
        "approved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "approved_row_hashes": [by_number[n]["row_hash"] for n in args.rows],
    }
    try:
        with open(args.out, "x", encoding="utf-8") as fh:
            json.dump(approval, fh, ensure_ascii=False, indent=2)
    except FileExistsError:
        print(f"ERROR: {args.out} already exists; delete it deliberately or use --out.", file=sys.stderr)
        return 2
    print(f"Wrote {args.out} with {len(args.rows)} row(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())