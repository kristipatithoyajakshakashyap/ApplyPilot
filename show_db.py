#!/usr/bin/env python3
"""
View the ApplyPilot job database in the terminal.

Usage:
    python show_db.py                    # all jobs, all columns (vertical records)
    python show_db.py --status done      # filter by status
    python show_db.py --status scraped
    python show_db.py --status skipped
    python show_db.py --id 5             # full detail for one job
    python show_db.py --table            # compact horizontal summary table
    python show_db.py --import-csv jobs.csv          # seed DB from CSV
    python show_db.py --import-csv applications.csv
"""
import argparse
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("applypilot.db")

# All columns in display order, with optional truncation limit for long text
ALL_COLS = [
    ("id",                   None),
    ("status",               None),
    ("company_name",         None),
    ("job_role",             None),
    ("job_location",         None),
    ("location",             None),
    ("job_url",              80),
    ("original_ats_score",   None),
    ("original_verdict",     None),
    ("optimized_ats_score",  None),
    ("optimized_verdict",    None),
    ("eval_score",           None),
    ("jd_match_score",       None),
    ("eval_iterations",      None),
    ("corrections_count",    None),
    ("suggested_resume",     None),
    ("resume_path",          70),
    ("start_date",           None),
    ("end_date",             None),
    ("why_this_role",        120),
    ("why_this_company",     120),
    ("responsibilities",     120),
    ("scraped_at",           None),
    ("processed_at",         None),
    ("timestamp",            None),
    ("job_description",      200),
    ("jd_hash",              None),
]

# Compact table columns for --table mode
TABLE_COLS = [
    ("id",                   4),
    ("company_name",        22),
    ("job_role",            24),
    ("status",               8),
    ("original_ats_score",   5),
    ("optimized_ats_score",  5),
    ("eval_score",           5),
    ("jd_match_score",       5),
    ("eval_iterations",      4),
    ("corrections_count",    5),
    ("suggested_resume",    12),
    ("original_verdict",     6),
    ("optimized_verdict",    6),
    ("start_date",          10),
    ("location",            18),
    ("processed_at",        16),
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _fmt(val, limit: int | None) -> str:
    s = str(val) if val is not None else ""
    if limit and len(s) > limit:
        return s[:limit - 3] + "..."
    return s


def _trunc(val, width: int) -> str:
    s = str(val) if val is not None else ""
    return (s[:width - 1] + "~") if len(s) > width else s.ljust(width)


def _fetch(status_filter: str | None, row_id: int | None):
    if not DB_PATH.exists():
        print("No applypilot.db found. Run scrape_jobs.py or main.py first.")
        sys.exit(0)
    conn = _connect()
    if row_id is not None:
        rows = conn.execute("SELECT * FROM jobs WHERE id = ?", (row_id,)).fetchall()
    elif status_filter:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY id DESC", (status_filter,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def show_records(status_filter: str | None = None, row_id: int | None = None) -> None:
    """Vertical record view — shows every column for each job."""
    rows = _fetch(status_filter, row_id)
    if not rows:
        label = f"id={row_id}" if row_id else (f"status={status_filter}" if status_filter else "any")
        print(f"No jobs found ({label}).")
        return

    sep = "=" * 72
    col_w = max(len(c) for c, _ in ALL_COLS) + 2

    for row in rows:
        keys = row.keys()
        print(f"\n{sep}")
        print(f"  Job #{row['id']}  [{row['status'].upper()}]  {row['company_name']}  -  {row['job_role']}")
        print(sep)
        for col, limit in ALL_COLS:
            val = _fmt(row[col] if col in keys else None, limit)
            if val:
                label = (col + ":").ljust(col_w)
                print(f"  {label} {val}")
    print(f"\n{sep}")

    done    = sum(1 for r in rows if r["status"] == "done")
    scraped = sum(1 for r in rows if r["status"] == "scraped")
    skipped = sum(1 for r in rows if r["status"] == "skipped")
    print(f"  Total: {len(rows)}  |  done: {done}  |  scraped: {scraped}  |  skipped: {skipped}")
    print(sep)


def show_table(status_filter: str | None = None) -> None:
    """Compact horizontal table — summary view."""
    rows = _fetch(status_filter, None)
    if not rows:
        label = f"status={status_filter}" if status_filter else "any"
        print(f"No jobs found ({label}).")
        return

    keys = rows[0].keys() if rows else []
    header  = "  ".join(_trunc(col, w) for col, w in TABLE_COLS)
    divider = "  ".join("-" * w for _, w in TABLE_COLS)
    print(f"\n{header}\n{divider}")
    for row in rows:
        line = "  ".join(
            _trunc(row[col] if col in keys else "", w)
            for col, w in TABLE_COLS
        )
        print(line)

    done    = sum(1 for r in rows if r["status"] == "done")
    scraped = sum(1 for r in rows if r["status"] == "scraped")
    skipped = sum(1 for r in rows if r["status"] == "skipped")
    print(f"\n  Total: {len(rows)}  |  done: {done}  |  scraped: {scraped}  |  skipped: {skipped}")


def import_csv(csv_path: str) -> None:
    from src.db import init_db, import_from_csv
    init_db()
    n = import_from_csv(csv_path)
    print(f"Imported {n} new row(s) from {csv_path} into applypilot.db.")


def main() -> None:
    parser = argparse.ArgumentParser(description="View or seed the ApplyPilot job DB.")
    parser.add_argument("--status", choices=["done", "scraped", "skipped"],
                        help="Filter rows by status")
    parser.add_argument("--id", type=int, metavar="ROW_ID",
                        help="Show full detail for a single job by ID")
    parser.add_argument("--table", action="store_true",
                        help="Compact horizontal summary table instead of full record view")
    parser.add_argument("--import-csv", metavar="CSV_FILE",
                        help="Import an existing jobs.csv or applications.csv into the DB")
    args = parser.parse_args()

    if args.import_csv:
        if not Path(args.import_csv).exists():
            print(f"Error: file not found: {args.import_csv}")
            sys.exit(1)
        import_csv(args.import_csv)
        show_records()
    elif args.table:
        show_table(args.status)
    else:
        show_records(args.status, args.id)


if __name__ == "__main__":
    main()
