"""Append application records to a persistent CSV file."""
import csv
import time
from datetime import datetime
from pathlib import Path

FIELDS = [
    "timestamp", "company_name", "job_role", "location", "job_url",
    "original_ats_score", "original_verdict",
    "optimized_ats_score", "optimized_verdict",
    "eval_score", "jd_match_score",
    "eval_iterations", "corrections_count",
    "resume_path", "why_this_role", "why_this_company",
    "responsibilities", "start_date", "end_date",
    "job_description",
]


def log(data: dict, csv_path: str = "applications.csv") -> None:
    path = Path(csv_path)
    is_new = not path.exists()
    row = {f: str(data.get(f, "")).replace("\n", " ") for f in FIELDS}
    row["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    for attempt in range(10):
        try:
            with open(path, "a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=FIELDS)
                if is_new:
                    writer.writeheader()
                writer.writerow(row)
            return
        except PermissionError:
            if attempt == 0:
                print(f"\n      applications.csv is locked (open in Excel?). Close it and press Enter to retry...", end="", flush=True)
                input()
            else:
                print(f"      Retrying... ({attempt}/9)", flush=True)
                time.sleep(1)

    print("      Warning: could not write to applications.csv — skipping log.")
